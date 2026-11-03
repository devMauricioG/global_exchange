"""
Enrutamiento URL para el módulo de Cajas, Turnos y Efectivo (apps.cash.urls).
"""

from django.urls import path
from .views import (
    CashDashboardView,
    CashMovementCreateView,
    CashRegisterListView,
    CashShiftCloseView,
    CashShiftDetailView,
    CashShiftListView,
    CashShiftOpenView,
    CashShiftReceiptView,
    CashShiftStatusApiView,
)

app_name = 'cash'

urlpatterns = [
    # Dashboard principal de ventanilla
    path('', CashDashboardView.as_view(), name='dashboard'),

    # Ciclo de vida de turnos
    path('shifts/open/', CashShiftOpenView.as_view(), name='shift_open'),
    path('shifts/<int:pk>/close/', CashShiftCloseView.as_view(), name='shift_close'),
    path('shifts/close/', CashShiftCloseView.as_view(), name='shift_close_current'),
    path('shifts/<int:pk>/', CashShiftDetailView.as_view(), name='shift_detail'),
    path('shifts/<int:pk>/receipt/', CashShiftReceiptView.as_view(), name='shift_receipt'),
    path('shifts/', CashShiftListView.as_view(), name='shift_list'),

    # Movimientos de efectivo
    path('movements/create/', CashMovementCreateView.as_view(), name='movement_create'),

    # Cajas y puestos de atención
    path('registers/', CashRegisterListView.as_view(), name='register_list'),

    # API JSON en tiempo real
    path('api/shift/<int:pk>/status/', CashShiftStatusApiView.as_view(), name='api_shift_status'),
]

