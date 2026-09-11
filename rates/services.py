"""
Módulo de servicios y motor de cálculo financiero para Tasas de Cambio y Comisiones (rates).

Provee las clases y funciones de negocio especializadas para:
1. Resolución dinámica del cliente activo y su segmento comercial (:class:`~customers.models.Cliente.Segmentacion`).
2. Consulta de reglas de comisión y políticas de precios por segmento (:class:`~rates.models.SegmentCommission`).
3. Obtención y validación de tasas de cambio vigentes (:class:`~rates.models.ExchangeRate`).
4. Motor matemático de cálculo de tasas netas, márgenes de spread bonificados, comisiones
   porcentuales/fijas y liquidaciones de cotización.
"""

from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any, Dict, Optional, Tuple, Union

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpRequest

from customers.models import Cliente, CustomerUserAssignment
from .models import Currency, ExchangeRate, SegmentCommission

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

        return (
            ExchangeRate.objects.filter(
                base_currency__code=base_code,
                base_currency__is_active=True,
                target_currency__code=target_code,
                target_currency__is_active=True,
                is_active=True,
            )
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
    ) -> Dict[str, Any]:
        """
        Ejecuta el cálculo completo de la cotización neta para una transacción cambiaria.

        Fórmulas financieras aplicadas:
        --------------------------------
        1. **Tasa Base Oficial:**
           - Si la operación es ``BUY`` (el cliente compra divisa base): la casa vende a ``exchange_rate.sell_rate``.
           - Si la operación es ``SELL`` (el cliente vende divisa base): la casa compra a ``exchange_rate.buy_rate``.

        2. **Spread y Bonificación Preferencial:**
           - Margen de spread base: ``spread = sell_rate - buy_rate``.
           - Spread efectivo bonificado: ``effective_spread = spread * (1 - spread_discount_percentage / 100)``.
           - Ahorro de spread por unidad: ``spread_benefit = spread - effective_spread``.
           - Tasa efectiva preferencial (*effective_rate*):
             * En ``BUY``: ``sell_rate - (spread_benefit / 2)`` (el cliente paga menos por cada unidad de divisa base).
             * En ``SELL``: ``buy_rate + (spread_benefit / 2)`` (el cliente recibe más por cada unidad de divisa base).

        3. **Conversión Bruta de Montos:**
           - Si ``is_source_base == True`` (monto expresado en divisa base, ej: 1.000 USD):
             * ``base_amount = amount``
             * ``gross_target_amount = amount * effective_rate``
           - Si ``is_source_base == False`` (monto expresado en divisa contraparte, ej: 7.500.000 PYG):
             * ``gross_target_amount = amount``
             * ``base_amount = amount / effective_rate``

        4. **Comisiones y Cargos Administrativos:**
           - Comisión porcentual: ``(gross_target_amount * commission_percentage) / 100``.
           - Cargo fijo: ``fixed_fee`` (en divisa contraparte / local).
           - Comisión total: ``total_commission = commission_percentage_amount + fixed_fee``.

        5. **Monto Neto Final y Tasa Neta Efectiva:**
           - En ``BUY`` (cliente entrega moneda objetivo para recibir divisa base):
             * ``net_target_amount = gross_target_amount + total_commission`` (total a pagar).
             * ``final_effective_rate = net_target_amount / base_amount``.
           - En ``SELL`` (cliente entrega divisa base para recibir moneda objetivo):
             * ``net_target_amount = max(0, gross_target_amount - total_commission)`` (total a recibir).
             * ``final_effective_rate = net_target_amount / base_amount``.

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
        :return: Diccionario exhaustivo con todos los componentes del cálculo financiero.
        :rtype: dict
        :raises django.core.exceptions.ValidationError: Si los parámetros o cotizaciones son inválidos.
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
