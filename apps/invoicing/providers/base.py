"""
Contrato e interfaz base para proveedores de facturación electrónica (SCRUM-117).

Define el patrón Strategy / Adapter para desacoplar el motor transaccional
de los clientes reales de PAC (Factura Segura) y de simuladores de testing (MockInvoiceProvider).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

from ..types import InvoiceResponse, StatusResponse


class InvoiceProvider(ABC):
    """
    Interfaz abstracta base (Strategy / Adapter) para proveedores de Facturación Electrónica SIFEN.

    Satisface el protocolo de interoperabilidad para Sistemas Externos (ESI v01)
    cubriendo las operaciones oficiales:
    - ``calcular_de``: Cálculo matemático de montos e IVA en base a un JSON resumido.
    - ``generar_de``: Generación, firma digital y solicitud de aprobación de DTE.
    - ``get_estado_sifen``: Consulta sincrónica de estado de aprobación o eventos en SIFEN.
    - ``sol_cancelacion``: Solicitud formal de evento de cancelación de DTE aprobado.
    - ``sol_inutilizacion``: Solicitud de inutilización de numeración no utilizada.
    - ``dwn_kude``: Descarga binaria de representación gráfica KuDE en PDF.
    - ``dwn_xml``: Descarga de archivo XML firmado digitalmente.
    - ``emitir_factura``: Fachada transaccional unificada para liquidaciones de cambio.
    """

    @abstractmethod
    def calcular_de(self, de_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recibe un JSON de DE (resumido o completo) y retorna el JSON con todos los
        campos numéricos, bases gravadas e IVA calculados según las fórmulas oficiales de SIFEN.

        :param de_data: Diccionario con los datos del documento electrónico.
        :return: Diccionario completo con campos calculados.
        """
        pass

    @abstractmethod
    def generar_de(self, de_data: Dict[str, Any], is_test: bool = False) -> InvoiceResponse:
        """
        Procesa el JSON del documento electrónico, genera el XML, aplica la firma digital,
        construye el KuDE y solicita la aprobación al SIFEN.

        :param de_data: Diccionario con la estructura completa del DE.
        :param is_test: Indica si la llamada se ejecuta en modo de prueba / test.
        :return: Objeto :class:`InvoiceResponse` con el CDC de 44 dígitos y metadatos.
        """
        pass

    @abstractmethod
    def get_estado_sifen(self, cdc: str, ruc_emisor: Optional[str] = None) -> StatusResponse:
        """
        Consulta en SIFEN el estado tributario del documento (aprobación, cancelación, inutilización).

        :param cdc: Código de Control de 44 dígitos numéricos.
        :param ruc_emisor: RUC del emisor sin dígito verificador.
        :return: Objeto :class:`StatusResponse` con los atributos normalizados.
        """
        pass

    @abstractmethod
    def sol_cancelacion(
        self,
        cdc: str,
        motivo: str = '',
        ruc_emisor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Solicita a SIFEN el evento de cancelación de un documento electrónico previamente aprobado.

        :param cdc: Código de Control de 44 dígitos del DTE a cancelar.
        :param motivo: Descripción justificada del motivo de cancelación.
        :param ruc_emisor: RUC del emisor sin DV.
        :return: Diccionario con el resultado de la solicitud del evento.
        """
        pass

    @abstractmethod
    def sol_inutilizacion(
        self,
        ruc_emisor: str,
        timbrado: str,
        est: str,
        pun_exp: str,
        num_doc: str,
        tipo_de: str = '1',
    ) -> Dict[str, Any]:
        """
        Solicita a SIFEN el evento de inutilización de un número de documento no emitido.

        :param ruc_emisor: RUC del emisor sin DV.
        :param timbrado: Número de timbrado fiscal.
        :param est: Código de establecimiento (3 dígitos).
        :param pun_exp: Punto de expedición (3 dígitos).
        :param num_doc: Número de documento (7 dígitos).
        :param tipo_de: Tipo de Documento Electrónico ('1' Factura, '5' Nota de Crédito).
        :return: Diccionario con la confirmación del registro del evento.
        """
        pass

    @abstractmethod
    def dwn_kude(self, cdc: str, ruc_emisor: Optional[str] = None) -> bytes:
        """
        Descarga el archivo binario PDF correspondiente a la representación gráfica KuDE.

        :param cdc: Código de Control de 44 dígitos.
        :param ruc_emisor: RUC del emisor sin DV.
        :return: Bytes binarios del archivo PDF generado.
        """
        pass

    @abstractmethod
    def dwn_xml(self, cdc: str, ruc_emisor: Optional[str] = None) -> str:
        """
        Descarga el archivo XML firmado digitalmente correspondiente al documento electrónico.

        :param cdc: Código de Control de 44 dígitos.
        :param ruc_emisor: RUC del emisor sin DV.
        :return: Cadena de texto con el XML firmado.
        """
        pass

    @abstractmethod
    def emitir_factura(self, transaction_or_data: Any, is_test: bool = False) -> InvoiceResponse:
        """
        Fachada de alto nivel para emitir una Factura Electrónica e-Kuatia a partir
        de una instancia de transacción cambiaria o un diccionario estructurado de datos.

        :param transaction_or_data: Instancia de modelo Transaction o dict de parámetros.
        :param is_test: Flag de prueba / QA.
        :return: Objeto :class:`InvoiceResponse`.
        """
        pass
