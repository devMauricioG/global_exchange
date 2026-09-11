from django.urls import path

from . import views

app_name = 'rates'

urlpatterns = [
    # Rutas para Currency (Monedas)
    path('currencies/', views.CurrencyListView.as_view(), name='currency-list'),
    path('currencies/create/', views.CurrencyCreateView.as_view(), name='currency-create'),
    path('currencies/<int:pk>/update/', views.CurrencyUpdateView.as_view(), name='currency-update'),
    path('currencies/<int:pk>/toggle/', views.CurrencyToggleStatusView.as_view(), name='currency-toggle'),

    # Rutas para ExchangeRate (Tasas de Cambio)
    path('exchange-rates/', views.ExchangeRateListView.as_view(), name='rate-list'),
    path('exchange-rates/create/', views.ExchangeRateCreateView.as_view(), name='rate-create'),
    path('exchange-rates/<int:pk>/update/', views.ExchangeRateUpdateView.as_view(), name='rate-update'),
    path('exchange-rates/<int:pk>/toggle/', views.ExchangeRateToggleStatusView.as_view(), name='rate-toggle'),
]
