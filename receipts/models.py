import secrets

from django.conf import settings
from django.db import models


def _generate_token():
    return secrets.token_urlsafe(24)


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    trial_start_date = models.DateTimeField(auto_now_add=True)
    telegram_chat_id = models.CharField(max_length=64, blank=True, null=True, unique=True)
    # shown to the user as a Telegram deep-link (t.me/<bot>?start=<token>) to link their account
    telegram_link_token = models.CharField(max_length=64, default=_generate_token, unique=True)

    def __str__(self):
        return f'Perfil de {self.user}'


class Receipt(models.Model):
    ORIGEN_CHOICES = [
        ('telegram', 'Telegram'),
        ('upload_web', 'Carga manual (web)'),
    ]
    ESTADO_CHOICES = [
        ('pendiente_revision', 'Pendiente de revisión'),
        ('pendiente_carga', 'Pendiente de carga en SIRADIG'),
        ('cargado_en_siradig', 'Cargado en SIRADIG'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='receipts')
    archivo_original = models.FileField(upload_to='receipts/%Y/%m/')

    fecha_emision = models.CharField(max_length=20, blank=True)
    cuit_emisor = models.CharField(max_length=11, blank=True)
    razon_social = models.CharField(max_length=255, blank=True)
    tipo_comprobante = models.CharField(max_length=50, blank=True)
    letra = models.CharField(max_length=5, blank=True)
    numero_comprobante = models.CharField(max_length=50, blank=True) # Mantenemos este por compatibilidad
    punto_venta = models.CharField(max_length=5, blank=True)         # NUEVO
    numero_solo = models.CharField(max_length=8, blank=True)         # NUEVO
    importe_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    importe_iva = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # MVP: solo se soporta la categoría "Gastos de Adquisición de Indumentaria y Equipamiento"
    categoria_gasto_siradig = models.CharField(max_length=100, blank=True)

    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente_revision')
    raw_ocr_json = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.razon_social or "sin nombre"} - {self.importe_total}'
