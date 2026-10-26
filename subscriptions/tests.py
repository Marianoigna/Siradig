from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.test import TestCase, override_settings
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


class PlanModelTests(TestCase):
    def test_creacion_plan_mensual(self):
        plan = Plan.objects.create(
            nombre="Plan Mensual Standard",
            tipo="mensual",
            precio=Decimal("15000.00"),
            periodicidad_meses=1,
            dias_duracion=30,
            descripcion="Acceso mensual completo a SIRADIG Auto",
            activo=True,
        )
        self.assertEqual(str(plan), "Plan Mensual Standard (Mensual) - $15000.00")
        self.assertTrue(plan.activo)
        self.assertEqual(plan.tipo, "mensual")

    def test_tipo_plan_unico(self):
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
        self.plan = Plan.objects.create(
            nombre="Plan Mensual",
            tipo="mensual",
            precio=Decimal("15000.00"),
            periodicidad_meses=1,
            dias_duracion=30,
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
        self.plan = Plan.objects.create(
            nombre="Plan Mensual",
            tipo="mensual",
            precio=Decimal("15000.00"),
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
        self.plan = Plan.objects.create(
            nombre="Plan Mensual",
            tipo="mensual",
            precio=Decimal("30000.00"),
            periodicidad_meses=1,
            dias_duracion=30,
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
        self.plan = Plan.objects.create(
            nombre="Plan Mensual",
            tipo="mensual",
            precio=Decimal("30000.00"),
            periodicidad_meses=1,
            dias_duracion=30,
        )

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
