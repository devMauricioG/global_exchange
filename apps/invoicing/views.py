"""
Vistas y endpoints para consulta, visualización y descarga de KuDE PDF y XML firmado (SCRUM-119).

Provee:
1. FacturaElectronicaDetailView: Visualización web interactiva de la Factura Electrónica / KuDE.
2. FacturaElectronicaPdfDownloadView: Descarga directa de la representación gráfica KuDE en PDF binario.
3. FacturaElectronicaXmlDownloadView: Descarga directa del archivo XML firmado digitalmente (e-Kuatia).
4. FacturaElectronicaSifenSyncAjaxView: Endpoint AJAX para consulta y sincronización en tiempo real del estado SIFEN.
5. FacturaConsultaApiView: Endpoint REST JSON de consulta pública de estado tributario.
"""

import logging
from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views import View
from django.views.generic import DetailView

from authentication.permissions import has_role
from rates.services import get_active_customer

from apps.invoicing.models import FacturaElectronica
from apps.invoicing.providers import get_invoice_provider
from apps.invoicing.services import InvoiceService

logger = logging.getLogger(__name__)


class InvoicingAccessMixin:
    """
    Mixin de seguridad para validar el acceso autorizado a comprobantes electrónicos.

    Autoriza:
    - Usuarios staff / superusuarios.
    - Usuarios con rol 'admin' u 'operator'.
    - El cliente titular de la transacción asociada.
    - El usuario operador/cajero creador de la transacción.
    """

    def check_factura_permission(self, request: HttpRequest, factura: FacturaElectronica) -> bool:
        if not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return True

        if has_role(request.user, 'admin,operator,cajero'):
            return True

        tx = getattr(factura, 'transaction', None)
        if not tx:
            return False

        cliente = get_active_customer(request)
        if cliente and getattr(tx, 'cliente_id', None) == cliente.id:
            return True

        if getattr(tx, 'usuario_id', None) == request.user.id:
            return True

        # Si el usuario tiene una asignación activa con el cliente
        if hasattr(tx, 'cliente') and tx.cliente:
            if tx.cliente.assignments.filter(user=request.user, is_active=True).exists():
                return True

        return False


class FacturaElectronicaDetailView(InvoicingAccessMixin, View):
    """
    Vista web para visualización completa de la Factura Electrónica y KuDE oficial.
    """

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        factura = get_object_or_404(
            FacturaElectronica.objects.select_related(
                'transaction',
                'transaction__cliente',
                'transaction__base_currency',
                'transaction__target_currency',
                'transaction__medio_pago_origen',
                'transaction__medio_acreditacion_destino',
            ),
            pk=pk,
        )

        if not self.check_factura_permission(request, factura):
            raise PermissionDenied("No tiene autorización para visualizar esta Factura Electrónica.")

        tx = factura.transaction
        cliente = getattr(tx, 'cliente', None)

        context: Dict[str, Any] = {
            'factura': factura,
            'invoice': factura,
            'transaction': tx,
            'cliente': cliente,
            'cdc_formatted': factura.cdc_formatted,
            'qr_data': factura.qr_data,
            'pdf_url': reverse('invoicing:pdf', kwargs={'pk': factura.pk}),
            'xml_url': reverse('invoicing:xml', kwargs={'pk': factura.pk}),
            'sync_url': reverse('invoicing:sync_sifen', kwargs={'pk': factura.pk}),
            'receipt_url': reverse('transactions:receipt', kwargs={'pk': tx.pk}) if tx else '',
            'detail_url': reverse('transactions:detail', kwargs={'pk': tx.pk}) if tx else '',
        }
        return render(request, 'transactions/kude.html', context)


class FacturaElectronicaPdfDownloadView(InvoicingAccessMixin, View):
    """
    Endpoint para descarga directa de la representación gráfica oficial KuDE en formato PDF binario.
    """

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        factura = get_object_or_404(
            FacturaElectronica.objects.select_related('transaction', 'transaction__cliente'),
            pk=pk,
        )

        if not self.check_factura_permission(request, factura):
            raise PermissionDenied("No tiene autorización para descargar este KuDE PDF.")

        pdf_bytes = b''
        # 1. Intentar leer desde archivo persistido
        if factura.archivo_pdf:
            try:
                factura.archivo_pdf.open('rb')
                pdf_bytes = factura.archivo_pdf.read()
                factura.archivo_pdf.close()
            except Exception as e:
                logger.warning("Error leyendo archivo_pdf para factura %s: %s", factura.pk, e)

        # 2. Si no tiene archivo físico o falló, obtener vía provider
        if not pdf_bytes:
            provider = get_invoice_provider()
            try:
                pdf_bytes = provider.dwn_kude(factura.cdc)
                # Persistir para futuras solicitudes
                if pdf_bytes:
                    factura.save_pdf_content(pdf_bytes, filename=f"kude_{factura.cdc}.pdf")
                    factura.save(update_fields=['archivo_pdf', 'updated_at'])
            except Exception as e:
                logger.error("Error descargando KuDE PDF vía provider: %s", e)

        # 3. Fallback a KudePdfGenerator si está disponible
        if not pdf_bytes:
            try:
                from transactions.kude_pdf import KudePdfGenerator
                pdf_bytes = KudePdfGenerator.generate_pdf(factura)
            except Exception as e:
                logger.error("Error generando PDF alternativo: %s", e)

        if not pdf_bytes:
            return HttpResponse("No se pudo generar el archivo KuDE PDF.", status=500, content_type='text/plain')

        filename = f"kude_{factura.numero_factura or factura.cdc[:12]}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(pdf_bytes)
        return response


class FacturaElectronicaXmlDownloadView(InvoicingAccessMixin, View):
    """
    Endpoint para descarga directa del archivo XML firmado digitalmente (e-Kuatia).
    """

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        factura = get_object_or_404(
            FacturaElectronica.objects.select_related('transaction', 'transaction__cliente'),
            pk=pk,
        )

        if not self.check_factura_permission(request, factura):
            raise PermissionDenied("No tiene autorización para descargar el XML de esta factura.")

        xml_content = factura.xml_firmado

        # Si no tiene XML en texto, intentar leer del archivo
        if not xml_content and factura.archivo_xml:
            try:
                factura.archivo_xml.open('r')
                xml_content = factura.archivo_xml.read()
                factura.archivo_xml.close()
            except Exception as e:
                logger.warning("Error leyendo archivo_xml para factura %s: %s", factura.pk, e)

        # Si aún no tiene, solicitar al provider
        if not xml_content:
            provider = get_invoice_provider()
            try:
                xml_content = provider.dwn_xml(factura.cdc)
                if xml_content:
                    factura.save_xml_content(xml_content, filename=f"sifen_{factura.cdc}.xml")
                    factura.save(update_fields=['xml_firmado', 'archivo_xml', 'updated_at'])
            except Exception as e:
                logger.error("Error descargando XML vía provider: %s", e)

        if not xml_content:
            return HttpResponse("No se encontró el XML firmado para este documento.", status=404, content_type='text/plain')

        filename = f"sifen_{factura.cdc}.xml"
        response = HttpResponse(xml_content, content_type='application/xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class FacturaElectronicaSifenSyncAjaxView(InvoicingAccessMixin, View):
    """
    Endpoint AJAX para consulta y sincronización en tiempo real del estado de la factura en SIFEN.

    Realiza:
    1. Consulta de estado al proveedor SIFEN configurado (MockInvoiceProvider o FacturaSeguraProvider).
    2. Actualización atómica en base de datos mediante InvoiceService.update_estado.
    3. Retorno de un payload JSON con el nuevo estado, descripción, metadatos y badge HTML formateado.
    """

    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        return self._sync_status(request, pk)

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        return self._sync_status(request, pk)

    def _sync_status(self, request: HttpRequest, pk: int) -> JsonResponse:
        factura = get_object_or_404(
            FacturaElectronica.objects.select_related('transaction', 'transaction__cliente'),
            pk=pk,
        )

        if not self.check_factura_permission(request, factura):
            return JsonResponse({'success': False, 'error': 'No autorizado.'}, status=403)

        provider = get_invoice_provider()
        try:
            status_response = provider.get_estado_sifen(factura.cdc)
            updated_factura = InvoiceService.update_estado(factura.cdc, status_response)
        except Exception as e:
            logger.error("Error sincronizando estado SIFEN para factura %s (CDC %s): %s", pk, factura.cdc, e)
            return JsonResponse({
                'success': False,
                'error': f'Error al consultar SIFEN: {str(e)}',
                'estado_actual': factura.estado_sifen,
                'estado_actual_display': factura.get_estado_sifen_display(),
            }, status=502)

        COLOR_MAP = {
            FacturaElectronica.EstadoSifen.APROBADO: ('#10b981', '#064e3b'),       # Verde
            FacturaElectronica.EstadoSifen.APROBADO_OBS: ('#8b5cf6', '#4c1d95'),   # Morado
            FacturaElectronica.EstadoSifen.RECHAZADO: ('#ef4444', '#7f1d1d'),      # Rojo
            FacturaElectronica.EstadoSifen.CANCELADO: ('#f97316', '#7c2d12'),      # Naranja
            FacturaElectronica.EstadoSifen.INUTILIZADO: ('#6b7280', '#1f2937'),    # Gris
            FacturaElectronica.EstadoSifen.EMITIDO: ('#06b6d4', '#164e63'),        # Cian
            FacturaElectronica.EstadoSifen.ENVIADO_A_SIFEN: ('#3b82f6', '#1e3a8a'),# Azul
            FacturaElectronica.EstadoSifen.SOL_APROBACION: ('#f59e0b', '#78350f'), # Ámbar
        }
        color, border_color = COLOR_MAP.get(
            updated_factura.estado_sifen,
            ('#6b7280', '#374151'),
        )

        badge_html = format_html(
            '<span class="badge" style="background-color: {}; color: #fff; font-weight: 700; '
            'padding: 0.35rem 0.75rem; border-radius: 9999px; display: inline-flex; '
            'align-items: center; gap: 0.35rem; font-size: 0.85rem; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">'
            '● {}</span>',
            color,
            updated_factura.get_estado_sifen_display(),
        )

        return JsonResponse({
            'success': True,
            'message': 'Estado SIFEN sincronizado exitosamente.',
            'cdc': updated_factura.cdc,
            'cdc_formatted': updated_factura.cdc_formatted,
            'numero_factura': updated_factura.numero_factura,
            'estado_sifen': updated_factura.estado_sifen,
            'estado_sifen_display': updated_factura.get_estado_sifen_display(),
            'descripcion_sifen': updated_factura.descripcion_sifen,
            'protocolo_autorizacion': updated_factura.protocolo_autorizacion,
            'is_approved': updated_factura.is_aprobado,
            'is_cancelled': updated_factura.is_cancelado,
            'is_inutilizado': updated_factura.is_inutilizado,
            'es_simulada': updated_factura.es_simulada,
            'updated_at': updated_factura.updated_at.strftime('%d/%m/%Y %H:%M:%S'),
            'badge_html': badge_html,
        })


class FacturaConsultaApiView(View):
    """
    Endpoint API REST JSON para consulta y verificación pública del estado de un DTE en SIFEN.
    Permite consultar por CDC de 44 dígitos, número de factura o código de referencia de transacción.
    """

    def get(self, request: HttpRequest, identifier: str = '', *args: Any, **kwargs: Any) -> JsonResponse:
        search_term = identifier or request.GET.get('q') or request.GET.get('cdc') or ''
        clean_id = str(search_term).strip()

        if not clean_id:
            return JsonResponse({
                'success': False,
                'error': 'Debe especificar un parámetro de consulta (CDC, código o número de factura).'
            }, status=400)

        factura = None

        # 1. Por CDC (44 dígitos)
        if len(clean_id) == 44 and clean_id.isdigit():
            factura = FacturaElectronica.objects.filter(cdc=clean_id).select_related('transaction', 'transaction__cliente').first()

        # 2. Por número de factura
        if not factura:
            factura = FacturaElectronica.objects.filter(numero_factura__iexact=clean_id).select_related('transaction', 'transaction__cliente').first()

        # 3. Por código de transacción
        if not factura:
            factura = FacturaElectronica.objects.filter(transaction__codigo_referencia__iexact=clean_id).select_related('transaction', 'transaction__cliente').first()

        # 4. Por ID numérico de transacción (solo si es un entero manejable)
        if not factura and clean_id.isdigit() and len(clean_id) <= 9:
            factura = FacturaElectronica.objects.filter(transaction_id=int(clean_id)).select_related('transaction', 'transaction__cliente').first()

        if not factura:
            return JsonResponse({
                'success': False,
                'error': f'No se encontró ningún comprobante electrónico para el identificador: {clean_id}'
            }, status=404)

        tx = factura.transaction
        cliente = getattr(tx, 'cliente', None)

        data = {
            'success': True,
            'cdc': factura.cdc,
            'cdc_formatted': factura.cdc_formatted,
            'numero_factura': factura.numero_factura,
            'timbrado': factura.timbrado,
            'fecha_emision': factura.fecha_emision.isoformat(),
            'estado_sifen': factura.estado_sifen,
            'estado_sifen_display': factura.get_estado_sifen_display(),
            'descripcion_sifen': factura.descripcion_sifen,
            'protocolo_autorizacion': factura.protocolo_autorizacion,
            'es_simulada': factura.es_simulada,
            'monto_total': str(factura.monto_total),
            'moneda': factura.moneda,
            'cliente': {
                'nombre': getattr(cliente, 'nombre', '') or factura.razon_social_receptor,
                'documento_ruc': getattr(cliente, 'documento_ruc', '') or factura.ruc_receptor,
            },
            'urls': {
                'detail_url': request.build_absolute_uri(reverse('invoicing:detail', kwargs={'pk': factura.pk})),
                'pdf_url': request.build_absolute_uri(reverse('invoicing:pdf', kwargs={'pk': factura.pk})),
                'xml_url': request.build_absolute_uri(reverse('invoicing:xml', kwargs={'pk': factura.pk})),
                'qr_url': factura.qr_data,
            }
        }
        return JsonResponse(data)
