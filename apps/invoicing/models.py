"""
Modelos de datos para Facturación Electrónica SIFEN / e-Kuatia (apps.invoicing - SCRUM-118).

Provee la persistencia formal del Documento Tributario Electrónico (DTE):
- Vinculación OneToOne con la transacción cambiaria liquidada.
- Código de Control (CDC) de 44 dígitos numéricos con índice único.
- Número legal de comprobante (Establecimiento-PuntoExpedición-Secuencia).
- RUC del emisor y receptor (con o sin DV).
- Condición de venta (Contado / Crédito).
- Estados de autorización en SIFEN y descripción oficial.
- Persistencia de respuesta cruda en JSON (respuesta_sifen_raw).
- Almacenamiento de archivos físicos XML firmado y KuDE PDF.
- Bandera de auditoría es_simulada (True para emisiones con MockInvoiceProvider).
"""

from decimal import Decimal
from typing import Optional

from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone


class FacturaElectronica(models.Model):
    """
    Representación persistente del Documento Tributario Electrónico (DTE) y KuDE (SCRUM-118).

    Almacena los metadatos fiscales, estados tributarios ante el SIFEN (DNIT / SET)
    y los archivos XML firmado y KuDE PDF asociados a una transacción cambiaria.
    """

    class CondicionVenta(models.TextChoices):
        """Condición de la operación comercial según estándar SIFEN."""
        CONTADO = 'CONTADO', 'Contado (1)'
        CREDITO = 'CREDITO', 'Crédito (2)'

    class EstadoSifen(models.TextChoices):
        """Estados oficiales de autorización y ciclo de vida en SIFEN / e-Kuatia."""
        EMITIDO = 'EMITIDO', 'Emitido'
        APROBADO = 'APROBADO', 'Aprobado / Autorizado'
        APROBADO_OBS = 'APROBADO_OBS', 'Aprobado con Observación'
        RECHAZADO = 'RECHAZADO', 'Rechazado'
        CANCELADO = 'CANCELADO', 'Cancelado / Anulado'
        INUTILIZADO = 'INUTILIZADO', 'Inutilizado'
        VERIFICAR_DATOS = 'VERIFICAR_DATOS', 'Verificar Datos'
        SOL_APROBACION = 'SOL_APROBACION', 'En Espera de Aprobación'
        ENVIADO_A_SIFEN = 'ENVIADO_A_SIFEN', 'Enviado a SIFEN'
        ERROR_SIFEN = 'ERROR_SIFEN', 'Error SIFEN'

    # Vinculación transaccional
    transaction = models.OneToOneField(
        'transactions.Transaction',
        on_delete=models.CASCADE,
        related_name='factura_sifen',
        verbose_name='Transacción Cambiaria',
        help_text='Transacción cambiaria liquidada asociada a este documento tributario.',
    )

    # Identificación tributaria y clave de acceso
    cdc = models.CharField(
        max_length=44,
        unique=True,
        db_index=True,
        verbose_name='Código de Control (CDC)',
        help_text='Clave de Acceso única de 44 dígitos numéricos según estándar SIFEN.',
    )
    numero_factura = models.CharField(
        max_length=20,
        db_index=True,
        verbose_name='Número de Factura',
        help_text='Formato legal oficial: 001-001-0000001 (Establecimiento-PuntoExpedición-Secuencia).',
    )
    timbrado = models.CharField(
        max_length=8,
        default='12548963',
        verbose_name='Número de Timbrado',
        help_text='Número de timbrado fiscal otorgado por la DNIT.',
    )

    # Partes intervinientes
    ruc_emisor = models.CharField(
        max_length=20,
        default='80012345-7',
        verbose_name='RUC Emisor',
        help_text='RUC con dígito verificador de la casa de cambio emisora.',
    )
    razon_social_emisor = models.CharField(
        max_length=255,
        default='Global Exchange S.A.',
        verbose_name='Razón Social Emisor',
    )
    ruc_receptor = models.CharField(
        max_length=20,
        verbose_name='RUC / Documento Receptor',
        help_text='RUC o documento de identidad del cliente beneficiario.',
    )
    razon_social_receptor = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Nombre / Razón Social Receptor',
    )

    # Condiciones comerciales y monetarias
    condicion_venta = models.CharField(
        max_length=20,
        choices=CondicionVenta.choices,
        default=CondicionVenta.CONTADO,
        verbose_name='Condición de Venta',
    )
    monto_total = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0'),
        verbose_name='Monto Total de la Operación',
    )
    moneda = models.CharField(
        max_length=5,
        default='PYG',
        verbose_name='Moneda de la Factura',
    )

    # Estados y autorizaciones SIFEN
    estado_sifen = models.CharField(
        max_length=30,
        choices=EstadoSifen.choices,
        default=EstadoSifen.APROBADO,
        db_index=True,
        verbose_name='Estado SIFEN',
        help_text='Estado oficial de respuesta retornado por SIFEN o PAC.',
    )
    descripcion_sifen = models.CharField(
        max_length=255,
        blank=True,
        default='0260 - Aprobado',
        verbose_name='Descripción de Estado SIFEN',
    )
    protocolo_autorizacion = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Protocolo de Autorización',
        help_text='Identificador único del protocolo de autorización asignado por SIFEN/PAC.',
    )
    fecha_emision = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='Fecha y Hora de Emisión',
    )

    # Datos técnicos, respuestas y archivos
    respuesta_sifen_raw = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Respuesta Cruda SIFEN / PAC',
        help_text='Payload JSON íntegro devuelto por el servicio externo para auditoría forense.',
    )
    xml_firmado = models.TextField(
        blank=True,
        verbose_name='XML Firmado (e-Kuatia)',
        help_text='Contenido canónico del documento tributario electrónico firmado con XML-DSig.',
    )
    archivo_xml = models.FileField(
        upload_to='invoicing/xml/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Archivo XML Firmado',
        help_text='Archivo físico XML firmado persistido en disco o storage.',
    )
    archivo_pdf = models.FileField(
        upload_to='invoicing/kude/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Archivo KuDE PDF',
        help_text='Documento PDF binario oficial de la representación gráfica KuDE.',
    )
    qr_data = models.TextField(
        blank=True,
        verbose_name='URL / Parámetros Código QR',
        help_text='Enlace de consulta pública oficial ante la DNIT vía código QR.',
    )

    # Banderas de auditoría y marcas temporales
    es_simulada = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='¿Es Factura Simulada?',
        help_text='Indica si el documento fue generado en entorno de pruebas/mock (0 cuota real).',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Modificación',
    )

    class Meta:
        verbose_name = 'Factura Electrónica (SIFEN)'
        verbose_name_plural = 'Facturas Electrónicas (SIFEN)'
        ordering = ['-fecha_emision']
        indexes = [
            models.Index(fields=['cdc']),
            models.Index(fields=['numero_factura']),
            models.Index(fields=['estado_sifen', '-fecha_emision']),
            models.Index(fields=['es_simulada', '-fecha_emision']),
        ]

    def __str__(self) -> str:
        sim = ' [SIMULADA]' if self.es_simulada else ' [REAL]'
        return f"Factura {self.numero_factura} ({self.cdc[:8]}...) - {self.get_estado_sifen_display()}{sim}"

    @property
    def cdc_formatted(self) -> str:
        """
        Formatea la clave de acceso de 44 dígitos en 11 grupos de 4 dígitos separados por guiones.
        Ejemplo: 0180-0022-4750-0100-1000-0064-2202-4030-4171-3407-3775
        """
        if not self.cdc or len(self.cdc) != 44:
            return self.cdc or ''
        return '-'.join(self.cdc[i:i + 4] for i in range(0, 44, 4))

    @property
    def is_aprobado(self) -> bool:
        """Determina si el DTE se encuentra debidamente aprobado por SIFEN."""
        return self.estado_sifen in (
            self.EstadoSifen.APROBADO,
            self.EstadoSifen.APROBADO_OBS,
            'Aprobado',
        )

    @property
    def is_cancelado(self) -> bool:
        """Determina si el documento fue cancelado ante SIFEN."""
        return self.estado_sifen in (self.EstadoSifen.CANCELADO, 'Cancelado')

    @property
    def is_inutilizado(self) -> bool:
        """Determina si la numeración fiscal fue inutilizada."""
        return self.estado_sifen in (self.EstadoSifen.INUTILIZADO, 'Inutilizado')

    def save_xml_content(self, xml_text: str, filename: Optional[str] = None) -> None:
        """
        Persiste tanto el texto plano como el archivo físico en ``archivo_xml``.
        """
        self.xml_firmado = xml_text
        if xml_text:
            fname = filename or f"sifen_{self.cdc or self.numero_factura}.xml"
            self.archivo_xml.save(fname, ContentFile(xml_text.encode('utf-8')), save=False)

    def save_pdf_content(self, pdf_bytes: bytes, filename: Optional[str] = None) -> None:
        """
        Persiste los bytes binarios del KuDE en ``archivo_pdf``.
        """
        if pdf_bytes:
            fname = filename or f"kude_{self.cdc or self.numero_factura}.pdf"
            self.archivo_pdf.save(fname, ContentFile(pdf_bytes), save=False)

