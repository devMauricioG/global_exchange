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

        # Priorizar FacturaElectronica canónica de apps.invoicing
        invoice = getattr(tx, 'factura_sifen', None)
        if not invoice:
            from apps.invoicing.models import FacturaElectronica
            invoice = FacturaElectronica.objects.filter(transaction=tx).first()

        # Si aún no existe, usar KudeService
        if not invoice:
            invoice = KudeService.get_or_create_invoice(tx)

        context: Dict[str, Any] = {
            'invoice': invoice,
            'factura': invoice,
            'transaction': tx,
            'cliente': tx.cliente,
            'cdc_formatted': getattr(invoice, 'cdc_formatted', getattr(invoice, 'cdc', '')),
            'qr_data': getattr(invoice, 'qr_data', ''),
            'pdf_url': reverse('transactions:kude_pdf', kwargs={'pk': tx.pk}),
            'xml_url': reverse('transactions:kude_xml', kwargs={'pk': tx.pk}),
            'sync_url': reverse('transactions:kude_sync_sifen', kwargs={'pk': tx.pk}),
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

        # Priorizar FacturaElectronica canónica de apps.invoicing
        factura_sifen = getattr(tx, 'factura_sifen', None)
        if not factura_sifen:
            from apps.invoicing.models import FacturaElectronica
            factura_sifen = FacturaElectronica.objects.filter(transaction=tx).first()

        if factura_sifen:
            pdf_bytes = b''
            if factura_sifen.archivo_pdf:
                try:
                    factura_sifen.archivo_pdf.open('rb')
                    pdf_bytes = factura_sifen.archivo_pdf.read()
                    factura_sifen.archivo_pdf.close()
                except Exception:
                    pass
            if not pdf_bytes:
                from apps.invoicing.providers import get_invoice_provider
                try:
                    pdf_bytes = get_invoice_provider().dwn_kude(factura_sifen.cdc)
                except Exception:
                    pass
            if not pdf_bytes:
                pdf_bytes = KudePdfGenerator.generate_pdf(factura_sifen)

            filename = f"kude_{tx.codigo_referencia or tx.pk}_{factura_sifen.numero_factura or factura_sifen.cdc[:12]}.pdf"
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = len(pdf_bytes)
            return response

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

        # Priorizar FacturaElectronica canónica de apps.invoicing
        factura_sifen = getattr(tx, 'factura_sifen', None)
        if not factura_sifen:
            from apps.invoicing.models import FacturaElectronica
            factura_sifen = FacturaElectronica.objects.filter(transaction=tx).first()

        if factura_sifen:
            xml_content = factura_sifen.xml_firmado
            if not xml_content and factura_sifen.archivo_xml:
                try:
                    factura_sifen.archivo_xml.open('r')
                    xml_content = factura_sifen.archivo_xml.read()
                    factura_sifen.archivo_xml.close()
                except Exception:
                    pass
            if not xml_content:
                from apps.invoicing.providers import get_invoice_provider
                try:
                    xml_content = get_invoice_provider().dwn_xml(factura_sifen.cdc)
                except Exception:
                    pass

            filename = f"sifen_{factura_sifen.cdc}.xml"
            response = HttpResponse(xml_content, content_type='application/xml; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

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


class TransactionSifenSyncAjaxView(BaseKudeAccessMixin, View):
    """
    Endpoint AJAX para consulta y sincronización en tiempo real del estado SIFEN
    asociado a una transacción cambiaria (SCRUM-119).
    """

    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        return self._sync_status(request, pk)

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        return self._sync_status(request, pk)

    def _sync_status(self, request: HttpRequest, pk: int) -> JsonResponse:
        tx = get_object_or_404(
            Transaction.objects.select_related('cliente', 'base_currency', 'target_currency'),
            pk=pk
        )

        if not self.check_kude_permission(request, tx):
            return JsonResponse({'success': False, 'error': 'No autorizado.'}, status=403)

        # 1. Priorizar modelo canónico FacturaElectronica de apps.invoicing
        factura_sifen = getattr(tx, 'factura_sifen', None)
        if not factura_sifen:
            from apps.invoicing.models import FacturaElectronica
            factura_sifen = FacturaElectronica.objects.filter(transaction=tx).first()

        # Si aún no existe pero la tx está completada, emitir mediante InvoiceProvider
        if not factura_sifen and tx.estado == Transaction.Estado.COMPLETADA:
            from apps.invoicing.providers import get_invoice_provider
            from apps.invoicing.services import InvoiceService
            provider = get_invoice_provider()
            resp = provider.emitir_factura(tx)
            factura_sifen = InvoiceService.create_from_response(tx, resp)

        if factura_sifen:
            from apps.invoicing.providers import get_invoice_provider
            from apps.invoicing.services import InvoiceService
            from apps.invoicing.models import FacturaElectronica

            provider = get_invoice_provider()
            try:
                status_response = provider.get_estado_sifen(factura_sifen.cdc)
                factura_sifen = InvoiceService.update_estado(factura_sifen.cdc, status_response)
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Error al consultar SIFEN: {str(e)}'}, status=502)

            COLOR_MAP = {
                FacturaElectronica.EstadoSifen.APROBADO: '#10b981',
                FacturaElectronica.EstadoSifen.APROBADO_OBS: '#8b5cf6',
                FacturaElectronica.EstadoSifen.RECHAZADO: '#ef4444',
                FacturaElectronica.EstadoSifen.CANCELADO: '#f97316',
                FacturaElectronica.EstadoSifen.INUTILIZADO: '#6b7280',
                FacturaElectronica.EstadoSifen.EMITIDO: '#06b6d4',
                FacturaElectronica.EstadoSifen.ENVIADO_A_SIFEN: '#3b82f6',
                FacturaElectronica.EstadoSifen.SOL_APROBACION: '#f59e0b',
            }
            color = COLOR_MAP.get(factura_sifen.estado_sifen, '#6b7280')
            badge_html = (
                f'<span class="badge" style="background-color: {color}; color: #fff; font-weight: 700; '
                f'padding: 0.35rem 0.75rem; border-radius: 9999px; display: inline-flex; '
                f'align-items: center; gap: 0.35rem; font-size: 0.85rem; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">'
                f'● {factura_sifen.get_estado_sifen_display()}</span>'
            )

            return JsonResponse({
                'success': True,
                'message': 'Estado SIFEN sincronizado exitosamente.',
                'cdc': factura_sifen.cdc,
                'cdc_formatted': factura_sifen.cdc_formatted,
                'numero_factura': factura_sifen.numero_factura,
                'estado_sifen': factura_sifen.estado_sifen,
                'estado_sifen_display': factura_sifen.get_estado_sifen_display(),
                'descripcion_sifen': factura_sifen.descripcion_sifen,
                'protocolo_autorizacion': factura_sifen.protocolo_autorizacion,
                'is_approved': factura_sifen.is_aprobado,
                'is_cancelled': factura_sifen.is_cancelado,
                'is_inutilizado': factura_sifen.is_inutilizado,
                'es_simulada': factura_sifen.es_simulada,
                'updated_at': factura_sifen.updated_at.strftime('%d/%m/%Y %H:%M:%S'),
                'badge_html': badge_html,
            })

        # Fallback a ElectronicInvoice legacy si existiera
        invoice = KudeService.get_or_create_invoice(tx)
        return JsonResponse({
            'success': True,
            'message': 'Estado SIFEN verificado exitosamente.',
            'cdc': invoice.cdc,
            'cdc_formatted': invoice.cdc_formatted,
            'numero_factura': invoice.numero_factura,
            'estado_sifen': invoice.estado,
            'estado_sifen_display': invoice.get_estado_display(),
            'descripcion_sifen': '0260 - Aprobado',
            'protocolo_autorizacion': invoice.protocolo_autorizacion,
            'is_approved': True,
            'is_cancelled': False,
            'es_simulada': True,
            'updated_at': invoice.updated_at.strftime('%d/%m/%Y %H:%M:%S'),
            'badge_html': '<span class="badge badge-active">● Aprobado</span>',
        })


