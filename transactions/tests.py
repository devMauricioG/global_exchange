"""
Suite de pruebas unitarias para la aplicación de transacciones cambiarias (transactions).

Cubre la creación del modelo :class:`Transaction`, validaciones personalizadas del
método ``clean()``, autogeneración de ``codigo_referencia``, transiciones de estado
(``mark_as_completed``, ``mark_as_cancelled``), propiedades derivadas, representación
en cadena, configuración del administrador Django, servicios de negocio (:class:`TransactionService`)
y vistas web / API de confirmación y listado de órdenes.
"""

from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate, OperationLimit
from rates.services import QuoteFreezeService, RateCalculationService
from transactions.admin import TransactionAdmin
from transactions.forms import TransactionOrderForm
from transactions.models import Transaction
from transactions.services import TransactionService


class TransactionTestMixin:
    """
    Mixin con la creación de datos de prueba compartidos por los TestCase de transacciones.
    """

    @classmethod
    def setUpTestData(cls):
        """Crea las dependencias de datos maestros reutilizables."""
        # Monedas
        cls.usd = Currency.objects.create(
            code='USD', name='Dólar Estadounidense', symbol='$', decimals=2, is_active=True
        )
        cls.pyg = Currency.objects.create(
            code='PYG', name='Guaraní Paraguayo', symbol='₲', decimals=0, is_active=True
        )
        cls.eur = Currency.objects.create(
            code='EUR', name='Euro', symbol='€', decimals=2, is_active=True
        )

        # Cliente
        cls.cliente = Cliente.objects.create(
            nombre='Juan Pérez',
            documento_ruc='1234567-8',
            correo='juan.perez@test.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
        )
        # Segundo cliente para validaciones de pertenencia
        cls.otro_cliente = Cliente.objects.create(
            nombre='María López',
            documento_ruc='8765432-1',
            correo='maria.lopez@test.com',
            segmentacion=Cliente.Segmentacion.MAYORISTA,
        )

        # User autenticado vinculado
        cls.user = User.objects.create_user(
            username='juanperez',
            email='juan.perez@test.com',
            password='Password123!',
        )

        # Entidad financiera
        cls.banco = EntidadFinanciera.objects.create(
            nombre='Banco Test', tipo='BANCO',
        )

        # Medios de pago y acreditación cliente
        cls.medio_pago = PaymentMethod.objects.create(
            cliente=cls.cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=cls.banco,
            numero_cuenta='12345678',
            titular='Juan Pérez',
            documento_titular='1234567-8',
            tipo_cuenta_bancaria='AHORRO',
            es_predeterminado=True,
            activo=True,
        )
        cls.medio_acreditacion = ReceivingMethod.objects.create(
            cliente=cls.cliente,
            entidad_bancaria=cls.banco,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO,
            numero_cuenta='87654321',
            titular='Juan Pérez',
            documento_titular='1234567-8',
            es_predeterminado=True,
            activo=True,
        )

        # Medios de pago y acreditación otro cliente
        cls.otro_medio_pago = PaymentMethod.objects.create(
            cliente=cls.otro_cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=cls.banco,
            numero_cuenta='99999999',
            titular='María López',
            documento_titular='8765432-1',
            tipo_cuenta_bancaria='CORRIENTE',
            activo=True,
        )
        cls.otro_medio_acreditacion = ReceivingMethod.objects.create(
            cliente=cls.otro_cliente,
            entidad_bancaria=cls.banco,
            tipo_cuenta=ReceivingMethod.TipoCuenta.CORRIENTE,
            numero_cuenta='88888888',
            titular='María López',
            documento_titular='8765432-1',
            activo=True,
        )

        # Exchange Rate oficial activa
        cls.exchange_rate = ExchangeRate.objects.create(
            base_currency=cls.usd,
            target_currency=cls.pyg,
            buy_rate=Decimal('7500.00'),
            sell_rate=Decimal('7600.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )

    def _build_valid_transaction_data(self, **overrides) -> dict:
        """Helper para construir un diccionario de datos válidos."""
        data = {
            'cliente': self.cliente,
            'tipo_operacion': Transaction.TipoOperacion.COMPRA,
            'base_currency': self.usd,
            'target_currency': self.pyg,
            'tasa_base': Decimal('7600.000000'),
            'comision_segmento': Decimal('0.00'),
            'tasa_neta': Decimal('7600.000000'),
            'monto_origen': Decimal('760000.00'),
            'monto_destino': Decimal('100.00'),
            'medio_pago_origen': self.medio_pago,
            'medio_acreditacion_destino': self.medio_acreditacion,
            'estado': Transaction.Estado.PENDIENTE,
        }
        data.update(overrides)
        return data


class TransactionModelTest(TransactionTestMixin, TestCase):
    """Pruebas del modelo Transaction."""

    def test_creacion_transaccion_exitosa(self):
        """Verifica la persistencia de una transacción válida."""
        data = self._build_valid_transaction_data()
        tx = Transaction.objects.create(**data)

        self.assertIsNotNone(tx.pk)
        self.assertTrue(tx.codigo_referencia.startswith('TX-'))
        self.assertEqual(tx.estado, Transaction.Estado.PENDIENTE)

    def test_clean_monedas_iguales_lanza_error(self):
        """clean() debe fallar si base_currency es igual a target_currency."""
        data = self._build_valid_transaction_data(target_currency=self.usd)
        tx = Transaction(**data)

        with self.assertRaises(ValidationError) as ctx:
            tx.clean()
        self.assertIn('target_currency', ctx.exception.message_dict)

    def test_clean_monto_origen_no_positivo_lanza_error(self):
        """monto_origen <= 0 debe lanzar ValidationError."""
        data = self._build_valid_transaction_data(monto_origen=Decimal('0.00'))
        tx = Transaction(**data)

        with self.assertRaises(ValidationError) as ctx:
            tx.clean()
        self.assertIn('monto_origen', ctx.exception.message_dict)

    def test_clean_medio_pago_ajeno_lanza_error(self):
        """medio_pago de otro cliente debe lanzar ValidationError."""
        data = self._build_valid_transaction_data(medio_pago_origen=self.otro_medio_pago)
        tx = Transaction(**data)

        with self.assertRaises(ValidationError) as ctx:
            tx.clean()
        self.assertIn('medio_pago_origen', ctx.exception.message_dict)

    def test_mark_as_completed(self):
        """mark_as_completed cambia el estado a COMPLETADA."""
        data = self._build_valid_transaction_data()
        tx = Transaction.objects.create(**data)
        tx.mark_as_completed()
        tx.refresh_from_db()

        self.assertEqual(tx.estado, Transaction.Estado.COMPLETADA)
        self.assertTrue(tx.is_completed)

    def test_mark_as_cancelled(self):
        """mark_as_cancelled cambia el estado a CANCELADA con motivo."""
        data = self._build_valid_transaction_data()
        tx = Transaction.objects.create(**data)
        tx.mark_as_cancelled(motivo='Expiró plazo de pago')
        tx.refresh_from_db()

        self.assertEqual(tx.estado, Transaction.Estado.CANCELADA)
        self.assertIn('Expiró plazo de pago', tx.observaciones)


class TransactionServiceTest(TransactionTestMixin, TestCase):
    """Pruebas para el servicio transaccional TransactionService."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_create_order_from_live_quote_success(self):
        """Creación exitosa de transacción con cotización en vivo."""
        request = self.factory.get('/')
        request.user = self.user
        request.active_customer = self.cliente

        tx = TransactionService.create_order_from_live_quote(
            request=request,
            base_currency_code='USD',
            target_currency_code='PYG',
            amount=Decimal('100.00'),
            operation_type='BUY',
            is_source_base=True,
            medio_pago_id=self.medio_pago.id,
            medio_acreditacion_id=self.medio_acreditacion.id,
            cliente=self.cliente,
            usuario=self.user,
        )

        self.assertIsNotNone(tx.id)
        self.assertEqual(tx.estado, Transaction.Estado.PENDIENTE)
        self.assertEqual(tx.cliente, self.cliente)
        self.assertEqual(tx.monto_destino, Decimal('100.00'))
        self.assertEqual(tx.monto_origen, Decimal('760000.00'))

    def test_create_order_from_frozen_quote_success(self):
        """Creación exitosa usando cotización congelada en sesión."""
        request = self.factory.get('/')
        request.user = self.user
        request.active_customer = self.cliente
        request.session = {}

        # Simular cálculo y congelamiento en sesión
        calc = RateCalculationService.calculate_quotation(
            exchange_rate=self.exchange_rate,
            segment_or_customer=self.cliente,
            amount=Decimal('200.00'),
            operation_type='BUY',
        )
        frozen = QuoteFreezeService.freeze_quote(request, calc)
        token = frozen['token']

        tx = TransactionService.create_order_from_frozen_quote(
            request=request,
            token=token,
            medio_pago_id=self.medio_pago.id,
            medio_acreditacion_id=self.medio_acreditacion.id,
            cliente=self.cliente,
            usuario=self.user,
        )

        self.assertIsNotNone(tx.id)
        self.assertEqual(tx.token_congelamiento, token)
        self.assertEqual(tx.estado, Transaction.Estado.PENDIENTE)
        # La cotización debe haber sido eliminada de la sesión
        self.assertNotIn('frozen_quote', request.session)

    def test_create_order_from_frozen_quote_invalid_token(self):
        """Falla al intentar usar un token inexistente."""
        request = self.factory.get('/')
        request.user = self.user
        request.active_customer = self.cliente
        request.session = {}

        with self.assertRaises(ValidationError) as ctx:
            TransactionService.create_order_from_frozen_quote(
                request=request,
                token='QTZ-INVALIDO99',
                medio_pago_id=self.medio_pago.id,
                medio_acreditacion_id=self.medio_acreditacion.id,
                cliente=self.cliente,
            )
        self.assertIn('token', ctx.exception.message_dict)

    def test_create_order_medio_pago_ajeno_lanza_error(self):
        """Falla si el medio de pago pertenece a otro cliente."""
        request = self.factory.get('/')
        request.user = self.user
        request.active_customer = self.cliente

        with self.assertRaises(ValidationError) as ctx:
            TransactionService.create_order_from_live_quote(
                request=request,
                base_currency_code='USD',
                target_currency_code='PYG',
                amount=Decimal('100.00'),
                operation_type='BUY',
                is_source_base=True,
                medio_pago_id=self.otro_medio_pago.id,
                medio_acreditacion_id=self.medio_acreditacion.id,
                cliente=self.cliente,
            )
        self.assertIn('medio_pago_origen', ctx.exception.message_dict)


class TransactionViewsTest(TransactionTestMixin, TestCase):
    """Pruebas de integración para las Vistas Web y API de Transacciones."""

    def setUp(self):
        self.client.force_login(self.user)

    def test_transaction_create_view_get(self):
        """GET /transactions/create/ renderiza el formulario de confirmación."""
        url = reverse('transactions:create') + '?base=USD&target=PYG&amount=100&operation_type=BUY'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/transaction_create.html')
        self.assertIn('form', response.context)
        self.assertIn('quote_data', response.context)

    def test_transaction_confirm_view_post_success(self):
        """POST /transactions/confirm/ registra la orden y redirige al detalle."""
        url = reverse('transactions:confirm')
        data = {
            'base_currency_code': 'USD',
            'target_currency_code': 'PYG',
            'amount': '100.00',
            'operation_type': 'BUY',
            'is_source_base': 'true',
            'medio_pago_origen': self.medio_pago.id,
            'medio_acreditacion_destino': self.medio_acreditacion.id,
            'observaciones': 'Prueba POST confirmación',
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        tx = Transaction.objects.latest('id')
        self.assertRedirects(response, reverse('transactions:detail', kwargs={'pk': tx.pk}))
        self.assertEqual(tx.observaciones, 'Prueba POST confirmación')

    def test_transaction_detail_view(self):
        """GET /transactions/<pk>/ visualiza el detalle de la transacción."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data())
        url = reverse('transactions:detail', kwargs={'pk': tx.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/transaction_detail.html')
        self.assertEqual(response.context['transaction'].id, tx.id)

    def test_transaction_list_view(self):
        """GET /transactions/ lista las operaciones filtrables."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data())
        url = reverse('transactions:list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/transaction_list.html')
        self.assertEqual(len(response.context['transactions']), 1)

    def test_transaction_api_create_view_success(self):
        """POST /transactions/api/create/ genera la orden vía JSON REST API."""
        url = reverse('transactions:api_create')
        payload = {
            'base_currency_code': 'USD',
            'target_currency_code': 'PYG',
            'amount': 150.00,
            'operation_type': 'BUY',
            'is_source_base': True,
            'medio_pago_id': self.medio_pago.id,
            'medio_acreditacion_id': self.medio_acreditacion.id,
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertTrue(res_json['success'])
        self.assertIn('codigo_referencia', res_json['transaction'])

    def test_is_transaction_expired(self):
        """is_transaction_expired detecta si pasaron más de 5 minutos desde la creación."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data(
            token_congelamiento='QTZ-TEST1234'
        ))
        self.assertFalse(TransactionService.is_transaction_expired(tx))

        # Simular transcurso del tiempo de 6 minutos (360s)
        tx.created_at = timezone.now() - timezone.timedelta(seconds=360)
        tx.save(update_fields=['created_at'])

        self.assertTrue(TransactionService.is_transaction_expired(tx))

    def test_cancel_expired_transactions_batch(self):
        """cancel_expired_transactions cancela masivamente las órdenes vencidas."""
        tx_recent = Transaction.objects.create(**self._build_valid_transaction_data())
        tx_old = Transaction.objects.create(**self._build_valid_transaction_data(
            token_congelamiento='QTZ-OLD9999'
        ))
        tx_old.created_at = timezone.now() - timezone.timedelta(seconds=400)
        tx_old.save(update_fields=['created_at'])

        count = TransactionService.cancel_expired_transactions()
        self.assertEqual(count, 1)

        tx_old.refresh_from_db()
        tx_recent.refresh_from_db()

        self.assertEqual(tx_old.estado, Transaction.Estado.CANCELADA)
        self.assertEqual(tx_recent.estado, Transaction.Estado.PENDIENTE)

    def test_cancel_transaction_by_customer_success(self):
        """cancel_transaction_by_customer anula manualmente la orden pendiente."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data())
        updated_tx = TransactionService.cancel_transaction_by_customer(
            transaction_id=tx.id,
            cliente=self.cliente,
            usuario=self.user,
            motivo='Anulación voluntaria',
        )

        self.assertEqual(updated_tx.estado, Transaction.Estado.CANCELADA)
        self.assertIn('Anulación voluntaria', updated_tx.observaciones)

    def test_cancel_transaction_by_customer_idor_prevention(self):
        """Falla al intentar cancelar una transacción perteneciente a otro cliente."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data(
            cliente=self.otro_cliente,
            medio_pago_origen=self.otro_medio_pago,
            medio_acreditacion_destino=self.otro_medio_acreditacion,
        ))

        with self.assertRaises(ValidationError) as ctx:
            TransactionService.cancel_transaction_by_customer(
                transaction_id=tx.id,
                cliente=self.cliente,
            )
        self.assertIn('cliente', ctx.exception.message_dict)

    def test_cancel_transaction_by_customer_already_completed(self):
        """Falla si la transacción ya está COMPLETADA."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data(
            estado=Transaction.Estado.COMPLETADA
        ))

        with self.assertRaises(ValidationError) as ctx:
            TransactionService.cancel_transaction_by_customer(
                transaction_id=tx.id,
                cliente=self.cliente,
            )
        self.assertIn('estado', ctx.exception.message_dict)

    def test_cancel_view_post_success(self):
        """POST /transactions/<pk>/cancel/ anula la orden y redirige al detalle."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data())
        url = reverse('transactions:cancel', kwargs={'pk': tx.pk})
        response = self.client.post(url, {'motivo': 'Prueba cancelación web'})

        self.assertEqual(response.status_code, 302)
        tx.refresh_from_db()
        self.assertEqual(tx.estado, Transaction.Estado.CANCELADA)

    def test_cancel_api_view_post_success(self):
        """POST /transactions/api/<pk>/cancel/ anula la orden vía API JSON REST."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data())
        url = reverse('transactions:api_cancel', kwargs={'pk': tx.pk})
        payload = {'motivo': 'Prueba API cancel'}
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertTrue(res_json['success'])
        tx.refresh_from_db()
        self.assertEqual(tx.estado, Transaction.Estado.CANCELADA)
