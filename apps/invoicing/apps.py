"""
Configuración de la aplicación de Facturación Electrónica SIFEN (apps.invoicing).
"""

from django.apps import AppConfig


class InvoicingConfig(AppConfig):
    """
    Configuración de la aplicación ``invoicing``.

    Gestiona la integración y arquitectura desacoplada para la emisión,
    consulta y representación gráfica (KuDE) de Documentos Tributarios
    Electrónicos (DTE / e-Kuatia) en conjunto con el Sistema Integrado
    de Facturación Electrónica Nacional (SIFEN) y PACs asociados (SCRUM-117).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.invoicing'
    label = 'invoicing'
    verbose_name = 'Facturación Electrónica SIFEN'

