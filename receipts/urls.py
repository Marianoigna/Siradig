from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_home, name='dashboard'),
    path('telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
    path('api/receipts/pending/', views.PendingReceiptListAPIView.as_view(), name='api_receipts_pending'),
    path('api/receipts/<int:pk>/', views.ReceiptUpdateAPIView.as_view(), name='api_receipt_update'),
]
