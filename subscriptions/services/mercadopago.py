from __future__ import annotations

import logging
from decimal import Decimal
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


def crear_o_asegurar_plan_mercadopago(
    nombre: str = "Plan Mensual SIRADIG Auto",
    monto: float | Decimal = Decimal("8999.00"),
    periodicidad_meses: int = 1,
) -> str:
    """
    Crea o asegura un plan de suscripción (preapproval_plan) recurrente en Mercado Pago.
    Actualiza el gateway_plan_id en el modelo local Plan (nombre='mensual') y retorna dicho ID.
    """
    sdk = obtener_sdk_mercadopago()

    back_url = getattr(settings, "MERCADOPAGO_BACK_URL", "")
    if not back_url:
        back_url = getattr(
            settings, "MERCADOPAGO_AUTO_RETURN_URL", "http://localhost:8000"
        )

    plan_data = {
        "reason": nombre,
        "auto_recurring": {
            "frequency": int(periodicidad_meses),
            "frequency_type": "months",
            "transaction_amount": float(monto),
            "currency_id": "ARS",
        },
        "back_url": back_url,
    }

    try:
        mp_response = sdk.preapproval_plan().create(plan_data)
    except Exception as exc:
        logger.exception(
            "Error de comunicación al crear preapproval_plan en Mercado Pago: %s", exc
        )
        raise RuntimeError(f"Error de comunicación con Mercado Pago: {exc}") from exc

    status_code = mp_response.get("status")
    response_body = mp_response.get("response", {})

    if status_code in (200, 201):
        gateway_plan_id = response_body.get("id", "")
        if not gateway_plan_id:
            logger.error(
                "Mercado Pago devolvió 200/201 sin ID de plan: %s", response_body
            )
            raise ValueError("Mercado Pago no retornó un identificador de plan válido.")

        Plan.objects.filter(nombre="mensual").update(gateway_plan_id=gateway_plan_id)
        logger.info(
            "Plan de Mercado Pago asegurado exitosamente con ID %s", gateway_plan_id
        )
        return str(gateway_plan_id)

    error_detail = (
        response_body.get("message") or response_body.get("error") or str(response_body)
    )
    logger.error(
        "Error al crear preapproval_plan en Mercado Pago (HTTP %s): %s",
        status_code,
        error_detail,
    )
    raise RuntimeError(f"Mercado Pago retornó un error ({status_code}): {error_detail}")


def crear_suscripcion_preapproval(
    usuario: Any,
    tipo_plan: str | Plan = "mensual",
    request: Any | None = None,
) -> dict[str, Any]:
    """
    Crea una suscripción de débito recurrente (Preapproval) en Mercado Pago y
    asocia el ID devuelto a la Suscripcion del usuario local.
    """
    try:
        sdk = obtener_sdk_mercadopago()
    except ImproperlyConfigured as e:
        logger.error(
            "Configuración inválida al inicializar MercadoPago para usuario %s: %s",
            getattr(usuario, "id", None),
            e,
        )
        return {
            "error": "La pasarela de pagos no está configurada correctamente en el servidor.",
            "status": "error",
        }
    except Exception as e:
        logger.exception(
            "Error inesperado al inicializar cliente MercadoPago para usuario %s: %s",
            getattr(usuario, "id", None),
            e,
        )
        return {
            "error": f"Error inesperado al inicializar la pasarela de pagos: {str(e)}",
            "status": "error",
        }

    # Resolver objeto Plan
    if isinstance(tipo_plan, Plan):
        plan = tipo_plan
        plan_slug = plan.nombre
    else:
        plan_slug = str(tipo_plan)
        plan = Plan.objects.filter(nombre=plan_slug).first()

    precio = (
        float(plan.precio_mensual)
        if plan
        else float(getattr(settings, "PRECIO_MENSUAL", Decimal("8999.00")))
    )
    frequency = plan.periodicidad_meses if plan else 1
    reason = f"Suscripción {plan.nombre if plan else 'Mensual'} - SIRADIG Auto"

    # Resolver back_url (RN-007 / settings.MERCADOPAGO_BACK_URL)
    base_back_url = getattr(settings, "MERCADOPAGO_BACK_URL", "")
    auto_return_url = getattr(settings, "MERCADOPAGO_AUTO_RETURN_URL", "")

    if auto_return_url and auto_return_url != getattr(
        settings, "MERCADOPAGO_BACK_URL", ""
    ):
        back_url = auto_return_url
    elif base_back_url and not (
        base_back_url.startswith("http://localhost:8000")
        and auto_return_url
        and not auto_return_url.startswith("http://localhost:8000")
    ):
        base_clean = base_back_url.rstrip("/")
        if base_clean.endswith("/suscripciones/retorno") or base_clean.endswith(
            "/suscripciones/pago-exitoso"
        ):
            back_url = base_clean
        else:
            back_url = f"{base_clean}/suscripciones/pago-exitoso/"
    elif auto_return_url:
        back_url = auto_return_url
    elif request:
        try:
            back_url = request.build_absolute_uri(reverse("subscriptions:retorno"))
        except Exception:
            back_url = request.build_absolute_uri("/")
    else:
        back_url = "http://localhost:8000/suscripciones/pago-exitoso/"

    payer_email = (
        usuario.email
        if getattr(usuario, "email", None)
        else f"user_{usuario.id}@siradigauto.com"
    )

    preapproval_data: dict[str, Any] = {
        "payer_email": payer_email,
        "back_url": back_url,
        "reason": reason,
        "external_reference": f"{usuario.id}:{plan_slug}",
        "status": "pending",
        "auto_recurring": {
            "frequency": frequency,
            "frequency_type": "months",
            "transaction_amount": precio,
            "currency_id": "ARS",
        },
    }

    # Si hay gateway_plan_id asociado en el Plan o en settings, podemos vincular preapproval_plan_id
    plan_id_asociado = getattr(plan, "gateway_plan_id", "") or getattr(
        settings, "MERCADOPAGO_PREAPPROVAL_PLAN_ID", ""
    )
    if plan_id_asociado:
        preapproval_data["preapproval_plan_id"] = plan_id_asociado

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

    try:
        status_code = mp_response.get("status")
        response_body = mp_response.get("response", {})

        if status_code in (200, 201):
            gateway_subscription_id = response_body.get("id", "")
            init_point = response_body.get("init_point", "")

            suscripcion, _ = Suscripcion.objects.get_or_create(usuario=usuario)
            if plan:
                suscripcion.plan = plan
            if gateway_subscription_id:
                suscripcion.gateway_subscription_id = gateway_subscription_id
            suscripcion.save(
                update_fields=["plan", "gateway_subscription_id"]
                if plan
                else ["gateway_subscription_id"]
            )

            return {
                "id": gateway_subscription_id,
                "init_point": init_point,
                "status": response_body.get("status", "pending"),
            }

        error_detail = (
            response_body.get("message")
            or response_body.get("error")
            or str(response_body)
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
    except Exception as e:
        logger.exception(
            "Error procesando la respuesta de suscripción en MercadoPago: %s", e
        )
        return {
            "error": f"Error procesando la respuesta del servicio de pagos: {str(e)}",
            "status": "error",
        }


def cancelar_suscripcion_preapproval(suscripcion_o_id: Suscripcion | str) -> bool:
    """
    Cancela la suscripción recurrente en Mercado Pago vía API de Preapproval
    y actualiza el estado local del modelo Suscripcion a 'cancelada' si se proveyó un objeto.
    Acepta tanto una instancia de Suscripcion como un string con gateway_subscription_id.
    """
    if isinstance(suscripcion_o_id, Suscripcion):
        suscripcion = suscripcion_o_id
        gateway_sub_id = suscripcion.gateway_subscription_id or ""
    else:
        gateway_sub_id = str(suscripcion_o_id).strip()
        suscripcion = Suscripcion.objects.filter(
            gateway_subscription_id=gateway_sub_id
        ).first()

    if gateway_sub_id:
        try:
            sdk = obtener_sdk_mercadopago()
            update_response = sdk.preapproval().update(
                gateway_sub_id,
                {"status": "cancelled"},
            )
            resp_status = update_response.get("status")
            if resp_status not in (200, 201):
                logger.warning(
                    "Respuesta inesperada al cancelar en MercadoPago Preapproval %s: HTTP %s - %s",
                    gateway_sub_id,
                    resp_status,
                    update_response.get("response"),
                )
        except Exception as exc:
            logger.exception(
                "Fallo al invocar cancelación en MercadoPago para id %s: %s",
                gateway_sub_id,
                exc,
            )

    if suscripcion:
        suscripcion.estado = "cancelada"
        suscripcion.fecha_cancelacion = timezone.now()
        suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
    return True
