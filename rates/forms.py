"""
Módulo de formularios para la parametrización de comisiones y simulación de cotizaciones (rates).

Define:
1. :class:`SegmentCommissionForm`: Formulario basado en modelo para la creación y edición de reglas
   tarifarias y bonificaciones por segmento (:class:`~rates.models.SegmentCommission`).
2. :class:`SegmentCommissionFilterForm`: Formulario de filtrado interactivo para el catálogo de comisiones.
3. :class:`RateCalculatorForm`: Formulario para el motor de cálculo y simulador de tasas netas.
"""

from decimal import Decimal
from typing import Any, Dict

from django import forms
from django.core.exceptions import ValidationError

from customers.models import Cliente
from .models import Currency, ExchangeRate, SegmentCommission


class SegmentCommissionForm(forms.ModelForm):
    """
    Formulario para la creación y edición de reglas de comisión por segmento.

    Incluye widgets con estilos corporativos y validaciones de rango
    (porcentajes entre 0.00% y 100.00%, cargos fijos no negativos).
    """

    class Meta:
        model = SegmentCommission
        fields = [
            'segment',
            'commission_percentage',
            'fixed_fee',
            'spread_discount_percentage',
            'is_active',
        ]
        widgets = {
            'segment': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_segment',
                }
            ),
            'commission_percentage': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'id': 'id_commission_percentage',
                    'step': '0.01',
                    'min': '0.00',
                    'max': '100.00',
                    'placeholder': 'Ej: 1.50',
                }
            ),
            'fixed_fee': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'id': 'id_fixed_fee',
                    'step': '0.01',
                    'min': '0.00',
                    'placeholder': 'Ej: 5000.00',
                }
            ),
            'spread_discount_percentage': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'id': 'id_spread_discount_percentage',
                    'step': '0.01',
                    'min': '0.00',
                    'max': '100.00',
                    'placeholder': 'Ej: 20.00',
                }
            ),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-checkbox',
                    'id': 'id_is_active',
                }
            ),
        }
        labels = {
            'segment': 'Segmento de Cliente',
            'commission_percentage': 'Comisión Porcentual (%)',
            'fixed_fee': 'Cargo Fijo Administrativo',
            'spread_discount_percentage': 'Bonificación sobre Spread (%)',
            'is_active': 'Regla Activa y Vigente',
        }
        help_texts = {
            'segment': 'Seleccione la categoría comercial de cliente a la que aplicará esta regla tarifaria.',
            'commission_percentage': 'Porcentaje cobrado sobre el valor bruto total de la operación (0.00% a 100.00%).',
            'fixed_fee': 'Monto fijo cobrado por transacción en moneda local (>= 0.00).',
            'spread_discount_percentage': 'Porcentaje de reducción del spread aplicado a favor del cliente (0.00% a 100.00%).',
            'is_active': 'Desmarcar para suspender la aplicación de esta regla tarifaria sin eliminarla.',
        }

    def clean_commission_percentage(self) -> Decimal:
        val = self.cleaned_data.get('commission_percentage')
        if val is not None:
            if val < Decimal('0.00') or val > Decimal('100.00'):
                raise ValidationError('La comisión porcentual debe estar comprendida entre 0.00% y 100.00%.')
        return val

    def clean_fixed_fee(self) -> Decimal:
        val = self.cleaned_data.get('fixed_fee')
        if val is not None and val < Decimal('0.00'):
            raise ValidationError('El cargo fijo administrativo no puede ser un valor negativo.')
        return val

    def clean_spread_discount_percentage(self) -> Decimal:
        val = self.cleaned_data.get('spread_discount_percentage')
        if val is not None:
            if val < Decimal('0.00') or val > Decimal('100.00'):
                raise ValidationError('El descuento sobre el spread debe estar comprendido entre 0.00% y 100.00%.')
        return val


class SegmentCommissionFilterForm(forms.Form):
    """
    Formulario de filtrado para la grilla administrativa de comisiones por segmento.
    """

    segment = forms.ChoiceField(
        choices=[('', 'Todos los Segmentos')] + list(Cliente.Segmentacion.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'filter-select', 'id': 'filter_segment'}),
        label='Segmento',
    )
    is_active = forms.ChoiceField(
        choices=[('', 'Todos los Estados'), ('true', 'Sólo Activos'), ('false', 'Inactivos')],
        required=False,
        widget=forms.Select(attrs={'class': 'filter-select', 'id': 'filter_is_active'}),
        label='Estado',
    )


class RateCalculatorForm(forms.Form):
    """
    Formulario interactivo para la simulación y cotización de tasas netas en tiempo real.
    """

    OPERATION_CHOICES = [
        ('BUY', 'Compra de Divisas (Cliente entrega moneda local)'),
        ('SELL', 'Venta de Divisas (Cliente entrega moneda extranjera)'),
    ]

    exchange_rate = forms.ModelChoiceField(
        queryset=ExchangeRate.objects.filter(is_active=True).select_related('base_currency', 'target_currency'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'calc_exchange_rate'}),
        label='Par de Divisas y Cotización',
        help_text='Seleccione la cotización vigente para la operación.',
    )
    operation_type = forms.ChoiceField(
        choices=OPERATION_CHOICES,
        initial='BUY',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'calc_operation_type'}),
        label='Tipo de Operación',
    )
    amount = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        min_value=Decimal('0.01'),
        initial=Decimal('100.00'),
        required=True,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-input',
                'id': 'calc_amount',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '100.00',
            }
        ),
        label='Monto de la Operación',
        help_text='Ingrese el volumen de dinero a cotizar.',
    )
    segment = forms.ChoiceField(
        choices=[('', '— Usar Segmento del Cliente Activo —')] + list(Cliente.Segmentacion.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'calc_segment'}),
        label='Segmento Específico (Opcional)',
        help_text='Permite forzar un segmento comercial para comparar condiciones tarifarias.',
    )
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(is_active=True).order_by('nombre'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'calc_cliente'}),
        label='Cliente de Referencia (Opcional)',
        help_text='Seleccione un cliente para heredar automáticamente su segmento.',
    )
    is_source_base = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'calc_is_source_base'}),
        label='El monto ingresado corresponde a la Moneda Base (ej: USD)',
    )
