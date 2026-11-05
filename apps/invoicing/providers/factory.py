"""
Fábrica y selector dinámico de proveedores de facturación electrónica (SCRUM-117).

Aplica el patrón Factory / Strategy para instanciar el proveedor adecuado:
- MockInvoiceProvider: por defecto en entornos de desarrollo y testing (FACTURA_SEGURA_LIVE_ENABLED=False).
- FacturaSeguraProvider: en producción o cuando se active explícitamente el flag LIVE.
"""

from typing import Any, Optional

from django.conf import settings

from .base import InvoiceProvider
from .facturasegura import FacturaSeguraProvider
from .mock import MockInvoiceProvider

_OVERRIDDEN_PROVIDER: Optional[InvoiceProvider] = None


def set_invoice_provider(provider: Optional[InvoiceProvider]) -> None:
    """
    Establece un proveedor explícito para sobreescribir el selector automático (inyección en tests).
    """
    global _OVERRIDDEN_PROVIDER
    _OVERRIDDEN_PROVIDER = provider


def reset_invoice_provider() -> None:
    """
    Restablece el proveedor al comportamiento predeterminado por configuración.
    """
    global _OVERRIDDEN_PROVIDER
    _OVERRIDDEN_PROVIDER = None


def get_invoice_provider(provider_type: Optional[str] = None, **kwargs: Any) -> InvoiceProvider:
    """
    Obtiene la instancia configurada del proveedor de facturación electrónica.

    :param provider_type: 'mock' o 'facturasegura'. Si se omite, se evalúa
                          ``settings.FACTURA_SEGURA_LIVE_ENABLED``.
    :param kwargs: Parámetros opcionales para la inicialización del proveedor.
    :return: Instancia concreta que implementa :class:`InvoiceProvider`.
    """
    global _OVERRIDDEN_PROVIDER
    if _OVERRIDDEN_PROVIDER is not None and provider_type is None:
        return _OVERRIDDEN_PROVIDER

    target = (provider_type or '').strip().lower()

    if target == 'mock':
        return MockInvoiceProvider()

    if target in ('facturasegura', 'real', 'live'):
        return FacturaSeguraProvider(**kwargs)

    # Selección automática por settings
    is_live = getattr(settings, 'FACTURA_SEGURA_LIVE_ENABLED', False)
    if is_live:
        return FacturaSeguraProvider(**kwargs)

    return MockInvoiceProvider()
