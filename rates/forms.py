"""
Módulo de formularios para la parametrización de monedas, tasas de cambio, comisiones y cotizaciones (rates).

Define:
1. :class:`CurrencyForm`: Formulario para la gestión de Monedas (:class:`~rates.models.Currency`).
2. :class:`ExchangeRateForm`: Formulario para registro y actualización de Cotizaciones (:class:`~rates.models.ExchangeRate`).
3. :class:`CurrencyFilterForm`: Filtrado interactivo de divisas.
4. :class:`ExchangeRateFilterForm`: Filtrado interactivo de tasas de cambio.
5. :class:`SegmentCommissionForm`: Formulario para la creación y edición de reglas de comisión por segmento (:class:`~rates.models.SegmentCommission`).
6. :class:`SegmentCommissionFilterForm`: Filtrado interactivo de reglas de comisión.
7. :class:`RateCalculatorForm`: Formulario para el simulador y motor de cotizaciones netas.
8. :class:`RateAlertSubscriptionForm`: Alta y edición de suscripciones de alerta de cotización.
"""

from decimal import Decimal
from typing import Any, Dict

from django import forms
from django.core.exceptions import ValidationError

from customers.models import Cliente
from .models import Currency, ExchangeRate, OperationLimit, RateAlertSubscription, SegmentCommission

from django.db.models import Q


# ==============================================================================
# FORMULARIOS PARA MONEDAS Y TASAS DE CAMBIO (SCRUM-51)
# ==============================================================================

class CurrencyForm(forms.ModelForm):
    """
    Formulario para la creación y actualización de monedas internacionales.
    """

    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol', 'decimals', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej. USD, EUR, PYG'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej. Dólar Estadounidense'}),
            'symbol': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej. $, €'}),
            'decimals': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 4}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'code': 'Código ISO 4217',
            'name': 'Nombre de la Moneda',
            'symbol': 'Símbolo',
            'decimals': 'Decimales',
            'is_active': 'Activa',
        }


class ExchangeRateForm(forms.ModelForm):
    """
    Formulario para el registro y actualización de cotizaciones oficiales.
    """

    class Meta:
        model = ExchangeRate
        fields = ['base_currency', 'target_currency', 'buy_rate', 'sell_rate', 'valid_to', 'is_active']
        widgets = {
            'base_currency': forms.Select(attrs={'class': 'form-select'}),
            'target_currency': forms.Select(attrs={'class': 'form-select'}),
            'buy_rate': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.000001', 'min': 0}),
            'sell_rate': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.000001', 'min': 0}),
            'valid_to': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'base_currency': 'Moneda Base (Origen)',
            'target_currency': 'Moneda Destino (Cotizada)',
            'buy_rate': 'Tasa de Compra',
            'sell_rate': 'Tasa de Venta',
            'valid_to': 'Vigente Hasta (Opcional)',
            'is_active': 'Activa',
        }


class CurrencyFilterForm(forms.Form):
    """
    Formulario de filtrado para el catálogo de monedas.
    """

    q = forms.CharField(
        required=False,
        label='Búsqueda',
        widget=forms.TextInput(attrs={'class': 'filter-input', 'placeholder': 'Buscar por código, nombre...'}),
    )
    is_active = forms.ChoiceField(
        required=False,
        label='Estado',
        choices=[('', 'Todos'), ('true', 'Activas'), ('false', 'Inactivas')],
        widget=forms.Select(attrs={'class': 'filter-select'}),
    )


class ExchangeRateFilterForm(forms.Form):
    """
    Formulario de filtrado para el listado de tasas de cambio.
    """

    currency = forms.ModelChoiceField(
        queryset=Currency.objects.all(),
        required=False,
        label='Moneda',
        empty_label='Todas las monedas',
        widget=forms.Select(attrs={'class': 'filter-select'}),
    )
    is_active = forms.ChoiceField(
        required=False,
        label='Estado',
        choices=[('', 'Todos'), ('true', 'Activas'), ('false', 'Inactivas')],
        widget=forms.Select(attrs={'class': 'filter-select'}),
    )


# ==============================================================================
# FORMULARIOS PARA COMISIONES Y COTIZADOR NETO (SCRUM-53)
# ==============================================================================

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


# ==============================================================================
# FORMULARIOS PARA LÍMITES OPERATIVOS (SCRUM-77)
# ==============================================================================

class OperationLimitForm(forms.ModelForm):
    """
    Formulario para la creación y edición de reglas de límites operativos por divisa y segmento.
    """

    class Meta:
        model = OperationLimit
        fields = [
            'segment',
            'currency',
            'monto_minimo',
            'monto_maximo',
            'limite_diario',
            'limite_mensual',
            'is_active',
        ]
        widgets = {
            'segment': forms.Select(attrs={'class': 'form-select', 'id': 'id_segment'}),
            'currency': forms.Select(attrs={'class': 'form-select', 'id': 'id_currency'}),
            'monto_minimo': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'id': 'id_monto_minimo',
                    'step': '0.01',
                    'min': '0.00',
                    'placeholder': 'Ej: 10.00',
                }
            ),
            'monto_maximo': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'id': 'id_monto_maximo',
                    'step': '0.01',
                    'min': '0.00',
                    'placeholder': 'Ej: 5000.00 (0 = sin máx)',
                }
            ),
            'limite_diario': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'id': 'id_limite_diario',
                    'step': '0.01',
                    'min': '0.00',
                    'placeholder': 'Ej: 10000.00 (0 = sin límite)',
                }
            ),
            'limite_mensual': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'id': 'id_limite_mensual',
                    'step': '0.01',
                    'min': '0.00',
                    'placeholder': 'Ej: 50000.00 (0 = sin límite)',
                }
            ),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'id_is_active'}),
        }
        labels = {
            'segment': 'Segmento de Cliente',
            'currency': 'Moneda',
            'monto_minimo': 'Monto Mínimo por Operación',
            'monto_maximo': 'Monto Máximo por Operación',
            'limite_diario': 'Límite Acumulado Diario',
            'limite_mensual': 'Límite Acumulado Mensual',
            'is_active': 'Regla Activa y Vigente',
        }
        help_texts = {
            'segment': 'Categoría comercial del cliente a la cual se aplican estos límites.',
            'currency': 'Divisa en la cual se fijan los montos parametrizados.',
            'monto_minimo': 'Monto mínimo requerido para poder emitir una cotización u orden.',
            'monto_maximo': 'Monto máximo individual por transacción (0.00 para permitir sin tope individual).',
            'limite_diario': 'Monto acumulado máximo permitido en 24 horas (0.00 para sin límite diario).',
            'limite_mensual': 'Monto acumulado máximo permitido en el mes calendario (0.00 para sin límite mensual).',
            'is_active': 'Desmarcar para deshabilitar temporalmente esta política de control de riesgos.',
        }


class OperationLimitFilterForm(forms.Form):
    """
    Formulario de filtrado para el listado de límites operativos.
    """

    segment = forms.ChoiceField(
        choices=[('', 'Todos los Segmentos')] + list(Cliente.Segmentacion.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'filter-select', 'id': 'filter_segment'}),
        label='Segmento',
    )
    currency = forms.ModelChoiceField(
        queryset=Currency.objects.all(),
        required=False,
        label='Moneda',
        empty_label='Todas las monedas',
        widget=forms.Select(attrs={'class': 'filter-select', 'id': 'filter_currency'}),
    )
    is_active = forms.ChoiceField(
        choices=[('', 'Todos los Estados'), ('true', 'Sólo Activos'), ('false', 'Inactivos')],
        required=False,
        widget=forms.Select(attrs={'class': 'filter-select', 'id': 'filter_is_active'}),
        label='Estado',
    )

# ==============================================================================
# FORMULARIOS PARA ALERTAS DE COTIZACIÓN (SCRUM-100)
# ==============================================================================

class RateAlertSubscriptionForm(forms.ModelForm):
    """
    Formulario para crear y editar suscripciones de alerta de cotización.

    El cliente no es un campo del formulario: la vista lo asigna a partir del
    cliente activo en sesión. Solo ofrece monedas activas, salvo las que ya
    usa la suscripción que se está editando.
    """

    class Meta:
        model = RateAlertSubscription
        fields = ['base_currency', 'target_currency', 'tipo_operacion', 'condicion', 'tasa_umbral', 'activo']
        widgets = {
            'base_currency': forms.Select(attrs={'class': 'form-select'}),
            'target_currency': forms.Select(attrs={'class': 'form-select'}),
            'tipo_operacion': forms.Select(attrs={'class': 'form-select'}),
            'condicion': forms.Select(attrs={'class': 'form-select'}),
            'tasa_umbral': forms.NumberInput(
                attrs={'class': 'form-input', 'step': 'any', 'min': '0', 'placeholder': 'Ej. 7500'}
            ),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'base_currency': 'Moneda Base',
            'target_currency': 'Moneda Destino',
            'tipo_operacion': 'Tipo de Operación',
            'condicion': 'Condición',
            'tasa_umbral': 'Tasa Umbral',
            'activo': 'Alerta activa',
        }
        help_texts = {
            'base_currency': 'Ej. USD en el par USD/PYG.',
            'target_currency': 'Ej. PYG en el par USD/PYG.',
            'tipo_operacion': 'Compra: usted compra la divisa base. Venta: usted la vende.',
            'condicion': 'Cuándo debe avisarle el sistema respecto del umbral.',
            'tasa_umbral': 'Valor de la tasa que activa el aviso.',
            'activo': '',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        monedas = Currency.objects.filter(is_active=True)
        if self.instance.pk:
            monedas = Currency.objects.filter(
                Q(is_active=True) | Q(pk__in=[self.instance.base_currency_id, self.instance.target_currency_id])
            )
            if self.instance.tasa_umbral is not None:
                # Quita los ceros sobrantes del valor guardado (7000.000000 -> 7000) sin redondearlo.
                self.initial['tasa_umbral'] = f'{self.instance.tasa_umbral.normalize():f}'
        monedas = monedas.order_by('code')
        self.fields['base_currency'].queryset = monedas
        self.fields['target_currency'].queryset = monedas

    def currency_decimals(self) -> Dict[int, int]:
        """
        Devuelve la cantidad de decimales de cada moneda, indexada por su id.

        La plantilla lo usa para ajustar el paso de las flechas del campo de
        umbral según la moneda destino elegida. Se limita a 6, que es la
        precisión máxima con la que se guardan las tasas.

        :return: Diccionario ``{id_moneda: decimales}``.
        :rtype: dict
        """
        return {moneda.pk: min(moneda.decimals, 6) for moneda in Currency.objects.all()}