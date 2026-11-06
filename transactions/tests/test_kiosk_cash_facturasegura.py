"""
Pruebas Unitarias y de Integración para KioskCashService y FacturaSeguraClient (SCRUM-122).

Cubre:
1. Protocolo de cuota y cliente real FacturaSeguraClient.
2. Reserva blindada inviolable de 10 pruebas para QA ante agotamiento comercial.
3. Aceptación física de billetes y validación de denominaciones permitidas por divisa.
4. Algoritmo de dispensación óptima según saldo disponible en casetes del tótem.
5. Manejo de excepciones por saldo insuficiente o cambio exacto imposible.
6. Generación de comprobante de caja con sellos SHA-256 y código QR SVG nativo.
7. Endpoints API REST y vistas web de efectivo y cuotas.
8. Flujo integrado de transacciones en Kiosco con efectivo y FacturaSegura.
"""

from decimal import Decimal
import json
import uuid
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate, SegmentCommission
from transactions.facturasegura_client import (
    FacturaSeguraApiError,
    FacturaSeguraClient,
    QuotaShieldExhaustedError,
    TestQuotaExhaustedError,
)
from transactions.kiosk_cash_service import (
    DENOMINACIONES_PERMITIDAS,
    CannotDispenseExactChangeError,
    InsufficientTotemBalanceError,
    InvalidBillDenominationError,
    KioskCashError,
    KioskCashService,
    TotemCassetteCapacityExceededError,
    generate_qr_svg,
)
from transactions.models import (
    ElectronicInvoice,
    FacturaSeguraConfig,
    KioskCashOperation,
    KioskCashVault,
    KioskTotem,
    Transaction,
)

User = get_user_model()


class FacturaSeguraClientAndQuotaTests(TestCase):
    """
    Pruebas para el cliente FacturaSegura y el protocolo de cuota con reserva blindada de 10 pruebas.
    """

    def setUp(self):
        self.client_fs = FacturaSeguraClient()
        self.config = FacturaSeguraConfig.get_config()
        self.config.total_quota = 100
        self.config.used_quota = 0
        self.config.test_quota_reserved = 10
        self.config.test_quota_used = 0
        self.config.save()

        # Configurar datos básicos de transacción
        self.cliente = Cliente.objects.create(
            nombre='Empresa FacturaSegura S.A.',
            documento_ruc='80012345-7',
            correo='facturacion@fs.com.py',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
            is_active=True,
        )
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='Gs', decimals=0, is_active=True)
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2, is_active=True)
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.00'),
            sell_rate=Decimal('7900.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )
        self.entidad = EntidadFinanciera.objects.create(nombre='Banco Test FS', tipo='BANCO', activo=True)
        self.medio_pago = PaymentMethod.objects.create(
            cliente=self.cliente, tipo_medio='EFECTIVO', entidad_bancaria=self.entidad,
            numero_cuenta='001', titular='Empresa Test', activo=True
        )
        self.medio_acred = ReceivingMethod.objects.create(
            cliente=self.cliente, entidad_bancaria=self.entidad,
            tipo_cuenta='AHORRO', numero_cuenta='002', titular='Empresa Test', activo=True
        )
        self.tx = Transaction.objects.create(
            cliente=self.cliente,
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
            base_currency=self.usd,
            target_currency=self.pyg,
            exchange_rate=self.rate,
            tasa_base=Decimal('7900.00'),
            comision_segmento=Decimal('0.00'),
            tasa_neta=Decimal('7900.00'),
            monto_origen=Decimal('100.00'),
            monto_destino=Decimal('790000.00'),
            medio_pago_origen=self.medio_pago,
            medio_acreditacion_destino=self.medio_acred,
            estado=Transaction.Estado.COMPLETADA,
            fecha_pago=timezone.now(),
        )

    def test_default_config_creation_and_quota_calculation(self):
        """Verifica que la configuración se inicialice con los valores requeridos y cuota operativa disponible."""
        cuota = self.client_fs.consultar_cuota()
        self.assertEqual(cuota['total_quota'], 100)
        self.assertEqual(cuota['test_quota_reserved'], 10)
        self.assertEqual(cuota['test_quota_available'], 10)
        # Operativa disponible: 100 - 0 - 10 = 90
        self.assertEqual(cuota['operational_quota_available'], 90)
        self.assertFalse(cuota['is_operational_quota_exhausted'])
        self.assertFalse(cuota['is_test_quota_exhausted'])

    def test_consume_operational_quota(self):
        """Verifica que el consumo ordinario descuente de la cuota operativa sin alterar la de prueba."""
        disp = self.config.consume_quota(is_test=False)
        self.config.refresh_from_db()
        self.assertEqual(self.config.used_quota, 1)
        self.assertEqual(self.config.test_quota_used, 0)
        self.assertEqual(self.config.operational_quota_available, 89)
        self.assertEqual(self.config.test_quota_available, 10)

    def test_operational_quota_exhaustion_blocks_with_shield_error(self):
        """
        Verifica que al agotarse el saldo comercial (alcanzando el piso de las 10 reservadas),
        cualquier emisión operativa ordinaria sea bloqueada para proteger las 10 pruebas.
        """
        # Agotar exactamente el cupo operativo (usadas = 90 de 100)
        self.config.used_quota = 90
        self.config.save()
        self.assertEqual(self.config.operational_quota_available, 0)
        self.assertTrue(self.config.is_operational_quota_exhausted)
        self.assertEqual(self.config.test_quota_available, 10)

        # Intentar llamada comercial debe disparar QuotaShieldExhaustedError
        with self.assertRaises(QuotaShieldExhaustedError) as ctx:
            self.config.consume_quota(is_test=False)
        self.assertIn("blindadas exclusivamente para pruebas", str(ctx.exception))

    def test_shielded_10_tests_can_be_executed_when_operational_exhausted(self):
        """
        Verifica que incluso con la cuota operativa totalmente agotada, las 10 pruebas
        blindadas se puedan ejecutar de forma garantizada.
        """
        self.config.used_quota = 90
        self.config.save()
        self.assertEqual(self.config.operational_quota_available, 0)

        # Invocación con is_test=True debe tener éxito
        restante = self.config.consume_quota(is_test=True)
        self.config.refresh_from_db()
        self.assertEqual(self.config.test_quota_used, 1)
        self.assertEqual(restante, 9)
        self.assertEqual(self.config.test_quota_available, 9)

    def test_depleting_all_10_test_units_raises_test_quota_exhausted(self):
        """Verifica que si se consumen las 10 pruebas blindadas, la 11ª llamada de prueba sea rechazada."""
        self.config.test_quota_used = 10
        self.config.save()
        self.assertTrue(self.config.is_test_quota_exhausted)

        with self.assertRaises(TestQuotaExhaustedError) as ctx:
            self.config.consume_quota(is_test=True)
        self.assertIn("Reserva blindada de 10 pruebas agotada", str(ctx.exception))

    def test_emitir_factura_creates_certified_response_and_updates_model(self):
        """Verifica la emisión a través del PAC FacturaSegura, generando CDC y protocolo."""
        resp = self.client_fs.emitir_factura(self.tx, is_test=True)
        self.assertTrue(resp['success'])
        self.assertEqual(resp['estado_sifen'], 'APROBADO')
        self.assertEqual(len(resp['cdc']), 44)
        self.assertIn('001-001-', resp['numero_factura'])
        self.assertTrue(resp['is_test_emission'])

        # Verificar persistencia en base de datos
        inv = ElectronicInvoice.objects.get(transaction=self.tx)
        self.assertEqual(inv.cdc, resp['cdc'])
        self.assertEqual(inv.estado, ElectronicInvoice.EstadoSifen.APROBADO)

    def test_consultar_factura_and_cancelar_factura(self):
        """Verifica la consulta y posterior anulación tributaria de una factura."""
        emit_resp = self.client_fs.emitir_factura(self.tx, is_test=True)
        cdc = emit_resp['cdc']

        # Consultar estado
        consulta = self.client_fs.consultar_factura(cdc, is_test=True)
        self.assertTrue(consulta['success'])
        self.assertEqual(consulta['cdc'], cdc)
        self.assertEqual(consulta['estado_sifen'], 'APROBADO')

        # Cancelar factura
        canc = self.client_fs.cancelar_factura(cdc, motivo="Error en cotización solicitada por cliente", is_test=True)
        self.assertTrue(canc['success'])
        self.assertEqual(canc['estado'], ElectronicInvoice.EstadoSifen.CANCELADO)

        # Verificar actualización en base de datos
        inv = ElectronicInvoice.objects.get(cdc=cdc)
        self.assertEqual(inv.estado, ElectronicInvoice.EstadoSifen.CANCELADO)


class KioskCashServiceTests(TestCase):
    """
    Pruebas para el servicio de efectivo físico en el tótem: aceptación, casetes y dispensación.
    """

    def setUp(self):
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='Gs', decimals=0, is_active=True)
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2, is_active=True)
        self.totem = KioskCashService.get_or_create_default_totem('TOTEM-TEST')

    def test_allowed_denominations_catalog(self):
        """Verifica que el catálogo de denominaciones permitidas contenga las series oficiales de PYG y USD."""
        self.assertIn('PYG', DENOMINACIONES_PERMITIDAS)
        self.assertIn(100000, DENOMINACIONES_PERMITIDAS['PYG'])
        self.assertIn(2000, DENOMINACIONES_PERMITIDAS['PYG'])
        self.assertIn('USD', DENOMINACIONES_PERMITIDAS)
        self.assertIn(100, DENOMINACIONES_PERMITIDAS['USD'])
        self.assertIn(1, DENOMINACIONES_PERMITIDAS['USD'])

    def test_validate_bills_valid_inputs(self):
        """Verifica la validación correcta de billetes ingresados en lista o diccionario."""
        # Lista de billetes en PYG
        total, breakdown = KioskCashService.validate_bills('PYG', [100000, 50000, 100000])
        self.assertEqual(total, Decimal('250000'))
        self.assertEqual(breakdown, {100000: 2, 50000: 1})

        # Diccionario de billetes en USD
        total_usd, bd_usd = KioskCashService.validate_bills('USD', {'100': 3, '50': 1, '20': 2})
        self.assertEqual(total_usd, Decimal('390'))
        self.assertEqual(bd_usd, {100: 3, 50: 1, 20: 2})

    def test_validate_bills_invalid_denomination_rejected(self):
        """Verifica que billetes no autorizados o inexistentes disparen InvalidBillDenominationError."""
        # 3.000 Gs no existe en Paraguay
        with self.assertRaises(InvalidBillDenominationError):
            KioskCashService.validate_bills('PYG', [100000, 3000])

        # 3 USD no existe
        with self.assertRaises(InvalidBillDenominationError):
            KioskCashService.validate_bills('USD', [3])

    def test_accept_cash_increments_cassette_and_creates_operation(self):
        """Verifica que aceptar efectivo incremente el stock del casete y registre la operación con hash SHA-256."""
        vault_100k = KioskCashVault.objects.get(totem=self.totem, currency=self.pyg, denominacion=Decimal('100000'))
        initial_qty = vault_100k.cantidad

        op = KioskCashService.accept_cash(self.totem, self.pyg, [100000, 100000])
        self.assertEqual(op.tipo_operacion, KioskCashOperation.TipoOperacion.ACEPTACION)
        self.assertEqual(op.monto_total, Decimal('200000'))
        self.assertEqual(op.total_billetes, 2)
        self.assertTrue(len(op.hash_verificacion) == 64)
        self.assertIn('https://globalexchange.com.py/kiosk/verify/', op.codigo_qr)

        vault_100k.refresh_from_db()
        self.assertEqual(vault_100k.cantidad, initial_qty + 2)

    def test_accept_cash_exceeding_capacity_raises_error(self):
        """Verifica que si la cantidad supera la capacidad máxima del casete se rechace la operación."""
        vault_100k = KioskCashVault.objects.get(totem=self.totem, currency=self.pyg, denominacion=Decimal('100000'))
        vault_100k.cantidad = 1999
        vault_100k.capacidad_maxima = 2000
        vault_100k.save()

        with self.assertRaises(TotemCassetteCapacityExceededError):
            KioskCashService.accept_cash(self.totem, self.pyg, [100000, 100000])

    def test_calculate_dispense_breakdown_optimal(self):
        """Verifica que el algoritmo calcule el desglose óptimo minimizando la cantidad de piezas físicas."""
        # Dispensar 270.000 Gs debe usar 2x100k, 1x50k, 1x20k (4 billetes)
        plan = KioskCashService.calculate_dispense_breakdown(self.totem, self.pyg, Decimal('270000'))
        self.assertEqual(plan, {100000: 2, 50000: 1, 20000: 1})

    def test_dispense_cash_decrements_cassette_and_creates_operation(self):
        """Verifica que dispensar efectivo descuente los billetes de los casetes y genere el comprobante."""
        vault_50 = KioskCashVault.objects.get(totem=self.totem, currency=self.usd, denominacion=Decimal('50'))
        vault_20 = KioskCashVault.objects.get(totem=self.totem, currency=self.usd, denominacion=Decimal('20'))
        init_50 = vault_50.cantidad
        init_20 = vault_20.cantidad

        op = KioskCashService.dispense_cash(self.totem, self.usd, Decimal('70.00'))
        self.assertEqual(op.tipo_operacion, KioskCashOperation.TipoOperacion.DISPENSACION)
        self.assertEqual(op.monto_total, Decimal('70.00'))
        self.assertEqual(op.desglose_billetes, {50: 1, 20: 1})

        vault_50.refresh_from_db()
        vault_20.refresh_from_db()
        self.assertEqual(vault_50.cantidad, init_50 - 1)
        self.assertEqual(vault_20.cantidad, init_20 - 1)

    def test_dispense_cash_insufficient_balance_raises_error(self):
        """Verifica que solicitar más dinero del existente en el tótem dispare InsufficientTotemBalanceError."""
        with self.assertRaises(InsufficientTotemBalanceError):
            KioskCashService.dispense_cash(self.totem, self.usd, Decimal('999999999.00'))

    def test_dispense_cash_impossible_change_raises_error(self):
        """Verifica que solicitar una fracción imposible (ej. 7.50 USD) dispare CannotDispenseExactChangeError."""
        with self.assertRaises(CannotDispenseExactChangeError):
            KioskCashService.dispense_cash(self.totem, self.usd, Decimal('7.50'))

    def test_generate_cash_receipt_structure(self):
        """Verifica que el recibo de caja contenga los campos requeridos y el código QR en SVG nativo."""
        op = KioskCashService.dispense_cash(self.totem, self.usd, Decimal('100.00'))
        receipt = KioskCashService.generate_cash_receipt(op)
        self.assertEqual(receipt['uuid'], str(op.uuid))
        self.assertEqual(receipt['totem_codigo'], self.totem.codigo)
        self.assertEqual(receipt['moneda_codigo'], 'USD')
        self.assertIn('<svg', receipt['qr_svg'])
        self.assertEqual(len(receipt['hash_verificacion']), 64)
        self.assertIn('hash=', receipt['codigo_qr'].lower())

    def test_get_totem_inventory_structure(self):
        """Verifica que el informe de inventario del tótem devuelva el balance por moneda y casetes."""
        inv = KioskCashService.get_totem_inventory(self.totem)
        self.assertEqual(inv['totem_codigo'], self.totem.codigo)
        self.assertEqual(inv['estado'], 'ONLINE')
        self.assertTrue(len(inv['currencies']) >= 2)


class KioskCashApiAndIntegrationTests(TestCase):
    """
    Pruebas para los endpoints REST del subsistema de efectivo y FacturaSegura en Kiosco.
    """

    def setUp(self):
        self.client = Client()
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='Gs', decimals=0, is_active=True)
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2, is_active=True)
        self.totem = KioskCashService.get_or_create_default_totem('TOTEM-01')
        self.config_fs = FacturaSeguraConfig.get_config()
        self.config_fs.total_quota = 500
        self.config_fs.used_quota = 0
        self.config_fs.test_quota_reserved = 10
        self.config_fs.test_quota_used = 0
        self.config_fs.save()

        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.00'),
            sell_rate=Decimal('7900.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )
        self.comm = SegmentCommission.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            commission_percentage=Decimal('0.00'),
            fixed_fee=Decimal('0.00'),
            spread_discount_percentage=Decimal('0.00'),
            is_active=True,
        )
        self.cliente = Cliente.objects.create(
            nombre='Carlos Kiosk Cash',
            documento_ruc='1234567-8',
            correo='carlos.cash@kiosk.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=True,
        )

    def test_api_cash_status(self):
        """Verifica que el endpoint /kiosk/api/cash/status/ retorne status HTTP 200 con el inventario."""
        response = self.client.get(reverse('kiosk:api_cash_status'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['totem']['totem_codigo'], 'TOTEM-01')
        self.assertIn('allowed_denominations', data)

    def test_api_cash_accept_success(self):
        """Verifica la aceptación de billetes vía API REST."""
        response = self.client.post(reverse('kiosk:api_cash_accept'), {
            'currency': 'PYG',
            'bills': json.dumps([100000, 50000]),
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(Decimal(str(data['operation']['monto_total'])), Decimal('150000'))
        self.assertIn('<svg', data['operation']['qr_svg'])

    def test_api_cash_accept_invalid_rejected(self):
        """Verifica que billetes no permitidos retornen HTTP 400 con mensaje de error."""
        response = self.client.post(reverse('kiosk:api_cash_accept'), {
            'currency': 'PYG',
            'bills': json.dumps([3000]),
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Denominación de billete 3000 no permitida', data['error'])

    def test_api_cash_dispense_success(self):
        """Verifica la dispensación de billetes vía API REST."""
        response = self.client.post(reverse('kiosk:api_cash_dispense'), {
            'currency': 'USD',
            'amount': '150',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(Decimal(str(data['operation']['monto_total'])), Decimal('150'))
        self.assertEqual(data['operation']['tipo_operacion'], 'DISPENSACION')

    def test_api_cash_receipt_json_and_html(self):
        """Verifica la consulta del comprobante de efectivo en formato JSON y vista HTML imprimible."""
        op = KioskCashService.dispense_cash(self.totem, self.usd, Decimal('100.00'))

        # API JSON
        url_json = reverse('kiosk:api_cash_receipt', kwargs={'uuid': op.uuid})
        res_json = self.client.get(url_json)
        self.assertEqual(res_json.status_code, 200)
        self.assertEqual(res_json.json()['receipt']['uuid'], str(op.uuid))

        # Vista HTML
        url_html = reverse('kiosk:cash_receipt', kwargs={'uuid': op.uuid})
        res_html = self.client.get(url_html)
        self.assertEqual(res_html.status_code, 200)
        self.assertTemplateUsed(res_html, 'kiosk/cash_receipt.html')
        self.assertContains(res_html, 'COMPROBANTE DE DISPENSACIÓN')
        self.assertContains(res_html, op.totem.codigo)
        self.assertContains(res_html, '<svg')

    def test_api_facturasegura_cuota(self):
        """Verifica el endpoint de consulta del protocolo de cuota y reserva blindada."""
        response = self.client.get(reverse('kiosk:api_facturasegura_cuota'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['quota']['total_quota'], 500)
        self.assertEqual(data['quota']['test_quota_reserved'], 10)
        self.assertTrue(data['quota']['shield_active'])

    def test_kiosk_transact_full_flow_with_cash_and_facturasegura(self):
        """
        Prueba de integración integral de liquidación en Kiosco:
        - Aceptación física de billetes.
        - Dispensación de divisas en efectivo.
        - Emisión certificada de KuDE con FacturaSegura.
        - Retorno de URLs de comprobantes fiscales y tickets de caja.
        """
        response = self.client.post(reverse('kiosk:api_transact'), {
            'currency': 'USD',
            'amount': '100',
            'operation_type': 'BUY',
            'customer_id': self.cliente.id,
            'customer_ruc': self.cliente.documento_ruc,
            'is_test': 'true',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('TX-', data['codigo_referencia'])
        self.assertEqual(len(data['cdc']), 44)
        self.assertIsNotNone(data['cash_receipt_url'])

        # Verificar transacción en BD
        tx = Transaction.objects.get(id=data['transaction_id'])
        self.assertEqual(tx.estado, Transaction.Estado.COMPLETADA)
        self.assertEqual(tx.pasarela_pago, 'KIOSK_EFECTIVO')

        # Verificar que se crearon los movimientos físicos de efectivo
        ops = KioskCashOperation.objects.filter(transaction=tx)
        self.assertTrue(ops.filter(tipo_operacion=KioskCashOperation.TipoOperacion.DISPENSACION).exists())

    def test_kiosk_transact_registers_cash_movement_and_banknote_inventory(self):
        """
        Verifica que una operación en el Kiosco impacta la simulación de Caja Registradora:
        - Creación o reutilización de CashRegister asociada al tótem (CAJA-TOTEM-01).
        - Registro de CashMovement de entrada y salida vinculados a la transacción.
        - Registro de BanknoteMovement (EXCHANGE_IN y EXCHANGE_OUT).
        - Actualización de inventario físico de billetes por denominación (BanknoteInventory).
        """
        from apps.cash.models import CashMovement, CashRegister, MovementFlow
        from apps.cash.inventory_models import BanknoteMovement, BanknoteMovementType

        response = self.client.post(reverse('kiosk:api_transact'), {
            'currency': 'USD',
            'amount': '100',
            'operation_type': 'BUY',
            'customer_id': self.cliente.id,
            'customer_ruc': self.cliente.documento_ruc,
            'is_test': 'true',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        tx = Transaction.objects.get(id=data['transaction_id'])

        # 1. Verificar Caja Registradora del Kiosco
        register = CashRegister.objects.get(register_code='CAJA-TOTEM-01')
        self.assertTrue(register.is_open)

        # 2. Verificar movimientos de efectivo contables (CashMovement)
        movements = CashMovement.objects.filter(transaction=tx)
        self.assertEqual(movements.count(), 2)
        self.assertTrue(movements.filter(flow=MovementFlow.IN).exists())
        self.assertTrue(movements.filter(flow=MovementFlow.OUT).exists())

        # 3. Verificar movimientos inmutables de billetes por denominación (BanknoteMovement)
        bn_movements = BanknoteMovement.objects.filter(transaction=tx)
        self.assertTrue(bn_movements.exists())
        self.assertTrue(bn_movements.filter(movement_type=BanknoteMovementType.EXCHANGE_IN).exists())
        self.assertTrue(bn_movements.filter(movement_type=BanknoteMovementType.EXCHANGE_OUT).exists())

