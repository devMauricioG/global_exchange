"""
Módulo de configuración de la aplicación de tasas y monedas (rates).
"""

from django.apps import AppConfig


class RatesConfig(AppConfig):
    """
    Configuración de la aplicación de gestión de monedas, tasas de cambio y comisiones.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rates'
    verbose_name = 'Monedas, Tasas de Cambio y Comisiones'
