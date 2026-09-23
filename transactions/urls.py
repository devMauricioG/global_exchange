"""
Rutas URL para la aplicación de Transacciones Cambiarias (transactions).
"""

from django.urls import path
from transactions.views import (
    TransactionCreateApiView,
    TransactionCreateView,
    TransactionConfirmView,
    TransactionDetailView,
    TransactionListView,
)

app_name = 'transactions'

urlpatterns = [
    path('', TransactionListView.as_view(), name='list'),
    path('create/', TransactionCreateView.as_view(), name='create'),
    path('confirm/', TransactionConfirmView.as_view(), name='confirm'),
    path('<int:pk>/', TransactionDetailView.as_view(), name='detail'),
    path('api/create/', TransactionCreateApiView.as_view(), name='api_create'),
]
