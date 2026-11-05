"""
Estructuras de datos, contratos y DTOs para Facturación Electrónica SIFEN (SCRUM-117).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class EstadoSifenEnum(str, Enum):
    """
    Estados posibles de un Documento Tributario Electrónico en el SIFEN (Manual ESI v01).
    """
    APROBADO = 'Aprobado'
    APROBADO_OBS = 'Aprobado con observación'
    RECHAZADO = 'Rechazado'
    CANCELADO = 'Cancelado'
    INUTILIZADO = 'Inutilizado'
    VERIFICAR_DATOS = 'Verificar datos'
    SOL_APROBACION = 'SOL.APROBACION'
    ENVIADO_A_SIFEN = 'ENVIADO_A_SIFEN'
    ERROR_SIFEN = 'ERROR_SIFEN'
    ERROR_ENVIO_LOTE = 'ERROR_ENVIO_LOTE'
    REINTENTAR_LOTE = 'REINTENTAR_LOTE'
    ERROR_CONSULTA_LOTE = 'ERROR_CONSULTA_LOTE'


@dataclass
class InvoiceResponse:
    """
    Respuesta normalizada de emisión de un Documento Tributario Electrónico (DTE).

    :param cdc: Código de Control de 44 dígitos numéricos.
    :param numero_factura: Número legal de la factura (ej. '001-001-0000001').
    :param estado: Estado operativo interno ('APROBADO', 'RECHAZADO', 'CANCELADO').
    :param estado_sifen: Estado tributario oficial retornado por el SIFEN.
    :param desc_sifen: Descripción literal del código de estado en SIFEN.
    :param protocolo: Número de protocolo de autorización o referencia PAC.
    :param fecha_emision: Fecha y hora formal de emisión del documento.
    :param xml_firmado: Contenido textual del XML firmado según estándar e-Kuatia.
    :param kude_pdf_bytes: Bytes binarios representativos del KuDE en PDF.
    :param qr_data: URL oficial o parámetros para consulta con código QR.
    :param raw_response: Respuesta cruda retornada por la API o motor de emisión.
    :param es_simulada: Booleano que indica si la factura fue emitida por el MockProvider.
    """
    cdc: str
    numero_factura: str
    estado: str
    estado_sifen: str
    desc_sifen: str
    protocolo: str
    fecha_emision: datetime
    xml_firmado: str
    kude_pdf_bytes: bytes = b''
    qr_data: str = ''
    raw_response: Dict[str, Any] = field(default_factory=dict)
    es_simulada: bool = False

    @property
    def is_approved(self) -> bool:
        """Determina si el documento fue aprobado formalmente por el SIFEN."""
        return self.estado_sifen in (
            EstadoSifenEnum.APROBADO.value,
            EstadoSifenEnum.APROBADO_OBS.value,
            'APROBADO',
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la respuesta a un diccionario plano."""
        return {
            'cdc': self.cdc,
            'numero_factura': self.numero_factura,
            'estado': self.estado,
            'estado_sifen': self.estado_sifen,
            'desc_sifen': self.desc_sifen,
            'protocolo': self.protocolo,
            'fecha_emision': self.fecha_emision.isoformat() if self.fecha_emision else None,
            'xml_firmado': self.xml_firmado,
            'qr_data': self.qr_data,
            'es_simulada': self.es_simulada,
            'raw_response': self.raw_response,
        }


@dataclass
class StatusResponse:
    """
    Respuesta normalizada de consulta de estado en el SIFEN (operation get_estado_sifen).

    Basado estrictamente en la especificación de la página 9-10 del manual ESI v01.
    """
    cdc: str
    estado_sifen: str
    desc_sifen: str = ''
    error_sifen: str = ''
    fch_sifen: str = ''
    estado_can: str = ''
    desc_can: str = ''
    error_can: str = ''
    fch_can: str = ''
    estado_inu: str = ''
    desc_inu: str = ''
    error_inu: str = ''
    fch_inu: str = ''
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        """Indica si el estado de aprobación es afirmativo."""
        return self.estado_sifen in (
            EstadoSifenEnum.APROBADO.value,
            EstadoSifenEnum.APROBADO_OBS.value,
            'APROBADO',
        )

    @property
    def is_cancelled(self) -> bool:
        """Indica si el evento de cancelación fue aprobado en SIFEN."""
        return self.estado_can == 'Aprobado' or self.estado_sifen == EstadoSifenEnum.CANCELADO.value

    @property
    def is_voided(self) -> bool:
        """Indica si el evento de inutilización fue aprobado en SIFEN."""
        return self.estado_inu == 'Aprobado' or self.estado_sifen == EstadoSifenEnum.INUTILIZADO.value

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el resultado de la consulta a diccionario."""
        return {
            'cdc': self.cdc,
            'estado_sifen': self.estado_sifen,
            'desc_sifen': self.desc_sifen,
            'error_sifen': self.error_sifen,
            'fch_sifen': self.fch_sifen,
            'estado_can': self.estado_can,
            'desc_can': self.desc_can,
            'error_can': self.error_can,
            'fch_can': self.fch_can,
            'estado_inu': self.estado_inu,
            'desc_inu': self.desc_inu,
            'error_inu': self.error_inu,
            'fch_inu': self.fch_inu,
            'is_approved': self.is_approved,
            'is_cancelled': self.is_cancelled,
            'is_voided': self.is_voided,
        }


@dataclass
class CalculationResult:
    """
    Resultado de la operación calcular_de según las fórmulas del manual ESI v01.
    """
    de_calculado: Dict[str, Any]
    subtotal_exenta: Decimal = Decimal('0')
    subtotal_exonerada: Decimal = Decimal('0')
    subtotal_5: Decimal = Decimal('0')
    subtotal_10: Decimal = Decimal('0')
    total_operacion: Decimal = Decimal('0')
    total_descuento: Decimal = Decimal('0')
    total_general: Decimal = Decimal('0')
    total_iva_5: Decimal = Decimal('0')
    total_iva_10: Decimal = Decimal('0')
    total_iva: Decimal = Decimal('0')
    base_gravada_5: Decimal = Decimal('0')
    base_gravada_10: Decimal = Decimal('0')
    total_base_gravada: Decimal = Decimal('0')
