from __future__ import annotations

import logging
from typing import Any

import mercadopago
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import Plan, Suscripcion

logger = logging.getLogger(__name__)


def obtener_sdk_mercadopago() -> mercadopago.SDK:
    """
    Obtiene e inicializa la instancia del cliente SDK de MercadoPago
    usando el token configurado en settings.MERCADOPAGO_ACCESS_TOKEN.
    """
    token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
    if not token:
        logger.error("MERCADOPAGO_ACCESS_TOKEN no está configurado en settings.")
        raise ImproperlyConfigured(
            "MERCADOPAGO_ACCESS_TOKEN no está configurado en settings."
        )
    return mercadopago.SDK(token)


def crear_suscripcion_preapproval(
    usuario: Any, plan: Plan, request: Any | None = None
) -> dict[str, Any]:
    """
    Crea una suscripción de débito recurrente (Preapproval) en MercadoPago y
    asocia el ID devuelto a la Suscripcion del usuario local.
    """
    sdk = obtener_sdk_mercadopago()

    # Resolver back_url
    back_url = getattr(settings, "MERCADOPAGO_AUTO_RETURN_URL", "")
    if not back_url:
        back_url = getattr(settings, "MERCADOPAGO_BACK_URL", "")
    if not back_url:
        if request:
            try:
                back_url = request.build_absolute_uri(reverse("subscriptions:retorno"))
            except Exception:
                back_url = request.build_absolute_uri("/")
        else:
            back_url = "http://localhost:8000"

    payer_email = (
        usuario.email
        if getattr(usuario, "email", None)
        else f"user_{usuario.id}@siradigauto.com"
    )

    frequency = (
        plan.periodicidad_meses
        if plan.periodicidad_meses
        else (12 if plan.tipo == "anual" else 1)
    )

    preapproval_data = {
        "payer_email": payer_email,
        "back_url": back_url,
        "reason": f"Suscripción {plan.nombre} - SIRADIG Auto",
        "external_reference": f"{usuario.id}:{plan.tipo}",
        "auto_recurring": {
            "frequency": frequency,
            "frequency_type": "months",
            "transaction_amount": float(plan.precio),
            "currency_id": "ARS",
        },
    }

    try:
        mp_response = sdk.preapproval().create(preapproval_data)
    except Exception as exc:
        logger.exception(
            "Error de comunicación al llamar a API Preapproval de MercadoPago: %s", exc
        )
        return {
            "error": f"Error de comunicación con la pasarela de pagos: {str(exc)}",
            "status": "error",
        }

    status_code = mp_response.get("status")
    response_body = mp_response.get("response", {})

    if status_code in (200, 201):
        gateway_subscription_id = response_body.get("id", "")
        init_point = response_body.get("init_point", "")

        suscripcion, _ = Suscripcion.objects.get_or_create(usuario=usuario)
        suscripcion.plan = plan
        if gateway_subscription_id:
            suscripcion.gateway_subscription_id = gateway_subscription_id
        suscripcion.save(update_fields=["plan", "gateway_subscription_id"])

        return {
            "id": gateway_subscription_id,
            "init_point": init_point,
            "status": response_body.get("status", "pending"),
        }

    error_detail = (
        response_body.get("message") or response_body.get("error") or str(response_body)
    )
    logger.error(
        "MercadoPago Preapproval error (HTTP %s): %s",
        status_code,
        error_detail,
    )
    return {
        "error": f"MercadoPago retornó un error ({status_code}): {error_detail}",
        "status": "error",
        "detail": response_body,
    }


def cancelar_suscripcion_preapproval(suscripcion: Suscripcion) -> bool:
    """
    Cancela la suscripción recurrente en MercadoPago vía API de Preapproval
    y actualiza el estado local del modelo Suscripcion a 'cancelada'.
    """
    if suscripcion.gateway_subscription_id:
        try:
            sdk = obtener_sdk_mercadopago()
            update_response = sdk.preapproval().update(
                suscripcion.gateway_subscription_id,
                {"status": "cancelled"},
            )
            resp_status = update_response.get("status")
            if resp_status not in (200, 201):
                logger.warning(
                    "Respuesta inesperada al cancelar en MercadoPago Preapproval %s: HTTP %s - %s",
                    suscripcion.gateway_subscription_id,
                    resp_status,
                    update_response.get("response"),
                )
        except Exception as exc:
            logger.exception(
                "Fallo al invocar cancelación en MercadoPago para id %s: %s",
                suscripcion.gateway_subscription_id,
                exc,
            )

    suscripcion.estado = "cancelada"
    suscripcion.fecha_cancelacion = timezone.now()
    suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
    return True
