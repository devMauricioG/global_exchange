from typing import Any, Dict
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import (
    CurrencyFilterForm,
    CurrencyForm,
    ExchangeRateFilterForm,
    ExchangeRateForm,
)
from .models import Currency, ExchangeRate


# ==============================================================================
# CURRENCY VIEWS
# ==============================================================================

class CurrencyListView(LoginRequiredMixin, ListView):
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
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        currency = get_object_or_404(Currency, pk=pk)
        currency.is_active = not currency.is_active
        currency.save()
        status = 'activada' if currency.is_active else 'desactivada'
        messages.success(request, f'Moneda "{currency.code}" {status} exitosamente.')
        next_url = request.META.get('HTTP_REFERER', reverse_lazy('rates:currency-list'))
        return redirect(next_url)


# ==============================================================================
# EXCHANGE RATE VIEWS
# ==============================================================================

class ExchangeRateListView(LoginRequiredMixin, ListView):
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
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        rate = get_object_or_404(ExchangeRate, pk=pk)
        rate.is_active = not rate.is_active
        rate.updated_by = request.user
        rate.save()
        status = 'activada' if rate.is_active else 'desactivada'
        messages.success(request, f'Tasa de cambio {rate.base_currency.code}/{rate.target_currency.code} {status} exitosamente.')
        next_url = request.META.get('HTTP_REFERER', reverse_lazy('rates:rate-list'))
        return redirect(next_url)
