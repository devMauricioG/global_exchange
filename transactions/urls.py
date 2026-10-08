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
    TransactionPaymentCheckoutView,
    TransactionReceiptView,
)

app_name = 'transactions'

urlpatterns = [
    path('', TransactionListView.as_view(), name='list'),
    path('create/', TransactionCreateView.as_view(), name='create'),
    path('confirm/', TransactionConfirmView.as_view(), name='confirm'),
    path('<int:pk>/', TransactionDetailView.as_view(), name='detail'),
    path('<int:pk>/pago/', TransactionPaymentCheckoutView.as_view(), name='payment-checkout'),
    path('<int:pk>/checkout/', TransactionPaymentCheckoutView.as_view(), name='payment_checkout'),
    path('<int:pk>/cancel/', TransactionCancelView.as_view(), name='cancel'),
    path('<int:pk>/receipt/', TransactionReceiptView.as_view(), name='receipt'),
    path('api/create/', TransactionCreateApiView.as_view(), name='api_create'),
    path('api/<int:pk>/cancel/', TransactionCancelApiView.as_view(), name='api_cancel'),
]
