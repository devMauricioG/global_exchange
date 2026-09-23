"""
Rutas URL para la aplicación de Transacciones Cambiarias (transactions).
"""

from django.urls import path
from transactions.views import (
    TransactionCancelApiView,
    TransactionCancelView,
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
    path('<int:pk>/cancel/', TransactionCancelView.as_view(), name='cancel'),
    path('api/create/', TransactionCreateApiView.as_view(), name='api_create'),
    path('api/<int:pk>/cancel/', TransactionCancelApiView.as_view(), name='api_cancel'),
]
