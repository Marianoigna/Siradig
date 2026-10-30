from __future__ import annotations

from typing import Any

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from subscriptions.services.access import usuario_tiene_acceso_activo


class HasActiveSubscriptionOrTrial(permissions.BasePermission):
    """
    Permiso DRF que restringe el acceso a la API a usuarios con período de prueba
    o suscripción de pago activa en Mercado Pago.
    Responde HTTP 403 Forbidden con un mensaje claro y código 'subscription_required' (CA-002, RF-011).
    """

    message = "Acceso restringido: Período de prueba vencido. Se requiere una suscripción activa."
    code = "subscription_required"

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            # Los usuarios anónimos son manejados por permissions.IsAuthenticated (HTTP 401)
            return True

        if usuario_tiene_acceso_activo(user):
            return True

        raise PermissionDenied(
            detail={
                "detail": self.message,
                "code": self.code,
            },
            code=self.code,
        )
