"""
Procesadores de contexto de la aplicación de tasas (rates).
"""

from typing import Any, Dict

from django.http import HttpRequest

from .models import UserNotification


def unread_notifications(request: HttpRequest) -> Dict[str, Any]:
    """
    Inyecta en todas las plantillas la cantidad de notificaciones no leídas del usuario.

    Hace una única consulta de conteo por solicitud (el modelo tiene un índice
    sobre ``usuario`` y ``leido``). Para usuarios anónimos devuelve 0.

    :param request: Solicitud HTTP entrante.
    :type request: django.http.HttpRequest
    :return: Diccionario con la clave ``unread_notifications_count``.
    :rtype: dict
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'unread_notifications_count': 0}
    return {
        'unread_notifications_count': UserNotification.objects.filter(
            usuario=request.user, leido=False,
        ).count(),
    }