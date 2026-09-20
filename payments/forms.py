"""
Módulo de formularios para la aplicación de medios de pago (payments).

Provee los formularios de captura y edición de instancias :class:`~payments.models.PaymentMethod`
así como formularios de filtrado y búsqueda para la interfaz de usuario.
"""

import re
from datetime import date
from typing import Optional
from django import forms
from .models import PaymentMethod, EntidadFinanciera


class PaymentMethodForm(forms.ModelForm):
    """
    Formulario basado en modelo para crear y editar medios de pago de un cliente.

    Aplica clases CSS conformes al diseño de Global Exchange (`form-input`, `form-select`, `form-checkbox`)
    y añade validaciones de campos requeridos.
    """

    class Meta:
        model = PaymentMethod
        fields = [
        'tipo_medio',
        'entidad_bancaria',
        'numero_cuenta',
        'titular',
        'documento_titular',
        'tarjeta_ultimos_digitos',
        'tarjeta_mes_vencimiento',
        'tarjeta_anio_vencimiento',
        'tipo_cuenta_bancaria',
        'telefono_billetera',
        'es_predeterminado',
        'activo',
        ]
        widgets = {
            'tipo_medio': forms.Select(
                attrs={
                    'class': 'form-select',
                }
            ),
            'entidad_bancaria': forms.Select(
                attrs={
                    'class': 'form-select',
                }
            ),
            'numero_cuenta': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'Ej. 12-345678-9 o +595 981 123456',
                    'required': True,
                }
            ),
            'titular': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'Ej. Juan Pérez o Razón Social',
                    'required': True,
                }
            ),
            'documento_titular': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'Ej. 4.567.890 o 80012345-6 (opcional)',
                }
            ),
            'es_predeterminado': forms.CheckboxInput(
                attrs={
                    'class': 'form-checkbox',
                }
            ),
            'activo': forms.CheckboxInput(
                attrs={
                    'class': 'form-checkbox',
                }
            ),
            'tarjeta_ultimos_digitos': forms.TextInput(
                attrs={
                    'class': 'form-input'}),
            'tarjeta_mes_vencimiento': forms.NumberInput(
                attrs={
                    'class': 'form-input'}),
            'tarjeta_anio_vencimiento': forms.NumberInput(
                attrs={
                    'class': 'form-input'}),
            'tipo_cuenta_bancaria': forms.Select(
                attrs={
                    'class': 'form-select'}),
            'telefono_billetera': forms.TextInput(
                attrs={
                    'class': 'form-input'}),
        }
        labels = {
            'tipo_medio': 'Tipo de Medio de Pago',
            'entidad_bancaria': 'Entidad Bancaria o Billetera',
            'numero_cuenta': 'Número de Cuenta o Teléfono',
            'titular': 'Nombre del Titular',
            'documento_titular': 'Documento / RUC del Titular (Opcional)',
            'es_predeterminado': 'Marcar como Predeterminado para transacciones',
            'activo': 'Medio de pago activo para operar',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['entidad_bancaria'].queryset = EntidadFinanciera.objects.filter(activo=True)

    def clean(self):
        cleaned_data = super().clean()
        es_predeterminado = cleaned_data.get('es_predeterminado')
        activo = cleaned_data.get('activo')
        if es_predeterminado and not activo:
            self.add_error('es_predeterminado', 'Un medio de pago inactivo no puede configurarse como predeterminado.')
        return cleaned_data


class PaymentMethodFilterForm(forms.Form):
    """
    Formulario para el filtrado dinámico del listado de medios de pago.
    """

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-input',
                'placeholder': 'Buscar por banco, cuenta o titular...',
            }
        ),
    )
    tipo_medio = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los tipos')] + PaymentMethod.TipoMedio.choices,
        widget=forms.Select(
            attrs={
                'class': 'form-select',
            }
        ),
    )
    activo = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Todos los estados'),
            ('true', 'Activos'),
            ('false', 'Inactivos'),
        ],
        widget=forms.Select(
            attrs={
                'class': 'form-select',
            }
        ),
    )

def _luhn_valido(numero: str) -> bool:
    """
    Valida un número de tarjeta mediante el algoritmo de Luhn.

    :param numero: Cadena de dígitos del número de tarjeta (sin espacios ni guiones).
    :return: True si el checksum de Luhn es válido.
    :rtype: bool
    """
    digitos = [int(d) for d in numero]
    for i in range(len(digitos) - 2, -1, -2):
        digitos[i] *= 2
        if digitos[i] > 9:
            digitos[i] -= 9
    return sum(digitos) % 10 == 0


class CreditDebitCardForm(forms.ModelForm):
    """
    Formulario especializado para medios de pago tipo Tarjeta de Crédito/Débito.

    Valida el número completo de tarjeta mediante el algoritmo de Luhn
    (sin persistirlo — solo se guardan los últimos 4 dígitos), la fecha
    de vencimiento (debe ser futura) y el CVV (validado, nunca almacenado).
    """

    numero_tarjeta = forms.CharField(
        max_length=19,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '4111 1111 1111 1111'}),
        help_text='Número completo de la tarjeta. No se almacena, solo se validan y guardan los últimos 4 dígitos.',
    )
    cvv = forms.CharField(
        max_length=4,
        widget=forms.PasswordInput(render_value=False, attrs={'class': 'form-input'}),
        help_text='Código de seguridad. No se almacena en el sistema.',
    )

    class Meta:
        model = PaymentMethod
        fields = ['entidad_bancaria', 'titular', 'documento_titular',
                   'tarjeta_mes_vencimiento', 'tarjeta_anio_vencimiento',
                   'es_predeterminado', 'activo']
        widgets = {
            'entidad_bancaria': forms.Select(attrs={'class': 'form-select'}),
            'titular': forms.TextInput(attrs={'class': 'form-input'}),
            'documento_titular': forms.TextInput(attrs={'class': 'form-input'}),
            'tarjeta_mes_vencimiento': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 12}),
            'tarjeta_anio_vencimiento': forms.NumberInput(attrs={'class': 'form-input'}),
            'es_predeterminado': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo_medio = PaymentMethod.TipoMedio.TARJETA
        self.fields['entidad_bancaria'].queryset = EntidadFinanciera.objects.filter(activo=True, tipo='BANCO')

    def clean_numero_tarjeta(self):
        numero = re.sub(r'[\s-]', '', self.cleaned_data['numero_tarjeta'])
        if not numero.isdigit() or not (13 <= len(numero) <= 19):
            raise forms.ValidationError('Número de tarjeta inválido.')
        if not _luhn_valido(numero):
            raise forms.ValidationError('Número de tarjeta inválido (falló verificación Luhn).')
        return numero

    def _post_clean(self):
        """
        Completa los campos derivados del modelo antes de que Django ejecute
        la validación completa de la instancia (full_clean), ya que estos
        dependen de datos que solo están disponibles tras limpiar los campos
        propios del formulario (numero_tarjeta).
        """
        if 'numero_tarjeta' in self.errors:
            return
        
        numero_tarjeta = self.cleaned_data.get('numero_tarjeta', '')
        self.instance.tarjeta_ultimos_digitos = numero_tarjeta[-4:] if numero_tarjeta else ''
        self.instance.numero_cuenta = self.instance.numero_cuenta or 'N/A'
        super()._post_clean()

    def clean(self):
        cleaned_data = super().clean()
        mes = cleaned_data.get('tarjeta_mes_vencimiento')
        anio = cleaned_data.get('tarjeta_anio_vencimiento')
        if mes and anio:
            hoy = date.today()
            if (anio, mes) < (hoy.year, hoy.month):
                raise forms.ValidationError('La tarjeta está vencida.')
        cvv = cleaned_data.get('cvv', '')
        if not cvv.isdigit() or len(cvv) not in (3, 4):
            self.add_error('cvv', 'CVV inválido.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance

class BankTransferForm(forms.ModelForm):
    """
    Formulario especializado para medios de pago tipo Transferencia Bancaria.

    Valida el formato del número de cuenta según el estándar paraguayo
    (dígitos con guiones, longitud variable por entidad).
    """

    class Meta:
        model = PaymentMethod
        fields = ['entidad_bancaria', 'tipo_cuenta_bancaria', 'numero_cuenta',
                   'titular', 'documento_titular', 'es_predeterminado', 'activo']
        widgets = {
            'entidad_bancaria': forms.Select(attrs={'class': 'form-select'}),
            'tipo_cuenta_bancaria': forms.Select(attrs={'class': 'form-select'}),
            'numero_cuenta': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '12-345678-9'}),
            'titular': forms.TextInput(attrs={'class': 'form-input'}),
            'documento_titular': forms.TextInput(attrs={'class': 'form-input'}),
            'es_predeterminado': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo_medio = PaymentMethod.TipoMedio.TRANSFERENCIA
        self.fields['entidad_bancaria'].queryset = EntidadFinanciera.objects.filter(activo=True, tipo='BANCO')

    def clean_numero_cuenta(self):
        numero = self.cleaned_data['numero_cuenta'].strip()
        if not re.match(r'^\d{2,4}-?\d{5,10}-?\d{0,2}$', numero.replace(' ', '')):
            raise forms.ValidationError('Formato de número de cuenta inválido (ej. 12-345678-9).')
        return numero

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance


class DigitalWalletForm(forms.ModelForm):
    """
    Formulario especializado para medios de pago tipo Billetera Digital/Móvil.

    Valida el formato del número de teléfono según el estándar de celulares
    paraguayos (prefijo 9, 8 dígitos adicionales).
    """

    class Meta:
        model = PaymentMethod
        fields = ['entidad_bancaria', 'telefono_billetera', 'titular',
                   'documento_titular', 'es_predeterminado', 'activo']
        widgets = {
            'entidad_bancaria': forms.Select(attrs={'class': 'form-select'}),
            'telefono_billetera': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '0981123456'}),
            'titular': forms.TextInput(attrs={'class': 'form-input'}),
            'documento_titular': forms.TextInput(attrs={'class': 'form-input'}),
            'es_predeterminado': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo_medio = PaymentMethod.TipoMedio.BILLETERA
        self.fields['entidad_bancaria'].queryset = EntidadFinanciera.objects.filter(activo=True, tipo='BILLETERA')

    def clean_telefono_billetera(self):
        telefono = re.sub(r'[\s-]', '', self.cleaned_data['telefono_billetera'])
        if not re.match(r'^0?9\d{8}$', telefono):
            raise forms.ValidationError('Formato de teléfono inválido (ej. 0981123456).')
        return telefono

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.numero_cuenta = self.cleaned_data['telefono_billetera']
        if commit:
            instance.save()
        return instance


class CashBranchForm(forms.ModelForm):
    """
    Formulario especializado para medios de pago tipo Efectivo / Cobro en Ventanilla.

    Sin validaciones de formato especiales, ya que no involucra datos
    bancarios ni de tarjeta — solo requiere identificar al titular.
    """

    class Meta:
        model = PaymentMethod
        fields = ['titular', 'documento_titular', 'es_predeterminado', 'activo']
        widgets = {
            'titular': forms.TextInput(attrs={'class': 'form-input'}),
            'documento_titular': forms.TextInput(attrs={'class': 'form-input'}),
            'es_predeterminado': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo_medio = PaymentMethod.TipoMedio.EFECTIVO
        self.instance.numero_cuenta = 'N/A'

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.entidad_bancaria = None
        if commit:
            instance.save()
        return instance