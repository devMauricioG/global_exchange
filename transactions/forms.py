"""
Formularios para la aplicación de Transacciones Cambiarias.
"""

from django import forms
from transactions.models import Transaction


class TransactionCreationForm(forms.ModelForm):
    """
    Formulario base para la creación y validación de transacciones cambiarias.
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
        ]
