import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import Pago, Plan, Suscripcion
from subscriptions.services.access import (
    calcular_dias_restantes_trial,
    dias_restantes_trial,
    obtener_estado_acceso,
    obtener_estado_cuenta,
    usuario_tiene_acceso_activo,
)
from subscriptions.services.mercadopago import (
    cancelar_suscripcion_preapproval,
    crear_suscripcion_preapproval,
    obtener_sdk_mercadopago,
)
from subscriptions.services.webhook import (
    procesar_notificacion_webhook,
    validar_firma_mercadopago,
)


class PlanModelTests(TestCase):
    def test_creacion_plan_mensual(self):
        # El plan mensual ya puede existir debido a la migración seed
        plan, _ = Plan.objects.update_or_create(
            tipo="mensual",
            defaults={
                "nombre": "Plan Mensual Standard",
                "precio": Decimal("15000.00"),
                "periodicidad_meses": 1,
                "dias_duracion": 30,
                "descripcion": "Acceso mensual completo a SIRADIG Auto",
                "activo": True,
            },
        )
        self.assertEqual(str(plan), "Plan Mensual Standard (Mensual) - $15000.00")
        self.assertTrue(plan.activo)
        self.assertEqual(plan.tipo, "mensual")

    def test_tipo_plan_unico(self):
        Plan.objects.filter(tipo="anual").delete()
        Plan.objects.create(
            nombre="Plan Anual 1",
            tipo="anual",
            precio=Decimal("150000.00"),
        )
        with self.assertRaises(IntegrityError):
            Plan.objects.create(
                nombre="Plan Anual 2",
                tipo="anual",
                precio=Decimal("160000.00"),
            )


class SuscripcionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            tipo="mensual",
            defaults={
                "nombre": "Plan Mensual",
                "precio": Decimal("15000.00"),
                "periodicidad_meses": 1,
                "dias_duracion": 30,
            },
        )

    def test_suscripcion_por_defecto_trial(self):
        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
        )
        self.assertEqual(suscripcion.estado, "trial")
        self.assertFalse(suscripcion.esta_vigente)
        self.assertIn("testuser", str(suscripcion))

    def test_propiedad_esta_vigente_activa_con_fecha_futura(self):
        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="activa",
            fecha_vencimiento=timezone.now() + timedelta(days=30),
        )
        self.assertTrue(suscripcion.esta_vigente)

    def test_propiedad_esta_vigente_vencida_por_fecha(self):
        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="activa",
            fecha_vencimiento=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(suscripcion.esta_vigente)

    def test_propiedad_esta_vigente_falsa_si_estado_no_activa(self):
        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="cancelada",
            fecha_vencimiento=timezone.now() + timedelta(days=15),
        )
        self.assertFalse(suscripcion.esta_vigente)

    def test_usuario_unico_por_suscripcion(self):
        Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
        )
        with self.assertRaises(IntegrityError):
            Suscripcion.objects.create(
                usuario=self.user,
                plan=self.plan,
            )


class PagoModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="payer",
            email="payer@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            tipo="mensual",
            defaults={
                "nombre": "Plan Mensual",
                "precio": Decimal("15000.00"),
            },
        )
        self.suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="activa",
            fecha_vencimiento=timezone.now() + timedelta(days=30),
        )

    def test_creacion_pago_exitoso(self):
        pago = Pago.objects.create(
            usuario=self.user,
            suscripcion=self.suscripcion,
            referencia_gateway="mp_pay_123456789",
            monto=Decimal("15000.00"),
            metodo="mercadopago",
            exitoso=True,
            datos_gateway={"status": "approved", "id": 123456789},
        )
        self.assertEqual(str(pago), "Pago mp_pay_123456789 - $15000.00 (Exitoso)")
        self.assertEqual(pago.datos_gateway["status"], "approved")

    def test_unicidad_referencia_gateway(self):
        Pago.objects.create(
            usuario=self.user,
            suscripcion=self.suscripcion,
            referencia_gateway="mp_duplicate_ref",
            monto=Decimal("15000.00"),
        )
        with self.assertRaises(IntegrityError):
            Pago.objects.create(
                usuario=self.user,
                suscripcion=self.suscripcion,
                referencia_gateway="mp_duplicate_ref",
                monto=Decimal("15000.00"),
            )


class AccessServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="client1",
            email="client1@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            tipo="mensual",
            defaults={
                "nombre": "Plan Mensual",
                "precio": Decimal("30000.00"),
                "periodicidad_meses": 1,
                "dias_duracion": 30,
            },
        )

    def test_usuario_anonimo_o_none(self):
        from django.contrib.auth.models import AnonymousUser

        anon = AnonymousUser()
        self.assertFalse(usuario_tiene_acceso_activo(None))
        self.assertFalse(usuario_tiene_acceso_activo(anon))

        res_none = obtener_estado_acceso(None)
        self.assertFalse(res_none["tiene_acceso"])
        self.assertEqual(res_none["motivo"], "sin_acceso")
        self.assertIsNone(res_none["dias_restantes_trial"])
        self.assertIsNone(res_none["dias_restantes_suscripcion"])
        self.assertFalse(res_none["es_trial"])
        self.assertIsNone(res_none["suscripcion"])

        res_anon = obtener_estado_acceso(anon)
        self.assertFalse(res_anon["tiene_acceso"])
        self.assertEqual(res_anon["motivo"], "sin_acceso")
        self.assertEqual(dias_restantes_trial(anon), 0)

    def test_usuario_nuevo_dentro_del_trial(self):
        # El usuario recién creado tiene trial_start_date = now()
        estado = obtener_estado_acceso(self.user)
        self.assertTrue(estado["tiene_acceso"])
        self.assertEqual(estado["motivo"], "trial_activo")
        self.assertTrue(estado["es_trial"])
        self.assertGreaterEqual(estado["dias_restantes_trial"], 14)
        self.assertTrue(usuario_tiene_acceso_activo(self.user))
        self.assertEqual(
            dias_restantes_trial(self.user), estado["dias_restantes_trial"]
        )
        self.assertEqual(obtener_estado_cuenta(self.user), estado)

    def test_usuario_con_trial_expirado_y_sin_suscripcion(self):
        # Modificamos trial_start_date a 16 días atrás (> 15 días)
        profile = self.user.profile
        profile.trial_start_date = timezone.now() - timedelta(days=16)
        profile.save()

        estado = obtener_estado_acceso(self.user)
        self.assertFalse(estado["tiene_acceso"])
        self.assertEqual(estado["motivo"], "trial_expirado")
        self.assertEqual(estado["dias_restantes_trial"], 0)
        self.assertFalse(estado["es_trial"])
        self.assertFalse(usuario_tiene_acceso_activo(self.user))
        self.assertEqual(dias_restantes_trial(self.user), 0)

    def test_usuario_con_trial_expirado_pero_suscripcion_activa_y_vigente(self):
        # Trial expirado
        profile = self.user.profile
        profile.trial_start_date = timezone.now() - timedelta(days=20)
        profile.save()

        # Suscripción activa con vencimiento en 25 días
        sub = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="activa",
            fecha_vencimiento=timezone.now() + timedelta(days=25),
        )

        estado = obtener_estado_acceso(self.user)
        self.assertTrue(estado["tiene_acceso"])
        self.assertEqual(estado["motivo"], "suscripcion_activa")
        self.assertFalse(estado["es_trial"])
        self.assertEqual(estado["suscripcion"], sub)
        self.assertGreaterEqual(estado["dias_restantes_suscripcion"], 24)
        self.assertTrue(usuario_tiene_acceso_activo(self.user))

    def test_usuario_con_trial_expirado_y_suscripcion_vencida(self):
        # Trial expirado
        profile = self.user.profile
        profile.trial_start_date = timezone.now() - timedelta(days=20)
        profile.save()

        # Suscripción con estado 'vencida' o fecha pasada
        sub = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="vencida",
            fecha_vencimiento=timezone.now() - timedelta(days=2),
        )

        estado = obtener_estado_acceso(self.user)
        self.assertFalse(estado["tiene_acceso"])
        self.assertEqual(estado["motivo"], "suscripcion_vencida")
        self.assertFalse(estado["es_trial"])
        self.assertEqual(estado["suscripcion"], sub)
        self.assertFalse(usuario_tiene_acceso_activo(self.user))

    def test_usuario_con_trial_expirado_y_suscripcion_cancelada_sin_vigencia(self):
        # Trial expirado
        profile = self.user.profile
        profile.trial_start_date = timezone.now() - timedelta(days=20)
        profile.save()

        sub = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="cancelada",
            fecha_vencimiento=timezone.now() - timedelta(days=1),
        )

        estado = obtener_estado_acceso(self.user)
        self.assertFalse(estado["tiene_acceso"])
        self.assertEqual(estado["motivo"], "suscripcion_vencida")
        self.assertEqual(estado["suscripcion"], sub)
        self.assertFalse(usuario_tiene_acceso_activo(self.user))

    def test_usuario_sin_perfil_manejo_seguro(self):
        # Simulamos un usuario cuyo perfil no existe
        self.user.profile.delete()
        self.user.refresh_from_db()

        self.assertIsNone(calcular_dias_restantes_trial(self.user))
        estado = obtener_estado_acceso(self.user)
        self.assertFalse(estado["tiene_acceso"])
        self.assertEqual(estado["motivo"], "trial_expirado")


class MercadoPagoServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mpuser",
            email="mpuser@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            tipo="mensual",
            defaults={
                "nombre": "Plan Mensual",
                "precio": Decimal("30000.00"),
                "periodicidad_meses": 1,
                "dias_duracion": 30,
            },
        )
        # Aseguramos el precio esperado para las aserciones de mock de MercadoPago
        self.plan.precio = Decimal("30000.00")
        self.plan.save()

    def test_obtener_sdk_sin_token_lanza_excepcion(self):
        with override_settings(MERCADOPAGO_ACCESS_TOKEN=""):
            with self.assertRaises(ImproperlyConfigured):
                obtener_sdk_mercadopago()

    @patch("subscriptions.services.mercadopago.mercadopago.SDK")
    def test_obtener_sdk_exitoso(self, mock_sdk_class):
        mock_instance = MagicMock()
        mock_sdk_class.return_value = mock_instance

        with override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123"):
            sdk = obtener_sdk_mercadopago()
            mock_sdk_class.assert_called_once_with("TEST_TOKEN_123")
            self.assertEqual(sdk, mock_instance)

    @patch("subscriptions.services.mercadopago.mercadopago.SDK")
    def test_crear_suscripcion_preapproval_exitoso(self, mock_sdk_class):
        mock_sdk_instance = MagicMock()
        mock_preapproval = MagicMock()
        mock_sdk_instance.preapproval.return_value = mock_preapproval
        mock_sdk_class.return_value = mock_sdk_instance

        mock_preapproval.create.return_value = {
            "status": 201,
            "response": {
                "id": "2c9380847290c0a8017290d29e700000",
                "init_point": "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_id=2c9380847290c0a8017290d29e700000",
                "status": "pending",
            },
        }

        with override_settings(
            MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123",
            MERCADOPAGO_AUTO_RETURN_URL="https://siradig.example.com/suscripciones/retorno/",
        ):
            resultado = crear_suscripcion_preapproval(self.user, self.plan)

            self.assertEqual(resultado["id"], "2c9380847290c0a8017290d29e700000")
            self.assertEqual(
                resultado["init_point"],
                "https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_id=2c9380847290c0a8017290d29e700000",
            )
            self.assertEqual(resultado["status"], "pending")

            mock_preapproval.create.assert_called_once()
            call_payload = mock_preapproval.create.call_args[0][0]
            self.assertEqual(call_payload["payer_email"], "mpuser@example.com")
            self.assertEqual(
                call_payload["back_url"],
                "https://siradig.example.com/suscripciones/retorno/",
            )
            self.assertEqual(
                call_payload["external_reference"],
                f"{self.user.id}:mensual",
            )
            self.assertEqual(call_payload["auto_recurring"]["frequency"], 1)
            self.assertEqual(
                call_payload["auto_recurring"]["transaction_amount"], 30000.0
            )

            # Verificar actualización/creación en base de datos local
            suscripcion = Suscripcion.objects.get(usuario=self.user)
            self.assertEqual(
                suscripcion.gateway_subscription_id,
                "2c9380847290c0a8017290d29e700000",
            )
            self.assertEqual(suscripcion.plan, self.plan)

    @patch("subscriptions.services.mercadopago.mercadopago.SDK")
    def test_crear_suscripcion_preapproval_error_api_mercadopago(self, mock_sdk_class):
        mock_sdk_instance = MagicMock()
        mock_preapproval = MagicMock()
        mock_sdk_instance.preapproval.return_value = mock_preapproval
        mock_sdk_class.return_value = mock_sdk_instance

        mock_preapproval.create.return_value = {
            "status": 400,
            "response": {
                "message": "Invalid payer email",
                "error": "bad_request",
                "status": 400,
            },
        }

        with override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123"):
            resultado = crear_suscripcion_preapproval(self.user, self.plan)

            self.assertEqual(resultado["status"], "error")
            self.assertIn("MercadoPago retornó un error (400)", resultado["error"])
            self.assertIn("Invalid payer email", resultado["error"])
            self.assertIn("detail", resultado)

    @patch("subscriptions.services.mercadopago.mercadopago.SDK")
    def test_crear_suscripcion_preapproval_excepcion_red(self, mock_sdk_class):
        mock_sdk_instance = MagicMock()
        mock_preapproval = MagicMock()
        mock_preapproval.create.side_effect = RuntimeError(
            "Network timeout connecting to MP"
        )
        mock_sdk_instance.preapproval.return_value = mock_preapproval
        mock_sdk_class.return_value = mock_sdk_instance

        with override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123"):
            resultado = crear_suscripcion_preapproval(self.user, self.plan)

            self.assertEqual(resultado["status"], "error")
            self.assertIn("Error de comunicación", resultado["error"])

    @patch("subscriptions.services.mercadopago.mercadopago.SDK")
    def test_cancelar_suscripcion_preapproval_exitoso(self, mock_sdk_class):
        mock_sdk_instance = MagicMock()
        mock_preapproval = MagicMock()
        mock_sdk_instance.preapproval.return_value = mock_preapproval
        mock_sdk_class.return_value = mock_sdk_instance

        mock_preapproval.update.return_value = {
            "status": 200,
            "response": {"id": "sub_12345", "status": "cancelled"},
        }

        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="activa",
            gateway_subscription_id="sub_12345",
            fecha_vencimiento=timezone.now() + timedelta(days=20),
        )

        with override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123"):
            resultado = cancelar_suscripcion_preapproval(suscripcion)

            self.assertTrue(resultado)
            mock_preapproval.update.assert_called_once_with(
                "sub_12345", {"status": "cancelled"}
            )

            suscripcion.refresh_from_db()
            self.assertEqual(suscripcion.estado, "cancelada")
            self.assertIsNotNone(suscripcion.fecha_cancelacion)

    @patch("subscriptions.services.mercadopago.mercadopago.SDK")
    def test_cancelar_suscripcion_sin_gateway_id_cancela_local(self, mock_sdk_class):
        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="trial",
            gateway_subscription_id="",
        )

        with override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123"):
            resultado = cancelar_suscripcion_preapproval(suscripcion)

            self.assertTrue(resultado)
            mock_sdk_class.assert_not_called()
            suscripcion.refresh_from_db()
            self.assertEqual(suscripcion.estado, "cancelada")
            self.assertIsNotNone(suscripcion.fecha_cancelacion)


class WebhookServiceTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.user = User.objects.create_user(
            username="whuser",
            email="whuser@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            tipo="mensual",
            defaults={
                "nombre": "Plan Mensual",
                "precio": Decimal("30000.00"),
                "periodicidad_meses": 1,
                "dias_duracion": 30,
            },
        )

    def test_validar_firma_sin_secret_configurado_devuelve_true(self):
        with override_settings(MERCADOPAGO_WEBHOOK_SECRET=""):
            req = self.rf.post("/suscripciones/webhook/mercadopago/")
            self.assertTrue(validar_firma_mercadopago(req))

    def test_validar_firma_con_secret_valida_correctamente(self):
        secret = "test_webhook_secret_key"
        data_id = "998877"
        request_id = "req-uuid-1234"
        ts = "1710000000"

        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        v1_hash = hmac.new(
            secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        with override_settings(MERCADOPAGO_WEBHOOK_SECRET=secret):
            body_bytes = json.dumps({"data": {"id": data_id}}).encode("utf-8")
            req = self.rf.post(
                "/suscripciones/webhook/mercadopago/",
                data=body_bytes,
                content_type="application/json",
                HTTP_X_SIGNATURE=f"ts={ts},v1={v1_hash}",
                HTTP_X_REQUEST_ID=request_id,
            )
            self.assertTrue(validar_firma_mercadopago(req))

    def test_validar_firma_adulterada_devuelve_false(self):
        secret = "test_webhook_secret_key"
        data_id = "998877"
        request_id = "req-uuid-1234"
        ts = "1710000000"

        with override_settings(MERCADOPAGO_WEBHOOK_SECRET=secret):
            body_bytes = json.dumps({"data": {"id": data_id}}).encode("utf-8")
            req = self.rf.post(
                "/suscripciones/webhook/mercadopago/",
                data=body_bytes,
                content_type="application/json",
                HTTP_X_SIGNATURE=f"ts={ts},v1=invalidsignaturehash",
                HTTP_X_REQUEST_ID=request_id,
            )
            self.assertFalse(validar_firma_mercadopago(req))

    def test_validar_firma_sin_header_signature_devuelve_false(self):
        secret = "test_webhook_secret_key"
        with override_settings(MERCADOPAGO_WEBHOOK_SECRET=secret):
            req = self.rf.post("/suscripciones/webhook/mercadopago/")
            self.assertFalse(validar_firma_mercadopago(req))

    @patch("subscriptions.services.webhook.obtener_sdk_mercadopago")
    def test_procesar_notificacion_pago_approved_crea_suscripcion_y_pago(
        self, mock_get_sdk
    ):
        mock_sdk = MagicMock()
        mock_get_sdk.return_value = mock_sdk
        mock_sdk.payment().get.return_value = {
            "status": 200,
            "response": {
                "id": 1234567,
                "status": "approved",
                "transaction_amount": 30000.0,
                "external_reference": f"{self.user.id}:mensual",
            },
        }

        payload = {"type": "payment", "data": {"id": "1234567"}}
        exito, msg = procesar_notificacion_webhook(payload)

        self.assertTrue(exito)
        self.assertIn("Pago procesado", msg)

        pago = Pago.objects.get(referencia_gateway="mp_pay_1234567")
        self.assertEqual(pago.usuario, self.user)
        self.assertEqual(pago.monto, Decimal("30000.0"))
        self.assertTrue(pago.exitoso)

        suscripcion = Suscripcion.objects.get(usuario=self.user)
        self.assertEqual(suscripcion.estado, "activa")
        self.assertIsNotNone(suscripcion.fecha_vencimiento)
        self.assertGreater(suscripcion.fecha_vencimiento, timezone.now())

    @patch("subscriptions.services.webhook.obtener_sdk_mercadopago")
    def test_procesar_notificacion_pago_idempotente(self, mock_get_sdk):
        mock_sdk = MagicMock()
        mock_get_sdk.return_value = mock_sdk
        mock_sdk.payment().get.return_value = {
            "status": 200,
            "response": {
                "id": 777888,
                "status": "approved",
                "transaction_amount": 30000.0,
                "external_reference": f"{self.user.id}:mensual",
            },
        }

        payload = {"type": "payment", "data": {"id": "777888"}}
        exito1, _ = procesar_notificacion_webhook(payload)
        self.assertTrue(exito1)
        sub1 = Suscripcion.objects.get(usuario=self.user)
        vencimiento_inicial = sub1.fecha_vencimiento

        exito2, msg2 = procesar_notificacion_webhook(payload)
        self.assertTrue(exito2)
        self.assertIn("idempotente", msg2)

        sub2 = Suscripcion.objects.get(usuario=self.user)
        self.assertEqual(sub2.fecha_vencimiento, vencimiento_inicial)
        self.assertEqual(
            Pago.objects.filter(referencia_gateway="mp_pay_777888").count(), 1
        )

    @patch("subscriptions.services.webhook.obtener_sdk_mercadopago")
    def test_procesar_notificacion_preapproval_authorized(self, mock_get_sdk):
        mock_sdk = MagicMock()
        mock_get_sdk.return_value = mock_sdk
        mock_sdk.preapproval().get.return_value = {
            "status": 200,
            "response": {
                "id": "preapp_112233",
                "status": "authorized",
                "external_reference": f"{self.user.id}:mensual",
            },
        }

        payload = {"type": "subscription_preapproval", "data": {"id": "preapp_112233"}}
        exito, msg = procesar_notificacion_webhook(payload)

        self.assertTrue(exito)
        self.assertIn("autorizada", msg)

        suscripcion = Suscripcion.objects.get(usuario=self.user)
        self.assertEqual(suscripcion.gateway_subscription_id, "preapp_112233")
        self.assertEqual(suscripcion.estado, "activa")

    @patch("subscriptions.services.webhook.obtener_sdk_mercadopago")
    def test_procesar_notificacion_preapproval_cancelled(self, mock_get_sdk):
        mock_sdk = MagicMock()
        mock_get_sdk.return_value = mock_sdk
        mock_sdk.preapproval().get.return_value = {
            "status": 200,
            "response": {
                "id": "preapp_998877",
                "status": "cancelled",
                "external_reference": f"{self.user.id}:mensual",
            },
        }

        payload = {"type": "preapproval", "data": {"id": "preapp_998877"}}
        exito, msg = procesar_notificacion_webhook(payload)

        self.assertTrue(exito)
        self.assertIn("cancelada", msg)

        suscripcion = Suscripcion.objects.get(usuario=self.user)
        self.assertEqual(suscripcion.estado, "cancelada")
        self.assertIsNotNone(suscripcion.fecha_cancelacion)

    def test_procesar_notificacion_sin_resource_id_retorna_false(self):
        exito, msg = procesar_notificacion_webhook({})
        self.assertFalse(exito)
        self.assertIn("sin resource_id", msg)

    @patch("subscriptions.services.webhook.obtener_sdk_mercadopago")
    def test_procesar_notificacion_pago_no_aprobado_ignora(self, mock_get_sdk):
        mock_sdk = MagicMock()
        mock_get_sdk.return_value = mock_sdk
        mock_sdk.payment().get.return_value = {
            "status": 200,
            "response": {
                "id": 555666,
                "status": "rejected",
                "external_reference": f"{self.user.id}:mensual",
            },
        }

        payload = {"type": "payment", "data": {"id": "555666"}}
        exito, msg = procesar_notificacion_webhook(payload)

        self.assertTrue(exito)
        self.assertIn("no aprobado", msg)
        self.assertFalse(
            Pago.objects.filter(referencia_gateway="mp_pay_555666").exists()
        )

    @patch("subscriptions.services.webhook.obtener_sdk_mercadopago")
    def test_procesar_notificacion_con_query_params_topic(self, mock_get_sdk):
        mock_sdk = MagicMock()
        mock_get_sdk.return_value = mock_sdk
        mock_sdk.payment().get.return_value = {
            "status": 200,
            "response": {
                "id": 111222,
                "status": "approved",
                "transaction_amount": 30000.0,
                "external_reference": f"{self.user.id}:mensual",
            },
        }

        exito, msg = procesar_notificacion_webhook(
            payload={}, query_params={"topic": "payment", "id": "111222"}
        )
        self.assertTrue(exito)
        self.assertIn("Pago procesado", msg)


class SubscriptionViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="viewuser",
            email="viewuser@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            tipo="mensual",
            defaults={
                "nombre": "Plan Mensual",
                "precio": Decimal("30000.00"),
                "periodicidad_meses": 1,
                "dias_duracion": 30,
            },
        )

    def test_planes_view_requiere_login(self):
        resp = self.client.get(reverse("subscriptions:planes"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)

    def test_planes_view_autenticado_renderiza_correctamente(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("subscriptions:planes"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "subscriptions/planes.html")
        self.assertContains(resp, "Plan Mensual")

    def test_iniciar_checkout_get_redirige_a_planes(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("subscriptions:iniciar_checkout", kwargs={"tipo_plan": "mensual"})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("subscriptions:planes"))

        # Siguiendo la redirección se observa el mensaje informativo
        resp_followed = self.client.get(
            reverse("subscriptions:iniciar_checkout", kwargs={"tipo_plan": "mensual"}),
            follow=True,
        )
        self.assertEqual(resp_followed.status_code, 200)
        self.assertContains(
            resp_followed, "Seleccioná tu plan para continuar con la suscripción."
        )

    def test_iniciar_checkout_sin_token_redirige_a_planes_sin_500(self):
        self.client.force_login(self.user)
        with override_settings(MERCADOPAGO_ACCESS_TOKEN=""):
            resp = self.client.post(
                reverse(
                    "subscriptions:iniciar_checkout", kwargs={"tipo_plan": "mensual"}
                ),
                follow=True,
            )
            self.assertEqual(resp.status_code, 200)
            self.assertTemplateUsed(resp, "subscriptions/planes.html")
            self.assertContains(
                resp,
                "La pasarela de pagos no está configurada correctamente en el servidor.",
            )

    @patch("subscriptions.views.crear_suscripcion_preapproval")
    def test_iniciar_checkout_exitoso_redirige_init_point(self, mock_crear):
        self.client.force_login(self.user)
        mock_crear.return_value = {
            "id": "preapp_test_123",
            "init_point": "https://www.mercadopago.com.ar/checkout/test",
            "status": "pending",
        }

        resp = self.client.post(
            reverse("subscriptions:iniciar_checkout", kwargs={"tipo_plan": "mensual"})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "https://www.mercadopago.com.ar/checkout/test")

    @patch("subscriptions.views.crear_suscripcion_preapproval")
    def test_iniciar_checkout_error_muestra_mensaje_y_redirige(self, mock_crear):
        self.client.force_login(self.user)
        mock_crear.return_value = {
            "error": "Error de comunicación con MP",
            "status": "error",
        }

        resp = self.client.post(
            reverse("subscriptions:iniciar_checkout", kwargs={"tipo_plan": "mensual"}),
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "subscriptions/planes.html")
        self.assertContains(resp, "Error de comunicación con MP")

    def test_retorno_view_autenticado(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("subscriptions:retorno") + "?status=approved")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "subscriptions/retorno.html")
        self.assertContains(resp, "aprobado exitosamente")

    @patch("subscriptions.views.cancelar_suscripcion_preapproval")
    def test_cancelar_suscripcion_view_activa(self, mock_cancelar):
        self.client.force_login(self.user)
        Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="activa",
            fecha_vencimiento=timezone.now() + timedelta(days=10),
            gateway_subscription_id="preapp_cancel_test",
        )

        resp = self.client.post(reverse("subscriptions:cancelar"), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "subscriptions/planes.html")
        mock_cancelar.assert_called_once()
        self.assertContains(resp, "renovación automática ha sido cancelada")

    def test_webhook_view_rechaza_firma_invalida(self):
        secret = "super_secret_webhook"
        with override_settings(MERCADOPAGO_WEBHOOK_SECRET=secret):
            resp = self.client.post(
                reverse("subscriptions:webhook"),
                data={"data": {"id": "12345"}},
                content_type="application/json",
                HTTP_X_SIGNATURE="ts=123,v1=invalidsignature",
                HTTP_X_REQUEST_ID="uuid-1",
            )
            self.assertEqual(resp.status_code, 401)

    @patch("subscriptions.views.procesar_notificacion_webhook")
    def test_webhook_view_exitoso_retorna_200(self, mock_procesar):
        mock_procesar.return_value = (True, "Pago procesado")
        with override_settings(MERCADOPAGO_WEBHOOK_SECRET=""):
            resp = self.client.post(
                reverse("subscriptions:webhook"),
                data=json.dumps({"type": "payment", "data": {"id": "12345"}}),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200)
            mock_procesar.assert_called_once()
