"""
Configuración del panel de administración de Django para la aplicación de medios de pago.
"""

from django.contrib import admin
from .models import PaymentMethod, EntidadFinanciera

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """
    Configuración de administración para el modelo :class:`~payments.models.PaymentMethod`.
    """
    list_display = (
        'id',
        'cliente',
        'tipo_medio',
        'entidad_bancaria',
        'numero_cuenta',
        'titular',
        'es_predeterminado',
        'activo',
        'created_at',
    )
    list_filter = ('tipo_medio', 'es_predeterminado', 'activo', 'created_at')
    search_fields = ('entidad_bancaria__nombre', 'numero_cuenta', 'titular', 'cliente__nombre', 'cliente__documento_ruc')
    raw_id_fields = ('cliente',)
    list_editable = ('es_predeterminado', 'activo')

@admin.register(EntidadFinanciera)
class EntidadFinancieraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'activo', 'orden')
    list_filter = ('tipo', 'activo')
    ordering = ('tipo', 'orden')


from .models import ReceivingMethod, PaymentGatewayRecord, PaymentWebhookEvent, SipapTransferRecord


@admin.register(ReceivingMethod)
class ReceivingMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'entidad_bancaria', 'tipo_cuenta', 'numero_cuenta', 'titular', 'es_predeterminado', 'activo')
    list_filter = ('tipo_cuenta', 'es_predeterminado', 'activo')
    search_fields = ('titular', 'numero_cuenta', 'cliente__nombre')


@admin.register(PaymentGatewayRecord)
class PaymentGatewayRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'gateway', 'monto', 'moneda', 'estado', 'session_id', 'payment_intent_id', 'created_at')
    list_filter = ('gateway', 'estado', 'moneda', 'created_at')
    search_fields = ('session_id', 'payment_intent_id', 'referencia_externa', 'cliente__nombre')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_id', 'gateway', 'tipo_evento', 'procesado', 'created_at')
    list_filter = ('gateway', 'procesado', 'tipo_evento', 'created_at')
    search_fields = ('event_id', 'tipo_evento')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SipapTransferRecord)
class SipapTransferRecordAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'codigo_transferencia',
        'banco_origen',
        'cuenta_origen',
        'titular_origen',
        'monto',
        'moneda',
        'estado',
        'fecha_transferencia',
        'fecha_conciliacion',
    )
    list_filter = ('estado', 'moneda', 'banco_origen', 'fecha_transferencia')
    search_fields = ('codigo_transferencia', 'titular_origen', 'cuenta_origen', 'documento_origen')
    readonly_fields = ('created_at', 'updated_at', 'fecha_conciliacion')
    raw_id_fields = ('transaction', 'gateway_record')

