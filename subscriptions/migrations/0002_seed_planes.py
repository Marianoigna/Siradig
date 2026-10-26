from decimal import Decimal

from django.db import migrations


def seed_planes(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    planes_data = [
        {
            "tipo": "mensual",
            "nombre": "Plan Mensual",
            "precio": Decimal("15000.00"),
            "periodicidad_meses": 1,
            "dias_duracion": 30,
            "descripcion": "Acceso completo mensual a SIRADIG Auto",
            "activo": True,
        },
        {
            "tipo": "anual",
            "nombre": "Plan Anual",
            "precio": Decimal("150000.00"),
            "periodicidad_meses": 12,
            "dias_duracion": 365,
            "descripcion": "Acceso completo anual a SIRADIG Auto con descuento",
            "activo": True,
        },
    ]

    for plan_kwargs in planes_data:
        tipo = plan_kwargs.pop("tipo")
        Plan.objects.update_or_create(tipo=tipo, defaults=plan_kwargs)


def unseed_planes(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.filter(tipo__in=["mensual", "anual"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_planes, reverse_code=unseed_planes),
    ]
