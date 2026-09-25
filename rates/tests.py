"""
Módulo de pruebas unitarias para la aplicación rates (SCRUM-50 y SCRUM-53).

Verifica la integridad de datos, lógica de negocio y restricciones de validación para:
- :class:`~rates.models.Currency`
- :class:`~rates.models.ExchangeRate`
- :class:`~rates.models.SegmentCommission`
- :class:`~rates.services.RateCalculationService` y resolución de cliente activo
- Formularios :class:`~rates.forms.SegmentCommissionForm`, :class:`~rates.forms.SegmentCommissionFilterForm`, :class:`~rates.forms.RateCalculatorForm`
- Vistas CBVs de administración de comisiones y simulador de cotizaciones
- Endpoints API REST JSON para liquidación en tiempo real y consulta de reglas
"""

from datetime import timedelta
from decimal import Decimal
import json

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Cliente, CustomerUserAssignment
from rates.admin import CurrencyAdmin, ExchangeRateAdmin, OperationLimitAdmin, SegmentCommissionAdmin
from rates.forms import (
    OperationLimitFilterForm,
    OperationLimitForm,
    RateCalculatorForm,
    SegmentCommissionFilterForm,
    SegmentCommissionForm,
)
from rates.models import Currency, ExchangeRate, OperationLimit, SegmentCommission
from rates.services import (
    OperationLimitValidationService,
    QuoteFreezeService,
    RateCalculationService,
    get_active_customer,
)
from rates.templatetags.currency_filters import format_currency, format_number, format_rate

User = get_user_model()


# ==============================================================================
# PRUEBAS DE MODELOS
# ==============================================================================

class CurrencyModelTest(TestCase):
    """
    Pruebas unitarias para el modelo Currency (Catálogo de Monedas).
    """

    def setUp(self):
        self.usd = Currency.objects.create(
            code='USD',
            name='Dólar Estadounidense',
            symbol='$',
            decimals=2,
            is_active=True,
        )

    def test_currency_creation_and_defaults(self):
        pyg = Currency.objects.create(
            code='PYG',
            name='Guaraní Paraguayo',
            symbol='₲',
            decimals=0,
        )
        self.assertEqual(pyg.code, 'PYG')
        self.assertEqual(pyg.name, 'Guaraní Paraguayo')
        self.assertEqual(pyg.symbol, '₲')
        self.assertEqual(pyg.decimals, 0)
        self.assertTrue(pyg.is_active)
        self.assertIsNotNone(pyg.created_at)
        self.assertIsNotNone(pyg.updated_at)

    def test_currency_str_representation(self):
        self.assertEqual(str(self.usd), 'USD - Dólar Estadounidense ($)')

    def test_currency_code_upper_conversion_on_save(self):
        eur = Currency.objects.create(
            code='eur',
            name='Euro',
            symbol='€',
            decimals=2,
        )
        self.assertEqual(eur.code, 'EUR')

    def test_currency_code_uniqueness(self):
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                Currency.objects.create(
                    code='USD',
                    name='Dólar Clon',
                    symbol='$',
                )

    def test_currency_negative_decimals_validation(self):
        invalid_curr = Currency(
            code='INV',
            name='Moneda Inválida',
            symbol='?',
            decimals=-1,
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_curr.save()
        self.assertIn('decimals', ctx.exception.message_dict)

    def test_currency_excessive_decimals_validation(self):
        invalid_curr = Currency(
            code='INV',
            name='Moneda Inválida',
            symbol='?',
            decimals=11,
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_curr.save()
        self.assertIn('decimals', ctx.exception.message_dict)

    def test_currency_decimal_places_property(self):
        self.assertEqual(self.usd.decimal_places, 2)


class ExchangeRateModelTest(TestCase):
    """
    Pruebas unitarias para el modelo ExchangeRate (Cotizaciones y Tasas de Cambio).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='operador',
            email='operador@globalexchange.com',
            password='Password123!',
        )
        self.usd = Currency.objects.create(code='USD', name='Dólar Estadounidense', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní Paraguayo', symbol='₲', decimals=0)

    def test_exchange_rate_creation_and_spread_auto_calculation(self):
        rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7450.000000'),
            sell_rate=Decimal('7550.000000'),
            updated_by=self.user,
        )
        self.assertEqual(rate.spread, Decimal('100.000000'))
        self.assertTrue(rate.is_active)
        self.assertIsNotNone(rate.valid_from)

    def test_exchange_rate_validation_same_currencies(self):
        rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.usd,
            buy_rate=Decimal('1.000000'),
            sell_rate=Decimal('1.000000'),
        )
        with self.assertRaises(ValidationError) as ctx:
            rate.save()
        self.assertIn('target_currency', ctx.exception.message_dict)

    def test_exchange_rate_validation_zero_or_negative_buy_rate(self):
        rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('0.000000'),
            sell_rate=Decimal('7550.000000'),
        )
        with self.assertRaises(ValidationError) as ctx:
            rate.save()
        self.assertIn('buy_rate', ctx.exception.message_dict)

    def test_exchange_rate_validation_sell_lower_than_buy(self):
        rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7600.000000'),
            sell_rate=Decimal('7400.000000'),
        )
        with self.assertRaises(ValidationError) as ctx:
            rate.save()
        self.assertIn('sell_rate', ctx.exception.message_dict)

    def test_is_currently_valid_methods(self):
        now = timezone.now()
        rate_valid = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            valid_from=now - timedelta(hours=1),
            valid_to=now + timedelta(hours=1),
            is_active=True,
        )
        self.assertTrue(rate_valid.is_currently_valid())

        rate_expired = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7300.000000'),
            sell_rate=Decimal('7400.000000'),
            valid_from=now - timedelta(days=2),
            valid_to=now - timedelta(days=1),
            is_active=True,
        )
        self.assertFalse(rate_expired.is_currently_valid())

    def test_get_rate_for_operation(self):
        rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
        )
        self.assertEqual(rate.get_rate_for_operation('BUY'), Decimal('7500.000000'))
        self.assertEqual(rate.get_rate_for_operation('SELL'), Decimal('7400.000000'))
        with self.assertRaises(ValueError):
            rate.get_rate_for_operation('INVALID')

    def test_exchange_rate_str_representation(self):
        rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
        )
        self.assertIn('USD/PYG', str(rate))
        self.assertIn('Compra: 7400.000000', str(rate))
        self.assertIn('Venta: 7500.000000', str(rate))


class SegmentCommissionModelTest(TestCase):
    """
    Pruebas unitarias para el modelo SegmentCommission (Comisiones y Políticas Cambiarias).
    """

    def setUp(self):
        self.commission_min = SegmentCommission.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            commission_percentage=Decimal('1.50'),
            fixed_fee=Decimal('5000.00'),
            spread_discount_percentage=Decimal('0.00'),
            is_active=True,
        )
        self.commission_vip = SegmentCommission.objects.create(
            segment=Cliente.Segmentacion.VIP,
            commission_percentage=Decimal('0.25'),
            fixed_fee=Decimal('0.00'),
            spread_discount_percentage=Decimal('50.00'),
            is_active=True,
        )

    def test_segment_commission_creation_and_fields(self):
        self.assertEqual(self.commission_min.segment, 'MIN')
        self.assertEqual(self.commission_min.commission_percentage, Decimal('1.50'))
        self.assertEqual(self.commission_min.fixed_fee, Decimal('5000.00'))
        self.assertEqual(self.commission_min.spread_discount_percentage, Decimal('0.00'))
        self.assertTrue(self.commission_min.is_active)

    def test_segment_unique_constraint(self):
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                SegmentCommission.objects.create(
                    segment=Cliente.Segmentacion.MINORISTA,
                    commission_percentage=Decimal('2.00'),
                )

    def test_commission_percentage_out_of_bounds(self):
        neg = SegmentCommission(
            segment=Cliente.Segmentacion.MAYORISTA,
            commission_percentage=Decimal('-1.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            neg.save()
        self.assertIn('commission_percentage', ctx.exception.message_dict)

        over = SegmentCommission(
            segment=Cliente.Segmentacion.CORPORATIVO,
            commission_percentage=Decimal('101.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            over.save()
        self.assertIn('commission_percentage', ctx.exception.message_dict)

    def test_fixed_fee_negative_validation(self):
        neg_fee = SegmentCommission(
            segment=Cliente.Segmentacion.MAYORISTA,
            fixed_fee=Decimal('-100.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            neg_fee.save()
        self.assertIn('fixed_fee', ctx.exception.message_dict)

    def test_spread_discount_out_of_bounds(self):
        over_discount = SegmentCommission(
            segment=Cliente.Segmentacion.MAYORISTA,
            spread_discount_percentage=Decimal('150.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            over_discount.save()
        self.assertIn('spread_discount_percentage', ctx.exception.message_dict)

    def test_calculate_commission_method(self):
        # Para 1.000.000 con 1.5% + 5.000 fijo: 15.000 + 5.000 = 20.000
        amount = Decimal('1000000.00')
        comm = self.commission_min.calculate_commission(amount)
        self.assertEqual(comm, Decimal('20000.00'))

        # Para monto <= 0
        self.assertEqual(self.commission_min.calculate_commission(Decimal('0.00')), Decimal('0.00'))

    def test_calculate_commission_inactive_rule(self):
        self.commission_min.is_active = False
        self.commission_min.save()
        self.assertEqual(self.commission_min.calculate_commission(Decimal('1000.00')), Decimal('0.00'))

    def test_apply_spread_discount_method(self):
        original_spread = Decimal('100.000000')
        # VIP tiene 50% de descuento sobre el spread: spread resultante = 50.00
        adjusted = self.commission_vip.apply_spread_discount(original_spread)
        self.assertEqual(adjusted, Decimal('50.000000'))

        # Minorista tiene 0% de descuento: spread resultante = 100.00
        adjusted_min = self.commission_min.apply_spread_discount(original_spread)
        self.assertEqual(adjusted_min, original_spread)

    def test_str_representation(self):
        str_repr = str(self.commission_vip)
        self.assertIn('VIP', str_repr)
        self.assertIn('0.25%', str_repr)
        self.assertIn('50.00%', str_repr)


class RatesAdminInterfaceTest(TestCase):
    """
    Pruebas de la configuración e interfaz de Django Admin para rates.
    """

    def setUp(self):
        self.site = AdminSite()
        self.user = User.objects.create_superuser('admin_rates', 'admin@rates.com', 'AdminPass123!')
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$')
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲')
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
        )
        self.factory = RequestFactory()

    def test_exchangerate_admin_save_model_sets_updated_by(self):
        request = self.factory.get('/admin/')
        request.user = self.user
        admin_obj = ExchangeRateAdmin(ExchangeRate, self.site)
        admin_obj.save_model(request, self.rate, form=None, change=True)
        self.assertEqual(self.rate.updated_by, self.user)


# ==============================================================================
# PRUEBAS DEL MOTOR DE CÁLCULO Y SERVICIOS (SCRUM-53)
# ==============================================================================

class RateCalculationServiceTest(TestCase):
    """
    Pruebas unitarias exhaustivas para RateCalculationService.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='tester', email='tester@test.com', password='Password123!')
        self.usd = Currency.objects.create(code='USD', name='Dólar Estadounidense', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní Paraguayo', symbol='₲', decimals=0)

        # Cotización oficial USD/PYG: Compra 7.400 / Venta 7.500 (Spread = 100)
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            updated_by=self.user,
            is_active=True,
        )

        # Reglas por segmento
        self.comm_min = SegmentCommission.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            commission_percentage=Decimal('1.00'),
            fixed_fee=Decimal('5000.00'),
            spread_discount_percentage=Decimal('0.00'),
            is_active=True,
        )
        self.comm_vip = SegmentCommission.objects.create(
            segment=Cliente.Segmentacion.VIP,
            commission_percentage=Decimal('0.20'),
            fixed_fee=Decimal('0.00'),
            spread_discount_percentage=Decimal('40.00'),  # 40% de descuento en spread -> spread ef = 60
            is_active=True,
        )

        # Clientes de prueba
        self.cliente_min = Cliente.objects.create(
            nombre='Cliente Minorista',
            documento_ruc='1111111-1',
            correo='min@test.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=True,
        )
        self.cliente_vip = Cliente.objects.create(
            nombre='Cliente VIP S.A.',
            documento_ruc='2222222-2',
            correo='vip@test.com',
            segmentacion=Cliente.Segmentacion.VIP,
            is_active=True,
        )

    def test_get_commission_rule_by_segment_code(self):
        rule = RateCalculationService.get_commission_rule('VIP')
        self.assertEqual(rule.id, self.comm_vip.id)

    def test_get_commission_rule_by_cliente_instance(self):
        rule = RateCalculationService.get_commission_rule(self.cliente_min)
        self.assertEqual(rule.id, self.comm_min.id)

    def test_get_commission_rule_fallback_virtual_when_unconfigured(self):
        rule = RateCalculationService.get_commission_rule('COR')
        self.assertEqual(rule.segment, 'COR')
        self.assertEqual(rule.commission_percentage, Decimal('0.00'))
        self.assertEqual(rule.fixed_fee, Decimal('0.00'))
        self.assertEqual(rule.spread_discount_percentage, Decimal('0.00'))
        self.assertIsNone(rule.id)

    def test_get_latest_exchange_rate_by_codes(self):
        rate = RateCalculationService.get_latest_exchange_rate('USD', 'PYG')
        self.assertIsNotNone(rate)
        self.assertEqual(rate.id, self.rate.id)

    def test_get_latest_exchange_rate_by_objects(self):
        rate = RateCalculationService.get_latest_exchange_rate(self.usd, self.pyg)
        self.assertIsNotNone(rate)
        self.assertEqual(rate.id, self.rate.id)

    def test_get_latest_exchange_rate_nonexistent(self):
        rate = RateCalculationService.get_latest_exchange_rate('EUR', 'PYG')
        self.assertIsNone(rate)

    def test_get_latest_exchange_rate_excludes_expired_and_future_quotes(self):
        """El cotizador no debe devolver cotizaciones fuera de su vigencia."""
        now = timezone.now()
        ExchangeRate.objects.filter(pk=self.rate.pk).update(valid_to=now - timedelta(seconds=1))
        ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7600.000000'),
            sell_rate=Decimal('7700.000000'),
            valid_from=now + timedelta(minutes=5),
            is_active=True,
        )

        self.assertIsNone(RateCalculationService.get_latest_exchange_rate('USD', 'PYG'))

    def test_calculate_quotation_buy_minorista(self):
        """
        Cliente Minorista compra 100 USD (op_type='BUY', is_source_base=True).
        - Tasa oficial de venta = 7.500.
        - Dto spread = 0% -> tasa efectiva = 7.500.
        - Monto bruto en PYG = 100 * 7.500 = 750.000 PYG.
        - Comisión porcentual (1.00%) = 7.500 PYG.
        - Cargo fijo = 5.000 PYG.
        - Total comisión = 12.500 PYG.
        - Total neto a pagar = 750.000 + 12.500 = 762.500 PYG.
        - Tasa neta final = 762.500 / 100 = 7.625.
        """
        res = RateCalculationService.calculate_quotation(
            exchange_rate=self.rate,
            segment_or_customer=self.cliente_min,
            amount=Decimal('100.00'),
            operation_type='BUY',
            is_source_base=True,
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['base_amount'], Decimal('100.00'))
        self.assertEqual(res['effective_rate'], Decimal('7500.000000'))
        self.assertEqual(res['gross_target_amount'], Decimal('750000'))
        self.assertEqual(res['commission_percentage_amount'], Decimal('7500'))
        self.assertEqual(res['fixed_fee'], Decimal('5000'))
        self.assertEqual(res['total_commission'], Decimal('12500'))
        self.assertEqual(res['net_target_amount'], Decimal('762500'))
        self.assertEqual(res['final_effective_rate'], Decimal('7625.000000'))

    def test_calculate_quotation_sell_vip_with_spread_discount(self):
        """
        Cliente VIP vende 1.000 USD (op_type='SELL', is_source_base=True).
        - Tasa oficial compra = 7.400, Venta = 7.500, Spread = 100.
        - Dto spread VIP (40%): spread ef = 60, ahorro = 40, mitad = 20.
        - Tasa efectiva compra ajustada para el cliente = 7.400 + 20 = 7.420.
        - Monto bruto en PYG = 1.000 * 7.420 = 7.420.000 PYG.
        - Comisión VIP (0.20%): 7.420.000 * 0.002 = 14.840 PYG.
        - Cargo fijo = 0.
        - Total neto a recibir = 7.420.000 - 14.840 = 7.405.160 PYG.
        - Tasa neta final = 7.405.160 / 1.000 = 7.405,16.
        """
        res = RateCalculationService.calculate_quotation(
            exchange_rate=self.rate,
            segment_or_customer=self.cliente_vip,
            amount=Decimal('1000.00'),
            operation_type='SELL',
            is_source_base=True,
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['effective_rate'], Decimal('7420.000000'))
        self.assertEqual(res['gross_target_amount'], Decimal('7420000'))
        self.assertEqual(res['total_commission'], Decimal('14840'))
        self.assertEqual(res['net_target_amount'], Decimal('7405160'))
        self.assertEqual(res['spread_savings'], Decimal('20000'))  # Ganó 20 PYG por dólar vs los 7.400 oficiales

    def test_calculate_quotation_source_in_target_currency(self):
        """
        Cliente Minorista ingresa 7.500.000 PYG (is_source_base=False, op_type='BUY').
        """
        res = RateCalculationService.calculate_quotation(
            exchange_rate=self.rate,
            segment_or_customer='MIN',
            amount=Decimal('7500000.00'),
            operation_type='BUY',
            is_source_base=False,
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['gross_target_amount'], Decimal('7500000'))
        self.assertEqual(res['base_amount'], Decimal('1000.00'))

    def test_calculate_quotation_invalid_operation_type(self):
        with self.assertRaises(ValidationError):
            RateCalculationService.calculate_quotation(
                exchange_rate=self.rate,
                amount=Decimal('100.00'),
                operation_type='EXCHANGE',
            )

    def test_calculate_quotation_zero_or_negative_amount(self):
        with self.assertRaises(ValidationError):
            RateCalculationService.calculate_quotation(
                exchange_rate=self.rate,
                amount=Decimal('0.00'),
            )
        with self.assertRaises(ValidationError):
            RateCalculationService.calculate_quotation(
                exchange_rate=self.rate,
                amount=Decimal('-50.00'),
            )

    def test_calculate_quotation_by_codes_valid(self):
        res = RateCalculationService.calculate_quotation_by_codes(
            base_currency_code='USD',
            target_currency_code='PYG',
            segment_or_customer='VIP',
            amount=Decimal('500.00'),
            operation_type='BUY',
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['base_amount'], Decimal('500.00'))

    def test_calculate_quotation_by_codes_missing_rate(self):
        with self.assertRaises(ValidationError):
            RateCalculationService.calculate_quotation_by_codes(
                base_currency_code='BRL',
                target_currency_code='PYG',
                amount=Decimal('100.00'),
            )


class ActiveCustomerResolutionTest(TestCase):
    """
    Pruebas para la resolución de cliente activo en get_active_customer().
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='cuser', email='cuser@test.com', password='Password123!')
        self.cliente = Cliente.objects.create(
            nombre='Empresa Activa S.A.',
            documento_ruc='3333333-3',
            correo='cuser@test.com',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
            is_active=True,
        )

    def test_anonymous_user_returns_none(self):
        request = self.factory.get('/')
        request.user = AnonymousUser()
        self.assertIsNone(get_active_customer(request))

    def test_active_customer_attribute_priority(self):
        request = self.factory.get('/')
        request.user = self.user
        request.active_customer = self.cliente
        self.assertEqual(get_active_customer(request), self.cliente)

    def test_session_active_customer_id_resolution(self):
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'active_customer_id': self.cliente.id}
        self.assertEqual(get_active_customer(request), self.cliente)

    def test_email_matching_resolution(self):
        request = self.factory.get('/')
        request.user = self.user
        request.session = {}
        self.assertEqual(get_active_customer(request), self.cliente)


# ==============================================================================
# PRUEBAS DE FORMULARIOS (SCRUM-53)
# ==============================================================================

class RatesFormsTest(TestCase):
    """
    Pruebas para los formularios de parametrización de comisiones y cotizador.
    """

    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$')
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲')
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
        )

    def test_segment_commission_form_valid(self):
        form = SegmentCommissionForm(
            data={
                'segment': 'MAY',
                'commission_percentage': '0.75',
                'fixed_fee': '2500.00',
                'spread_discount_percentage': '25.00',
                'is_active': True,
            }
        )
        self.assertTrue(form.is_valid())

    def test_segment_commission_form_invalid_percentages(self):
        form_high = SegmentCommissionForm(
            data={
                'segment': 'MAY',
                'commission_percentage': '105.00',
                'fixed_fee': '0.00',
                'spread_discount_percentage': '0.00',
                'is_active': True,
            }
        )
        self.assertFalse(form_high.is_valid())
        self.assertIn('commission_percentage', form_high.errors)

        form_neg_spread = SegmentCommissionForm(
            data={
                'segment': 'MAY',
                'commission_percentage': '1.00',
                'fixed_fee': '0.00',
                'spread_discount_percentage': '-5.00',
                'is_active': True,
            }
        )
        self.assertFalse(form_neg_spread.is_valid())
        self.assertIn('spread_discount_percentage', form_neg_spread.errors)

    def test_segment_commission_filter_form(self):
        form = SegmentCommissionFilterForm(data={'segment': 'MIN', 'is_active': 'true'})
        self.assertTrue(form.is_valid())

    def test_rate_calculator_form_valid(self):
        form = RateCalculatorForm(
            data={
                'exchange_rate': self.rate.id,
                'operation_type': 'BUY',
                'amount': '250.00',
                'segment': 'VIP',
                'is_source_base': True,
            }
        )
        self.assertTrue(form.is_valid())


# ==============================================================================
# PRUEBAS DE VISTAS CBVs Y ENDPOINTS API (SCRUM-53)
# ==============================================================================

class RatesViewsAndApiTest(TestCase):
    """
    Pruebas para las vistas web CBVs y endpoints API JSON de rates.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='operador_web',
            email='operador@web.com',
            password='Password123!',
        )
        self.client.force_login(self.user)

        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            is_active=True,
        )
        self.commission = SegmentCommission.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            commission_percentage=Decimal('1.50'),
            fixed_fee=Decimal('5000.00'),
            spread_discount_percentage=Decimal('10.00'),
            is_active=True,
        )

    def test_commission_list_view_get(self):
        response = self.client.get(reverse('rates:commission_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'rates/commission_list.html')
        self.assertIn('commissions', response.context)
        self.assertEqual(response.context['total_rules'], 1)

    def test_commission_list_view_filters(self):
        response = self.client.get(reverse('rates:commission_list'), {'segment': 'MIN', 'is_active': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['commissions']), 1)

        response_empty = self.client.get(reverse('rates:commission_list'), {'segment': 'VIP'})
        self.assertEqual(response_empty.status_code, 200)
        self.assertEqual(len(response_empty.context['commissions']), 0)

    def test_commission_create_view_get_and_post(self):
        get_res = self.client.get(reverse('rates:commission_create'))
        self.assertEqual(get_res.status_code, 200)
        self.assertTemplateUsed(get_res, 'rates/commission_form.html')

        post_res = self.client.post(
            reverse('rates:commission_create'),
            {
                'segment': 'VIP',
                'commission_percentage': '0.50',
                'fixed_fee': '0.00',
                'spread_discount_percentage': '40.00',
                'is_active': True,
            },
        )
        self.assertEqual(post_res.status_code, 302)
        self.assertTrue(SegmentCommission.objects.filter(segment='VIP').exists())

    def test_commission_update_view(self):
        response = self.client.post(
            reverse('rates:commission_update', kwargs={'pk': self.commission.id}),
            {
                'segment': 'MIN',
                'commission_percentage': '1.80',
                'fixed_fee': '6000.00',
                'spread_discount_percentage': '5.00',
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.commission.refresh_from_db()
        self.assertEqual(self.commission.commission_percentage, Decimal('1.80'))
        self.assertEqual(self.commission.fixed_fee, Decimal('6000.00'))

    def test_commission_detail_view(self):
        response = self.client.get(reverse('rates:commission_detail', kwargs={'pk': self.commission.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'rates/commission_detail.html')
        self.assertIn('simulations', response.context)

    def test_commission_delete_view(self):
        response = self.client.post(reverse('rates:commission_delete', kwargs={'pk': self.commission.id}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SegmentCommission.objects.filter(id=self.commission.id).exists())

    def test_rate_calculator_view_get(self):
        response = self.client.get(reverse('rates:rate_calculator'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'rates/rate_calculator.html')

    def test_rate_calculator_view_get_with_params(self):
        response = self.client.get(
            reverse('rates:rate_calculator'),
            {
                'exchange_rate': self.rate.id,
                'operation_type': 'BUY',
                'amount': '150.00',
                'segment': 'MIN',
                'is_source_base': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['calculation'])
        self.assertEqual(response.context['calculation']['base_amount'], Decimal('150.00'))

    def test_rate_calculator_view_post_valid(self):
        response = self.client.post(
            reverse('rates:rate_calculator'),
            {
                'exchange_rate': self.rate.id,
                'operation_type': 'SELL',
                'amount': '300.00',
                'segment': 'MIN',
                'is_source_base': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['calculation'])
        self.assertEqual(response.context['calculation']['operation_type'], 'SELL')

    def test_api_calculate_endpoint_get(self):
        response = self.client.get(
            reverse('rates:api_calculate'),
            {
                'exchange_rate_id': self.rate.id,
                'operation_type': 'BUY',
                'amount': '100.00',
                'segment': 'MIN',
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['base_amount'], 100.0)

    def test_api_calculate_endpoint_post_json(self):
        payload = {
            'base_currency': 'USD',
            'target_currency': 'PYG',
            'operation_type': 'SELL',
            'amount': 500.0,
            'segment': 'MIN',
        }
        response = self.client.post(
            reverse('rates:api_calculate'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['base_amount'], 500.0)

    def test_api_calculate_endpoint_not_found(self):
        response = self.client.get(
            reverse('rates:api_calculate'),
            {
                'base_currency': 'GBP',
                'target_currency': 'PYG',
                'amount': '100.00',
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_api_calculate_rejects_expired_quote(self):
        """La integración del cotizador devuelve 404 cuando ya expiró la tasa."""
        ExchangeRate.objects.filter(pk=self.rate.pk).update(
            valid_to=timezone.now() - timedelta(seconds=1)
        )

        response = self.client.get(
            reverse('rates:api_calculate'),
            {
                'base_currency': 'USD',
                'target_currency': 'PYG',
                'amount': '100.00',
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_api_calculate_endpoint_bad_request_negative_amount(self):
        response = self.client.get(
            reverse('rates:api_calculate'),
            {
                'exchange_rate_id': self.rate.id,
                'amount': '-50.00',
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_api_calculate_with_cliente_id_and_post_form(self):
        cliente = Cliente.objects.create(
            nombre='Test Cliente API',
            documento_ruc='4444444-4',
            correo='api@cliente.com',
            segmentacion='MIN',
            is_active=True,
        )
        response = self.client.post(
            reverse('rates:api_calculate'),
            {
                'base_currency': 'USD',
                'target_currency': 'PYG',
                'amount': '200.00',
                'cliente_id': cliente.id,
                'operation_type': 'BUY',
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

    def test_api_calculate_invalid_json(self):
        response = self.client.post(
            reverse('rates:api_calculate'),
            data='{invalid_json}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_api_commissions_list(self):
        response = self.client.get(reverse('rates:api_commissions'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 1)

    def test_api_commission_detail_found_and_not_found(self):
        res_found = self.client.get(reverse('rates:api_commission_detail', kwargs={'segment': 'MIN'}))
        self.assertEqual(res_found.status_code, 200)
        self.assertEqual(res_found.json()['rule']['segment'], 'MIN')

        res_not_found = self.client.get(reverse('rates:api_commission_detail', kwargs={'segment': 'XYZ'}))
        self.assertEqual(res_not_found.status_code, 404)

    def test_commission_list_filter_inactive(self):
        SegmentCommission.objects.create(
            segment=Cliente.Segmentacion.CORPORATIVO,
            commission_percentage=Decimal('0.80'),
            is_active=False,
        )
        res_inactive = self.client.get(reverse('rates:commission_list'), {'is_active': 'false'})
        self.assertEqual(res_inactive.status_code, 200)
        self.assertEqual(len(res_inactive.context['commissions']), 1)

    def test_rate_calculator_view_post_invalid(self):
        res = self.client.post(
            reverse('rates:rate_calculator'),
            {
                'exchange_rate': '',
                'amount': '-100.00',
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.context['calculation'])

    def test_rate_calculator_view_with_cliente_selector(self):
        cliente = Cliente.objects.create(
            nombre='Cliente Selector Corp',
            documento_ruc='5555555-5',
            correo='corp@test.com',
            segmentacion='COR',
            is_active=True,
        )
        res = self.client.post(
            reverse('rates:rate_calculator'),
            {
                'exchange_rate': self.rate.id,
                'operation_type': 'BUY',
                'amount': '100.00',
                'cliente': cliente.id,
                'is_source_base': True,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.context['calculation'])
        self.assertEqual(res.context['calculation']['segment']['code'], 'COR')


class AdditionalModelAndServiceCoverageTest(TestCase):
    """
    Pruebas auxiliares para alcanzar 100% de cobertura en modelos, servicios y validadores.
    """

    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            is_active=True,
        )
        self.admin_user = User.objects.create_superuser('admin_cov', 'admin_cov@test.com', 'Pass123!')
        self.factory = RequestFactory()

    def test_currency_invalid_code_non_alpha(self):
        c = Currency(code='123', name='Numérica')
        with self.assertRaises(ValidationError):
            c.save()

    def test_exchange_rate_invalid_valid_dates(self):
        now = timezone.now()
        rate_inv = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            valid_from=now,
            valid_to=now - timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            rate_inv.save()

    def test_exchange_rate_is_current_boundary_conditions(self):
        now = timezone.now()
        # Inactiva
        self.rate.is_active = False
        self.assertFalse(self.rate.is_current)
        self.rate.is_active = True

        # Futura
        self.rate.valid_from = now + timedelta(days=1)
        self.assertFalse(self.rate.is_current)

        # Pasada
        self.rate.valid_from = now - timedelta(days=2)
        self.rate.valid_to = now - timedelta(days=1)
        self.assertFalse(self.rate.is_current)

    def test_segment_commission_form_negative_fixed_fee(self):
        form = SegmentCommissionForm(
            data={
                'segment': 'MIN',
                'commission_percentage': '1.00',
                'fixed_fee': '-50.00',
                'spread_discount_percentage': '0.00',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('fixed_fee', form.errors)

    def test_get_active_customer_staff_explicit_param(self):
        c = Cliente.objects.create(nombre='Staff Cliente', documento_ruc='7777777-7', is_active=True)
        request = self.factory.get(f'/?cliente_id={c.id}')
        request.user = self.admin_user
        resolved = get_active_customer(request)
        self.assertEqual(resolved, c)

    def test_rate_calculation_invalid_amount_string(self):
        with self.assertRaises(ValidationError):
            RateCalculationService.calculate_quotation(
                exchange_rate=self.rate,
                amount='abc_invalid',
            )


class CurrencyAndExchangeRateViewsTest(TestCase):
    """
    Pruebas unitarias para las vistas CBVs de Monedas y Tasas de Cambio (SCRUM-51).
    """

    def setUp(self):
        self.user = User.objects.create_user(username='operador_crud', email='op@test.com', password='Password123!')
        self.client.force_login(self.user)
        self.usd = Currency.objects.create(code='USD', name='Dólar Estadounidense', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní Paraguayo', symbol='₲', decimals=0)
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            is_active=True,
        )

    def test_currency_list_view_and_filtering(self):
        res = self.client.get(reverse('rates:currency-list'))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'rates/currency_list.html')
        self.assertIn('currencies', res.context)

        # Filtro por texto
        res_q = self.client.get(reverse('rates:currency-list'), {'q': 'USD'})
        self.assertEqual(res_q.status_code, 200)
        self.assertEqual(len(res_q.context['currencies']), 1)

        # Filtro por inactivo
        res_inact = self.client.get(reverse('rates:currency-list'), {'is_active': 'false'})
        self.assertEqual(res_inact.status_code, 200)
        self.assertEqual(len(res_inact.context['currencies']), 0)

    def test_currency_create_view(self):
        res_get = self.client.get(reverse('rates:currency-create'))
        self.assertEqual(res_get.status_code, 200)
        self.assertTemplateUsed(res_get, 'rates/currency_form.html')

        res_post = self.client.post(
            reverse('rates:currency-create'),
            {
                'code': 'BRL',
                'name': 'Real Brasileño',
                'symbol': 'R$',
                'decimals': 2,
                'is_active': True,
            },
        )
        self.assertEqual(res_post.status_code, 302)
        self.assertTrue(Currency.objects.filter(code='BRL').exists())

    def test_currency_update_view(self):
        res_post = self.client.post(
            reverse('rates:currency-update', kwargs={'pk': self.usd.id}),
            {
                'code': 'USD',
                'name': 'Dólar Americano Modificado',
                'symbol': '$',
                'decimals': 2,
                'is_active': True,
            },
        )
        self.assertEqual(res_post.status_code, 302)
        self.usd.refresh_from_db()
        self.assertEqual(self.usd.name, 'Dólar Americano Modificado')

    def test_currency_toggle_status_view(self):
        res_toggle = self.client.post(reverse('rates:currency-toggle', kwargs={'pk': self.usd.id}))
        self.assertEqual(res_toggle.status_code, 302)
        self.usd.refresh_from_db()
        self.assertFalse(self.usd.is_active)

    def test_exchangerate_list_view_and_filtering(self):
        res = self.client.get(reverse('rates:rate-list'))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'rates/exchangerate_list.html')
        self.assertIn('rates', res.context)

        # Filtro por moneda
        res_cur = self.client.get(reverse('rates:rate-list'), {'currency': self.usd.id})
        self.assertEqual(res_cur.status_code, 200)
        self.assertEqual(len(res_cur.context['rates']), 1)

    def test_exchangerate_create_view(self):
        eur = Currency.objects.create(code='EUR', name='Euro', symbol='€', decimals=2)
        res_post = self.client.post(
            reverse('rates:rate-create'),
            {
                'base_currency': eur.id,
                'target_currency': self.pyg.id,
                'buy_rate': '8000.000000',
                'sell_rate': '8200.000000',
                'is_active': True,
            },
        )
        self.assertEqual(res_post.status_code, 302)
        self.assertTrue(ExchangeRate.objects.filter(base_currency=eur, target_currency=self.pyg).exists())

    def test_exchangerate_update_view(self):
        res_post = self.client.post(
            reverse('rates:rate-update', kwargs={'pk': self.rate.id}),
            {
                'base_currency': self.usd.id,
                'target_currency': self.pyg.id,
                'buy_rate': '7420.000000',
                'sell_rate': '7520.000000',
                'is_active': True,
            },
        )
        self.assertEqual(res_post.status_code, 302)
        self.rate.refresh_from_db()
        self.assertEqual(self.rate.buy_rate, Decimal('7420.000000'))

    def test_exchangerate_toggle_status_view(self):
        res_toggle = self.client.post(reverse('rates:rate-toggle', kwargs={'pk': self.rate.id}))
        self.assertEqual(res_toggle.status_code, 302)
        self.rate.refresh_from_db()
        self.assertFalse(self.rate.is_active)


class ExchangeRateDashboardTests(TestCase):
    """Pruebas del tablero y API de evolución histórica de SCRUM-52."""

    def setUp(self):
        self.user = User.objects.create_user('dashboard_user', password='Password123!')
        self.client.force_login(self.user)
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)
        now = timezone.now()
        self.recent_rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            valid_from=now - timedelta(days=2),
        )
        ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7300.000000'),
            sell_rate=Decimal('7400.000000'),
            valid_from=now - timedelta(days=20),
        )

    def test_dashboard_displays_summary_and_chart_controls(self):
        response = self.client.get(reverse('rates:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'rates/exchange_rate_dashboard.html')
        self.assertEqual(response.context['active_quotes_count'], 1)
        self.assertContains(response, 'Últimos 90 días')
        self.assertContains(response, 'USD/PYG')

    def test_history_api_returns_only_requested_period(self):
        response = self.client.get(
            reverse('rates:api_history'), {'pair': f'{self.usd.id}:{self.pyg.id}', 'period': '7d'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['pair'], 'USD/PYG')
        self.assertEqual(data['buy_rates'], [7400.0])
        self.assertEqual(data['sell_rates'], [7500.0])

    def test_history_api_rejects_invalid_parameters(self):
        invalid_period = self.client.get(reverse('rates:api_history'), {'pair': '1:2', 'period': '2y'})
        invalid_pair = self.client.get(reverse('rates:api_history'), {'pair': 'USD/PYG', 'period': '7d'})
        self.assertEqual(invalid_period.status_code, 400)
        self.assertEqual(invalid_pair.status_code, 400)

    def test_dashboard_and_api_require_authentication(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('rates:dashboard')).status_code, 302)
        self.assertEqual(self.client.get(reverse('rates:api_history')).status_code, 302)


# ==============================================================================
# PRUEBAS DEL SERVICIO DE CONGELAMIENTO DE COTIZACIONES (SCRUM-54)
# ==============================================================================

class QuoteFreezeServiceTest(TestCase):
    """
    Pruebas unitarias para QuoteFreezeService y la gestión de tokens con temporizador de 5 minutos.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='freeze_tester',
            email='freeze@example.com',
            password='Password123!',
        )
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
        )
        self.calc_data = {
            'official_rate': Decimal('7400.000000'),
            'effective_rate': Decimal('7420.000000'),
            'base_amount': Decimal('100.00'),
            'net_target_amount': Decimal('742000.00'),
            'operation_type': 'BUY',
        }

    def _get_request_with_session(self):
        request = self.factory.get('/rates/calculator/')
        request.user = self.user
        # Simular sesión de Django
        session_middleware = type('MockSession', (), {})()
        session_data = {}

        class MockSession(dict):
            modified = False

        request.session = MockSession()
        return request

    def test_freeze_quote_generates_token_and_payload(self):
        request = self._get_request_with_session()
        result = QuoteFreezeService.freeze_quote(request, self.calc_data)

        self.assertTrue(result['success'])
        self.assertTrue(result['token'].startswith('QTZ-'))
        self.assertEqual(result['duration_seconds'], 300)
        self.assertEqual(result['remaining_seconds'], 300)
        self.assertFalse(result['is_expired'])
        self.assertEqual(result['calculation']['base_amount'], 100.0)
        self.assertIn('frozen_quote', request.session)
        self.assertTrue(request.session.modified)

    def test_get_frozen_quote_calculates_remaining_time(self):
        request = self._get_request_with_session()
        freeze_res = QuoteFreezeService.freeze_quote(request, self.calc_data)
        token = freeze_res['token']

        quote = QuoteFreezeService.get_frozen_quote(request, token=token)
        self.assertIsNotNone(quote)
        self.assertEqual(quote['token'], token)
        self.assertFalse(quote['is_expired'])
        self.assertGreaterEqual(quote['remaining_seconds'], 295)
        self.assertLessEqual(quote['remaining_seconds'], 300)

    def test_get_frozen_quote_detects_expiration(self):
        request = self._get_request_with_session()
        QuoteFreezeService.freeze_quote(request, self.calc_data)

        # Forzar expiración simulando timestamp vencido en sesión
        expired_time = timezone.now() - timedelta(minutes=6)
        request.session['frozen_quote']['expires_at'] = expired_time.isoformat()

        quote = QuoteFreezeService.get_frozen_quote(request)
        self.assertIsNotNone(quote)
        self.assertTrue(quote['is_expired'])
        self.assertEqual(quote['remaining_seconds'], 0)

    def test_unfreeze_quote_clears_session(self):
        request = self._get_request_with_session()
        res = QuoteFreezeService.freeze_quote(request, self.calc_data)
        token = res['token']

        # Descongelar con token correcto
        cleared = QuoteFreezeService.unfreeze_quote(request, token=token)
        self.assertTrue(cleared)
        self.assertNotIn('frozen_quote', request.session)

        # Intentar descongelar nuevamente retorna False
        cleared_again = QuoteFreezeService.unfreeze_quote(request, token=token)
        self.assertFalse(cleared_again)

    def test_validate_quote_token_states(self):
        request = self._get_request_with_session()
        res = QuoteFreezeService.freeze_quote(request, self.calc_data)
        token = res['token']

        # Token válido
        is_valid, data, msg = QuoteFreezeService.validate_quote_token(request, token)
        self.assertTrue(is_valid)
        self.assertIsNotNone(data)

        # Token inválido / no existente
        is_valid_fake, _, _ = QuoteFreezeService.validate_quote_token(request, 'QTZ-INVALID')
        self.assertFalse(is_valid_fake)

        # Token expirado
        request.session['frozen_quote']['expires_at'] = (timezone.now() - timedelta(seconds=10)).isoformat()
        is_valid_exp, _, msg_exp = QuoteFreezeService.validate_quote_token(request, token)
        self.assertFalse(is_valid_exp)
        self.assertIn('expirado', msg_exp)


# ==============================================================================
# PRUEBAS DE ENDPOINTS API DE CONGELAMIENTO (SCRUM-54)
# ==============================================================================

class QuoteFreezeApiTests(TestCase):
    """
    Pruebas de integración para los endpoints API REST de congelamiento de cotizaciones.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='api_client_user',
            password='Password123!',
        )
        self.client.force_login(self.user)
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            is_active=True,
        )

    def test_api_freeze_quote_success(self):
        payload = {
            'exchange_rate_id': self.rate.id,
            'amount': '250.00',
            'operation_type': 'BUY',
            'is_source_base': True,
        }
        res = self.client.post(
            reverse('rates:api_freeze'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('frozen_quote', data)
        self.assertTrue(data['frozen_quote']['token'].startswith('QTZ-'))
        self.assertEqual(data['frozen_quote']['duration_seconds'], 300)

    def test_api_get_frozen_quote_returns_active_quote(self):
        # Primero congelamos
        payload = {
            'exchange_rate_id': self.rate.id,
            'amount': '100.00',
            'operation_type': 'SELL',
        }
        self.client.post(
            reverse('rates:api_freeze'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        # Consultamos el estado activo
        res_get = self.client.get(reverse('rates:api_frozen_quote'))
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.json()
        self.assertTrue(data_get['success'])
        self.assertFalse(data_get['is_expired'])
        self.assertGreater(data_get['remaining_seconds'], 0)

    def test_api_unfreeze_quote(self):
        # Congelar
        payload = {'exchange_rate_id': self.rate.id, 'amount': '150.00'}
        freeze_res = self.client.post(
            reverse('rates:api_freeze'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        token = freeze_res.json()['frozen_quote']['token']

        # Descongelar
        unfreeze_res = self.client.post(
            reverse('rates:api_unfreeze'),
            data=json.dumps({'token': token}),
            content_type='application/json',
        )
        self.assertEqual(unfreeze_res.status_code, 200)
        self.assertTrue(unfreeze_res.json()['cleared'])

        # Verificar que ya no hay cotización congelada
        check_res = self.client.get(reverse('rates:api_frozen_quote'))
        self.assertEqual(check_res.status_code, 404)

    def test_api_freeze_quote_missing_rate(self):
        payload = {'exchange_rate_id': 99999, 'amount': '100.00'}
        res = self.client.post(
            reverse('rates:api_freeze'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 404)


# ==============================================================================
# PRUEBAS DE VISTA DEL COTIZADOR Y TEMPORIZADOR (SCRUM-54)
# ==============================================================================

class RateCalculatorInteractiveViewTests(TestCase):
    """
    Pruebas de la interfaz de usuario del cotizador y su integración con el temporizador de congelamiento.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='calc_user', password='Password123!')
        self.client.force_login(self.user)
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)
        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.000000'),
            sell_rate=Decimal('7500.000000'),
            is_active=True,
        )

    def test_rate_calculator_get_view(self):
        response = self.client.get(reverse('rates:rate_calculator'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'rates/rate_calculator.html')
        self.assertIn('form', response.context)
        self.assertIn('currencies', response.context)
        self.assertContains(response, 'Simulador Interactivo de Cotizaciones')
        self.assertContains(response, 'Congelar Cotización por 5 Minutos')

    def test_rate_calculator_post_calculation_success(self):
        response = self.client.post(
            reverse('rates:rate_calculator'),
            {
                'exchange_rate': self.rate.id,
                'amount': '500.00',
                'operation_type': 'BUY',
                'is_source_base': 'on',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['calculation'])
        self.assertContains(response, 'USD/PYG')
        self.assertContains(response, 'Desglose de Tarifas y Beneficios')

    def test_rate_calculator_displays_frozen_quote_banner(self):
        # Congelar primero una cotización en sesión
        payload = {
            'exchange_rate_id': self.rate.id,
            'amount': '300.00',
            'operation_type': 'BUY',
        }
        freeze_res = self.client.post(
            reverse('rates:api_freeze'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        token = freeze_res.json()['frozen_quote']['token']

        # Cargar página del cotizador
        response = self.client.get(reverse('rates:rate_calculator'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['frozen_quote'])
        self.assertEqual(response.context['frozen_quote']['token'], token)
        self.assertContains(response, token)
        self.assertContains(response, 'Cotización Congelada')
        self.assertContains(response, 'countdownDisplay')


# ==============================================================================
# PRUEBAS PARA LÍMITES OPERATIVOS (SCRUM-77)
# ==============================================================================

class OperationLimitModelTest(TestCase):
    """
    Pruebas unitarias para el modelo OperationLimit (Límites por Segmento y Moneda).
    """

    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)

    def test_operation_limit_creation_and_defaults(self):
        limit = OperationLimit.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('50.00'),
            monto_maximo=Decimal('5000.00'),
            limite_diario=Decimal('10000.00'),
            limite_mensual=Decimal('50000.00'),
            is_active=True,
        )
        self.assertEqual(limit.segment, 'MIN')
        self.assertEqual(limit.currency, self.usd)
        self.assertEqual(limit.monto_minimo, Decimal('50.00'))
        self.assertEqual(limit.monto_maximo, Decimal('5000.00'))
        self.assertEqual(limit.limite_diario, Decimal('10000.00'))
        self.assertEqual(limit.limite_mensual, Decimal('50000.00'))
        self.assertTrue(limit.is_active)
        self.assertIsNotNone(limit.created_at)
        self.assertIsNotNone(limit.updated_at)
        self.assertIn('Minorista', str(limit))
        self.assertIn('USD', str(limit))

    def test_operation_limit_str_representation(self):
        limit = OperationLimit.objects.create(
            segment=Cliente.Segmentacion.VIP,
            currency=self.usd,
            monto_minimo=Decimal('100.00'),
            monto_maximo=Decimal('100000.00'),
            limite_diario=Decimal('200000.00'),
            limite_mensual=Decimal('1000000.00'),
        )
        self.assertIn('VIP', str(limit))
        self.assertIn('USD', str(limit))
        self.assertIn('100.00', str(limit))
        self.assertIn('100000.00', str(limit))

    def test_operation_limit_uniqueness_segment_currency(self):
        OperationLimit.objects.create(
            segment=Cliente.Segmentacion.CORPORATIVO,
            currency=self.usd,
            monto_minimo=Decimal('100.00'),
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                OperationLimit.objects.create(
                    segment=Cliente.Segmentacion.CORPORATIVO,
                    currency=self.usd,
                    monto_minimo=Decimal('200.00'),
                )

    def test_operation_limit_negative_amounts_validation(self):
        invalid_limit = OperationLimit(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('-10.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_limit.save()
        self.assertIn('monto_minimo', ctx.exception.message_dict)

    def test_operation_limit_monto_minimo_exceeds_monto_maximo(self):
        invalid_limit = OperationLimit(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('500.00'),
            monto_maximo=Decimal('200.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_limit.save()
        self.assertIn('monto_minimo', ctx.exception.message_dict)

    def test_operation_limit_monto_maximo_exceeds_limite_diario(self):
        invalid_limit = OperationLimit(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('50.00'),
            monto_maximo=Decimal('6000.00'),
            limite_diario=Decimal('5000.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_limit.save()
        self.assertIn('monto_maximo', ctx.exception.message_dict)

    def test_operation_limit_limite_diario_exceeds_limite_mensual(self):
        invalid_limit = OperationLimit(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('50.00'),
            monto_maximo=Decimal('2000.00'),
            limite_diario=Decimal('15000.00'),
            limite_mensual=Decimal('10000.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_limit.save()
        self.assertIn('limite_diario', ctx.exception.message_dict)

    def test_operation_limit_model_validate_amount(self):
        limit = OperationLimit.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('50.00'),
            monto_maximo=Decimal('1000.00'),
            limite_diario=Decimal('2000.00'),
            limite_mensual=Decimal('10000.00'),
        )
        # 1. Monto válido
        res_ok = limit.validate_amount(Decimal('100.00'))
        self.assertTrue(res_ok['is_valid'])
        self.assertEqual(len(res_ok['errors']), 0)
        self.assertEqual(res_ok['remaining_daily'], Decimal('1900.00'))
        self.assertEqual(res_ok['remaining_monthly'], Decimal('9900.00'))

        # 2. Monto bajo el mínimo
        res_low = limit.validate_amount(Decimal('20.00'))
        self.assertFalse(res_low['is_valid'])
        self.assertIn('inferior al mínimo', res_low['errors'][0])

        # 3. Monto sobre el máximo
        res_high = limit.validate_amount(Decimal('1500.00'))
        self.assertFalse(res_high['is_valid'])
        self.assertIn('supera el máximo', res_high['errors'][0])

        # 4. Supera límite diario con acumulado
        res_daily = limit.validate_amount(Decimal('600.00'), accumulated_daily=Decimal('1600.00'))
        self.assertFalse(res_daily['is_valid'])
        self.assertTrue(any('límite diario' in e for e in res_daily['errors']))

        # 5. Supera límite mensual con acumulado
        res_monthly = limit.validate_amount(Decimal('600.00'), accumulated_monthly=Decimal('9800.00'))
        self.assertFalse(res_monthly['is_valid'])
        self.assertTrue(any('límite mensual' in e for e in res_monthly['errors']))


class OperationLimitValidationServiceTest(TestCase):
    """
    Pruebas unitarias para el servicio OperationLimitValidationService.
    """

    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)

        self.cliente_min = Cliente.objects.create(
            nombre='Juan Pérez',
            documento_ruc='1234567-8',
            correo='juan@example.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
        )
        self.cliente_vip = Cliente.objects.create(
            nombre='Empresa VIP',
            documento_ruc='80001234-5',
            correo='vip@empresa.com',
            segmentacion=Cliente.Segmentacion.VIP,
        )

        self.limit_min_usd = OperationLimit.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('50.00'),
            monto_maximo=Decimal('3000.00'),
            limite_diario=Decimal('6000.00'),
            limite_mensual=Decimal('30000.00'),
            is_active=True,
        )

        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7400.00'),
            sell_rate=Decimal('7500.00'),
            is_active=True,
        )

    def test_get_limit_rule_by_customer(self):
        rule = OperationLimitValidationService.get_limit_rule(self.cliente_min, self.usd)
        self.assertIsNotNone(rule)
        self.assertEqual(rule.id, self.limit_min_usd.id)

    def test_get_limit_rule_by_segment_string(self):
        rule = OperationLimitValidationService.get_limit_rule('MIN', 'USD')
        self.assertIsNotNone(rule)
        self.assertEqual(rule.id, self.limit_min_usd.id)

    def test_get_limit_rule_non_existent(self):
        rule = OperationLimitValidationService.get_limit_rule(self.cliente_vip, self.usd)
        self.assertIsNone(rule)

    def test_validate_operation_amount_success(self):
        result = OperationLimitValidationService.validate_operation_amount(
            segment_or_customer=self.cliente_min,
            currency='USD',
            amount=Decimal('500.00'),
        )
        self.assertTrue(result['is_valid'])
        self.assertTrue(result['has_rule'])
        self.assertEqual(result['monto_minimo'], Decimal('50.00'))
        self.assertEqual(result['remaining_daily'], Decimal('5500.00'))
        self.assertEqual(result['remaining_monthly'], Decimal('29500.00'))

    def test_validate_operation_amount_below_minimum(self):
        result = OperationLimitValidationService.validate_operation_amount(
            segment_or_customer=self.cliente_min,
            currency=self.usd,
            amount=Decimal('25.00'),
        )
        self.assertFalse(result['is_valid'])
        self.assertIn('inferior al mínimo', result['errors'][0])

    def test_validate_operation_amount_exceeds_maximum(self):
        result = OperationLimitValidationService.validate_operation_amount(
            segment_or_customer=self.cliente_min,
            currency=self.usd,
            amount=Decimal('3500.00'),
        )
        self.assertFalse(result['is_valid'])
        self.assertIn('supera el máximo', result['errors'][0])

    def test_validate_operation_amount_exceeds_daily_accumulated(self):
        result = OperationLimitValidationService.validate_operation_amount(
            segment_or_customer=self.cliente_min,
            currency=self.usd,
            amount=Decimal('2000.00'),
            accumulated_daily=Decimal('5000.00'),
        )
        self.assertFalse(result['is_valid'])
        self.assertTrue(any('límite diario' in err for err in result['errors']))

    def test_validate_operation_amount_exceeds_monthly_accumulated(self):
        result = OperationLimitValidationService.validate_operation_amount(
            segment_or_customer=self.cliente_min,
            currency=self.usd,
            amount=Decimal('1000.00'),
            accumulated_monthly=Decimal('29500.00'),
        )
        self.assertFalse(result['is_valid'])
        self.assertTrue(any('límite mensual' in err for err in result['errors']))

    def test_validate_operation_amount_without_rule(self):
        result = OperationLimitValidationService.validate_operation_amount(
            segment_or_customer=self.cliente_vip,
            currency=self.usd,
            amount=Decimal('999999.00'),
        )
        self.assertTrue(result['is_valid'])
        self.assertFalse(result['has_rule'])

    def test_validate_operation_amount_raise_exception(self):
        with self.assertRaises(ValidationError):
            OperationLimitValidationService.validate_operation_amount(
                segment_or_customer=self.cliente_min,
                currency=self.usd,
                amount=Decimal('10.00'),
                raise_exception=True,
            )

    def test_calculate_quotation_includes_limits_payload(self):
        calc = RateCalculationService.calculate_quotation(
            exchange_rate=self.rate,
            segment_or_customer=self.cliente_min,
            amount=Decimal('500.00'),
            operation_type='BUY',
            is_source_base=True,
            validate_limits=True,
        )
        self.assertIn('limits', calc)
        self.assertIsNotNone(calc['limits'])
        self.assertTrue(calc['limits']['is_valid'])
        self.assertEqual(calc['limits']['monto_minimo'], Decimal('50.00'))

    def test_calculate_quotation_raise_on_limit_violation(self):
        with self.assertRaises(ValidationError):
            RateCalculationService.calculate_quotation(
                exchange_rate=self.rate,
                segment_or_customer=self.cliente_min,
                amount=Decimal('10.00'),
                operation_type='BUY',
                is_source_base=True,
                validate_limits=True,
                raise_on_limit_violation=True,
            )


class OperationLimitFormTest(TestCase):
    """
    Pruebas unitarias para formularios OperationLimitForm y OperationLimitFilterForm.
    """

    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)

    def test_operation_limit_form_valid(self):
        data = {
            'segment': 'MIN',
            'currency': self.usd.id,
            'monto_minimo': '10.00',
            'monto_maximo': '1000.00',
            'limite_diario': '2000.00',
            'limite_mensual': '10000.00',
            'is_active': True,
        }
        form = OperationLimitForm(data=data)
        self.assertTrue(form.is_valid())

    def test_operation_limit_form_invalid_hierarchy(self):
        data = {
            'segment': 'MIN',
            'currency': self.usd.id,
            'monto_minimo': '500.00',
            'monto_maximo': '100.00',
            'limite_diario': '2000.00',
            'limite_mensual': '10000.00',
            'is_active': True,
        }
        form = OperationLimitForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('monto_minimo', form.errors)

    def test_operation_limit_filter_form(self):
        form = OperationLimitFilterForm(data={'segment': 'MIN', 'is_active': 'true'})
        self.assertTrue(form.is_valid())


class OperationLimitViewsTest(TestCase):
    """
    Pruebas para las vistas CBVs de gestión de límites operativos.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='admin_user', password='password123', is_staff=True)
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.limit = OperationLimit.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('50.00'),
            monto_maximo=Decimal('2000.00'),
            limite_diario=Decimal('5000.00'),
            limite_mensual=Decimal('20000.00'),
            is_active=True,
        )

    def test_limit_list_view_authenticated(self):
        self.client.login(username='admin_user', password='password123')
        response = self.client.get(reverse('rates:limit_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Límites Operativos')
        self.assertContains(response, 'USD')
        self.assertContains(response, 'Minorista')

    def test_limit_create_view(self):
        self.client.login(username='admin_user', password='password123')
        pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)
        response = self.client.post(
            reverse('rates:limit_create'),
            data={
                'segment': 'MAY',
                'currency': pyg.id,
                'monto_minimo': '100000.00',
                'monto_maximo': '50000000.00',
                'limite_diario': '100000000.00',
                'limite_mensual': '500000000.00',
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(OperationLimit.objects.filter(segment='MAY', currency=pyg).exists())

    def test_limit_update_view(self):
        self.client.login(username='admin_user', password='password123')
        response = self.client.post(
            reverse('rates:limit_update', args=[self.limit.id]),
            data={
                'segment': 'MIN',
                'currency': self.usd.id,
                'monto_minimo': '100.00',
                'monto_maximo': '3000.00',
                'limite_diario': '8000.00',
                'limite_mensual': '30000.00',
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.limit.refresh_from_db()
        self.assertEqual(self.limit.monto_minimo, Decimal('100.00'))

    def test_limit_detail_view(self):
        self.client.login(username='admin_user', password='password123')
        response = self.client.get(reverse('rates:limit_detail', args=[self.limit.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Política de Límites Operativos')
        self.assertContains(response, 'Simulación de Validaciones')

    def test_limit_delete_view(self):
        self.client.login(username='admin_user', password='password123')
        response = self.client.post(reverse('rates:limit_delete', args=[self.limit.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OperationLimit.objects.filter(id=self.limit.id).exists())


class OperationLimitApiViewsTest(TestCase):
    """
    Pruebas para los endpoints API REST JSON de límites operativos.
    """

    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$', decimals=2)
        self.limit = OperationLimit.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            currency=self.usd,
            monto_minimo=Decimal('50.00'),
            monto_maximo=Decimal('2000.00'),
            limite_diario=Decimal('5000.00'),
            limite_mensual=Decimal('20000.00'),
            is_active=True,
        )

    def test_api_limits_list(self):
        response = self.client.get(reverse('rates:api_limits'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['segment'], 'MIN')

    def test_api_limit_detail(self):
        response = self.client.get(reverse('rates:api_limit_detail', args=['MIN', 'USD']))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['limit']['monto_minimo'], 50.0)

    def test_api_limit_detail_not_found(self):
        response = self.client.get(reverse('rates:api_limit_detail', args=['VIP', 'USD']))
        self.assertEqual(response.status_code, 404)

    def test_api_limits_validate_valid_amount(self):
        payload = {
            'segment': 'MIN',
            'currency': 'USD',
            'amount': '500.00',
        }
        response = self.client.post(
            reverse('rates:api_limits_validate'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['validation']['is_valid'])

    def test_api_limits_validate_invalid_amount_below_min(self):
        payload = {
            'segment': 'MIN',
            'currency': 'USD',
            'amount': '10.00',
        }
        response = self.client.post(
            reverse('rates:api_limits_validate'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertFalse(data['validation']['is_valid'])
        self.assertIn('inferior al mínimo', data['validation']['errors'][0])


class CurrencyFiltersTemplateTagTest(TestCase):
    """
    Pruebas unitarias para las etiquetas y filtros de plantilla monetarios (SCRUM-83 / SCRUM-70).
    Verifica formateo estándar paraguayo/latinoamericano: miles con punto (.) y decimales con coma (,).
    """

    def setUp(self):
        self.pyg = Currency.objects.create(
            code='PYG',
            name='Guaraní Paraguayo',
            symbol='₲',
            decimals=0,
        )
        self.usd = Currency.objects.create(
            code='USD',
            name='Dólar Estadounidense',
            symbol='$',
            decimals=2,
        )
        self.eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€',
            decimals=2,
        )

    def test_format_currency_with_currency_model_pyg(self):
        """PYG no utiliza decimales y antepone el símbolo ₲."""
        result = format_currency(Decimal('7500000'), self.pyg)
        self.assertEqual(result, '₲ 7.500.000')

        result_int = format_currency(7500000, self.pyg)
        self.assertEqual(result_int, '₲ 7.500.000')

    def test_format_currency_with_currency_model_usd(self):
        """USD utiliza 2 decimales y antepone el símbolo $."""
        result = format_currency(Decimal('1250.50'), self.usd)
        self.assertEqual(result, '$ 1.250,50')

        result_float = format_currency(1250.5, self.usd)
        self.assertEqual(result_float, '$ 1.250,50')

    def test_format_currency_without_currency_object(self):
        """Sin objeto Currency utiliza 2 decimales por defecto sin símbolo."""
        result = format_currency(Decimal('1250.50'))
        self.assertEqual(result, '1.250,50')

    def test_format_currency_empty_and_none(self):
        """Valores vacíos o None retornan cadena vacía."""
        self.assertEqual(format_currency(None), '')
        self.assertEqual(format_currency(''), '')
        self.assertEqual(format_currency(None, self.usd), '')

    def test_format_number_various_decimal_places(self):
        """format_number formatea con separadores de miles (.) y decimales (,)."""
        self.assertEqual(format_number(1250.5, 2), '1.250,50')
        self.assertEqual(format_number(7500000, 0), '7.500.000')
        self.assertEqual(format_number(1000000.1234, 4), '1.000.000,1234')
        self.assertEqual(format_number(-1250.5, 2), '-1.250,50')
        self.assertEqual(format_number(0, 2), '0,00')

    def test_format_number_invalid_values(self):
        """Valores no numéricos retornan el valor original o cadena vacía."""
        self.assertEqual(format_number(None), '')
        self.assertEqual(format_number(''), '')
        self.assertEqual(format_number('invalido'), 'invalido')

    def test_format_rate_precision(self):
        """format_rate maneja tasas con 2 decimales por defecto y hasta 6 decimales."""
        self.assertEqual(format_rate(Decimal('7450.00')), '7.450,00')
        self.assertEqual(format_rate(Decimal('0.000134')), '0,000134')
        self.assertEqual(format_rate(Decimal('150.0000'), 4), '150,0000')
        self.assertEqual(format_rate(None), '')
        self.assertEqual(format_rate(''), '')



