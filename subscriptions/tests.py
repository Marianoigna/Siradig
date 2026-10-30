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
from subscriptions.permissions import HasActiveSubscriptionOrTrial
from subscriptions.services.access import (
    calcular_dias_restantes_trial,
    dias_restantes_trial,
    obtener_estado_acceso,
    obtener_estado_cuenta,
    usuario_tiene_acceso_activo,
)
from subscriptions.services.mercadopago import (
    cancelar_suscripcion_preapproval,
    crear_o_asegurar_plan_mercadopago,
    crear_suscripcion_preapproval,
    obtener_sdk_mercadopago,
)
from subscriptions.services.webhook import (
    procesar_notificacion_webhook,
    validar_firma_mercadopago,
)


class PlanModelTests(TestCase):
    def test_creacion_plan_mensual(self):
        plan = Plan.objects.create(
            nombre="plan_test_mensual",
            descripcion="Plan Mensual de prueba",
            dias_duracion=30,
        )
        self.assertEqual(plan.precio_mensual, Decimal("8999.00"))
        self.assertEqual(plan.dias_duracion, 30)
        self.assertEqual(plan.gateway_plan_id, "")
        self.assertIn("plan_test_mensual", str(plan))
        self.assertIn("8999.00", str(plan))

    def test_nombre_plan_unico(self):
        Plan.objects.create(
            nombre="plan_unico_test",
            precio_mensual=Decimal("8999.00"),
        )
        with self.assertRaises(IntegrityError):
            Plan.objects.create(
                nombre="plan_unico_test",
                precio_mensual=Decimal("9999.00"),
            )


class SuscripcionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            nombre="mensual",
            defaults={
                "precio_mensual": Decimal("8999.00"),
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

    def test_propiedad_esta_vigente_falsa_si_estado_no_activa_ni_cancelada(self):
        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="vencida",
            fecha_vencimiento=timezone.now() + timedelta(days=15),
        )
        self.assertFalse(suscripcion.esta_vigente)

    def test_propiedad_esta_vigente_verdadera_si_cancelada_con_fecha_futura(self):
        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="cancelada",
            fecha_vencimiento=timezone.now() + timedelta(days=15),
        )
        self.assertTrue(suscripcion.esta_vigente)

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
            nombre="mensual",
            defaults={
                "precio_mensual": Decimal("8999.00"),
                "dias_duracion": 30,
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
            monto=Decimal("8999.00"),
            metodo="mercadopago",
            exitoso=True,
            datos_gateway={"status": "approved", "id": 123456789},
        )
        self.assertEqual(str(pago), "Pago mp_pay_123456789 - $8999.00 (Exitoso)")
        self.assertEqual(pago.fecha, pago.fecha_pago)
        self.assertEqual(pago.datos_gateway["status"], "approved")

    def test_unicidad_referencia_gateway(self):
        Pago.objects.create(
            usuario=self.user,
            suscripcion=self.suscripcion,
            referencia_gateway="mp_duplicate_ref",
            monto=Decimal("8999.00"),
        )
        with self.assertRaises(IntegrityError):
            Pago.objects.create(
                usuario=self.user,
                suscripcion=self.suscripcion,
                referencia_gateway="mp_duplicate_ref",
                monto=Decimal("8999.00"),
            )


class AccessServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="client1",
            email="client1@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            nombre="mensual",
            defaults={
                "precio_mensual": Decimal("8999.00"),
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

    def test_usuario_con_trial_expirado_y_suscripcion_cancelada_con_vigencia_conserva_acceso(
        self,
    ):
        # RN-005: Conserva acceso hasta fecha_vencimiento aunque esté cancelada
        profile = self.user.profile
        profile.trial_start_date = timezone.now() - timedelta(days=20)
        profile.save()

        sub = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="cancelada",
            fecha_vencimiento=timezone.now() + timedelta(days=12),
        )

        estado = obtener_estado_cuenta(self.user)
        self.assertTrue(estado["tiene_acceso"])
        self.assertTrue(estado["suscripcion_activa"])
        self.assertEqual(estado["estado_suscripcion"], "cancelada")
        self.assertEqual(estado["motivo"], "suscripcion_activa")
        self.assertEqual(estado["suscripcion"], sub)
        self.assertGreaterEqual(estado["dias_restantes_suscripcion"], 11)
        self.assertTrue(usuario_tiene_acceso_activo(self.user))

    def test_superuser_y_staff_siempre_tienen_acceso_activo(self):
        self.user.is_staff = True
        self.user.save()
        # Perfil con trial expirado y sin suscripción
        profile = self.user.profile
        profile.trial_start_date = timezone.now() - timedelta(days=40)
        profile.save()

        self.assertTrue(usuario_tiene_acceso_activo(self.user))
        estado = obtener_estado_cuenta(self.user)
        self.assertTrue(estado["tiene_acceso"])
        self.assertEqual(estado["motivo"], "admin")

    def test_calculo_dias_restantes_trial_preciso(self):
        profile = self.user.profile
        # Exactamente 5 días transcurridos de 15 -> restan 10
        profile.trial_start_date = timezone.now() - timedelta(days=5)
        profile.save()

        dias = dias_restantes_trial(self.user)
        self.assertIn(dias, (10, 11))  # Por segundos de redondeo ceil

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
            nombre="mensual",
            defaults={
                "precio_mensual": Decimal("8999.00"),
                "dias_duracion": 30,
            },
        )
        self.plan.precio_mensual = Decimal("8999.00")
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
                call_payload["auto_recurring"]["transaction_amount"], 8999.0
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
    def test_cancelar_suscripcion_por_string_id(self, mock_sdk_class):
        mock_sdk_instance = MagicMock()
        mock_preapproval = MagicMock()
        mock_sdk_instance.preapproval.return_value = mock_preapproval
        mock_sdk_class.return_value = mock_sdk_instance
        mock_preapproval.update.return_value = {
            "status": 200,
            "response": {"status": "cancelled"},
        }

        suscripcion = Suscripcion.objects.create(
            usuario=self.user,
            plan=self.plan,
            estado="activa",
            gateway_subscription_id="sub_string_999",
            fecha_vencimiento=timezone.now() + timedelta(days=10),
        )

        with override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123"):
            res = cancelar_suscripcion_preapproval("sub_string_999")
            self.assertTrue(res)
            mock_preapproval.update.assert_called_once_with(
                "sub_string_999", {"status": "cancelled"}
            )
            suscripcion.refresh_from_db()
            self.assertEqual(suscripcion.estado, "cancelada")

    @patch("subscriptions.services.mercadopago.mercadopago.SDK")
    def test_crear_o_asegurar_plan_mercadopago_exitoso(self, mock_sdk_class):
        mock_sdk_instance = MagicMock()
        mock_plan_service = MagicMock()
        mock_sdk_instance.preapproval_plan.return_value = mock_plan_service
        mock_sdk_class.return_value = mock_sdk_instance

        mock_plan_service.create.return_value = {
            "status": 201,
            "response": {"id": "mp_plan_abc123", "status": "active"},
        }

        with override_settings(
            MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123",
            MERCADOPAGO_BACK_URL="https://siradig.example.com",
        ):
            plan_id = crear_o_asegurar_plan_mercadopago(
                nombre="Plan Mensual SIRADIG Auto",
                monto=Decimal("8999.00"),
                periodicidad_meses=1,
            )
            self.assertEqual(plan_id, "mp_plan_abc123")
            mock_plan_service.create.assert_called_once()
            call_args = mock_plan_service.create.call_args[0][0]
            self.assertEqual(call_args["reason"], "Plan Mensual SIRADIG Auto")
            self.assertEqual(call_args["auto_recurring"]["frequency"], 1)
            self.assertEqual(call_args["auto_recurring"]["frequency_type"], "months")
            self.assertEqual(call_args["auto_recurring"]["transaction_amount"], 8999.0)
            self.assertEqual(call_args["auto_recurring"]["currency_id"], "ARS")

            self.plan.refresh_from_db()
            self.assertEqual(self.plan.gateway_plan_id, "mp_plan_abc123")

    @patch("subscriptions.services.mercadopago.mercadopago.SDK")
    def test_crear_o_asegurar_plan_mercadopago_error_api(self, mock_sdk_class):
        mock_sdk_instance = MagicMock()
        mock_plan_service = MagicMock()
        mock_sdk_instance.preapproval_plan.return_value = mock_plan_service
        mock_sdk_class.return_value = mock_sdk_instance

        mock_plan_service.create.return_value = {
            "status": 400,
            "response": {"message": "Invalid transaction amount"},
        }

        with override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123"):
            with self.assertRaises(RuntimeError) as ctx:
                crear_o_asegurar_plan_mercadopago()
            self.assertIn("Invalid transaction amount", str(ctx.exception))


class EnsureMercadoPagoPlanCommandTests(TestCase):
    def setUp(self):
        Plan.objects.all().delete()

    def test_ensure_plan_crea_plan_local_sin_token(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        with override_settings(
            MERCADOPAGO_ACCESS_TOKEN="", PRECIO_MENSUAL=Decimal("8999.00")
        ):
            call_command("ensure_mercadopago_plan", stdout=out)

        plan = Plan.objects.get(nombre="mensual")
        self.assertEqual(plan.precio_mensual, Decimal("8999.00"))
        self.assertEqual(plan.dias_duracion, 30)
        self.assertEqual(plan.gateway_plan_id, "")
        output = out.getvalue()
        self.assertIn("Plan local 'mensual' creado exitosamente", output)
        self.assertIn("MERCADOPAGO_ACCESS_TOKEN no está configurado", output)

    @patch(
        "subscriptions.management.commands.ensure_mercadopago_plan.crear_o_asegurar_plan_mercadopago"
    )
    def test_ensure_plan_con_token_sincroniza_con_mercadopago(self, mock_crear_plan):
        from io import StringIO

        from django.core.management import call_command

        mock_crear_plan.return_value = "plan_mp_generated_99"

        out = StringIO()
        with override_settings(
            MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123", PRECIO_MENSUAL=Decimal("8999.00")
        ):
            call_command("ensure_mercadopago_plan", stdout=out)

        mock_crear_plan.assert_called_once()
        output = out.getvalue()
        self.assertIn("Plan aprovisionado exitosamente en Mercado Pago", output)

    @patch(
        "subscriptions.management.commands.ensure_mercadopago_plan.crear_o_asegurar_plan_mercadopago"
    )
    def test_ensure_plan_si_ya_tiene_gateway_plan_id_no_lo_recrea(
        self, mock_crear_plan
    ):
        from io import StringIO

        from django.core.management import call_command

        Plan.objects.create(
            nombre="mensual",
            precio_mensual=Decimal("8999.00"),
            dias_duracion=30,
            gateway_plan_id="existing_plan_id_77",
        )

        out = StringIO()
        with override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST_TOKEN_123"):
            call_command("ensure_mercadopago_plan", stdout=out)

        mock_crear_plan.assert_not_called()
        self.assertIn(
            "El plan ya cuenta con un identificador de Mercado Pago", out.getvalue()
        )


class WebhookServiceTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.user = User.objects.create_user(
            username="whuser",
            email="whuser@example.com",
            password="securepassword123",
        )
        self.plan, _ = Plan.objects.get_or_create(
            nombre="mensual",
            defaults={
                "precio_mensual": Decimal("8999.00"),
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
            nombre="mensual",
            defaults={
                "precio_mensual": Decimal("8999.00"),
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

    def test_webhook_view_rechaza_sin_firma_cuando_secret_configurado(self):
        secret = "super_secret_webhook"
        with override_settings(MERCADOPAGO_WEBHOOK_SECRET=secret):
            resp = self.client.post(
                reverse("subscriptions:webhook"),
                data={"data": {"id": "12345"}},
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 401)

    @patch("subscriptions.views.procesar_notificacion_webhook")
    def test_webhook_view_con_firma_valida_retorna_200(self, mock_procesar):
        mock_procesar.return_value = (True, "Pago procesado y suscripción activada")
        secret = "super_secret_webhook"
        data_id = "54321"
        request_id = "req-uuid-abc"
        ts = "1710000000"
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        v1_hash = hmac.new(
            secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        with override_settings(MERCADOPAGO_WEBHOOK_SECRET=secret):
            resp = self.client.post(
                reverse("subscriptions:webhook"),
                data=json.dumps({"type": "payment", "data": {"id": data_id}}),
                content_type="application/json",
                HTTP_X_SIGNATURE=f"ts={ts},v1={v1_hash}",
                HTTP_X_REQUEST_ID=request_id,
            )
            self.assertEqual(resp.status_code, 200)
            mock_procesar.assert_called_once()

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


class HasActiveSubscriptionOrTrialPermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="permuser",
            email="permuser@example.com",
            password="securepassword123",
        )
        self.permission = HasActiveSubscriptionOrTrial()

    def test_anonymous_user_returns_true_for_auth_permission_to_handle(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/api/receipts/pending/")
        request.user = AnonymousUser()
        self.assertTrue(self.permission.has_permission(request, None))

    def test_authenticated_user_with_active_trial_returns_true(self):
        self.user.profile.trial_start_date = timezone.now() - timedelta(days=5)
        self.user.profile.save()

        request = self.factory.get("/api/receipts/pending/")
        request.user = self.user
        self.assertTrue(self.permission.has_permission(request, None))

    def test_authenticated_user_with_expired_trial_raises_permission_denied(self):
        from rest_framework.exceptions import PermissionDenied

        self.user.profile.trial_start_date = timezone.now() - timedelta(days=20)
        self.user.profile.save()

        request = self.factory.get("/api/receipts/pending/")
        request.user = self.user

        with self.assertRaises(PermissionDenied) as ctx:
            self.permission.has_permission(request, None)

        exc = ctx.exception
        self.assertEqual(exc.detail.get("code"), "subscription_required")
        self.assertIn("Acceso restringido", exc.detail.get("detail", ""))
