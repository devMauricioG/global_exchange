"""
Módulo de modelos de datos para la gestión física de Cajas, Turnos y Movimientos de Efectivo (apps.cash).

Define las entidades principales para la operatoria presencial de ventanilla en Global Exchange:
- :class:`CashRegister`: Punto de atención físico, terminal o caja registradora de sucursal.
- :class:`CashShift`: Sesión o turno operativo de caja asignado a un cajero con control de fondo inicial y arqueo.
- :class:`CashMovement`: Registro inmutable de transacciones físicas de efectivo (entradas, salidas y ajustes).

Cumple estrictamente con las especificaciones del diseño de software y requerimientos:
- RF-22: Apertura y Asignación de Cajas Presenciales con registro de fondo inicial por divisa.
- RF-23: Cierre y Arqueo de Caja Físico con conteo de billetes y reporte de diferencias.
- RF-24: Auditoría y Monitoreo Inmutable de Movimientos con trazabilidad a usuario Keycloak.
- RN05: Regla de Negocio de caja abierta y usuario con rol Cajero para operaciones presenciales.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class CashRegisterStatus(models.TextChoices):
    """Estados operativos de una caja registradora o terminal física."""

    CLOSED = 'CLOSED', 'Cerrada'
    OPEN = 'OPEN', 'Abierta'
    PENDING_CONTROL = 'PENDING_CONTROL', 'Pendiente de Control'
    MAINTENANCE = 'MAINTENANCE', 'En Mantenimiento'
    INACTIVE = 'INACTIVE', 'Inactiva'


class ShiftStatus(models.TextChoices):
    """Estados del ciclo de vida de un turno o sesión de caja."""

    OPEN = 'OPEN', 'Abierto'
    PENDING_REVIEW = 'PENDING_REVIEW', 'Pendiente de Control'
    CLOSED = 'CLOSED', 'Cerrado'
    RECONCILED = 'RECONCILED', 'Arqueado / Cuadrado'
    DISCREPANCY = 'DISCREPANCY', 'Cerrado con Diferencias'


class MovementFlow(models.TextChoices):
    """Sentido del flujo de dinero en efectivo respecto a la caja."""

    IN = 'IN', 'Ingreso / Entrada (+)'
    OUT = 'OUT', 'Egreso / Salida (-)'


class MovementType(models.TextChoices):
    """
    Tipos formales de movimientos físicos de efectivo admitidos en caja.
    """

    INITIAL_FLOAT = 'INITIAL_FLOAT', 'Fondo Inicial de Apertura'
    TRANSACTION_IN = 'TRANSACTION_IN', 'Cobro / Ingreso por Operación Cambiaria'
    TRANSACTION_OUT = 'TRANSACTION_OUT', 'Entrega / Egreso por Operación Cambiaria'
    MANUAL_DEPOSIT = 'MANUAL_DEPOSIT', 'Aporte Manual / Dotación de Tesorería'
    MANUAL_WITHDRAWAL = 'MANUAL_WITHDRAWAL', 'Retiro Manual / Remesa a Tesorería'
    SURPLUS_ADJUSTMENT = 'SURPLUS_ADJUSTMENT', 'Ajuste por Sobrante de Arqueo'
    SHORTAGE_ADJUSTMENT = 'SHORTAGE_ADJUSTMENT', 'Ajuste por Faltante de Arqueo'
    FINAL_WITHDRAWAL = 'FINAL_WITHDRAWAL', 'Retiro Final de Cierre'


class CashRegister(models.Model):
    """
    Representa una caja registradora física o terminal de ventanilla en una sucursal.

    Mantiene la identidad del puesto físico, la sucursal a la que pertenece, su estado
    operativo y la trazabilidad histórica de los saldos iniciales y finales registrados.

    :ivar register_code: Código alfanumérico único de la caja (ej: 'CAJA-01', 'VENT-02').
    :ivar name: Nombre descriptivo del puesto de atención.
    :ivar branch_name: Nombre o denominación de la sucursal física.
    :ivar status: Estado operativo actual de la caja (Cerrada, Abierta, Mantenimiento, Inactiva).
    :ivar current_cashier: Usuario del sistema que actualmente opera la caja en un turno activo.
    :ivar initial_balances_json: Registro de fondo inicial del turno más reciente (JSON).
    :ivar final_balances_json: Registro de saldo final verificado del turno más reciente (JSON).
    :ivar opened_at: Fecha y hora de la última apertura registrada.
    :ivar closed_at: Fecha y hora del último cierre registrado.
    :ivar is_active: Indicador de habilitación administrativa para operar.
    """

    register_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='Código de Caja',
        help_text='Identificador único de la caja o ventanilla (ej. CAJA-01).',
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Nombre Descriptivo',
        help_text='Denominación del puesto de atención (ej. Ventanilla 1 - Principal).',
    )
    branch_name = models.CharField(
        max_length=150,
        default='Casa Central',
        db_index=True,
        verbose_name='Sucursal / Agencia',
        help_text='Nombre de la sucursal física en la que opera la caja.',
    )
    status = models.CharField(
        max_length=20,
        choices=CashRegisterStatus.choices,
        default=CashRegisterStatus.CLOSED,
        db_index=True,
        verbose_name='Estado Operativo',
    )
    current_cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cash_registers',
        verbose_name='Cajero Actual',
        help_text='Usuario asignado operando la caja en el turno vigente.',
    )
    initial_balances_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Saldos Iniciales Registrados',
        help_text='Saldos de fondo inicial del último turno.',
    )
    final_balances_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Saldos Finales Registrados',
        help_text='Saldos finales tras arqueo del último turno.',
    )
    opened_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Última Apertura',
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último Cierre',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Habilitada para Operar',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Alta',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Modificación',
    )

    class Meta:
        verbose_name = 'Caja Registradora'
        verbose_name_plural = 'Cajas Registradoras'
        ordering = ['branch_name', 'register_code']

    def __str__(self) -> str:
        return f"{self.register_code} - {self.name} ({self.get_status_display()})"

    @property
    def is_open(self) -> bool:
        """Indica si la caja se encuentra en estado Abierta."""
        return self.status == CashRegisterStatus.OPEN

    @property
    def current_shift(self) -> Optional['CashShift']:
        """Retorna el turno abierto actualmente en la caja, o None si está cerrada."""
        return self.shifts.filter(status=ShiftStatus.OPEN).first()

    def clean(self) -> None:
        super().clean()
        if not self.is_active and self.status == CashRegisterStatus.OPEN:
            raise ValidationError(
                {'status': 'Una caja deshabilitada/inactiva no puede permanecer en estado Abierta.'}
            )


class CashShift(models.Model):
    """
    Representa una sesión o turno operativo de caja abierto por un cajero.

    Agrupa la apertura con fondo inicial en efectivo (RF-22), los movimientos ejecutados
    durante la jornada (RF-24) y el arqueo físico final con cálculo de diferencias (RF-23).

    :ivar cash_register: Caja física donde se ejecuta el turno.
    :ivar cashier: Usuario cajero que opera el turno.
    :ivar keycloak_user_id: ID inmutable del cajero en Keycloak para auditoría (RN05).
    :ivar shift_number: Número de comprobante único de turno.
    :ivar status: Estado del turno (Abierto, Cerrado, Arqueado, Con Diferencias).
    :ivar opened_at: Marca temporal de apertura.
    :ivar closed_at: Marca temporal de cierre.
    :ivar initial_balances_json: Fondo inicial declarado por divisa (ej. {"PYG": "1500000.00"}).
    :ivar expected_balances_json: Saldo teórico calculado por el sistema al cierre.
    :ivar final_balances_json: Conteo físico declarado por el cajero en el arqueo.
    :ivar difference_balances_json: Diferencias de arqueo (Declarado - Esperado).
    :ivar denominations_breakdown_json: Desglose de piezas/billetes físicos contados.
    :ivar opening_notes: Observaciones o justificación registrada al abrir.
    :ivar closing_notes: Observaciones o justificación registrada al cerrar/arquear.
    :ivar closed_by: Supervisor o cajero que formalizó el cierre del turno.
    """

    cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        related_name='shifts',
        verbose_name='Caja Registradora',
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cash_shifts',
        verbose_name='Cajero / Operador',
    )
    keycloak_user_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name='Keycloak User ID del Cajero',
        help_text='Identificador inmutable sub del cajero en Keycloak para trazabilidad y auditoría (RN05, RF-24).',
    )
    shift_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name='Número de Turno',
        help_text='Identificador correlativo del turno (ej. SHIFT-20261103-CAJA01-0001).',
    )
    status = models.CharField(
        max_length=20,
        choices=ShiftStatus.choices,
        default=ShiftStatus.OPEN,
        db_index=True,
        verbose_name='Estado del Turno',
    )
    opened_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='Fecha y Hora de Apertura',
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha y Hora de Cierre',
    )
    initial_balances_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Saldos Iniciales por Divisa (Fondo)',
        help_text='Diccionario con código de moneda y monto inicial de apertura.',
    )
    expected_balances_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Saldos Teóricos Esperados',
        help_text='Saldos calculados por el sistema (Inicial + Ingresos - Egresos).',
    )
    final_balances_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Saldos Físicos Contados (Arqueo)',
        help_text='Saldos físicos reales declarados por el cajero al arqueo.',
    )
    difference_balances_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Diferencias de Arqueo',
        help_text='Diferencia matemática: Contado - Esperado (+ sobrante, - faltante).',
    )
    denominations_breakdown_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Desglose Físico de Billetes',
        help_text='Detalle de conteo de piezas físicas por denominación y divisa.',
    )
    opening_notes = models.TextField(
        blank=True,
        verbose_name='Observaciones de Apertura',
    )
    closing_notes = models.TextField(
        blank=True,
        verbose_name='Observaciones de Cierre / Arqueo',
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_closed_shifts',
        verbose_name='Cerrado / Supervisado por',
    )

    class Meta:
        verbose_name = 'Turno de Caja'
        verbose_name_plural = 'Turnos de Caja'
        ordering = ['-opened_at', '-id']

    def __str__(self) -> str:
        return f"{self.shift_number} - {self.cash_register.register_code} ({self.get_status_display()})"

    @property
    def is_open(self) -> bool:
        """Indica si el turno está actualmente abierto."""
        return self.status == ShiftStatus.OPEN

    def get_initial_balance(self, currency_code: str) -> Decimal:
        """
        Retorna el saldo inicial declarado para la divisa indicada en este turno.
        """
        raw = self.initial_balances_json.get(currency_code.upper(), '0.0000')
        return Decimal(str(raw))

    def calculate_current_balance(self, currency_code: str) -> Decimal:
        """
        Calcula en tiempo real el saldo actual en caja para una divisa.
        Formula: Saldo Inicial + sum(Ingresos posteriores) - sum(Egresos).
        """
        code = currency_code.upper()
        balance = self.get_initial_balance(code)

        movements = self.movements.filter(currency__code=code).exclude(
            movement_type=MovementType.INITIAL_FLOAT
        )
        for mov in movements:
            if mov.flow == MovementFlow.IN:
                balance += mov.amount
            elif mov.flow == MovementFlow.OUT:
                balance -= mov.amount
        return balance

    def calculate_expected_balances(self) -> Dict[str, str]:
        """
        Calcula los saldos teóricos esperados para todas las divisas con movimientos
        o fondo inicial en este turno.
        """
        currencies_seen = set(self.initial_balances_json.keys())
        for code in self.movements.values_list('currency__code', flat=True).distinct():
            currencies_seen.add(code)

        result: Dict[str, str] = {}
        for code in sorted(currencies_seen):
            bal = self.calculate_current_balance(code)
            result[code] = f"{bal:.4f}"
        return result

    def close_and_reconcile(
        self,
        counted_balances: Dict[str, Any],
        closed_by: Optional[Any] = None,
        closing_notes: str = '',
        denominations_breakdown: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Ejecuta el arqueo físico de caja (RF-23), calcula diferencias y cierra el turno.

        :param counted_balances: Diccionario con los montos contados físicamente por divisa.
        :param closed_by: Usuario supervisor o cajero que ejecuta el cierre.
        :param closing_notes: Observaciones y justificaciones del arqueo.
        :param denominations_breakdown: Conteo detallado opcional de billetes por denominación.
        :raises ValidationError: Si el turno ya se encontraba cerrado.
        """
        if not self.is_open:
            raise ValidationError('Este turno ya se encuentra cerrado o arqueado.')

        expected = self.calculate_expected_balances()
        differences: Dict[str, str] = {}
        has_discrepancy = False

        normalized_counted: Dict[str, str] = {}
        all_currencies = set(expected.keys()).union(
            {k.upper() for k in counted_balances.keys()}
        )

        for code in sorted(all_currencies):
            exp_val = Decimal(expected.get(code, '0.0000'))
            cnt_val = Decimal(str(counted_balances.get(code, '0.0000')))
            diff = cnt_val - exp_val

            normalized_counted[code] = f"{cnt_val:.4f}"
            differences[code] = f"{diff:.4f}"

            if diff != Decimal('0.0000'):
                has_discrepancy = True

        self.expected_balances_json = expected
        self.final_balances_json = normalized_counted
        self.difference_balances_json = differences
        if denominations_breakdown:
            self.denominations_breakdown_json = denominations_breakdown

        self.closed_at = timezone.now()
        self.closed_by = closed_by or self.cashier
        self.closing_notes = closing_notes
        self.status = ShiftStatus.DISCREPANCY if has_discrepancy else ShiftStatus.RECONCILED
        self.save()

        # Actualizar estado de la caja registradora asociada
        reg = self.cash_register
        reg.status = CashRegisterStatus.CLOSED
        reg.current_cashier = None
        reg.final_balances_json = normalized_counted
        reg.closed_at = self.closed_at
        reg.save(update_fields=['status', 'current_cashier', 'final_balances_json', 'closed_at', 'updated_at'])

        logger.info(
            "Turno de caja %s cerrado exitosamente. Estado: %s - Diferencias: %s",
            self.shift_number,
            self.status,
            differences,
        )


class CashMovement(models.Model):
    """
    Registro inmutable de movimientos físicos de efectivo en ventanilla (RF-24).

    Garantiza trazabilidad y auditoría forense para cada entrada o salida física de dinero,
    asociando el turno, la divisa, el monto, el saldo anterior y resultante, el cajero responsable
    y su identificador inmutable en Keycloak (RN05).

    :ivar shift: Turno de caja en el que se ejecuta el movimiento.
    :ivar movement_type: Clasificación formal del movimiento (apertura, cobro, entrega, etc.).
    :ivar flow: Sentido del flujo monetario (IN para ingresos, OUT para egresos).
    :ivar currency: Divisa involucrada en la transacción física.
    :ivar amount: Monto de la operación (siempre positivo).
    :ivar previous_balance: Saldo existente en caja para dicha divisa antes del movimiento.
    :ivar resulting_balance: Saldo en caja resultante tras la aplicación del movimiento.
    :ivar transaction: Clave foránea opcional a la transacción cambiaria formalizada.
    :ivar concept: Descripción o motivo justificativo del movimiento.
    :ivar receipt_number: Identificador de comprobante físico o recibo de caja.
    :ivar denominations_json: Desglose de piezas de billetes procesadas en el movimiento.
    :ivar cashier: Usuario operador que registra la acción.
    :ivar keycloak_user_id: ID inmutable sub del cajero en Keycloak (RF-24).
    :ivar created_at: Marca temporal de creación del registro (inmutable).
    :ivar is_immutable: Bandera de seguridad que previene edición o eliminación del registro.
    """

    shift = models.ForeignKey(
        CashShift,
        on_delete=models.PROTECT,
        related_name='movements',
        verbose_name='Turno de Caja',
    )
    movement_type = models.CharField(
        max_length=32,
        choices=MovementType.choices,
        db_index=True,
        verbose_name='Tipo de Movimiento',
    )
    flow = models.CharField(
        max_length=10,
        choices=MovementFlow.choices,
        db_index=True,
        verbose_name='Flujo Monetario',
    )
    currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.PROTECT,
        related_name='cash_movements',
        verbose_name='Divisa',
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        verbose_name='Monto del Movimiento',
        help_text='Importe monetario positivo del movimiento.',
    )
    previous_balance = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name='Saldo Anterior',
        help_text='Saldo en caja antes de impactar este movimiento.',
    )
    resulting_balance = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0.0000'),
        verbose_name='Saldo Resultante',
        help_text='Saldo en caja tras impactar este movimiento.',
    )
    transaction = models.ForeignKey(
        'transactions.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_movements',
        verbose_name='Transacción Cambiaria',
        help_text='Transacción cambiaria formalizada a la que responde este cobro o entrega (RF-24).',
    )
    concept = models.CharField(
        max_length=255,
        verbose_name='Concepto / Justificación',
    )
    receipt_number = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Nº Comprobante / Recibo',
    )
    denominations_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Desglose de Billetes',
        help_text='Conteo de billetes recibidos o entregados por denominación.',
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='authored_cash_movements',
        verbose_name='Cajero / Operador',
    )
    keycloak_user_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name='Keycloak User ID del Cajero',
        help_text='Auditoría inmutable para trazabilidad (RF-24).',
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        editable=False,
        verbose_name='Fecha y Hora',
    )
    is_immutable = models.BooleanField(
        default=True,
        editable=False,
        verbose_name='Registro Inmutable',
    )

    class Meta:
        verbose_name = 'Movimiento de Efectivo'
        verbose_name_plural = 'Movimientos de Efectivo'
        ordering = ['-created_at', '-id']

    def __str__(self) -> str:
        return (
            f"[{self.flow}] {self.currency.code} {self.amount:,.2f} - "
            f"{self.get_movement_type_display()} ({self.shift.shift_number})"
        )

    def clean(self) -> None:
        super().clean()
        if self.amount is not None and self.amount <= Decimal('0.0000'):
            raise ValidationError({'amount': 'El monto del movimiento debe ser estrictamente positivo.'})

        # Control de inmutabilidad estricta (RF-24)
        if self.pk is not None:
            original = CashMovement.objects.get(pk=self.pk)
            if original.is_immutable:
                raise ValidationError(
                    'Los movimientos de efectivo de caja son inmutables para fines de auditoría (RF-24) '
                    'y no admiten modificaciones.'
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:
        if self.is_immutable:
            raise ValidationError(
                'Los registros de movimientos de efectivo son inmutables por normativa de auditoría (RF-24) '
                'y no pueden ser eliminados del sistema.'
            )
        super().delete(*args, **kwargs)


# Alias en español para integración fluida de dominio
Caja = CashRegister
TurnoCaja = CashShift
MovimientoEfectivo = CashMovement


# ==============================================================================
# MÓDULO DE INVENTARIO DE BILLETES Y BÓVEDA (SCRUM-116)
# ==============================================================================
from .inventory_models import (
    LocationType,
    BanknoteMovementType,
    ReconciliationAction,
    Vault,
    CurrencyDenomination,
    BanknoteInventory,
    InitialFloatConfig,
    BanknoteMovement,
    ShiftDenominationCount,
)

Boveda = Vault
DenominacionMoneda = CurrencyDenomination
InventarioBilletes = BanknoteInventory
MovimientoBilletes = BanknoteMovement
ArqueoDenominacion = ShiftDenominationCount
