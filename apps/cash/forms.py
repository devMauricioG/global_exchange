"""
Formularios para la gestión de Cajas, Turnos y Arqueo Ciego de Efectivo (apps.cash.forms).

Provee validaciones rigurosas y campos especializados para:
- :class:`CashShiftOpenForm`: Apertura formal de turno presencial con declaración de fondo inicial por divisa.
- :class:`CashMovementForm`: Registro de movimientos manuales de caja (dotaciones, remesas y ajustes).
- :class:`BlindReconciliationForm`: Arqueo ciego de cierre físico con ingreso de billetes sin sesgo contable.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from django import forms
from django.core.exceptions import ValidationError

from rates.models import Currency
from .models import (
    CashMovement,
    CashRegister,
    CashRegisterStatus,
    CashShift,
    MovementFlow,
    MovementType,
    ShiftStatus,
)
from .services import CashService, CashShiftError, InsufficientCashBalanceError

logger = logging.getLogger(__name__)


class CashShiftOpenForm(forms.Form):
    """
    Formulario para la apertura formal de una sesión o turno de caja (RF-22, RN05).

    Permite seleccionar una caja física disponible y registrar los importes del fondo inicial
    en efectivo por cada una de las divisas activas en la sucursal.
    """

    cash_register = forms.ModelChoiceField(
        queryset=CashRegister.objects.none(),
        empty_label="-- Seleccione una caja física habilitada --",
        label="Caja Registradora / Ventanilla",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': 'required',
        }),
        help_text="Puesto físico de ventanilla en el que operará la jornada.",
    )
    opening_notes = forms.CharField(
        required=False,
        label="Observaciones de Apertura",
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Observaciones, número de precinto o detalles del fondo de cambio asignado...',
        }),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Filtrar exclusivamente cajas activas que no tengan turno abierto
        self.fields['cash_register'].queryset = CashRegister.objects.filter(
            is_active=True,
            status=CashRegisterStatus.CLOSED,
        ).order_by('branch_name', 'register_code')

        # Generar dinámicamente campos de fondo inicial para cada moneda activa
        currencies = Currency.objects.filter(is_active=True).order_by('code')
        self.currency_fields: List[Dict[str, Any]] = []

        for cur in currencies:
            field_name = f"initial_{cur.code}"
            decimals = cur.decimals if cur.decimals is not None else 2
            self.fields[field_name] = forms.DecimalField(
                required=False,
                min_value=Decimal('0.00'),
                max_digits=18,
                decimal_places=decimals,
                initial=Decimal('0.00'),
                label=f"Fondo Inicial en {cur.code} ({cur.symbol})",
                widget=forms.NumberInput(attrs={
                    'class': 'form-input currency-input',
                    'placeholder': f"0.{'0' * decimals}",
                    'step': '1' if decimals == 0 else f"0.{'0' * (decimals - 1)}1",
                }),
                help_text=f"Monto físico en billetes/monedas con el que se inicia la gaveta en {cur.name}.",
            )
            self.currency_fields.append({
                'name': field_name,
                'currency': cur,
                'bound_field': self[field_name],
            })

    def clean_cash_register(self) -> CashRegister:
        register = self.cleaned_data.get('cash_register')
        if not register:
            raise ValidationError("Debe seleccionar una caja física para operar.")
        if register.is_open:
            raise ValidationError(f"La caja {register.register_code} ya posee un turno abierto en curso.")
        if not register.is_active:
            raise ValidationError(f"La caja {register.register_code} se encuentra deshabilitada administrativamente.")
        return register

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()
        initial_balances: Dict[str, Any] = {}

        for key, val in cleaned_data.items():
            if key.startswith('initial_'):
                cur_code = key.replace('initial_', '').upper()
                amt = val if val is not None else Decimal('0.00')
                if amt < Decimal('0.00'):
                    self.add_error(key, "El fondo inicial no puede ser negativo.")
                initial_balances[cur_code] = amt

        cleaned_data['initial_balances'] = initial_balances
        return cleaned_data

    def save(self, cashier: Any, keycloak_user_id: str = '') -> CashShift:
        """
        Invoca la capa de servicios para formalizar la apertura atómica del turno.
        """
        cash_register = self.cleaned_data['cash_register']
        initial_balances = self.cleaned_data['initial_balances']
        opening_notes = self.cleaned_data.get('opening_notes', '')

        return CashService.open_shift(
            cash_register=cash_register,
            cashier=cashier,
            initial_balances=initial_balances,
            keycloak_user_id=keycloak_user_id,
            opening_notes=opening_notes,
        )


class CashMovementForm(forms.Form):
    """
    Formulario para el registro manual de entradas o salidas de efectivo (RF-24).

    Utilizado para dotaciones extraordinarias de tesorería, retiros de remesas
    o ajustes autorizados durante la guardia del cajero.
    """

    movement_type = forms.ChoiceField(
        label="Tipo de Movimiento",
        choices=[
            (MovementType.MANUAL_DEPOSIT, "Aporte Manual / Dotación de Tesorería (+ Entrada)"),
            (MovementType.MANUAL_WITHDRAWAL, "Retiro Manual / Remesa a Tesorería (- Salida)"),
            (MovementType.SURPLUS_ADJUSTMENT, "Ajuste por Sobrante de Caja (+ Entrada)"),
            (MovementType.SHORTAGE_ADJUSTMENT, "Ajuste por Faltante de Caja (- Salida)"),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    currency = forms.ModelChoiceField(
        queryset=Currency.objects.none(),
        empty_label="-- Seleccione Divisa --",
        label="Divisa / Moneda",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    amount = forms.DecimalField(
        min_value=Decimal('0.0001'),
        max_digits=18,
        decimal_places=4,
        label="Importe del Movimiento",
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': 'any',
        }),
        help_text="Importe positivo del dinero que ingresa o egresa.",
    )
    concept = forms.CharField(
        max_length=255,
        label="Concepto / Motivo",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej. Remesa de seguridad a boveda, fondo de cambio...',
        }),
    )
    receipt_number = forms.CharField(
        required=False,
        max_length=64,
        label="Nº de Recibo / Remito Interno (Opcional)",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej. REM-2026-0042',
        }),
    )

    def __init__(self, shift: CashShift, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.shift = shift
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True).order_by('code')

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()
        if not self.shift.is_open:
            raise ValidationError("No es posible registrar movimientos en un turno cerrado o arqueado.")

        m_type = cleaned_data.get('movement_type')
        currency = cleaned_data.get('currency')
        amount = cleaned_data.get('amount')

        if m_type and currency and amount:
            # Flujo de salida
            is_outflow = m_type in [MovementType.MANUAL_WITHDRAWAL, MovementType.SHORTAGE_ADJUSTMENT]
            if is_outflow:
                current_balance = self.shift.calculate_current_balance(currency.code)
                if current_balance < amount:
                    raise ValidationError({
                        'amount': (
                            f"Saldo insuficiente en caja para {currency.code}. "
                            f"Saldo actual disponible: {current_balance:,.2f}, Monto solicitado: {amount:,.2f}."
                        )
                    })

        return cleaned_data

    def save(self, cashier: Any, keycloak_user_id: str = '') -> CashMovement:
        """Registra el movimiento inmutable en el turno activo."""
        m_type = self.cleaned_data['movement_type']
        currency = self.cleaned_data['currency']
        amount = self.cleaned_data['amount']
        concept = self.cleaned_data['concept']
        receipt_number = self.cleaned_data.get('receipt_number', '')

        return CashService.register_movement(
            shift=self.shift,
            movement_type=m_type,
            currency=currency,
            amount=amount,
            concept=concept,
            cashier=cashier,
            receipt_number=receipt_number,
            keycloak_user_id=keycloak_user_id,
        )


class BlindReconciliationForm(forms.Form):
    """
    Formulario de Arqueo Ciego para el Cierre de Caja (RF-23).

    Protocolo de Arqueo Ciego:
    --------------------------
    A fin de garantizar imparcialidad, prevenir sesgos de redondeo o manipulación contable,
    el formulario no expone ni revela al cajero los saldos teóricos esperados del sistema.
    El operador debe efectuar el conteo físico independiente de los billetes y monedas en su gaveta
    e ingresar el importe exacto para cada divisa con actividad.

    Tras la confirmación, el sistema contrasta matemáticamente el conteo físico contra el balance contable
    calculado a partir del fondo inicial y los movimientos inmutables registrados, determinando
    exactamente cualquier sobrante o faltante.
    """

    closing_notes = forms.CharField(
        required=False,
        label="Observaciones de Cierre y Arqueo",
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Observaciones, justificación de anomalías o detalles del cierre...',
        }),
    )

    def __init__(self, shift: CashShift, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.shift = shift

        # Determinar el conjunto de divisas que tuvieron movimientos o fondo inicial
        currencies_seen = set(shift.initial_balances_json.keys())
        for code in shift.movements.values_list('currency__code', flat=True).distinct():
            currencies_seen.add(code)

        if not currencies_seen:
            # Fallback a monedas activas
            currencies_seen = set(Currency.objects.filter(is_active=True).values_list('code', flat=True))

        self.reconciliation_currencies: List[Dict[str, Any]] = []

        for code in sorted(currencies_seen):
            cur = Currency.objects.filter(code=code).first()
            symbol = cur.symbol if cur else '$'
            decimals = cur.decimals if (cur and cur.decimals is not None) else 2
            field_name = f"counted_{code}"

            self.fields[field_name] = forms.DecimalField(
                required=True,
                min_value=Decimal('0.00'),
                max_digits=18,
                decimal_places=decimals,
                label=f"Total Físico Contado en {code} ({symbol})",
                widget=forms.NumberInput(attrs={
                    'class': 'form-input blind-input',
                    'placeholder': f"0.{'0' * decimals}",
                    'step': '1' if decimals == 0 else f"0.{'0' * (decimals - 1)}1",
                    'autocomplete': 'off',
                }),
                help_text=f"Total neto en billetes y monedas de {code} verificado físicamente.",
            )
            self.reconciliation_currencies.append({
                'code': code,
                'name': cur.name if cur else code,
                'symbol': symbol,
                'field_name': field_name,
                'bound_field': self[field_name],
            })

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()
        if not self.shift.is_open:
            raise ValidationError("Este turno de caja ya se encuentra cerrado o arqueado.")

        counted_balances: Dict[str, Any] = {}
        for key, val in cleaned_data.items():
            if key.startswith('counted_'):
                code = key.replace('counted_', '').upper()
                if val is None or val < Decimal('0.00'):
                    self.add_error(key, "El monto físico contado no puede ser negativo.")
                counted_balances[code] = val if val is not None else Decimal('0.00')

        cleaned_data['counted_balances'] = counted_balances
        return cleaned_data

    def save(self, closed_by: Any) -> CashShift:
        """
        Ejecuta el cierre formal y arqueo ciego, calculando diferencias y actualizando el turno.
        """
        counted_balances = self.cleaned_data['counted_balances']
        closing_notes = self.cleaned_data.get('closing_notes', '')

        return CashService.close_shift(
            shift=self.shift,
            counted_balances=counted_balances,
            closed_by=closed_by,
            closing_notes=closing_notes,
        )

