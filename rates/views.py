"""
Módulo de vistas y controladores para la gestión de Monedas, Tasas de Cambio, Comisiones y Cotizaciones (rates).

Implementa:
1. **Vistas Basadas en Clases (CBVs)** para el CRUD de Monedas (:class:`~rates.models.Currency`) y Tasas de Cambio (:class:`~rates.models.ExchangeRate`).
2. **Vistas Basadas en Clases (CBVs)** para la parametrización de comisiones por segmento (:class:`~rates.models.SegmentCommission`).
3. **Simulador de Cotizaciones Interactivo**: interfaz para el cálculo de tasas netas en tiempo real.
4. **Endpoints API REST (JSON)** para consultas programáticas y consumo asíncrono desde el frontend.
"""

from datetime import timedelta
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
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from django.views.generic import TemplateView

from customers.models import Cliente
from .forms import (
    CurrencyFilterForm,
    CurrencyForm,
    ExchangeRateFilterForm,
    ExchangeRateForm,
    RateCalculatorForm,
    SegmentCommissionFilterForm,
    SegmentCommissionForm,
)
from .models import Currency, ExchangeRate, SegmentCommission
from .services import RateCalculationService, get_active_customer

logger = logging.getLogger(__name__)


# ==============================================================================
# CURRENCY VIEWS (SCRUM-51)
# ==============================================================================

class CurrencyListView(LoginRequiredMixin, ListView):
    """
    Vista de listado para el catálogo de monedas internacionales.
    """

    model = Currency
    template_name = 'rates/currency_list.html'
    context_object_name = 'currencies'
    paginate_by = 10

    def get_queryset(self) -> QuerySet[Currency]:
        queryset = Currency.objects.all().order_by('code')
        self.filter_form = CurrencyFilterForm(self.request.GET)

        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get('q')
            is_active = self.filter_form.cleaned_data.get('is_active')

            if q:
                queryset = queryset.filter(
                    Q(code__icontains=q) | Q(name__icontains=q) | Q(symbol__icontains=q)
                )

            if is_active == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active == 'false':
                queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['filter_form'] = getattr(self, 'filter_form', CurrencyFilterForm(self.request.GET))
        context['total_count'] = Currency.objects.count()
        context['active_count'] = Currency.objects.filter(is_active=True).count()
        context['inactive_count'] = Currency.objects.filter(is_active=False).count()

        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['querystring'] = query_params.urlencode()
        return context


class CurrencyCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Vista para crear una nueva moneda en el catálogo.
    """

    model = Currency
    form_class = CurrencyForm
    template_name = 'rates/currency_form.html'
    success_url = reverse_lazy('rates:currency-list')
    success_message = 'Moneda "%(code)s" creada exitosamente.'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nueva Moneda'
        context['action'] = 'Crear'
        return context


class CurrencyUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Vista para actualizar una moneda existente.
    """

    model = Currency
    form_class = CurrencyForm
    template_name = 'rates/currency_form.html'
    success_url = reverse_lazy('rates:currency-list')
    success_message = 'Moneda "%(code)s" actualizada exitosamente.'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['title'] = f'Editar Moneda: {self.object.code}'
        context['action'] = 'Actualizar'
        return context


class CurrencyToggleStatusView(LoginRequiredMixin, View):
    """
    Controlador para activar o desactivar una moneda.
    """

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        currency = get_object_or_404(Currency, pk=pk)
        currency.is_active = not currency.is_active
        currency.save()
        status = 'activada' if currency.is_active else 'desactivada'
        messages.success(request, f'Moneda "{currency.code}" {status} exitosamente.')
        next_url = request.META.get('HTTP_REFERER', reverse_lazy('rates:currency-list'))
        return redirect(next_url)


# ==============================================================================
# EXCHANGE RATE VIEWS (SCRUM-51)
# ==============================================================================

class ExchangeRateListView(LoginRequiredMixin, ListView):
    """
    Vista de listado para las cotizaciones y tasas de cambio vigentes.
    """

    model = ExchangeRate
    template_name = 'rates/exchangerate_list.html'
    context_object_name = 'rates'
    paginate_by = 15

    def get_queryset(self) -> QuerySet[ExchangeRate]:
        queryset = ExchangeRate.objects.select_related('base_currency', 'target_currency', 'updated_by').order_by('-valid_from', '-created_at')
        self.filter_form = ExchangeRateFilterForm(self.request.GET)

        if self.filter_form.is_valid():
            currency = self.filter_form.cleaned_data.get('currency')
            is_active = self.filter_form.cleaned_data.get('is_active')

            if currency:
                queryset = queryset.filter(
                    Q(base_currency=currency) | Q(target_currency=currency)
                )

            if is_active == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active == 'false':
                queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['filter_form'] = getattr(self, 'filter_form', ExchangeRateFilterForm(self.request.GET))
        context['total_count'] = ExchangeRate.objects.count()
        context['active_count'] = ExchangeRate.objects.filter(is_active=True).count()

        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['querystring'] = query_params.urlencode()
        return context


class ExchangeRateCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Vista para registrar una nueva tasa de cambio.
    """

    model = ExchangeRate
    form_class = ExchangeRateForm
    template_name = 'rates/exchangerate_form.html'
    success_url = reverse_lazy('rates:rate-list')
    success_message = 'Tasa de cambio registrada exitosamente.'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['title'] = 'Registrar Tasa de Cambio'
        context['action'] = 'Registrar'
        return context

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class ExchangeRateUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Vista para modificar una cotización existente.
    """

    model = ExchangeRate
    form_class = ExchangeRateForm
    template_name = 'rates/exchangerate_form.html'
    success_url = reverse_lazy('rates:rate-list')
    success_message = 'Tasa de cambio actualizada exitosamente.'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Tasa de Cambio'
        context['action'] = 'Actualizar'
        return context

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class ExchangeRateToggleStatusView(LoginRequiredMixin, View):
    """
    Controlador para cambiar el estado de una cotización.
    """

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        rate = get_object_or_404(ExchangeRate, pk=pk)
        rate.is_active = not rate.is_active
        rate.updated_by = request.user
        rate.save()
        status = 'activada' if rate.is_active else 'desactivada'
        messages.success(request, f'Tasa de cambio {rate.base_currency.code}/{rate.target_currency.code} {status} exitosamente.')
        next_url = request.META.get('HTTP_REFERER', reverse_lazy('rates:rate-list'))
        return redirect(next_url)


# ==============================================================================
# DASHBOARD DE COTIZACIONES HISTÓRICAS (SCRUM-52)
# ==============================================================================

class ExchangeRateDashboardView(LoginRequiredMixin, TemplateView):
    """Muestra el tablero de cotizaciones y sus indicadores operativos actuales."""

    template_name = 'rates/exchange_rate_dashboard.html'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        current_rates = ExchangeRate.objects.filter(
            is_active=True,
            valid_from__lte=now,
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now)).select_related(
            'base_currency', 'target_currency'
        ).order_by('base_currency__code', 'target_currency__code', '-valid_from', '-created_at')

        latest_quotes = []
        seen_pairs = set()
        for rate in current_rates:
            pair = (rate.base_currency_id, rate.target_currency_id)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                latest_quotes.append(rate)

        historical_pairs = ExchangeRate.objects.select_related(
            'base_currency', 'target_currency'
        ).order_by('base_currency__code', 'target_currency__code').values(
            'base_currency_id', 'base_currency__code', 'target_currency_id', 'target_currency__code'
        ).distinct()

        context.update({
            'latest_quotes': latest_quotes,
            'historical_pairs': historical_pairs,
            'active_quotes_count': len(latest_quotes),
            'currencies_count': Currency.objects.filter(is_active=True).count(),
            'updated_today_count': ExchangeRate.objects.filter(
                updated_at__date=now.date(), is_active=True
            ).count(),
            'range_options': (
                ('7d', 'Últimos 7 días'),
                ('30d', 'Últimos 30 días'),
                ('90d', 'Últimos 90 días'),
                ('1y', 'Último año'),
            ),
        })
        return context


class ExchangeRateHistoryApiView(LoginRequiredMixin, View):
    """Entrega las series históricas de compra y venta para el gráfico de cotizaciones."""

    PERIOD_DAYS = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}

    def get(self, request: HttpRequest) -> JsonResponse:
        period = request.GET.get('period', '30d')
        if period not in self.PERIOD_DAYS:
            return JsonResponse(
                {'success': False, 'error': 'El período seleccionado no es válido.'}, status=400
            )

        try:
            base_currency_id, target_currency_id = (
                int(value) for value in request.GET.get('pair', '').split(':', 1)
            )
        except (TypeError, ValueError):
            return JsonResponse(
                {'success': False, 'error': 'El par de monedas seleccionado no es válido.'}, status=400
            )

        end_date = timezone.now()
        start_date = end_date - timedelta(days=self.PERIOD_DAYS[period])
        rates = list(ExchangeRate.objects.filter(
            base_currency_id=base_currency_id,
            target_currency_id=target_currency_id,
            valid_from__gte=start_date,
            valid_from__lte=end_date,
        ).select_related('base_currency', 'target_currency').order_by('valid_from', 'created_at'))

        if not rates:
            return JsonResponse({
                'success': True, 'period': period, 'pair': None,
                'labels': [], 'buy_rates': [], 'sell_rates': [],
            })

        first_rate = rates[0]
        return JsonResponse({
            'success': True,
            'period': period,
            'pair': f'{first_rate.base_currency.code}/{first_rate.target_currency.code}',
            'labels': [rate.valid_from.strftime('%d/%m/%Y %H:%M') for rate in rates],
            'buy_rates': [float(rate.buy_rate) for rate in rates],
            'sell_rates': [float(rate.sell_rate) for rate in rates],
        })


# ==============================================================================
# VISTAS CBVs: GESTIÓN DE COMISIONES POR SEGMENTO (SCRUM-53)
# ==============================================================================

def _serialize_commission_rule(rule: SegmentCommission) -> Dict[str, Any]:
    """
    Serializa una regla de :class:`~rates.models.SegmentCommission` a un diccionario JSON estándar.
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
# VISTA CBV: COTIZADOR Y MOTOR DE CÁLCULO DE TASAS NETAS (SCRUM-53)
# ==============================================================================

class RateCalculatorView(LoginRequiredMixin, View):
    """
    Vista interactiva para el cálculo y simulación de cotizaciones con tasas netas.
    """

    template_name = 'rates/rate_calculator.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        active_customer = get_active_customer(request)
        initial_data = {
            'amount': Decimal('100.00'),
            'operation_type': 'BUY',
            'is_source_base': True,
        }

        rate_id = request.GET.get('exchange_rate')
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
