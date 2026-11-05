"""
Servicio de persistencia de Facturas Electrónicas SIFEN (SCRUM-118).

Encapsula la lógica de creación y actualización del modelo FacturaElectronica,
coordinando los datos provenientes de los proveedores (MockInvoiceProvider /
FacturaSeguraProvider) con la capa de persistencia de Django.

Uso típico::

    from apps.invoicing.services import InvoiceService
    from apps.invoicing.providers import get_invoice_provider

    provider = get_invoice_provider()
    response = provider.emitir_factura(transaction)
    factura = InvoiceService.create_from_response(transaction, response)
"""

import logging
from decimal import Decimal

from django.db import transaction as db_transaction

from apps.invoicing.models import FacturaElectronica
from apps.invoicing.types import InvoiceResponse, StatusResponse

logger = logging.getLogger(__name__)


class InvoiceService:
    """
    Servicio de dominio para la gestión del ciclo de vida de Facturas Electrónicas SIFEN.

    Todos los métodos son ``@classmethod`` para facilitar su uso sin instanciación
    y para mantener la cohesión con el modelo ``FacturaElectronica``.
    """

    @classmethod
    def create_from_response(
        cls,
        transaction,
        invoice_response: InvoiceResponse,
    ) -> FacturaElectronica:
        """
        Crea y persiste un registro ``FacturaElectronica`` a partir de la respuesta
        de un proveedor SIFEN (MockInvoiceProvider o FacturaSeguraProvider).

        Guarda además los archivos físicos XML firmado y KuDE PDF si están presentes
        en la respuesta.

        Args:
            transaction: Instancia de ``transactions.Transaction`` ya liquidada.
            invoice_response: Objeto ``InvoiceResponse`` retornado por el proveedor.

        Returns:
            Instancia ``FacturaElectronica`` creada y guardada en BD.

        Raises:
            ValueError: Si ya existe una FacturaElectronica para esta transacción.
        """
        # Derivar número de factura desde la respuesta
        numero = invoice_response.numero_factura or ''

        # Intentar extraer datos del cliente desde la transacción
        ruc_receptor = ''
        razon_social_receptor = ''
        monto_total = Decimal('0')
        moneda = 'PYG'

        try:
            cliente = transaction.cliente
            ruc_receptor = getattr(cliente, 'documento_ruc', '') or ''
            razon_social_receptor = getattr(cliente, 'nombre', '') or ''
        except AttributeError:
            logger.warning(
                'InvoiceService: no se pudo leer cliente de la transacción %s',
                getattr(transaction, 'id', '?'),
            )

        try:
            monto_total = Decimal(str(getattr(transaction, 'monto_destino', 0) or 0))
            moneda = getattr(transaction.target_currency, 'code', 'PYG') or 'PYG'
        except (AttributeError, TypeError, Exception):
            pass

        with db_transaction.atomic():
            factura = FacturaElectronica(
                transaction=transaction,
                cdc=invoice_response.cdc,
                numero_factura=numero,
                ruc_receptor=ruc_receptor,
                razon_social_receptor=razon_social_receptor,
                monto_total=monto_total,
                moneda=moneda,
                estado_sifen=cls._map_estado(invoice_response.estado_sifen),
                descripcion_sifen=invoice_response.desc_sifen or '',
                protocolo_autorizacion=invoice_response.protocolo or '',
                respuesta_sifen_raw=invoice_response.to_dict(),
                es_simulada=invoice_response.es_simulada,
            )

            # Persistir XML firmado y archivo físico
            if invoice_response.xml_firmado:
                factura.save_xml_content(
                    invoice_response.xml_firmado,
                    filename=f"sifen_{invoice_response.cdc}.xml",
                )

            # Persistir KuDE PDF
            if invoice_response.kude_pdf_bytes:
                factura.save_pdf_content(
                    invoice_response.kude_pdf_bytes,
                    filename=f"kude_{invoice_response.cdc}.pdf",
                )

            # Guardar el QR si disponible
            if hasattr(invoice_response, 'qr_data') and invoice_response.qr_data:
                factura.qr_data = invoice_response.qr_data

            factura.save()

        logger.info(
            'InvoiceService: FacturaElectronica creada — CDC=%s, numero=%s, tx=%s',
            factura.cdc,
            factura.numero_factura,
            getattr(transaction, 'id', '?'),
        )
        return factura

    @classmethod
    def update_estado(
        cls,
        cdc: str,
        status_response: StatusResponse,
    ) -> FacturaElectronica:
        """
        Actualiza el estado SIFEN de una ``FacturaElectronica`` existente
        a partir de la respuesta de consulta del proveedor.

        Args:
            cdc: Código de Control de 44 dígitos de la factura a actualizar.
            status_response: Objeto ``StatusResponse`` del proveedor.

        Returns:
            Instancia ``FacturaElectronica`` actualizada.

        Raises:
            FacturaElectronica.DoesNotExist: Si no existe el CDC.
        """
        with db_transaction.atomic():
            factura = FacturaElectronica.objects.select_for_update().get(cdc=cdc)

            nuevo_estado = cls._map_estado(status_response.estado_sifen)
            factura.estado_sifen = nuevo_estado
            factura.descripcion_sifen = status_response.desc_sifen or ''
            factura.respuesta_sifen_raw = status_response.to_dict()

            factura.save(update_fields=[
                'estado_sifen',
                'descripcion_sifen',
                'respuesta_sifen_raw',
                'updated_at',
            ])

        logger.info(
            'InvoiceService: estado actualizado — CDC=%s, nuevo_estado=%s',
            cdc,
            factura.estado_sifen,
        )
        return factura

    @classmethod
    def get_or_create_for_transaction(
        cls,
        transaction,
        invoice_response: InvoiceResponse,
    ) -> tuple:
        """
        Obtiene o crea de forma idempotente una ``FacturaElectronica`` para la
        transacción dada. Si ya existe (por ``transaction__id``), retorna la existente.

        Args:
            transaction: Instancia ``transactions.Transaction``.
            invoice_response: Respuesta del proveedor para usar en caso de creación.

        Returns:
            Tupla ``(FacturaElectronica, created: bool)``.
        """
        try:
            factura = FacturaElectronica.objects.get(transaction=transaction)
            return factura, False
        except FacturaElectronica.DoesNotExist:
            factura = cls.create_from_response(transaction, invoice_response)
            return factura, True

    # -------------------------------------------------------------------------
    # Helpers privados
    # -------------------------------------------------------------------------

    @staticmethod
    def _map_estado(estado_raw: str) -> str:
        """
        Mapea el string de estado recibido del proveedor al valor interno
        del ``EstadoSifen`` TextChoices del modelo.

        Los providers pueden retornar valores como ``'Aprobado'``, ``'APROBADO'``,
        ``EstadoSifenEnum.APROBADO.value``, etc. Este método normaliza todos esos casos.
        """
        if not estado_raw:
            return FacturaElectronica.EstadoSifen.EMITIDO

        mapping = {
            # Valores en español (StatusResponse de MockInvoiceProvider)
            'aprobado': FacturaElectronica.EstadoSifen.APROBADO,
            'aprobado con observación': FacturaElectronica.EstadoSifen.APROBADO_OBS,
            'aprobado con observacion': FacturaElectronica.EstadoSifen.APROBADO_OBS,
            'rechazado': FacturaElectronica.EstadoSifen.RECHAZADO,
            'cancelado': FacturaElectronica.EstadoSifen.CANCELADO,
            'inutilizado': FacturaElectronica.EstadoSifen.INUTILIZADO,
            'verificar datos': FacturaElectronica.EstadoSifen.VERIFICAR_DATOS,
            'emitido': FacturaElectronica.EstadoSifen.EMITIDO,
            'enviado a sifen': FacturaElectronica.EstadoSifen.ENVIADO_A_SIFEN,
            'error sifen': FacturaElectronica.EstadoSifen.ERROR_SIFEN,
        }

        # Intentar match directo con los valores internos del TextChoices
        valid_choices = {c[0] for c in FacturaElectronica.EstadoSifen.choices}
        if estado_raw in valid_choices:
            return estado_raw

        # Normalizar a minúsculas para el mapeo
        return mapping.get(estado_raw.lower(), FacturaElectronica.EstadoSifen.EMITIDO)

