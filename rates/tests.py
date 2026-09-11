"""
Módulo de pruebas unitarias para la aplicación rates (SCRUM-50).

Verifica la integridad de datos, lógica de negocio y restricciones de validación para:
- :class:`~rates.models.Currency`
- :class:`~rates.models.ExchangeRate`
- :class:`~rates.models.SegmentCommission`
"""

from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.db import models, IntegrityError, transaction
from django.test import TestCase, RequestFactory
from django.utils import timezone

from customers.models import Cliente
from rates.admin import ExchangeRateAdmin
from rates.models import Currency, ExchangeRate, SegmentCommission

User = get_user_model()


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
        """Verifica la creación básica y los valores por defecto del modelo Currency."""
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
        """Verifica el formato del método __str__ de Currency."""
        self.assertEqual(str(self.usd), 'USD - Dólar Estadounidense ($)')

    def test_currency_code_normalization_and_stripping(self):
        """Verifica que clean() convierta el código ISO a mayúsculas y limpie espacios en blanco."""
        eur = Currency(
            code=' eur ',
            name=' Euro ',
            symbol=' € ',
        )
        eur.save()
        self.assertEqual(eur.code, 'EUR')
        self.assertEqual(eur.name, 'Euro')
        self.assertEqual(eur.symbol, '€')

    def test_currency_invalid_code_length(self):
        """Verifica que falle la validación si el código ISO no tiene exactamente 3 caracteres."""
        invalid_short = Currency(code='US', name='Dólar', symbol='$')
        with self.assertRaises(ValidationError) as ctx:
            invalid_short.full_clean()
        self.assertIn('code', ctx.exception.message_dict)

        invalid_long = Currency(code='USDT', name='Tether', symbol='$')
        with self.assertRaises(ValidationError) as ctx:
            invalid_long.full_clean()
        self.assertIn('code', ctx.exception.message_dict)

    def test_currency_invalid_code_non_alpha(self):
        """Verifica que falle la validación si el código ISO contiene caracteres no alfabéticos."""
        invalid_numeric = Currency(code='U12', name='Moneda Invalida', symbol='$')
        with self.assertRaises(ValidationError) as ctx:
            invalid_numeric.full_clean()
        self.assertIn('code', ctx.exception.message_dict)

    def test_currency_unique_code(self):
        """Verifica que el código ISO sea único en la base de datos."""
        with self.assertRaises((ValidationError, IntegrityError)):
            Currency.objects.create(
                code='USD',
                name='Otro Dólar',
                symbol='$',
            )


class ExchangeRateModelTest(TestCase):
    """
    Pruebas unitarias para el modelo ExchangeRate (Tasas de Cambio y Cotizaciones).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='cambista',
            email='cambista@globalexchange.com',
            password='Password123!',
        )
        self.usd = Currency.objects.create(
            code='USD',
            name='Dólar Estadounidense',
            symbol='$',
            decimals=2,
        )
        self.pyg = Currency.objects.create(
            code='PYG',
            name='Guaraní Paraguayo',
            symbol='₲',
            decimals=0,
        )

    def test_exchange_rate_creation_and_auto_spread(self):
        """Verifica el cálculo automático del spread al persistir una cotización."""
        rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.000000'),
            sell_rate=Decimal('7850.000000'),
            updated_by=self.user,
        )
        self.assertEqual(rate.spread, Decimal('50.000000'))
        self.assertTrue(rate.is_active)
        self.assertIn('USD/PYG', str(rate))
        self.assertIn('Compra: 7800.000000', str(rate))
        self.assertIn('Venta: 7850.000000', str(rate))
        self.assertIn('Spread: 50.000000', str(rate))

    def test_same_base_and_target_currency_rejected(self):
        """Verifica que no se permita una cotización con la misma moneda base y destino."""
        rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.usd,
            buy_rate=Decimal('1.000000'),
            sell_rate=Decimal('1.000000'),
        )
        with self.assertRaises(ValidationError) as ctx:
            rate.full_clean()
        self.assertIn('target_currency', ctx.exception.message_dict)

    def test_negative_or_zero_rates_rejected(self):
        """Verifica que las tasas de compra y venta deban ser estrictamente mayores a cero."""
        zero_buy = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('0.000000'),
            sell_rate=Decimal('7800.000000'),
        )
        with self.assertRaises(ValidationError) as ctx:
            zero_buy.full_clean()
        self.assertIn('buy_rate', ctx.exception.message_dict)

        negative_sell = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.000000'),
            sell_rate=Decimal('-10.000000'),
        )
        with self.assertRaises(ValidationError) as ctx:
            negative_sell.full_clean()
        self.assertIn('sell_rate', ctx.exception.message_dict)

    def test_sell_rate_less_than_buy_rate_rejected(self):
        """Verifica que la tasa de venta no pueda ser menor a la tasa de compra (margen negativo)."""
        rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7900.000000'),
            sell_rate=Decimal('7800.000000'),
        )
        with self.assertRaises(ValidationError) as ctx:
            rate.full_clean()
        self.assertIn('sell_rate', ctx.exception.message_dict)

    def test_valid_to_before_valid_from_rejected(self):
        """Verifica que valid_to deba ser posterior a valid_from."""
        now = timezone.now()
        rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.000000'),
            sell_rate=Decimal('7850.000000'),
            valid_from=now,
            valid_to=now - timedelta(hours=1),
        )
        with self.assertRaises(ValidationError) as ctx:
            rate.full_clean()
        self.assertIn('valid_to', ctx.exception.message_dict)

    def test_is_current_property(self):
        """Evalúa las diferentes condiciones de vigencia temporal de una cotización."""
        now = timezone.now()

        # 1. Vigente activa y sin fecha límite
        rate_open = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.000000'),
            sell_rate=Decimal('7850.000000'),
            valid_from=now - timedelta(minutes=5),
            valid_to=None,
            is_active=True,
        )
        self.assertTrue(rate_open.is_current)

        # 2. Inactiva manualmente
        rate_open.is_active = False
        self.assertFalse(rate_open.is_current)

        # 3. Vigencia en el futuro
        future_rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.000000'),
            sell_rate=Decimal('7850.000000'),
            valid_from=now + timedelta(days=1),
            is_active=True,
        )
        self.assertFalse(future_rate.is_current)

        # 4. Vigencia expirada en el pasado
        past_rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.000000'),
            sell_rate=Decimal('7850.000000'),
            valid_from=now - timedelta(days=2),
            valid_to=now - timedelta(days=1),
            is_active=True,
        )
        self.assertFalse(past_rate.is_current)

    def test_currency_protect_on_delete(self):
        """Verifica que una divisa no pueda eliminarse si está asociada a tasas de cambio."""
        ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.000000'),
            sell_rate=Decimal('7850.000000'),
        )
        with self.assertRaises(models.ProtectedError):
            with transaction.atomic():
                self.usd.delete()


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
            spread_discount_percentage=Decimal('30.00'),
            is_active=True,
        )

    def test_segment_commission_str_representation(self):
        """Verifica la representación __str__ de la regla de comisión por segmento."""
        self.assertIn('Minorista', str(self.commission_min))
        self.assertIn('1.50%', str(self.commission_min))
        self.assertIn('5000.00 fijo', str(self.commission_min))

    def test_unique_segment_constraint(self):
        """Verifica que no se puedan registrar dos reglas para el mismo segmento."""
        with self.assertRaises((ValidationError, IntegrityError)):
            SegmentCommission.objects.create(
                segment=Cliente.Segmentacion.MINORISTA,
                commission_percentage=Decimal('2.00'),
            )

    def test_commission_percentage_range_validation(self):
        """Verifica que el porcentaje de comisión esté restringido entre 0.00% y 100.00%."""
        neg = SegmentCommission(
            segment=Cliente.Segmentacion.MAYORISTA,
            commission_percentage=Decimal('-1.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            neg.full_clean()
        self.assertIn('commission_percentage', ctx.exception.message_dict)

        over = SegmentCommission(
            segment=Cliente.Segmentacion.MAYORISTA,
            commission_percentage=Decimal('100.01'),
        )
        with self.assertRaises(ValidationError) as ctx:
            over.full_clean()
        self.assertIn('commission_percentage', ctx.exception.message_dict)

    def test_fixed_fee_negative_validation(self):
        """Verifica que el cargo fijo no pueda ser negativo."""
        neg_fee = SegmentCommission(
            segment=Cliente.Segmentacion.CORPORATIVO,
            fixed_fee=Decimal('-500.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            neg_fee.full_clean()
        self.assertIn('fixed_fee', ctx.exception.message_dict)

    def test_spread_discount_percentage_range_validation(self):
        """Verifica que el descuento sobre el spread esté entre 0.00% y 100.00%."""
        over_discount = SegmentCommission(
            segment=Cliente.Segmentacion.CORPORATIVO,
            spread_discount_percentage=Decimal('105.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            over_discount.full_clean()
        self.assertIn('spread_discount_percentage', ctx.exception.message_dict)

    def test_calculate_commission(self):
        """Verifica el cálculo de comisiones (porcentual + fija) para diversos montos."""
        # Minorista: 1.5% de 1.000.000 = 15.000 + 5.000 fijo = 20.000
        amount = Decimal('1000000.00')
        calc_min = self.commission_min.calculate_commission(amount)
        self.assertEqual(calc_min, Decimal('20000.00'))

        # VIP: 0.25% de 1.000.000 = 2.500 + 0 fijo = 2.500
        calc_vip = self.commission_vip.calculate_commission(amount)
        self.assertEqual(calc_vip, Decimal('2500.00'))

        # Monto 0 o negativo retorna 0.00
        self.assertEqual(self.commission_min.calculate_commission(Decimal('0')), Decimal('0.00'))
        self.assertEqual(self.commission_min.calculate_commission(Decimal('-500')), Decimal('0.00'))

        # Regla inactiva retorna 0.00
        self.commission_min.is_active = False
        self.assertEqual(self.commission_min.calculate_commission(amount), Decimal('0.00'))

    def test_apply_spread_discount(self):
        """Verifica la aplicación de descuentos sobre el spread."""
        spread = Decimal('100.000000')

        # Minorista: 0% descuento -> 100
        self.assertEqual(self.commission_min.apply_spread_discount(spread), Decimal('100.000000'))

        # VIP: 30% descuento -> 100 - 30 = 70
        self.assertEqual(self.commission_vip.apply_spread_discount(spread), Decimal('70.000000'))

        # Regla inactiva -> retorna spread original
        self.commission_vip.is_active = False
        self.assertEqual(self.commission_vip.apply_spread_discount(spread), Decimal('100.000000'))


class RatesAdminTest(TestCase):
    """
    Pruebas unitarias para las personalizaciones del Django Admin en rates.
    """

    def setUp(self):
        self.site = AdminSite()
        self.user = User.objects.create_superuser(
            username='admin_rates',
            email='admin@globalexchange.com',
            password='AdminPassword123!',
        )
        self.factory = RequestFactory()
        self.usd = Currency.objects.create(code='USD', name='Dólar', symbol='$')
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní', symbol='₲', decimals=0)

    def test_exchange_rate_admin_save_model_assigns_user(self):
        """Verifica que ExchangeRateAdmin.save_model asigne el usuario autenticado automáticamente."""
        admin_obj = ExchangeRateAdmin(ExchangeRate, self.site)
        rate = ExchangeRate(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.000000'),
            sell_rate=Decimal('7850.000000'),
        )

        request = self.factory.post('/admin/rates/exchangerate/add/')
        request.user = self.user

        admin_obj.save_model(request, rate, form=None, change=False)
        self.assertEqual(rate.updated_by, self.user)
