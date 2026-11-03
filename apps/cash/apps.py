"""
Configuración de la aplicación de gestión de cajas, turnos y efectivo (apps.cash).
"""

from django.apps import AppConfig


class CashConfig(AppConfig):
    """
    Configuración de la aplicación ``cash``.

    Gestiona el ciclo de vida de puestos físicos de atención (Cajas/Ventanillas),
    sesiones y turnos operativos de cajeros con fondo inicial y arqueo de efectivo,
    y el registro inmutable de movimientos monetarios físicos (entradas/salidas)
    conforme a los requerimientos normativos RF-22, RF-23, RF-24 y RN05 de Global Exchange.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cash'
    label = 'cash'
    verbose_name = 'Gestión de Cajas, Turnos y Efectivo'

