"""
Formularios para la aplicación de Transacciones Cambiarias (transactions).

Define los formularios Django para la creación, captura de medios de pago/acreditación
y validación de solicitudes de operaciones cambiarias por parte de clientes y operadores.
"""

from django import forms

from customers.models import Cliente
from payments.models import PaymentMethod, ReceivingMethod
from transactions.models import Transaction


class TransactionCreationForm(forms.ModelForm):
    """
    Formulario base para la creación y validación directa del modelo Transaction.
    """

    class Meta:
        model = Transaction
        fields = [
            'cliente',
            'tipo_operacion',
            'base_currency',
            'target_currency',
            'monto_origen',
            'monto_destino',
            'tasa_base',
            'comision_segmento',
            'tasa_neta',
            'medio_pago_origen',
            'medio_acreditacion_destino',
            'token_congelamiento',
            'observaciones',
        ]


class TransactionOrderForm(forms.Form):
    """
    Formulario para formalizar una Orden de Compra/Venta de Divisas desde el cotizador web.

    Maneja la selección de medios de pago y de acreditación pertenecientes al cliente,
    así como los parámetros ocultos de cotización (en vivo o congelada).
    """

    token_congelamiento = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text='Token único de cotización congelada si aplica.'
    )
    base_currency_code = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.HiddenInput(),
    )
    target_currency_code = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.HiddenInput(),
    )
    amount = forms.DecimalField(
        required=False,
        max_digits=18,
        decimal_places=4,
        widget=forms.HiddenInput(),
    )
    operation_type = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.HiddenInput(),
    )
    is_source_base = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
    )

    medio_pago_origen = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.none(),
        required=True,
        empty_label='-- Seleccione medio de pago de origen --',
        label='Medio de Pago Origen',
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        help_text='Cuenta o billetera desde la cual transferirá los fondos.',
    )

    medio_acreditacion_destino = forms.ModelChoiceField(
        queryset=ReceivingMethod.objects.none(),
        required=True,
        empty_label='-- Seleccione cuenta de acreditación destino --',
        label='Cuenta de Acreditación Destino',
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        help_text='Cuenta bancaria o billetera donde recibirá la divisa liquidada.',
    )

    observaciones = forms.CharField(
        required=False,
        label='Observaciones adicionales',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Comentarios opcionales para la mesa de cambios...'
        }),
    )

    def __init__(self, *args, cliente: Cliente = None, **kwargs):
        """
        Inicializa el formulario filtrando dinámicamente los querysets de medios de pago
        y acreditación para el cliente activo especificado.
        """
        super().__init__(*args, **kwargs)
        self.cliente = cliente

        if cliente:
            self.fields['medio_pago_origen'].queryset = PaymentMethod.objects.filter(
                cliente=cliente,
                activo=True,
            )
            self.fields['medio_acreditacion_destino'].queryset = ReceivingMethod.objects.filter(
                cliente=cliente,
                activo=True,
            )

    def clean(self):
        """
        Valida que existan los datos mínimos requeridos para invocar al servicio transaccional.
        """
        cleaned_data = super().clean()
        token = cleaned_data.get('token_congelamiento')
        base_code = cleaned_data.get('base_currency_code')
        target_code = cleaned_data.get('target_currency_code')
        amount = cleaned_data.get('amount')

        if not token and not (base_code and target_code and amount):
            raise forms.ValidationError(
                'Debe proporcionar un token de cotización congelada o los parámetros completos de cotización en vivo.'
            )

        return cleaned_data
