"""
Módulo de enrutamiento y URLs para la aplicación de Tasas y Comisiones (rates).
"""

from django.urls import path
from . import views

app_name = 'rates'

urlpatterns = [
    # Tablero de cotizaciones históricas (SCRUM-52)
    path('dashboard/', views.ExchangeRateDashboardView.as_view(), name='dashboard'),
    path('api/history/', views.ExchangeRateHistoryApiView.as_view(), name='api_history'),

    # Rutas para Currency (Monedas - SCRUM-51)
    path('currencies/', views.CurrencyListView.as_view(), name='currency-list'),
    path('currencies/create/', views.CurrencyCreateView.as_view(), name='currency-create'),
    path('currencies/<int:pk>/update/', views.CurrencyUpdateView.as_view(), name='currency-update'),
    path('currencies/<int:pk>/toggle/', views.CurrencyToggleStatusView.as_view(), name='currency-toggle'),

    # Rutas para ExchangeRate (Tasas de Cambio - SCRUM-51)
    path('exchange-rates/', views.ExchangeRateListView.as_view(), name='rate-list'),
    path('exchange-rates/create/', views.ExchangeRateCreateView.as_view(), name='rate-create'),
    path('exchange-rates/<int:pk>/update/', views.ExchangeRateUpdateView.as_view(), name='rate-update'),
    path('exchange-rates/<int:pk>/toggle/', views.ExchangeRateToggleStatusView.as_view(), name='rate-toggle'),

    # Gestión Administrativa de Comisiones por Segmento (SCRUM-53)
    path('commissions/', views.SegmentCommissionListView.as_view(), name='commission_list'),
    path('commissions/add/', views.SegmentCommissionCreateView.as_view(), name='commission_create'),
    path('commissions/<int:pk>/', views.SegmentCommissionDetailView.as_view(), name='commission_detail'),
    path('commissions/<int:pk>/edit/', views.SegmentCommissionUpdateView.as_view(), name='commission_update'),
    path('commissions/<int:pk>/delete/', views.SegmentCommissionDeleteView.as_view(), name='commission_delete'),

    # Simulador y Motor de Cotizaciones Netas (SCRUM-53)
    path('calculator/', views.RateCalculatorView.as_view(), name='rate_calculator'),

    # Endpoints API REST (JSON)
    path('api/calculate/', views.CalculateNetRateApiView.as_view(), name='api_calculate'),
    path('api/commissions/', views.SegmentCommissionListApiView.as_view(), name='api_commissions'),
    path('api/commissions/<str:segment>/', views.SegmentCommissionDetailApiView.as_view(), name='api_commission_detail'),

    # Endpoints API REST Congelamiento de Cotizaciones (SCRUM-54)
    path('api/freeze/', views.FreezeQuoteApiView.as_view(), name='api_freeze'),
    path('api/frozen-quote/', views.GetFrozenQuoteApiView.as_view(), name='api_frozen_quote'),
    path('api/unfreeze/', views.UnfreezeQuoteApiView.as_view(), name='api_unfreeze'),

    # Gestión Administrativa de Límites Operativos por Moneda y Segmento (SCRUM-77)
    path('limits/', views.OperationLimitListView.as_view(), name='limit_list'),
    path('limits/add/', views.OperationLimitCreateView.as_view(), name='limit_create'),
    path('limits/<int:pk>/', views.OperationLimitDetailView.as_view(), name='limit_detail'),
    path('limits/<int:pk>/edit/', views.OperationLimitUpdateView.as_view(), name='limit_update'),
    path('limits/<int:pk>/delete/', views.OperationLimitDeleteView.as_view(), name='limit_delete'),

    # Endpoints API REST Límites Operativos (SCRUM-77)
    path('api/limits/', views.OperationLimitListApiView.as_view(), name='api_limits'),
    path('api/limits/validate/', views.ValidateOperationLimitApiView.as_view(), name='api_limits_validate'),
    path('api/limits/<str:segment>/<str:currency_code>/', views.OperationLimitDetailApiView.as_view(), name='api_limit_detail'),
]
