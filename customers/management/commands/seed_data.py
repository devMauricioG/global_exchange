"""
Comando de gestión de Django para poblar la base de datos con fixtures completos
e idempotentes para pruebas del sistema (SCRUM-75 / SCRUM-62).

Puebla:
1. Roles y usuarios de prueba (Admin, Operador, Clientes por segmento).
2. Clientes segmentados y asignaciones de representación multi-usuario.
3. Catálogo de divisas (USD, PYG, EUR, BRL, ARS, GBP).
4. Cotizaciones vigentes e historial de 30 días con fluctuaciones realistas.
5. Políticas y reglas de comisiones diferenciadas por segmento.
6. Catálogo de entidades bancarias y billeteras digitales.
7. Medios de pago y cuentas de acreditación asociadas.
8. Límites operativos por segmento y moneda.
9. Transacciones de prueba en estados Pendiente, Completada y Cancelada.
"""

from datetime import timedelta
from decimal import Decimal
import random

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from customers.models import Cliente, CustomerUserAssignment
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate, OperationLimit, SegmentCommission
from transactions.models import Transaction

User = get_user_model()


class Command(BaseCommand):
    """
    Comando para inicializar la base de datos con un conjunto exhaustivo de datos de prueba.
    """

    help = "Puebla la base de datos con fixtures completos e idempotentes para pruebas del sistema (SCRUM-75/SCRUM-62)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina previamente las transacciones, medios de pago y clientes de prueba antes de sembrar.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Iniciando Seeding de Datos para Global Exchange ==="))

        with transaction.atomic():
            if options.get("reset"):
                self._reset_data()

            users_map = self._seed_roles_and_users()
            customers_map = self._seed_customers(users_map)
            currencies_map = self._seed_currencies()
            self._seed_exchange_rates(currencies_map, users_map["admin"])
            self._seed_segment_commissions()
            financial_entities_map = self._seed_financial_entities()
            pm_rm_map = self._seed_payment_and_receiving_methods(customers_map, financial_entities_map)
            self._seed_operation_limits(currencies_map)
            self._seed_transactions(customers_map, currencies_map, pm_rm_map, users_map)

        self.stdout.write(
            self.style.SUCCESS("=== Seeding de datos completado exitosamente de forma idempotente ===")
        )

    def _reset_data(self):
        """Limpia los datos transaccionales y de prueba para reinicio limpio."""
        self.stdout.write("Limpiando datos transaccionales existentes...")
        Transaction.objects.all().delete()
        ReceivingMethod.objects.all().delete()
        PaymentMethod.objects.all().delete()
        CustomerUserAssignment.objects.all().delete()
        self.stdout.write(self.style.WARNING("Datos previos eliminados para reinicio."))

    def _seed_roles_and_users(self):
        """Crea o actualiza los grupos y usuarios estándar del sistema."""
        self.stdout.write("1. Sembrando roles y usuarios...")

        # 1. Grupos
        admin_group, _ = Group.objects.get_or_create(name="admin")
        operator_group, _ = Group.objects.get_or_create(name="operator")
        user_group, _ = Group.objects.get_or_create(name="user")

        users_data = [
            {
                "key": "admin",
                "username": "admin",
                "email": "admin@globalexchange.com.py",
                "first_name": "Administrador",
                "last_name": "Sistema",
                "is_staff": True,
                "is_superuser": True,
                "groups": [admin_group, operator_group],
            },
            {
                "key": "operador",
                "username": "operador",
                "email": "operador@globalexchange.com.py",
                "first_name": "Marcos",
                "last_name": "Cajero",
                "is_staff": True,
                "is_superuser": False,
                "groups": [operator_group],
            },
            {
                "key": "cliente_minorista",
                "username": "cliente_minorista",
                "email": "juan.perez@gmail.com",
                "first_name": "Juan",
                "last_name": "Pérez Gómez",
                "is_staff": False,
                "is_superuser": False,
                "groups": [user_group],
            },
            {
                "key": "cliente_vip",
                "username": "cliente_vip",
                "email": "victoria.vip@inversiones.com.py",
                "first_name": "Victoria",
                "last_name": "Silveira",
                "is_staff": False,
                "is_superuser": False,
                "groups": [user_group],
            },
            {
                "key": "cliente_corporativo",
                "username": "cliente_corporativo",
                "email": "finanzas@agroexport.com.py",
                "first_name": "Roberto",
                "last_name": "Agroexport",
                "is_staff": False,
                "is_superuser": False,
                "groups": [user_group],
            },
            {
                "key": "cliente_mayorista",
                "username": "cliente_mayorista",
                "email": "carlos.mayorista@distribuidora.com.py",
                "first_name": "Carlos",
                "last_name": "Benítez",
                "is_staff": False,
                "is_superuser": False,
                "groups": [user_group],
            },
        ]

        users_map = {}
        for u_data in users_data:
            user, created = User.objects.get_or_create(
                username=u_data["username"],
                defaults={
                    "email": u_data["email"],
                    "first_name": u_data["first_name"],
                    "last_name": u_data["last_name"],
                    "is_staff": u_data["is_staff"],
                    "is_superuser": u_data["is_superuser"],
                },
            )
            if not created:
                user.email = u_data["email"]
                user.first_name = u_data["first_name"]
                user.last_name = u_data["last_name"]
                user.is_staff = u_data["is_staff"]
                user.is_superuser = u_data["is_superuser"]

            user.set_password("Password123!")
            user.save()
            user.groups.set(u_data["groups"])
            users_map[u_data["key"]] = user

        self.stdout.write(f"   [OK] {len(users_map)} usuarios configurados (password: Password123!).")
        return users_map

    def _seed_customers(self, users_map):
        """Crea clientes segmentados y vincula asignaciones de representación."""
        self.stdout.write("2. Sembrando clientes y representaciones...")

        customers_data = [
            {
                "key": "minorista",
                "nombre": "Juan Pérez Gómez",
                "documento_ruc": "4567890-1",
                "correo": "juan.perez@gmail.com",
                "telefono": "0981123456",
                "segmentacion": Cliente.Segmentacion.MINORISTA,
                "user_key": "cliente_minorista",
                "keycloak_sub": "kc-sub-user-minorista-001",
            },
            {
                "key": "vip",
                "nombre": "Victoria Silveira Inversiones",
                "documento_ruc": "80012345-6",
                "correo": "victoria.vip@inversiones.com.py",
                "telefono": "0971987654",
                "segmentacion": Cliente.Segmentacion.VIP,
                "user_key": "cliente_vip",
                "keycloak_sub": "kc-sub-user-vip-002",
            },
            {
                "key": "corporativo",
                "nombre": "Agroexportadora del Este S.A.",
                "documento_ruc": "80098765-4",
                "correo": "finanzas@agroexport.com.py",
                "telefono": "021654321",
                "segmentacion": Cliente.Segmentacion.CORPORATIVO,
                "user_key": "cliente_corporativo",
                "keycloak_sub": "kc-sub-user-corp-003",
            },
            {
                "key": "mayorista",
                "nombre": "Distribuidora Mayorista Guaraní S.R.L.",
                "documento_ruc": "80055443-2",
                "correo": "carlos.mayorista@distribuidora.com.py",
                "telefono": "0982555666",
                "segmentacion": Cliente.Segmentacion.MAYORISTA,
                "user_key": "cliente_mayorista",
                "keycloak_sub": "kc-sub-user-mayo-004",
            },
        ]

        customers_map = {}
        for c_data in customers_data:
            cliente, _ = Cliente.objects.update_or_create(
                documento_ruc=c_data["documento_ruc"],
                defaults={
                    "nombre": c_data["nombre"],
                    "correo": c_data["correo"],
                    "telefono": c_data["telefono"],
                    "segmentacion": c_data["segmentacion"],
                    "keycloak_id": c_data["keycloak_sub"],
                    "is_active": True,
                },
            )

            # Asignación multi-representación
            assigned_user = users_map[c_data["user_key"]]
            CustomerUserAssignment.objects.update_or_create(
                customer=cliente,
                user=assigned_user,
                defaults={
                    "is_primary_representative": True,
                    "is_active": True,
                },
            )
            customers_map[c_data["key"]] = cliente

        self.stdout.write(f"   [OK] {len(customers_map)} clientes segmentados vinculados.")
        return customers_map

    def _seed_currencies(self):
        """Crea el catálogo oficial de monedas ISO 4217."""
        self.stdout.write("3. Sembrando catálogo de divisas...")

        currencies_data = [
            {"code": "PYG", "name": "Guaraní Paraguayo", "symbol": "₲", "decimals": 0},
            {"code": "USD", "name": "Dólar Estadounidense", "symbol": "$", "decimals": 2},
            {"code": "EUR", "name": "Euro", "symbol": "€", "decimals": 2},
            {"code": "BRL", "name": "Real Brasileño", "symbol": "R$", "decimals": 2},
            {"code": "ARS", "name": "Peso Argentino", "symbol": "$", "decimals": 2},
            {"code": "GBP", "name": "Libra Esterlina", "symbol": "£", "decimals": 2},
        ]

        currencies_map = {}
        for c in currencies_data:
            currency, _ = Currency.objects.update_or_create(
                code=c["code"],
                defaults={
                    "name": c["name"],
                    "symbol": c["symbol"],
                    "decimals": c["decimals"],
                    "is_active": True,
                },
            )
            currencies_map[c["code"]] = currency

        self.stdout.write(f"   [OK] {len(currencies_map)} divisas registradas.")
        return currencies_map

    def _seed_exchange_rates(self, currencies_map, admin_user):
        """Crea las tasas de cambio activas e histórico de 30 días."""
        self.stdout.write("4. Sembrando cotizaciones activas e históricas (30 días)...")

        pyg = currencies_map["PYG"]
        usd = currencies_map["USD"]
        eur = currencies_map["EUR"]
        brl = currencies_map["BRL"]
        ars = currencies_map["ARS"]
        gbp = currencies_map["GBP"]

        active_pairs = [
            {"base": usd, "target": pyg, "buy": Decimal("7850.000000"), "sell": Decimal("7920.000000")},
            {"base": eur, "target": pyg, "buy": Decimal("8450.000000"), "sell": Decimal("8600.000000")},
            {"base": brl, "target": pyg, "buy": Decimal("1380.000000"), "sell": Decimal("1440.000000")},
            {"base": ars, "target": pyg, "buy": Decimal("6.500000"), "sell": Decimal("7.500000")},
            {"base": gbp, "target": pyg, "buy": Decimal("9900.000000"), "sell": Decimal("10150.000000")},
            {"base": eur, "target": usd, "buy": Decimal("1.075000"), "sell": Decimal("1.090000")},
        ]

        now = timezone.now()

        # Desactivar tasas previas para asegurar que las nuevas sean las únicas activas
        ExchangeRate.objects.filter(is_active=True).update(is_active=False)

        for pair in active_pairs:
            ExchangeRate.objects.create(
                base_currency=pair["base"],
                target_currency=pair["target"],
                buy_rate=pair["buy"],
                sell_rate=pair["sell"],
                valid_from=now - timedelta(hours=1),
                valid_to=None,
                is_active=True,
                updated_by=admin_user,
            )

        # Histórico de 30 días para gráficos e inteligencia financiera
        random.seed(42)  # Semilla fija para reproducibilidad
        for days_ago in range(1, 31):
            rate_date = now - timedelta(days=days_ago)

            # Fluctuaciones ligeras simuladas
            usd_factor = Decimal(str(round(1 + (random.uniform(-0.015, 0.015)), 4)))
            eur_factor = Decimal(str(round(1 + (random.uniform(-0.02, 0.02)), 4)))
            brl_factor = Decimal(str(round(1 + (random.uniform(-0.03, 0.03)), 4)))

            historical_pairs = [
                (usd, pyg, Decimal("7850.000000") * usd_factor, Decimal("7920.000000") * usd_factor),
                (eur, pyg, Decimal("8450.000000") * eur_factor, Decimal("8600.000000") * eur_factor),
                (brl, pyg, Decimal("1380.000000") * brl_factor, Decimal("1440.000000") * brl_factor),
            ]

            for base_c, target_c, b_rate, s_rate in historical_pairs:
                b_round = round(b_rate, 4)
                s_round = max(b_round + Decimal("10.0000"), round(s_rate, 4))

                ExchangeRate.objects.create(
                    base_currency=base_c,
                    target_currency=target_c,
                    buy_rate=b_round,
                    sell_rate=s_round,
                    valid_from=rate_date.replace(hour=8, minute=0, second=0),
                    valid_to=rate_date.replace(hour=20, minute=0, second=0),
                    is_active=False,
                    updated_by=admin_user,
                )

        self.stdout.write(f"   [OK] 6 tasas activas y 90 cotizaciones historicas generadas.")

    def _seed_segment_commissions(self):
        """Crea políticas y comisiones por segmento comercial."""
        self.stdout.write("5. Sembrando comisiones por segmento...")

        commissions_data = [
            {
                "segment": Cliente.Segmentacion.MINORISTA,
                "commission_percentage": Decimal("1.50"),
                "fixed_fee": Decimal("5000.00"),
                "spread_discount_percentage": Decimal("0.00"),
            },
            {
                "segment": Cliente.Segmentacion.MAYORISTA,
                "commission_percentage": Decimal("0.80"),
                "fixed_fee": Decimal("2000.00"),
                "spread_discount_percentage": Decimal("15.00"),
            },
            {
                "segment": Cliente.Segmentacion.CORPORATIVO,
                "commission_percentage": Decimal("0.40"),
                "fixed_fee": Decimal("0.00"),
                "spread_discount_percentage": Decimal("30.00"),
            },
            {
                "segment": Cliente.Segmentacion.VIP,
                "commission_percentage": Decimal("0.20"),
                "fixed_fee": Decimal("0.00"),
                "spread_discount_percentage": Decimal("50.00"),
            },
        ]

        for com in commissions_data:
            SegmentCommission.objects.update_or_create(
                segment=com["segment"],
                defaults={
                    "commission_percentage": com["commission_percentage"],
                    "fixed_fee": com["fixed_fee"],
                    "spread_discount_percentage": com["spread_discount_percentage"],
                    "is_active": True,
                },
            )

        self.stdout.write("   [OK] 4 politicas de comision por segmento configuradas.")

    def _seed_financial_entities(self):
        """Crea entidades financieras (bancos y billeteras)."""
        self.stdout.write("6. Sembrando entidades financieras...")

        bancos = [
            ("Banco Itaú", 1),
            ("Banco Continental", 2),
            ("BNF", 3),
            ("Banco GNB", 4),
            ("Banco Basa", 5),
            ("Banco Sudameris", 6),
            ("Banco Ueno", 7),
            ("Banco Atlas", 8),
            ("Banco Familiar", 9),
        ]
        billeteras = [
            ("Tigo Money", 1),
            ("Personal", 2),
            ("Wally", 3),
            ("Zimple", 4),
        ]

        entities_map = {}
        for nombre, orden in bancos:
            ent, _ = EntidadFinanciera.objects.update_or_create(
                nombre=nombre,
                defaults={"tipo": EntidadFinanciera.TipoEntidad.BANCO, "activo": True, "orden": orden},
            )
            entities_map[nombre] = ent

        for nombre, orden in billeteras:
            ent, _ = EntidadFinanciera.objects.update_or_create(
                nombre=nombre,
                defaults={"tipo": EntidadFinanciera.TipoEntidad.BILLETERA, "activo": True, "orden": orden},
            )
            entities_map[nombre] = ent

        self.stdout.write(f"   [OK] {len(entities_map)} entidades financieras disponibles.")
        return entities_map

    def _seed_payment_and_receiving_methods(self, customers_map, financial_entities_map):
        """Crea instrumentos de pago y cuentas de recepción para cada cliente."""
        self.stdout.write("7. Sembrando medios de pago y acreditación...")

        itau = financial_entities_map["Banco Itaú"]
        continental = financial_entities_map["Banco Continental"]
        tigo = financial_entities_map["Tigo Money"]
        personal = financial_entities_map["Personal"]

        pm_rm_map = {}

        for key, cliente in customers_map.items():
            # 1. Medio de pago: Transferencia Bancaria
            pm_bank, _ = PaymentMethod.objects.update_or_create(
                cliente=cliente,
                tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
                numero_cuenta=f"100-{cliente.documento_ruc.replace('-', '')}",
                defaults={
                    "entidad_bancaria": itau if key in ["minorista", "vip"] else continental,
                    "titular": cliente.nombre,
                    "documento_titular": cliente.documento_ruc,
                    "tipo_cuenta_bancaria": PaymentMethod.TipoCuentaBancaria.CORRIENTE
                    if key in ["corporativo", "mayorista"]
                    else PaymentMethod.TipoCuentaBancaria.AHORRO,
                    "es_predeterminado": True,
                    "activo": True,
                },
            )

            # 2. Medio de pago: Billetera Digital
            pm_wallet, _ = PaymentMethod.objects.update_or_create(
                cliente=cliente,
                tipo_medio=PaymentMethod.TipoMedio.BILLETERA,
                numero_cuenta=cliente.telefono if cliente.telefono.startswith("09") else "0981111222",
                defaults={
                    "entidad_bancaria": tigo if key in ["minorista", "vip"] else personal,
                    "titular": cliente.nombre,
                    "documento_titular": cliente.documento_ruc,
                    "telefono_billetera": cliente.telefono if cliente.telefono.startswith("09") else "0981111222",
                    "es_predeterminado": False,
                    "activo": True,
                },
            )

            # 3. Medio de pago: Tarjeta Débito/Crédito
            pm_card, _ = PaymentMethod.objects.update_or_create(
                cliente=cliente,
                tipo_medio=PaymentMethod.TipoMedio.TARJETA,
                numero_cuenta=f"XXXX-XXXX-XXXX-{cliente.id:04d}",
                defaults={
                    "entidad_bancaria": itau,
                    "titular": cliente.nombre,
                    "documento_titular": cliente.documento_ruc,
                    "tarjeta_ultimos_digitos": f"{cliente.id:04d}"[-4:],
                    "tarjeta_mes_vencimiento": 12,
                    "tarjeta_anio_vencimiento": 2028,
                    "es_predeterminado": False,
                    "activo": True,
                },
            )

            # 4. Medio de Acreditación: Caja de Ahorro / Corriente
            rm_bank, _ = ReceivingMethod.objects.update_or_create(
                cliente=cliente,
                numero_cuenta=f"999-{cliente.documento_ruc.replace('-', '')}",
                defaults={
                    "entidad_bancaria": itau if key in ["minorista", "vip"] else continental,
                    "tipo_cuenta": ReceivingMethod.TipoCuenta.CORRIENTE
                    if key in ["corporativo", "mayorista"]
                    else ReceivingMethod.TipoCuenta.AHORRO,
                    "titular": cliente.nombre,
                    "documento_titular": cliente.documento_ruc,
                    "es_predeterminado": True,
                    "activo": True,
                },
            )

            # 5. Medio de Acreditación: Billetera
            rm_wallet, _ = ReceivingMethod.objects.update_or_create(
                cliente=cliente,
                numero_cuenta=cliente.telefono if cliente.telefono.startswith("09") else "0981111222",
                defaults={
                    "entidad_bancaria": tigo if key in ["minorista", "vip"] else personal,
                    "tipo_cuenta": ReceivingMethod.TipoCuenta.BILLETERA,
                    "titular": cliente.nombre,
                    "documento_titular": cliente.documento_ruc,
                    "es_predeterminado": False,
                    "activo": True,
                },
            )

            pm_rm_map[key] = {
                "pm_bank": pm_bank,
                "pm_wallet": pm_wallet,
                "pm_card": pm_card,
                "rm_bank": rm_bank,
                "rm_wallet": rm_wallet,
            }

        self.stdout.write(f"   [OK] Medios de pago y acreditacion asignados a los {len(customers_map)} clientes.")
        return pm_rm_map

    def _seed_operation_limits(self, currencies_map):
        """Crea los límites operativos por segmento y divisa."""
        self.stdout.write("8. Sembrando límites operativos...")

        pyg = currencies_map["PYG"]
        usd = currencies_map["USD"]
        eur = currencies_map["EUR"]
        brl = currencies_map["BRL"]

        limits_data = [
            # MINORISTA
            {
                "segment": Cliente.Segmentacion.MINORISTA,
                "currency": usd,
                "min": Decimal("10.00"),
                "max": Decimal("5000.00"),
                "daily": Decimal("10000.00"),
                "monthly": Decimal("30000.00"),
            },
            {
                "segment": Cliente.Segmentacion.MINORISTA,
                "currency": pyg,
                "min": Decimal("50000.00"),
                "max": Decimal("35000000.00"),
                "daily": Decimal("70000000.00"),
                "monthly": Decimal("200000000.00"),
            },
            {
                "segment": Cliente.Segmentacion.MINORISTA,
                "currency": eur,
                "min": Decimal("10.00"),
                "max": Decimal("4000.00"),
                "daily": Decimal("8000.00"),
                "monthly": Decimal("25000.00"),
            },
            {
                "segment": Cliente.Segmentacion.MINORISTA,
                "currency": brl,
                "min": Decimal("50.00"),
                "max": Decimal("25000.00"),
                "daily": Decimal("50000.00"),
                "monthly": Decimal("150000.00"),
            },
            # MAYORISTA
            {
                "segment": Cliente.Segmentacion.MAYORISTA,
                "currency": usd,
                "min": Decimal("100.00"),
                "max": Decimal("50000.00"),
                "daily": Decimal("100000.00"),
                "monthly": Decimal("500000.00"),
            },
            {
                "segment": Cliente.Segmentacion.MAYORISTA,
                "currency": pyg,
                "min": Decimal("500000.00"),
                "max": Decimal("350000000.00"),
                "daily": Decimal("700000000.00"),
                "monthly": Decimal("3000000000.00"),
            },
            # CORPORATIVO
            {
                "segment": Cliente.Segmentacion.CORPORATIVO,
                "currency": usd,
                "min": Decimal("500.00"),
                "max": Decimal("200000.00"),
                "daily": Decimal("500000.00"),
                "monthly": Decimal("2000000.00"),
            },
            {
                "segment": Cliente.Segmentacion.CORPORATIVO,
                "currency": pyg,
                "min": Decimal("3000000.00"),
                "max": Decimal("1500000000.00"),
                "daily": Decimal("3500000000.00"),
                "monthly": Decimal("10000000000.00"),
            },
            # VIP
            {
                "segment": Cliente.Segmentacion.VIP,
                "currency": usd,
                "min": Decimal("50.00"),
                "max": Decimal("100000.00"),
                "daily": Decimal("200000.00"),
                "monthly": Decimal("1000000.00"),
            },
            {
                "segment": Cliente.Segmentacion.VIP,
                "currency": pyg,
                "min": Decimal("300000.00"),
                "max": Decimal("700000000.00"),
                "daily": Decimal("1400000000.00"),
                "monthly": Decimal("5000000000.00"),
            },
        ]

        for lim in limits_data:
            OperationLimit.objects.update_or_create(
                segment=lim["segment"],
                currency=lim["currency"],
                defaults={
                    "monto_minimo": lim["min"],
                    "monto_maximo": lim["max"],
                    "limite_diario": lim["daily"],
                    "limite_mensual": lim["monthly"],
                    "is_active": True,
                },
            )

        self.stdout.write(f"   [OK] {len(limits_data)} reglas de limites operativos parametrizadas.")

    def _seed_transactions(self, customers_map, currencies_map, pm_rm_map, users_map):
        """Crea transacciones de prueba representativas en diferentes estados."""
        self.stdout.write("9. Sembrando transacciones de compra/venta de ejemplo...")

        usd = currencies_map["USD"]
        pyg = currencies_map["PYG"]
        eur = currencies_map["EUR"]
        brl = currencies_map["BRL"]

        c_min = customers_map["minorista"]
        c_vip = customers_map["vip"]
        c_corp = customers_map["corporativo"]
        c_may = customers_map["mayorista"]

        active_usd_pyg = ExchangeRate.objects.filter(base_currency=usd, target_currency=pyg, is_active=True).first()
        active_eur_pyg = ExchangeRate.objects.filter(base_currency=eur, target_currency=pyg, is_active=True).first()
        active_brl_pyg = ExchangeRate.objects.filter(base_currency=brl, target_currency=pyg, is_active=True).first()

        transactions_data = [
            # 1. Compra de USD por Minorista (COMPLETADA)
            {
                "ref": "TX-SEED-00001",
                "cliente": c_min,
                "tipo_operacion": Transaction.TipoOperacion.COMPRA,
                "base_currency": usd,
                "target_currency": pyg,
                "exchange_rate": active_usd_pyg,
                "tasa_base": Decimal("7920.000000"),
                "comision_segmento": Decimal("123800.00"),
                "tasa_neta": Decimal("8043.800000"),
                "monto_origen": Decimal("8043800.00"),
                "monto_destino": Decimal("1000.00"),
                "pm": pm_rm_map["minorista"]["pm_bank"],
                "rm": pm_rm_map["minorista"]["rm_bank"],
                "estado": Transaction.Estado.COMPLETADA,
                "usuario": users_map["operador"],
                "observaciones": "Operación completada exitosamente vía transferencia bancaria.",
            },
            # 2. Venta de USD por VIP (COMPLETADA)
            {
                "ref": "TX-SEED-00002",
                "cliente": c_vip,
                "tipo_operacion": Transaction.TipoOperacion.VENTA,
                "base_currency": usd,
                "target_currency": pyg,
                "exchange_rate": active_usd_pyg,
                "tasa_base": Decimal("7850.000000"),
                "comision_segmento": Decimal("78500.00"),
                "tasa_neta": Decimal("7834.300000"),
                "monto_origen": Decimal("5000.00"),
                "monto_destino": Decimal("39171500.00"),
                "pm": pm_rm_map["vip"]["pm_bank"],
                "rm": pm_rm_map["vip"]["rm_bank"],
                "estado": Transaction.Estado.COMPLETADA,
                "usuario": users_map["operador"],
                "observaciones": "Venta preferencial de divisas con descuento VIP sobre spread.",
            },
            # 3. Compra de EUR por Corporativo (COMPLETADA)
            {
                "ref": "TX-SEED-00003",
                "cliente": c_corp,
                "tipo_operacion": Transaction.TipoOperacion.COMPRA,
                "base_currency": eur,
                "target_currency": pyg,
                "exchange_rate": active_eur_pyg,
                "tasa_base": Decimal("8600.000000"),
                "comision_segmento": Decimal("344000.00"),
                "tasa_neta": Decimal("8634.400000"),
                "monto_origen": Decimal("86344000.00"),
                "monto_destino": Decimal("10000.00"),
                "pm": pm_rm_map["corporativo"]["pm_bank"],
                "rm": pm_rm_map["corporativo"]["rm_bank"],
                "estado": Transaction.Estado.COMPLETADA,
                "usuario": users_map["admin"],
                "observaciones": "Operación de tesorería y comercio exterior liquidada.",
            },
            # 4. Compra de USD por Minorista (PENDIENTE)
            {
                "ref": "TX-SEED-00004",
                "cliente": c_min,
                "tipo_operacion": Transaction.TipoOperacion.COMPRA,
                "base_currency": usd,
                "target_currency": pyg,
                "exchange_rate": active_usd_pyg,
                "tasa_base": Decimal("7920.000000"),
                "comision_segmento": Decimal("64400.00"),
                "tasa_neta": Decimal("8048.800000"),
                "monto_origen": Decimal("4024400.00"),
                "monto_destino": Decimal("500.00"),
                "pm": pm_rm_map["minorista"]["pm_wallet"],
                "rm": pm_rm_map["minorista"]["rm_wallet"],
                "estado": Transaction.Estado.PENDIENTE,
                "usuario": users_map["cliente_minorista"],
                "token_congelamiento": "QTZ-SEED-PENDING-001",
                "observaciones": "Orden creada pendiente de confirmación de pago por Tigo Money.",
            },
            # 5. Compra de BRL por Mayorista (CANCELADA por expiración)
            {
                "ref": "TX-SEED-00005",
                "cliente": c_may,
                "tipo_operacion": Transaction.TipoOperacion.COMPRA,
                "base_currency": brl,
                "target_currency": pyg,
                "exchange_rate": active_brl_pyg,
                "tasa_base": Decimal("1440.000000"),
                "comision_segmento": Decimal("11720.00"),
                "tasa_neta": Decimal("1451.720000"),
                "monto_origen": Decimal("1451720.00"),
                "monto_destino": Decimal("1000.00"),
                "pm": pm_rm_map["mayorista"]["pm_bank"],
                "rm": pm_rm_map["mayorista"]["rm_bank"],
                "estado": Transaction.Estado.CANCELADA,
                "usuario": users_map["cliente_mayorista"],
                "token_congelamiento": "QTZ-SEED-EXPIRED-002",
                "observaciones": "[Cancelación] Cotización congelada expirada tras superar el límite de 5 minutos sin confirmación.",
            },
        ]

        for tx_data in transactions_data:
            Transaction.objects.update_or_create(
                codigo_referencia=tx_data["ref"],
                defaults={
                    "cliente": tx_data["cliente"],
                    "tipo_operacion": tx_data["tipo_operacion"],
                    "base_currency": tx_data["base_currency"],
                    "target_currency": tx_data["target_currency"],
                    "exchange_rate": tx_data["exchange_rate"],
                    "tasa_base": tx_data["tasa_base"],
                    "comision_segmento": tx_data["comision_segmento"],
                    "tasa_neta": tx_data["tasa_neta"],
                    "monto_origen": tx_data["monto_origen"],
                    "monto_destino": tx_data["monto_destino"],
                    "medio_pago_origen": tx_data["pm"],
                    "medio_acreditacion_destino": tx_data["rm"],
                    "estado": tx_data["estado"],
                    "usuario": tx_data["usuario"],
                    "token_congelamiento": tx_data.get("token_congelamiento"),
                    "observaciones": tx_data["observaciones"],
                },
            )

        self.stdout.write(f"   [OK] {len(transactions_data)} transacciones de prueba sembradas.")
