"""
Módulo de etiquetas y filtros personalizados de plantilla para autorización basada en roles.

Provee utilidades para verificar permisos y roles de usuario directamente en las plantillas Django
(:class:`~django.template.Library`), facilitando el renderizado condicional de menús, botones y
elementos de la interfaz según los roles del token JWT / Keycloak.
"""

from typing import Any, List, Set
from django import template
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.utils.safestring import mark_safe

register = template.Library()


def _extract_user_roles(user: Any) -> Set[str]:
    """
    Función interna para extraer el conjunto de roles asignados a un usuario.

    :param user: Instancia del usuario actual (autenticado o anónimo).
    :return: Conjunto de códigos de roles en minúsculas.
    :rtype: set[str]
    """
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return set()

    roles: Set[str] = set()
    for group in user.groups.all():
        roles.add(group.name.lower())

    if getattr(user, 'is_superuser', False):
        roles.add('admin')
        roles.add('operator')
        roles.add('cajero')

    if getattr(user, 'is_staff', False) and not roles:
        roles.add('operator')
        roles.add('cajero')

    if not roles:
        roles.add('user')

    return roles


@register.filter(name='has_role')
def has_role(user: Any, role_name: str) -> bool:
    """
    Filtro de plantilla que evalúa si un usuario posee un rol específico.

    Uso en plantilla:
        .. code-block:: django

            {% if user|has_role:"admin" %}
                <!-- Contenido exclusivo para administradores -->
            {% endif %}

    :param user: Usuario a evaluar.
    :type user: django.contrib.auth.models.User
    :param role_name: Nombre o código del rol (ej. 'admin', 'operator', 'user').
    :type role_name: str
    :return: True si el usuario posee el rol solicitado o privilegios superiores.
    :rtype: bool
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    roles = _extract_user_roles(user)
    target = role_name.strip().lower()

    if target == 'admin':
        return 'admin' in roles or getattr(user, 'is_superuser', False)
    elif target == 'operator':
        return 'operator' in roles or 'admin' in roles or getattr(user, 'is_staff', False)
    elif target in ('cajero', 'cashier'):
        return 'cajero' in roles or 'operator' in roles or 'admin' in roles or getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)
    elif target == 'user':
        return 'user' in roles or len(roles) > 0

    return target in roles


@register.filter(name='has_any_role')
def has_any_role(user: Any, roles_list_str: str) -> bool:
    """
    Filtro de plantilla que evalúa si un usuario posee al menos uno de los roles indicados.

    Uso en plantilla:
        .. code-block:: django

            {% if user|has_any_role:"admin,operator" %}
                <!-- Visible para Administradores u Operadores -->
            {% endif %}

    :param user: Usuario a evaluar.
    :type user: django.contrib.auth.models.User
    :param roles_list_str: Cadena con roles separados por coma (ej. 'admin,operator').
    :type roles_list_str: str
    :return: True si el usuario tiene al menos uno de los roles especificados.
    :rtype: bool
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    target_roles = [r.strip().lower() for r in roles_list_str.split(',') if r.strip()]
    return any(has_role(user, r) for r in target_roles)


@register.simple_tag
def user_role_badge(user: Any) -> str:
    """
    Etiqueta de plantilla que genera un badge HTML estilizado para el rol principal del usuario.

    Uso en plantilla:
        .. code-block:: django

            {% user_role_badge request.user %}

    :param user: Usuario del cual generar el badge.
    :type user: django.contrib.auth.models.User
    :return: Fragmento HTML seguro que representa visualmente el rol del usuario.
    :rtype: str
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return mark_safe('<span class="role-badge role-guest">Invitado</span>')

    roles = _extract_user_roles(user)
    if 'admin' in roles or getattr(user, 'is_superuser', False):
        return mark_safe('<span class="role-badge role-admin">👑 Administrador</span>')
    elif 'operator' in roles or getattr(user, 'is_staff', False):
        return mark_safe('<span class="role-badge role-operator">⚡ Operador</span>')
    elif 'cajero' in roles or 'cashier' in roles:
        return mark_safe('<span class="role-badge role-cajero">💵 Cajero</span>')
    else:
        return mark_safe('<span class="role-badge role-user">👤 Usuario</span>')
