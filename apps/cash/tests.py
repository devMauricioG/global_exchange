"""
Suite integral de pruebas unitarias e integración para Cajas, Turnos y Movimientos de Efectivo (apps.cash.tests).

Verifica el cumplimiento de requerimientos:
- RF-22: Apertura y Asignación de Cajas Presenciales con dotación inicial por divisa.
- RF-23: Cierre y Arqueo de Caja Físico con cálculo matemático de diferencias.
- RF-24: Auditoría y Trazabilidad Inmutable de Movimientos de Efectivo.
- RN05: Control estricto de caja abierta y un solo turno activo por cajero.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate
from transactions.models import Transaction
from .models import (
    Caja,
    CashMovement,
    CashRegister,
    CashRegisterStatus,
    CashShift,
    MovementFlow,
    MovementType,
    MovimientoEfectivo,
    ShiftStatus,
    TurnoCaja,
)
from .services import (
    CashRegisterError,
    CashService,
    CashShiftError,
    InsufficientCashBalanceError,
)

User = get_user_model()


class CashTestCaseBase(TestCase):
    """Clase base con utilitarios para inicialización de entidades de prueba."""

    def setUp(self) -> None:
        super().setUp()
        self.user_cajero = User.objects.create_user(
            username='cajero1',
            email='cajero1@globalexchange.com.py',
            password='Password123!',
        )
        self.user_cajero2 = User.objects.create_user(
            username='cajero2',
            email='cajero2@globalexchange.com.py',
            password='Password123!',
        )
        self.user_supervisor = User.objects.create_user(
            username='supervisor1',
            email='supervisor1@globalexchange.com.py',
            password='Password123!',
        )

        # Monedas base
        self.pyg, _ = Currency.objects.get_or_create(
            code='PYG',
            defaults={'name': 'Guaraní Paraguayo', 'symbol': '₲', 'decimals': 0, 'is_active': True},
        )
        self.usd, _ = Currency.objects.get_or_create(
            code='USD',
            defaults={'name': 'Dólar Estadounidense', 'symbol': '$', 'decimals': 2, 'is_active': True},
        )
        self.eur, _ = Currency.objects.get_or_create(
            code='EUR',
            defaults={'name': 'Euro', 'symbol': '€', 'decimals': 2, 'is_active': True},
        )

        # Caja de prueba
        self.register = CashRegister.objects.create(
            register_code='CAJA-01',
            name='Ventanilla 1 - Central',
            branch_name='Casa Central',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )


class CashRegisterModelTests(CashTestCaseBase):
    """Pruebas del modelo CashRegister."""

    def test_str_representation(self) -> None:
        expected = f"{self.register.register_code} - {self.register.name} (Cerrada)"
        self.assertEqual(str(self.register), expected)

    def test_unique_register_code(self) -> None:
        with self.assertRaises(Exception):
            CashRegister.objects.create(
                register_code='CAJA-01',
                name='Duplicada',
                branch_name='Casa Central',
            )

    def test_cannot_set_open_status_on_inactive_register(self) -> None:
        inactive_reg = CashRegister.objects.create(
            register_code='CAJA-INACTIVA',
            name='Caja Fuera de Servicio',
            is_active=False,
            status=CashRegisterStatus.OPEN,
        )
        with self.assertRaises(ValidationError):
            inactive_reg.clean()

    def test_spanish_aliases(self) -> None:
        self.assertIs(Caja, CashRegister)
        self.assertIs(TurnoCaja, CashShift)
        self.assertIs(MovimientoEfectivo, CashMovement)


class CashShiftLifecycleTests(CashTestCaseBase):
    """Pruebas para el ciclo de vida de turnos de caja (RF-22, RF-23, RN05)."""

    def test_open_shift_success(self) -> None:
        initial = {'PYG': 2000000, 'USD': 500}
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances=initial,
            keycloak_user_id='sub-keycloak-cajero1',
            opening_notes='Apertura turno mañana',
        )

        self.assertEqual(shift.status, ShiftStatus.OPEN)
        self.assertEqual(shift.cashier, self.user_cajero)
        self.assertEqual(shift.keycloak_user_id, 'sub-keycloak-cajero1')
        self.assertTrue(shift.shift_number.startswith('SHIFT-'))

        # La caja debe transicionar a OPEN
        self.register.refresh_from_db()
        self.assertEqual(self.register.status, CashRegisterStatus.OPEN)
        self.assertEqual(self.register.current_cashier, self.user_cajero)
        self.assertTrue(self.register.is_open)
        self.assertEqual(self.register.current_shift, shift)

        # Se deben haber creado los movimientos de fondo inicial
        movements = shift.movements.filter(movement_type=MovementType.INITIAL_FLOAT)
        self.assertEqual(movements.count(), 2)
        self.assertEqual(shift.calculate_current_balance('PYG'), Decimal('2000000.0000'))
        self.assertEqual(shift.calculate_current_balance('USD'), Decimal('500.0000'))

    def test_cannot_open_already_open_register(self) -> None:
        CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000},
        )
        with self.assertRaises(CashRegisterError):
            CashService.open_shift(
                cash_register=self.register,
                cashier=self.user_cajero2,
                initial_balances={'PYG': 500000},
            )

    def test_cashier_cannot_have_two_open_shifts(self) -> None:
        CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000},
        )
        register2 = CashRegister.objects.create(
            register_code='CAJA-02',
            name='Ventanilla 2',
        )
        with self.assertRaises(CashShiftError):
            CashService.open_shift(
                cash_register=register2,
                cashier=self.user_cajero,
                initial_balances={'PYG': 500000},
            )

    def test_reconcile_and_close_shift_without_discrepancy(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1500000, 'USD': 200},
        )

        # Conteo físico exacto igual a saldo inicial (sin movimientos posteriores)
        counted = {'PYG': 1500000, 'USD': 200}
        closed_shift = CashService.close_shift(
            shift=shift,
            counted_balances=counted,
            closed_by=self.user_supervisor,
            closing_notes='Cuadre perfecto',
        )

        self.assertEqual(closed_shift.status, ShiftStatus.RECONCILED)
        self.assertFalse(closed_shift.is_open)
        self.assertEqual(closed_shift.difference_balances_json.get('PYG'), '0.0000')
        self.assertEqual(closed_shift.difference_balances_json.get('USD'), '0.0000')

        # La caja debe quedar cerrada y liberada
        self.register.refresh_from_db()
        self.assertEqual(self.register.status, CashRegisterStatus.CLOSED)
        self.assertIsNone(self.register.current_cashier)

    def test_reconcile_and_close_shift_with_discrepancy(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000, 'USD': 100},
        )

        # Faltante en PYG (-50.000) y Sobrante en USD (+10)
        counted = {'PYG': 950000, 'USD': 110}
        closed_shift = CashService.close_shift(
            shift=shift,
            counted_balances=counted,
            closed_by=self.user_supervisor,
            closing_notes='Diferencias detectadas en conteo',
        )

        self.assertEqual(closed_shift.status, ShiftStatus.DISCREPANCY)
        self.assertEqual(closed_shift.difference_balances_json.get('PYG'), '-50000.0000')
        self.assertEqual(closed_shift.difference_balances_json.get('USD'), '10.0000')

    def test_cannot_close_already_closed_shift(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000},
        )
        CashService.close_shift(shift=shift, counted_balances={'PYG': 1000000}, closed_by=self.user_cajero)
        with self.assertRaises(ValidationError):
            shift.close_and_reconcile({'PYG': 1000000})


class CashMovementTests(CashTestCaseBase):
    """Pruebas para movimientos inmutables de efectivo y control de saldo (RF-24)."""

    def setUp(self) -> None:
        super().setUp()
        self.shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000, 'USD': 500},
            keycloak_user_id='sub-keycloak-cajero1',
        )

    def test_register_manual_deposit(self) -> None:
        mov = CashService.register_movement(
            shift=self.shift,
            movement_type=MovementType.MANUAL_DEPOSIT,
            currency=self.pyg,
            amount=500000,
            concept='Aporte de Tesorería por alta demanda',
            cashier=self.user_cajero,
        )

        self.assertEqual(mov.flow, MovementFlow.IN)
        self.assertEqual(mov.previous_balance, Decimal('1000000.0000'))
        self.assertEqual(mov.resulting_balance, Decimal('1500000.0000'))
        self.assertEqual(self.shift.calculate_current_balance('PYG'), Decimal('1500000.0000'))

    def test_register_manual_withdrawal(self) -> None:
        mov = CashService.register_movement(
            shift=self.shift,
            movement_type=MovementType.MANUAL_WITHDRAWAL,
            currency=self.usd,
            amount=200,
            concept='Remesa de seguridad a tesorería',
            cashier=self.user_cajero,
        )

        self.assertEqual(mov.flow, MovementFlow.OUT)
        self.assertEqual(mov.previous_balance, Decimal('500.0000'))
        self.assertEqual(mov.resulting_balance, Decimal('300.0000'))
        self.assertEqual(self.shift.calculate_current_balance('USD'), Decimal('300.0000'))

    def test_insufficient_cash_balance_error_on_excessive_withdrawal(self) -> None:
        # Intento de egresar 600 USD cuando solo hay 500 USD
        with self.assertRaises(InsufficientCashBalanceError):
            CashService.register_movement(
                shift=self.shift,
                movement_type=MovementType.MANUAL_WITHDRAWAL,
                currency=self.usd,
                amount=600,
                concept='Retiro no autorizado por saldo insuficiente',
                cashier=self.user_cajero,
            )

    def test_negative_or_zero_amount_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CashService.register_movement(
                shift=self.shift,
                movement_type=MovementType.MANUAL_DEPOSIT,
                currency=self.pyg,
                amount=-1000,
                concept='Monto inválido',
                cashier=self.user_cajero,
            )

    def test_movement_immutability_on_save(self) -> None:
        mov = CashService.register_movement(
            shift=self.shift,
            movement_type=MovementType.MANUAL_DEPOSIT,
            currency=self.pyg,
            amount=200000,
            concept='Depósito inicial',
            cashier=self.user_cajero,
        )

        # Modificación prohibida (RF-24)
        mov.amount = Decimal('300000.0000')
        with self.assertRaises(ValidationError):
            mov.save()

    def test_movement_immutability_on_delete(self) -> None:
        mov = CashService.register_movement(
            shift=self.shift,
            movement_type=MovementType.MANUAL_DEPOSIT,
            currency=self.pyg,
            amount=200000,
            concept='Depósito',
            cashier=self.user_cajero,
        )

        # Eliminación prohibida (RF-24)
        with self.assertRaises(ValidationError):
            mov.delete()


class CashTransactionIntegrationTests(CashTestCaseBase):
    """Pruebas de integración con transacciones cambiarias presenciales en efectivo."""

    def setUp(self) -> None:
        super().setUp()
        self.shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 10000000, 'USD': 2000},
            keycloak_user_id='sub-keycloak-cajero1',
        )

        # Cliente de prueba
        self.cliente = Cliente.objects.create(
            nombre='Juan Pérez',
            documento_ruc='1234567-8',
            correo='juan.perez@example.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=True,
        )

        # Entidad financiera
        self.entidad, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Ventanilla Casa Central',
            defaults={'tipo': EntidadFinanciera.TipoEntidad.BANCO, 'activo': True},
        )

        # Medio de pago en Efectivo
        self.pay_method = PaymentMethod.objects.create(
            cliente=self.cliente,
            tipo_medio=PaymentMethod.TipoMedio.EFECTIVO,
            titular='Juan Pérez',
            documento_titular='1234567',
            numero_cuenta='N/A',
            activo=True,
        )

        # Medio de acreditación en Efectivo
        self.rec_method = ReceivingMethod.objects.create(
            cliente=self.cliente,
            entidad_bancaria=self.entidad,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO,
            numero_cuenta='1234567890',
            titular='Juan Pérez',
            activo=True,
        )

        # Tasa de cambio PYG/USD
        now = timezone.now()
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            valid_from=now,
            is_active=True,
            updated_by=self.user_cajero,
        )

    def test_register_transaction_cash_in_and_out(self) -> None:
        # Transacción de compra de 100 USD entregando 740.000 PYG
        tx = Transaction.objects.create(
            codigo_referencia='TX-TEST-CASH-001',
            cliente=self.cliente,
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
            base_currency=self.usd,
            target_currency=self.pyg,
            exchange_rate=self.rate,
            tasa_base=Decimal('7400.0000'),
            tasa_neta=Decimal('7400.0000'),
            monto_origen=Decimal('100.00'),
            monto_destino=Decimal('740000.00'),
            medio_pago_origen=self.pay_method,
            medio_acreditacion_destino=self.rec_method,
            usuario=self.user_cajero,
            estado=Transaction.Estado.COMPLETADA,
        )

        movements = CashService.register_transaction_cash(
            shift=self.shift,
            transaction=tx,
            cashier=self.user_cajero,
            is_cash_in=True,
            is_cash_out=True,
        )

        self.assertEqual(len(movements), 2)
        mov_in = movements[0]
        mov_out = movements[1]

        # Cliente pagó 100 USD (Entrada a la caja)
        self.assertEqual(mov_in.flow, MovementFlow.IN)
        self.assertEqual(mov_in.currency, self.usd)
        self.assertEqual(mov_in.amount, Decimal('100.0000'))
        self.assertEqual(mov_in.transaction, tx)

        # Caja entregó 740.000 PYG (Salida de la caja)
        self.assertEqual(mov_out.flow, MovementFlow.OUT)
        self.assertEqual(mov_out.currency, self.pyg)
        self.assertEqual(mov_out.amount, Decimal('740000.0000'))
        self.assertEqual(mov_out.transaction, tx)

        # Balances verificados
        # USD: 2000 inicial + 100 in = 2100
        self.assertEqual(self.shift.calculate_current_balance('USD'), Decimal('2100.0000'))
        # PYG: 10.000.000 inicial - 740.000 out = 9.260.000
        self.assertEqual(self.shift.calculate_current_balance('PYG'), Decimal('9260000.0000'))

    def test_get_shift_summary(self) -> None:
        summary = CashService.get_shift_summary(self.shift)
        self.assertEqual(summary['shift_number'], self.shift.shift_number)
        self.assertEqual(summary['cash_register'], self.register.register_code)
        self.assertEqual(summary['status'], ShiftStatus.OPEN)
        self.assertTrue(len(summary['currencies']) >= 2)
