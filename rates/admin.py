"""
Configuración del panel de administración Django para el módulo de tasas de cambio (rates).

Registra y personaliza las vistas administrativas para:
- :class:`~rates.models.Currency`: Catálogo de monedas y divisas operativas.
- :class:`~rates.models.ExchangeRate`: Cotizaciones históricas y vigentes de compra/venta.
- :class:`~rates.models.SegmentCommission`: Parámetros de comisiones y cargos por segmento.
"""

from django.contrib import admin
from .models import Currency, ExchangeRate, SegmentCommission


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """
    Panel administrativo para la gestión del catálogo de divisas.
    """
    list_display = ('code', 'name', 'symbol', 'decimals', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'symbol')
    ordering = ('code',)
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    """
    Panel administrativo para la gestión y consulta de cotizaciones de cambio.
    """
    list_display = (
        '__str__',
        'base_currency',
        'target_currency',
        'buy_rate',
        'sell_rate',
        'spread',
        'valid_from',
        'valid_to',
        'is_active',
        'updated_by',
    )
    list_filter = ('is_active', 'base_currency', 'target_currency', 'valid_from')
    search_fields = ('base_currency__code', 'base_currency__name', 'target_currency__code', 'target_currency__name')
    readonly_fields = ('spread', 'created_at', 'updated_at')
    ordering = ('-valid_from', '-created_at')
    date_hierarchy = 'valid_from'
    raw_id_fields = ('updated_by',)

    def save_model(self, request, obj, form, change):
        """Asigna automáticamente el usuario autenticado como responsable de la actualización."""
        if not obj.updated_by and request.user.is_authenticated:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SegmentCommission)
class SegmentCommissionAdmin(admin.ModelAdmin):
    """
    Panel administrativo para la parametrización de comisiones por segmento de cliente.
    """
    list_display = (
        'segment',
        'commission_percentage',
        'fixed_fee',
        'spread_discount_percentage',
        'is_active',
        'updated_at',
    )
    list_filter = ('is_active', 'segment')
    search_fields = ('segment',)
    ordering = ('segment',)
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('commission_percentage', 'fixed_fee', 'spread_discount_percentage', 'is_active')
