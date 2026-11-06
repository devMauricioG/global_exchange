"""Carga inicial segura de catálogos operativos para producción."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from customers.models import Cliente
from rates.models import Currency, ExchangeRate, OperationLimit, SegmentCommission


class Command(BaseCommand):
    help = (
        "Crea los catálogos mínimos de operación sin usuarios, clientes ni datos demo. "
        "No reemplaza tasas activas existentes."
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            currencies = self._seed_currencies()
            self._seed_commissions()
            self._seed_limits(currencies)
            self._seed_initial_rates(currencies)
        self.stdout.write(self.style.SUCCESS("Catálogos operativos verificados correctamente."))

    def _seed_currencies(self):
        data = [
            ("PYG", "Guaraní Paraguayo", "₲", 0),
            ("USD", "Dólar Estadounidense", "$", 2),
            ("EUR", "Euro", "€", 2),
            ("BRL", "Real Brasileño", "R$", 2),
            ("ARS", "Peso Argentino", "$", 2),
            ("GBP", "Libra Esterlina", "£", 2),
        ]
        result = {}
        for code, name, symbol, decimals in data:
            currency, _ = Currency.objects.get_or_create(
                code=code,
                defaults={"name": name, "symbol": symbol, "decimals": decimals, "is_active": True},
            )
            result[code] = currency
        return result

    def _seed_commissions(self):
        data = [
            (Cliente.Segmentacion.MINORISTA, "1.50", "5000.00", "0.00"),
            (Cliente.Segmentacion.MAYORISTA, "0.80", "2000.00", "15.00"),
            (Cliente.Segmentacion.CORPORATIVO, "0.40", "0.00", "30.00"),
            (Cliente.Segmentacion.VIP, "0.20", "0.00", "50.00"),
        ]
        for segment, percentage, fixed_fee, discount in data:
            SegmentCommission.objects.get_or_create(
                segment=segment,
                defaults={
                    "commission_percentage": Decimal(percentage),
                    "fixed_fee": Decimal(fixed_fee),
                    "spread_discount_percentage": Decimal(discount),
                    "is_active": True,
                },
            )

    def _seed_limits(self, currencies):
        data = [
            (Cliente.Segmentacion.MINORISTA, "USD", "10", "5000", "10000", "30000"),
            (Cliente.Segmentacion.MINORISTA, "PYG", "50000", "35000000", "70000000", "200000000"),
            (Cliente.Segmentacion.MAYORISTA, "USD", "100", "50000", "100000", "500000"),
            (Cliente.Segmentacion.MAYORISTA, "PYG", "500000", "350000000", "700000000", "3000000000"),
            (Cliente.Segmentacion.CORPORATIVO, "USD", "500", "200000", "500000", "2000000"),
            (Cliente.Segmentacion.CORPORATIVO, "PYG", "3000000", "1500000000", "3500000000", "10000000000"),
            (Cliente.Segmentacion.VIP, "USD", "50", "100000", "200000", "1000000"),
            (Cliente.Segmentacion.VIP, "PYG", "300000", "700000000", "1400000000", "5000000000"),
        ]
        for segment, code, minimum, maximum, daily, monthly in data:
            OperationLimit.objects.get_or_create(
                segment=segment,
                currency=currencies[code],
                defaults={
                    "monto_minimo": Decimal(minimum), "monto_maximo": Decimal(maximum),
                    "limite_diario": Decimal(daily), "limite_mensual": Decimal(monthly),
                    "is_active": True,
                },
            )

    def _seed_initial_rates(self, currencies):
        data = [
            ("USD", "PYG", "7850", "7920"), ("EUR", "PYG", "8450", "8600"),
            ("BRL", "PYG", "1380", "1440"), ("ARS", "PYG", "6.5", "7.5"),
            ("GBP", "PYG", "9900", "10150"), ("EUR", "USD", "1.075", "1.090"),
        ]
        for base, target, buy, sell in data:
            if not ExchangeRate.objects.filter(
                base_currency=currencies[base], target_currency=currencies[target], is_active=True,
            ).exists():
                ExchangeRate.objects.create(
                    base_currency=currencies[base], target_currency=currencies[target],
                    buy_rate=Decimal(buy), sell_rate=Decimal(sell), valid_from=timezone.now(), is_active=True,
                )
