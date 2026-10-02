"""
Suite de pruebas unitarias e integración para la aplicación de transacciones cambiarias (transactions).

Cubre exhaustivamente:
- Integridad y validaciones del modelo :class:`~transactions.models.Transaction` (código correlativo, clean(), restricciones de divisas y montos, transiciones de estado).
- Formulario de orden :class:`~transactions.forms.TransactionOrderForm` (filtrado por cliente activo y validaciones).
- Servicios transaccionales :class:`~transactions.services.TransactionService` (cotización en vivo, cotización congelada, integración con límites y comisiones, detección y cancelación por expiración temporal de 5 minutos, anulación manual y prevención IDOR).
- Vistas Web CBVs (:class:`~transactions.views.TransactionCreateView`, :class:`~transactions.views.TransactionConfirmView`, :class:`~transactions.views.TransactionDetailView`, :class:`~transactions.views.TransactionListView`, :class:`~transactions.views.TransactionReceiptView`, :class:`~transactions.views.TransactionCancelView`).
- Endpoints REST API JSON (:class:`~transactions.views.TransactionCreateApiView`, :class:`~transactions.views.TransactionCancelApiView`).
- Panel de administración :class:`~transactions.admin.TransactionAdmin`.
"""

from decimal import Decimal
import io
import json

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Cliente, CustomerUserAssignment
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate, OperationLimit, SegmentCommission
from rates.services import QuoteFreezeService, RateCalculationService
from transactions.admin import TransactionAdmin
from transactions.forms import TransactionOrderForm
from transactions.models import Transaction
from transactions.services import TransactionService

User = get_user_model()


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

        # Cliente 1 (Minorista)
        cls.cliente = Cliente.objects.create(
            nombre='Juan Pérez',
            documento_ruc='1234567-8',
            correo='juan.perez@test.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
        )
        cls.user = User.objects.create_user(
            username='juanperez',
            email='juan.perez@test.com',
            password='Password123!',
        )
        CustomerUserAssignment.objects.create(
            customer=cls.cliente,
            user=cls.user,
            is_primary_representative=True,
            is_active=True,
        )

        # Cliente 2 (Mayorista) para validaciones de pertenencia e IDOR
        cls.otro_cliente = Cliente.objects.create(
            nombre='María López',
            documento_ruc='8765432-1',
            correo='maria.lopez@test.com',
            segmentacion=Cliente.Segmentacion.MAYORISTA,
        )
        cls.otro_user = User.objects.create_user(
            username='marialopez',
            email='maria.lopez@test.com',
            password='Password123!',
        )
        CustomerUserAssignment.objects.create(
            customer=cls.otro_cliente,
            user=cls.otro_user,
            is_primary_representative=True,
            is_active=True,
        )

        # Entidad financiera
        cls.banco, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Test Transacciones',
            defaults={'tipo': EntidadFinanciera.TipoEntidad.BANCO, 'activo': True},
        )

        # Medios de pago y acreditación cliente 1
        cls.medio_pago = PaymentMethod.objects.create(
            cliente=cls.cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=cls.banco,
            numero_cuenta='12345678',
            titular='Juan Pérez',
            documento_titular='1234567-8',
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.AHORRO,
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

        # Medios de pago y acreditación cliente 2
        cls.otro_medio_pago = PaymentMethod.objects.create(
            cliente=cls.otro_cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=cls.banco,
            numero_cuenta='99999999',
            titular='María López',
            documento_titular='8765432-1',
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.CORRIENTE,
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

        # Tasa de cambio oficial activa USD/PYG
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
    """Pruebas del modelo Transaction y validaciones clean()."""

    def test_creacion_transaccion_exitosa(self):
        """Verifica la persistencia de una transacción válida y autogeneración de código."""
        data = self._build_valid_transaction_data()
        tx = Transaction.objects.create(**data)

        self.assertIsNotNone(tx.pk)
        self.assertTrue(tx.codigo_referencia.startswith('TX-'))
        self.assertEqual(tx.estado, Transaction.Estado.PENDIENTE)
        self.assertTrue(tx.is_pending)
        self.assertFalse(tx.is_completed)
        self.assertFalse(tx.is_cancelled)
        self.assertIn(tx.codigo_referencia, str(tx))
        self.assertIn('Juan Pérez', str(tx))

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

    def test_clean_monto_destino_no_positivo_lanza_error(self):
        """monto_destino <= 0 debe lanzar ValidationError."""
        data = self._build_valid_transaction_data(monto_destino=Decimal('-10.00'))
        tx = Transaction(**data)

        with self.assertRaises(ValidationError) as ctx:
            tx.clean()
        self.assertIn('monto_destino', ctx.exception.message_dict)

    def test_clean_tasa_base_no_positiva_lanza_error(self):
        """tasa_base <= 0 debe lanzar ValidationError."""
        data = self._build_valid_transaction_data(tasa_base=Decimal('0.00'))
        tx = Transaction(**data)

        with self.assertRaises(ValidationError) as ctx:
            tx.clean()
        self.assertIn('tasa_base', ctx.exception.message_dict)

    def test_clean_tasa_neta_no_positiva_lanza_error(self):
        """tasa_neta <= 0 debe lanzar ValidationError."""
        data = self._build_valid_transaction_data(tasa_neta=Decimal('-5.00'))
        tx = Transaction(**data)

        with self.assertRaises(ValidationError) as ctx:
            tx.clean()
        self.assertIn('tasa_neta', ctx.exception.message_dict)

    def test_clean_medio_pago_ajeno_lanza_error(self):
        """medio_pago de otro cliente debe lanzar ValidationError."""
        data = self._build_valid_transaction_data(medio_pago_origen=self.otro_medio_pago)
        tx = Transaction(**data)

        with self.assertRaises(ValidationError) as ctx:
            tx.clean()
        self.assertIn('medio_pago_origen', ctx.exception.message_dict)

    def test_clean_medio_acreditacion_ajeno_lanza_error(self):
        """medio_acreditacion de otro cliente debe lanzar ValidationError."""
        data = self._build_valid_transaction_data(medio_acreditacion_destino=self.otro_medio_acreditacion)
        tx = Transaction(**data)

        with self.assertRaises(ValidationError) as ctx:
            tx.clean()
        self.assertIn('medio_acreditacion_destino', ctx.exception.message_dict)

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
        self.assertTrue(tx.is_cancelled)
        self.assertIn('Expiró plazo de pago', tx.observaciones)

    def test_moneda_properties(self):
        """Propiedades moneda_origen y moneda_destino según tipo_operacion."""
        tx_compra = Transaction.objects.create(**self._build_valid_transaction_data(
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
        ))
        self.assertEqual(tx_compra.moneda_origen, self.pyg)
        self.assertEqual(tx_compra.moneda_destino, self.usd)

        tx_venta = Transaction.objects.create(**self._build_valid_transaction_data(
            tipo_operacion=Transaction.TipoOperacion.VENTA,
            monto_origen=Decimal('100.00'),
            monto_destino=Decimal('750000.00'),
        ))
        self.assertEqual(tx_venta.moneda_origen, self.usd)
        self.assertEqual(tx_venta.moneda_destino, self.pyg)


class TransactionOrderFormTest(TransactionTestMixin, TestCase):
    """Pruebas del formulario TransactionOrderForm."""

    def test_form_filters_querysets_by_cliente(self):
        """El formulario filtra los medios de pago y acreditación del cliente especificado."""
        form = TransactionOrderForm(cliente=self.cliente)
        pago_ids = list(form.fields['medio_pago_origen'].queryset.values_list('id', flat=True))
        acred_ids = list(form.fields['medio_acreditacion_destino'].queryset.values_list('id', flat=True))

        self.assertIn(self.medio_pago.id, pago_ids)
        self.assertNotIn(self.otro_medio_pago.id, pago_ids)
        self.assertIn(self.medio_acreditacion.id, acred_ids)
        self.assertNotIn(self.otro_medio_acreditacion.id, acred_ids)

    def test_form_valid_with_live_parameters(self):
        """Formulario válido con parámetros de cotización en vivo."""
        data = {
            'base_currency_code': 'USD',
            'target_currency_code': 'PYG',
            'amount': '100.00',
            'operation_type': 'BUY',
            'is_source_base': True,
            'medio_pago_origen': self.medio_pago.id,
            'medio_acreditacion_destino': self.medio_acreditacion.id,
            'observaciones': 'Nota de prueba',
        }
        form = TransactionOrderForm(data=data, cliente=self.cliente)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_invalid_missing_token_and_live_params(self):
        """Formulario inválido si no provee ni token ni datos completos de cotización."""
        data = {
            'medio_pago_origen': self.medio_pago.id,
            'medio_acreditacion_destino': self.medio_acreditacion.id,
        }
        form = TransactionOrderForm(data=data, cliente=self.cliente)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)


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

    def test_create_order_from_live_quote_sell_success(self):
        """Creación exitosa de transacción de VENTA (SELL)."""
        request = self.factory.get('/')
        request.user = self.user
        request.active_customer = self.cliente

        tx = TransactionService.create_order_from_live_quote(
            request=request,
            base_currency_code='USD',
            target_currency_code='PYG',
            amount=Decimal('100.00'),
            operation_type='SELL',
            is_source_base=True,
            medio_pago_id=self.medio_pago.id,
            medio_acreditacion_id=self.medio_acreditacion.id,
            cliente=self.cliente,
            usuario=self.user,
        )

        self.assertIsNotNone(tx.id)
        self.assertEqual(tx.tipo_operacion, Transaction.TipoOperacion.VENTA)
        self.assertEqual(tx.monto_origen, Decimal('100.00'))
        self.assertEqual(tx.monto_destino, Decimal('750000.00'))

    def test_create_order_from_live_quote_violates_operation_limit(self):
        """Lanza ValidationError si el monto no respeta los límites operativos configurados."""
        OperationLimit.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('50.00'),
            monto_maximo=Decimal('500.00'),
            limite_diario=Decimal('1000.00'),
            limite_mensual=Decimal('5000.00'),
            is_active=True,
        )

        request = self.factory.get('/')
        request.user = self.user
        request.active_customer = self.cliente

        # Monto 10 USD está por debajo del mínimo de 50 USD
        with self.assertRaises(ValidationError) as ctx:
            TransactionService.create_order_from_live_quote(
                request=request,
                base_currency_code='USD',
                target_currency_code='PYG',
                amount=Decimal('10.00'),
                operation_type='BUY',
                is_source_base=True,
                medio_pago_id=self.medio_pago.id,
                medio_acreditacion_id=self.medio_acreditacion.id,
                cliente=self.cliente,
                usuario=self.user,
            )
        self.assertIn('amount', ctx.exception.message_dict)

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

    def test_create_order_medio_acreditacion_ajeno_lanza_error(self):
        """Falla si el medio de acreditación pertenece a otro cliente."""
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
                medio_pago_id=self.medio_pago.id,
                medio_acreditacion_id=self.otro_medio_acreditacion.id,
                cliente=self.cliente,
            )
        self.assertIn('medio_acreditacion_destino', ctx.exception.message_dict)

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
        self.assertIn('remaining_seconds', response.context)

    def test_transaction_detail_view_idor_prevention(self):
        """user1 no puede ver los detalles de una transacción del cliente 2 (retorna 404)."""
        tx2 = Transaction.objects.create(**self._build_valid_transaction_data(
            cliente=self.otro_cliente,
            medio_pago_origen=self.otro_medio_pago,
            medio_acreditacion_destino=self.otro_medio_acreditacion,
        ))
        url = reverse('transactions:detail', kwargs={'pk': tx2.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_transaction_receipt_view(self):
        """GET /transactions/<pk>/receipt/ renderiza el comprobante formal de liquidación."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data())
        url = reverse('transactions:receipt', kwargs={'pk': tx.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/receipt.html')
        self.assertEqual(response.context['transaction'].id, tx.id)
        self.assertContains(response, tx.codigo_referencia)

    def test_transaction_receipt_view_idor_prevention(self):
        """user1 no puede acceder al comprobante de transacción del cliente 2."""
        tx2 = Transaction.objects.create(**self._build_valid_transaction_data(
            cliente=self.otro_cliente,
            medio_pago_origen=self.otro_medio_pago,
            medio_acreditacion_destino=self.otro_medio_acreditacion,
        ))
        url = reverse('transactions:receipt', kwargs={'pk': tx2.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_transaction_list_view_and_filtering(self):
        """GET /transactions/ lista operaciones del cliente y aplica filtros por estado."""
        tx1 = Transaction.objects.create(**self._build_valid_transaction_data(
            estado=Transaction.Estado.PENDIENTE
        ))
        tx2 = Transaction.objects.create(**self._build_valid_transaction_data(
            estado=Transaction.Estado.COMPLETADA
        ))
        url = reverse('transactions:list') + '?estado=PENDIENTE'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/transaction_list.html')
        transactions_list = response.context['transactions']
        self.assertIn(tx1, transactions_list)
        self.assertNotIn(tx2, transactions_list)

    def test_transaction_list_view_idor_isolation(self):
        """Aislamiento de datos: user1 jamás ve las transacciones del cliente 2 en el listado."""
        tx_user1 = Transaction.objects.create(**self._build_valid_transaction_data())
        tx_user2 = Transaction.objects.create(**self._build_valid_transaction_data(
            cliente=self.otro_cliente,
            medio_pago_origen=self.otro_medio_pago,
            medio_acreditacion_destino=self.otro_medio_acreditacion,
        ))
        url = reverse('transactions:list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        transactions_list = list(response.context['transactions'])
        self.assertIn(tx_user1, transactions_list)
        self.assertNotIn(tx_user2, transactions_list)

    def test_cancel_view_post_success(self):
        """POST /transactions/<pk>/cancel/ anula la orden y redirige al detalle."""
        tx = Transaction.objects.create(**self._build_valid_transaction_data())
        url = reverse('transactions:cancel', kwargs={'pk': tx.pk})
        response = self.client.post(url, {'motivo': 'Prueba cancelación web'})

        self.assertEqual(response.status_code, 302)
        tx.refresh_from_db()
        self.assertEqual(tx.estado, Transaction.Estado.CANCELADA)

    def test_cancel_view_idor_prevention(self):
        """user1 no puede cancelar una orden perteneciente a cliente 2 (redirige con mensaje de error)."""
        tx2 = Transaction.objects.create(**self._build_valid_transaction_data(
            cliente=self.otro_cliente,
            medio_pago_origen=self.otro_medio_pago,
            medio_acreditacion_destino=self.otro_medio_acreditacion,
        ))
        url = reverse('transactions:cancel', kwargs={'pk': tx2.pk})
        response = self.client.post(url, {'motivo': 'Intento no autorizado'})

        self.assertEqual(response.status_code, 302)
        tx2.refresh_from_db()
        self.assertEqual(tx2.estado, Transaction.Estado.PENDIENTE)

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

    def test_transaction_api_create_view_invalid_json(self):
        """POST /transactions/api/create/ responde error 400 ante cuerpo JSON corrupto."""
        url = reverse('transactions:api_create')
        response = self.client.post(
            url,
            data='cuerpo_invalido_no_json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        res_json = response.json()
        self.assertFalse(res_json['success'])

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

    def test_cancel_api_view_idor_prevention(self):
        """POST /transactions/api/<pk>/cancel/ rechaza anulación de transacción de otro cliente."""
        tx2 = Transaction.objects.create(**self._build_valid_transaction_data(
            cliente=self.otro_cliente,
            medio_pago_origen=self.otro_medio_pago,
            medio_acreditacion_destino=self.otro_medio_acreditacion,
        ))
        url = reverse('transactions:api_cancel', kwargs={'pk': tx2.pk})
        payload = {'motivo': 'Intento IDOR'}
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        res_json = response.json()
        self.assertFalse(res_json['success'])
        tx2.refresh_from_db()
        self.assertEqual(tx2.estado, Transaction.Estado.PENDIENTE)


class TransactionAdminTest(TransactionTestMixin, TestCase):
    """Pruebas para el modelo admin de transacciones."""

    def test_transaction_admin_configuration(self):
        """Verifica la correcta parametrización de campos en TransactionAdmin."""
        admin_site = AdminSite()
        tx_admin = TransactionAdmin(Transaction, admin_site)

        self.assertIn('codigo_referencia', tx_admin.list_display)
        self.assertIn('estado', tx_admin.list_display)
        self.assertIn('estado', tx_admin.list_filter)
        self.assertIn('codigo_referencia', tx_admin.search_fields)
        self.assertIn('codigo_referencia', tx_admin.readonly_fields)
