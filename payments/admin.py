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
