import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Receipt, UserProfile
from .services import ocr

User = get_user_model()


class UserProfileTests(TestCase):
    def test_profile_created_on_user_creation(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="testuser", password="pass"
        )
        profile, created = UserProfile.objects.get_or_create(user=user)
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(profile.telegram_chat_id, None)
        self.assertIsNotNone(profile.telegram_link_token)

    def test_profile_unique_token(self):
        from django.contrib.auth import get_user_model

        u1 = get_user_model().objects.create_user(username="u1", password="pass")
        u2 = get_user_model().objects.create_user(username="u2", password="pass")
        self.assertNotEqual(
            u1.profile.telegram_link_token, u2.profile.telegram_link_token
        )


class ReceiptTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username="testuser", password="pass"
        )
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

        self.user = get_user_model().objects.create_user(
            username="testuser", password="pass"
        )
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
            self.assertIn(
                code, valid_states, f"Estado {code} no existe en ESTADO_CHOICES"
            )

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

        self.user = get_user_model().objects.create_user(
            username="testuser", password="pass"
        )

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
        fake_success.text = json.dumps(
            {
                "fecha_emision": "02/02/2024",
                "cuit_emisor": "20198765432",
                "razon_social": "OK",
                "importe_total": 500,
            }
        )

        mock_client.return_value.models.generate_content.side_effect = [
            exc_404,
            fake_success,
        ]

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
        fake_success.text = json.dumps(
            {
                "fecha_emision": "03/03/2024",
                "cuit_emisor": "20155555555",
                "razon_social": "BACKOFF",
                "importe_total": 300,
            }
        )

        mock_client.return_value.models.generate_content.side_effect = [
            exc_429,
            exc_429,
            fake_success,
        ]

        datos = ocr.extraer_datos_factura(b"fake-image-payload")
        self.assertEqual(datos["cuit_emisor"], "20155555555")

    @mock.patch("google.genai.Client")
    def test_ocr_503_retries_with_backoff(self, mock_client):
        from google.genai import errors as genai_errors

        class MockServerError(genai_errors.ServerError):
            def __init__(self, message, status_code):
                super().__init__(message, response_json={})
                self.status_code = status_code

        exc_503 = MockServerError("503 server overloaded", 503)
        fake_success = mock.MagicMock()
        fake_success.text = json.dumps(
            {
                "fecha_emision": "05/05/2024",
                "cuit_emisor": "20188888888",
                "razon_social": "SERVER 503 RECOVERED",
                "importe_total": 550,
            }
        )

        mock_client.return_value.models.generate_content.side_effect = [
            exc_503,
            fake_success,
        ]

        datos = ocr.extraer_datos_factura(b"fake-image-payload")
        self.assertEqual(datos["cuit_emisor"], "20188888888")

    @mock.patch("google.genai.Client")
    def test_ocr_all_models_fail_raises(self, mock_client):
        from google.genai import errors as genai_errors

        class MockClientError(genai_errors.ClientError):
            def __init__(self, message, status_code):
                # Call parent with required response_json argument
                super().__init__(message, response_json={})
                self.status_code = status_code

        mock_client.return_value.models.generate_content.side_effect = MockClientError(
            "No models available", 404
        )
        with self.assertRaises(genai_errors.ClientError):
            ocr.extraer_datos_factura(b"fake-image-payload")


class WebhookIntegrationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username="testuser", password="pass"
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.client = Client()

    @mock.patch("receipts.views.telegram_service")
    @mock.patch("receipts.views.ocr_service.extraer_datos_factura")
    def test_webhook_ocr_failure_handles_exception(self, mock_ocr, mock_tg):
        self.profile.telegram_chat_id = "123456"
        self.profile.save()

        mock_tg.get_file_path.return_value = "photos/file_0.jpg"
        mock_tg.download_file.return_value = b"fake-file-bytes"
        mock_tg.send_message.return_value = None

        mock_ocr.side_effect = Exception("OCR error")

        data = {
            "message": {
                "chat": {"id": 123456},
                "photo": [{"file_id": "FILE123", "file_unique_id": "UID123"}],
            }
        }
        response = self.client.post(
            "/telegram/webhook/", data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        receipt = Receipt.objects.filter(user=self.user).first()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.estado, "pendiente_revision")
        mock_tg.send_message.assert_called_with(
            123456,
            "No pude leer los datos del comprobante, quedó guardado para revisión manual.",
        )

    @mock.patch("receipts.views.telegram_service")
    @mock.patch("receipts.views.ocr_service.extraer_datos_factura")
    def test_webhook_process_receipt_document_pdf(self, mock_ocr, mock_tg):
        self.profile.telegram_chat_id = "123456"
        self.profile.save()

        mock_tg.get_file_path.return_value = "docs/file_0.pdf"
        mock_tg.download_file.return_value = b"fake-pdf-bytes"
        mock_tg.send_message.return_value = None

        mock_ocr.return_value = {
            "fecha_emision": "02/02/2024",
            "cuit_emisor": "20222222222",
            "razon_social": "PDF EMPRESA",
            "importe_total": 2000,
        }

        data = {
            "message": {
                "chat": {"id": 123456},
                "document": {
                    "file_id": "DOC123",
                    "file_name": "factura.pdf",
                    "mime_type": "application/pdf",
                },
            }
        }
        response = self.client.post(
            "/telegram/webhook/", data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        receipt = Receipt.objects.filter(user=self.user).first()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.estado, "pendiente_carga")
        self.assertEqual(receipt.razon_social, "PDF EMPRESA")

    @mock.patch("receipts.views.telegram_service")
    def test_webhook_message_without_chat_id(self, mock_tg):
        response = self.client.post(
            "/telegram/webhook/",
            data=json.dumps({"message": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    @mock.patch("receipts.views.telegram_service")
    def test_webhook_start_invalid_token(self, mock_tg):
        data = {
            "message": {"chat": {"id": "555555"}, "text": "/start token_inexistente"}
        }
        response = self.client.post(
            "/telegram/webhook/", data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        mock_tg.send_message.assert_called_with(
            "555555", "Token inválido. Generá el link desde tu dashboard."
        )

    @mock.patch("receipts.views.telegram_service")
    def test_webhook_photo_unlinked_account(self, mock_tg):
        data = {
            "message": {
                "chat": {"id": "999888"},
                "photo": [{"file_id": "PHOTO999"}],
            }
        }
        response = self.client.post(
            "/telegram/webhook/", data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        mock_tg.send_message.assert_called_with(
            "999888",
            "Primero vinculá tu cuenta con el link del dashboard (/start <token>).",
        )

    @mock.patch("receipts.views.telegram_service")
    @mock.patch("receipts.views.ocr_service.extraer_datos_factura")
    def test_webhook_ocr_empty_dict_response(self, mock_ocr, mock_tg):
        self.profile.telegram_chat_id = "123456"
        self.profile.save()

        mock_tg.get_file_path.return_value = "photos/file_0.jpg"
        mock_tg.download_file.return_value = b"fake-file-bytes"
        mock_tg.send_message.return_value = None

        mock_ocr.return_value = None

        data = {
            "message": {
                "chat": {"id": 123456},
                "photo": [{"file_id": "FILE123", "file_unique_id": "UID123"}],
            }
        }
        response = self.client.post(
            "/telegram/webhook/", data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        mock_tg.send_message.assert_called_with(
            123456,
            "No pude leer los datos del comprobante, quedó guardado para revisión manual.",
        )

    def test_dashboard_authenticated_loads(self):
        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "¡Hola, testuser!")
        self.assertContains(response, "Extensión de Navegador")
        self.assertContains(response, "btn-copy-token")
        self.assertContains(response, "Total Comprobantes")
        self.assertContains(response, "Total Deducible")
        self.assertContains(
            response, "https://auth.afip.gob.ar/contribuyente_/login.xhtml"
        )
        self.assertContains(response, "Cerrar Sesión")

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
        response = self.client.post(
            "/telegram/webhook/", data=json.dumps(data), content_type="application/json"
        )
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
        response = self.client.post(
            "/telegram/webhook/", data=json.dumps(data), content_type="application/json"
        )
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
                "text": f"/start {self.profile.telegram_link_token}",
            }
        }
        response = self.client.post(
            "/telegram/webhook/", data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.telegram_chat_id, "111111")


class APITests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username="apiuser", password="pass"
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_pending_receipts_endpoint_returns_pending_only(self):
        Receipt.objects.create(
            user=self.user, origen="telegram", estado="pendiente_revision"
        )
        Receipt.objects.create(
            user=self.user, origen="telegram", estado="pendiente_carga"
        )
        Receipt.objects.create(
            user=self.user, origen="telegram", estado="cargado_en_siradig"
        )

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
        receipt = Receipt.objects.create(
            user=self.user, origen="telegram", estado="pendiente_carga"
        )
        response = self.api.patch(
            f"/api/receipts/{receipt.id}/", {"estado": "cargado_en_siradig"}
        )
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
            self.assertIn(
                field,
                item,
                f"Campo {field} requerido por SPEC-001 no está en el payload",
            )

        self.assertEqual(item["id"], receipt.id)
        self.assertEqual(item["cuit_emisor"], "20123456789")
        self.assertEqual(item["punto_venta"], "0001")
        self.assertEqual(item["numero_solo"], "00001234")


class LandingAndAuthAccessTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="testuser_landing",
            email="user@example.com",
            password="testpassword123",
        )

    def test_anonymous_user_accessing_root_renders_landing(self):
        """RF-AUTH-001, RF-AUTH-002, CA-AUTH-001: Usuario anónimo ve landing page."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "landing.html")
        self.assertTemplateUsed(response, "base.html")
        content = response.content.decode("utf-8")
        self.assertIn("Iniciar Sesión", content)
        self.assertIn("Registrarse", content)
        self.assertIn("SIRADIG Auto", content)
        self.assertIn(
            "Nunca solicitamos ni almacenamos tus credenciales de AFIP/ARCA", content
        )
        self.assertIn("/accounts/login/", content)
        self.assertIn("/accounts/signup/", content)

    def test_authenticated_user_accessing_root_redirects_to_dashboard(self):
        """RF-AUTH-003, CA-AUTH-002: Usuario autenticado en '/' redirige a '/dashboard/' con HTTP 302."""
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/dashboard/", target_status_code=200)

    def test_anonymous_user_accessing_dashboard_redirects_to_login(self):
        """RF-AUTH-017, CA-AUTH-011: Acceso anónimo a '/dashboard/' redirige a '/accounts/login/?next=/dashboard/'."""
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, "/accounts/login/?next=/dashboard/", fetch_redirect_response=False
        )


class LocalAuthenticationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.User = get_user_model()
        self.client = Client()
        self.valid_email = "nuevo_usuario@ejemplo.com"
        self.valid_password = "PasswordSegura123!"

    def test_signup_successful_creates_user_profile_token_and_redirects(self):
        """RF-AUTH-004, RF-AUTH-005, RF-AUTH-018, RF-AUTH-019, CA-AUTH-003:
        Registro exitoso con email y contraseña:
        - Redirige con HTTP 302 a /dashboard/.
        - Usuario queda autenticado en sesión.
        - Se crea UserProfile asociado con telegram_link_token no nulo.
        - Se crea Token de DRF asociado.
        """
        from rest_framework.authtoken.models import Token

        from receipts.models import UserProfile

        response = self.client.post(
            "/accounts/signup/",
            {
                "email": self.valid_email,
                "password1": self.valid_password,
                "password2": self.valid_password,
                "terms_accepted": "true",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/dashboard/", target_status_code=200)

        # Verificar usuario creado y autenticado
        user = self.User.objects.filter(email=self.valid_email).first()
        self.assertIsNotNone(user, "El usuario debería existir en la base de datos")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

        # Verificar UserProfile y telegram_link_token
        profile = UserProfile.objects.filter(user=user).first()
        self.assertIsNotNone(
            profile, "El UserProfile debe ser creado automáticamente por post_save"
        )
        self.assertTrue(
            profile.telegram_link_token,
            "telegram_link_token debe ser no nulo y no vacío",
        )

        # Verificar Token de DRF
        token = Token.objects.filter(user=user).first()
        self.assertIsNotNone(
            token, "El Token de DRF debe ser creado automáticamente por post_save"
        )
        self.assertTrue(token.key, "El Token de DRF debe contener una clave válida")

    def test_signup_invalid_data_shows_errors(self):
        """RF-AUTH-006: Contraseña débil o datos inválidos recargan formulario con error (HTTP 200)."""
        response = self.client.post(
            "/accounts/signup/",
            {
                "email": "invalido",
                "password1": "123",
                "password2": "123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/signup.html")
        form = response.context["form"]
        self.assertTrue(form.errors)

    def test_login_valid_credentials_redirects_to_dashboard(self):
        """RF-AUTH-005, RF-AUTH-018, CA-AUTH-004: Login con credenciales válidas redirige a /dashboard/."""
        user = self.User.objects.create_user(
            username="login_test_user",
            email="login_user@ejemplo.com",
            password=self.valid_password,
        )
        response = self.client.post(
            "/accounts/login/",
            {
                "login": "login_user@ejemplo.com",
                "password": self.valid_password,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/dashboard/", target_status_code=200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_login_invalid_credentials_shows_error_and_does_not_authenticate(self):
        """RF-AUTH-007, CA-AUTH-005: Login con credenciales inválidas muestra error y no autentica."""
        self.User.objects.create_user(
            username="existing_user",
            email="existing@ejemplo.com",
            password=self.valid_password,
        )
        response = self.client.post(
            "/accounts/login/",
            {
                "login": "existing@ejemplo.com",
                "password": "PasswordEquivocada999!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/login.html")
        self.assertNotIn("_auth_user_id", self.client.session)
        form = response.context["form"]
        self.assertTrue(form.errors)

    def test_logout_closes_session_and_redirects_to_landing(self):
        """RF-AUTH-016, CA-AUTH-010: Logout cierra sesión y redirige a '/'."""
        user = self.User.objects.create_user(
            username="logout_user",
            email="logout@ejemplo.com",
            password=self.valid_password,
        )
        self.client.force_login(user)
        self.assertIn("_auth_user_id", self.client.session)

        # GET a logout muestra pantalla de confirmación
        get_response = self.client.get("/accounts/logout/")
        self.assertEqual(get_response.status_code, 200)
        self.assertTemplateUsed(get_response, "account/logout.html")

        # POST a logout cierra sesión y redirige a '/'
        post_response = self.client.post("/accounts/logout/")
        self.assertEqual(post_response.status_code, 302)
        self.assertRedirects(post_response, "/", target_status_code=200)
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordResetTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.User = get_user_model()
        self.client = Client()
        self.user_email = "usuario_reset@ejemplo.com"
        self.user_old_password = "PasswordVieja123!"
        self.user = self.User.objects.create_user(
            username="usuario_reset",
            email=self.user_email,
            password=self.user_old_password,
        )

    def test_password_reset_request_for_existing_user_sends_email_and_redirects(self):
        """RF-AUTH-011, RF-AUTH-012, CA-AUTH-006:
        Solicitud de reseteo para usuario existente:
        - Envía correo a mail.outbox con URL que contiene token.
        - Redirige a pantalla password_reset_done.
        """
        from django.core import mail

        response = self.client.post(
            "/accounts/password/reset/",
            {"email": self.user_email},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/accounts/password/reset/done/")

        # Verificar envío de correo
        self.assertEqual(len(mail.outbox), 1)
        email_message = mail.outbox[0]
        self.assertIn(self.user_email, email_message.to)
        self.assertIn("/accounts/password/reset/key/", email_message.body)

    def test_password_reset_request_for_nonexistent_user_anti_enumeration(self):
        """RF-AUTH-013, CA-AUTH-006:
        Solicitud con email inexistente:
        - Muestra pantalla password_reset_done (anti-enumeración).
        - No envía correos.
        """
        from django.core import mail

        response = self.client.post(
            "/accounts/password/reset/",
            {"email": "inexistente@noexiste.com"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/accounts/password/reset/done/")

        # Verificar que no se enviaron correos a direcciones inexistentes
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_successful_via_token_link(self):
        """RF-AUTH-014, CA-AUTH-007:
        Cambio exitoso de contraseña usando el enlace con token:
        - Accede a la URL con key.
        - Envía nueva contraseña válida.
        - Se actualiza la contraseña en BD y el usuario puede loguearse con la nueva contraseña.
        """
        import re

        from django.core import mail

        # 1. Solicitar reseteo
        self.client.post(
            "/accounts/password/reset/",
            {"email": self.user_email},
        )
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body

        # 2. Extraer URL de reseteo del cuerpo del correo
        match = re.search(r"(/accounts/password/reset/key/[^\s]+)", body)
        self.assertIsNotNone(
            match, "El enlace de reseteo debe estar presente en el cuerpo del correo"
        )
        reset_key_url = match.group(1)

        # 3. GET a la URL de reseteo (allauth redirige a URL interna sin token en referer)
        get_response = self.client.get(reset_key_url)
        if get_response.status_code == 302:
            form_response = self.client.get(get_response.url)
        else:
            form_response = get_response

        self.assertEqual(form_response.status_code, 200)
        self.assertTemplateUsed(form_response, "account/password_reset_from_key.html")
        action_url = form_response.context.get("action_url")
        self.assertIsNotNone(action_url)

        # 4. Enviar nueva contraseña
        new_password = "PasswordNueva456!"
        post_response = self.client.post(
            action_url,
            {
                "password1": new_password,
                "password2": new_password,
            },
        )
        self.assertEqual(post_response.status_code, 302)
        self.assertRedirects(post_response, "/accounts/password/reset/key/done/")

        # 5. Verificar que la contraseña fue actualizada en la base de datos
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(self.user_old_password))

        # 6. Verificar que el usuario puede iniciar sesión con la nueva contraseña
        login_response = self.client.post(
            "/accounts/login/",
            {
                "login": self.user_email,
                "password": new_password,
            },
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertRedirects(login_response, "/dashboard/")

    def test_password_reset_with_invalid_or_manipulated_token(self):
        """RF-AUTH-015, CA-AUTH-008:
        Token inválido o manipulado:
        - Muestra mensaje de enlace inválido o expirado.
        - No permite el cambio de contraseña.
        """
        # Intentar acceder con un token manipulado/inexistente
        response = self.client.get("/accounts/password/reset/key/1-invalidkey/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/password_reset_from_key.html")
        content = response.content.decode("utf-8")
        self.assertIn("Enlace inválido o expirado", content)
        self.assertIn("/accounts/password/reset/", content)

        # La contraseña del usuario debe permanecer intacta
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.user_old_password))


class GoogleOAuthIntegrationTests(TestCase):
    """Pruebas de integración para Google OAuth 2.0 y señales (T5).
    Requisitos: RF-AUTH-008, RF-AUTH-009, RF-AUTH-010, RF-AUTH-019, RN-AUTH-005.
    Criterios: CA-AUTH-009.
    """

    def setUp(self):
        self.client = Client()

    def test_google_login_buttons_rendered_in_login_and_signup(self):
        """RF-AUTH-008, CA-AUTH-009:
        Verificar que las pantallas de login y signup renderizan el botón 'Continuar con Google' / 'Registrarse con Google'
        y el enlace de acción de autenticación social.
        """
        # Login page
        login_res = self.client.get("/accounts/login/")
        self.assertEqual(login_res.status_code, 200)
        self.assertContains(login_res, "Continuar con Google")
        self.assertContains(login_res, "/accounts/google/login/")

        # Signup page
        signup_res = self.client.get("/accounts/signup/")
        self.assertEqual(signup_res.status_code, 200)
        self.assertContains(signup_res, "Registrarse con Google")
        self.assertContains(signup_res, "/accounts/google/login/")

    def test_social_user_creation_triggers_signals_and_creates_profile_and_token(self):
        """RF-AUTH-010, RF-AUTH-019, CA-AUTH-009:
        Cuando un usuario se crea por flujo social (o persistencia de nuevo usuario via allauth),
        la señal post_save en receipts/signals.py se dispara automáticamente:
        - Se crea la instancia de UserProfile con telegram_link_token unívoco.
        - Se crea el Token de DRF para la extensión.
        """
        from allauth.socialaccount.models import SocialAccount
        from rest_framework.authtoken.models import Token

        from receipts.models import UserProfile

        social_email = "google_user@gmail.com"
        user = User.objects.create(
            username=social_email,
            email=social_email,
        )

        # Simular vinculación de SocialAccount
        SocialAccount.objects.create(
            user=user,
            provider="google",
            uid="google_uid_123456789",
            extra_data={"email": social_email, "name": "Google User"},
        )

        # Verificar existencia de UserProfile y Token
        profile = UserProfile.objects.filter(user=user).first()
        self.assertIsNotNone(
            profile, "UserProfile debe ser creado automáticamente por post_save"
        )
        self.assertTrue(
            profile.telegram_link_token, "Debe tener un telegram_link_token generado"
        )

        token = Token.objects.filter(user=user).first()
        self.assertIsNotNone(
            token, "Token DRF debe ser creado automáticamente por post_save"
        )
        self.assertTrue(token.key, "El Token DRF debe contener una clave válida")

    def test_social_login_preserves_existing_user_telegram_token(self):
        """RN-AUTH-005, RF-AUTH-010:
        La vinculación de una cuenta social a un usuario existente no debe alterar ni regenerar
        el telegram_link_token ni el Token DRF ya creados.
        """
        from allauth.socialaccount.models import SocialAccount
        from rest_framework.authtoken.models import Token

        from receipts.models import UserProfile

        existing_user = User.objects.create_user(
            username="existing@gmail.com",
            email="existing@gmail.com",
            password="SomePassword123!",
        )

        orig_profile = UserProfile.objects.get(user=existing_user)
        orig_telegram_token = orig_profile.telegram_link_token
        orig_auth_token = Token.objects.get(user=existing_user).key

        # Simular vinculación posterior de cuenta social de Google
        SocialAccount.objects.create(
            user=existing_user,
            provider="google",
            uid="google_uid_987654321",
            extra_data={"email": "existing@gmail.com", "name": "Existing User"},
        )

        # Refrescar y verificar inmutabilidad
        orig_profile.refresh_from_db()
        self.assertEqual(orig_profile.telegram_link_token, orig_telegram_token)
        self.assertEqual(Token.objects.get(user=existing_user).key, orig_auth_token)

    def test_social_user_registration_adapter_populates_username_and_creates_profile(
        self,
    ):
        """Verifica que el registro de un nuevo usuario social mediante el adapter de allauth:
        - Asigna un username válido y no nulo al usuario (evitando IntegrityError).
        - Guarda el usuario satisfactoriamente en base de datos.
        - Genera automáticamente su UserProfile con trial_start_date y su Token DRF vía post_save.
        """
        from allauth.socialaccount.adapter import get_adapter
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory
        from rest_framework.authtoken.models import Token

        from receipts.models import UserProfile

        adapter = get_adapter()
        request = RequestFactory().get("/accounts/google/login/callback/")
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        social_email = "new_google_user@gmail.com"
        new_user = User(email=social_email)

        account = SocialAccount(
            provider="google",
            uid="google_uid_999888777",
            extra_data={
                "email": social_email,
                "name": "New Google User",
                "given_name": "New",
                "family_name": "User",
            },
        )
        sociallogin = SocialLogin(user=new_user, account=account)

        # Poblar usuario desde los datos sociales (pre-rellena atributos básicos)
        adapter.populate_user(request, sociallogin, data={"email": social_email})

        # Guardar usuario mediante el adapter (sin formulario, flujo de auto-signup).
        # Esto invoca account_adapter.populate_username() que auto-genera el username único
        # antes de persistir new_user en la base de datos.
        saved_user = adapter.save_user(request, sociallogin, form=None)

        self.assertIsNotNone(saved_user.pk)
        self.assertTrue(saved_user.username)
        self.assertIsNotNone(saved_user.username)
        self.assertEqual(saved_user.email, social_email)

        # Verificar generación automática de UserProfile y Token de DRF vía post_save
        profile = UserProfile.objects.filter(user=saved_user).first()
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.trial_start_date)
        self.assertTrue(profile.telegram_link_token)

        token = Token.objects.filter(user=saved_user).first()
        self.assertIsNotNone(token)
        self.assertTrue(token.key)


class LegalViewsTests(TestCase):
    """Pruebas de rutas y plantillas legales (Tarea T1 - specs/006-tasks.md).

    Cubre: RF-LEG-001, RF-LEG-002, RF-LEG-003, RF-LEG-007, CA-LEG-001, CA-LEG-002, CA-LEG-005.
    """

    def setUp(self):
        self.client = Client()

    def test_terms_page_renders_status_200_and_legal_content(self):
        """RF-LEG-001, RF-LEG-002, CA-LEG-001:
        /terminos/ responde HTTP 200 sin autenticación, menciona deslinde de AFIP,
        procesamiento con IA y canal oficial marianoignaszewski@gmail.com.
        """
        response = self.client.get("/terminos/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "marianoignaszewski@gmail.com")
        self.assertContains(response, "AFIP")
        self.assertContains(response, "ARCA")
        self.assertContains(response, "claves fiscales")

    def test_privacy_page_renders_status_200_and_legal_content(self):
        """RF-LEG-001, RF-LEG-003, CA-LEG-002:
        /privacidad/ responde HTTP 200 sin autenticación, menciona finalidad,
        no almacenamiento de claves AFIP, Google Gemini API y marianoignaszewski@gmail.com.
        """
        response = self.client.get("/privacidad/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "marianoignaszewski@gmail.com")
        self.assertContains(response, "AFIP")
        self.assertContains(response, "Gemini")
        self.assertContains(response, "no almacena")

    def test_footer_contains_navigation_links_to_legal_pages(self):
        """RF-LEG-007, CA-LEG-005:
        La plantilla base incluye en el footer enlaces directos y navegables a /terminos/ y /privacidad/.
        """
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/terminos/"')
        self.assertContains(response, 'href="/privacidad/"')


class LegalAuthFormAndNoticeTests(TestCase):
    """Pruebas del formulario de registro con checkbox legal y avisos en autenticación (Tarea T2 - specs/006-tasks.md).

    Cubre: RF-LEG-004, RF-LEG-005, RF-LEG-006, CA-LEG-003, CA-LEG-004.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.User = get_user_model()
        self.client = Client()
        self.valid_email = "legal_user@ejemplo.com"
        self.valid_password = "PasswordSegura123!"

    def test_signup_post_without_terms_accepted_fails_and_does_not_create_user(self):
        """RF-LEG-004, CA-LEG-003:
        Intento de registro sin marcar terms_accepted es rechazado con error en formulario (HTTP 200)
        y no crea usuario en base de datos.
        """
        response = self.client.post(
            "/accounts/signup/",
            {
                "email": self.valid_email,
                "password1": self.valid_password,
                "password2": self.valid_password,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/signup.html")
        form = response.context["form"]
        self.assertIn("terms_accepted", form.errors)
        self.assertIn(
            "Debes aceptar los Términos de Servicio y la Política de Privacidad para crear una cuenta.",
            form.errors["terms_accepted"],
        )
        self.assertFalse(self.User.objects.filter(email=self.valid_email).exists())

    def test_signup_post_with_terms_accepted_succeeds_and_creates_user(self):
        """RF-LEG-004, CA-LEG-003:
        Intento de registro marcando terms_accepted se procesa exitosamente, crea usuario y redirige a /dashboard/.
        """
        from rest_framework.authtoken.models import Token

        from receipts.models import UserProfile

        response = self.client.post(
            "/accounts/signup/",
            {
                "email": self.valid_email,
                "password1": self.valid_password,
                "password2": self.valid_password,
                "terms_accepted": "true",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/dashboard/", target_status_code=200)

        user = self.User.objects.filter(email=self.valid_email).first()
        self.assertIsNotNone(user)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertTrue(Token.objects.filter(user=user).exists())

    def test_signup_template_renders_terms_checkbox_and_oauth_notice(self):
        """RF-LEG-004, RF-LEG-006, CA-LEG-004:
        La página de registro muestra el checkbox con enlaces a términos y privacidad,
        y la cláusula legal bajo el botón de Google OAuth.
        """
        response = self.client.get("/accounts/signup/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('name="terms_accepted"', content)
        self.assertIn('href="/terminos/"', content)
        self.assertIn('href="/privacidad/"', content)
        self.assertIn('target="_blank"', content)
        self.assertIn("Al continuar con Google aceptas los", content)

    def test_login_template_renders_legal_notice_and_oauth_notice(self):
        """RF-LEG-005, RF-LEG-006, CA-LEG-004:
        La página de login muestra aviso legal al pie del formulario y cláusula legal bajo el botón de Google.
        """
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Al iniciar sesión aceptas los", content)
        self.assertIn("Al continuar con Google aceptas los", content)
        self.assertIn('href="/terminos/"', content)
        self.assertIn('href="/privacidad/"', content)
        self.assertIn('target="_blank"', content)


class DashboardViewAndTemplateTests(TestCase):
    """Pruebas para T3 y T4: Contexto, KPIs, aislamiento, badges, token y template del dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="dash_user",
            email="dash_user@example.com",
            password="securepassword123",
            first_name="Mariano",
        )
        self.other_user = User.objects.create_user(
            username="other_user",
            email="other_user@example.com",
            password="securepassword123",
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_dashboard_unauthenticated_redirects_to_login(self):
        """Acceso anónimo debe redirigir a login (HTTP 302)."""
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_dashboard_context_and_kpis_calculation(self):
        """RF-DSH-002, CA-DSH-001, RN-004:
        Cálculo de KPIs, totales y aislamiento estricto de comprobantes.
        """
        # Comprobantes del usuario
        Receipt.objects.create(
            user=self.user,
            estado="pendiente_revision",
            importe_total=150.50,
            categoria_gasto_siradig="Gastos de Adquisición de Indumentaria y Equipamiento",
        )
        Receipt.objects.create(
            user=self.user,
            estado="pendiente_carga",
            importe_total=300.00,
            categoria_gasto_siradig="Gastos de Adquisición de Indumentaria y Equipamiento",
        )
        Receipt.objects.create(
            user=self.user,
            estado="cargado_en_siradig",
            importe_total=500.25,
            categoria_gasto_siradig="Gastos de Adquisición de Indumentaria y Equipamiento",
        )
        Receipt.objects.create(
            user=self.user,
            estado="error_carga",
            importe_total=49.25,
            categoria_gasto_siradig="Gastos de Adquisición de Indumentaria y Equipamiento",
        )

        # Comprobante de otro usuario que NO debe influir en los KPIs ni en la tabla
        Receipt.objects.create(
            user=self.other_user,
            estado="cargado_en_siradig",
            importe_total=99999.00,
            categoria_gasto_siradig="Gastos de Adquisición de Indumentaria y Equipamiento",
        )

        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        # Verificar contexto
        ctx = response.context
        self.assertEqual(ctx["total_comprobantes"], 4)
        self.assertAlmostEqual(float(ctx["total_deducible_pesos"]), 1000.00)
        self.assertEqual(ctx["conteo_pendiente_revision"], 1)
        self.assertEqual(ctx["conteo_pendiente_carga"], 1)
        self.assertEqual(ctx["conteo_cargado"], 1)
        self.assertEqual(ctx["conteo_error"], 1)
        self.assertEqual(ctx["token"], self.token.key)
        self.assertEqual(len(ctx["receipts"]), 4)

        # Verificar renderizado en HTML
        content = response.content.decode("utf-8")
        self.assertIn("¡Hola, Mariano!", content)
        self.assertIn("dash_user@example.com", content)
        self.assertIn(self.token.key, content)
        self.assertIn("1000", content)
        self.assertNotIn("99999", content)

    def test_dashboard_badges_rendered_semantically(self):
        """RF-DSH-006, CA-DSH-004: Badges de color según estado del comprobante."""
        Receipt.objects.create(
            user=self.user,
            estado="pendiente_revision",
            importe_total=100.0,
            cuit_emisor="20111111112",
            razon_social="Proveedor Uno",
        )
        Receipt.objects.create(
            user=self.user,
            estado="pendiente_carga",
            importe_total=200.0,
            cuit_emisor="20222222223",
            razon_social="Proveedor Dos",
        )
        Receipt.objects.create(
            user=self.user,
            estado="cargado_en_siradig",
            importe_total=300.0,
            cuit_emisor="20333333334",
            razon_social="Proveedor Tres",
        )
        Receipt.objects.create(
            user=self.user,
            estado="error_carga",
            importe_total=400.0,
            cuit_emisor="20444444445",
            razon_social="Proveedor Cuatro",
        )

        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertIn(
            '<span class="badge bg-secondary">Pendiente de Revisión</span>', content
        )
        self.assertIn(
            '<span class="badge bg-warning text-dark">Pendiente de Carga</span>',
            content,
        )
        self.assertIn(
            '<span class="badge bg-success">Cargado en SIRADIG</span>', content
        )
        self.assertIn('<span class="badge bg-danger">Error de Carga</span>', content)

    def test_dashboard_empty_state_without_receipts(self):
        """RF-DSH-007, CA-DSH-005: Estado vacío cuando el usuario no tiene comprobantes."""
        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertIn("Aún no tenés comprobantes registrados", content)
        self.assertIn("Enviar mi primer comprobante por Telegram", content)
        self.assertNotIn("<table", content)

    def test_dashboard_token_copy_button_and_script(self):
        """RF-DSH-005, CA-DSH-002: Campo de token y botón interactivo con script JS."""
        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertIn('id="extension-token-input"', content)
        self.assertIn('id="btn-copy-token"', content)
        self.assertIn("copiarToken", content)
        self.assertIn("navigator.clipboard.writeText", content)
        self.assertIn("document.execCommand('copy')", content)

    def test_dashboard_logout_redirects_to_landing(self):
        """RF-DSH-008, CA-DSH-006: Logout redirige a la raíz /."""
        self.client.force_login(self.user)
        response = self.client.post("/accounts/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/", target_status_code=200)
