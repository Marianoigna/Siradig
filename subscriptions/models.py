from django.conf import settings
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    TIPO_CHOICES = [
        ("mensual", "Mensual"),
        ("anual", "Anual"),
    ]

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, unique=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    periodicidad_meses = models.PositiveSmallIntegerField(default=1)
    dias_duracion = models.PositiveIntegerField(default=30)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ["precio"]

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()}) - ${self.precio}"


class Suscripcion(models.Model):
    ESTADO_CHOICES = [
        ("trial", "Prueba"),
        ("activa", "Activa"),
        ("vencida", "Vencida"),
        ("cancelada", "Cancelada"),
    ]

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suscripcion",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.SET_NULL,
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
    gateway_subscription_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
    )
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    codigo_cancelacion = models.CharField(max_length=6, blank=True, default="")

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"Suscripción de {self.usuario.username} ({self.get_estado_display()})"

    @property
    def esta_vigente(self) -> bool:
        if self.estado != "activa":
            return False
        if not self.fecha_vencimiento:
            return False
        return self.fecha_vencimiento > timezone.now()


class Pago(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pagos",
    )
    suscripcion = models.ForeignKey(
        Suscripcion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos",
    )
    referencia_gateway = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    metodo = models.CharField(max_length=50, default="mercadopago")
    exitoso = models.BooleanField(default=True)
    datos_gateway = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha_pago"]

    def __str__(self):
        estado_str = "Exitoso" if self.exitoso else "Fallido"
        return f"Pago {self.referencia_gateway} - ${self.monto} ({estado_str})"
