"""
Configuración del panel de administración para Facturación Electrónica SIFEN (SCRUM-118).

Registra el modelo FacturaElectronica con vista de auditoría completa:
- Listado con columnas clave y estado SIFEN con badges de color.
- Filtros laterales por estado, tipo de emisión y condición de venta.
- Búsqueda por CDC, número de factura, RUC y razón social del receptor.
- Campos de solo lectura para integridad del registro tributario.
"""

from django.contrib import admin
from django.utils.html import format_html

from apps.invoicing.models import FacturaElectronica


@admin.register(FacturaElectronica)
class FacturaElectronicaAdmin(admin.ModelAdmin):
    """
    Panel de administración de Facturas Electrónicas SIFEN.

    Diseñado como panel de auditoría: todos los campos son de solo lectura
    para garantizar la integridad del registro tributario.
    """

    # Columnas del listado principal
    list_display = (
        'numero_factura',
        'cdc_truncado',
        'transaction',
        'estado_sifen_badge',
        'condicion_venta',
        'monto_total',
        'moneda',
        'ruc_receptor',
        'es_simulada',
        'fecha_emision',
    )

    # Filtros laterales
    list_filter = (
        'estado_sifen',
        'es_simulada',
        'condicion_venta',
        'moneda',
    )

    # Campos de búsqueda
    search_fields = (
        'cdc',
        'numero_factura',
        'ruc_receptor',
        'razon_social_receptor',
        'ruc_emisor',
        'timbrado',
    )

    # Ordenamiento predeterminado
    ordering = ('-fecha_emision',)

    # Paginación
    list_per_page = 25

    # Todos los campos son de solo lectura (registro tributario inmutable)
    readonly_fields = (
        'transaction',
        'cdc',
        'cdc_formatted_display',
        'numero_factura',
        'timbrado',
        'ruc_emisor',
        'razon_social_emisor',
        'ruc_receptor',
        'razon_social_receptor',
        'condicion_venta',
        'monto_total',
        'moneda',
        'estado_sifen',
        'descripcion_sifen',
        'protocolo_autorizacion',
        'fecha_emision',
        'respuesta_sifen_raw',
        'xml_firmado',
        'archivo_xml',
        'archivo_pdf',
        'qr_data',
        'es_simulada',
        'created_at',
        'updated_at',
    )

    # Layout con secciones temáticas
    fieldsets = (
        ('Identificación Tributaria', {
            'fields': (
                'cdc',
                'cdc_formatted_display',
                'numero_factura',
                'timbrado',
            ),
        }),
        ('Vinculación Transaccional', {
            'fields': ('transaction',),
        }),
        ('Partes Intervinientes', {
            'fields': (
                'ruc_emisor',
                'razon_social_emisor',
                'ruc_receptor',
                'razon_social_receptor',
            ),
        }),
        ('Datos Comerciales', {
            'fields': (
                'condicion_venta',
                'monto_total',
                'moneda',
            ),
        }),
        ('Estado SIFEN', {
            'fields': (
                'estado_sifen',
                'descripcion_sifen',
                'protocolo_autorizacion',
                'fecha_emision',
                'respuesta_sifen_raw',
            ),
        }),
        ('Archivos y Contenido', {
            'classes': ('collapse',),
            'fields': (
                'xml_firmado',
                'archivo_xml',
                'archivo_pdf',
                'qr_data',
            ),
        }),
        ('Auditoría', {
            'fields': (
                'es_simulada',
                'created_at',
                'updated_at',
            ),
        }),
    )

    # -------------------------------------------------------------------------
    # Columnas personalizadas
    # -------------------------------------------------------------------------

    @admin.display(description='CDC (inicio)')
    def cdc_truncado(self, obj: FacturaElectronica) -> str:
        """Muestra solo los primeros 12 caracteres del CDC para ahorrar espacio."""
        if obj.cdc:
            return f"{obj.cdc[:12]}…"
        return '-'

    @admin.display(description='CDC Formateado')
    def cdc_formatted_display(self, obj: FacturaElectronica) -> str:
        """Muestra el CDC completo formateado en grupos de 4 dígitos."""
        return obj.cdc_formatted or '-'

    @admin.display(description='Estado SIFEN')
    def estado_sifen_badge(self, obj: FacturaElectronica) -> str:
        """Renderiza el estado SIFEN con un badge de color HTML."""
        COLOR_MAP = {
            FacturaElectronica.EstadoSifen.APROBADO: '#28a745',          # Verde
            FacturaElectronica.EstadoSifen.APROBADO_OBS: '#6f42c1',      # Morado
            FacturaElectronica.EstadoSifen.RECHAZADO: '#dc3545',         # Rojo
            FacturaElectronica.EstadoSifen.CANCELADO: '#fd7e14',         # Naranja
            FacturaElectronica.EstadoSifen.INUTILIZADO: '#6c757d',       # Gris
            FacturaElectronica.EstadoSifen.EMITIDO: '#17a2b8',           # Cian
            FacturaElectronica.EstadoSifen.ENVIADO_A_SIFEN: '#007bff',   # Azul
            FacturaElectronica.EstadoSifen.SOL_APROBACION: '#ffc107',    # Amarillo
            FacturaElectronica.EstadoSifen.VERIFICAR_DATOS: '#e83e8c',   # Rosa
            FacturaElectronica.EstadoSifen.ERROR_SIFEN: '#721c24',       # Rojo oscuro
        }
        color = COLOR_MAP.get(obj.estado_sifen, '#6c757d')
        label = obj.get_estado_sifen_display()
        return format_html(
            '<span style="background-color:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:0.85em;font-weight:600;">{}</span>',
            color,
            label,
        )

