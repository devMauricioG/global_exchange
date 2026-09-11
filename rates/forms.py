from django import forms
from .models import Currency, ExchangeRate

class CurrencyForm(forms.ModelForm):
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
    q = forms.CharField(
        required=False,
        label='Búsqueda',
        widget=forms.TextInput(attrs={'class': 'filter-input', 'placeholder': 'Buscar por código, nombre...'})
    )
    is_active = forms.ChoiceField(
        required=False,
        label='Estado',
        choices=[('', 'Todos'), ('true', 'Activas'), ('false', 'Inactivas')],
        widget=forms.Select(attrs={'class': 'filter-select'})
    )

class ExchangeRateFilterForm(forms.Form):
    currency = forms.ModelChoiceField(
        queryset=Currency.objects.all(),
        required=False,
        label='Moneda',
        empty_label='Todas las monedas',
        widget=forms.Select(attrs={'class': 'filter-select'})
    )
    is_active = forms.ChoiceField(
        required=False,
        label='Estado',
        choices=[('', 'Todos'), ('true', 'Activas'), ('false', 'Inactivas')],
        widget=forms.Select(attrs={'class': 'filter-select'})
    )
