"""
Configuración del panel de administración Django para el módulo de transacciones cambiarias (transactions).
"""

from django.contrib import admin
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """
    Panel administrativo para la consulta, filtrado y auditoría de transacciones cambiarias.
    """
    list_display = (
        'codigo_referencia',
        'cliente',
        'tipo_operacion',
        'base_currency',
        'target_currency',
        'monto_origen',
        'monto_destino',
        'tasa_neta',
        'estado',
        'token_congelamiento',
        'created_at',
    )
    list_filter = (
        'estado',
        'tipo_operacion',
        'base_currency',
        'target_currency',
        'created_at',
    )
    search_fields = (
        'codigo_referencia',
        'cliente__nombre',
        'cliente__documento_ruc',
        'token_congelamiento',
    )
    readonly_fields = (
        'codigo_referencia',
        'created_at',
        'updated_at',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    raw_id_fields = ('cliente', 'medio_pago_origen', 'medio_acreditacion_destino', 'exchange_rate', 'usuario')
    fieldsets = (
        ('Identificación y Cliente', {
            'fields': ('codigo_referencia', 'cliente', 'usuario', 'estado', 'token_congelamiento')
        }),
        ('Detalle de la Operación Cambiaria', {
            'fields': (
                'tipo_operacion',
                'base_currency',
                'target_currency',
                'exchange_rate',
                'tasa_base',
                'comision_segmento',
                'tasa_neta',
                'monto_origen',
                'monto_destino',
            )
        }),
        ('Instrumentos Financieros', {
            'fields': ('medio_pago_origen', 'medio_acreditacion_destino')
        }),
        ('Trazabilidad y Observaciones', {
            'fields': ('observaciones', 'created_at', 'updated_at')
        }),
    )
