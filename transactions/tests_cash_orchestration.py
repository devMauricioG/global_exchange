"""
Suite de pruebas unitarias e integración para la Orquestación Transaccional en Efectivo (SCRUM-123).

Verifica la atomicidad e integridad financiera de:
- TransactionService.process_cash_payment():
  1. Vinculación atómica con turno de caja activo (CashShift).
  2. Generación inmutable de movimientos de cobro y entrega (CashMovement / MovimientoCaja).
  3. Control estricto de disponibilidad física de efectivo (InsufficientCashBalanceError).
  4. Transición irreversible de la orden a COMPLETADA con referencia y pasarela 'EFECTIVO'.
  5. Emisión atómica y sincronizada del Documento Tributario Electrónico (SIFEN / KuDE).
  6. Idempotencia y rechazo ante órdenes ya completadas o canceladas.
  7. Trazabilidad completa hacia auditoría con Keycloak User ID.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.cash.models import (
    Caja,
    CashMovement,
    CashRegister,
    CashRegisterStatus,
    CashShift,
    MovementFlow,
    MovementType,
    MovimientoCaja,
    MovimientoEfectivo,
    ShiftStatus,
    TurnoCaja,
)
from apps.cash.services import (
    CashError,
    CashRegisterError,
    CashService,
    CashShiftError,
    InsufficientCashBalanceError,
)
from apps.invoicing.models import FacturaElectronica
from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate
from transactions.models import ElectronicInvoice, Transaction
from transactions.services import TransactionService

User = get_user_model()


class CashOrchestrationTestCase(TestCase):
    """
    Pruebas exhaustivas para la liquidación presencial atómica en efectivo (SCRUM-123).
    """

    def setUp(self):
        super().setUp()

        # 1. Usuarios y roles
        self.group_operator, _ = Group.objects.get_or_create(name='operator')

        self.cajero = User.objects.create_user(
            username='cajero_ventanilla',
            email='cajero@globalexchange.com.py',
            password='Password123!',
        )
        self.cajero.groups.add(self.group_operator)
        self.cajero.keycloak_id = 'kc-sub-cajero-uuid-999'

        # 2. Cliente titular
        self.cliente = Cliente.objects.create(
            nombre='Casa de Cambios Guaraní S.R.L.',
            documento_ruc='80011223-5',
            correo='admin@casaguarani.com.py',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
            is_active=True,
        )

        # 3. Monedas
        self.pyg, _ = Currency.objects.get_or_create(
            code='PYG',
            defaults={'name': 'Guaraní Paraguayo', 'symbol': '₲', 'decimals': 0, 'is_active': True},
        )
        self.usd, _ = Currency.objects.get_or_create(
            code='USD',
            defaults={'name': 'Dólar Estadounidense', 'symbol': '$', 'decimals': 2, 'is_active': True},
        )

        # 4. Cotización oficial
        self.exchange_rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.00'),
            sell_rate=Decimal('7900.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )

        # 5. Caja física
        self.register = CashRegister.objects.create(
            register_code='CAJA-05',
            name='Ventanilla 5 - Casa Central',
            branch_name='Casa Central',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )

        # 6. Apertura de turno con fondos suficientes
        self.initial_balances = {
            'PYG': Decimal('15000000.00'),  # 15.000.000 Gs
            'USD': Decimal('5000.00'),      # 5.000 USD
        }
        self.shift = CashService.open_shift(
            cash_register=self.register,
            cashier=self.cajero,
            initial_balances=self.initial_balances,
            keycloak_user_id=self.cajero.keycloak_id,
            opening_notes='Apertura turno regular SCRUM-123',
        )

        # 7. Medios de pago en efectivo
        self.entidad = EntidadFinanciera.objects.create(
            nombre='Banco Central de Prueba',
            tipo=EntidadFinanciera.TipoEntidad.BANCO,
            activo=True,
        )
        self.medio_pago_efectivo = PaymentMethod.objects.create(
            cliente=self.cliente,
            tipo_medio=PaymentMethod.TipoMedio.EFECTIVO,
            entidad_bancaria=self.entidad,
            numero_cuenta='EFECTIVO-01',
            titular='Casa de Cambios Guaraní S.R.L.',
            activo=True,
        )
        self.medio_rec_efectivo = ReceivingMethod.objects.create(
            cliente=self.cliente,
            entidad_bancaria=self.entidad,
            tipo_cuenta=ReceivingMethod.TipoCuenta.CORRIENTE,
            numero_cuenta='EFECTIVO-REC-01',
            titular='Casa de Cambios Guaraní S.R.L.',
            activo=True,
        )

    def _create_pending_tx(self, monto_usd: Decimal = Decimal('100.00'), tasa: Decimal = Decimal('7900.00')) -> Transaction:
        """Crea una transacción cambiaria de prueba en estado PENDIENTE."""
        monto_pyg = (monto_usd * tasa).quantize(Decimal('0.01'))
        return Transaction.objects.create(
            cliente=self.cliente,
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
            base_currency=self.usd,
            target_currency=self.pyg,
            exchange_rate=self.exchange_rate,
            tasa_base=tasa,
            comision_segmento=Decimal('0.00'),
            tasa_neta=tasa,
            monto_origen=monto_usd,
            monto_destino=monto_pyg,
            medio_pago_origen=self.medio_pago_efectivo,
            medio_acreditacion_destino=self.medio_rec_efectivo,
            estado=Transaction.Estado.PENDIENTE,
        )

    def test_alias_movimiento_caja_exists(self):
        """Verifica que el alias MovimientoCaja = CashMovement esté correctamente disponible."""
        self.assertIs(MovimientoCaja, CashMovement)
        self.assertIs(MovimientoEfectivo, CashMovement)
        self.assertIs(TurnoCaja, CashShift)
        self.assertIs(Caja, CashRegister)

    def test_process_cash_payment_successful_full_lifecycle(self):
        """
        Verifica el flujo integral exitoso de process_cash_payment:
        - Registro de movimientos IN y OUT.
        - Transición a COMPLETADA.
        - Emisión de FacturaElectronica SIFEN y ElectronicInvoice KuDE.
        """
        tx = self._create_pending_tx(monto_usd=Decimal('200.00'), tasa=Decimal('7900.00'))
        denominations_in = {'100': 2}
        denominations_out = {'100000': 15, '50000': 1, '20000': 1, '10000': 1}

        completed_tx = TransactionService.process_cash_payment(
            transaction_obj=tx,
            shift=self.shift,
            cashier=self.cajero,
            concepto='Operación en ventanilla cliente habitual',
            denominations_in=denominations_in,
            denominations_out=denominations_out,
            is_cash_in=True,
            is_cash_out=True,
            emitir_factura=True,
            is_test=True,
        )

        # 1. Estado de la transacción
        self.assertEqual(completed_tx.estado, Transaction.Estado.COMPLETADA)
        self.assertEqual(completed_tx.pasarela_pago, 'EFECTIVO')
        self.assertEqual(completed_tx.referencia_externa_pago, f"CASH-{self.register.register_code}-{tx.id}")
        self.assertIsNotNone(completed_tx.fecha_pago)
        self.assertEqual(completed_tx.usuario, self.cajero)
        self.assertIn('ventanilla', completed_tx.observaciones.lower())

        # 2. Movimientos de efectivo en caja (MovimientoCaja)
        movements = CashMovement.objects.filter(transaction=completed_tx).order_by('id')
        self.assertEqual(movements.count(), 2)

        # Cobro recibido del cliente (IN: 200 USD)
        mov_in = movements.filter(flow=MovementFlow.IN).first()
        self.assertIsNotNone(mov_in)
        self.assertEqual(mov_in.movement_type, MovementType.TRANSACTION_IN)
        self.assertEqual(mov_in.currency, self.usd)
        self.assertEqual(mov_in.amount, Decimal('200.00'))
        self.assertEqual(mov_in.shift, self.shift)
        self.assertEqual(mov_in.cashier, self.cajero)
        self.assertEqual(mov_in.keycloak_user_id, self.cajero.keycloak_id)
        self.assertEqual(mov_in.denominations_json, denominations_in)

        # Entrega al cliente (OUT: 1.580.000 PYG)
        mov_out = movements.filter(flow=MovementFlow.OUT).first()
        self.assertIsNotNone(mov_out)
        self.assertEqual(mov_out.movement_type, MovementType.TRANSACTION_OUT)
        self.assertEqual(mov_out.currency, self.pyg)
        self.assertEqual(mov_out.amount, Decimal('1580000.00'))
        self.assertEqual(mov_out.shift, self.shift)
        self.assertEqual(mov_out.denominations_json, denominations_out)

        # Saldos actualizados de caja
        balance_usd = self.shift.calculate_current_balance('USD')
        balance_pyg = self.shift.calculate_current_balance('PYG')
        self.assertEqual(balance_usd, Decimal('5000.00') + Decimal('200.00'))
        self.assertEqual(balance_pyg, Decimal('15000000.00') - Decimal('1580000.00'))

        # 3. Emisión de facturas
        # 3.1. Factura e-Kuatia / SIFEN (apps.invoicing)
        self.assertTrue(FacturaElectronica.objects.filter(transaction=completed_tx).exists())
        factura_sifen = FacturaElectronica.objects.get(transaction=completed_tx)
        self.assertEqual(len(factura_sifen.cdc), 44)
        self.assertTrue(factura_sifen.es_simulada)

        # 3.2. KuDE (transactions.ElectronicInvoice)
        self.assertTrue(ElectronicInvoice.objects.filter(transaction=completed_tx).exists())
        inv_kude = ElectronicInvoice.objects.get(transaction=completed_tx)
        self.assertEqual(len(inv_kude.cdc), 44)
        self.assertTrue(completed_tx.has_kude)

    def test_insufficient_cash_balance_atomic_rollback(self):
        """
        Verifica que ante fondos insuficientes en la caja para la divisa a entregar:
        - Se lance InsufficientCashBalanceError.
        - La transacción no cambie de estado (permanezca PENDIENTE).
        - No se persista ningún movimiento de efectivo.
        - No se emita ninguna factura electrónica.
        """
        # Saldo actual en USD es 5.000. Solicitamos entregar 6.000 USD al cliente.
        # Para COMPRA con base_currency=USD: monto_destino = 6000 * 7900 PYG pero
        # nosotros controlamos que la entrega sea en USD forzando is_cash_out=True.
        # Creamos una VENTA donde el cliente recibe USD:
        # VENTA: moneda_origen=base_currency=USD, moneda_destino=target_currency=PYG
        # register_transaction_cash: IN→USD(monto_origen), OUT→PYG(monto_destino)
        # Pero queremos OUT en USD... Mejor: creamos con montos que excedan el saldo disponible.
        tx = self._create_pending_tx(monto_usd=Decimal('100.00'), tasa=Decimal('7900.00'))
        # monto_destino = 790000 PYG. Forzamos is_cash_out=True.
        # Pero 790000 < 15000000 PYG disponibles. Necesitamos generar un caso que exceda.

        # Creamos una TX con monto_destino que exceda PYG disponible
        big_tx = Transaction.objects.create(
            cliente=self.cliente,
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
            base_currency=self.usd,
            target_currency=self.pyg,
            exchange_rate=self.exchange_rate,
            tasa_base=Decimal('7900.00'),
            comision_segmento=Decimal('0.00'),
            tasa_neta=Decimal('7900.00'),
            monto_origen=Decimal('3000.00'),
            monto_destino=Decimal('23700000.00'),
            medio_pago_origen=self.medio_pago_efectivo,
            medio_acreditacion_destino=self.medio_rec_efectivo,
            estado=Transaction.Estado.PENDIENTE,
        )

        with self.assertRaises(InsufficientCashBalanceError):
            TransactionService.process_cash_payment(
                transaction_obj=big_tx.id,
                shift=self.shift,
                cashier=self.cajero,
                is_cash_in=True,
                is_cash_out=True,
            )

        # Verificar integridad tras el rollback
        big_tx.refresh_from_db()
        self.assertEqual(big_tx.estado, Transaction.Estado.PENDIENTE)
        self.assertFalse(big_tx.is_completed)
        self.assertFalse(CashMovement.objects.filter(transaction=big_tx).exists())
        self.assertFalse(FacturaElectronica.objects.filter(transaction=big_tx).exists())
        self.assertFalse(ElectronicInvoice.objects.filter(transaction=big_tx).exists())

    def test_process_cash_payment_rejects_already_completed_tx(self):
        """Verifica que no se permita procesar el pago de una orden ya COMPLETADA."""
        tx = self._create_pending_tx()
        tx.mark_as_completed(user=self.cajero, save=True)

        with self.assertRaises(ValidationError) as ctx:
            TransactionService.process_cash_payment(
                transaction_obj=tx,
                shift=self.shift,
                cashier=self.cajero,
            )
        self.assertIn('estado', ctx.exception.message_dict)

    def test_process_cash_payment_rejects_cancelled_tx(self):
        """Verifica que no se permita procesar el pago de una orden CANCELADA."""
        tx = self._create_pending_tx()
        tx.mark_as_cancelled(motivo='Expirada por cliente', save=True)

        with self.assertRaises(ValidationError) as ctx:
            TransactionService.process_cash_payment(
                transaction_obj=tx,
                shift=self.shift,
                cashier=self.cajero,
            )
        self.assertIn('estado', ctx.exception.message_dict)

    def test_process_cash_payment_with_closed_shift_fails(self):
        """Verifica que un turno cerrado o no abierto impida procesar el pago."""
        # Cerrar el turno activo
        CashService.close_shift(
            shift=self.shift,
            counted_balances={},
            closed_by=self.cajero,
            closing_notes='Cierre para prueba',
        )

        tx = self._create_pending_tx()
        with self.assertRaises(CashShiftError):
            TransactionService.process_cash_payment(
                transaction_obj=tx,
                shift=self.shift,
                cashier=self.cajero,
            )

        tx.refresh_from_db()
        self.assertEqual(tx.estado, Transaction.Estado.PENDIENTE)

    def test_process_cash_payment_infer_open_shift(self):
        """
        Verifica que al no suministrar shift=None, se infiera automáticamente
        el turno abierto del cajero.
        """
        tx = self._create_pending_tx(monto_usd=Decimal('50.00'))

        completed_tx = TransactionService.process_cash_payment(
            transaction_obj=tx.id,
            shift=None,  # Inferencia
            cashier=self.cajero,
        )

        self.assertEqual(completed_tx.estado, Transaction.Estado.COMPLETADA)
        mov = CashMovement.objects.filter(transaction=completed_tx).first()
        self.assertEqual(mov.shift, self.shift)

    def test_process_cash_payment_with_register_instance_or_id(self):
        """
        Verifica que shift acepte una instancia de CashRegister o el ID numérico del turno.
        """
        # Por CashRegister
        tx1 = self._create_pending_tx(monto_usd=Decimal('10.00'))
        res1 = TransactionService.process_cash_payment(tx1, shift=self.register, cashier=self.cajero)
        self.assertEqual(res1.estado, Transaction.Estado.COMPLETADA)

        # Por ID numérico
        tx2 = self._create_pending_tx(monto_usd=Decimal('10.00'))
        res2 = TransactionService.process_cash_payment(tx2, shift=self.shift.id, cashier=self.cajero)
        self.assertEqual(res2.estado, Transaction.Estado.COMPLETADA)

    def test_process_cash_payment_without_invoice(self):
        """Verifica que emitir_factura=False omita la generación de comprobantes fiscales."""
        tx = self._create_pending_tx(monto_usd=Decimal('30.00'))
        completed = TransactionService.process_cash_payment(
            transaction_obj=tx,
            shift=self.shift,
            cashier=self.cajero,
            emitir_factura=False,
        )
        self.assertEqual(completed.estado, Transaction.Estado.COMPLETADA)
        self.assertFalse(FacturaElectronica.objects.filter(transaction=completed).exists())
        self.assertFalse(ElectronicInvoice.objects.filter(transaction=completed).exists())

    def test_process_cash_payment_invalid_transaction_identifier(self):
        """Verifica el manejo de error ante IDs de transacción inexistentes o inválidos."""
        with self.assertRaises(ValidationError) as ctx1:
            TransactionService.process_cash_payment(transaction_obj=99999999, shift=self.shift)
        self.assertIn('transaction', ctx1.exception.message_dict)

        with self.assertRaises(ValidationError) as ctx2:
            TransactionService.process_cash_payment(transaction_obj='codigo-invalido', shift=self.shift)
        self.assertIn('transaction', ctx2.exception.message_dict)

    def test_process_cash_payment_via_apps_transactions_namespace(self):
        """
        Verifica que el servicio sea accesible y funcional mediante el namespace transactions.services.
        """
        from transactions.services import TransactionService as TxService

        tx = self._create_pending_tx(monto_usd=Decimal('40.00'))
        completed = TxService.process_cash_payment(
            transaction_obj=tx,
            shift=self.shift,
            cashier=self.cajero,
        )
        self.assertEqual(completed.estado, Transaction.Estado.COMPLETADA)
        self.assertEqual(completed.pasarela_pago, 'EFECTIVO')
