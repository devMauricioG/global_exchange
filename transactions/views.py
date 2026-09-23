"""
Vistas para la aplicación de Transacciones Cambiarias (transactions).

Provee la interfaz web y endpoints de API JSON para el registro, confirmación,
consulta detallada y listado de transacciones cambiarias en Global Exchange.
"""

from decimal import Decimal, InvalidOperation
import json
import logging
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, TemplateView

from customers.models import Cliente
from payments.models import PaymentMethod, ReceivingMethod
from rates.services import (
    QuoteFreezeService,
    RateCalculationService,
    get_active_customer,
)
from transactions.forms import TransactionOrderForm
from transactions.models import Transaction
from transactions.services import TransactionService

logger = logging.getLogger(__name__)


class TransactionCreateView(LoginRequiredMixin, View):
    """
    Vista GET para la pantalla de registro y selección de medios de pago/acreditación
    para una orden de compra o venta de divisas.
    """
    template_name = 'transactions/transaction_create.html'

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        cliente = get_active_customer(request)
        if not cliente:
            messages.error(request, 'No tenés una ficha de cliente activa vinculada para operar.')
            return redirect('rates:calculator')

        token = request.GET.get('token', '').strip()
        base_code = request.GET.get('base', 'USD').strip().upper()
        target_code = request.GET.get('target', 'PYG').strip().upper()
        raw_amount = request.GET.get('amount', '100').strip()
        operation_type = request.GET.get('operation_type', 'BUY').strip().upper()
        is_source_base_str = request.GET.get('is_source_base', 'true').strip().lower()
        is_source_base = is_source_base_str in ('true', '1', 'yes')

        quote_data = None
        error_msg = None

        if token:
            # Flujo con cotización congelada
            is_valid, frozen, msg = QuoteFreezeService.validate_quote_token(request, token)
            if is_valid and frozen:
                quote_data = frozen.get('calculation')
            else:
                error_msg = f"La cotización congelada no es válida: {msg}"
        else:
            # Flujo con cotización en vivo
            try:
                amount = Decimal(raw_amount)
                quote_data = RateCalculationService.calculate_quotation_by_codes(
                    base_currency_code=base_code,
                    target_currency_code=target_code,
                    segment_or_customer=cliente,
                    amount=amount,
                    operation_type='BUY' if operation_type in ('BUY', 'COMPRA') else 'SELL',
                    is_source_base=is_source_base,
                )
            except Exception as exc:
                error_msg = f"No se pudo obtener la cotización: {exc}"

        if not quote_data:
            messages.error(request, error_msg or 'No se pudo cargar los datos de la cotización.')
            return redirect('rates:calculator')

        # Buscar medios de pago predeterminados para inicializar el formulario
        default_payment = PaymentMethod.objects.filter(cliente=cliente, activo=True, es_predeterminado=True).first()
        default_receiving = ReceivingMethod.objects.filter(cliente=cliente, activo=True, es_predeterminado=True).first()

        initial_data = {
            'token_congelamiento': token,
            'base_currency_code': base_code,
            'target_currency_code': target_code,
            'amount': raw_amount,
            'operation_type': operation_type,
            'is_source_base': is_source_base,
        }
        if default_payment:
            initial_data['medio_pago_origen'] = default_payment.id
        if default_receiving:
            initial_data['medio_acreditacion_destino'] = default_receiving.id

        form = TransactionOrderForm(cliente=cliente, initial=initial_data)

        context = {
            'cliente': cliente,
            'form': form,
            'quote_data': quote_data,
            'token': token,
            'base_code': base_code,
            'target_code': target_code,
            'operation_type': operation_type,
        }
        return render(request, self.template_name, context)


class TransactionConfirmView(LoginRequiredMixin, View):
    """
    Vista POST para procesar el formulario de confirmación de orden y crear
    la transacción en estado PENDIENTE.
    """
    template_name = 'transactions/transaction_create.html'

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        cliente = get_active_customer(request)
        if not cliente:
            messages.error(request, 'No se pudo verificar el cliente activo para esta transacción.')
            return redirect('rates:calculator')

        form = TransactionOrderForm(request.POST, cliente=cliente)
        token = request.POST.get('token_congelamiento', '').strip()
        base_code = request.POST.get('base_currency_code', 'USD').strip().upper()
        target_code = request.POST.get('target_currency_code', 'PYG').strip().upper()
        raw_amount = request.POST.get('amount', '100').strip()
        operation_type = request.POST.get('operation_type', 'BUY').strip().upper()
        is_source_base_str = request.POST.get('is_source_base', 'true').strip().lower()
        is_source_base = is_source_base_str in ('true', '1', 'yes')

        if form.is_valid():
            medio_pago = form.cleaned_data['medio_pago_origen']
            medio_acreditacion = form.cleaned_data['medio_acreditacion_destino']
            observaciones = form.cleaned_data.get('observaciones', '')

            try:
                if token:
                    tx = TransactionService.create_order_from_frozen_quote(
                        request=request,
                        token=token,
                        medio_pago_id=medio_pago,
                        medio_acreditacion_id=medio_acreditacion,
                        cliente=cliente,
                        usuario=request.user,
                        observaciones=observaciones,
                    )
                else:
                    tx = TransactionService.create_order_from_live_quote(
                        request=request,
                        base_currency_code=base_code,
                        target_currency_code=target_code,
                        amount=Decimal(raw_amount) if raw_amount else Decimal('100'),
                        operation_type=operation_type,
                        is_source_base=is_source_base,
                        medio_pago_id=medio_pago,
                        medio_acreditacion_id=medio_acreditacion,
                        cliente=cliente,
                        usuario=request.user,
                        observaciones=observaciones,
                    )

                messages.success(
                    request,
                    f"¡Orden registrada exitosamente! Código de referencia: {tx.codigo_referencia}"
                )
                return redirect('transactions:detail', pk=tx.pk)

            except ValidationError as ve:
                for field, err_list in ve.message_dict.items() if hasattr(ve, 'message_dict') else [('__all__', ve.messages)]:
                    for err in err_list:
                        messages.error(request, f"Error en la orden: {err}")
            except Exception as exc:
                logger.exception("Error inesperado procesando confirmación de transacción")
                messages.error(request, f"No se pudo completar el registro de la orden: {exc}")

        # Si el formulario o el servicio devuelven error, recargar pantalla con los datos de cotización
        quote_data = None
        if token:
            _, frozen, _ = QuoteFreezeService.validate_quote_token(request, token)
            if frozen:
                quote_data = frozen.get('calculation')
        if not quote_data:
            try:
                quote_data = RateCalculationService.calculate_quotation_by_codes(
                    base_currency_code=base_code,
                    target_currency_code=target_code,
                    segment_or_customer=cliente,
                    amount=Decimal(raw_amount) if raw_amount else Decimal('100'),
                    operation_type='BUY' if operation_type in ('BUY', 'COMPRA') else 'SELL',
                    is_source_base=is_source_base,
                )
            except Exception:
                pass

        context = {
            'cliente': cliente,
            'form': form,
            'quote_data': quote_data,
            'token': token,
            'base_code': base_code,
            'target_code': target_code,
            'operation_type': operation_type,
        }
        return render(request, self.template_name, context)


class TransactionDetailView(LoginRequiredMixin, DetailView):
    """
    Vista para visualizar los detalles y el comprobante de una transacción.
    Verifica automáticamente si la cotización ha expirado antes de renderizar.
    """
    model = Transaction
    template_name = 'transactions/transaction_detail.html'
    context_object_name = 'transaction'

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'cliente', 'base_currency', 'target_currency',
            'medio_pago_origen', 'medio_acreditacion_destino',
            'usuario'
        )
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs

        cliente = get_active_customer(self.request)
        if cliente:
            return qs.filter(cliente=cliente)
        return qs.none()

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if obj and obj.estado == Transaction.Estado.PENDIENTE:
            TransactionService.check_and_cancel_single(obj)
        return obj

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        tx = self.object
        cliente = get_active_customer(self.request)

        is_expired = TransactionService.is_transaction_expired(tx)
        remaining_seconds = 0
        if tx.estado == Transaction.Estado.PENDIENTE and tx.created_at:
            from django.utils import timezone
            elapsed = (timezone.now() - tx.created_at).total_seconds()
            remaining_seconds = max(0, int(TransactionService.EXPIRATION_DURATION_SECONDS - elapsed))

        context['is_expired'] = is_expired
        context['remaining_seconds'] = remaining_seconds
        context['can_cancel'] = (
            tx.estado == Transaction.Estado.PENDIENTE and cliente and tx.cliente_id == cliente.id
        )
        return context


class TransactionListView(LoginRequiredMixin, ListView):
    """
    Vista de listado de transacciones con filtros por estado y tipo de operación.
    """
    model = Transaction
    template_name = 'transactions/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 15

    def get_queryset(self):
        # Ejecutar limpieza/cancelación automática de órdenes expiradas al consultar el listado
        TransactionService.cancel_expired_transactions()

        qs = Transaction.objects.select_related(
            'cliente', 'base_currency', 'target_currency'
        ).order_by('-created_at')

        if not (self.request.user.is_staff or self.request.user.is_superuser):
            cliente = get_active_customer(self.request)
            if cliente:
                qs = qs.filter(cliente=cliente)
            else:
                return qs.none()

        # Filtros opcionales por GET
        estado = self.request.GET.get('estado', '').strip().upper()
        if estado in dict(Transaction.Estado.choices):
            qs = qs.filter(estado=estado)

        tipo = self.request.GET.get('tipo', '').strip().upper()
        if tipo in dict(Transaction.TipoOperacion.choices):
            qs = qs.filter(tipo_operacion=tipo)

        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        cliente = get_active_customer(self.request)

        base_qs = Transaction.objects.all()
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            if cliente:
                base_qs = base_qs.filter(cliente=cliente)
            else:
                base_qs = base_qs.none()

        context['total_count'] = base_qs.count()
        context['pending_count'] = base_qs.filter(estado=Transaction.Estado.PENDIENTE).count()
        context['completed_count'] = base_qs.filter(estado=Transaction.Estado.COMPLETADA).count()
        context['cancelled_count'] = base_qs.filter(estado=Transaction.Estado.CANCELADA).count()
        context['selected_estado'] = self.request.GET.get('estado', '')
        context['selected_tipo'] = self.request.GET.get('tipo', '')
        context['cliente'] = cliente
        return context


class TransactionCancelView(LoginRequiredMixin, View):
    """
    Vista POST para la anulación manual de una transacción pendiente por parte del cliente.
    """

    def post(self, request: HttpRequest, pk: int, *args, **kwargs) -> HttpResponse:
        cliente = get_active_customer(request)
        if not cliente:
            messages.error(request, 'No se pudo verificar el cliente activo para esta operación.')
            return redirect('transactions:list')

        motivo = request.POST.get('motivo', '').strip()

        try:
            tx = TransactionService.cancel_transaction_by_customer(
                transaction_id=pk,
                cliente=cliente,
                usuario=request.user,
                motivo=motivo,
            )
            messages.success(
                request,
                f"La transacción {tx.codigo_referencia} ha sido anulada exitosamente."
            )
            return redirect('transactions:detail', pk=tx.pk)

        except ValidationError as ve:
            for field, err_list in ve.message_dict.items() if hasattr(ve, 'message_dict') else [('__all__', ve.messages)]:
                for err in err_list:
                    messages.error(request, f"Error al cancelar la orden: {err}")
        except Exception as exc:
            logger.exception("Error inesperado al anular la transacción")
            messages.error(request, f"No se pudo cancelar la orden: {exc}")

        return redirect('transactions:detail', pk=pk)


@method_decorator(csrf_exempt, name='dispatch')
class TransactionCancelApiView(View):
    """
    Endpoint de API JSON para la anulación programática de transacciones pendientes.
    """

    def post(self, request: HttpRequest, pk: int, *args, **kwargs) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Usuario no autenticado.'}, status=401)

        cliente = get_active_customer(request)
        if not cliente:
            return JsonResponse({'success': False, 'error': 'No se encontró un cliente activo.'}, status=400)

        try:
            body_data = json.loads(request.body.decode('utf-8'))
        except Exception:
            body_data = request.POST.dict()

        motivo = body_data.get('motivo', '').strip()

        try:
            tx = TransactionService.cancel_transaction_by_customer(
                transaction_id=pk,
                cliente=cliente,
                usuario=request.user,
                motivo=motivo,
            )
            return JsonResponse({
                'success': True,
                'message': 'Transacción anulada exitosamente.',
                'transaction': {
                    'id': tx.id,
                    'codigo_referencia': tx.codigo_referencia,
                    'estado': tx.estado,
                    'observaciones': tx.observaciones,
                    'updated_at': tx.updated_at.isoformat(),
                }
            })

        except ValidationError as ve:
            errors_dict = ve.message_dict if hasattr(ve, 'message_dict') else {'detail': ve.messages}
            return JsonResponse({'success': False, 'errors': errors_dict}, status=400)
        except Exception as exc:
            logger.exception("Error en API de cancelación de transacción")
            return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TransactionCreateApiView(View):
    """
    Endpoint de API JSON para la creación programática de transacciones cambiarias.
    """

    def post(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Usuario no autenticado.'}, status=401)

        cliente = get_active_customer(request)
        if not cliente:
            return JsonResponse({'success': False, 'error': 'No se encontró un cliente activo.'}, status=400)

        try:
            body_data = json.loads(request.body.decode('utf-8'))
        except Exception:
            body_data = request.POST.dict()

        token = body_data.get('token', '').strip()
        medio_pago_id = body_data.get('medio_pago_id')
        medio_acreditacion_id = body_data.get('medio_acreditacion_id')
        observaciones = body_data.get('observaciones', '')

        if not medio_pago_id or not medio_acreditacion_id:
            return JsonResponse({
                'success': False,
                'error': 'Se requieren medio_pago_id y medio_acreditacion_id.'
            }, status=400)

        try:
            if token:
                tx = TransactionService.create_order_from_frozen_quote(
                    request=request,
                    token=token,
                    medio_pago_id=medio_pago_id,
                    medio_acreditacion_id=medio_acreditacion_id,
                    cliente=cliente,
                    usuario=request.user,
                    observaciones=observaciones,
                )
            else:
                base_code = body_data.get('base_currency_code', 'USD')
                target_code = body_data.get('target_currency_code', 'PYG')
                amount = body_data.get('amount', 100)
                op_type = body_data.get('operation_type', 'BUY')
                is_source_base = body_data.get('is_source_base', True)

                tx = TransactionService.create_order_from_live_quote(
                    request=request,
                    base_currency_code=base_code,
                    target_currency_code=target_code,
                    amount=amount,
                    operation_type=op_type,
                    is_source_base=is_source_base,
                    medio_pago_id=medio_pago_id,
                    medio_acreditacion_id=medio_acreditacion_id,
                    cliente=cliente,
                    usuario=request.user,
                    observaciones=observaciones,
                )

            return JsonResponse({
                'success': True,
                'message': 'Transacción registrada con éxito.',
                'transaction': {
                    'id': tx.id,
                    'codigo_referencia': tx.codigo_referencia,
                    'estado': tx.estado,
                    'tipo_operacion': tx.tipo_operacion,
                    'monto_origen': float(tx.monto_origen),
                    'monto_destino': float(tx.monto_destino),
                    'moneda_origen': tx.moneda_origen.code,
                    'moneda_destino': tx.moneda_destino.code,
                    'tasa_neta': float(tx.tasa_neta),
                    'created_at': tx.created_at.isoformat(),
                }
            })

        except ValidationError as ve:
            errors_dict = ve.message_dict if hasattr(ve, 'message_dict') else {'detail': ve.messages}
            return JsonResponse({'success': False, 'errors': errors_dict}, status=400)
        except Exception as exc:
            logger.exception("Error en API de transacción")
            return JsonResponse({'success': False, 'error': str(exc)}, status=500)
