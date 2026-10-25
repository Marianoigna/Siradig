from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path("", views.landing_page, name="landing"),
    path(
        "terminos/",
        TemplateView.as_view(template_name="legal/terms.html"),
        name="terminos",
    ),
    path(
        "privacidad/",
        TemplateView.as_view(template_name="legal/privacy.html"),
        name="privacidad",
    ),
    path("dashboard/", views.dashboard_home, name="dashboard"),
    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),
    path(
        "api/receipts/pending/",
        views.PendingReceiptListAPIView.as_view(),
        name="api_receipts_pending",
    ),
    path(
        "api/receipts/<int:pk>/",
        views.ReceiptUpdateAPIView.as_view(),
        name="api_receipt_update",
    ),
]
