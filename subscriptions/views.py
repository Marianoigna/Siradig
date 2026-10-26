from __future__ import annotations

import json
import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from subscriptions.models import Plan, Suscripcion
from subscriptions.services.access import obtener_estado_cuenta
from subscriptions.services.mercadopago import (
    cancelar_suscripcion_preapproval,
    crear_suscripcion_preapproval,
)
from subscriptions.services.webhook import (
    procesar_notificacion_webhook,
    validar_firma_mercadopago,
)

logger = logging.getLogger(__name__)


@login_required
def planes_view(request: HttpRequest) -> HttpResponse:
    """
    Muestra la grilla de planes activos disponibles y el estado actual de la cuenta
    (período de prueba o suscripción activa).
    """
    planes = Plan.objects.filter(activo=True).order_by("precio")
    estado_cuenta = obtener_estado_cuenta(request.user)
    suscripcion = getattr(request.user, "suscripcion", None)

    context = {
        "planes": planes,
        "estado_cuenta": estado_cuenta,
        "suscripcion": suscripcion,
    }
    return render(request, "subscriptions/planes.html", context)


@login_required
def iniciar_checkout_view(request: HttpRequest, tipo_plan: str) -> HttpResponse:
    """
    Inicia la suscripción de débito automático recurrente en MercadoPago para el plan solicitado.
    Si es GET, redirige amigablemente a la lista de planes.
    Si es POST, ejecuta la creación de la suscripción de forma defensiva.
    Si MercadoPago devuelve init_point, redirige con HTTP 302 al checkout.
    Si falla, notifica el error vía Django messages y redirige a la grilla de planes sin arrojar 500.
    """
    if request.method == "GET":
        messages.info(request, "Seleccioná tu plan para continuar con la suscripción.")
        return redirect("subscriptions:planes")

    if request.method != "POST":
        return redirect("subscriptions:planes")

    plan = get_object_or_404(Plan, tipo=tipo_plan, activo=True)

    try:
        resultado = crear_suscripcion_preapproval(
            usuario=request.user,
            plan=plan,
            request=request,
        )
    except Exception as e:
        logger.exception(
            "Excepción no controlada al iniciar checkout para usuario %s: %s",
            request.user.id,
            e,
        )
        resultado = {
            "error": "No se pudo iniciar el proceso de pago. Por favor intenta nuevamente.",
            "status": "error",
        }

    init_point = resultado.get("init_point")
    if init_point:
        return HttpResponseRedirect(init_point)

    error_msg = (
        resultado.get("error")
        or "No se pudo iniciar el proceso de pago. Por favor intenta nuevamente."
    )
    logger.error(
        "Fallo en checkout de suscripción para usuario %s (plan %s): %s",
        request.user.id,
        tipo_plan,
        error_msg,
    )
    messages.error(request, error_msg)
    return redirect("subscriptions:planes")


@login_required
def retorno_view(request: HttpRequest) -> HttpResponse:
    """
    Vista de retorno desde el checkout de MercadoPago.
    Informa al usuario sobre el procesamiento de su pago/suscripción
    y renderiza la pantalla de confirmación o redirige al dashboard.
    """
    status = request.GET.get("status") or request.GET.get("collection_status")
    if status == "approved":
        messages.success(
            request,
            "¡Tu pago fue aprobado exitosamente! Tu cuenta está siendo activada.",
        )
    else:
        messages.info(
            request,
            "Hemos recibido tu solicitud de suscripción. MercadoPago está procesando la operación.",
        )

    return render(request, "subscriptions/retorno.html", {"status": status})


@login_required
@require_POST
def cancelar_suscripcion_view(request: HttpRequest) -> HttpResponse:
    """
    Cancela el débito recurrente de la suscripción del usuario en MercadoPago
    y actualiza su estado local a cancelada preservando el acceso hasta la fecha de vencimiento.
    """
    suscripcion: Suscripcion | None = getattr(request.user, "suscripcion", None)
    if not suscripcion or suscripcion.estado != "activa":
        messages.warning(request, "No tenés una suscripción activa para cancelar.")
        return redirect("subscriptions:planes")

    cancelar_suscripcion_preapproval(suscripcion)
    messages.success(
        request,
        f"Tu renovación automática ha sido cancelada. Mantendrás el acceso a la plataforma hasta el {suscripcion.fecha_vencimiento.strftime('%d/%m/%Y') if suscripcion.fecha_vencimiento else 'vencimiento del período actual'}.",
    )
    return redirect("subscriptions:planes")


@csrf_exempt
@require_POST
def mercadopago_webhook_view(request: HttpRequest) -> HttpResponse:
    """
    Endpoint público para recibir notificaciones HTTP POST de MercadoPago (Webhooks / IPN).
    Valida firma HMAC si está configurada (HTTP 401 si falla) y procesa la notificación
    de manera idempotente y atómica, respondiendo siempre HTTP 200 OK a MercadoPago.
    """
    if not validar_firma_mercadopago(request):
        logger.warning("Firma inválida o no autorizada en mercadopago_webhook_view.")
        return JsonResponse({"error": "Firma no autorizada o inválida"}, status=401)

    try:
        payload: dict[str, Any] = (
            json.loads(request.body.decode("utf-8")) if request.body else {}
        )
    except Exception:
        payload = {}

    query_params = dict(request.GET.items())

    exito, mensaje = procesar_notificacion_webhook(
        payload=payload, query_params=query_params
    )
    logger.info("Resultado webhook MercadoPago: exito=%s, detalle=%s", exito, mensaje)

    return JsonResponse({"status": "ok", "message": mensaje}, status=200)
