"""
Configuración de la aplicación de autenticación y autorización (authentication).
"""

from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    """
    Clase de configuración para la aplicación ``authentication``.

    Define los metadatos de la aplicación de autenticación y control de acceso RBAC.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentication'
    verbose_name = 'Autenticación y Control de Acceso'
