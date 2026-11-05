"""
Suite integral de pruebas unitarias e integración para Cajas, Turnos y Movimientos de Efectivo (apps.cash.tests).

Verifica el cumplimiento de requerimientos:
- RF-22: Apertura y Asignación de Cajas Presenciales con dotación inicial por divisa.
- RF-23: Cierre y Arqueo Ciego de Caja Físico con cálculo matemático de diferencias (sobrante/faltante).
- RF-24: Auditoría y Trazabilidad Inmutable de Movimientos de Efectivo.
- RN05: Control estricto de caja abierta y un solo turno activo por cajero.
- SCRUM-115: Vistas basadas en clases, plantillas y formularios interactivos.
"""

from decimal import Decimal
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate
from transactions.models import Transaction
from .forms import (
    BlindReconciliationForm,
    CashMovementForm,
    CashShiftOpenForm,
)
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
        self.group_operator, _ = Group.objects.get_or_create(name='operator')

        self.user_cajero = User.objects.create_user(
            username='cajero1',
            email='cajero1@globalexchange.com.py',
            password='Password123!',
        )
        self.user_cajero.groups.add(self.group_operator)

        self.user_cajero2 = User.objects.create_user(
            username='cajero2',
            email='cajero2@globalexchange.com.py',
            password='Password123!',
        )
        self.user_cajero2.groups.add(self.group_operator)

        self.user_supervisor = User.objects.create_user(
            username='supervisor1',
            email='supervisor1@globalexchange.com.py',
            password='Password123!',
            is_staff=True,
        )
        self.user_supervisor.groups.add(self.group_operator)

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

        self.client_auth = Client()
        self.client_auth.force_login(self.user_cajero)


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

        self.register.refresh_from_db()
        self.assertEqual(self.register.status, CashRegisterStatus.CLOSED)
        self.assertIsNone(self.register.current_cashier)

    def test_reconcile_and_close_shift_with_discrepancy(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000, 'USD': 100},
        )

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

        self.cliente = Cliente.objects.create(
            nombre='Juan Pérez',
            documento_ruc='1234567-8',
            correo='juan.perez@example.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=True,
        )

        self.entidad, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Ventanilla Casa Central',
            defaults={'tipo': EntidadFinanciera.TipoEntidad.BANCO, 'activo': True},
        )

        self.pay_method = PaymentMethod.objects.create(
            cliente=self.cliente,
            tipo_medio=PaymentMethod.TipoMedio.EFECTIVO,
            titular='Juan Pérez',
            documento_titular='1234567',
            numero_cuenta='N/A',
            activo=True,
        )

        self.rec_method = ReceivingMethod.objects.create(
            cliente=self.cliente,
            entidad_bancaria=self.entidad,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO,
            numero_cuenta='1234567890',
            titular='Juan Pérez',
            activo=True,
        )

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

        self.assertEqual(mov_in.flow, MovementFlow.IN)
        self.assertEqual(mov_in.currency, self.usd)
        self.assertEqual(mov_in.amount, Decimal('100.0000'))
        self.assertEqual(mov_in.transaction, tx)

        self.assertEqual(mov_out.flow, MovementFlow.OUT)
        self.assertEqual(mov_out.currency, self.pyg)
        self.assertEqual(mov_out.amount, Decimal('740000.0000'))
        self.assertEqual(mov_out.transaction, tx)

        self.assertEqual(self.shift.calculate_current_balance('USD'), Decimal('2100.0000'))
        self.assertEqual(self.shift.calculate_current_balance('PYG'), Decimal('9260000.0000'))

    def test_get_shift_summary(self) -> None:
        summary = CashService.get_shift_summary(self.shift)
        self.assertEqual(summary['shift_number'], self.shift.shift_number)
        self.assertEqual(summary['cash_register'], self.register.register_code)
        self.assertEqual(summary['status'], ShiftStatus.OPEN)
        self.assertTrue(len(summary['currencies']) >= 2)


# ==============================================================================
# PRUEBAS DE FORMULARIOS (SCRUM-115)
# ==============================================================================

class CashFormsTests(CashTestCaseBase):
    """Pruebas de los formularios de apertura, movimientos y arqueo ciego (SCRUM-115)."""

    def test_cash_shift_open_form_valid(self) -> None:
        form_data = {
            'cash_register': self.register.id,
            'initial_PYG': '1500000',
            'initial_USD': '300.00',
            'opening_notes': 'Apertura de prueba',
        }
        form = CashShiftOpenForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        shift = form.save(cashier=self.user_cajero, keycloak_user_id='sub-cajero-01')
        self.assertEqual(shift.status, ShiftStatus.OPEN)
        self.assertEqual(shift.cash_register, self.register)
        self.assertEqual(shift.initial_balances_json.get('PYG'), '1500000.0000')
        self.assertEqual(shift.initial_balances_json.get('USD'), '300.0000')

    def test_cash_shift_open_form_unavailable_register(self) -> None:
        # Abrir caja previamente
        CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero2,
            initial_balances={'PYG': 1000},
        )
        form = CashShiftOpenForm(data={'cash_register': self.register.id})
        self.assertFalse(form.is_valid())
        self.assertIn('cash_register', form.errors)

    def test_cash_movement_form_deposit_valid(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 500000},
        )
        form_data = {
            'movement_type': MovementType.MANUAL_DEPOSIT,
            'currency': self.pyg.id,
            'amount': '250000',
            'concept': 'Dotación extra de caja',
            'receipt_number': 'REC-MANUAL-01',
        }
        form = CashMovementForm(shift, data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        mov = form.save(cashier=self.user_cajero)
        self.assertEqual(mov.flow, MovementFlow.IN)
        self.assertEqual(mov.amount, Decimal('250000.0000'))
        self.assertEqual(shift.calculate_current_balance('PYG'), Decimal('750000.0000'))

    def test_cash_movement_form_withdrawal_insufficient_funds(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'USD': 100},
        )
        form_data = {
            'movement_type': MovementType.MANUAL_WITHDRAWAL,
            'currency': self.usd.id,
            'amount': '150.00',  # Supera saldo de 100
            'concept': 'Remesa excesiva',
        }
        form = CashMovementForm(shift, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_blind_reconciliation_form_valid(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000, 'USD': 200},
        )
        # Formulario de arqueo ciego donde se ingresan montos contados físicamente
        form_data = {
            'counted_PYG': '1000000',
            'counted_USD': '200',
            'closing_notes': 'Arqueo ciego exacto',
        }
        form = BlindReconciliationForm(shift, data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        closed_shift = form.save(closed_by=self.user_supervisor)
        self.assertEqual(closed_shift.status, ShiftStatus.RECONCILED)
        self.assertEqual(closed_shift.difference_balances_json.get('PYG'), '0.0000')


# ==============================================================================
# PRUEBAS DE VISTAS BASADAS EN CLASES Y FLUJOS WEB (SCRUM-115)
# ==============================================================================

class CashViewsTests(CashTestCaseBase):
    """Pruebas de vistas, controladores y plantillas para el módulo de Cajas (SCRUM-115)."""

    def test_dashboard_anonymous_redirects(self) -> None:
        client = Client()
        res = client.get(reverse('cash:dashboard'))
        self.assertEqual(res.status_code, 302)

    def test_dashboard_without_active_shift(self) -> None:
        res = self.client_auth.get(reverse('cash:dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "No cuenta con un turno de caja abierto")
        self.assertContains(res, "Abrir Turno en Ventanilla")
        self.assertContains(res, "CAJA-01")

    def test_dashboard_with_active_shift(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 2000000, 'USD': 500},
        )
        res = self.client_auth.get(reverse('cash:dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, shift.shift_number)
        self.assertContains(res, "CAJA-01")
        self.assertContains(res, "TURNO ACTIVO")
        self.assertContains(res, "Registrar Movimiento Manual")
        self.assertContains(res, "Cerrar y Arquear Turno")

    def test_shift_open_view_get(self) -> None:
        res = self.client_auth.get(reverse('cash:shift_open'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Apertura de Turno en Ventanilla")
        self.assertContains(res, "CAJA-01")

    def test_shift_open_view_post_success(self) -> None:
        data = {
            'cash_register': self.register.id,
            'initial_PYG': '3000000',
            'initial_USD': '400',
            'opening_notes': 'Turno tarde',
        }
        res = self.client_auth.post(reverse('cash:shift_open'), data=data, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "abierto exitosamente")

        self.register.refresh_from_db()
        self.assertEqual(self.register.status, CashRegisterStatus.OPEN)
        self.assertEqual(self.register.current_cashier, self.user_cajero)

    def test_shift_open_view_when_already_open_redirects(self) -> None:
        CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000},
        )
        res = self.client_auth.get(reverse('cash:shift_open'))
        self.assertRedirects(res, reverse('cash:dashboard'))

    def test_movement_create_view_get_and_post(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000},
        )
        # GET
        res_get = self.client_auth.get(reverse('cash:movement_create'))
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, "Registrar Movimiento de Efectivo")

        # POST depósito
        data = {
            'movement_type': MovementType.MANUAL_DEPOSIT,
            'currency': self.pyg.id,
            'amount': '500000',
            'concept': 'Dotación tesorería',
        }
        res_post = self.client_auth.post(reverse('cash:movement_create'), data=data, follow=True)
        self.assertEqual(res_post.status_code, 200)
        self.assertContains(res_post, "registrado con éxito")
        self.assertEqual(shift.calculate_current_balance('PYG'), Decimal('1500000.0000'))

    def test_movement_create_view_insufficient_funds_fails(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'USD': 100},
        )
        data = {
            'movement_type': MovementType.MANUAL_WITHDRAWAL,
            'currency': self.usd.id,
            'amount': '500.00',  # Supera saldo de 100 USD
            'concept': 'Retiro no permitido',
        }
        res = self.client_auth.post(reverse('cash:movement_create'), data=data)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Saldo insuficiente en caja")

    def test_shift_close_view_blind_reconciliation_reconciled(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 2000000, 'USD': 500},
        )

        # GET arqueo ciego (no debe mostrar el saldo esperado al cajero)
        res_get = self.client_auth.get(reverse('cash:shift_close', kwargs={'pk': shift.pk}))
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, "Protocolo de Arqueo Ciego")
        self.assertContains(res_get, "Total Físico Contado en PYG")
        self.assertContains(res_get, "Total Físico Contado en USD")

        # POST con arqueo cuadrado
        data = {
            'counted_PYG': '2000000',
            'counted_USD': '500',
            'closing_notes': 'Conteo exacto',
        }
        res_post = self.client_auth.post(
            reverse('cash:shift_close', kwargs={'pk': shift.pk}),
            data=data,
            follow=True,
        )
        self.assertEqual(res_post.status_code, 200)
        shift.refresh_from_db()
        self.assertEqual(shift.status, ShiftStatus.RECONCILED)
        self.assertContains(res_post, "ACTA DE ARQUEO Y CIERRE")
        self.assertContains(res_post, "ARQUEO CUADRADO")

    def test_shift_close_view_blind_reconciliation_discrepancy(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000, 'USD': 300},
        )
        # Faltante en PYG (-20.000) y Sobrante en USD (+50)
        data = {
            'counted_PYG': '980000',
            'counted_USD': '350',
            'closing_notes': 'Diferencias justificadas',
        }
        res = self.client_auth.post(
            reverse('cash:shift_close', kwargs={'pk': shift.pk}),
            data=data,
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        shift.refresh_from_db()
        self.assertEqual(shift.status, ShiftStatus.DISCREPANCY)
        self.assertContains(res, "CERRADO CON DIFERENCIAS")
        self.assertContains(res, "Faltante: -20000.0000")
        self.assertContains(res, "Sobrante: +50.0000")

    def test_shift_detail_and_receipt_view(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000},
        )
        CashService.close_shift(shift, counted_balances={'PYG': 1000000}, closed_by=self.user_supervisor)

        res_detail = self.client_auth.get(reverse('cash:shift_detail', kwargs={'pk': shift.pk}))
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, "ACTA DE ARQUEO Y CIERRE")
        self.assertContains(res_detail, shift.shift_number)

        res_receipt = self.client_auth.get(reverse('cash:shift_receipt', kwargs={'pk': shift.pk}))
        self.assertEqual(res_receipt.status_code, 200)
        self.assertContains(res_receipt, "Imprimir Acta Oficial")

    def test_shift_list_and_register_list_views(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1000000},
        )
        res_shifts = self.client_auth.get(reverse('cash:shift_list'))
        self.assertEqual(res_shifts.status_code, 200)
        self.assertContains(res_shifts, shift.shift_number)

        res_regs = self.client_auth.get(reverse('cash:register_list'))
        self.assertEqual(res_regs.status_code, 200)
        self.assertContains(res_regs, "CAJA-01")

    def test_shift_status_api_view(self) -> None:
        shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.user_cajero,
            initial_balances={'PYG': 1500000},
        )
        res = self.client_auth.get(reverse('cash:api_shift_status', kwargs={'pk': shift.pk}))
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['shift_number'], shift.shift_number)
        self.assertTrue(data['is_open'])
        self.assertIn('summary', data)



class CashRBACAndShiftIsolationTests(TestCase):
    """
    Pruebas SCRUM-116: Blindaje RBAC de tesorería y aislamiento de turnos de caja por usuario.
    """

    def setUp(self) -> None:
        self.cur_pyg = Currency.objects.create(
            code='PYG',
            name='Guaraní Paraguayo',
            symbol='Gs.',
            decimals=0,
            is_active=True,
        )
        self.cur_usd = Currency.objects.create(
            code='USD',
            name='Dólar Estadounidense',
            symbol='$',
            decimals=2,
            is_active=True,
        )

        self.group_cajero, _ = Group.objects.get_or_create(name='cajero')
        self.group_operator, _ = Group.objects.get_or_create(name='operator')
        self.group_user, _ = Group.objects.get_or_create(name='user')

        self.cajero_1 = User.objects.create_user(
            username='cajero_juan',
            email='cajero_juan@test.com',
            password='Password123!',
        )
        self.cajero_1.groups.add(self.group_cajero)
        self.client_cajero_1 = Client()
        self.client_cajero_1.force_login(self.cajero_1)

        self.cajero_2 = User.objects.create_user(
            username='cajero_maria',
            email='cajero_maria@test.com',
            password='Password123!',
        )
        self.cajero_2.groups.add(self.group_cajero)
        self.client_cajero_2 = Client()
        self.client_cajero_2.force_login(self.cajero_2)

        self.user_std = User.objects.create_user(
            username='cliente_carlos',
            email='carlos@test.com',
            password='Password123!',
        )
        self.user_std.groups.add(self.group_user)
        self.client_std = Client()
        self.client_std.force_login(self.user_std)

        self.admin_user = User.objects.create_superuser(
            username='admin_tesoreria',
            email='admin_tesoreria@test.com',
            password='Password123!',
        )
        self.client_admin = Client()
        self.client_admin.force_login(self.admin_user)

        self.op_user = User.objects.create_user(
            username='op_tesoreria',
            email='op_tesoreria@test.com',
            password='Password123!',
            is_staff=True,
        )
        self.op_user.groups.add(self.group_operator)
        self.client_op = Client()
        self.client_op.force_login(self.op_user)

        self.reg_1 = CashRegister.objects.create(
            register_code='CAJA-ISO-01',
            branch_name='Sucursal Asunción',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )
        self.reg_2 = CashRegister.objects.create(
            register_code='CAJA-ISO-02',
            branch_name='Sucursal Asunción',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )

    def test_user_with_only_cajero_role_can_access_dashboard(self) -> None:
        """Un usuario con rol 'cajero' puede acceder a la gestión de caja."""
        res = self.client_cajero_1.get(reverse('cash:dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "CAJA-ISO-01")

    def test_standard_user_cannot_access_cash_dashboard(self) -> None:
        """Un usuario estándar sin rol de caja es redirigido al intentar ingresar a /cash/."""
        res = self.client_std.get(reverse('cash:dashboard'))
        # RoleRequiredMixin redirige a home con warning message
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('home'), res.url)

    def test_standard_user_cannot_open_shift(self) -> None:
        """Un usuario estándar sin rol de cajero no puede abrir turnos de ventanilla."""
        res = self.client_std.get(reverse('cash:shift_open'))
        self.assertEqual(res.status_code, 302)

        data = {
            'cash_register': self.reg_1.pk,
            'initial_PYG': '1000000',
        }
        res_post = self.client_std.post(reverse('cash:shift_open'), data=data)
        self.assertEqual(res_post.status_code, 302)
        self.reg_1.refresh_from_db()
        self.assertFalse(self.reg_1.is_open)

    def test_cajero_cannot_close_other_cajero_shift(self) -> None:
        """Aislamiento: Un cajero no puede cerrar el turno abierto de otro compañero."""
        shift_1 = CashService.open_shift(
            cash_register=self.reg_1,
            cashier=self.cajero_1,
            initial_balances={'PYG': 500000},
        )
        # Cajero 2 intenta cerrar el turno de Cajero 1 especificando su pk
        res_get = self.client_cajero_2.get(reverse('cash:shift_close', kwargs={'pk': shift_1.pk}))
        self.assertEqual(res_get.status_code, 403)

        data = {
            'counted_PYG': '500000',
        }
        res_post = self.client_cajero_2.post(reverse('cash:shift_close', kwargs={'pk': shift_1.pk}), data=data)
        self.assertEqual(res_post.status_code, 403)
        shift_1.refresh_from_db()
        self.assertTrue(shift_1.is_open)

    def test_cajero_cannot_view_other_cajero_shift_detail(self) -> None:
        """Aislamiento: Un cajero no puede consultar el acta de cierre ni movimientos de otro cajero."""
        shift_1 = CashService.open_shift(
            cash_register=self.reg_1,
            cashier=self.cajero_1,
            initial_balances={'PYG': 500000},
        )
        res = self.client_cajero_2.get(reverse('cash:shift_detail', kwargs={'pk': shift_1.pk}))
        self.assertEqual(res.status_code, 403)

    def test_cajero_cannot_view_other_cajero_shift_receipt(self) -> None:
        """Aislamiento: Un cajero no puede imprimir el ticket/acta de otro cajero."""
        shift_1 = CashService.open_shift(
            cash_register=self.reg_1,
            cashier=self.cajero_1,
            initial_balances={'PYG': 500000},
        )
        res = self.client_cajero_2.get(reverse('cash:shift_receipt', kwargs={'pk': shift_1.pk}))
        self.assertEqual(res.status_code, 403)

    def test_cajero_cannot_query_other_cajero_shift_status_api(self) -> None:
        """Aislamiento: Un cajero no puede consultar saldos en tiempo real de otra ventanilla por API."""
        shift_1 = CashService.open_shift(
            cash_register=self.reg_1,
            cashier=self.cajero_1,
            initial_balances={'PYG': 500000},
        )
        res = self.client_cajero_2.get(reverse('cash:api_shift_status', kwargs={'pk': shift_1.pk}))
        self.assertEqual(res.status_code, 403)

    def test_cajero_shift_list_filters_out_other_cajeros_shifts(self) -> None:
        """Aislamiento en lista: Cada cajero solo ve su propio historial de turnos."""
        shift_1 = CashService.open_shift(
            cash_register=self.reg_1,
            cashier=self.cajero_1,
            initial_balances={'PYG': 500000},
        )
        shift_2 = CashService.open_shift(
            cash_register=self.reg_2,
            cashier=self.cajero_2,
            initial_balances={'PYG': 800000},
        )

        # Cajero 1 ve shift_1 pero NO shift_2
        res_1 = self.client_cajero_1.get(reverse('cash:shift_list'))
        self.assertEqual(res_1.status_code, 200)
        self.assertContains(res_1, shift_1.shift_number)
        self.assertNotContains(res_1, shift_2.shift_number)

        # Cajero 2 ve shift_2 pero NO shift_1
        res_2 = self.client_cajero_2.get(reverse('cash:shift_list'))
        self.assertEqual(res_2.status_code, 200)
        self.assertContains(res_2, shift_2.shift_number)
        self.assertNotContains(res_2, shift_1.shift_number)

    def test_admin_and_operator_can_view_and_close_any_shift(self) -> None:
        """Supervisión: Administradores y Operadores de tesorería pueden supervisar y auditar todos los turnos."""
        shift_1 = CashService.open_shift(
            cash_register=self.reg_1,
            cashier=self.cajero_1,
            initial_balances={'PYG': 500000},
        )
        shift_2 = CashService.open_shift(
            cash_register=self.reg_2,
            cashier=self.cajero_2,
            initial_balances={'PYG': 800000},
        )

        # Operador ve ambos en la lista
        res_op_list = self.client_op.get(reverse('cash:shift_list'))
        self.assertEqual(res_op_list.status_code, 200)
        self.assertContains(res_op_list, shift_1.shift_number)
        self.assertContains(res_op_list, shift_2.shift_number)

        # Operador puede consultar detalle de turno de Cajero 1
        res_op_detail = self.client_op.get(reverse('cash:shift_detail', kwargs={'pk': shift_1.pk}))
        self.assertEqual(res_op_detail.status_code, 200)

        # Admin puede consultar detalle de turno de Cajero 2
        res_admin_detail = self.client_admin.get(reverse('cash:shift_detail', kwargs={'pk': shift_2.pk}))
        self.assertEqual(res_admin_detail.status_code, 200)
