"""
Configuración de la aplicación de transacciones cambiarias (transactions).
"""

from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    """
    Clase de configuración para la aplicación ``transactions``.

    Gestiona los modelos y controladores para la administración, ejecución y
    seguimiento del ciclo de vida de operaciones cambiarias (compra/venta de divisas)
    en Global Exchange.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transactions'
    verbose_name = 'Gestión de Transacciones Cambiarias'
