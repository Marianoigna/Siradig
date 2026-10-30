import math
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from subscriptions.models import Suscripcion


def dias_restantes_trial(usuario: Any) -> int:
    """
    Calcula los días restantes de trial gratuito para un usuario según RN-001 y RN-002:
    max(0, ceil((trial_start_date + TRIAL_DURATION_DAYS - now()).total_seconds() / 86400))
    Usa user.profile.trial_start_date y settings.TRIAL_DURATION_DAYS (default 15).
    Si no está autenticado o no tiene perfil/trial_start_date, retorna 0.
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return 0

    profile = getattr(usuario, "profile", None)
    if not profile:
        return 0

    trial_start_date = getattr(profile, "trial_start_date", None)
    if not trial_start_date:
        return 0

    duracion_dias = getattr(settings, "TRIAL_DURATION_DAYS", 15)
    fin_trial = trial_start_date + timedelta(days=duracion_dias)
    segundos_restantes = (fin_trial - timezone.now()).total_seconds()

    return max(0, math.ceil(segundos_restantes / 86400))


def calcular_dias_restantes_trial(usuario: Any) -> int | None:
    """
    Helper retrocompatible que retorna None si el usuario no tiene perfil o no está autenticado,
    o int con los días restantes de trial.
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return None

    profile = getattr(usuario, "profile", None)
    if not profile or not getattr(profile, "trial_start_date", None):
        return None

    return dias_restantes_trial(usuario)


def usuario_tiene_acceso_activo(usuario: Any) -> bool:
    """
    Determina si un usuario tiene acceso activo según RF-004, RN-001, RN-002, RN-003, RN-005:
    - Retorna True si es superuser o staff.
    - Retorna True si tiene Suscripcion donde fecha_vencimiento > now() y estado in ('activa', 'cancelada')
      (según RN-005, el usuario conserva acceso hasta la fecha de vencimiento pagada aunque esté cancelada).
    - Retorna True si dias_restantes_trial(usuario) > 0.
    - En cualquier otro caso retorna False.
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False

    if getattr(usuario, "is_superuser", False) or getattr(usuario, "is_staff", False):
        return True

    suscripcion: Suscripcion | None = getattr(usuario, "suscripcion", None)
    if suscripcion and suscripcion.fecha_vencimiento:
        if (
            suscripcion.estado in ("activa", "cancelada")
            and suscripcion.fecha_vencimiento > timezone.now()
        ):
            return True

    if dias_restantes_trial(usuario) > 0:
        return True

    return False


def obtener_estado_cuenta(usuario: Any) -> dict[str, Any]:
    """
    Devuelve un diccionario estructurado con el estado de cuenta y acceso del usuario:
    - tiene_acceso: bool
    - en_trial: bool
    - dias_trial_restantes: int
    - suscripcion_activa: bool
    - estado_suscripcion: str | None
    - fecha_vencimiento: datetime | None
    - motivo: str
    - suscripcion: Suscripcion | None
    """
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {
            "tiene_acceso": False,
            "en_trial": False,
            "dias_trial_restantes": 0,
            "suscripcion_activa": False,
            "estado_suscripcion": None,
            "fecha_vencimiento": None,
            "motivo": "sin_acceso",
            "suscripcion": None,
            "dias_restantes_trial": None,
            "dias_restantes_suscripcion": None,
            "es_trial": False,
        }

    es_admin = bool(
        getattr(usuario, "is_superuser", False) or getattr(usuario, "is_staff", False)
    )

    suscripcion: Suscripcion | None = getattr(usuario, "suscripcion", None)
    dias_trial = dias_restantes_trial(usuario)

    sub_vigente = False
    estado_sub = None
    fecha_venc = None
    dias_restantes_sub: int | None = None

    if suscripcion:
        estado_sub = suscripcion.estado
        fecha_venc = suscripcion.fecha_vencimiento
        if fecha_venc:
            segundos_sub = (fecha_venc - timezone.now()).total_seconds()
            dias_restantes_sub = max(0, math.ceil(segundos_sub / 86400))
        if (
            estado_sub in ("activa", "cancelada")
            and fecha_venc
            and fecha_venc > timezone.now()
        ):
            sub_vigente = True

    tiene_acceso = es_admin or sub_vigente or (dias_trial > 0)
    en_trial = (dias_trial > 0) and not sub_vigente and not es_admin

    if es_admin:
        motivo = "admin"
    elif sub_vigente:
        motivo = "suscripcion_activa"
    elif dias_trial > 0:
        motivo = "trial_activo"
    elif suscripcion and (
        suscripcion.estado in ("vencida", "cancelada")
        or (suscripcion.fecha_vencimiento and not sub_vigente)
    ):
        motivo = "suscripcion_vencida"
    else:
        motivo = "trial_expirado"

    return {
        "tiene_acceso": tiene_acceso,
        "en_trial": en_trial,
        "dias_trial_restantes": dias_trial,
        "suscripcion_activa": sub_vigente,
        "estado_suscripcion": estado_sub,
        "fecha_vencimiento": fecha_venc,
        "motivo": motivo,
        "suscripcion": suscripcion,
        # Claves de compatibilidad adicional
        "dias_restantes_trial": dias_trial,
        "dias_restantes_suscripcion": dias_restantes_sub,
        "es_trial": en_trial,
    }


def obtener_estado_acceso(usuario: Any) -> dict[str, Any]:
    """
    Alias retrocompatible para obtener_estado_cuenta.
    """
    return obtener_estado_cuenta(usuario)
