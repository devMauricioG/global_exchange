"""
Suite de pruebas unitarias para la aplicación de transacciones cambiarias (transactions).

Cubre la creación del modelo :class:`Transaction`, validaciones personalizadas del
método ``clean()``, autogeneración de ``codigo_referencia``, transiciones de estado
(``mark_as_completed``, ``mark_as_cancelled``), propiedades derivadas, representación
en cadena y configuración del administrador Django.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import TestCase

from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency
from transactions.admin import TransactionAdmin
from transactions.models import Transaction


class TransactionTestMixin:
    """
    Mixin con la creación de datos de prueba compartidos por los TestCase de transacciones.
    """

    @classmethod
    def setUpTestData(cls):
        """Crea las dependencias de datos maestros reutilizables."""
        # Monedas
        cls.usd = Currency.objects.create(
            code='USD', name='Dólar Estadounidense', symbol='$', decimals=2,
        )
        cls.pyg = Currency.objects.create(
            code='PYG', name='Guaraní Paraguayo', symbol='₲', decimals=0,
        )
        cls.eur = Currency.objects.create(
            code='EUR', name='Euro', symbol='€', decimals=2,
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

        # Entidad financiera
        cls.banco = EntidadFinanciera.objects.create(
            nombre='Banco Test', tipo='BANCO',
        )

        # Medio de pago del cliente titular
        cls.medio_pago = PaymentMethod.objects.create(
            cliente=cls.cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=cls.banco,
            numero_cuenta='1234567890',
            titular='Juan Pérez',
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.AHORRO,
        )

        # Medio de acreditación del cliente titular
        cls.medio_acreditacion = ReceivingMethod.objects.create(
            cliente=cls.cliente,
            entidad_bancaria=cls.banco,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO,
            numero_cuenta='0987654321',
            titular='Juan Pérez',
        )

        # Medio de pago del OTRO cliente (para validaciones de pertenencia)
        cls.medio_pago_otro = PaymentMethod.objects.create(
            cliente=cls.otro_cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=cls.banco,
            numero_cuenta='1111111111',
            titular='María López',
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.CORRIENTE,
        )

        # Medio de acreditación del OTRO cliente (para validaciones de pertenencia)
        cls.medio_acreditacion_otro = ReceivingMethod.objects.create(
            cliente=cls.otro_cliente,
            entidad_bancaria=cls.banco,
            tipo_cuenta=ReceivingMethod.TipoCuenta.CORRIENTE,
            numero_cuenta='2222222222',
            titular='María López',
        )

    def _build_valid_transaction_data(self, **overrides):
        """
        Retorna un diccionario con datos válidos por defecto para crear una Transaction.

        Acepta ``**overrides`` para sobrescribir campos específicos en cada test.
        """
        defaults = {
            'cliente': self.cliente,
            'tipo_operacion': Transaction.TipoOperacion.COMPRA,
            'base_currency': self.usd,
            'target_currency': self.pyg,
            'tasa_base': Decimal('7350.000000'),
            'comision_segmento': Decimal('50.00'),
            'tasa_neta': Decimal('7300.000000'),
            'monto_origen': Decimal('1000.00'),
            'monto_destino': Decimal('7300000.00'),
            'medio_pago_origen': self.medio_pago,
            'medio_acreditacion_destino': self.medio_acreditacion,
        }
        defaults.update(overrides)
        return defaults


class TransactionCreationTest(TransactionTestMixin, TestCase):
    """Pruebas de creación correcta de transacciones COMPRA y VENTA."""

    def test_crear_transaccion_compra_exitosa(self):
        """Verifica la creación exitosa de una transacción de tipo COMPRA."""
        data = self._build_valid_transaction_data()
        tx = Transaction(**data)
        tx.save()
        tx.refresh_from_db()

        self.assertEqual(tx.tipo_operacion, Transaction.TipoOperacion.COMPRA)
        self.assertEqual(tx.estado, Transaction.Estado.PENDIENTE)
        self.assertEqual(tx.cliente_id, self.cliente.pk)
        self.assertEqual(tx.base_currency_id, self.usd.pk)
        self.assertEqual(tx.target_currency_id, self.pyg.pk)
        self.assertEqual(tx.monto_origen, Decimal('1000.00'))
        self.assertEqual(tx.monto_destino, Decimal('7300000.00'))
        self.assertIsNotNone(tx.codigo_referencia)
        self.assertTrue(tx.codigo_referencia.startswith('TX-'))
        self.assertIsNotNone(tx.created_at)
        self.assertIsNotNone(tx.updated_at)

    def test_crear_transaccion_venta_exitosa(self):
        """Verifica la creación exitosa de una transacción de tipo VENTA."""
        data = self._build_valid_transaction_data(
            tipo_operacion=Transaction.TipoOperacion.VENTA,
            monto_origen=Decimal('500.00'),
            monto_destino=Decimal('3650000.00'),
        )
        tx = Transaction(**data)
        tx.save()
        tx.refresh_from_db()

        self.assertEqual(tx.tipo_operacion, Transaction.TipoOperacion.VENTA)
        self.assertEqual(tx.estado, Transaction.Estado.PENDIENTE)
        self.assertEqual(tx.monto_origen, Decimal('500.00'))

    def test_estado_predeterminado_es_pendiente(self):
        """Verifica que el estado predeterminado sea PENDIENTE."""
        data = self._build_valid_transaction_data()
        tx = Transaction(**data)
        tx.save()
        self.assertEqual(tx.estado, Transaction.Estado.PENDIENTE)

    def test_transaccion_almacena_token_congelamiento(self):
        """Verifica que se almacene correctamente el token de congelamiento."""
        data = self._build_valid_transaction_data(
            token_congelamiento='QTZ-ABC12345',
        )
        tx = Transaction(**data)
        tx.save()
        tx.refresh_from_db()
        self.assertEqual(tx.token_congelamiento, 'QTZ-ABC12345')

    def test_transaccion_almacena_observaciones(self):
        """Verifica que las observaciones se persistan correctamente."""
        data = self._build_valid_transaction_data(
            observaciones='Transacción de prueba para cliente VIP.',
        )
        tx = Transaction(**data)
        tx.save()
        tx.refresh_from_db()
        self.assertEqual(tx.observaciones, 'Transacción de prueba para cliente VIP.')


class TransactionReferenceCodeTest(TransactionTestMixin, TestCase):
    """Pruebas de autogeneración del código de referencia."""

    def test_codigo_referencia_autogenerado(self):
        """Verifica que el código se genera automáticamente al guardar sin uno explícito."""
        data = self._build_valid_transaction_data()
        tx = Transaction(**data)
        self.assertFalse(tx.codigo_referencia)
        tx.save()
        self.assertTrue(tx.codigo_referencia)
        self.assertTrue(tx.codigo_referencia.startswith('TX-'))

    def test_codigo_referencia_formato_correcto(self):
        """Verifica el formato TX-YYYYMMDD-XXXXXX."""
        data = self._build_valid_transaction_data()
        tx = Transaction(**data)
        tx.save()
        parts = tx.codigo_referencia.split('-')
        self.assertEqual(parts[0], 'TX')
        self.assertEqual(len(parts[1]), 8)  # YYYYMMDD
        self.assertTrue(parts[1].isdigit())
        self.assertEqual(len(parts[2]), 6)  # 6 hex chars

    def test_codigo_referencia_personalizado_se_preserva(self):
        """Si se proporciona un código manualmente, no se sobrescribe."""
        data = self._build_valid_transaction_data(
            codigo_referencia='TX-CUSTOM-99999',
        )
        tx = Transaction(**data)
        tx.save()
        self.assertEqual(tx.codigo_referencia, 'TX-CUSTOM-99999')

    def test_codigo_referencia_unico_por_transaccion(self):
        """Cada transacción generada recibe un código diferente."""
        data1 = self._build_valid_transaction_data()
        tx1 = Transaction(**data1)
        tx1.save()

        data2 = self._build_valid_transaction_data()
        tx2 = Transaction(**data2)
        tx2.save()

        self.assertNotEqual(tx1.codigo_referencia, tx2.codigo_referencia)


class TransactionCleanValidationTest(TransactionTestMixin, TestCase):
    """Pruebas de las validaciones personalizadas en ``clean()``."""

    def test_validacion_monedas_identicas(self):
        """Rechaza par de monedas con base_currency == target_currency."""
        data = self._build_valid_transaction_data(
            base_currency=self.usd,
            target_currency=self.usd,
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('target_currency', cm.exception.message_dict)

    def test_validacion_monto_origen_cero(self):
        """Rechaza monto_origen igual a cero."""
        data = self._build_valid_transaction_data(
            monto_origen=Decimal('0.00'),
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('monto_origen', cm.exception.message_dict)

    def test_validacion_monto_origen_negativo(self):
        """Rechaza monto_origen negativo."""
        data = self._build_valid_transaction_data(
            monto_origen=Decimal('-100.00'),
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('monto_origen', cm.exception.message_dict)

    def test_validacion_monto_destino_cero(self):
        """Rechaza monto_destino igual a cero."""
        data = self._build_valid_transaction_data(
            monto_destino=Decimal('0.00'),
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('monto_destino', cm.exception.message_dict)

    def test_validacion_monto_destino_negativo(self):
        """Rechaza monto_destino negativo."""
        data = self._build_valid_transaction_data(
            monto_destino=Decimal('-500.00'),
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('monto_destino', cm.exception.message_dict)

    def test_validacion_tasa_base_cero(self):
        """Rechaza tasa_base igual a cero."""
        data = self._build_valid_transaction_data(
            tasa_base=Decimal('0.00'),
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('tasa_base', cm.exception.message_dict)

    def test_validacion_tasa_neta_negativa(self):
        """Rechaza tasa_neta negativa."""
        data = self._build_valid_transaction_data(
            tasa_neta=Decimal('-100.000000'),
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('tasa_neta', cm.exception.message_dict)

    def test_validacion_comision_negativa(self):
        """Rechaza comisión de segmento negativa."""
        data = self._build_valid_transaction_data(
            comision_segmento=Decimal('-10.00'),
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('comision_segmento', cm.exception.message_dict)

    def test_validacion_comision_cero_permitida(self):
        """Una comisión de cero es válida (no debe rechazarse)."""
        data = self._build_valid_transaction_data(
            comision_segmento=Decimal('0.00'),
        )
        tx = Transaction(**data)
        try:
            tx.full_clean()
        except ValidationError:
            self.fail('Una comisión de segmento igual a cero debería ser válida.')

    def test_validacion_medio_pago_ajeno(self):
        """Rechaza medio de pago que no pertenece al cliente titular."""
        data = self._build_valid_transaction_data(
            medio_pago_origen=self.medio_pago_otro,
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('medio_pago_origen', cm.exception.message_dict)

    def test_validacion_medio_acreditacion_ajeno(self):
        """Rechaza medio de acreditación que no pertenece al cliente titular."""
        data = self._build_valid_transaction_data(
            medio_acreditacion_destino=self.medio_acreditacion_otro,
        )
        tx = Transaction(**data)
        with self.assertRaises(ValidationError) as cm:
            tx.full_clean()
        self.assertIn('medio_acreditacion_destino', cm.exception.message_dict)

    def test_validacion_datos_validos_no_lanza_error(self):
        """Datos válidos completos no deben generar ValidationError."""
        data = self._build_valid_transaction_data()
        tx = Transaction(**data)
        try:
            tx.full_clean()
        except ValidationError:
            self.fail('full_clean() no debería fallar con datos válidos.')


class TransactionStateTransitionTest(TransactionTestMixin, TestCase):
    """Pruebas de las transiciones de estado ``mark_as_completed`` y ``mark_as_cancelled``."""

    def _create_pending_transaction(self, **overrides):
        """Helper para crear y persistir una transacción PENDIENTE."""
        data = self._build_valid_transaction_data(**overrides)
        tx = Transaction(**data)
        tx.save()
        return tx

    def test_mark_as_completed(self):
        """Transición PENDIENTE → COMPLETADA exitosa."""
        tx = self._create_pending_transaction()
        self.assertTrue(tx.is_pending)
        tx.mark_as_completed()
        tx.refresh_from_db()
        self.assertEqual(tx.estado, Transaction.Estado.COMPLETADA)
        self.assertTrue(tx.is_completed)
        self.assertFalse(tx.is_pending)

    def test_mark_as_completed_with_user(self):
        """Asigna usuario operador al completar la transacción."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        operador = User.objects.create_user(
            username='cajero_test', password='pass12345',
        )
        tx = self._create_pending_transaction()
        tx.mark_as_completed(user=operador)
        tx.refresh_from_db()
        self.assertEqual(tx.usuario_id, operador.pk)
        self.assertTrue(tx.is_completed)

    def test_mark_as_cancelled(self):
        """Transición PENDIENTE → CANCELADA exitosa."""
        tx = self._create_pending_transaction()
        tx.mark_as_cancelled()
        tx.refresh_from_db()
        self.assertEqual(tx.estado, Transaction.Estado.CANCELADA)
        self.assertTrue(tx.is_cancelled)
        self.assertFalse(tx.is_pending)

    def test_mark_as_cancelled_with_motivo(self):
        """El motivo de cancelación se agrega a las observaciones."""
        tx = self._create_pending_transaction()
        tx.mark_as_cancelled(motivo='Expiró la cotización congelada.')
        tx.refresh_from_db()
        self.assertIn('Cancelación', tx.observaciones)
        self.assertIn('Expiró la cotización congelada.', tx.observaciones)

    def test_mark_as_cancelled_preserva_observaciones_existentes(self):
        """Si ya existían observaciones, el motivo se añade sin borrarlas."""
        tx = self._create_pending_transaction(observaciones='Notas previas.')
        tx.mark_as_cancelled(motivo='Cliente desistió.')
        tx.refresh_from_db()
        self.assertIn('Notas previas.', tx.observaciones)
        self.assertIn('Cliente desistió.', tx.observaciones)


class TransactionPropertiesTest(TransactionTestMixin, TestCase):
    """Pruebas de las propiedades calculadas del modelo."""

    def test_moneda_origen_compra(self):
        """En COMPRA, moneda_origen es target_currency (PYG)."""
        data = self._build_valid_transaction_data(
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
        )
        tx = Transaction(**data)
        self.assertEqual(tx.moneda_origen, self.pyg)

    def test_moneda_destino_compra(self):
        """En COMPRA, moneda_destino es base_currency (USD)."""
        data = self._build_valid_transaction_data(
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
        )
        tx = Transaction(**data)
        self.assertEqual(tx.moneda_destino, self.usd)

    def test_moneda_origen_venta(self):
        """En VENTA, moneda_origen es base_currency (USD)."""
        data = self._build_valid_transaction_data(
            tipo_operacion=Transaction.TipoOperacion.VENTA,
        )
        tx = Transaction(**data)
        self.assertEqual(tx.moneda_origen, self.usd)

    def test_moneda_destino_venta(self):
        """En VENTA, moneda_destino es target_currency (PYG)."""
        data = self._build_valid_transaction_data(
            tipo_operacion=Transaction.TipoOperacion.VENTA,
        )
        tx = Transaction(**data)
        self.assertEqual(tx.moneda_destino, self.pyg)

    def test_is_pending_true(self):
        """is_pending es True cuando el estado es PENDIENTE."""
        tx = Transaction(estado=Transaction.Estado.PENDIENTE)
        self.assertTrue(tx.is_pending)

    def test_is_completed_true(self):
        """is_completed es True cuando el estado es COMPLETADA."""
        tx = Transaction(estado=Transaction.Estado.COMPLETADA)
        self.assertTrue(tx.is_completed)

    def test_is_cancelled_true(self):
        """is_cancelled es True cuando el estado es CANCELADA."""
        tx = Transaction(estado=Transaction.Estado.CANCELADA)
        self.assertTrue(tx.is_cancelled)


class TransactionStringRepresentationTest(TransactionTestMixin, TestCase):
    """Pruebas de ``__str__``."""

    def test_str_con_codigo_referencia(self):
        """__str__ incluye el código de referencia, tipo y estado."""
        data = self._build_valid_transaction_data(
            codigo_referencia='TX-20260923-TEST01',
        )
        tx = Transaction(**data)
        cadena = str(tx)
        self.assertIn('TX-20260923-TEST01', cadena)
        self.assertIn('Compra de Divisas', cadena)
        self.assertIn('Juan Pérez', cadena)

    def test_str_sin_codigo_referencia(self):
        """__str__ muestra 'TX-NUEVA' si no hay código asignado."""
        data = self._build_valid_transaction_data()
        tx = Transaction(**data)
        cadena = str(tx)
        self.assertIn('TX-NUEVA', cadena)


class TransactionAdminTest(TransactionTestMixin, TestCase):
    """Pruebas de configuración del panel de administración ``TransactionAdmin``."""

    def test_admin_list_display_configurado(self):
        """Verifica que list_display tenga los campos principales."""
        admin_instance = TransactionAdmin(Transaction, AdminSite())
        self.assertIn('codigo_referencia', admin_instance.list_display)
        self.assertIn('cliente', admin_instance.list_display)
        self.assertIn('tipo_operacion', admin_instance.list_display)
        self.assertIn('estado', admin_instance.list_display)

    def test_admin_search_fields_configurado(self):
        """Verifica que search_fields incluya código y cliente."""
        admin_instance = TransactionAdmin(Transaction, AdminSite())
        search = admin_instance.search_fields
        self.assertTrue(
            any('codigo_referencia' in f for f in search),
            'search_fields debe incluir codigo_referencia',
        )

    def test_admin_list_filter_configurado(self):
        """Verifica que list_filter tenga al menos estado y tipo_operacion."""
        admin_instance = TransactionAdmin(Transaction, AdminSite())
        filtros = admin_instance.list_filter
        self.assertTrue(
            any('estado' in str(f) for f in filtros),
            'list_filter debe incluir estado',
        )
        self.assertTrue(
            any('tipo_operacion' in str(f) for f in filtros),
            'list_filter debe incluir tipo_operacion',
        )

    def test_admin_readonly_fields_configurado(self):
        """Verifica que los campos de timestamp y código sean de solo lectura."""
        admin_instance = TransactionAdmin(Transaction, AdminSite())
        readonly = admin_instance.readonly_fields
        self.assertIn('created_at', readonly)
        self.assertIn('updated_at', readonly)
        self.assertIn('codigo_referencia', readonly)
