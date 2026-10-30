from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from subscriptions.models import Pago, Plan, Suscripcion
from subscriptions.services.mercadopago import obtener_sdk_mercadopago

logger = logging.getLogger(__name__)
User = get_user_model()


def validar_firma_mercadopago(request: Any) -> bool:
    """
    Valida la firma digital de MercadoPago provista en los encabezados HTTP.

    Headers requeridos:
      - x-signature: formato 'ts=<timestamp>,v1=<hash_hex>'
      - x-request-id: UUID o ID único del request

    Algoritmo:
      Si settings.MERCADOPAGO_WEBHOOK_SECRET no está configurado, loggea advertencia
      y retorna True para entornos de desarrollo / pruebas.
      Si está configurado, extrae 'ts' y 'v1', obtiene el ID del recurso (data.id o id
      desde query params o body JSON), construye la plantilla:
        template = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
      calcula HMAC-SHA256 con MERCADOPAGO_WEBHOOK_SECRET y compara de forma segura
      usando hmac.compare_digest.
    """
    secret = getattr(settings, "MERCADOPAGO_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning(
            "MERCADOPAGO_WEBHOOK_SECRET no configurado. Omitiendo validación de firma en dev/test."
        )
        return True

    x_signature = request.headers.get("x-signature") or request.META.get(
        "HTTP_X_SIGNATURE", ""
    )
    x_request_id = request.headers.get("x-request-id") or request.META.get(
        "HTTP_X_REQUEST_ID", ""
    )

    if not x_signature:
        logger.warning("Firma de MercadoPago ausente: x-signature no provisto.")
        return False

    # Extraer ts y v1 de x-signature (ej: "ts=1700000000,v1=abcdef...")
    ts_match = re.search(r"ts=([^,]+)", x_signature)
    v1_match = re.search(r"v1=([^,]+)", x_signature)

    if not ts_match or not v1_match:
        logger.warning(
            "Encabezado x-signature malformado (no contiene ts o v1): %s", x_signature
        )
        return False

    ts = ts_match.group(1).strip()
    v1 = v1_match.group(1).strip()

    # Obtener data.id desde query params o body JSON
    data_id = (
        request.GET.get("data.id")
        or request.GET.get("id")
        or request.GET.get("resource_id")
    )
    if not data_id:
        try:
            body = (
                json.loads(request.body.decode("utf-8"))
                if getattr(request, "body", None)
                else {}
            )
            data_id = (
                body.get("data", {}).get("id")
                or body.get("id")
                or body.get("resource_id")
            )
        except Exception:
            data_id = None

    if not data_id:
        logger.warning("No se pudo obtener data.id del webhook para validar la firma.")
        return False

    data_id = str(data_id)
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

    crypted = hmac.new(
        key=secret.encode("utf-8"),
        msg=manifest.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(crypted, v1):
        logger.warning(
            "Firma de MercadoPago inválida. Calculada: %s, Recibida: %s",
            crypted,
            v1,
        )
        return False

    return True


def procesar_notificacion_mercadopago(
    payload: dict[str, Any] | None, query_params: dict[str, Any] | None = None
) -> tuple[bool, str]:
    """
    Procesa las notificaciones enviadas por MercadoPago (Webhooks / IPN).
    Alias canónico según especificación T6 / RF-007 / RF-008.
    """
    return procesar_notificacion_webhook(payload, query_params)


def procesar_notificacion_webhook(
    payload: dict[str, Any] | None, query_params: dict[str, Any] | None = None
) -> tuple[bool, str]:
    """
    Procesa las notificaciones enviadas por MercadoPago (Webhooks / IPN).
    Maneja eventos de payment y subscription_preapproval / preapproval.

    Garantiza:
      1. Idempotencia estricta mediante Pago.referencia_gateway única.
      2. Transaccionalidad atómica (transaction.atomic).
      3. Acreditación de Suscripcion y extensión de vigencia (dias_duracion del Plan).
    """
    payload = payload or {}
    query_params = query_params or {}

    # Determinar tipo de tópico/evento y resource_id
    tipo_evento = (
        payload.get("type")
        or payload.get("topic")
        or query_params.get("type")
        or query_params.get("topic")
        or ""
    )

    resource_id = (
        payload.get("data", {}).get("id")
        or payload.get("id")
        or payload.get("resource_id")
        or query_params.get("data.id")
        or query_params.get("id")
    )

    if not resource_id:
        logger.warning(
            "Webhook recibido sin resource_id detectable. Payload: %s, Params: %s",
            payload,
            query_params,
        )
        return False, "Notificación sin resource_id"

    resource_id = str(resource_id)

    # Identificar si es un pago o una suscripción recurrente
    if tipo_evento in ("payment", "") and (
        "payment" in tipo_evento
        or query_params.get("topic") == "payment"
        or "data" in payload
    ):
        return _procesar_evento_pago(resource_id, payload)

    if tipo_evento in (
        "subscription_preapproval",
        "preapproval",
        "subscription_authorized_payment",
    ):
        return _procesar_evento_preapproval(resource_id, payload, tipo_evento)

    # Si no coincide exactamente pero tenemos resource_id, intentar como payment si es numérico
    if resource_id.isdigit():
        return _procesar_evento_pago(resource_id, payload)

    return _procesar_evento_preapproval(resource_id, payload, tipo_evento)


def _consultar_pago_mp(payment_id: str) -> dict[str, Any]:
    """Obtiene los detalles de un pago usando el SDK de MercadoPago."""
    try:
        sdk = obtener_sdk_mercadopago()
        payment_info = sdk.payment().get(payment_id)
        if payment_info.get("status") in (200, 201):
            return payment_info.get("response", {})
    except Exception as exc:
        logger.warning("Error al consultar pago %s en MercadoPago: %s", payment_id, exc)
    return {}


def _consultar_preapproval_mp(preapproval_id: str) -> dict[str, Any]:
    """Obtiene los detalles de una suscripción Preapproval usando el SDK de MercadoPago."""
    try:
        sdk = obtener_sdk_mercadopago()
        preapproval_info = sdk.preapproval().get(preapproval_id)
        if preapproval_info.get("status") in (200, 201):
            return preapproval_info.get("response", {})
    except Exception as exc:
        logger.warning(
            "Error al consultar preapproval %s en MercadoPago: %s", preapproval_id, exc
        )
    return {}


def _parse_external_reference(
    external_reference: str | None,
) -> tuple[Any | None, Plan | None]:
    """
    Parsea external_reference con formato '<user_id>:<tipo_plan>' o solo '<user_id>'.
    Retorna (usuario, plan).
    """
    if not external_reference:
        return None, None

    partes = str(external_reference).split(":")
    user_id = partes[0]
    tipo_plan = partes[1] if len(partes) > 1 else "mensual"

    try:
        usuario = User.objects.get(id=user_id)
    except (User.DoesNotExist, ValueError):
        usuario = None

    plan = Plan.objects.filter(nombre=tipo_plan).first()
    if not plan:
        plan = Plan.objects.filter(activo=True).first()

    return usuario, plan


def _procesar_evento_pago(payment_id: str, payload: dict[str, Any]) -> tuple[bool, str]:
    referencia = f"mp_pay_{payment_id}"

    # Idempotencia: Verificar si el pago ya fue registrado y fue exitoso (RN-006)
    if Pago.objects.filter(referencia_gateway=referencia, exitoso=True).exists():
        logger.info(
            "Pago %s ya procesado previamente (idempotente). Omitiendo.", referencia
        )
        return True, "Pago ya procesado (idempotente)"

    # Consultar detalle del pago en MercadoPago
    payment_data = _consultar_pago_mp(payment_id)
    if not payment_data:
        # Fallback si vino en el payload directamente
        payment_data = payload.get("data", {}) or payload

    status = payment_data.get("status", "")
    if status != "approved":
        logger.info(
            "Pago %s con status no aprobado (%s). Registrando o ignorando.",
            referencia,
            status,
        )
        return True, f"Pago no aprobado (status: {status})"

    # Obtener usuario y plan desde external_reference o payer_email
    external_ref = payment_data.get("external_reference")
    usuario, plan = _parse_external_reference(external_ref)

    if not usuario:
        payer_email = payment_data.get("payer", {}).get("email")
        if payer_email:
            usuario = User.objects.filter(email=payer_email).first()

    if not usuario:
        logger.warning(
            "No se encontró usuario local para el pago %s (ref: %s)",
            payment_id,
            external_ref,
        )
        return False, f"Usuario no encontrado para pago {payment_id}"

    # Si no se dedujo el plan, buscar el plan actual de su suscripción o el mensual por defecto
    if not plan:
        sub_actual = getattr(usuario, "suscripcion", None)
        plan = (
            sub_actual.plan
            if (sub_actual and sub_actual.plan)
            else Plan.objects.filter(activo=True).first()
        )

    monto = Decimal(str(payment_data.get("transaction_amount") or 0))

    with transaction.atomic():
        # Buscar o crear Suscripción del usuario primero (requerida por FK en Pago)
        suscripcion, _ = Suscripcion.objects.get_or_create(usuario=usuario)

        # Registrar o actualizar Pago
        pago, _ = Pago.objects.update_or_create(
            referencia_gateway=referencia,
            defaults={
                "usuario": usuario,
                "suscripcion": suscripcion,
                "monto": monto,
                "metodo": "mercadopago",
                "exitoso": True,
                "datos_gateway": payment_data,
            },
        )

        if plan:
            suscripcion.plan = plan

        dias = plan.dias_duracion if plan else 30

        # Extender vencimiento: si ya está activa y con vencimiento futuro, sumar a partir de allí
        ahora = timezone.now()
        base_vencimiento = (
            suscripcion.fecha_vencimiento
            if (suscripcion.fecha_vencimiento and suscripcion.fecha_vencimiento > ahora)
            else ahora
        )

        suscripcion.fecha_vencimiento = base_vencimiento + timedelta(days=dias)
        suscripcion.estado = "activa"
        suscripcion.save(update_fields=["plan", "estado", "fecha_vencimiento"])

    logger.info(
        "Pago %s procesado con éxito para usuario %s. Vencimiento: %s",
        referencia,
        usuario.username,
        suscripcion.fecha_vencimiento,
    )
    return True, "Pago procesado y suscripción activada"


def _procesar_evento_preapproval(
    preapproval_id: str, payload: dict[str, Any], tipo_evento: str
) -> tuple[bool, str]:
    preapproval_data = _consultar_preapproval_mp(preapproval_id)
    if not preapproval_data:
        preapproval_data = payload.get("data", {}) or payload

    status = preapproval_data.get("status", "")
    external_ref = preapproval_data.get("external_reference")
    usuario, plan = _parse_external_reference(external_ref)

    if not usuario:
        # Intentar buscar por gateway_subscription_id existente
        sub_existente = Suscripcion.objects.filter(
            gateway_subscription_id=preapproval_id
        ).first()
        if sub_existente:
            usuario = sub_existente.usuario

    if not usuario:
        payer_email = preapproval_data.get("payer_email")
        if payer_email:
            usuario = User.objects.filter(email=payer_email).first()

    if not usuario:
        logger.warning(
            "No se encontró usuario para suscripción Preapproval %s", preapproval_id
        )
        return False, f"Usuario no encontrado para suscripción {preapproval_id}"

    with transaction.atomic():
        suscripcion, _ = Suscripcion.objects.get_or_create(usuario=usuario)
        suscripcion.gateway_subscription_id = preapproval_id

        if plan:
            suscripcion.plan = plan

        if status == "authorized":
            suscripcion.estado = "activa"
            dias = plan.dias_duracion if plan else 30
            ahora = timezone.now()
            base_vencimiento = (
                suscripcion.fecha_vencimiento
                if (
                    suscripcion.fecha_vencimiento
                    and suscripcion.fecha_vencimiento > ahora
                )
                else ahora
            )
            suscripcion.fecha_vencimiento = base_vencimiento + timedelta(days=dias)
            suscripcion.save(
                update_fields=[
                    "gateway_subscription_id",
                    "plan",
                    "estado",
                    "fecha_vencimiento",
                ]
            )
            return True, "Suscripción Preapproval autorizada y activada"

        elif status == "cancelled":
            suscripcion.estado = "cancelada"
            suscripcion.fecha_cancelacion = timezone.now()
            suscripcion.save(
                update_fields=[
                    "gateway_subscription_id",
                    "estado",
                    "fecha_cancelacion",
                ]
            )
            return True, "Suscripción Preapproval cancelada"

        else:
            suscripcion.save(update_fields=["gateway_subscription_id"])
            return True, f"Suscripción Preapproval actualizada con status {status}"
