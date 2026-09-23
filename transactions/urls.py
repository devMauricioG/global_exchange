"""
Rutas URL para la aplicación de Transacciones Cambiarias.
"""

from django.urls import path
from transactions.views import TransactionPlaceholderView

app_name = 'transactions'

urlpatterns = [
    path('', TransactionPlaceholderView.as_view(), name='index'),
]
