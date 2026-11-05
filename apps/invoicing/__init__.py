"""
Módulo de Facturación Electrónica SIFEN (apps.invoicing - SCRUM-117 / SCRUM-118).
"""

from .calculators import calculate_de, compute_mod11_dv, generate_cdc
from .exceptions import (
    InvoicingError,
    InvoiceNotFoundError,
    InvoiceProviderError,
    InvoiceValidationError,
    LiveModeDisabledError,
    QuotaExhaustedError,
)
from .providers import (
    FacturaSeguraProvider,
    InvoiceProvider,
    MockInvoiceProvider,
    get_invoice_provider,
    reset_invoice_provider,
    set_invoice_provider,
)
from .types import (
    CalculationResult,
    EstadoSifenEnum,
    InvoiceResponse,
    StatusResponse,
)

__all__ = [
    # Providers
    'InvoiceProvider',
    'MockInvoiceProvider',
    'FacturaSeguraProvider',
    'get_invoice_provider',
    'set_invoice_provider',
    'reset_invoice_provider',
    # Calculators
    'calculate_de',
    'generate_cdc',
    'compute_mod11_dv',
    # Types
    'InvoiceResponse',
    'StatusResponse',
    'CalculationResult',
    'EstadoSifenEnum',
    # Exceptions
    'InvoicingError',
    'InvoiceProviderError',
    'QuotaExhaustedError',
    'LiveModeDisabledError',
    'InvoiceValidationError',
    'InvoiceNotFoundError',
    # Models (SCRUM-118)
    'FacturaElectronica',
    # Services (SCRUM-118)
    'InvoiceService',
    # Views (SCRUM-119)
    'FacturaElectronicaDetailView',
    'FacturaElectronicaPdfDownloadView',
    'FacturaElectronicaXmlDownloadView',
    'FacturaElectronicaSifenSyncAjaxView',
    'FacturaConsultaApiView',
]

# Importaciones tardías para evitar circular imports con Django ORM
def __getattr__(name):
    if name == 'FacturaElectronica':
        from .models import FacturaElectronica
        return FacturaElectronica
    if name == 'InvoiceService':
        from .services import InvoiceService
        return InvoiceService
    if name in (
        'FacturaElectronicaDetailView',
        'FacturaElectronicaPdfDownloadView',
        'FacturaElectronicaXmlDownloadView',
        'FacturaElectronicaSifenSyncAjaxView',
        'FacturaConsultaApiView',
    ):
        from . import views
        return getattr(views, name)
    raise AttributeError(f"module 'apps.invoicing' has no attribute {name!r}")

