from django.contrib import admin

from .models import Receipt, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'trial_start_date', 'telegram_chat_id')
    search_fields = ('user__username', 'user__email', 'telegram_chat_id')


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('user', 'razon_social', 'importe_total', 'estado', 'origen', 'created_at')
    list_filter = ('estado', 'origen')
    search_fields = ('razon_social', 'cuit_emisor', 'numero_comprobante')
