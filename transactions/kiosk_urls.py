"""
Rutas URL para la terminal táctil de autoservicio Kiosco y hardware de efectivo (SCRUM-121 / SCRUM-122).
"""

from django.urls import path
from .kiosk_views import (
    FacturaSeguraQuotaApiView,
    KioskCashAcceptApiView,
    KioskCashDispenseApiView,
    KioskCashReceiptApiView,
    KioskCashReceiptView,
    KioskCashStatusApiView,
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
    # KuDE y Facturación Electrónica (SCRUM-121)
    path('kude/<int:pk>/', TransactionKudeView.as_view(), name='kude_view'),
    path('kude/<int:pk>/pdf/', TransactionKudePdfDownloadView.as_view(), name='kude_pdf'),
    path('kude/<int:pk>/xml/', TransactionKudeXmlDownloadView.as_view(), name='kude_xml'),
    # Hardware de Efectivo y FacturaSegura PAC (SCRUM-122)
    path('api/cash/status/', KioskCashStatusApiView.as_view(), name='api_cash_status'),
    path('api/cash/accept/', KioskCashAcceptApiView.as_view(), name='api_cash_accept'),
    path('api/cash/dispense/', KioskCashDispenseApiView.as_view(), name='api_cash_dispense'),
    path('api/cash/receipt/<uuid:uuid>/', KioskCashReceiptApiView.as_view(), name='api_cash_receipt'),
    path('receipt/<uuid:uuid>/', KioskCashReceiptView.as_view(), name='cash_receipt'),
    path('api/facturasegura/cuota/', FacturaSeguraQuotaApiView.as_view(), name='api_facturasegura_cuota'),
]
