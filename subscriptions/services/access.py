import math
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from subscriptions.models import Suscripcion


def calcular_dias_restantes_trial(usuario: Any) -> int | None:
    """
    Calcula los días restantes de trial gratuito para un usuario según RN-001 y RN-002:
    max(0, ceil((trial_start_date + TRIAL_DURATION_DAYS - now()).total_seconds() / 86400))
    Si no está autenticado o no tiene perfil, retorna None.
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return None

    profile = getattr(usuario, "profile", None)
    if not profile:
        return None

    trial_start_date = getattr(profile, "trial_start_date", None)
    if not trial_start_date:
        return None

    duracion_dias = getattr(settings, "TRIAL_DURATION_DAYS", 15)
    fin_trial = trial_start_date + timedelta(days=duracion_dias)
    segundos_restantes = (fin_trial - timezone.now()).total_seconds()

    return max(0, math.ceil(segundos_restantes / 86400))


def obtener_estado_acceso(usuario: Any) -> dict[str, Any]:
    """
    Determina de manera centralizada el estado de acceso de un usuario (trial o suscripción de pago).

    Retorna un diccionario con:
      - tiene_acceso: bool (True si está en trial o tiene suscripción activa vigente).
      - motivo: 'trial_activo' | 'suscripcion_activa' | 'trial_expirado' | 'suscripcion_vencida' | 'sin_acceso'.
      - dias_restantes_trial: int o None.
      - dias_restantes_suscripcion: int o None.
      - es_trial: bool.
      - suscripcion: Suscripcion o None.
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {
            "tiene_acceso": False,
            "motivo": "sin_acceso",
            "dias_restantes_trial": None,
            "dias_restantes_suscripcion": None,
            "es_trial": False,
            "suscripcion": None,
        }

    # Obtener suscripción asociada si existe
    suscripcion: Suscripcion | None = getattr(usuario, "suscripcion", None)

    dias_restantes_suscripcion: int | None = None
    if suscripcion and suscripcion.fecha_vencimiento:
        segundos_sub = (suscripcion.fecha_vencimiento - timezone.now()).total_seconds()
        dias_restantes_suscripcion = max(0, math.ceil(segundos_sub / 86400))

    dias_restantes_trial = calcular_dias_restantes_trial(usuario)

    # 1. Si tiene suscripción activa vigente (prevalencia según RN-003 / RF-004)
    if suscripcion and suscripcion.esta_vigente:
        return {
            "tiene_acceso": True,
            "motivo": "suscripcion_activa",
            "dias_restantes_trial": dias_restantes_trial,
            "dias_restantes_suscripcion": dias_restantes_suscripcion,
            "es_trial": False,
            "suscripcion": suscripcion,
        }

    # 2. Si está dentro del período de prueba (trial activo)
    if dias_restantes_trial is not None and dias_restantes_trial > 0:
        return {
            "tiene_acceso": True,
            "motivo": "trial_activo",
            "dias_restantes_trial": dias_restantes_trial,
            "dias_restantes_suscripcion": dias_restantes_suscripcion,
            "es_trial": True,
            "suscripcion": suscripcion,
        }

    # 3. Sin acceso activo: determinar motivo específico
    motivo = "trial_expirado"
    if suscripcion and (
        suscripcion.estado in ("vencida", "cancelada")
        or (suscripcion.fecha_vencimiento and not suscripcion.esta_vigente)
    ):
        motivo = "suscripcion_vencida"

    return {
        "tiene_acceso": False,
        "motivo": motivo,
        "dias_restantes_trial": dias_restantes_trial,
        "dias_restantes_suscripcion": dias_restantes_suscripcion,
        "es_trial": False,
        "suscripcion": suscripcion,
    }


def usuario_tiene_acceso_activo(usuario: Any) -> bool:
    """
    Función auxiliar rápida que devuelve True si el usuario tiene acceso habilitado (trial o suscripción).
    """
    estado = obtener_estado_acceso(usuario)
    return bool(estado.get("tiene_acceso", False))


def dias_restantes_trial(usuario: Any) -> int:
    """
    Alias / compatibilidad según especificación 007-tasks.md (T3).
    Retorna 0 si es None o <= 0.
    """
    dias = calcular_dias_restantes_trial(usuario)
    return dias if dias is not None else 0


def obtener_estado_cuenta(usuario: Any) -> dict[str, Any]:
    """
    Alias / compatibilidad con 007-tasks.md para vistas y templates.
    """
    return obtener_estado_acceso(usuario)
