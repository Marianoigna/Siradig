import logging
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from subscriptions.models import Plan
from subscriptions.services.mercadopago import crear_o_asegurar_plan_mercadopago

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Aprovisiona o asegura el Plan de Suscripción en base de datos local y Mercado Pago "
        "(ensure_mercadopago_plan)."
    )

    def handle(self, *args, **options):
        precio_mensual = getattr(settings, "PRECIO_MENSUAL", Decimal("8999.00"))
        plan, created = Plan.objects.get_or_create(
            nombre="mensual",
            defaults={
                "precio_mensual": precio_mensual,
                "descripcion": "Acceso ilimitado mensual para carga automática de SIRADIG",
                "dias_duracion": 30,
                "activo": True,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Plan local 'mensual' creado exitosamente con precio ${plan.precio_mensual} ARS."
                )
            )
        else:
            self.stdout.write(
                f"Plan local 'mensual' ya existe (ID local: {plan.id}, precio: ${plan.precio_mensual})."
            )

        token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
        if not token:
            self.stdout.write(
                self.style.WARNING(
                    "MERCADOPAGO_ACCESS_TOKEN no está configurado. "
                    "Se creó/mantuvo el plan local sin sincronizar con Mercado Pago."
                )
            )
            return

        if plan.gateway_plan_id:
            self.stdout.write(
                self.style.SUCCESS(
                    f"El plan ya cuenta con un identificador de Mercado Pago: {plan.gateway_plan_id}"
                )
            )
            return

        self.stdout.write(
            "Sincronizando plan con la API de Mercado Pago (preapproval_plan)..."
        )
        try:
            gateway_plan_id = crear_o_asegurar_plan_mercadopago(
                nombre="Plan Mensual SIRADIG Auto",
                monto=plan.precio_mensual,
                periodicidad_meses=plan.periodicidad_meses,
            )
            plan.refresh_from_db()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Plan aprovisionado exitosamente en Mercado Pago con ID: {gateway_plan_id}"
                )
            )
        except Exception as exc:
            logger.exception("Error al aprovisionar plan en Mercado Pago: %s", exc)
            self.stdout.write(
                self.style.ERROR(f"Error al sincronizar con Mercado Pago: {exc}")
            )
