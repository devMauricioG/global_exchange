"""
Vistas para la aplicación de Transacciones Cambiarias.
"""

from django.views.generic import TemplateView


class TransactionPlaceholderView(TemplateView):
    """
    Vista de marcador de posición para futuras interfaces de usuario de transacciones.
    """
    template_name = "transactions/placeholder.html"
