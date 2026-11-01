"""
Vistas y endpoints para consulta, visualización y descarga de KUDE PDF y XML firmado (SCRUM-121).

Provee las interfaces web y API REST para:
1. Visualización interactiva del comprobante KuDE (e-Kuatia).
2. Descarga del archivo oficial en formato PDF binario.
3. Descarga del XML firmado digitalmente (XML-DSig).
4. Endpoint JSON de consulta de estado tributario en SIFEN por CDC o código de transacción.
"""

from typing import Any, Dict
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from authentication.permissions import has_role
from rates.services import get_active_customer
from .kude_pdf import KudePdfGenerator
from .kude_service import KudeService
from .models import ElectronicInvoice, Transaction


class BaseKudeAccessMixin:
    """
    Mixin de seguridad para validar el acceso autorizado a comprobantes KuDE.

    Permite acceso:
    - A usuarios administradores u operadores del sistema.
    - Al cliente titular de la transacción (o usuario representante asignado).
    - O acceso público para consultas directas mediante el CDC de 44 dígitos oficial.
    """

    def check_kude_permission(self, request: HttpRequest, transaction: Transaction) -> bool:
        if request.user.is_staff or request.user.is_superuser:
            return True

        if has_role(request.user, 'admin,operator'):
            return True

        # Acceso de cliente
        cliente = get_active_customer(request)
        if cliente and transaction.cliente_id == cliente.id:
            return True

        # Si el usuario es el operador o usuario asignado a la transacción
        if request.user.is_authenticated and transaction.usuario_id == request.user.id:
            return True

        return False


class TransactionKudeView(BaseKudeAccessMixin, View):
    """
    Vista web interactiva para la visualización del comprobante electrónico KuDE.

    Renderiza la plantilla oficial de Factura Electrónica con layout responsivo,
    código de barras, desglose de impuestos e importes, y botones de descarga y print.
    """

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        tx = get_object_or_404(
            Transaction.objects.select_related(
                'cliente', 'base_currency', 'target_currency',
                'medio_pago_origen', 'medio_acreditacion_destino', 'usuario'
            ),
            pk=pk
        )

        # Si el usuario está autenticado, validar pertenencia (a menos que se consulte por kiosco)
        if request.user.is_authenticated and not self.check_kude_permission(request, tx):
            raise PermissionDenied("No tiene autorización para visualizar el KuDE de esta transacción.")

        # Obtener o generar automáticamente la factura electrónica
        invoice = KudeService.get_or_create_invoice(tx)

        context: Dict[str, Any] = {
            'invoice': invoice,
            'transaction': tx,
            'cliente': tx.cliente,
            'cdc_formatted': invoice.cdc_formatted,
            'qr_data': invoice.qr_data,
            'pdf_url': reverse('transactions:kude_pdf', kwargs={'pk': tx.pk}),
            'xml_url': reverse('transactions:kude_xml', kwargs={'pk': tx.pk}),
            'receipt_url': reverse('transactions:receipt', kwargs={'pk': tx.pk}),
            'is_kiosk': 'kiosk' in request.path or request.GET.get('source') == 'kiosk',
        }
        return render(request, 'transactions/kude.html', context)


class TransactionKudePdfDownloadView(BaseKudeAccessMixin, View):
    """
    Endpoint para generar y descargar la representación gráfica oficial del KuDE en formato PDF binario.
    """

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        tx = get_object_or_404(Transaction.objects.select_related('cliente', 'base_currency', 'target_currency'), pk=pk)

        if request.user.is_authenticated and not self.check_kude_permission(request, tx):
            raise PermissionDenied("No tiene autorización para descargar el KuDE de esta transacción.")

        invoice = KudeService.get_or_create_invoice(tx)
        pdf_bytes = KudePdfGenerator.generate_pdf(invoice)

        filename = f"kude_{tx.codigo_referencia or tx.pk}_{invoice.numero_factura}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(pdf_bytes)
        return response


class TransactionKudeXmlDownloadView(BaseKudeAccessMixin, View):
    """
    Endpoint para descargar el archivo XML firmado digitalmente (e-Kuatia) de la factura electrónica.
    """

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        tx = get_object_or_404(Transaction.objects.select_related('cliente', 'base_currency', 'target_currency'), pk=pk)

        if request.user.is_authenticated and not self.check_kude_permission(request, tx):
            raise PermissionDenied("No tiene autorización para descargar el XML de esta transacción.")

        invoice = KudeService.get_or_create_invoice(tx)

        filename = f"kude_{invoice.cdc}.xml"
        response = HttpResponse(invoice.xml_firmado, content_type='application/xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class TransactionKudeConsultaApiView(View):
    """
    Endpoint API REST JSON para consulta y verificación pública del estado de un KuDE en SIFEN.

    Permite consultar por CDC de 44 dígitos, número de factura o código de referencia de transacción.
    """

    def get(self, request: HttpRequest, identifier: str = '', *args: Any, **kwargs: Any) -> JsonResponse:
        search_term = identifier or request.GET.get('q') or request.GET.get('cdc') or ''
        if not search_term:
            return JsonResponse({
                'success': False,
                'error': 'Debe especificar un parámetro de consulta (CDC, código o número de factura).'
            }, status=400)

        invoice = KudeService.lookup_invoice(search_term)
        if not invoice:
            return JsonResponse({
                'success': False,
                'error': f'No se encontró ningún comprobante electrónico para el identificador: {search_term}'
            }, status=404)

        tx = invoice.transaction
        cliente = tx.cliente

        data = {
            'success': True,
            'cdc': invoice.cdc,
            'cdc_formatted': invoice.cdc_formatted,
            'numero_factura': invoice.numero_factura,
            'timbrado': invoice.timbrado,
            'fecha_emision': invoice.fecha_emision.isoformat(),
            'estado_sifen': invoice.estado,
            'protocolo_autorizacion': invoice.protocolo_autorizacion,
            'cliente': {
                'nombre': getattr(cliente, 'nombre', ''),
                'documento_ruc': getattr(cliente, 'documento_ruc', ''),
                'segmento': getattr(cliente, 'get_segmentacion_display', lambda: '')(),
            },
            'transaccion': {
                'id': tx.id,
                'codigo_referencia': tx.codigo_referencia,
                'tipo_operacion': tx.get_tipo_operacion_display(),
                'moneda_origen': tx.moneda_origen.code,
                'monto_origen': str(tx.monto_origen),
                'moneda_destino': tx.moneda_destino.code,
                'monto_destino': str(tx.monto_destino),
                'tasa_neta': str(tx.tasa_neta),
                'estado': tx.get_estado_display(),
            },
            'urls': {
                'view_url': request.build_absolute_uri(reverse('transactions:kude', kwargs={'pk': tx.pk})),
                'pdf_url': request.build_absolute_uri(reverse('transactions:kude_pdf', kwargs={'pk': tx.pk})),
                'xml_url': request.build_absolute_uri(reverse('transactions:kude_xml', kwargs={'pk': tx.pk})),
                'qr_url': invoice.qr_data,
            }
        }
        return JsonResponse(data)

