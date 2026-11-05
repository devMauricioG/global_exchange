"""
Capa de servicios de dominio para la gestión de Cajas, Turnos y Movimientos de Efectivo (apps.cash.services).

Encapsula la lógica de negocio requerida por las normativas de Global Exchange:
- RF-22: Apertura de cajas presenciales y asignación con dotación de fondo inicial en efectivo.
- RF-23: Cierre formal de turno y arqueo físico con cálculo matemático de diferencias por divisa.
- RF-24: Auditoría y trazabilidad inmutable de movimientos físicos asociados al cajero y transacción.
- RN05: Validación de caja en estado Abierta y rol de Cajero para recepción o entrega de efectivo.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

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

logger = logging.getLogger(__name__)


class CashError(Exception):
    """Excepción base para fallas en el módulo de cajas y efectivo."""
    pass


class CashRegisterError(CashError):
    """Falla operativa en la caja registradora o terminal física."""
    pass


class CashShiftError(CashError):
    """Falla en el ciclo de vida del turno de caja (apertura, cierre, arqueo)."""
    pass


class InsufficientCashBalanceError(CashError):
    """Falla al intentar egresar un monto superior al saldo disponible en caja."""
    pass


class CashService:
    """
    Servicio de dominio para la orquestación de operaciones de caja y efectivo.
    """

    @classmethod
    @db_transaction.atomic
    def open_shift(
        cls,
        cash_register: CashRegister,
        cashier: Any,
        initial_balances: Dict[str, Any],
        keycloak_user_id: str = '',
        opening_notes: str = '',
        denominations_breakdown: Optional[Dict[str, Any]] = None,
    ) -> CashShift:
        """
        Abre formalmente un turno de caja con registro de fondo inicial (RF-22, RN05).

        :param cash_register: Puesto físico de atención.
        :param cashier: Usuario cajero asignado.
        :param initial_balances: Diccionario de saldos iniciales por divisa (ej. {'PYG': 1500000, 'USD': 500}).
        :param keycloak_user_id: Identificador inmutable sub del cajero en Keycloak.
        :param opening_notes: Observaciones o justificación de apertura.
        :param denominations_breakdown: Desglose físico de billetes iniciales.
        :return: Instancia creada de :class:`CashShift`.
        :raises CashRegisterError: Si la caja está deshabilitada o ya posee un turno abierto.
        :raises CashShiftError: Si el cajero ya posee otro turno abierto en simultáneo.
        """
        if not cash_register.is_active:
            raise CashRegisterError(f"La caja {cash_register.register_code} está deshabilitada para operar.")

        if cash_register.is_open:
            raise CashRegisterError(
                f"La caja {cash_register.register_code} ya se encuentra abierta en el turno "
                f"{cash_register.current_shift.shift_number if cash_register.current_shift else 'N/A'}."
            )

        # Regla: Un cajero no puede tener dos turnos abiertos simultáneamente
        active_shifts = CashShift.objects.filter(cashier=cashier, status=ShiftStatus.OPEN)
        if active_shifts.exists():
            existing = active_shifts.first()
            raise CashShiftError(
                f"El cajero {cashier.username} ya cuenta con el turno abierto "
                f"{existing.shift_number} en la caja {existing.cash_register.register_code}."
            )

        now = timezone.now()
        date_str = now.strftime('%Y%m%d')
        clean_code = cash_register.register_code.replace('-', '').replace(' ', '').upper()
        count_today = CashShift.objects.filter(
            cash_register=cash_register,
            opened_at__date=now.date(),
        ).count() + 1
        shift_number = f"SHIFT-{date_str}-{clean_code}-{count_today:04d}"

        # Normalizar diccionario de saldos iniciales
        normalized_initial: Dict[str, str] = {}
        for cur_code, amount in initial_balances.items():
            amt = Decimal(str(amount))
            if amt < Decimal('0.0000'):
                raise CashShiftError(f"El fondo inicial para {cur_code} no puede ser negativo ({amt}).")
            normalized_initial[cur_code.upper()] = f"{amt:.4f}"

        # Crear instancia de CashShift
        shift = CashShift.objects.create(
            cash_register=cash_register,
            cashier=cashier,
            keycloak_user_id=keycloak_user_id,
            shift_number=shift_number,
            status=ShiftStatus.OPEN,
            opened_at=now,
            initial_balances_json=normalized_initial,
            denominations_breakdown_json=denominations_breakdown or {},
            opening_notes=opening_notes,
        )

        # Registrar movimientos de fondo inicial para cada divisa con monto > 0
        for cur_code, amt_str in normalized_initial.items():
            amt_val = Decimal(amt_str)
            if amt_val > Decimal('0.0000'):
                currency_obj = Currency.objects.get(code=cur_code)
                CashMovement.objects.create(
                    shift=shift,
                    movement_type=MovementType.INITIAL_FLOAT,
                    flow=MovementFlow.IN,
                    currency=currency_obj,
                    amount=amt_val,
                    previous_balance=Decimal('0.0000'),
                    resulting_balance=amt_val,
                    concept=f"Dotación de Fondo Inicial de Apertura ({shift_number})",
                    receipt_number=f"REC-INIT-{shift_number}-{cur_code}",
                    cashier=cashier,
                    keycloak_user_id=keycloak_user_id,
                )

        # Actualizar estado de la caja física
        cash_register.status = CashRegisterStatus.OPEN
        cash_register.current_cashier = cashier
        cash_register.initial_balances_json = normalized_initial
        cash_register.opened_at = now
        cash_register.save(update_fields=['status', 'current_cashier', 'initial_balances_json', 'opened_at', 'updated_at'])

        logger.info(
            "Turno de caja %s abierto en %s por cajero %s (Keycloak: %s)",
            shift_number,
            cash_register.register_code,
            cashier.username,
            keycloak_user_id,
        )
        return shift

    @classmethod
    @db_transaction.atomic
    def register_movement(
        cls,
        shift: CashShift,
        movement_type: str,
        currency: Currency,
        amount: Any,
        concept: str,
        cashier: Any,
        flow: Optional[str] = None,
        transaction: Optional[Any] = None,
        receipt_number: str = '',
        denominations: Optional[Dict[str, Any]] = None,
        keycloak_user_id: str = '',
    ) -> CashMovement:
        """
        Registra un movimiento inmutable de efectivo en la caja (RF-24).

        Valida el estado del turno, el sentido del flujo y la disponibilidad de fondos.
        """
        if not shift.is_open:
            raise CashShiftError(f"No es posible registrar movimientos en un turno cerrado ({shift.shift_number}).")

        amt = Decimal(str(amount))
        if amt <= Decimal('0.0000'):
            raise ValidationError({'amount': 'El importe del movimiento de caja debe ser estrictamente positivo.'})

        # Inferir flujo si no se especificó explícitamente
        if not flow:
            if movement_type in [
                MovementType.INITIAL_FLOAT,
                MovementType.TRANSACTION_IN,
                MovementType.MANUAL_DEPOSIT,
                MovementType.SURPLUS_ADJUSTMENT,
            ]:
                flow = MovementFlow.IN
            else:
                flow = MovementFlow.OUT

        current_balance = shift.calculate_current_balance(currency.code)

        # Si es un egreso, validar que la caja cuente con saldo físico suficiente
        if flow == MovementFlow.OUT:
            if current_balance < amt:
                raise InsufficientCashBalanceError(
                    f"Saldo insuficiente en caja para {currency.code}. "
                    f"Saldo disponible: {current_balance:,.2f}, Monto a egresar: {amt:,.2f}."
                )
            resulting_balance = current_balance - amt
        else:
            resulting_balance = current_balance + amt

        movement = CashMovement.objects.create(
            shift=shift,
            movement_type=movement_type,
            flow=flow,
            currency=currency,
            amount=amt,
            previous_balance=current_balance,
            resulting_balance=resulting_balance,
            transaction=transaction,
            concept=concept,
            receipt_number=receipt_number,
            denominations_json=denominations or {},
            cashier=cashier,
            keycloak_user_id=keycloak_user_id or shift.keycloak_user_id,
        )

        logger.info(
            "Movimiento de efectivo registrado en turno %s: [%s] %s %s - Saldo: %s",
            shift.shift_number,
            flow,
            currency.code,
            amt,
            resulting_balance,
        )
        return movement

    @classmethod
    @db_transaction.atomic
    def register_transaction_cash(
        cls,
        shift: CashShift,
        transaction: Any,
        cashier: Any,
        keycloak_user_id: str = '',
        is_cash_in: Optional[bool] = None,
        is_cash_out: Optional[bool] = None,
        denominations_in: Optional[Dict[str, Any]] = None,
        denominations_out: Optional[Dict[str, Any]] = None,
    ) -> List[CashMovement]:
        """
        Registra los movimientos de efectivo derivados de una transacción cambiaria (compra o venta).
        """
        movements: List[CashMovement] = []

        medio_pago = getattr(transaction, 'medio_pago_origen', None) or getattr(transaction, 'payment_method', None)
        moneda_origen = getattr(transaction, 'base_currency', None) or getattr(transaction, 'moneda_origen', None)

        medio_rec = getattr(transaction, 'medio_acreditacion_destino', None) or getattr(transaction, 'receiving_method', None)
        moneda_destino = getattr(transaction, 'target_currency', None) or getattr(transaction, 'moneda_destino', None)

        tipo_pago = getattr(medio_pago, 'tipo_medio', None) or getattr(medio_pago, 'tipo_instrumento', None)
        tipo_rec = getattr(medio_rec, 'tipo_medio', None) or getattr(medio_rec, 'tipo_instrumento', None)

        should_in = is_cash_in if is_cash_in is not None else (tipo_pago == 'EFECTIVO' or medio_pago is None)
        should_out = is_cash_out if is_cash_out is not None else (tipo_rec == 'EFECTIVO' or medio_rec is None)

        # Cobro recibido del cliente (IN)
        if should_in and moneda_origen:
            mov_in = cls.register_movement(
                shift=shift,
                movement_type=MovementType.TRANSACTION_IN,
                currency=moneda_origen,
                amount=transaction.monto_origen,
                concept=f"Cobro por Transacción Cambiaria #{transaction.id} ({transaction.tipo_operacion})",
                cashier=cashier,
                flow=MovementFlow.IN,
                transaction=transaction,
                receipt_number=f"REC-TX-{transaction.id}-IN",
                denominations=denominations_in,
                keycloak_user_id=keycloak_user_id,
            )
            movements.append(mov_in)

        # Entrega de efectivo al cliente (OUT)
        if should_out and moneda_destino:
            mov_out = cls.register_movement(
                shift=shift,
                movement_type=MovementType.TRANSACTION_OUT,
                currency=moneda_destino,
                amount=transaction.monto_destino,
                concept=f"Entrega por Transacción Cambiaria #{transaction.id} ({transaction.tipo_operacion})",
                cashier=cashier,
                flow=MovementFlow.OUT,
                transaction=transaction,
                receipt_number=f"REC-TX-{transaction.id}-OUT",
                denominations=denominations_out,
                keycloak_user_id=keycloak_user_id,
            )
            movements.append(mov_out)

        return movements

    @classmethod
    @db_transaction.atomic
    def close_shift(
        cls,
        shift: CashShift,
        counted_balances: Dict[str, Any],
        closed_by: Any,
        closing_notes: str = '',
        denominations_breakdown: Optional[Dict[str, Any]] = None,
    ) -> CashShift:
        """
        Cierra y concilia el turno de caja mediante arqueo físico (RF-23).
        """
        shift.close_and_reconcile(
            counted_balances=counted_balances,
            closed_by=closed_by,
            closing_notes=closing_notes,
            denominations_breakdown=denominations_breakdown,
        )
        return shift

    @classmethod
    def get_shift_summary(cls, shift: CashShift) -> Dict[str, Any]:
        """
        Genera un informe integral del balance operativo del turno.
        """
        currencies_seen = set(shift.initial_balances_json.keys())
        for code in shift.movements.values_list('currency__code', flat=True).distinct():
            currencies_seen.add(code)

        currencies_summary = []
        for code in sorted(currencies_seen):
            init_bal = shift.get_initial_balance(code)
            movs = shift.movements.filter(currency__code=code).exclude(
                movement_type=MovementType.INITIAL_FLOAT
            )

            total_in = Decimal('0.0000')
            total_out = Decimal('0.0000')
            for m in movs:
                if m.flow == MovementFlow.IN:
                    total_in += m.amount
                elif m.flow == MovementFlow.OUT:
                    total_out += m.amount

            expected_bal = init_bal + total_in - total_out
            counted_bal = Decimal(str(shift.final_balances_json.get(code, expected_bal)))
            diff = Decimal(str(shift.difference_balances_json.get(code, counted_bal - expected_bal)))

            currencies_summary.append({
                'currency': code,
                'initial_balance': f"{init_bal:.4f}",
                'total_in': f"{total_in:.4f}",
                'total_out': f"{total_out:.4f}",
                'expected_balance': f"{expected_bal:.4f}",
                'counted_balance': f"{counted_bal:.4f}",
                'difference': f"{diff:.4f}",
                'movements_count': shift.movements.filter(currency__code=code).count(),
            })

        return {
            'shift_number': shift.shift_number,
            'cash_register': shift.cash_register.register_code,
            'cashier': shift.cashier.username,
            'status': shift.status,
            'opened_at': shift.opened_at,
            'closed_at': shift.closed_at,
            'currencies': currencies_summary,
            'total_movements': shift.movements.count(),
        }
