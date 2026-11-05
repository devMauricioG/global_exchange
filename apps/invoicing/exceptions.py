"""
Excepciones específicas para el módulo de facturación electrónica (SCRUM-117).
"""

from typing import Any, Dict, Optional


class InvoicingError(Exception):
    """Excepción base para todos los errores del subsistema de facturación."""
    pass


class InvoiceProviderError(InvoicingError):
    """
    Excepción genérica para fallos originados en un proveedor de facturación.

    :ivar message: Mensaje explicativo del fallo.
    :ivar status_code: Código de estado HTTP o código devuelto por el PAC.
    :ivar error_details: Diccionario con datos adicionales de depuración.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_details = error_details or {}

    def __str__(self) -> str:
        return f"{self.message} (code: {self.status_code})"


class QuotaExhaustedError(InvoiceProviderError):
    """
    Excepción disparada cuando la cuota de peticiones contratada o asignada en el PAC se agota.
    """
    pass


class QuotaShieldExhaustedError(QuotaExhaustedError):
    """
    Excepción disparada cuando la cuota operativa comercial se agota y las 10 llamadas
    restantes se encuentran blindadas exclusivamente para la presentación en vivo y QA (SCRUM-120).
    """
    pass


class TestQuotaExhaustedError(QuotaExhaustedError):
    """
    Excepción disparada cuando se consumen íntegramente las 10 unidades de la reserva blindada de pruebas/presentación.
    """
    pass


PresentationQuotaExhaustedError = TestQuotaExhaustedError


class LiveModeDisabledError(InvoiceProviderError):
    """
    Excepción disparada al intentar ejecutar peticiones contra la API real en vivo cuando
    FACTURA_SEGURA_LIVE_ENABLED=False.
    """
    pass


class InvoiceValidationError(InvoiceProviderError):
    """
    Excepción disparada cuando los datos del documento electrónico (DE) no superan
    las validaciones sintácticas o semánticas del estándar SIFEN.
    """
    pass


class InvoiceNotFoundError(InvoiceProviderError):
    """
    Excepción disparada cuando un CDC o identificador de factura no existe en el sistema.
    """
    pass

