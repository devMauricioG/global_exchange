"""
Enrutamiento URL para el módulo de Inventario de Billetes por Denominación (SCRUM-116).
Incluido desde apps/cash/urls.py bajo el namespace 'cash'.
"""

from django.urls import path

from .inventory_views import (
    AdminReconciliationActionView,
    AdminReconciliationListView,
    CashierDenominationCountView,
    ShiftInventoryView,
    VaultDashboardView,
    VaultDepositView,
)

urlpatterns = [
    path('vault/', VaultDashboardView.as_view(), name='vault_dashboard'),
    path('vault/deposit/', VaultDepositView.as_view(), name='vault_deposit'),
    path('shifts/<int:pk>/inventory/', ShiftInventoryView.as_view(), name='shift_inventory'),
    path('shifts/<int:pk>/denomination-count/', CashierDenominationCountView.as_view(), name='cashier_denomination_count'),
    path('admin/reconciliation/', AdminReconciliationListView.as_view(), name='admin_reconciliation_list'),
    path('admin/reconciliation/<int:pk>/', AdminReconciliationActionView.as_view(), name='admin_reconciliation_action'),
]
