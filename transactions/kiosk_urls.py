"""
Rutas URL para la terminal táctil de autoservicio Kiosco (SCRUM-121).
"""

from django.urls import path
from .kiosk_views import (
    KioskCustomerLookupApiView,
    KioskExpressRegisterApiView,
    KioskHomeView,
    KioskQuoteApiView,
    KioskTransactApiView,
)
from .kude_views import (
    TransactionKudePdfDownloadView,
    TransactionKudeView,
    TransactionKudeXmlDownloadView,
)

app_name = 'kiosk'

urlpatterns = [
    path('', KioskHomeView.as_view(), name='home'),
    path('api/quote/', KioskQuoteApiView.as_view(), name='api_quote'),
    path('api/customer-lookup/', KioskCustomerLookupApiView.as_view(), name='api_customer_lookup'),
    path('api/customer-register/', KioskExpressRegisterApiView.as_view(), name='api_customer_register'),
    path('api/transact/', KioskTransactApiView.as_view(), name='api_transact'),
    path('kude/<int:pk>/', TransactionKudeView.as_view(), name='kude_view'),
    path('kude/<int:pk>/pdf/', TransactionKudePdfDownloadView.as_view(), name='kude_pdf'),
    path('kude/<int:pk>/xml/', TransactionKudeXmlDownloadView.as_view(), name='kude_xml'),
]

