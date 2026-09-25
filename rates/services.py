"""
Módulo de servicios y motor de cálculo financiero para Tasas de Cambio y Comisiones (rates).

Provee las clases y funciones de negocio especializadas para:

1. Resolución dinámica del cliente activo y su segmento comercial (:class:`~customers.models.Cliente.Segmentacion`).
2. Consulta de reglas de comisión y políticas de precios por segmento (:class:`~rates.models.SegmentCommission`).
3. Obtención y validación de tasas de cambio vigentes (:class:`~rates.models.ExchangeRate`).
4. Motor matemático de cálculo de tasas netas, márgenes de spread bonificados, comisiones porcentuales/fijas y liquidaciones de cotización.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any, Dict, Optional, Tuple, Union
import uuid

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpRequest
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from customers.models import Cliente, CustomerUserAssignment
from .models import Currency, ExchangeRate, OperationLimit, SegmentCommission

logger = logging.getLogger(__name__)


def get_active_customer(request: HttpRequest) -> Optional[Cliente]:
    """
    Resuelve de manera unificada y segura la instancia de :class:`~customers.models.Cliente`
    activa en la sesión o contexto de la solicitud HTTP.

    Estrategia de resolución:
    1. Atributo dinámico ``request.active_customer`` (provisto por middleware).
    2. Identificador en sesión ``request.session['active_customer_id']``.
    3. Asignación de representación activa con el usuario autenticado (:class:`~customers.models.CustomerUserAssignment`).
    4. Coincidencia por correo institucional/personal del usuario.
    5. Parámetro ``cliente_id`` en GET/POST (disponible para operadores o administradores).
    6. Fallback al primer cliente activo en el sistema para roles administrativos.

    :param request: Solicitud HTTP entrante.
    :type request: django.http.HttpRequest
    :return: Instancia del cliente activo o None si no se encuentra ninguno.
    :rtype: customers.models.Cliente or None
    """
    if not request.user.is_authenticated:
        return None

    # 1. Atributo inyectado en middleware
    if hasattr(request, 'active_customer') and request.active_customer:
        return request.active_customer

    # 2. Clave en sesión
    if hasattr(request, 'session') and request.session:
        session_customer_id = request.session.get('active_customer_id')
        if session_customer_id:
            c = Cliente.objects.filter(id=session_customer_id, is_active=True).first()
            if c:
                return c

    # 3. Asignación en CustomerUserAssignment
    if hasattr(request.user, 'customer_assignments'):
        asig = (
            request.user.customer_assignments.filter(is_active=True, customer__is_active=True)
            .select_related('customer')
            .order_by('-is_primary_representative', '-assigned_at')
            .first()
        )
        if asig:
            return asig.customer

    # 4. Consulta por correo
    if request.user.email:
        cliente_email = Cliente.objects.filter(correo__iexact=request.user.email, is_active=True).first()
        if cliente_email:
            return cliente_email

    # 5. Parámetro explícito para administradores o personal staff
    if request.user.is_staff or request.user.is_superuser:
        cliente_id_param = request.GET.get('cliente_id') or request.POST.get('cliente_id')
        if cliente_id_param:
            return Cliente.objects.filter(id=cliente_id_param, is_active=True).first()
        return Cliente.objects.filter(is_active=True).first()

    return None


class OperationLimitValidationService:
    """
    Servicio de validación y control de límites operativos por moneda y segmento (SCRUM-77 / SCRUM-64).

    Permite verificar que las cotizaciones y operaciones cambiarias respeten:
    - Monto mínimo por operación.
    - Monto máximo por operación.
    - Límite acumulado diario por cliente en la divisa operada.
    - Límite acumulado mensual por cliente en la divisa operada.
    """

    DEFAULT_SEGMENT = Cliente.Segmentacion.MINORISTA

    @classmethod
    def get_limit_rule(
        cls,
        segment_or_customer: Union[str, Cliente, None] = None,
        currency: Union[str, Currency, None] = None,
    ) -> Optional[OperationLimit]:
        """
        Obtiene la regla activa de :class:`~rates.models.OperationLimit` correspondiente al
        segmento y divisa especificados.

        :param segment_or_customer: Código de segmento ('MIN', 'MAY', 'COR', 'VIP') o instancia de Cliente.
        :type segment_or_customer: str or customers.models.Cliente or None
        :param currency: Código ISO de moneda (ej: 'USD') o instancia de Currency.
        :type currency: str or rates.models.Currency or None
        :return: Instancia de OperationLimit activa o None si no existe parametrización.
        :rtype: rates.models.OperationLimit or None
        """
        segment_code = cls.DEFAULT_SEGMENT
        if isinstance(segment_or_customer, Cliente):
            segment_code = segment_or_customer.segmentacion or cls.DEFAULT_SEGMENT
        elif isinstance(segment_or_customer, str) and segment_or_customer.strip():
            segment_code = segment_or_customer.strip().upper()

        if not currency:
            return None

        currency_code = currency.code if isinstance(currency, Currency) else str(currency).upper().strip()

        return (
            OperationLimit.objects.filter(
                segment=segment_code,
                currency__code=currency_code,
                currency__is_active=True,
                is_active=True,
            )
            .select_related('currency')
            .first()
        )

    @classmethod
    def get_customer_accumulated_volume(
        cls,
        cliente: Optional[Cliente],
        currency: Union[str, Currency],
        period: str = 'daily',
        reference_date: Optional[timezone.datetime] = None,
    ) -> Decimal:
        """
        Calcula el volumen acumulado de transacciones no canceladas para un cliente
        en una divisa dada dentro del período especificado ('daily' o 'monthly').

        :param cliente: Ficha de cliente.
        :type cliente: customers.models.Cliente or None
        :param currency: Código ISO o instancia de Currency.
        :type currency: str or rates.models.Currency
        :param period: 'daily' para el día en curso o 'monthly' para el mes en curso.
        :type period: str
        :param reference_date: Momento de referencia (por defecto ahora).
        :type reference_date: datetime.datetime or None
        :return: Volumen monetario acumulado.
        :rtype: decimal.Decimal
        """
        if not cliente:
            return Decimal('0.00')

        now = reference_date or timezone.now()
        curr_code = currency.code if isinstance(currency, Currency) else str(currency).upper().strip()

        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Consulta desacoplada al modelo Transaction si existe
        try:
            from django.apps import apps
            if apps.is_installed('transactions'):
                TransactionModel = apps.get_model('transactions', 'Transaction')
                from django.db.models import Sum
                total = TransactionModel.objects.filter(
                    cliente=cliente,
                    base_currency__code=curr_code,
                    created_at__gte=start_date,
                    created_at__lte=now,
                ).exclude(estado__iexact='CANCELADA').aggregate(total=Sum('monto_origen'))['total']

                if total is not None:
                    return Decimal(str(total))
        except Exception:
            pass

        return Decimal('0.00')

    @classmethod
    def validate_operation_amount(
        cls,
        segment_or_customer: Union[str, Cliente, None] = None,
        currency: Union[str, Currency, None] = None,
        amount: Union[Decimal, float, int, str] = Decimal('0.00'),
        cliente: Optional[Cliente] = None,
        accumulated_daily: Optional[Union[Decimal, float, int, str]] = None,
        accumulated_monthly: Optional[Union[Decimal, float, int, str]] = None,
        raise_exception: bool = False,
    ) -> Dict[str, Any]:
        """
        Valida un monto frente a las reglas de límites operativos vigentes.

        :param segment_or_customer: Código de segmento o instancia de Cliente.
        :type segment_or_customer: str or customers.models.Cliente or None
        :param currency: Moneda de la transacción (código ISO o instancia Currency).
        :type currency: str or rates.models.Currency or None
        :param amount: Monto de la operación individual.
        :type amount: decimal.Decimal or float or int or str
        :param cliente: Cliente ejecutor (para computar consumos acumulados).
        :type cliente: customers.models.Cliente or None
        :param accumulated_daily: Volumen diario ya acumulado (opcional para inyección/tests).
        :type accumulated_daily: decimal.Decimal or float or int or str or None
        :param accumulated_monthly: Volumen mensual ya acumulado (opcional para inyección/tests).
        :type accumulated_monthly: decimal.Decimal or float or int or str or None
        :param raise_exception: Si es True, lanza ValidationError si no supera la validación.
        :type raise_exception: bool
        :return: Diccionario completo de validación.
        :rtype: dict
        :raises django.core.exceptions.ValidationError: Si raise_exception=True y la validación falla.
        """
        try:
            dec_amount = Decimal(str(amount))
        except Exception as exc:
            if raise_exception:
                raise ValidationError({'amount': f'Monto numérico inválido: {exc}'})
            return {
                'is_valid': False,
                'has_rule': False,
                'errors': [f'Monto numérico inválido: {exc}'],
                'warnings': [],
                'limit_rule_id': None,
                'segment': cls.DEFAULT_SEGMENT,
                'currency_code': 'DIVISA',
                'monto_minimo': Decimal('0.00'),
                'monto_maximo': Decimal('0.00'),
                'limite_diario': Decimal('0.00'),
                'limite_mensual': Decimal('0.00'),
                'accumulated_daily': Decimal('0.00'),
                'accumulated_monthly': Decimal('0.00'),
                'remaining_daily': None,
                'remaining_monthly': None,
                'amount': Decimal('0.00'),
            }

        resolved_client = (
            cliente
            if isinstance(cliente, Cliente)
            else (segment_or_customer if isinstance(segment_or_customer, Cliente) else None)
        )
        rule = cls.get_limit_rule(segment_or_customer=segment_or_customer or resolved_client, currency=currency)

        curr_code = (
            currency.code
            if isinstance(currency, Currency)
            else (str(currency).upper().strip() if currency else 'DIVISA')
        )
        segment_code = (
            rule.segment
            if rule
            else (
                resolved_client.segmentacion
                if resolved_client
                else (str(segment_or_customer).upper().strip() if segment_or_customer else cls.DEFAULT_SEGMENT)
            )
        )

        if not rule:
            # Sin regla parametrizada: comportamiento permisivo por defecto
            return {
                'is_valid': True,
                'has_rule': False,
                'errors': [],
                'warnings': [],
                'limit_rule_id': None,
                'segment': segment_code,
                'currency_code': curr_code,
                'monto_minimo': Decimal('0.00'),
                'monto_maximo': Decimal('0.00'),
                'limite_diario': Decimal('0.00'),
                'limite_mensual': Decimal('0.00'),
                'accumulated_daily': Decimal('0.00'),
                'accumulated_monthly': Decimal('0.00'),
                'remaining_daily': None,
                'remaining_monthly': None,
                'amount': dec_amount,
            }

        # Resolver acumulados
        if accumulated_daily is None:
            dec_accum_daily = cls.get_customer_accumulated_volume(resolved_client, currency, period='daily')
        else:
            dec_accum_daily = Decimal(str(accumulated_daily))

        if accumulated_monthly is None:
            dec_accum_monthly = cls.get_customer_accumulated_volume(resolved_client, currency, period='monthly')
        else:
            dec_accum_monthly = Decimal(str(accumulated_monthly))

        validation = rule.validate_amount(
            amount=dec_amount,
            accumulated_daily=dec_accum_daily,
            accumulated_monthly=dec_accum_monthly,
        )

        result_payload = {
            'is_valid': validation['is_valid'],
            'has_rule': True,
            'limit_rule_id': rule.id,
            'errors': validation['errors'],
            'warnings': [],
            'segment': segment_code,
            'currency_code': curr_code,
            'monto_minimo': rule.monto_minimo,
            'monto_maximo': rule.monto_maximo,
            'limite_diario': rule.limite_diario,
            'limite_mensual': rule.limite_mensual,
            'accumulated_daily': dec_accum_daily,
            'accumulated_monthly': dec_accum_monthly,
            'remaining_daily': validation['remaining_daily'],
            'remaining_monthly': validation['remaining_monthly'],
            'amount': dec_amount,
        }

        if not result_payload['is_valid'] and raise_exception:
            raise ValidationError({'amount': result_payload['errors']})

        return result_payload


class RateCalculationService:
    """
    Motor de cálculo financiero de cotizaciones y tasas netas aplicables.

    Implementa las fórmulas financieras requeridas para:
    - Aplicar bonificaciones y descuentos preferenciales sobre el margen cambiario (*spread*).
    - Ajustar la tasa oficial de compra o venta a la tasa preferencial del segmento.
    - Computar las comisiones porcentuales sobre el volumen operado y los cargos fijos administrativos.
    - Determinar el monto bruto, los cargos totales y el monto neto final a pagar o recibir.
    """

    DEFAULT_SEGMENT = Cliente.Segmentacion.MINORISTA

    @classmethod
    def get_commission_rule(
        cls,
        segment_or_customer: Union[str, Cliente, None] = None,
    ) -> SegmentCommission:
        """
        Obtiene la regla de comisión activa (:class:`~rates.models.SegmentCommission`)
        correspondiente al segmento especificado o al segmento del cliente provisto.

        Si no existe una regla parametrizada o se encuentra inactiva, retorna una instancia
        virtual de :class:`~rates.models.SegmentCommission` con valores neutros (0.00).

        :param segment_or_customer: Código de segmento ('MIN', 'MAY', 'COR', 'VIP') o instancia de Cliente.
        :type segment_or_customer: str or customers.models.Cliente or None
        :return: Instancia de SegmentCommission (persistida o virtual por defecto).
        :rtype: rates.models.SegmentCommission
        """
        segment_code = cls.DEFAULT_SEGMENT

        if isinstance(segment_or_customer, Cliente):
            segment_code = segment_or_customer.segmentacion or cls.DEFAULT_SEGMENT
        elif isinstance(segment_or_customer, str) and segment_or_customer.strip():
            segment_code = segment_or_customer.strip().upper()

        rule = SegmentCommission.objects.filter(segment=segment_code, is_active=True).first()
        if rule:
            return rule

        # Si no existe regla configurada, retornar instancia en memoria con valores en cero
        return SegmentCommission(
            segment=segment_code,
            commission_percentage=Decimal('0.00'),
            fixed_fee=Decimal('0.00'),
            spread_discount_percentage=Decimal('0.00'),
            is_active=True,
        )

    @classmethod
    def get_latest_exchange_rate(
        cls,
        base_currency: Union[str, Currency],
        target_currency: Union[str, Currency],
    ) -> Optional[ExchangeRate]:
        """
        Obtiene la tasa de cambio activa más reciente entre dos divisas.

        :param base_currency: Código ISO o instancia de la moneda base (ej: 'USD').
        :type base_currency: str or rates.models.Currency
        :param target_currency: Código ISO o instancia de la moneda objetivo (ej: 'PYG').
        :type target_currency: str or rates.models.Currency
        :return: Instancia de ExchangeRate más reciente o None si no existe cotización vigente.
        :rtype: rates.models.ExchangeRate or None
        """
        base_code = base_currency.code if isinstance(base_currency, Currency) else str(base_currency).upper().strip()
        target_code = target_currency.code if isinstance(target_currency, Currency) else str(target_currency).upper().strip()

        now = timezone.now()
        return (
            ExchangeRate.objects.filter(
                base_currency__code=base_code,
                base_currency__is_active=True,
                target_currency__code=target_code,
                target_currency__is_active=True,
                is_active=True,
                valid_from__lte=now,
            )
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now))
            .select_related('base_currency', 'target_currency')
            .order_by('-valid_from', '-created_at')
            .first()
        )

    @classmethod
    def calculate_quotation(
        cls,
        exchange_rate: ExchangeRate,
        segment_or_customer: Union[str, Cliente, None] = None,
        amount: Union[Decimal, float, int, str] = Decimal('100.00'),
        operation_type: str = 'BUY',
        is_source_base: bool = True,
        validate_limits: bool = True,
        raise_on_limit_violation: bool = False,
    ) -> Dict[str, Any]:
        """
        Ejecuta el cálculo completo de la cotización neta para una transacción cambiaria.

        Fórmulas financieras aplicadas:

        1. **Tasa Base Oficial:**
           - Si la operación es ``BUY`` (el cliente compra divisa base): la casa vende a ``exchange_rate.sell_rate``.
           - Si la operación es ``SELL`` (el cliente vende divisa base): la casa compra a ``exchange_rate.buy_rate``.

        2. **Spread y Bonificación Preferencial:**
           - Margen de spread base: ``spread = sell_rate - buy_rate``.
           - Spread efectivo bonificado: ``effective_spread = spread * (1 - spread_discount_percentage / 100)``.
           - Ahorro de spread por unidad: ``spread_benefit = spread - effective_spread``.
           - Tasa efectiva preferencial (*effective_rate*): en BUY ``sell_rate - (spread_benefit / 2)``, en SELL ``buy_rate + (spread_benefit / 2)``.

        3. **Conversión Bruta de Montos:**
           - Si ``is_source_base == True``: ``base_amount = amount`` y ``gross_target_amount = amount * effective_rate``.
           - Si ``is_source_base == False``: ``gross_target_amount = amount`` y ``base_amount = amount / effective_rate``.

        4. **Comisiones y Cargos Administrativos:**
           - Comisión porcentual: ``(gross_target_amount * commission_percentage) / 100``.
           - Cargo fijo: ``fixed_fee`` (en divisa contraparte / local).
           - Comisión total: ``total_commission = commission_percentage_amount + fixed_fee``.

        5. **Monto Neto Final y Tasa Neta Efectiva:**
           - En ``BUY``: ``net_target_amount = gross_target_amount + total_commission``, ``final_effective_rate = net_target_amount / base_amount``.
           - En ``SELL``: ``net_target_amount = max(0, gross_target_amount - total_commission)``, ``final_effective_rate = net_target_amount / base_amount``.

        6. **Validación de Límites Operativos (SCRUM-77):**
           - Control de topes mínimos, máximos, diarios y mensuales según el segmento del cliente y divisa.

        :param exchange_rate: Instancia de la cotización oficial base.
        :type exchange_rate: rates.models.ExchangeRate
        :param segment_or_customer: Ficha de cliente o código de segmentación.
        :type segment_or_customer: str or customers.models.Cliente or None
        :param amount: Monto de la operación (debe ser estrictamente positivo).
        :type amount: decimal.Decimal or float or int or str
        :param operation_type: Tipo de operación: 'BUY' (compra de divisa base) o 'SELL' (venta de divisa base).
        :type operation_type: str
        :param is_source_base: True si el monto está en divisa base, False si está en divisa objetivo.
        :type is_source_base: bool
        :param validate_limits: Si es True, ejecuta la verificación de límites operativos del segmento.
        :type validate_limits: bool
        :param raise_on_limit_violation: Si es True, lanza ValidationError cuando se exceden los límites.
        :type raise_on_limit_violation: bool
        :return: Diccionario exhaustivo con todos los componentes del cálculo financiero y límites.
        :rtype: dict
        :raises django.core.exceptions.ValidationError: Si los parámetros o límites son violados con raise_on_limit_violation=True.
        """
        # Validación de tipo de operación
        op_type = str(operation_type).upper().strip()
        if op_type not in ('BUY', 'SELL'):
            raise ValidationError({'operation_type': "El tipo de operación debe ser 'BUY' (Compra) o 'SELL' (Venta)."})

        # Conversión y validación de monto
        try:
            dec_amount = Decimal(str(amount))
        except Exception as exc:
            raise ValidationError({'amount': f'Monto inválido: {exc}'})

        if dec_amount <= Decimal('0'):
            raise ValidationError({'amount': 'El monto de la transacción debe ser estrictamente mayor a cero.'})

        # Regla de comisión por segmento
        commission_rule = cls.get_commission_rule(segment_or_customer)
        segment_code = commission_rule.segment
        segment_display = dict(Cliente.Segmentacion.choices).get(segment_code, segment_code)

        # Divisas
        base_curr = exchange_rate.base_currency
        target_curr = exchange_rate.target_currency

        # Tasas oficiales
        buy_rate = exchange_rate.buy_rate
        sell_rate = exchange_rate.sell_rate
        official_spread = exchange_rate.spread
        mid_rate = (buy_rate + sell_rate) / Decimal('2.00')

        # 1. Tasa base según operación
        official_rate = sell_rate if op_type == 'BUY' else buy_rate

        # 2. Aplicación de descuento de spread
        discount_pct = commission_rule.spread_discount_percentage or Decimal('0.00')
        effective_spread = commission_rule.apply_spread_discount(official_spread)
        spread_benefit = official_spread - effective_spread
        half_benefit = (spread_benefit / Decimal('2.00')).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

        if op_type == 'BUY':
            # Cliente compra divisa base: paga menos
            effective_rate = (sell_rate - half_benefit).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            # Asegurar que nunca sea menor a la tasa de compra oficial
            if effective_rate < buy_rate:
                effective_rate = buy_rate
        else:
            # Cliente vende divisa base: recibe más
            effective_rate = (buy_rate + half_benefit).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            # Asegurar que nunca sea mayor a la tasa de venta oficial
            if effective_rate > sell_rate:
                effective_rate = sell_rate

        # 3. Conversión de volúmenes brutos
        target_decimals = target_curr.decimal_places if target_curr else 2
        base_decimals = base_curr.decimal_places if base_curr else 2

        target_quantize = Decimal('10') ** -target_decimals
        base_quantize = Decimal('10') ** -base_decimals

        if is_source_base:
            base_amount = dec_amount.quantize(base_quantize, rounding=ROUND_HALF_UP)
            gross_target_amount = (base_amount * effective_rate).quantize(target_quantize, rounding=ROUND_HALF_UP)
            official_gross_target = (base_amount * official_rate).quantize(target_quantize, rounding=ROUND_HALF_UP)
        else:
            gross_target_amount = dec_amount.quantize(target_quantize, rounding=ROUND_HALF_UP)
            base_amount = (gross_target_amount / effective_rate).quantize(base_quantize, rounding=ROUND_HALF_UP)
            official_gross_target = gross_target_amount

        # 4. Cálculo de comisiones sobre el volumen en moneda objetivo/local
        comm_pct = commission_rule.commission_percentage or Decimal('0.00')
        commission_pct_amount = ((gross_target_amount * comm_pct) / Decimal('100.00')).quantize(
            target_quantize, rounding=ROUND_HALF_UP
        )
        fixed_fee = (commission_rule.fixed_fee or Decimal('0.00')).quantize(target_quantize, rounding=ROUND_HALF_UP)
        total_commission = (commission_pct_amount + fixed_fee).quantize(target_quantize, rounding=ROUND_HALF_UP)

        # 5. Montos netos y tasa final
        if op_type == 'BUY':
            # Cliente paga el total convertido más las comisiones aplicables
            net_target_amount = (gross_target_amount + total_commission).quantize(target_quantize, rounding=ROUND_HALF_UP)
            # Ahorro por bonificación de spread
            spread_savings = max(Decimal('0.00'), (official_gross_target - gross_target_amount)).quantize(
                target_quantize, rounding=ROUND_HALF_UP
            )
        else:
            # Cliente recibe el total convertido menos las comisiones aplicables
            net_target_amount = max(Decimal('0.00'), (gross_target_amount - total_commission)).quantize(
                target_quantize, rounding=ROUND_HALF_UP
            )
            # Ahorro por bonificación de spread (ganancia extra recibida)
            spread_savings = max(Decimal('0.00'), (gross_target_amount - official_gross_target)).quantize(
                target_quantize, rounding=ROUND_HALF_UP
            )

        if base_amount > Decimal('0'):
            final_effective_rate = (net_target_amount / base_amount).quantize(
                Decimal('0.000001'), rounding=ROUND_HALF_UP
            )
        else:
            final_effective_rate = effective_rate

        # 6. Validación de límites operativos (SCRUM-77)
        limits_result = None
        if validate_limits:
            limits_result = OperationLimitValidationService.validate_operation_amount(
                segment_or_customer=segment_or_customer,
                currency=base_curr if is_source_base else target_curr,
                amount=base_amount if is_source_base else gross_target_amount,
                cliente=segment_or_customer if isinstance(segment_or_customer, Cliente) else None,
                raise_exception=raise_on_limit_violation,
            )

        return {
            'success': True,
            'exchange_rate_id': exchange_rate.id,
            'base_currency': {
                'code': base_curr.code,
                'name': base_curr.name,
                'symbol': base_curr.symbol,
                'decimal_places': base_decimals,
            },
            'target_currency': {
                'code': target_curr.code,
                'name': target_curr.name,
                'symbol': target_curr.symbol,
                'decimal_places': target_decimals,
            },
            'operation_type': op_type,
            'operation_label': 'Compra de Divisas' if op_type == 'BUY' else 'Venta de Divisas',
            'is_source_base': is_source_base,
            'segment': {
                'code': segment_code,
                'name': segment_display,
                'commission_percentage': comm_pct,
                'fixed_fee': fixed_fee,
                'spread_discount_percentage': discount_pct,
            },
            # Cotización y spreads
            'official_buy_rate': buy_rate,
            'official_sell_rate': sell_rate,
            'official_rate': official_rate,
            'official_spread': official_spread,
            'mid_rate': mid_rate,
            'effective_spread': effective_spread,
            'effective_rate': effective_rate,
            # Importes
            'base_amount': base_amount,
            'gross_target_amount': gross_target_amount,
            'commission_percentage_amount': commission_pct_amount,
            'fixed_fee': fixed_fee,
            'total_commission': total_commission,
            'net_target_amount': net_target_amount,
            'final_effective_rate': final_effective_rate,
            'spread_savings': spread_savings,
            'limits': limits_result,
        }

    @classmethod
    def calculate_quotation_by_codes(
        cls,
        base_currency_code: str,
        target_currency_code: str,
        segment_or_customer: Union[str, Cliente, None] = None,
        amount: Union[Decimal, float, int, str] = Decimal('100.00'),
        operation_type: str = 'BUY',
        is_source_base: bool = True,
    ) -> Dict[str, Any]:
        """
        Ejecuta la cotización buscando automáticamente la cotización activa más reciente
        entre los códigos de moneda dados.

        :param base_currency_code: Código ISO de la moneda base (ej: 'USD').
        :type base_currency_code: str
        :param target_currency_code: Código ISO de la moneda contraparte (ej: 'PYG').
        :type target_currency_code: str
        :param segment_or_customer: Ficha de cliente o código de segmentación.
        :type segment_or_customer: str or customers.models.Cliente or None
        :param amount: Monto de la operación.
        :type amount: decimal.Decimal or str or float
        :param operation_type: 'BUY' o 'SELL'.
        :type operation_type: str
        :param is_source_base: Indicador de si el monto es en divisa base.
        :type is_source_base: bool
        :return: Diccionario con la cotización completa.
        :rtype: dict
        :raises django.core.exceptions.ValidationError: Si no se encuentra tasa para el par de divisas.
        """
        rate = cls.get_latest_exchange_rate(base_currency_code, target_currency_code)
        if not rate:
            raise ValidationError({
                'exchange_rate': (
                    f'No se encontró una cotización activa vigente para el par '
                    f'{base_currency_code.upper()}/{target_currency_code.upper()}.'
                )
            })

        return cls.calculate_quotation(
            exchange_rate=rate,
            segment_or_customer=segment_or_customer,
            amount=amount,
            operation_type=operation_type,
            is_source_base=is_source_base,
        )


class QuoteFreezeService:
    """
    Servicio de gestión y congelamiento temporal de cotizaciones para clientes (SCRUM-54).

    Permite asegurar una tasa de cambio y desglose financiero durante un lapso de
    5 minutos (300 segundos) mediante un token de sesión único.
    """

    FREEZE_DURATION_SECONDS = 300  # 5 minutos

    @classmethod
    def _sanitize_data(cls, data: Any) -> Any:
        """
        Convierte de forma recursiva Decimals a floats o estructuras compatibles
        con JSON y la serialización de sesiones de Django.
        """
        if isinstance(data, Decimal):
            return float(data)
        if isinstance(data, (int, float, str, bool)) or data is None:
            return data
        if isinstance(data, dict):
            return {str(k): cls._sanitize_data(v) for k, v in data.items()}
        if isinstance(data, (list, tuple, set)):
            return [cls._sanitize_data(item) for item in data]
        return str(data)

    @classmethod
    def freeze_quote(cls, request: HttpRequest, calculation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Congela una cotización en la sesión HTTP del usuario por 5 minutos (300 segundos).

        :param request: Solicitud HTTP del usuario/cliente.
        :type request: django.http.HttpRequest
        :param calculation_data: Diccionario retornado por RateCalculationService.calculate_quotation.
        :type calculation_data: dict
        :return: Diccionario con token, timestamps y cálculo serializado.
        :rtype: dict
        """
        now = timezone.now()
        expires_at = now + timedelta(seconds=cls.FREEZE_DURATION_SECONDS)
        token = f"QTZ-{uuid.uuid4().hex[:12].upper()}"

        sanitized_calc = cls._sanitize_data(calculation_data)

        payload = {
            'token': token,
            'frozen_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'duration_seconds': cls.FREEZE_DURATION_SECONDS,
            'calculation': sanitized_calc,
        }

        if hasattr(request, 'session'):
            request.session['frozen_quote'] = payload
            if hasattr(request.session, 'modified'):
                request.session.modified = True

        return {
            'success': True,
            'token': token,
            'frozen_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'duration_seconds': cls.FREEZE_DURATION_SECONDS,
            'remaining_seconds': cls.FREEZE_DURATION_SECONDS,
            'is_expired': False,
            'calculation': sanitized_calc,
        }

    @classmethod
    def get_frozen_quote(cls, request: HttpRequest, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene la cotización congelada activa de la sesión, calculando el tiempo restante y estado.

        :param request: Solicitud HTTP.
        :type request: django.http.HttpRequest
        :param token: Token de cotización opcional para verificar coincidencia.
        :type token: str or None
        :return: Diccionario de la cotización con estado de expiración y segundos restantes, o None.
        :rtype: dict or None
        """
        if not hasattr(request, 'session'):
            return None

        frozen = request.session.get('frozen_quote')
        if not frozen or not isinstance(frozen, dict):
            return None

        if token and frozen.get('token') != token:
            return None

        expires_at_str = frozen.get('expires_at')
        if not expires_at_str:
            return None

        try:
            expires_at = parse_datetime(expires_at_str)
            if expires_at is None:
                return None
            if timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at)
        except Exception:
            return None

        now = timezone.now()
        remaining_seconds = max(0, int((expires_at - now).total_seconds()))
        is_expired = (now >= expires_at) or (remaining_seconds <= 0)

        result = dict(frozen)
        result['remaining_seconds'] = remaining_seconds
        result['is_expired'] = is_expired
        return result

    @classmethod
    def unfreeze_quote(cls, request: HttpRequest, token: Optional[str] = None) -> bool:
        """
        Descongela o remueve la cotización activa de la sesión del usuario.

        :param request: Solicitud HTTP.
        :type request: django.http.HttpRequest
        :param token: Token opcional para validar antes de eliminar.
        :type token: str or None
        :return: True si se eliminó una cotización existente, False en caso contrario.
        :rtype: bool
        """
        if not hasattr(request, 'session'):
            return False

        frozen = request.session.get('frozen_quote')
        if not frozen:
            return False

        if token and frozen.get('token') != token:
            return False

        del request.session['frozen_quote']
        if hasattr(request.session, 'modified'):
            request.session.modified = True
        return True

    @classmethod
    def validate_quote_token(cls, request: HttpRequest, token: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Valida si un token de cotización existe en sesión y se encuentra vigente dentro de los 5 minutos.

        :param request: Solicitud HTTP.
        :type request: django.http.HttpRequest
        :param token: Token a verificar.
        :type token: str
        :return: Tupla (es_valido, datos_cotizacion, mensaje_estado).
        :rtype: tuple[bool, dict or None, str]
        """
        if not token:
            return False, None, "Token de cotización no provisto."

        frozen = cls.get_frozen_quote(request, token=token)
        if not frozen:
            return False, None, "No se encontró una cotización congelada para este token o sesión."

        if frozen.get('is_expired', False):
            return False, frozen, "La cotización congelada ha expirado (límite de 5 minutos excedido)."

        return True, frozen, "Cotización congelada válida y vigente."
