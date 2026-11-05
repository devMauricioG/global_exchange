"""
Rutas URL para el módulo de Facturación Electrónica SIFEN (apps.invoicing - SCRUM-119).
"""

from django.urls import path

from .views import (
    FacturaConsultaApiView,
    FacturaElectronicaDetailView,
    FacturaElectronicaPdfDownloadView,
    FacturaElectronicaSifenSyncAjaxView,
    FacturaElectronicaXmlDownloadView,
)

app_name = 'invoicing'

urlpatterns = [
    # Visualización completa del KuDE / Factura Electrónica
    path('facturas/<int:pk>/', FacturaElectronicaDetailView.as_view(), name='detail'),
    # Descarga directa de archivos oficiales
    path('facturas/<int:pk>/pdf/', FacturaElectronicaPdfDownloadView.as_view(), name='pdf'),
    path('facturas/<int:pk>/xml/', FacturaElectronicaXmlDownloadView.as_view(), name='xml'),
    # Sincronización AJAX de estado SIFEN
    path('facturas/<int:pk>/sync-sifen/', FacturaElectronicaSifenSyncAjaxView.as_view(), name='sync_sifen'),
    # Endpoint REST API de consulta pública por CDC / identificador
    path('api/consulta/<str:identifier>/', FacturaConsultaApiView.as_view(), name='consulta_api'),
    path('api/consulta/', FacturaConsultaApiView.as_view(), name='consulta_api_query'),
]

