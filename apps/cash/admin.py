from django import forms
"""
Configuración del panel de administración Django para el módulo de Cajas, Turnos y Efectivo (apps.cash.admin).
"""

from typing import Any
from django.contrib import admin
from django.utils.html import format_html

from .models import CashMovement, CashRegister, CashShift


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    """Administración de puestos físicos de atención (Cajas registradoras)."""

    list_display = (
        'register_code',
        'name',
        'branch_name',
        'status_badge',
        'current_cashier',
        'is_active',
        'updated_at',
    )
    list_filter = ('status', 'branch_name', 'is_active')
    search_fields = ('register_code', 'name', 'branch_name')
    readonly_fields = ('opened_at', 'closed_at', 'created_at', 'updated_at')

    @admin.display(description='Estado Operativo')
    def status_badge(self, obj: CashRegister) -> str:
        colors = {
            'OPEN': '#10B981',        # Verde
            'CLOSED': '#6B7280',      # Gris
            'MAINTENANCE': '#F59E0B', # Ámbar
            'INACTIVE': '#EF4444',    # Rojo
        }
        color = colors.get(obj.status, '#374151')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(CashShift)
class CashShiftAdmin(admin.ModelAdmin):
    """Administración y auditoría de turnos de caja."""

    list_display = (
        'shift_number',
        'cash_register',
        'cashier',
        'status_badge',
        'opened_at',
        'closed_at',
    )
    list_filter = ('status', 'cash_register__branch_name', 'opened_at')
    search_fields = ('shift_number', 'cashier__username', 'cash_register__register_code', 'keycloak_user_id')
    readonly_fields = (
        'shift_number',
        'opened_at',
        'closed_at',
        'expected_balances_json',
        'difference_balances_json',
        'keycloak_user_id',
    )
    inlines = ['ShiftDenominationCountInline']  # se reemplaza abajo tras definir el inline

    @admin.display(description='Estado')
    def status_badge(self, obj: CashShift) -> str:
        colors = {
            'OPEN': '#3B82F6',        # Azul
            'CLOSED': '#6B7280',      # Gris
            'RECONCILED': '#10B981',  # Verde
            'DISCREPANCY': '#EF4444', # Rojo
        }
        color = colors.get(obj.status, '#374151')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    """Auditoría y registro inmutable de movimientos de efectivo en caja."""

    list_display = (
        'id',
        'shift',
        'movement_type',
        'flow_badge',
        'currency',
        'amount',
        'resulting_balance',
        'cashier',
        'created_at',
    )
    list_filter = ('flow', 'movement_type', 'currency', 'created_at')
    search_fields = ('shift__shift_number', 'receipt_number', 'concept', 'cashier__username', 'keycloak_user_id')
    readonly_fields = [f.name for f in CashMovement._meta.fields]

    def has_add_permission(self, request: Any) -> bool:
        # Los movimientos solo deben generarse a través de la capa de servicios
        return False

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        # Inmutabilidad estricta (RF-24)
        return False

    @admin.display(description='Flujo')
    def flow_badge(self, obj: CashMovement) -> str:
        if obj.flow == 'IN':
            return format_html('<span style="color: #10B981; font-weight: bold;">▲ IN</span>')
        return format_html('<span style="color: #EF4444; font-weight: bold;">▼ OUT</span>')


# ==============================================================================
# SCRUM-116 — Inventario de Billetes por Denominación
# ==============================================================================
from .inventory_models import (
    Vault,
    CurrencyDenomination,
    BanknoteInventory,
    InitialFloatConfig,
    BanknoteMovement,
    ShiftDenominationCount,
)


class ShiftDenominationCountInline(admin.TabularInline):
    """Inline de arqueo físico por denominación, embebido en el detalle del turno."""
    model = ShiftDenominationCount
    extra = 0
    can_delete = False
    readonly_fields = (
        'currency', 'denomination', 'opening_quantity', 'operations_in',
        'operations_out', 'system_expected_quantity', 'counted_quantity',
        'difference_quantity', 'difference_amount', 'admin_adjusted_quantity', 'admin_notes',
    )
    ordering = ['currency__code', '-denomination__value']

    def has_add_permission(self, request, obj=None):
        return False


# Parchamos el inline en CashShiftAdmin ahora que está definido
CashShiftAdmin.inlines = [ShiftDenominationCountInline]


@admin.register(Vault)
class VaultAdmin(admin.ModelAdmin):
    """Bóvedas centrales de efectivo por sucursal."""
    list_display = ('code', 'name', 'branch_name', 'is_active', 'created_at')
    list_filter = ('is_active', 'branch_name')
    search_fields = ('code', 'name', 'branch_name')
    readonly_fields = ('created_at', 'updated_at')



class BanknoteInventoryAdminForm(forms.ModelForm):
    class Meta:
        model = BanknoteInventory
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        denom = cleaned_data.get('denomination')
        cur = cleaned_data.get('currency')
        if denom:
            if not cur:
                cleaned_data['currency'] = denom.currency
            elif denom.currency_id != cur.id:
                raise forms.ValidationError({
                    'denomination': f"La denominación '{denom}' pertenece a {denom.currency.code}, no a {cur.code}."
                })
        return cleaned_data


class InitialFloatConfigAdminForm(forms.ModelForm):
    class Meta:
        model = InitialFloatConfig
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        denom = cleaned_data.get('denomination')
        cur = cleaned_data.get('currency')
        if denom:
            if not cur:
                cleaned_data['currency'] = denom.currency
            elif denom.currency_id != cur.id:
                raise forms.ValidationError({
                    'denomination': f"La denominación '{denom}' pertenece a {denom.currency.code}, no a {cur.code}."
                })
        return cleaned_data

@admin.register(CurrencyDenomination)
class CurrencyDenominationAdmin(admin.ModelAdmin):
    """Denominaciones oficiales de billetes y monedas por divisa."""
    list_display = ('currency', 'value', 'is_coin', 'is_active', 'order')
    list_filter = ('currency', 'is_active', 'is_coin')
    search_fields = ('currency__code', 'currency__name', 'value')
    ordering = ['currency__code', '-value']


@admin.register(BanknoteInventory)
class BanknoteInventoryAdmin(admin.ModelAdmin):
    """Stock físico actual de billetes por denominación y ubicación."""
    form = BanknoteInventoryAdminForm
    autocomplete_fields = ('denomination',)
    list_display = ('denomination', 'currency', 'location_type', 'vault', 'cash_register', 'quantity', 'total_amount_display', 'updated_at')
    list_filter = ('location_type', 'currency')
    search_fields = ('denomination__value', 'currency__code', 'vault__code', 'cash_register__register_code')
    readonly_fields = ('updated_at',)

    @admin.display(description='Valor Total')
    def total_amount_display(self, obj):
        return f"{obj.total_amount:,.2f} {obj.currency.code}"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InitialFloatConfig)
class InitialFloatConfigAdmin(admin.ModelAdmin):
    """Configuración de dotación inicial de billetes por denominación para apertura de turno."""
    form = InitialFloatConfigAdminForm
    autocomplete_fields = ('denomination',)
    list_display = ('denomination', 'currency', 'default_quantity', 'allow_partial_fill', 'is_active')
    list_filter = ('currency', 'is_active', 'allow_partial_fill')
    search_fields = ('currency__code', 'denomination__value')
    ordering = ['currency__code', '-denomination__value']


@admin.register(BanknoteMovement)
class BanknoteMovementAdmin(admin.ModelAdmin):
    """Auditoría inmutable de movimientos físicos de billetes entre ubicaciones."""
    list_display = (
        'id', 'movement_type', 'denomination', 'currency', 'quantity',
        'source_location_type', 'target_location_type', 'user', 'created_at',
    )
    list_filter = ('movement_type', 'currency', 'source_location_type', 'target_location_type', 'created_at')
    search_fields = ('denomination__value', 'currency__code', 'reference', 'user__username', 'shift__shift_number')
    readonly_fields = [f.name for f in BanknoteMovement._meta.fields]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
