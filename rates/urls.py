"""
Módulo de enrutamiento y URLs para la aplicación de Tasas y Comisiones (rates).
"""

from django.urls import path
from . import views

app_name = 'rates'

urlpatterns = [
    # Gestión Administrativa de Comisiones por Segmento
    path('commissions/', views.SegmentCommissionListView.as_view(), name='commission_list'),
    path('commissions/add/', views.SegmentCommissionCreateView.as_view(), name='commission_create'),
    path('commissions/<int:pk>/', views.SegmentCommissionDetailView.as_view(), name='commission_detail'),
    path('commissions/<int:pk>/edit/', views.SegmentCommissionUpdateView.as_view(), name='commission_update'),
    path('commissions/<int:pk>/delete/', views.SegmentCommissionDeleteView.as_view(), name='commission_delete'),

    # Simulador y Motor de Cotizaciones Netas
    path('calculator/', views.RateCalculatorView.as_view(), name='rate_calculator'),

    # Endpoints API REST (JSON)
    path('api/calculate/', views.CalculateNetRateApiView.as_view(), name='api_calculate'),
    path('api/commissions/', views.SegmentCommissionListApiView.as_view(), name='api_commissions'),
    path('api/commissions/<str:segment>/', views.SegmentCommissionDetailApiView.as_view(), name='api_commission_detail'),
]
