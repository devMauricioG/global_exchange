"""
Módulo de servicios transaccionales para operaciones cambiarias (transactions).

Provee la lógica de negocio atómica (:class:`TransactionService`) para formalizar
órdenes de compra y venta de divisas en estado PENDIENTE, validando la vigencia
de cotizaciones congeladas en sesión o cotizaciones en vivo, comprobando límites
operativos y asociando los instrumentos de pago y acreditación del cliente.
"""

from datetime import timedelta
from decimal import Decimal
import logging
from typing import Any, Dict, Optional, Union

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

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

    EXPIRATION_DURATION_SECONDS = 300  # 5 minutos

    @classmethod
    def is_transaction_expired(cls, tx: Transaction) -> bool:
        """
        Determina si una transacción en estado PENDIENTE ha expirado.

        Una transacción expira si se encuentra en estado PENDIENTE y han transcurrido
        más de 5 minutos (300 segundos) desde su fecha de creación (created_at).

        :param tx: Instancia de Transaction a evaluar.
        :type tx: transactions.models.Transaction
        :return: True si ha expirado, False en caso contrario.
        :rtype: bool
        """
        if not tx or tx.estado != Transaction.Estado.PENDIENTE:
            return False

        now = timezone.now()
        elapsed_seconds = (now - tx.created_at).total_seconds()
        return elapsed_seconds >= cls.EXPIRATION_DURATION_SECONDS

    @classmethod
    def check_and_cancel_single(cls, tx: Transaction) -> bool:
        """
        Evalúa si una transacción individual ha expirado y la transiciona a CANCELADA en BD.

        :param tx: Instancia de Transaction.
        :type tx: transactions.models.Transaction
        :return: True si la orden fue cancelada por expiración, False si sigue vigente o completada.
        :rtype: bool
        """
        if cls.is_transaction_expired(tx):
            motivo_expiracion = (
                f"[Expiración Automática] Cotización congelada vencida "
                f"(límite de {cls.EXPIRATION_DURATION_SECONDS // 60} minutos excedido sin confirmación de pago)."
            )
            tx.mark_as_cancelled(motivo=motivo_expiracion)
            logger.info(f"Transacción {tx.codigo_referencia} cancelada automáticamente por expiración.")
            return True
        return False

    @classmethod
    def cancel_expired_transactions(cls) -> int:
        """
        Consulta y cancela de manera atómica en lote todas las transacciones PENDIENTES
        cuya fecha de creación haya superado el tiempo límite de 5 minutos.

        :return: Cantidad total de transacciones canceladas en el proceso.
        :rtype: int
        """
        now = timezone.now()
        cutoff_time = now - timedelta(seconds=cls.EXPIRATION_DURATION_SECONDS)

        pending_expired_qs = Transaction.objects.filter(
            estado=Transaction.Estado.PENDIENTE,
            created_at__lte=cutoff_time,
        )

        count = 0
        with transaction.atomic():
            for tx in pending_expired_qs:
                if cls.check_and_cancel_single(tx):
                    count += 1

        if count > 0:
            logger.info(f"Se cancelaron automáticamente {count} transacciones expiradas por tiempo de cotización.")
        return count

    @classmethod
    def cancel_transaction_by_customer(
        cls,
        transaction_id: Union[int, str],
        cliente: Cliente,
        usuario: Any = None,
        motivo: str = '',
    ) -> Transaction:
        """
        Ejecuta la anulación manual de una transacción pendiente por solicitud del cliente.

        :param transaction_id: Identificador de la transacción.
        :param cliente: Cliente titular autenticado (para verificación de permisos IDOR).
        :param usuario: Usuario operador/cliente que solicita la anulación.
        :param motivo: Motivo explicativo opcional ingresado por el usuario.
        :return: Instancia de Transaction actualizada en estado CANCELADA.
        :rtype: transactions.models.Transaction
        :raises django.core.exceptions.ValidationError: Si la orden no existe, no pertenece al cliente o no está PENDIENTE.
        """
        try:
            tx = Transaction.objects.select_related('cliente').get(id=int(transaction_id))
        except (Transaction.DoesNotExist, ValueError, TypeError):
            raise ValidationError({'transaction': 'La transacción solicitada no fue encontrada.'})

        # Control de seguridad IDOR: verificar pertenencia del cliente
        if tx.cliente_id != cliente.id:
            raise ValidationError({
                'cliente': 'No tenés permisos para cancelar esta transacción ya que no pertenece a tu ficha de cliente.'
            })

        # Verificar si ya había expirado automáticamente
        if cls.check_and_cancel_single(tx):
            raise ValidationError({
                'estado': 'La cotización de esta orden ha expirado (límite de 5 min) y la transacción fue cancelada automáticamente.'
            })

        if tx.estado != Transaction.Estado.PENDIENTE:
            raise ValidationError({
                'estado': f'La transacción se encuentra en estado "{tx.get_estado_display()}" y no puede ser anulada.'
            })

        motivo_final = motivo.strip() or "Anulación manual realizada por el cliente titular."
        if usuario and hasattr(usuario, 'username'):
            motivo_final = f"{motivo_final} (Solicitado por: {usuario.username})"

        with transaction.atomic():
            tx.mark_as_cancelled(motivo=motivo_final)
            logger.info(f"Transacción {tx.codigo_referencia} anulada manualmente por cliente {cliente.id}.")
            return tx

    # ==========================================================================
    # ORQUESTACIÓN DE PAGO Y LIQUIDACIÓN (SCRUM-94 / SCRUM-87)
    # ==========================================================================

    @classmethod
    def process_payment_confirmation(
        cls,
        transaction_obj: Union[int, str, Transaction],
        gateway: str,
        referencia_externa: str,
        monto_pagado: Union[Decimal, float, int, str],
        moneda_pagada: str,
        datos_adicionales: Optional[Dict[str, Any]] = None,
        usuario_operador: Optional[Any] = None,
        fecha_pago: Optional[Any] = None,
    ) -> Transaction:
        """
        Orquesta y procesa la confirmación atómica de pago y liquidación de una orden cambiaria (SCRUM-94 / SCRUM-87).

        Ejecuta las validaciones de consistencia financiera e integridad:
        - Resuelve la orden cambiaria asegurando su existencia.
        - **Idempotencia estricta**: si la orden ya se encuentra COMPLETADA con la misma referencia de pago,
          retorna la transacción sin duplicar asientos contables ni alterar estados.
        - Valida que la transacción no haya sido cancelada previamente ni se encuentre en un estado terminal inválido.
        - Comprueba que el monto pagado coincida de manera exacta con el `monto_origen` de la orden.
        - Comprueba que la divisa informada coincida exactamente con la `moneda_origen` de la orden.
        - Transiciona atómicamente la orden cambiaria de PENDIENTE a COMPLETADA registrando `fecha_pago`,
          `referencia_externa_pago`, `pasarela_pago`, notas de auditoría, y actualiza los registros
          asociados de pasarela (:class:`payments.models.PaymentGatewayRecord`) a COMPLETADO.

        :param transaction_obj: ID numérico o instancia de :class:`~transactions.models.Transaction`.
        :type transaction_obj: int or str or transactions.models.Transaction
        :param gateway: Pasarela o medio tecnológico utilizado (ej. 'STRIPE', 'SIPAP', 'EFECTIVO').
        :type gateway: str
        :param referencia_externa: Identificador devuelto por la pasarela o comprobante interbancario.
        :type referencia_externa: str
        :param monto_pagado: Monto exacto cobrado o transferido.
        :type monto_pagado: decimal.Decimal or float or int or str
        :param moneda_pagada: Código ISO de la divisa del pago (ej. 'USD', 'PYG').
        :type moneda_pagada: str
        :param datos_adicionales: Metadatos adicionales de la liquidación (opcional).
        :type datos_adicionales: dict or None
        :param usuario_operador: Usuario operador o cajero que formalizó la liquidación (opcional).
        :type usuario_operador: Any or None
        :param fecha_pago: Marca temporal informada del pago (opcional).
        :type fecha_pago: datetime.datetime or None
        :return: Instancia de Transaction liquidada en estado COMPLETADA.
        :rtype: transactions.models.Transaction
        :raises django.core.exceptions.ValidationError: Ante discrepancias en montos, monedas o estados incompatibles.
        """
        if isinstance(transaction_obj, Transaction):
            tx = transaction_obj
        else:
            try:
                tx = Transaction.objects.select_related('cliente', 'base_currency', 'target_currency').get(id=int(transaction_obj))
            except (Transaction.DoesNotExist, ValueError, TypeError):
                raise ValidationError({'transaction': f'No se encontró la transacción cambiaria especificada: {transaction_obj}.'})

        ref = (referencia_externa or '').strip()
        if not ref:
            raise ValidationError({'referencia_externa': 'Debe suministrarse una referencia externa válida para liquidar el pago.'})

        gateway_str = (gateway or 'PASARELA').strip().upper()

        # 1. Idempotencia estricta
        if tx.estado == Transaction.Estado.COMPLETADA:
            if tx.referencia_externa_pago == ref or not tx.referencia_externa_pago:
                logger.info('Transacción %s ya fue completada previamente con referencia %s. Omitiendo duplicado.', tx.codigo_referencia, ref)
                return tx
            raise ValidationError({
                'estado': f'La transacción {tx.codigo_referencia} ya fue completada con una referencia de pago diferente ({tx.referencia_externa_pago}).'
            })

        # 2. Control de estado previo
        if tx.estado == Transaction.Estado.CANCELADA:
            raise ValidationError({
                'estado': f'No es posible confirmar el pago de la transacción {tx.codigo_referencia} porque se encuentra CANCELADA.'
            })

        if tx.estado != Transaction.Estado.PENDIENTE:
            raise ValidationError({
                'estado': f'La transacción {tx.codigo_referencia} se encuentra en estado "{tx.get_estado_display()}" y no admite confirmación de pago.'
            })

        # 3. Validación de integridad del monto
        try:
            amount_decimal = Decimal(str(monto_pagado))
        except Exception:
            raise ValidationError({'monto': 'El monto informado para la confirmación de pago no es un número válido.'})

        if amount_decimal <= Decimal('0.00'):
            raise ValidationError({'monto': 'El monto de pago debe ser mayor a cero.'})

        expected_amount = tx.monto_origen
        if amount_decimal != expected_amount:
            raise ValidationError({
                'monto': f'Discrepancia en el monto de pago: la transacción requiere {expected_amount} pero se informó un pago de {amount_decimal}.'
            })

        # 4. Validación de divisa
        currency_code = (moneda_pagada or '').strip().upper()
        expected_currency = getattr(tx.moneda_origen, 'code', 'PYG').upper() if hasattr(tx, 'moneda_origen') else 'PYG'
        if currency_code != expected_currency:
            raise ValidationError({
                'moneda': f'Discrepancia en la divisa: la transacción espera cobrar en {expected_currency} pero el pago se recibió en {currency_code}.'
            })

        # 5. Transición atómica a COMPLETADA
        payment_time = fecha_pago or timezone.now()
        display_gateway = 'Stripe' if gateway_str == 'STRIPE' else ('SIPAP' if gateway_str == 'SIPAP' else gateway_str)
        note = f'Pago liquidado exitosamente vía {display_gateway} [Ref: {ref}].'
        if datos_adicionales:
            detalles = ', '.join(f'{k}={v}' for k, v in datos_adicionales.items() if v)
            if detalles:
                note = f'{note} ({detalles})'

        with transaction.atomic():
            if tx.observaciones:
                tx.observaciones = f'{tx.observaciones}\n{note}'
            else:
                tx.observaciones = note

            tx.mark_as_completed(
                user=usuario_operador,
                fecha_pago=payment_time,
                referencia_externa=ref,
                pasarela=gateway_str,
                save=True,
            )

            # Sincronizar PaymentGatewayRecord si existe
            try:
                from payments.models import PaymentGatewayRecord
                PaymentGatewayRecord.objects.filter(
                    gateway=gateway_str,
                    referencia_externa=ref,
                ).update(
                    transaction=tx,
                    cliente=tx.cliente,
                    estado=PaymentGatewayRecord.Estado.COMPLETADO,
                )
            except Exception as exc:
                logger.warning('No se pudo actualizar PaymentGatewayRecord para ref %s: %s', ref, str(exc))

            logger.info('Transacción %s liquidada y completada exitosamente vía %s [%s].', tx.codigo_referencia, gateway_str, ref)
            return tx

    @classmethod
    def confirm_stripe_payment(
        cls,
        transaction_obj: Union[int, str, Transaction],
        payment_reference: str,
        monto: Union[Decimal, float, int, str],
        moneda: str = 'USD',
        metadata: Optional[Dict[str, Any]] = None,
        usuario_operador: Optional[Any] = None,
        fecha_pago: Optional[Any] = None,
    ) -> Transaction:
        """
        Método de conveniencia para orquestar la confirmación de cobros recibidos vía Stripe.
        """
        return cls.process_payment_confirmation(
            transaction_obj=transaction_obj,
            gateway='STRIPE',
            referencia_externa=payment_reference,
            monto_pagado=monto,
            moneda_pagada=moneda,
            datos_adicionales=metadata,
            usuario_operador=usuario_operador,
            fecha_pago=fecha_pago,
        )

    @classmethod
    def confirm_sipap_payment(
        cls,
        transaction_obj: Union[int, str, Transaction],
        codigo_transferencia: str,
        monto: Union[Decimal, float, int, str],
        moneda: str = 'PYG',
        banco_origen: Optional[str] = None,
        cuenta_origen: Optional[str] = None,
        titular_origen: Optional[str] = None,
        usuario_operador: Optional[Any] = None,
        fecha_pago: Optional[Any] = None,
    ) -> Transaction:
        """
        Método de conveniencia para orquestar la confirmación de transferencias locales SIPAP.
        """
        datos = {}
        if banco_origen:
            datos['banco_origen'] = banco_origen
        if cuenta_origen:
            datos['cuenta_origen'] = cuenta_origen
        if titular_origen:
            datos['titular_origen'] = titular_origen

        return cls.process_payment_confirmation(
            transaction_obj=transaction_obj,
            gateway='SIPAP',
            referencia_externa=codigo_transferencia,
            monto_pagado=monto,
            moneda_pagada=moneda,
            datos_adicionales=datos,
            usuario_operador=usuario_operador,
            fecha_pago=fecha_pago,
        )

    @classmethod
    def reject_payment_and_cancel(
        cls,
        transaction_obj: Union[int, str, Transaction],
        gateway: str,
        referencia_externa: str,
        motivo: str = 'Pago rechazado por la pasarela de pagos.',
        usuario_operador: Optional[Any] = None,
    ) -> Transaction:
        """
        Transiciona atómicamente la orden cambiaria a CANCELADA ante un rechazo de pago en pasarela (SCRUM-87 / SCRUM-94).
        """
        if isinstance(transaction_obj, Transaction):
            tx = transaction_obj
        else:
            try:
                tx = Transaction.objects.get(id=int(transaction_obj))
            except (Transaction.DoesNotExist, ValueError, TypeError):
                raise ValidationError({'transaction': 'La transacción solicitada no existe.'})

        if tx.estado == Transaction.Estado.COMPLETADA:
            raise ValidationError({'estado': 'No es posible cancelar una transacción que ya fue COMPLETADA.'})

        gateway_str = (gateway or 'PASARELA').strip().upper()
        ref = (referencia_externa or '').strip()

        if tx.estado == Transaction.Estado.PENDIENTE:
            with transaction.atomic():
                motivo_cancel = f"[Rechazo de Pago - {gateway_str}] Transacción cancelada: transferencia {gateway_str} rechazada [{motivo}]. Ref: {ref}"
                tx.mark_as_cancelled(motivo=motivo_cancel)
                if usuario_operador:
                    tx.usuario = usuario_operador
                    tx.save(update_fields=['usuario', 'updated_at'])

                try:
                    from payments.models import PaymentGatewayRecord
                    PaymentGatewayRecord.objects.filter(
                        gateway=gateway_str,
                        referencia_externa=ref,
                    ).update(
                        estado=PaymentGatewayRecord.Estado.FALLIDO,
                        error_mensaje=motivo,
                    )
                except Exception as exc:
                    logger.warning('No se pudo actualizar PaymentGatewayRecord a FALLIDO: %s', str(exc))

                logger.info('Transacción %s cancelada debido a rechazo de pago en %s [%s].', tx.codigo_referencia, gateway_str, ref)

        return tx
