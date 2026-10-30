from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    NOMBRE_CHOICES = [
        ("gratuito", "Gratuito"),
        ("mensual", "Mensual"),
        ("anual", "Anual"),
    ]

    nombre = models.CharField(max_length=50, unique=True)
    precio_mensual = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("8999.00")
    )
    descripcion = models.TextField(blank=True)
    dias_duracion = models.PositiveIntegerField(default=30)
    gateway_plan_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Identificador del preapproval_plan en Mercado Pago",
    )
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ["precio_mensual"]

    def __str__(self):
        return f"{self.nombre} - ${self.precio_mensual}"

    @property
    def tipo(self):
        return self.nombre

    @property
    def precio(self):
        return self.precio_mensual

    @property
    def periodicidad_meses(self):
        return 12 if self.nombre == "anual" else 1


class Suscripcion(models.Model):
    ESTADO_CHOICES = [
        ("activa", "Activa"),
        ("vencida", "Vencida"),
        ("cancelada", "Cancelada"),
        ("trial", "Prueba"),
    ]

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suscripcion",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="suscripciones",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="trial",
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    gateway_subscription_id = models.CharField(  # noqa: DJ001
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )
    codigo_cancelacion = models.CharField(  # noqa: DJ001
        max_length=6, blank=True, null=True
    )
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"Suscripción de {self.usuario.username} ({self.get_estado_display()})"

    @property
    def esta_vigente(self) -> bool:
        if self.estado not in ("activa", "cancelada"):
            return False
        if not self.fecha_vencimiento:
            return False
        return self.fecha_vencimiento > timezone.now()


class Pago(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pagos_usuario",
        null=True,
        blank=True,
    )
    suscripcion = models.ForeignKey(
        Suscripcion,
        on_delete=models.CASCADE,
        related_name="pagos",
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    metodo = models.CharField(max_length=50, default="mercadopago")
    referencia_gateway = models.CharField(
        max_length=200,
        unique=True,
    )
    exitoso = models.BooleanField(default=True)
    datos_gateway = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha"]

    def __str__(self):
        estado_str = "Exitoso" if self.exitoso else "Fallido"
        return f"Pago {self.referencia_gateway} - ${self.monto} ({estado_str})"

    @property
    def fecha_pago(self):
        return self.fecha
