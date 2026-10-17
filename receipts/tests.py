from unittest import mock

import json

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Receipt, UserProfile
from .services import ocr


class UserProfileTests(TestCase):
    def test_profile_created_on_user_creation(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username="testuser", password="pass")
        profile, created = UserProfile.objects.get_or_create(user=user)
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(profile.telegram_chat_id, None)
        self.assertIsNotNone(profile.telegram_link_token)

    def test_profile_unique_token(self):
        from django.contrib.auth import get_user_model

        u1 = get_user_model().objects.create_user(username="u1", password="pass")
        u2 = get_user_model().objects.create_user(username="u2", password="pass")
        self.assertNotEqual(u1.profile.telegram_link_token, u2.profile.telegram_link_token)


class ReceiptTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(username="testuser", password="pass")
        self.receipt = Receipt.objects.create(
            user=self.user,
            origen="telegram",
            estado="pendiente_revision",
            archivo_original=SimpleUploadedFile("factura.jpg", b"fake-image-data"),
        )

    def test_receipt_default_state(self):
        self.assertEqual(self.receipt.estado, "pendiente_revision")

    def test_receipt_valid_fields(self):
        self.assertEqual(self.receipt.origen, "telegram")
        self.assertEqual(self.receipt.user, self.user)
        self.assertEqual(self.receipt.raw_ocr_json, None)

    def test_receipt_number_splitting_logic(self):
        self.receipt.numero_comprobante = "00005-00001234"
        self.receipt.save()
        pv, solo = ocr.procesar_numero_comprobante(self.receipt.numero_comprobante)
        self.assertEqual(pv, "00005")
        self.assertEqual(solo, "00001234")

    def test_receipt_number_no_separator(self):
        pv, solo = ocr.procesar_numero_comprobante("1234")
        self.assertEqual(pv, "")
        self.assertEqual(solo, "00001234")


class ReceiptStateMachineTests(TestCase):
    """Principio #6: zero tolerance para cambios de estado sin test de transición."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(username="testuser", password="pass")
        self.receipt = Receipt.objects.create(
            user=self.user,
            origen="telegram",
            estado="pendiente_revision",
        )

    def test_transition_revision_to_pending(self):
        self.assertEqual(self.receipt.estado, "pendiente_revision")
        self.receipt.estado = "pendiente_carga"
        self.receipt.save()
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.estado, "pendiente_carga")

    def test_transition_pending_to_loaded(self):
        self.receipt.estado = "pendiente_carga"
        self.receipt.save()
        self.receipt.estado = "cargado_en_siradig"
        self.receipt.save()
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.estado, "cargado_en_siradig")

    def test_transition_pending_to_error(self):
        self.receipt.estado = "pendiente_carga"
        self.receipt.save()
        self.receipt.estado = "error_carga"
        self.receipt.save()
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.estado, "error_carga")

    def test_state_values_valid(self):
        valid_states = {code: label for code, label in Receipt.ESTADO_CHOICES}
        for code, _ in Receipt.ESTADO_CHOICES:
            self.assertIn(code, valid_states, f"Estado {code} no existe en ESTADO_CHOICES")

    def test_only_supported_category_mvp(self):
        receipt = Receipt.objects.create(
            user=self.user,
            origen="telegram",
            estado="pendiente_revision",
            categoria_gasto_siradig="Gastos de Adquisición de Indumentaria y Equipamiento",
        )
        self.assertTrue(
            "Indumentaria" in receipt.categoria_gasto_siradig,
            "Solo la categoría de equipamiento está soportada en el MVP",
        )


class OCRServiceTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(username="testuser", password="pass")

    @mock.patch("google.genai.Client")
    def test_ocr_success_first_model(self, mock_client):
        fake_response = mock.MagicMock()
        fake_response.text = json.dumps(
            {
                "fecha_emision": "01/01/2024",
                "cuit_emisor": "20123456789",
                "razon_social": "EMPRESA TEST SA",
                "importe_total": 1000,
                "importe_iva": 210,
                "numero_comprobante": "00005-00001234",
                "categoria_gasto_siradig": "Gastos de Adquisición de Indumentaria y Equipamiento",
            }
        )
        mock_client.return_value.models.generate_content.return_value = fake_response

        datos = ocr.extraer_datos_factura(b"fake-image-payload")

        self.assertEqual(datos["cuit_emisor"], "20123456789")
        self.assertEqual(datos["razon_social"], "EMPRESA TEST SA")
        self.assertEqual(datos["importe_total"], 1000)
        self.assertEqual(datos["punto_venta"], "00005")
        self.assertEqual(datos["numero_solo"], "00001234")

    @mock.patch("google.genai.Client")
    def test_ocr_404_skips_model_and_retries_next(self, mock_client):
        from google.genai import errors as genai_errors

        class MockClientError(genai_errors.ClientError):
            def __init__(self, message, status_code):
                # Call parent with required response_json argument
                super().__init__(message, response_json={})
                self.status_code = status_code

        exc_404 = MockClientError("404 model deprecated", 404)
        fake_success = mock.MagicMock()
        fake_success.text = json.dumps({"fecha_emision": "02/02/2024", "cuit_emisor": "20198765432", "razon_social": "OK", "importe_total": 500})

        mock_client.return_value.models.generate_content.side_effect = [exc_404, fake_success]

        datos = ocr.extraer_datos_factura(b"fake-image-payload")
        self.assertEqual(datos["cuit_emisor"], "20198765432")

    @mock.patch("google.genai.Client")
    def test_ocr_429_retries_once_with_backoff(self, mock_client):
        from google.genai import errors as genai_errors

        class MockClientError(genai_errors.ClientError):
            def __init__(self, message, status_code):
                # Call parent with required response_json argument
                super().__init__(message, response_json={})
                self.status_code = status_code

        exc_429 = MockClientError("429 rate limit", 429)
        fake_success = mock.MagicMock()
        fake_success.text = json.dumps({
            "fecha_emision": "03/03/2024",
            "cuit_emisor": "20155555555",
            "razon_social": "BACKOFF",
            "importe_total": 300,
        })

        mock_client.return_value.models.generate_content.side_effect = [exc_429, exc_429, fake_success]

        datos = ocr.extraer_datos_factura(b"fake-image-payload")
        self.assertEqual(datos["cuit_emisor"], "20155555555")

    @mock.patch("google.genai.Client")
    def test_ocr_all_models_fail_raises(self, mock_client):
        from google.genai import errors as genai_errors

        class MockClientError(genai_errors.ClientError):
            def __init__(self, message, status_code):
                # Call parent with required response_json argument
                super().__init__(message, response_json={})
                self.status_code = status_code

        mock_client.return_value.models.generate_content.side_effect = MockClientError("No models available", 404)
        with self.assertRaises(genai_errors.ClientError):
            ocr.extraer_datos_factura(b"fake-image-payload")


class WebhookIntegrationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(username="testuser", password="pass")
        self.profile = UserProfile.objects.get(user=self.user)
        self.client = Client()

    @mock.patch("receipts.views.telegram_service")
    @mock.patch("receipts.views.ocr_service.extraer_datos_factura")
    def test_webhook_process_receipt_photo(self, mock_ocr, mock_tg):
        self.profile.telegram_chat_id = "123456"
        self.profile.save()

        mock_tg.get_file_path.return_value = "photos/file_0.jpg"
        mock_tg.download_file.return_value = b"fake-file-bytes"
        mock_tg.send_message.return_value = None

        mock_ocr.return_value = {
            "fecha_emision": "01/01/2024",
            "cuit_emisor": "20123456789",
            "razon_social": "EMPRESA TEST",
            "importe_total": 1000,
        }

        data = {
            "message": {
                "chat": {"id": 123456},
                "photo": [{"file_id": "FILE123", "file_unique_id": "UID123"}],
            }
        }
        response = self.client.post("/telegram/webhook/", data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        receipt = Receipt.objects.filter(user=self.user).first()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.estado, "pendiente_carga")
        self.assertEqual(receipt.razon_social, "EMPRESA TEST")

    @mock.patch("receipts.views.telegram_service")
    def test_webhook_no_linked_account(self, mock_tg):
        mock_tg.send_message.return_value = None

        data = {
            "message": {"chat": {"id": "999999"}, "text": "hola"},
        }
        response = self.client.post("/telegram/webhook/", data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 200)

    @mock.patch("receipts.views.telegram_service")
    @mock.patch("receipts.views.ocr_service.extraer_datos_factura")
    def test_webhook_link_account_start(self, mock_ocr, mock_tg):
        mock_ocr.return_value = {
            "fecha_emision": "01/01/2024",
            "cuit_emisor": "20123456789",
            "razon_social": "EMPRESA TEST",
            "importe_total": 1000,
        }
        mock_tg.send_message.return_value = None

        data = {
            "message": {
                "chat": {"id": "111111"},  # Different chat ID to avoid conflict
                "text": f"/start {self.profile.telegram_link_token}"
            }
        }
        response = self.client.post("/telegram/webhook/", data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.telegram_chat_id, "111111")


class APITests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(username="apiuser", password="pass")
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_pending_receipts_endpoint_returns_pending_only(self):
        Receipt.objects.create(user=self.user, origen="telegram", estado="pendiente_revision")
        Receipt.objects.create(user=self.user, origen="telegram", estado="pendiente_carga")
        Receipt.objects.create(user=self.user, origen="telegram", estado="cargado_en_siradig")

        response = self.api.get("/api/receipts/pending/")
        self.assertEqual(response.status_code, 200)
        results = response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["estado"], "pendiente_carga")

    def test_unauthenticated_requests_fails(self):
        noauth = APIClient()
        response = noauth.get("/api/receipts/pending/")
        self.assertEqual(response.status_code, 401)

    def test_update_receipt_endpoint(self):
        receipt = Receipt.objects.create(user=self.user, origen="telegram", estado="pendiente_carga")
        response = self.api.patch(f"/api/receipts/{receipt.id}/", {"estado": "cargado_en_siradig"})
        self.assertEqual(response.status_code, 200)
        receipt.refresh_from_db()
        self.assertEqual(receipt.estado, "cargado_en_siradig")

    def test_pending_receipts_payload_matches_spec_001_contract(self):
        """Valida que la respuesta de /api/receipts/pending/ contenga todos los campos requeridos por SPEC-001."""
        receipt = Receipt.objects.create(
            user=self.user,
            origen="telegram",
            estado="pendiente_carga",
            fecha_emision="15/06/2026",
            cuit_emisor="20123456789",
            razon_social="FARMACIA TEST",
            tipo_comprobante="Factura",
            letra="B",
            numero_comprobante="0001-00001234",
            punto_venta="0001",
            numero_solo="00001234",
            importe_total=15000.50,
            importe_iva=3150.10,
            categoria_gasto_siradig="Gastos de Adquisición de Indumentaria y Equipamiento",
        )
        response = self.api.get("/api/receipts/pending/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]

        expected_fields = [
            "id",
            "fecha_emision",
            "cuit_emisor",
            "razon_social",
            "tipo_comprobante",
            "letra",
            "numero_comprobante",
            "punto_venta",
            "numero_solo",
            "importe_total",
            "importe_iva",
            "categoria_gasto_siradig",
            "origen",
            "estado",
            "created_at",
        ]
        for field in expected_fields:
            self.assertIn(field, item, f"Campo {field} requerido por SPEC-001 no está en el payload")

        self.assertEqual(item["id"], receipt.id)
        self.assertEqual(item["cuit_emisor"], "20123456789")
        self.assertEqual(item["punto_venta"], "0001")
        self.assertEqual(item["numero_solo"], "00001234")
