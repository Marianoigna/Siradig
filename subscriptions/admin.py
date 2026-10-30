from django.contrib import admin

from .models import Pago, Plan, Suscripcion


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "precio_mensual",
        "dias_duracion",
        "gateway_plan_id",
        "activo",
        "fecha_creacion",
    )
    list_filter = ("activo",)
    search_fields = ("nombre", "descripcion", "gateway_plan_id")
    ordering = ("precio_mensual",)


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "plan",
        "estado",
        "fecha_inicio",
        "fecha_vencimiento",
        "esta_vigente",
        "gateway_subscription_id",
    )
    list_filter = ("estado", "plan")
    search_fields = (
        "usuario__username",
        "usuario__email",
        "gateway_subscription_id",
        "codigo_cancelacion",
    )
    readonly_fields = ("fecha_inicio", "esta_vigente")
    ordering = ("-fecha_inicio",)

    @admin.display(boolean=True, description="Vigente")
    def esta_vigente(self, obj):
        return obj.esta_vigente


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        "referencia_gateway",
        "usuario",
        "suscripcion",
        "monto",
        "metodo",
        "exitoso",
        "fecha",
    )
    list_filter = ("exitoso", "metodo", "fecha")
    search_fields = (
        "referencia_gateway",
        "usuario__username",
        "usuario__email",
        "suscripcion__usuario__username",
    )
    readonly_fields = ("fecha",)
    ordering = ("-fecha",)
