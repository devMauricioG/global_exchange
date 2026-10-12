"""
Módulo de vistas y controladores para el flujo de autenticación y navegación principal.

Provee la vista de inicio del sistema :func:`home_view` adaptada con renderizado
dinámico según roles JWT/OIDC y el controlador :class:`KeycloakLogoutView` para
el cierre de sesión unificado SSO con Keycloak.
"""

import logging
from typing import Any, Dict
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


def home_view(request: HttpRequest) -> HttpResponse:
    """
    Vista principal del dashboard en la ruta raíz ``/``.

    Si el usuario se encuentra autenticado, renderiza la plantilla :file:`templates/home.html`
    aprovechando los datos inyectados por el procesador de contexto de roles (:func:`~authentication.context_processors.auth_roles`)
    para mostrar menús y accesos condicionales.

    Si el usuario no está autenticado, lo redirige al flujo de autenticación OIDC/Keycloak.

    :param request: Objeto de solicitud HTTP.
    :type request: django.http.HttpRequest
    :return: Respuesta HTTP con la plantilla renderizada o redirección al SSO.
    :rtype: django.http.HttpResponse
    """
    if request.user.is_authenticated:
        return render(request, 'home.html')
    else:
        return redirect('/oidc/authenticate/')


class UserProfileView(LoginRequiredMixin, TemplateView):
    """
    Vista del perfil de usuario y estado de seguridad 2FA/MFA.

    Muestra el resumen del usuario autenticado, su rol principal, el estado del
    doble factor extraído del backend OIDC (mfa_enabled) y la URL directa para
    la gestión de credenciales MFA en Keycloak.
    """
    template_name = "profile.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        mfa_enabled = getattr(user, "mfa_enabled", False)

        public_url = getattr(settings, "KEYCLOAK_PUBLIC_URL", "http://localhost:8080")
        realm = getattr(settings, "KEYCLOAK_REALM", "GlobalExchangeRealm")
        keycloak_account_url = f"{public_url}/realms/{realm}/account/#/security/signing-and-log-in"

        context.update({
            "user_info": user,
            "mfa_enabled": mfa_enabled,
            "keycloak_account_url": keycloak_account_url,
        })
        return context


class KeycloakLogoutView(View):
    """
    Controlador de cierre de sesión unificado (SSO Logout).

    Invalida la sesión local de Django y redirige al endpoint de revocación de sesión
    de Keycloak (:attr:`django.conf.settings.OIDC_OP_LOGOUT_ENDPOINT`) para cerrar también
    la sesión del proveedor de identidad (IdP).
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        """
        Procesa el cierre de sesión local y la redirección hacia Keycloak.

        :param request: Objeto de solicitud HTTP GET.
        :type request: django.http.HttpRequest
        :return: Redirección al endpoint de logout de Keycloak o fallback a LOGOUT_REDIRECT_URL.
        :rtype: django.http.HttpResponse
        """
        logout(request)

        keycloak_logout_url = getattr(
            settings,
            "OIDC_OP_LOGOUT_ENDPOINT",
            "",
        )

        if keycloak_logout_url:
            redirect_uri = request.build_absolute_uri(
                getattr(settings, "LOGOUT_REDIRECT_URL", "/")
            )
            params = urlencode({
                "client_id": settings.OIDC_RP_CLIENT_ID,
                "post_logout_redirect_uri": redirect_uri,
            })
            full_logout_url = f"{keycloak_logout_url}?{params}"

            logger.info("Logout SSO: redirigiendo a Keycloak")
            return redirect(full_logout_url)

        logger.warning("OIDC_OP_LOGOUT_ENDPOINT no configurado, logout solo local")
        return redirect(getattr(settings, "LOGOUT_REDIRECT_URL", "/"))
