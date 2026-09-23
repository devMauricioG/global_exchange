"""
Módulo de servicios transaccionales para operaciones cambiarias (transactions).

Provee la lógica de negocio atómica (:class:`TransactionService`) para formalizar
órdenes de compra y venta de divisas en estado PENDIENTE, validando la vigencia
de cotizaciones congeladas en sesión o cotizaciones en vivo, comprobando límites
operativos y asociando los instrumentos de pago y acreditación del cliente.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, Optional, Union

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest

from customers.models import Cliente
from payments.models import PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate
from rates.services import (
    OperationLimitValidationService,
    QuoteFreezeService,
    RateCalculationService,
    get_active_customer,
)
from .models import Transaction

logger = logging.getLogger(__name__)


class TransactionService:
    """
    Servicio transaccional atómico para el registro y formalización de órdenes de cambio.

    Garantiza la consistencia financiera, el respeto de límites operativos por segmento
    y la validez de los tokens de congelamiento de cotizaciones durante el flujo de orden.
    """

    @classmethod

    def _resolve_customer(
        cls,
        request: Optional[HttpRequest] = None,
        cliente: Optional[Cliente] = None,
    ) -> Cliente:
        """
        Resuelve y valida la presencia de una instancia activa de Cliente.
        """
        target_client = cliente
        if not target_client and request:
            target_client = get_active_customer(request)

        if not target_client or not isinstance(target_client, Cliente):
            raise ValidationError({
                'cliente': 'No se pudo identificar un cliente activo para procesar la transacción.'
            })
        return target_client

    @classmethod
    def _validate_payment_and_receiving_methods(
        cls,
        cliente: Cliente,
        medio_pago_id: Union[int, str, PaymentMethod],
        medio_acreditacion_id: Union[int, str, ReceivingMethod],
    ) -> tuple[PaymentMethod, ReceivingMethod]:
        """
        Valida que los medios de pago y acreditación indicados existan, estén activos
        y pertenezcan al cliente titular de la orden.
        """
        if isinstance(medio_pago_id, PaymentMethod):
            medio_pago = medio_pago_id
        else:
            try:
                medio_pago = PaymentMethod.objects.get(
                    id=int(medio_pago_id),
                    cliente=cliente,
                    activo=True,
                )
            except (PaymentMethod.DoesNotExist, ValueError, TypeError):
                raise ValidationError({
                    'medio_pago_origen': 'El medio de pago seleccionado es inválido, inactivo o no pertenece al cliente.'
                })

        if isinstance(medio_acreditacion_id, ReceivingMethod):
            medio_acreditacion = medio_acreditacion_id
        else:
            try:
                medio_acreditacion = ReceivingMethod.objects.get(
                    id=int(medio_acreditacion_id),
                    cliente=cliente,
                    activo=True,
                )
            except (ReceivingMethod.DoesNotExist, ValueError, TypeError):
                raise ValidationError({
                    'medio_acreditacion_destino': 'El medio de acreditación seleccionado es inválido, inactivo o no pertenece al cliente.'
                })

        return medio_pago, medio_acreditacion

    @classmethod
    def create_order_from_frozen_quote(
        cls,
        request: HttpRequest,
        token: str,
        medio_pago_id: Union[int, str, PaymentMethod],
        medio_acreditacion_id: Union[int, str, ReceivingMethod],
        cliente: Optional[Cliente] = None,
        usuario: Any = None,
        observaciones: str = '',
    ) -> Transaction:
        """
        Crea y formaliza una transacción en estado PENDIENTE utilizando los datos de una
        cotización congelada previamente en sesión.

        :param request: Solicitud HTTP con la sesión activa.
        :type request: django.http.HttpRequest
        :param token: Token de congelamiento (ej. QTZ-XXXXXXXX).
        :type token: str
        :param medio_pago_id: ID o instancia del medio de pago de origen.
        :param medio_acreditacion_id: ID o instancia de la cuenta de acreditación destino.
        :param cliente: Cliente opcional si se desea forzar una instancia específica.
        :param usuario: Usuario operador/cajero autenticado que formaliza.
        :param observaciones: Notas adicionales para la orden.
        :return: Instancia de Transaction creada en estado PENDIENTE.
        :rtype: transactions.models.Transaction
        :raises django.core.exceptions.ValidationError: Si el token o los parámetros son inválidos.
        """
        # 1. Validar cotización congelada en sesión
        is_valid, frozen_data, msg = QuoteFreezeService.validate_quote_token(request, token)
        if not is_valid or not frozen_data:
            raise ValidationError({'token': msg})

        calc = frozen_data.get('calculation', {})
        if not calc:
            raise ValidationError({'token': 'Los datos de cotización congelada se encuentran corruptos o incompletos.'})

        # 2. Resolver y validar cliente
        resolved_client = cls._resolve_customer(request=request, cliente=cliente)

        # 3. Validar instrumentos de pago y acreditación
        medio_pago, medio_acreditacion = cls._validate_payment_and_receiving_methods(
            cliente=resolved_client,
            medio_pago_id=medio_pago_id,
            medio_acreditacion_id=medio_acreditacion_id,
        )

        # 4. Obtener modelos de Moneda
        base_code = calc['base_currency']['code']
        target_code = calc['target_currency']['code']

        base_curr = Currency.objects.filter(code=base_code, is_active=True).first()
        target_curr = Currency.objects.filter(code=target_code, is_active=True).first()

        if not base_curr or not target_curr:
            raise ValidationError({'currency': 'Una de las divisas involucradas ya no se encuentra activa en el sistema.'})

        # 5. Re-validar límites operativos para el cliente y monto base
        base_amount = Decimal(str(calc['base_amount']))
        OperationLimitValidationService.validate_operation_amount(
            segment_or_customer=resolved_client,
            currency=base_curr,
            amount=base_amount,
            cliente=resolved_client,
            raise_exception=True,
        )

        # 6. Mapear montos de origen y destino según tipo de operación
        op_type_str = str(calc['operation_type']).upper().strip()
        tipo_op = Transaction.TipoOperacion.COMPRA if op_type_str == 'BUY' else Transaction.TipoOperacion.VENTA

        official_rate = Decimal(str(calc['official_rate']))
        total_commission = Decimal(str(calc['total_commission']))
        net_rate = Decimal(str(calc['final_effective_rate']))
        net_target_amount = Decimal(str(calc['net_target_amount']))

        if tipo_op == Transaction.TipoOperacion.VENTA:
            # VENTA: Cliente entrega base currency (monto_origen), recibe target currency (monto_destino)
            monto_origen = base_amount
            monto_destino = net_target_amount
        else:
            # COMPRA: Cliente entrega target currency (monto_origen), recibe base currency (monto_destino)
            monto_origen = net_target_amount
            monto_destino = base_amount

        exchange_rate_obj = None
        ex_id = calc.get('exchange_rate_id')
        if ex_id:
            exchange_rate_obj = ExchangeRate.objects.filter(id=ex_id).first()

        operator_user = usuario
        if not operator_user and request and hasattr(request, 'user') and request.user.is_authenticated:
            operator_user = request.user

        # 7. Operación atómica en BD y descongelamiento de sesión
        with transaction.atomic():
            tx = Transaction(
                cliente=resolved_client,
                tipo_operacion=tipo_op,
                base_currency=base_curr,
                target_currency=target_curr,
                exchange_rate=exchange_rate_obj,
                tasa_base=official_rate,
                comision_segmento=total_commission,
                tasa_neta=net_rate,
                monto_origen=monto_origen,
                monto_destino=monto_destino,
                medio_pago_origen=medio_pago,
                medio_acreditacion_destino=medio_acreditacion,
                estado=Transaction.Estado.PENDIENTE,
                token_congelamiento=token,
                usuario=operator_user,
                observaciones=observaciones.strip(),
            )
            tx.save()

            # Eliminar la cotización congelada de la sesión para evitar reutilización del token
            QuoteFreezeService.unfreeze_quote(request, token=token)

            logger.info(
                f"Transacción congelada creada exitosamente: {tx.codigo_referencia} "
                f"para cliente {resolved_client.id} (Token: {token})"
            )
            return tx

    @classmethod
    def create_order_from_live_quote(
        cls,
        request: Optional[HttpRequest],
        base_currency_code: str,
        target_currency_code: str,
        amount: Union[Decimal, float, int, str],
        operation_type: str,
        is_source_base: bool,
        medio_pago_id: Union[int, str, PaymentMethod],
        medio_acreditacion_id: Union[int, str, ReceivingMethod],
        cliente: Optional[Cliente] = None,
        usuario: Any = None,
        observaciones: str = '',
    ) -> Transaction:
        """
        Crea y formaliza una transacción en estado PENDIENTE utilizando una cotización calculada en vivo.

        :param request: Solicitud HTTP opcional.
        :param base_currency_code: Código de moneda base (ej. 'USD').
        :param target_currency_code: Código de moneda objetivo (ej. 'PYG').
        :param amount: Monto ingresado por el usuario.
        :param operation_type: 'BUY' o 'SELL' (o 'COMPRA' / 'VENTA').
        :param is_source_base: True si el monto ingresado está en divisa base.
        :param medio_pago_id: ID del medio de pago de origen.
        :param medio_acreditacion_id: ID de la cuenta de acreditación destino.
        :param cliente: Instancia explícita de Cliente (opcional).
        :param usuario: Usuario operador/cajero.
        :param observaciones: Comentarios adicionales.
        :return: Instancia de Transaction creada en estado PENDIENTE.
        :rtype: transactions.models.Transaction
        """
        resolved_client = cls._resolve_customer(request=request, cliente=cliente)

        medio_pago, medio_acreditacion = cls._validate_payment_and_receiving_methods(
            cliente=resolved_client,
            medio_pago_id=medio_pago_id,
            medio_acreditacion_id=medio_acreditacion_id,
        )

        op_type_norm = str(operation_type).upper().strip()
        if op_type_norm in ('COMPRA', 'BUY'):
            op_calc = 'BUY'
            tipo_op = Transaction.TipoOperacion.COMPRA
        elif op_type_norm in ('VENTA', 'SELL'):
            op_calc = 'SELL'
            tipo_op = Transaction.TipoOperacion.VENTA
        else:
            raise ValidationError({'operation_type': "Tipo de operación no válido (debe ser COMPRA o VENTA)."})

        # Calcular cotización en vivo con validación de límites
        calc = RateCalculationService.calculate_quotation_by_codes(
            base_currency_code=base_currency_code,
            target_currency_code=target_currency_code,
            segment_or_customer=resolved_client,
            amount=amount,
            operation_type=op_calc,
            is_source_base=is_source_base,
        )

        base_curr = Currency.objects.filter(code=base_currency_code.upper().strip(), is_active=True).first()
        target_curr = Currency.objects.filter(code=target_currency_code.upper().strip(), is_active=True).first()

        if not base_curr or not target_curr:
            raise ValidationError({'currency': 'Moneda base o destino no encontrada o inactiva.'})

        base_amount = Decimal(str(calc['base_amount']))
        OperationLimitValidationService.validate_operation_amount(
            segment_or_customer=resolved_client,
            currency=base_curr,
            amount=base_amount,
            cliente=resolved_client,
            raise_exception=True,
        )

        official_rate = Decimal(str(calc['official_rate']))
        total_commission = Decimal(str(calc['total_commission']))
        net_rate = Decimal(str(calc['final_effective_rate']))
        net_target_amount = Decimal(str(calc['net_target_amount']))

        if tipo_op == Transaction.TipoOperacion.VENTA:
            monto_origen = base_amount
            monto_destino = net_target_amount
        else:
            monto_origen = net_target_amount
            monto_destino = base_amount

        exchange_rate_obj = None
        ex_id = calc.get('exchange_rate_id')
        if ex_id:
            exchange_rate_obj = ExchangeRate.objects.filter(id=ex_id).first()

        operator_user = usuario
        if not operator_user and request and hasattr(request, 'user') and request.user.is_authenticated:
            operator_user = request.user

        with transaction.atomic():
            tx = Transaction(
                cliente=resolved_client,
                tipo_operacion=tipo_op,
                base_currency=base_curr,
                target_currency=target_curr,
                exchange_rate=exchange_rate_obj,
                tasa_base=official_rate,
                comision_segmento=total_commission,
                tasa_neta=net_rate,
                monto_origen=monto_origen,
                monto_destino=monto_destino,
                medio_pago_origen=medio_pago,
                medio_acreditacion_destino=medio_acreditacion,
                estado=Transaction.Estado.PENDIENTE,
                usuario=operator_user,
                observaciones=observaciones.strip(),
            )
            tx.save()

            logger.info(
                f"Transacción en vivo creada exitosamente: {tx.codigo_referencia} "
                f"para cliente {resolved_client.id}"
            )
            return tx
