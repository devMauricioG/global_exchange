"""
Módulo de enrutamiento y definición de URLs para la aplicación de autenticación.

Define las rutas asociadas al cierre de sesión unificado SSO con Keycloak y la
gestión de sesiones locales de usuario.

Rutas:
    * ``/auth/logout/`` (nombre: ``logout``): Cierre de sesión local y redirección hacia el IdP Keycloak.
"""

from django.urls import path
from . import views

app_name = "authentication"

urlpatterns = [
    path("logout/", views.KeycloakLogoutView.as_view(), name="logout"),
]

