"""
Configuración de la aplicación de medios de pago (payments).
"""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """
    Clase de configuración para la aplicación ``payments``.

    Gestiona los modelos y controladores para la administración de medios de pago
    (cuentas bancarias, billeteras digitales y tarjetas) de los clientes de Global Exchange.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payments'
    verbose_name = 'Gestión de Medios de Pago'
