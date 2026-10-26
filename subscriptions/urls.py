from django.urls import path

from subscriptions.views import (
    cancelar_suscripcion_view,
    iniciar_checkout_view,
    mercadopago_webhook_view,
    planes_view,
    retorno_view,
)

app_name = "subscriptions"

urlpatterns = [
    path("planes/", planes_view, name="planes"),
    path(
        "checkout/<str:tipo_plan>/",
        iniciar_checkout_view,
        name="iniciar_checkout",
    ),
    path("retorno/", retorno_view, name="retorno"),
    path("cancelar/", cancelar_suscripcion_view, name="cancelar"),
    path("webhook/mercadopago/", mercadopago_webhook_view, name="webhook"),
]
