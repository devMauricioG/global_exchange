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
