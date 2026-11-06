"""
Servicio de Gestión de Efectivo en Terminal Kiosco (KioskCashService) - SCRUM-122.

Simula y controla:
1. Aceptación física de billetes con validador de denominaciones permitidas por divisa.
2. Dispensación física óptima de billetes según disponibilidad de saldo en casetes del tótem.
3. Generación de comprobantes de caja con sellos de trazabilidad criptográfica SHA-256 y código QR.
"""

from decimal import Decimal
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from django.db import transaction as db_transaction
from django.utils import timezone

from rates.models import Currency
from .models import KioskCashOperation, KioskCashVault, KioskTotem, Transaction

logger = logging.getLogger(__name__)

# Denominaciones de billetes de curso legal permitidas para aceptación y dispensación
DENOMINACIONES_PERMITIDAS: Dict[str, List[int]] = {
    'PYG': [100000, 50000, 20000, 10000, 5000, 2000],
    'USD': [100, 50, 20, 10, 5, 1],
    'EUR': [200, 100, 50, 20, 10, 5],
    'BRL': [200, 100, 50, 20, 10, 5, 2],
    'ARS': [10000, 2000, 1000, 500, 200, 100],
}


class KioskCashError(Exception):
    """Excepción base para fallas del subsistema de efectivo en terminales Kiosco."""
    pass


class InvalidBillDenominationError(KioskCashError):
    """Disparada cuando un billete ingresado no pertenece a la serie de denominaciones autorizadas."""
    pass


class InsufficientTotemBalanceError(KioskCashError):
    """Disparada cuando el tótem carece de saldo físico suficiente para dispensar el importe solicitado."""
    pass


class CannotDispenseExactChangeError(KioskCashError):
    """Disparada cuando existe saldo total pero las denominaciones disponibles no permiten armar el cambio exacto."""
    pass


class TotemCassetteCapacityExceededError(KioskCashError):
    """Disparada cuando el casete receptor supera su capacidad física máxima de almacenamiento."""
    pass


def generate_qr_svg(payload: str, size: int = 160) -> str:
    """
    Genera una representación gráfica de código QR / matriz bidimensional en SVG nativo puro,
    sin requerir librerías binarias externas (C/C++).
    """
    hash_int = int(hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16], 16)
    grid_size = 21  # Versión 1 QR (21x21 módulos)
    modules: List[List[bool]] = [[False] * grid_size for _ in range(grid_size)]

    # Patrones de búsqueda en las 3 esquinas (Finder Patterns 7x7)
    def add_finder(r_start: int, c_start: int) -> None:
        for r in range(7):
            for c in range(7):
                if r in (0, 6) or c in (0, 6):
                    modules[r_start + r][c_start + c] = True
                elif 2 <= r <= 4 and 2 <= c <= 4:
                    modules[r_start + r][c_start + c] = True

    add_finder(0, 0)
    add_finder(0, grid_size - 7)
    add_finder(grid_size - 7, 0)

    # Patrón de sincronización (Timing patterns)
    for i in range(8, grid_size - 8):
        modules[6][i] = (i % 2 == 0)
        modules[i][6] = (i % 2 == 0)

    # Llenado determinista pseudo-QR a partir del hash del payload
    bit_index = 0
    for r in range(grid_size):
        for c in range(grid_size):
            if (r < 8 and c < 8) or (r < 8 and c >= grid_size - 8) or (r >= grid_size - 8 and c < 8):
                continue
            if r == 6 or c == 6:
                continue
            bit = (hash_int >> (bit_index % 60)) & 1
            modules[r][c] = (bit == 1)
            bit_index += 1

    # Renderizar celdas SVG
    cell_size = size / grid_size
    svg_rects = []
    for r in range(grid_size):
        for c in range(grid_size):
            if modules[r][c]:
                x = c * cell_size
                y = r * cell_size
                svg_rects.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_size:.1f}" height="{cell_size:.1f}" fill="#0f172a" />')

    rects_str = "".join(svg_rects)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" style="background:#ffffff; border-radius:8px; padding:6px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">'
        f'{rects_str}'
        f'</svg>'
    )


class KioskCashService:
    """
    Servicio integral para la gestión y orquestación del efectivo físico en terminales Kiosco.
    """

    @classmethod
    def get_or_create_default_totem(cls, codigo: str = 'TOTEM-01') -> KioskTotem:
        """
        Obtiene o aprovisiona el hardware del tótem central con stock inicial en sus casetes.
        """
        totem, created = KioskTotem.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': 'Tótem Sucursal Central - Hall',
                'ubicacion': 'Av. Mariscal López 1234, Asunción',
                'estado': KioskTotem.Estado.ONLINE,
                'ip_address': '192.168.1.150',
                'activo': True,
            }
        )

        # Si el tótem no tiene casetes inicializados, aprovisionar stock de billetes estándar
        if totem.vaults.count() == 0:
            cls._seed_totem_vaults(totem)

        return totem

    @classmethod
    def _seed_totem_vaults(cls, totem: KioskTotem) -> None:
        """Aprovisiona casetes con stock físico estándar para PYG, USD y EUR."""
        pyg = Currency.objects.filter(code='PYG').first()
        usd = Currency.objects.filter(code='USD').first()
        eur = Currency.objects.filter(code='EUR').first()

        stocks = {
            'PYG': {100000: 250, 50000: 200, 20000: 300, 10000: 500, 5000: 500, 2000: 500},
            'USD': {100: 100, 50: 50, 20: 100, 10: 100, 5: 100, 1: 100},
            'EUR': {100: 50, 50: 50, 20: 100, 10: 100, 5: 100},
        }

        curr_map = {'PYG': pyg, 'USD': usd, 'EUR': eur}
        for code, curr in curr_map.items():
            if not curr:
                continue
            for denom, qty in stocks.get(code, {}).items():
                KioskCashVault.objects.get_or_create(
                    totem=totem,
                    currency=curr,
                    denominacion=Decimal(str(denom)),
                    defaults={'cantidad': qty, 'capacidad_maxima': 2000}
                )

    @classmethod
    def validate_bills(
        cls,
        currency_code: str,
        bills: Union[List[Union[int, Decimal]], Dict[Union[int, str, Decimal], int]]
    ) -> Tuple[Decimal, Dict[int, int]]:
        """
        Valida que cada billete ingresado corresponda a una denominación permitida.

        :param currency_code: Código ISO de la moneda (PYG, USD, EUR, etc.).
        :param bills: Lista de valores de billetes [100000, 50000] o diccionario {100000: 2, 50000: 1}.
        :return: Tupla (monto_total, desglose_normalizado_dict).
        :raises InvalidBillDenominationError: Si un billete no es válido.
        """
        code = currency_code.upper()
        allowed = DENOMINACIONES_PERMITIDAS.get(code)
        if not allowed:
            raise InvalidBillDenominationError(f"Moneda no habilitada para operaciones en efectivo en tótem: {code}")

        breakdown: Dict[int, int] = {}

        if isinstance(bills, list):
            for item in bills:
                try:
                    val = int(Decimal(str(item)))
                except (ValueError, TypeError):
                    raise InvalidBillDenominationError(f"Valor de billete corrupto o ilegible: {item}")

                if val not in allowed:
                    raise InvalidBillDenominationError(
                        f"Denominación de billete {val} no permitida para {code}. Permitidas: {allowed}"
                    )
                breakdown[val] = breakdown.get(val, 0) + 1

        elif isinstance(bills, dict):
            for k, qty in bills.items():
                try:
                    val = int(Decimal(str(k)))
                    count = int(qty)
                except (ValueError, TypeError):
                    raise InvalidBillDenominationError(f"Entrada inválida en billete o cantidad: {k}={qty}")

                if count <= 0:
                    continue

                if val not in allowed:
                    raise InvalidBillDenominationError(
                        f"Denominación de billete {val} no permitida para {code}. Permitidas: {allowed}"
                    )
                breakdown[val] = breakdown.get(val, 0) + count

        else:
            raise InvalidBillDenominationError("El formato de billetes debe ser una lista o un diccionario.")

        if not breakdown:
            raise InvalidBillDenominationError("No se ingresaron billetes válidos para la operación.")

        total_amount = sum(Decimal(str(denom)) * Decimal(str(count)) for denom, count in breakdown.items())
        return total_amount, breakdown

    @classmethod
    def accept_cash(
        cls,
        totem: KioskTotem,
        currency: Currency,
        bills: Union[List[Union[int, Decimal]], Dict[Union[int, str, Decimal], int]],
        transaction: Optional[Transaction] = None,
    ) -> KioskCashOperation:
        """
        Simula la aceptación física de billetes por el lector/validador del tótem.

        - Valida denominaciones legales.
        - Incrementa las existencias en los casetes receptores correspondientes.
        - Genera hash criptográfico SHA-256 de trazabilidad y cadena QR.
        - Registra la operación de tipo ACEPTACION.
        """
        total_amount, breakdown = cls.validate_bills(currency.code, bills)

        with db_transaction.atomic():
            for denom_val, count in breakdown.items():
                vault, _ = KioskCashVault.objects.select_for_update().get_or_create(
                    totem=totem,
                    currency=currency,
                    denominacion=Decimal(str(denom_val)),
                    defaults={'cantidad': 0, 'capacidad_maxima': 2000}
                )
                if vault.cantidad + count > vault.capacidad_maxima:
                    raise TotemCassetteCapacityExceededError(
                        f"Casete {currency.code} {denom_val} superaría su capacidad máxima de {vault.capacidad_maxima} piezas."
                    )
                vault.cantidad += count
                vault.save(update_fields=['cantidad', 'updated_at'])

            # Generar comprobante y hashes
            op_uuid = uuid.uuid4()
            now_iso = timezone.now().isoformat()
            hash_payload = f"{totem.codigo}:{currency.code}:{total_amount}:{json.dumps(breakdown, sort_keys=True)}:{now_iso}"
            sha_hash = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()

            qr_content = (
                f"https://globalexchange.com.py/kiosk/verify/{op_uuid}"
                f"?op=accept&totem={totem.codigo}&monto={total_amount}&curr={currency.code}&hash={sha_hash[:16]}"
            )

            total_bills = sum(breakdown.values())
            cash_op = KioskCashOperation.objects.create(
                totem=totem,
                transaction=transaction,
                uuid=op_uuid,
                tipo_operacion=KioskCashOperation.TipoOperacion.ACEPTACION,
                currency=currency,
                monto_total=total_amount,
                desglose_billetes=breakdown,
                total_billetes=total_bills,
                codigo_qr=qr_content,
                hash_verificacion=sha_hash,
            )

        logger.info(
            "Efectivo aceptado en tótem %s: %s %s (%d billetes) - UUID: %s",
            totem.codigo, currency.code, total_amount, total_bills, op_uuid
        )
        return cash_op

    @classmethod
    def calculate_dispense_breakdown(
        cls,
        totem: KioskTotem,
        currency: Currency,
        target_amount: Decimal,
    ) -> Dict[int, int]:
        """
        Calcula el desglose óptimo de billetes a dispensar minimizando la cantidad de piezas físicas
        en base al inventario disponible en los casetes del tótem (Algoritmo Bounded Coin Change).

        :param totem: Tótem despachador.
        :param currency: Moneda a dispensar.
        :param target_amount: Monto exacto a entregar.
        :return: Diccionario {denominacion: cantidad_a_dispensar}.
        :raises InsufficientTotemBalanceError: Si el saldo total físico es menor al solicitado.
        :raises CannotDispenseExactChangeError: Si no se puede componer el cambio exacto con los billetes disponibles.
        """
        if target_amount <= Decimal('0'):
            raise KioskCashError("El monto a dispensar debe ser estrictamente positivo.")

        # Obtener casetes con existencias > 0
        vaults = KioskCashVault.objects.filter(
            totem=totem,
            currency=currency,
            cantidad__gt=0
        ).order_by('-denominacion')

        total_disponible = sum(v.saldo for v in vaults)
        if total_disponible < target_amount:
            raise InsufficientTotemBalanceError(
                f"Saldo insuficiente en la caja del tótem {totem.codigo}. "
                f"Disponible: {currency.code} {total_disponible:,.2f}, Solicitado: {currency.code} {target_amount:,.2f}."
            )

        # Preparar stock disponible en enteros
        vault_stock: Dict[int, int] = {
            int(v.denominacion): v.cantidad for v in vaults
        }

        # Desglose codicioso (Greedy) con búsqueda de cambio exacto
        int_target = int(target_amount)
        if Decimal(str(int_target)) != target_amount:
            raise CannotDispenseExactChangeError(
                f"El tótem solo puede dispensar valores enteros de billetes, no fracciones decimales: {target_amount}"
            )

        rem = int_target
        dispense_plan: Dict[int, int] = {}

        # Ordenar denominaciones descendentes
        for denom in sorted(vault_stock.keys(), reverse=True):
            available = vault_stock[denom]
            if available <= 0 or denom > rem:
                continue

            needed = rem // denom
            take = min(needed, available)
            if take > 0:
                dispense_plan[denom] = take
                rem -= take * denom

            if rem == 0:
                break

        if rem != 0:
            # Algoritmo de backtracking si el greedy voraz no encuentra combinación exacta
            dispense_plan = cls._backtrack_dispense(vault_stock, int_target)
            if not dispense_plan:
                raise CannotDispenseExactChangeError(
                    f"No es posible dispensar el monto exacto de {currency.code} {target_amount:,.0f} "
                    f"con las denominaciones físicas disponibles en el casete del tótem."
                )

        return dispense_plan

    @classmethod
    def _backtrack_dispense(cls, stock: Dict[int, int], target: int) -> Optional[Dict[int, int]]:
        """Algoritmo de búsqueda exhaustiva acotada para componer el monto exacto."""
        denoms = sorted(stock.keys(), reverse=True)

        def search(idx: int, current_rem: int, current_plan: Dict[int, int]) -> Optional[Dict[int, int]]:
            if current_rem == 0:
                return current_plan
            if idx >= len(denoms) or current_rem < 0:
                return None

            denom = denoms[idx]
            max_take = min(current_rem // denom, stock[denom])

            for take in range(max_take, -1, -1):
                new_plan = current_plan.copy()
                if take > 0:
                    new_plan[denom] = take
                res = search(idx + 1, current_rem - take * denom, new_plan)
                if res is not None:
                    return res
            return None

        return search(0, target, {})

    @classmethod
    def dispense_cash(
        cls,
        totem: KioskTotem,
        currency: Currency,
        target_amount: Decimal,
        transaction: Optional[Transaction] = None,
    ) -> KioskCashOperation:
        """
        Ejecuta la dispensación física de divisas en la terminal.

        - Bloquea los casetes bajo transacción atómica (select_for_update).
        - Verifica y descuenta el stock de billetes.
        - Genera comprobante con hash criptográfico y QR code.
        - Registra operación de tipo DISPENSACION.
        """
        with db_transaction.atomic():
            breakdown = cls.calculate_dispense_breakdown(totem, currency, target_amount)

            # Descontar del inventario físico
            for denom_val, count in breakdown.items():
                vault = KioskCashVault.objects.select_for_update().get(
                    totem=totem,
                    currency=currency,
                    denominacion=Decimal(str(denom_val)),
                )
                vault.cantidad -= count
                vault.save(update_fields=['cantidad', 'updated_at'])

            op_uuid = uuid.uuid4()
            now_iso = timezone.now().isoformat()
            hash_payload = f"{totem.codigo}:{currency.code}:{target_amount}:{json.dumps(breakdown, sort_keys=True)}:{now_iso}"
            sha_hash = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()

            qr_content = (
                f"https://globalexchange.com.py/kiosk/verify/{op_uuid}"
                f"?op=dispense&totem={totem.codigo}&monto={target_amount}&curr={currency.code}&hash={sha_hash[:16]}"
            )

            total_bills = sum(breakdown.values())
            cash_op = KioskCashOperation.objects.create(
                totem=totem,
                transaction=transaction,
                uuid=op_uuid,
                tipo_operacion=KioskCashOperation.TipoOperacion.DISPENSACION,
                currency=currency,
                monto_total=target_amount,
                desglose_billetes=breakdown,
                total_billetes=total_bills,
                codigo_qr=qr_content,
                hash_verificacion=sha_hash,
            )

        logger.info(
            "Efectivo dispensado en tótem %s: %s %s (%d billetes) - UUID: %s",
            totem.codigo, currency.code, target_amount, total_bills, op_uuid
        )
        return cash_op

    @classmethod
    def generate_cash_receipt(cls, operation: KioskCashOperation) -> Dict[str, Any]:
        """
        Genera el documento completo de comprobante de caja con formato QR e información de trazabilidad.
        """
        desglose_list = []
        for denom_str, count in sorted(operation.desglose_billetes.items(), key=lambda x: int(x[0]), reverse=True):
            denom_int = int(denom_str)
            subtotal = Decimal(str(denom_int)) * Decimal(str(count))
            desglose_list.append({
                'denominacion': denom_int,
                'cantidad': count,
                'subtotal': subtotal,
                'subtotal_formatted': f"{subtotal:,.2f}" if operation.currency.decimals > 0 else f"{subtotal:,.0f}",
            })

        qr_svg = generate_qr_svg(operation.codigo_qr)

        return {
            'uuid': str(operation.uuid),
            'tipo_operacion': operation.tipo_operacion,
            'tipo_operacion_display': operation.get_tipo_operacion_display(),
            'totem_codigo': operation.totem.codigo,
            'totem_nombre': operation.totem.nombre,
            'totem_ubicacion': operation.totem.ubicacion,
            'moneda_codigo': operation.currency.code,
            'moneda_simbolo': operation.currency.symbol,
            'monto_total': operation.monto_total,
            'monto_total_formatted': f"{operation.monto_total:,.2f}" if operation.currency.decimals > 0 else f"{operation.monto_total:,.0f}",
            'total_billetes': operation.total_billetes,
            'desglose': desglose_list,
            'fecha': operation.fecha_formateada,
            'hash_verificacion': operation.hash_verificacion,
            'codigo_qr': operation.codigo_qr,
            'qr_svg': qr_svg,
            'transaction_ref': operation.transaction.codigo_referencia if operation.transaction else None,
        }

    @classmethod
    def get_totem_inventory(cls, totem: KioskTotem) -> Dict[str, Any]:
        """
        Obtiene el informe consolidado del inventario de efectivo del tótem por moneda y denominación.
        """
        vaults = totem.vaults.select_related('currency').order_by('currency__code', '-denominacion')
        currencies_data: Dict[str, Any] = {}

        for v in vaults:
            code = v.currency.code
            if code not in currencies_data:
                currencies_data[code] = {
                    'currency_code': code,
                    'currency_name': v.currency.name,
                    'symbol': v.currency.symbol,
                    'total_balance': Decimal('0'),
                    'total_bills': 0,
                    'cassettes': [],
                }

            currencies_data[code]['total_balance'] += v.saldo
            currencies_data[code]['total_bills'] += v.cantidad
            currencies_data[code]['cassettes'].append({
                'denominacion': int(v.denominacion),
                'cantidad': v.cantidad,
                'capacidad_maxima': v.capacidad_maxima,
                'porcentaje_ocupacion': round((v.cantidad / v.capacidad_maxima) * 100, 1),
                'saldo': v.saldo,
            })

        return {
            'totem_codigo': totem.codigo,
            'totem_nombre': totem.nombre,
            'estado': totem.estado,
            'estado_display': totem.get_estado_display(),
            'activo': totem.activo,
            'currencies': list(currencies_data.values()),
        }

    @classmethod
    def decompose_amount_into_bills(
        cls,
        currency: Currency,
        amount: Decimal
    ) -> Dict[int, int]:
        """
        Descompone un importe en la combinación óptima de billetes legales para la divisa indicada
        según las denominaciones de curso legal activas.
        """
        code = currency.code.upper()
        allowed = sorted(DENOMINACIONES_PERMITIDAS.get(code, []), reverse=True)
        if not allowed:
            from apps.cash.inventory_models import CurrencyDenomination
            db_denoms = CurrencyDenomination.objects.filter(currency=currency, is_active=True).values_list('value', flat=True)
            allowed = sorted([int(v) for v in db_denoms if v > 0], reverse=True)

        if not allowed:
            return {}

        int_amt = int(amount)
        rem = int_amt
        breakdown: Dict[int, int] = {}
        for denom in allowed:
            if denom <= 0 or denom > rem:
                continue
            count = rem // denom
            if count > 0:
                breakdown[denom] = count
                rem -= count * denom
            if rem == 0:
                break

        return breakdown

    @classmethod
    @db_transaction.atomic
    def get_or_create_kiosk_register(cls, totem: KioskTotem) -> Tuple[Any, Any]:
        """
        Obtiene o aprovisiona la Caja Registradora física (CashRegister) asociada a la terminal
        de autoservicio Kiosco y asegura que cuente con un turno de caja (CashShift) activo y abierto.
        """
        from apps.cash.models import CashRegister, CashRegisterStatus, CashShift, ShiftStatus
        from apps.cash.services import CashService
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        User = get_user_model()
        user_name = f'kiosk_{totem.codigo.lower().replace("-", "_")}'
        kiosk_user, _ = User.objects.get_or_create(
            username=user_name,
            defaults={
                'first_name': 'Terminal',
                'last_name': f'Kiosco {totem.codigo}',
                'email': f'{user_name}@kiosk.globalexchange.com.py',
                'is_active': True,
            }
        )
        cajero_group, _ = Group.objects.get_or_create(name='cajero')
        kiosk_user.groups.add(cajero_group)

        reg_code = f"CAJA-{totem.codigo}"
        register, _ = CashRegister.objects.get_or_create(
            register_code=reg_code,
            defaults={
                'name': f"Caja {totem.nombre}",
                'branch_name': totem.ubicacion.split('-')[0].strip() if '-' in totem.ubicacion else 'Casa Central',
                'status': CashRegisterStatus.CLOSED,
                'is_active': True,
            }
        )

        shift = CashShift.objects.filter(cash_register=register, status=ShiftStatus.OPEN).first()
        if not shift:
            # Asegurar que el usuario no tenga otro turno abierto en otra caja
            CashShift.objects.filter(cashier=kiosk_user, status=ShiftStatus.OPEN).exclude(cash_register=register).update(
                status=ShiftStatus.CLOSED, closed_at=timezone.now()
            )

            # Fondo inicial de apertura para simulación
            initial_balances = {
                'PYG': Decimal('100000000'),
                'USD': Decimal('20000'),
                'EUR': Decimal('20000'),
            }
            active_codes = set(Currency.objects.filter(is_active=True).values_list('code', flat=True))
            initial_balances = {k: v for k, v in initial_balances.items() if k in active_codes}

            register.status = CashRegisterStatus.CLOSED
            register.save(update_fields=['status'])

            shift = CashService.open_shift(
                cash_register=register,
                cashier=kiosk_user,
                initial_balances=initial_balances,
                opening_notes=f"Turno de autoservicio Kiosk {totem.codigo}",
            )

        # Garantizar inventario físico en caja para todas las monedas activas
        cls._ensure_kiosk_banknote_inventory(register, shift)
        return register, shift

    @classmethod
    def _ensure_kiosk_banknote_inventory(cls, register: Any, shift: Any) -> None:
        """
        Aprovisiona existencias físicas de billetes en la caja registradora del kiosco
        para todas las denominaciones de divisas con tasas de cambio activas.
        """
        from apps.cash.inventory_models import (
            CurrencyDenomination, BanknoteInventory, LocationType, ShiftDenominationCount
        )
        from rates.models import ExchangeRate

        active_codes = set(
            ExchangeRate.objects.filter(is_active=True).values_list('base_currency__code', flat=True)
        ) | set(
            ExchangeRate.objects.filter(is_active=True).values_list('target_currency__code', flat=True)
        )
        if not active_codes:
            active_codes = set(Currency.objects.filter(is_active=True).values_list('code', flat=True))

        for code in active_codes:
            curr = Currency.objects.filter(code=code).first()
            if not curr:
                continue
            allowed_denoms = DENOMINACIONES_PERMITIDAS.get(code, [])
            for val in allowed_denoms:
                denom_obj, _ = CurrencyDenomination.objects.get_or_create(
                    currency=curr,
                    value=Decimal(str(val)),
                    defaults={'is_coin': False, 'is_active': True, 'order': val}
                )

                inv, created = BanknoteInventory.objects.get_or_create(
                    location_type=LocationType.REGISTER,
                    cash_register=register,
                    currency=curr,
                    denomination=denom_obj,
                    defaults={'quantity': 500}
                )
                if not created and inv.quantity < 50:
                    inv.quantity = 500
                    inv.save(update_fields=['quantity', 'updated_at'])

                ShiftDenominationCount.objects.get_or_create(
                    shift=shift,
                    currency=curr,
                    denomination=denom_obj,
                    defaults={
                        'opening_quantity': inv.quantity,
                        'system_expected_quantity': inv.quantity,
                    }
                )

    @classmethod
    @db_transaction.atomic
    def sync_transaction_to_cash_register(
        cls,
        totem: KioskTotem,
        transaction: Transaction,
        breakdown_in: Dict[int, int],
        breakdown_out: Dict[int, int],
    ) -> Dict[str, Any]:
        """
        Registra la transacción del Kiosco en la Caja Registradora asociada:
        1. Movimientos contables de caja (CashMovement: TRANSACTION_IN / TRANSACTION_OUT).
        2. Movimientos físicos de billetes (BanknoteInventory, BanknoteMovement, ShiftDenominationCount).
        """
        from apps.cash.services import CashService
        from apps.cash.inventory_services import InventoryService
        from apps.cash.inventory_models import (
            CurrencyDenomination, BanknoteInventory, LocationType, ShiftDenominationCount
        )

        register, shift = cls.get_or_create_kiosk_register(totem)

        # 1. Movimientos contables de caja
        movements = CashService.register_transaction_cash(
            shift=shift,
            transaction=transaction,
            cashier=shift.cashier,
            keycloak_user_id=getattr(shift.cashier, 'username', 'kiosk_system'),
            is_cash_in=True,
            is_cash_out=True,
        )

        # 2. Desglose de entradas a IDs de CurrencyDenomination
        denom_in_amounts: Dict[int, int] = {}
        for denom_val, qty in breakdown_in.items():
            if qty <= 0:
                continue
            denom_obj, _ = CurrencyDenomination.objects.get_or_create(
                currency=transaction.moneda_origen,
                value=Decimal(str(denom_val)),
                defaults={'is_coin': False, 'is_active': True, 'order': denom_val}
            )
            BanknoteInventory.objects.get_or_create(
                location_type=LocationType.REGISTER,
                cash_register=register,
                currency=transaction.moneda_origen,
                denomination=denom_obj,
                defaults={'quantity': 0}
            )
            ShiftDenominationCount.objects.get_or_create(
                shift=shift,
                currency=transaction.moneda_origen,
                denomination=denom_obj,
                defaults={'opening_quantity': 0, 'system_expected_quantity': 0}
            )
            denom_in_amounts[denom_obj.id] = qty

        # 3. Desglose de salidas a IDs de CurrencyDenomination
        denom_out_amounts: Dict[int, int] = {}
        for denom_val, qty in breakdown_out.items():
            if qty <= 0:
                continue
            denom_obj, _ = CurrencyDenomination.objects.get_or_create(
                currency=transaction.moneda_destino,
                value=Decimal(str(denom_val)),
                defaults={'is_coin': False, 'is_active': True, 'order': denom_val}
            )
            inv, _ = BanknoteInventory.objects.get_or_create(
                location_type=LocationType.REGISTER,
                cash_register=register,
                currency=transaction.moneda_destino,
                denomination=denom_obj,
                defaults={'quantity': 500}
            )
            if inv.quantity < qty:
                inv.quantity += (qty + 100)
                inv.save(update_fields=['quantity', 'updated_at'])

            ShiftDenominationCount.objects.get_or_create(
                shift=shift,
                currency=transaction.moneda_destino,
                denomination=denom_obj,
                defaults={'opening_quantity': inv.quantity, 'system_expected_quantity': inv.quantity}
            )
            denom_out_amounts[denom_obj.id] = qty

        # 4. Impacto en inventario físico de billetes
        InventoryService.register_exchange_operation(
            shift=shift,
            currency_in=transaction.moneda_origen,
            denomination_in_amounts=denom_in_amounts,
            currency_out=transaction.moneda_destino,
            denomination_out_amounts=denom_out_amounts,
            performed_by=shift.cashier,
            transaction=transaction,
            keycloak_id=getattr(shift.cashier, 'username', 'kiosk_system'),
        )

        return {
            'register_code': register.register_code,
            'shift_number': shift.shift_number,
            'movements': movements,
            'breakdown_in': breakdown_in,
            'breakdown_out': breakdown_out,
        }

