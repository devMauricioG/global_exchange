"""
Módulo de procesadores de contexto para la gestión dinámica de roles y permisos.

Este módulo extrae y analiza las funciones y roles asignados a los usuarios
desde los tokens JWT / OIDC de Keycloak y los grupos nativos de Django, inyectando
variables globales de autenticación y autorización en el contexto de todas las plantillas.
"""

from typing import Any, Dict, Set
from django.http import HttpRequest


def auth_roles(request: HttpRequest) -> Dict[str, Any]:
    """
    Procesador de contexto de Django que inyecta información de roles y permisos del usuario.

    Analiza:
    1. Grupos de Django sincronizados a partir de los claims OIDC/JWT (`admin`, `operator`, `user`).
    2. Banderas de superusuario y staff de Django (`is_superuser`, `is_staff`).
    3. Claims de roles en sesión almacenadas por el flujo OIDC si estuvieran disponibles.

    :param request: Objeto de solicitud HTTP entrante.
    :type request: django.http.HttpRequest
    :return: Diccionario con variables de contexto sobre roles del usuario.
    :rtype: dict

    Variables inyectadas en el contexto:
        * ``user_roles`` (*list[str]*): Lista de códigos de roles normalizados en minúsculas (ej. ``['admin', 'operator']``).
        * ``is_admin`` (*bool*): Verdadero si el usuario tiene rol 'admin' o es superusuario.
        * ``is_operator`` (*bool*): Verdadero si el usuario tiene rol 'operator' o permisos de administración.
        * ``is_user_role`` (*bool*): Verdadero si el usuario tiene rol 'user' asignado.
        * ``primary_role`` (*str*): Nombre descriptivo en español del rol principal (ej. 'Administrador', 'Operador', 'Usuario').
        * ``primary_role_code`` (*str*): Código identificador del rol principal ('admin', 'operator', 'user', 'guest').
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'user_roles': [],
            'is_admin': False,
            'is_operator': False,
            'is_user_role': False,
            'primary_role': 'Invitado',
            'primary_role_code': 'guest',
        }

    user = request.user
    roles: Set[str] = set()

    # 1. Obtener roles asignados en los grupos de Django (mapeados desde OIDC)
    for group in user.groups.all():
        roles.add(group.name.lower())

    # 2. Superusuario siempre adquiere rol admin y operador
    if user.is_superuser:
        roles.add('admin')
        roles.add('operator')

    # 3. Staff adquiere al menos rol operator si no tiene rol explícito
    if user.is_staff and not roles:
        roles.add('operator')

    # 4. Si no tiene roles asignados pero está autenticado, asigna rol básico de usuario
    if not roles:
        roles.add('user')

    is_admin = 'admin' in roles or user.is_superuser
    is_operator = 'operator' in roles or is_admin
    is_user_role = 'user' in roles

    if is_admin:
        primary_role = 'Administrador'
        primary_role_code = 'admin'
    elif 'operator' in roles:
        primary_role = 'Operador'
        primary_role_code = 'operator'
    else:
        primary_role = 'Usuario'
        primary_role_code = 'user'

    from django.conf import settings
    public_url = getattr(settings, 'KEYCLOAK_PUBLIC_URL', 'http://localhost:8080')
    realm = getattr(settings, 'KEYCLOAK_REALM', 'GlobalExchangeRealm')
    keycloak_manage_2fa_url = f"{public_url}/realms/{realm}/account/#/security/signing-and-log-in"

    mfa_enabled = getattr(user, 'mfa_enabled', False)

    return {
        'user_roles': sorted(list(roles)),
        'is_admin': is_admin,
        'is_operator': is_operator,
        'is_user_role': is_user_role,
        'primary_role': primary_role,
        'primary_role_code': primary_role_code,
        'mfa_enabled': mfa_enabled,
        'keycloak_manage_2fa_url': keycloak_manage_2fa_url,
    }
