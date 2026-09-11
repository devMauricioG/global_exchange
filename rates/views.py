"""
Módulo de vistas y controladores para la parametrización de comisiones y motor de cálculo de tasas netas (rates).

Implementa:
1. **Vistas Basadas en Clases (CBVs)** para la gestión y administración de comisiones por segmento
   (:class:`~rates.models.SegmentCommission`): listado, alta, edición, eliminación y detalle analítico.
2. **Simulador de Cotizaciones Interactivo**: interfaz para el cálculo de tasas netas en tiempo real.
3. **Endpoints API REST (JSON)** para consultas programáticas y consumo asíncrono desde el frontend.
"""

from decimal import Decimal
import json
import logging
from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from customers.models import Cliente
from .forms import (
    RateCalculatorForm,
    SegmentCommissionFilterForm,
    SegmentCommissionForm,
)
from .models import Currency, ExchangeRate, SegmentCommission
from .services import RateCalculationService, get_active_customer

logger = logging.getLogger(__name__)


def _serialize_commission_rule(rule: SegmentCommission) -> Dict[str, Any]:
    """
    Serializa una regla de :class:`~rates.models.SegmentCommission` a un diccionario JSON estándar.

    :param rule: Instancia de la regla de comisión.
    :type rule: rates.models.SegmentCommission
    :return: Diccionario con los parámetros de la regla.
    :rtype: dict
    """
    return {
        'id': rule.id,
        'segment': rule.segment,
        'segment_display': rule.get_segment_display(),
        'commission_percentage': float(rule.commission_percentage),
        'fixed_fee': float(rule.fixed_fee),
        'spread_discount_percentage': float(rule.spread_discount_percentage),
        'is_active': rule.is_active,
        'created_at': rule.created_at.isoformat() if rule.created_at else None,
        'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
    }


# ==============================================================================
# VISTAS CBVs: GESTIÓN DE COMISIONES POR SEGMENTO
# ==============================================================================

class SegmentCommissionListView(LoginRequiredMixin, ListView):
    """
    Vista de listado administrativo para las reglas de comisión por segmento de cliente.
    """

    model = SegmentCommission
    template_name = 'rates/commission_list.html'
    context_object_name = 'commissions'
    ordering = ['segment']

    def get_queryset(self) -> QuerySet[SegmentCommission]:
        qs = super().get_queryset()
        segment = self.request.GET.get('segment')
        is_active = self.request.GET.get('is_active')

        if segment:
            qs = qs.filter(segment=segment)
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        all_rules = SegmentCommission.objects.all()

        # Métricas de resumen para tarjetas informativas
        context['total_rules'] = all_rules.count()
        context['active_rules'] = all_rules.filter(is_active=True).count()
        context['avg_commission'] = all_rules.filter(is_active=True).aggregate(
            avg=Avg('commission_percentage')
        )['avg'] or Decimal('0.00')
        context['avg_spread_discount'] = all_rules.filter(is_active=True).aggregate(
            avg=Avg('spread_discount_percentage')
        )['avg'] or Decimal('0.00')

        context['filter_form'] = SegmentCommissionFilterForm(self.request.GET or None)
        context['active_customer'] = get_active_customer(self.request)
        context['available_segments_count'] = len(Cliente.Segmentacion.choices)
        return context


class SegmentCommissionCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Vista para parametrizar una nueva regla tarifaria por segmento.
    """

    model = SegmentCommission
    form_class = SegmentCommissionForm
    template_name = 'rates/commission_form.html'
    success_url = reverse_lazy('rates:commission_list')
    success_message = 'Regla de comisión para el segmento %(segment)s configurada exitosamente.'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Nueva Regla de Comisión por Segmento'
        context['submit_btn_text'] = 'Guardar Parámetros'
        return context


class SegmentCommissionUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Vista para modificar una regla de comisión existente.
    """

    model = SegmentCommission
    form_class = SegmentCommissionForm
    template_name = 'rates/commission_form.html'
    success_url = reverse_lazy('rates:commission_list')
    success_message = 'Regla de comisión para %(segment)s actualizada satisfactoriamente.'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Editar Comisión — {self.object.get_segment_display()}'
        context['submit_btn_text'] = 'Actualizar Parámetros'
        return context


class SegmentCommissionDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    """
    Vista de confirmación para dar de baja o eliminar una regla tarifaria.
    """

    model = SegmentCommission
    template_name = 'rates/commission_confirm_delete.html'
    success_url = reverse_lazy('rates:commission_list')
    context_object_name = 'commission'

    def delete(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        obj = self.get_object()
        segment_name = obj.get_segment_display()
        messages.success(request, f'La regla de comisión para {segment_name} fue eliminada correctamente.')
        return super().delete(request, *args, **kwargs)


class SegmentCommissionDetailView(LoginRequiredMixin, DetailView):
    """
    Vista analítica de detalle para una regla de comisión con simulaciones de impacto financiero.
    """

    model = SegmentCommission
    template_name = 'rates/commission_detail.html'
    context_object_name = 'commission'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        rule = self.object

        # Simulador de tarifas para montos de muestra
        sample_amounts = [
            Decimal('100.00'),
            Decimal('500.00'),
            Decimal('1000.00'),
            Decimal('5000.00'),
            Decimal('10000.00'),
            Decimal('50000.00'),
        ]

        simulations = []
        for amt in sample_amounts:
            comm = rule.calculate_commission(amt)
            effective_pct = (comm / amt * Decimal('100.00')).quantize(Decimal('0.01')) if amt > 0 else Decimal('0.00')
            simulations.append({
                'amount': amt,
                'commission_total': comm,
                'effective_percentage': effective_pct,
            })

        context['simulations'] = simulations
        context['latest_rates'] = ExchangeRate.objects.filter(is_active=True).select_related(
            'base_currency', 'target_currency'
        )[:5]
        return context


# ==============================================================================
# VISTA CBV: COTIZADOR Y MOTOR DE CÁLCULO DE TASAS NETAS
# ==============================================================================

class RateCalculatorView(LoginRequiredMixin, View):
    """
    Vista interactiva para el cálculo y simulación de cotizaciones con tasas netas.

    Procesa la solicitud tanto vía GET como vía POST y presenta el desglose
    completo de tarifas, spreads bonificados, comisiones y montos netos a liquidar.
    """

    template_name = 'rates/rate_calculator.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        active_customer = get_active_customer(request)
        initial_data = {
            'amount': Decimal('100.00'),
            'operation_type': 'BUY',
            'is_source_base': True,
        }

        # Si hay parámetros en query string (ej: ?exchange_rate=1&amount=500), intentar calcular
        rate_id = request.GET.get('exchange_rate')
        amount_val = request.GET.get('amount')
        op_type = request.GET.get('operation_type', 'BUY')
        segment_val = request.GET.get('segment')

        calculation_result = None
        form = RateCalculatorForm(request.GET or None, initial=initial_data)

        if rate_id and form.is_valid():
            rate_obj = form.cleaned_data['exchange_rate']
            amt = form.cleaned_data['amount']
            op = form.cleaned_data['operation_type']
            selected_segment = form.cleaned_data.get('segment') or (active_customer.segmentacion if active_customer else None)
            is_base = form.cleaned_data.get('is_source_base', True)

            try:
                calculation_result = RateCalculationService.calculate_quotation(
                    exchange_rate=rate_obj,
                    segment_or_customer=selected_segment,
                    amount=amt,
                    operation_type=op,
                    is_source_base=is_base,
                )
            except ValidationError as err:
                messages.error(request, f'Error en el cálculo: {err.message_dict if hasattr(err, "message_dict") else err}')

        # Obtener cotizaciones activas para la barra lateral
        active_rates = ExchangeRate.objects.filter(is_active=True).select_related('base_currency', 'target_currency')

        context = {
            'form': form,
            'calculation': calculation_result,
            'active_customer': active_customer,
            'active_rates': active_rates,
            'commission_rules': SegmentCommission.objects.filter(is_active=True),
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        active_customer = get_active_customer(request)
        form = RateCalculatorForm(request.POST)
        calculation_result = None

        if form.is_valid():
            rate_obj = form.cleaned_data['exchange_rate']
            amt = form.cleaned_data['amount']
            op = form.cleaned_data['operation_type']
            selected_segment = (
                form.cleaned_data.get('segment')
                or (form.cleaned_data.get('cliente').segmentacion if form.cleaned_data.get('cliente') else None)
                or (active_customer.segmentacion if active_customer else None)
            )
            is_base = form.cleaned_data.get('is_source_base', True)

            try:
                calculation_result = RateCalculationService.calculate_quotation(
                    exchange_rate=rate_obj,
                    segment_or_customer=selected_segment,
                    amount=amt,
                    operation_type=op,
                    is_source_base=is_base,
                )
            except ValidationError as err:
                msg = err.message_dict if hasattr(err, 'message_dict') else str(err)
                messages.error(request, f'Error en la liquidación de cotización: {msg}')
        else:
            messages.warning(request, 'Por favor revise los datos ingresados en el cotizador.')

        active_rates = ExchangeRate.objects.filter(is_active=True).select_related('base_currency', 'target_currency')

        context = {
            'form': form,
            'calculation': calculation_result,
            'active_customer': active_customer,
            'active_rates': active_rates,
            'commission_rules': SegmentCommission.objects.filter(is_active=True),
        }
        return render(request, self.template_name, context)


# ==============================================================================
# ENDPOINTS API REST (JSON)
# ==============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class CalculateNetRateApiView(View):
    """
    Endpoint API REST para el cálculo y simulación de cotizaciones netas con formato JSON.

    Admite solicitudes GET y POST con soporte de payloads JSON y parámetros query string.
    """

    def _extract_params(self, request: HttpRequest) -> Dict[str, Any]:
        params = {}
        if request.method == 'POST':
            if request.content_type == 'application/json' and request.body:
                try:
                    params = json.loads(request.body.decode('utf-8'))
                except json.JSONDecodeError:
                    pass
            if not params:
                params = request.POST.dict()
        else:
            params = request.GET.dict()
        return params

    def get(self, request: HttpRequest) -> JsonResponse:
        return self._process_calculation(request)

    def post(self, request: HttpRequest) -> JsonResponse:
        return self._process_calculation(request)

    def _process_calculation(self, request: HttpRequest) -> JsonResponse:
        params = self._extract_params(request)

        # 1. Resolver cotización
        rate_id = params.get('exchange_rate_id') or params.get('exchange_rate')
        base_code = params.get('base_currency')
        target_code = params.get('target_currency')

        exchange_rate = None
        if rate_id:
            try:
                exchange_rate = ExchangeRate.objects.filter(id=rate_id, is_active=True).select_related(
                    'base_currency', 'target_currency'
                ).first()
            except (ValueError, TypeError):
                pass

        if not exchange_rate and base_code and target_code:
            exchange_rate = RateCalculationService.get_latest_exchange_rate(base_code, target_code)

        if not exchange_rate:
            return JsonResponse(
                {
                    'success': False,
                    'error': 'No se encontró una cotización activa para los parámetros especificados.',
                },
                status=404,
            )

        # 2. Resolver cliente o segmento
        active_customer = get_active_customer(request)
        cliente_id = params.get('cliente_id')
        segment = params.get('segment')

        segment_target = segment
        if not segment_target and cliente_id:
            c = Cliente.objects.filter(id=cliente_id, is_active=True).first()
            if c:
                segment_target = c.segmentacion

        if not segment_target and active_customer:
            segment_target = active_customer.segmentacion

        # 3. Monto y tipo de operación
        amount_raw = params.get('amount', '100.00')
        op_type = str(params.get('operation_type', 'BUY')).upper()
        is_source_base = str(params.get('is_source_base', 'true')).lower() in ('true', '1', 'yes')

        try:
            result = RateCalculationService.calculate_quotation(
                exchange_rate=exchange_rate,
                segment_or_customer=segment_target,
                amount=amount_raw,
                operation_type=op_type,
                is_source_base=is_source_base,
            )
            # Convertir Decimals a floats para serialización JSON estándar
            json_friendly = json.loads(json.dumps(result, default=float))
            return JsonResponse(json_friendly, status=200)

        except ValidationError as val_err:
            return JsonResponse(
                {
                    'success': False,
                    'error': val_err.message_dict if hasattr(val_err, 'message_dict') else str(val_err),
                },
                status=400,
            )
        except Exception as exc:
            logger.exception("Error inesperado en endpoint CalculateNetRateApiView: %s", exc)
            return JsonResponse(
                {
                    'success': False,
                    'error': f'Error interno en el cálculo financiero: {str(exc)}',
                },
                status=500,
            )


class SegmentCommissionListApiView(View):
    """
    Endpoint API REST para listar y consultar reglas de comisión por segmento.
    """

    def get(self, request: HttpRequest) -> JsonResponse:
        rules = SegmentCommission.objects.all().order_by('segment')
        data = [_serialize_commission_rule(r) for r in rules]
        return JsonResponse({'success': True, 'count': len(data), 'results': data}, status=200)


class SegmentCommissionDetailApiView(View):
    """
    Endpoint API REST para consultar una regla de comisión específica por segmento.
    """

    def get(self, request: HttpRequest, segment: str) -> JsonResponse:
        seg_code = str(segment).upper().strip()
        rule = SegmentCommission.objects.filter(segment=seg_code).first()
        if not rule:
            return JsonResponse(
                {'success': False, 'error': f'No existe regla de comisión para el segmento {seg_code}.'},
                status=404,
            )
        return JsonResponse({'success': True, 'rule': _serialize_commission_rule(rule)}, status=200)
