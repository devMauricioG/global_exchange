"""
Módulo de formularios para la aplicación de medios de pago (payments).

Provee los formularios de captura y edición de instancias :class:`~payments.models.PaymentMethod`
así como formularios de filtrado y búsqueda para la interfaz de usuario.
"""

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
