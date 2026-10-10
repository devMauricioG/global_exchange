"""
Módulo de backends de autenticación personalizados para la integración con Keycloak.

Extiende :class:`mozilla_django_oidc.auth.OIDCAuthenticationBackend` para:
- Crear usuarios automáticamente a partir de claims del token OIDC/JWT.
- Actualizar datos del perfil de usuario en cada inicio de sesión.
- Mapear roles de Keycloak a grupos y permisos nativos de Django.
"""

import logging
from typing import Any, Dict, List, Optional
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser, Group
from django.db.models import QuerySet
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

logger = logging.getLogger(__name__)


class KeycloakOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Backend OIDC que integra Keycloak con el sistema de usuarios de Django.

    Claims esperadas del token ID de Keycloak:
        * ``email``: Correo electrónico del usuario.
        * ``preferred_username``: Nombre de usuario en Keycloak.
        * ``given_name``: Nombre de pila.
        * ``family_name``: Apellido.
        * ``realm_roles``: Lista de roles del realm (requiere protocol mapper en Keycloak).
    """

    def create_user(self, claims: Dict[str, Any]) -> AbstractBaseUser:
        """
        Crea un nuevo usuario de Django a partir de las claims del token OIDC.

        Se invoca automáticamente cuando un usuario inicia sesión por primera
        vez vía Keycloak y no existe previamente en la base de datos local.
        Vincula automáticamente la ficha de cliente con el claim ``sub``.

        :param claims: Diccionario de claims decodificadas del token JWT / ID token.
        :type claims: dict
        :return: Instancia del nuevo usuario creado y persistido.
        :rtype: django.contrib.auth.models.User
        """
        user = super().create_user(claims)
        self._update_user_from_claims(user, claims)
        self._sync_cliente_keycloak(user, claims)
        logger.info("Usuario creado vía OIDC: %s", user.username)
        return user

    def update_user(self, user: AbstractBaseUser, claims: Dict[str, Any]) -> AbstractBaseUser:
        """
        Actualiza un usuario existente con claims frescas en cada inicio de sesión.

        Garantiza que los datos locales de Django (nombre, email, roles y permisos)
        y la vinculación con la ficha de cliente estén siempre sincronizados con Keycloak.

        :param user: Instancia de usuario de Django a actualizar.
        :type user: django.contrib.auth.models.User
        :param claims: Diccionario de claims provistas por Keycloak.
        :type claims: dict
        :return: Instancia del usuario actualizado.
        :rtype: django.contrib.auth.models.User
        """
        self._update_user_from_claims(user, claims)
        self._sync_cliente_keycloak(user, claims)
        logger.info("Usuario actualizado vía OIDC: %s", user.username)
        return user

    def _sync_cliente_keycloak(self, user: AbstractBaseUser, claims: Dict[str, Any]) -> None:
        """
        Sincroniza y vincula la ficha de Cliente con la identidad Keycloak (claim ``sub``).

        Emite la señal :data:`~customers.signals.keycloak_user_authenticated` y ejecuta
        el servicio de vinculación automática.

        :param user: Usuario autenticado.
        :type user: django.contrib.auth.models.User
        :param claims: Diccionario de claims del token OIDC.
        :type claims: dict
        """
        sub = claims.get("sub")
        try:
            from customers.signals import keycloak_user_authenticated
            from customers.services import vincular_cliente_keycloak

            vincular_cliente_keycloak(
                user=user,
                keycloak_id=sub,
                email=claims.get("email"),
                claims=claims,
            )
            keycloak_user_authenticated.send(
                sender=self.__class__,
                user=user,
                claims=claims,
                keycloak_id=sub,
            )
        except Exception as exc:
            logger.exception("Error al sincronizar ficha de cliente para %s: %s", user.username, exc)

    def filter_users_by_claims(self, claims: Dict[str, Any]) -> QuerySet:
        """
        Busca usuarios existentes por dirección de correo electrónico para evitar duplicados.

        :param claims: Diccionario de claims del token OIDC.
        :type claims: dict
        :return: QuerySet con los usuarios coincidentes por email.
        :rtype: django.db.models.QuerySet
        """
        email = claims.get("email")
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email=email)

    def _extract_mfa_enabled(self, claims: Dict[str, Any]) -> bool:
        """
        Extrae y evalúa los claims de MFA (amr, otp, mfa_enabled) provistos por Keycloak.

        :param claims: Diccionario de claims OIDC.
        :type claims: dict
        :return: Verdadero si se detecta autenticación de doble factor activa.
        :rtype: bool
        """
        amr = claims.get("amr", [])
        if isinstance(amr, str):
            amr = [amr]
        if isinstance(amr, (list, tuple, set)):
            if any(isinstance(m, str) and m.lower() in ("otp", "totp", "mfa", "duo", "sms") for m in amr):
                return True

        otp_claim = claims.get("otp")
        if otp_claim is True or str(otp_claim).lower() in ("true", "1", "yes"):
            return True

        mfa_claim = claims.get("mfa_enabled")
        if mfa_claim is True or str(mfa_claim).lower() in ("true", "1", "yes"):
            return True

        return False

    def _update_user_from_claims(self, user: AbstractBaseUser, claims: Dict[str, Any]) -> None:
        """
        Actualiza los campos del usuario y sincroniza sus grupos y permisos a partir de las claims.

        :param user: Usuario a actualizar.
        :type user: django.contrib.auth.models.User
        :param claims: Diccionario con claims OIDC.
        :type claims: dict
        """
        user.email = claims.get("email", user.email)
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.username = claims.get("preferred_username", user.username)

        # Sincronizar estado mfa_enabled en la instancia del modelo de usuario
        user.mfa_enabled = self._extract_mfa_enabled(claims)

        # Mapear roles de Keycloak a permisos de Django
        # Soporta tanto el claim personalizado 'realm_roles' como el formato estándar 'realm_access.roles'
        realm_roles = (
            claims.get("realm_roles")
            or claims.get("realm_access", {}).get("roles", [])
        )
        self._map_roles_to_permissions(user, realm_roles)

        user.save()

    def _map_roles_to_permissions(self, user: AbstractBaseUser, realm_roles: List[str]) -> None:
        """
        Mapea roles del realm de Keycloak a grupos y permisos de Django.

        Esquema de mapeo:
            * ``admin``: ``is_staff=True``, ``is_superuser=True``, grupo 'admin'.
            * ``operator``: ``is_staff=True``, ``is_superuser=False``, grupo 'operator'.
            * ``user``: ``is_staff=False``, ``is_superuser=False``, grupo 'user'.

        :param user: Usuario al que se le aplicarán los roles y grupos.
        :type user: django.contrib.auth.models.User
        :param realm_roles: Lista de nombres de roles extraídos del token.
        :type realm_roles: list[str]
        """
        # Reset de permisos base antes de recalcular
        user.is_staff = False
        user.is_superuser = False

        # Limpiar grupos anteriores para resincronizar
        user.groups.clear()

        for role in realm_roles:
            role_lower = role.lower()

            if role_lower == "admin":
                user.is_staff = True
                user.is_superuser = True

            elif role_lower == "operator":
                user.is_staff = True

            # Crear el grupo si no existe y asignar al usuario
            if role_lower in ("admin", "operator", "user"):
                group, _ = Group.objects.get_or_create(name=role_lower)
                user.groups.add(group)

        logger.debug(
            "Roles mapeados para %s: roles=%s, is_staff=%s, is_superuser=%s",
            user.username,
            realm_roles,
            user.is_staff,
            user.is_superuser,
        )
