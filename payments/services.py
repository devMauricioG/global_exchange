"""
Módulo de servicios de pasarelas de pago externas (payments.services).

Implementa :class:`StripeService` para la integración segura con Stripe:
- Creación de sesiones alojadas de Stripe Checkout.
- Creación de PaymentIntents para cobros directos con tarjetas.
- Verificación criptográfica de signaturas HMAC-SHA256 en webhooks de Stripe.
- Procesamiento idempotente de eventos de webhook con persistencia transaccional.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, Optional, Union
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
import stripe

from .models import PaymentGatewayRecord, PaymentWebhookEvent, SipapTransferRecord

logger = logging.getLogger(__name__)

# Monedas de cero decimales reconocidas por Stripe (ej. Guaraní paraguayo)
ZERO_DECIMAL_CURRENCIES = {
    'BIF', 'CLP', 'DJF', 'GNF', 'JPY', 'KMF', 'KRW', 'MGA',
    'PYG', 'RWF', 'UGX', 'VND', 'VUV', 'XAF', 'XOF', 'XPF',
}


class StripeService:
    """
    Servicio de integración con la pasarela de pagos Stripe (SCRUM-92 / SCRUM-87).

    Gestiona el ciclo de vida de cobros mediante tarjeta de crédito/débito internacional,
    orquestando la creación de sesiones de Checkout, PaymentIntents, verificación de
    firmas en webhooks y actualización idempotente del estado de las órdenes cambiarias.
    """

    @classmethod
    def get_api_key(cls) -> str:
        """
        Obtiene la clave secreta de la API de Stripe configurada en settings.

        :return: Clave secreta (ej. 'sk_test_...').
        :rtype: str
        """
        key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        if not key:
            raise ValidationError('No se ha configurado STRIPE_SECRET_KEY en los ajustes del sistema.')
        return key

    @classmethod
    def get_webhook_secret(cls) -> str:
        """
        Obtiene la clave secreta del Webhook de Stripe configurada en settings.

        :return: Secreto de webhook (ej. 'whsec_...').
        :rtype: str
        """
        secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        if not secret:
            raise ValidationError('No se ha configurado STRIPE_WEBHOOK_SECRET en los ajustes del sistema.')
        return secret

    @classmethod
    def to_stripe_amount(cls, amount: Union[Decimal, float, int], currency_code: str) -> int:
        """
        Convierte un monto decimal al formato requerido por Stripe (enteros/centavos).

        Si la moneda es de cero decimales (ej. PYG), el valor se redondea directamente a entero.
        Para monedas con decimales estándar (ej. USD, EUR), se multiplica por 100.

        :param amount: Monto de la operación.
        :type amount: decimal.Decimal or float or int
        :param currency_code: Código ISO de la moneda (ej. 'USD', 'PYG').
        :type currency_code: str
        :return: Monto en centavos o unidades mínimas.
        :rtype: int
        """
        dec_amount = Decimal(str(amount))
        code = (currency_code or 'USD').upper()
        if code in ZERO_DECIMAL_CURRENCIES:
            return int(round(dec_amount))
        return int(round(dec_amount * Decimal('100')))

    @classmethod
    def from_stripe_amount(cls, stripe_amount: int, currency_code: str) -> Decimal:
        """
        Convierte el monto en centavos/enteros de Stripe a un objeto Decimal legible.

        :param stripe_amount: Monto devuelto por Stripe.
        :type stripe_amount: int
        :param currency_code: Código ISO de la moneda.
        :type currency_code: str
        :return: Monto en unidades monetarias estándar.
        :rtype: decimal.Decimal
        """
        code = (currency_code or 'USD').upper()
        if code in ZERO_DECIMAL_CURRENCIES:
            return Decimal(stripe_amount)
        return Decimal(stripe_amount) / Decimal('100')

    @classmethod
    def create_checkout_session(
        cls,
        transaction_obj: Any,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        customer_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Genera una sesión de Stripe Checkout alojada para una transacción cambiaria.

        Crea el registro :class:`~payments.models.PaymentGatewayRecord` en estado PENDIENTE
        asociado a la transacción y retorna los detalles de la sesión creada (ID y URL).

        :param transaction_obj: Instancia de :class:`transactions.models.Transaction`.
        :type transaction_obj: transactions.models.Transaction
        :param success_url: URL de retorno exitoso (admite placeholder {CHECKOUT_SESSION_ID}).
        :type success_url: str or None
        :param cancel_url: URL de retorno en caso de cancelación por parte del usuario.
        :type cancel_url: str or None
        :param customer_email: Correo electrónico del cliente para prellenado en Stripe.
        :type customer_email: str or None
        :param metadata: Metadatos adicionales para adjuntar a la sesión en Stripe.
        :type metadata: dict or None
        :return: Diccionario con session_id, checkout_url, record_id y estado.
        :rtype: dict
        """
        stripe.api_key = cls.get_api_key()

        # Determinar monto y moneda a cobrar
        # En compras de divisas, el cliente entrega monto_origen en la moneda de pago
        currency_code = getattr(transaction_obj.moneda_origen, 'code', 'USD') if hasattr(transaction_obj, 'moneda_origen') else 'USD'
        amount = getattr(transaction_obj, 'monto_origen', Decimal('0.00'))
        if amount <= Decimal('0.00'):
            raise ValidationError('El monto a cobrar a través de Stripe debe ser mayor a cero.')

        stripe_amount = cls.to_stripe_amount(amount, currency_code)
        ref_code = getattr(transaction_obj, 'codigo_referencia', '') or f'TX-{uuid.uuid4().hex[:8].upper()}'
        cliente = getattr(transaction_obj, 'cliente', None)

        # Preparar metadatos de conciliación
        session_metadata: Dict[str, str] = {
            'transaction_id': str(getattr(transaction_obj, 'id', '')),
            'codigo_referencia': str(ref_code),
            'cliente_id': str(getattr(cliente, 'id', '')),
            'gateway': PaymentGatewayRecord.Gateway.STRIPE,
        }
        if metadata:
            session_metadata.update({str(k): str(v) for k, v in metadata.items()})

        # URLs por defecto si no son provistas
        default_success = success_url or f'/transactions/{getattr(transaction_obj, "id", "")}/?checkout=success&session_id={{CHECKOUT_SESSION_ID}}'
        default_cancel = cancel_url or f'/transactions/{getattr(transaction_obj, "id", "")}/?checkout=cancel'

        session_params: Dict[str, Any] = {
            'payment_method_types': ['card'],
            'mode': 'payment',
            'client_reference_id': str(ref_code),
            'success_url': default_success,
            'cancel_url': default_cancel,
            'metadata': session_metadata,
            'line_items': [{
                'price_data': {
                    'currency': currency_code.lower(),
                    'unit_amount': stripe_amount,
                    'product_data': {
                        'name': f'Orden Cambiaria {ref_code}',
                        'description': f'Operación {getattr(transaction_obj, "get_tipo_operacion_display", lambda: "Cambio")()} en Global Exchange',
                    },
                },
                'quantity': 1,
            }],
        }

        # Correo del cliente si está disponible
        email = customer_email or getattr(cliente, 'correo', None)
        if email:
            session_params['customer_email'] = email

        try:
            session = stripe.checkout.Session.create(**session_params)
        except stripe.StripeError as e:
            logger.error('Error al invocar API de Stripe Checkout: %s', str(e), exc_info=True)
            raise ValidationError(f'Error al generar la sesión de pago en Stripe: {getattr(e, "user_message", str(e))}')

        # Persistir el registro de pasarela en base de datos
        with transaction.atomic():
            record = PaymentGatewayRecord.objects.create(
                cliente=cliente,
                transaction=transaction_obj if getattr(transaction_obj, 'id', None) else None,
                gateway=PaymentGatewayRecord.Gateway.STRIPE,
                session_id=session.id,
                payment_intent_id=getattr(session, 'payment_intent', None),
                monto=amount,
                moneda=currency_code.upper(),
                estado=PaymentGatewayRecord.Estado.PENDIENTE,
                checkout_url=session.url,
                referencia_externa=ref_code,
                datos_evento={
                    'session_id': session.id,
                    'status': getattr(session, 'status', 'open'),
                },
            )

        return {
            'session_id': session.id,
            'checkout_url': session.url,
            'record_id': record.id,
            'status': getattr(session, 'status', 'open'),
            'monto': amount,
            'moneda': currency_code.upper(),
        }

    @classmethod
    def create_payment_intent(
        cls,
        transaction_obj: Any,
        payment_method_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """
        Crea un PaymentIntent directo en Stripe para cobro con tarjeta o elementos personalizados.

        :param transaction_obj: Transacción asociada.
        :type transaction_obj: transactions.models.Transaction
        :param payment_method_id: Identificador de instrumento de pago guardado en Stripe (opcional).
        :type payment_method_id: str or None
        :param metadata: Metadatos adicionales.
        :type metadata: dict or None
        :param confirm: Confirma el intento de pago de forma inmediata si se provee el método.
        :type confirm: bool
        :return: Diccionario con payment_intent_id, client_secret, status y record_id.
        :rtype: dict
        """
        stripe.api_key = cls.get_api_key()

        currency_code = getattr(transaction_obj.moneda_origen, 'code', 'USD') if hasattr(transaction_obj, 'moneda_origen') else 'USD'
        amount = getattr(transaction_obj, 'monto_origen', Decimal('0.00'))
        if amount <= Decimal('0.00'):
            raise ValidationError('El monto a cobrar en Stripe debe ser mayor a cero.')

        stripe_amount = cls.to_stripe_amount(amount, currency_code)
        ref_code = getattr(transaction_obj, 'codigo_referencia', '') or f'TX-{uuid.uuid4().hex[:8].upper()}'
        cliente = getattr(transaction_obj, 'cliente', None)

        intent_metadata: Dict[str, str] = {
            'transaction_id': str(getattr(transaction_obj, 'id', '')),
            'codigo_referencia': str(ref_code),
            'cliente_id': str(getattr(cliente, 'id', '')),
            'gateway': PaymentGatewayRecord.Gateway.STRIPE,
        }
        if metadata:
            intent_metadata.update({str(k): str(v) for k, v in metadata.items()})

        intent_params: Dict[str, Any] = {
            'amount': stripe_amount,
            'currency': currency_code.lower(),
            'metadata': intent_metadata,
            'description': f'Pago orden cambiaria {ref_code}',
        }
        if payment_method_id:
            intent_params['payment_method'] = payment_method_id
            if confirm:
                intent_params['confirm'] = True
                intent_params['automatic_payment_methods'] = {'enabled': True, 'allow_redirects': 'never'}

        try:
            intent = stripe.PaymentIntent.create(**intent_params)
        except stripe.StripeError as e:
            logger.error('Error al crear PaymentIntent en Stripe: %s', str(e), exc_info=True)
            raise ValidationError(f'Error al crear el intento de pago en Stripe: {str(e)}')

        with transaction.atomic():
            record = PaymentGatewayRecord.objects.create(
                cliente=cliente,
                transaction=transaction_obj if getattr(transaction_obj, 'id', None) else None,
                gateway=PaymentGatewayRecord.Gateway.STRIPE,
                payment_intent_id=intent.id,
                monto=amount,
                moneda=currency_code.upper(),
                estado=PaymentGatewayRecord.Estado.PENDIENTE,
                referencia_externa=ref_code,
                datos_evento={
                    'payment_intent_id': intent.id,
                    'status': getattr(intent, 'status', 'requires_payment_method'),
                },
            )

        return {
            'payment_intent_id': intent.id,
            'client_secret': getattr(intent, 'client_secret', None),
            'status': getattr(intent, 'status', 'requires_payment_method'),
            'record_id': record.id,
            'monto': amount,
            'moneda': currency_code.upper(),
        }

    @classmethod
    def verify_webhook_signature(
        cls,
        payload: Union[bytes, str],
        sig_header: str,
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Valida criptográficamente la firma del webhook recibida de Stripe (HMAC-SHA256).

        Verifica que la petición no haya sido alterada en tránsito y provenga legítimamente
        de los servidores de Stripe utilizando el secreto de webhook configurado.

        :param payload: Cuerpo raw de la solicitud HTTP (request.body en bytes o str).
        :type payload: bytes or str
        :param sig_header: Contenido de la cabecera HTTP `Stripe-Signature`.
        :type sig_header: str
        :param secret: Secreto de webhook opcional (usa `STRIPE_WEBHOOK_SECRET` por defecto).
        :type secret: str or None
        :return: Objeto/Diccionario del evento decodificado y autenticado.
        :rtype: dict
        :raises ValidationError: Si la firma o el formato de la carga útil son inválidos.
        """
        if not sig_header:
            raise ValidationError('Cabecera de firma Stripe-Signature ausente en la petición.')

        webhook_secret = secret or cls.get_webhook_secret()
        payload_bytes = payload.encode('utf-8') if isinstance(payload, str) else payload

        try:
            event = stripe.Webhook.construct_event(
                payload=payload_bytes,
                sig_header=sig_header,
                secret=webhook_secret,
            )
            # Retornar dict para manejo uniforme
            if hasattr(event, 'to_dict'):
                return event.to_dict()
            return dict(event)
        except ValueError as e:
            logger.warning('Payload inválido en webhook de Stripe: %s', str(e))
            raise ValidationError('Cuerpo de la petición del webhook inválido.')
        except stripe.SignatureVerificationError as e:
            logger.warning('Firma criptográfica inválida en webhook de Stripe: %s', str(e))
            raise ValidationError('Firma de webhook de Stripe inválida o expirada.')
        except Exception as e:
            logger.error('Error al verificar firma de webhook de Stripe: %s', str(e), exc_info=True)
            raise ValidationError(f'Error al verificar webhook: {str(e)}')

    @classmethod
    def process_webhook_event(cls, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa de forma idempotente un evento autenticado de webhook de Stripe.

        Reconoce los eventos:
        - `checkout.session.completed`: Pago exitoso mediante formulario Checkout.
        - `payment_intent.succeeded`: Pago exitoso directo.
        - `payment_intent.payment_failed`: Cobro rechazado o fallido.
        - `checkout.session.expired`: Sesión expirada sin pago.

        Garantiza idempotencia absoluta mediante :class:`~payments.models.PaymentWebhookEvent`:
        si el `event_id` ya fue procesado, no vuelve a aplicar cambios en la base de datos.

        :param event_data: Diccionario del evento validado.
        :type event_data: dict
        :return: Resultado del procesamiento con estado, event_id y acción ejecutada.
        :rtype: dict
        """
        event_id = event_data.get('id')
        event_type = event_data.get('type')
        data_object = event_data.get('data', {}).get('object', {})

        if not event_id or not event_type:
            raise ValidationError('El evento recibido no contiene identificador (id) o tipo (type).')

        # Control de idempotencia
        with transaction.atomic():
            webhook_record, created = PaymentWebhookEvent.objects.get_or_create(
                event_id=event_id,
                defaults={
                    'gateway': PaymentWebhookEvent.Gateway.STRIPE if hasattr(PaymentWebhookEvent, 'Gateway') else 'STRIPE',
                    'tipo_evento': event_type,
                    'payload': event_data,
                    'procesado': False,
                },
            )
            if not created and webhook_record.procesado:
                logger.info('Evento de Stripe %s ya procesado previamente. Omitiendo duplicado.', event_id)
                return {
                    'status': 'already_processed',
                    'event_id': event_id,
                    'event_type': event_type,
                    'message': 'El evento ya fue procesado con anterioridad.',
                }

        action_taken = 'unhandled_event'
        error_msg = ''

        try:
            with transaction.atomic():
                if event_type == 'checkout.session.completed':
                    action_taken = cls._handle_checkout_completed(data_object)
                elif event_type == 'payment_intent.succeeded':
                    action_taken = cls._handle_payment_intent_succeeded(data_object)
                elif event_type == 'payment_intent.payment_failed':
                    action_taken = cls._handle_payment_intent_failed(data_object)
                elif event_type == 'checkout.session.expired':
                    action_taken = cls._handle_checkout_expired(data_object)
                else:
                    action_taken = f'ignored_{event_type}'

                # Marcar evento como procesado
                webhook_record.procesado = True
                webhook_record.updated_at = timezone.now()
                webhook_record.save(update_fields=['procesado', 'updated_at'])

        except Exception as e:
            error_msg = str(e)
            logger.error('Error al procesar webhook de Stripe %s (%s): %s', event_id, event_type, error_msg, exc_info=True)
            webhook_record.error_mensaje = error_msg
            webhook_record.save(update_fields=['error_mensaje', 'updated_at'])
            raise

        return {
            'status': 'success',
            'event_id': event_id,
            'event_type': event_type,
            'action': action_taken,
        }

    @classmethod
    def _handle_checkout_completed(cls, session_data: Dict[str, Any]) -> str:
        """
        Gestiona la finalización exitosa de una sesión de Checkout.
        """
        session_id = session_data.get('id')
        payment_intent_id = session_data.get('payment_intent')
        metadata = session_data.get('metadata', {})
        transaction_id = metadata.get('transaction_id')
        ref_code = metadata.get('codigo_referencia') or session_data.get('client_reference_id')

        # Buscar registro de pasarela existente
        record = None
        if session_id:
            record = PaymentGatewayRecord.objects.filter(session_id=session_id).first()
        if not record and transaction_id:
            record = PaymentGatewayRecord.objects.filter(transaction_id=transaction_id).first()

        if record:
            record.estado = PaymentGatewayRecord.Estado.COMPLETADO
            if payment_intent_id:
                record.payment_intent_id = payment_intent_id
            record.datos_evento.update({'checkout_completed_at': timezone.now().isoformat(), 'session': session_data})
            record.save(update_fields=['estado', 'payment_intent_id', 'datos_evento', 'updated_at'])

            # Sincronizar estado en Transaction si existe
            if record.transaction:
                cls._mark_transaction_completed(record.transaction, payment_intent_id or session_id)
            return 'checkout_completed_and_transaction_updated'

        # Si no había registro previo, crearlo
        amount_total = session_data.get('amount_total', 0)
        currency = session_data.get('currency', 'usd').upper()
        amount_decimal = cls.from_stripe_amount(amount_total, currency)

        target_trans = None
        if transaction_id:
            from transactions.models import Transaction
            target_trans = Transaction.objects.filter(id=transaction_id).first()

        record = PaymentGatewayRecord.objects.create(
            transaction=target_trans,
            cliente=getattr(target_trans, 'cliente', None),
            gateway=PaymentGatewayRecord.Gateway.STRIPE,
            session_id=session_id,
            payment_intent_id=payment_intent_id,
            monto=amount_decimal,
            moneda=currency,
            estado=PaymentGatewayRecord.Estado.COMPLETADO,
            referencia_externa=ref_code or '',
            datos_evento={'session': session_data},
        )
        if target_trans:
            cls._mark_transaction_completed(target_trans, payment_intent_id or session_id)

        return 'checkout_completed_new_record_created'

    @classmethod
    def _handle_payment_intent_succeeded(cls, intent_data: Dict[str, Any]) -> str:
        """
        Gestiona la acreditación exitosa de un PaymentIntent directo.
        """
        intent_id = intent_data.get('id')
        metadata = intent_data.get('metadata', {})
        transaction_id = metadata.get('transaction_id')
        ref_code = metadata.get('codigo_referencia')

        record = None
        if intent_id:
            record = PaymentGatewayRecord.objects.filter(payment_intent_id=intent_id).first()
        if not record and transaction_id:
            record = PaymentGatewayRecord.objects.filter(transaction_id=transaction_id).first()

        if record:
            record.estado = PaymentGatewayRecord.Estado.COMPLETADO
            record.payment_intent_id = intent_id
            record.datos_evento.update({'intent_succeeded_at': timezone.now().isoformat()})
            record.save(update_fields=['estado', 'payment_intent_id', 'datos_evento', 'updated_at'])
            if record.transaction:
                cls._mark_transaction_completed(record.transaction, intent_id)
            return 'payment_intent_succeeded_updated'

        amount_received = intent_data.get('amount_received', intent_data.get('amount', 0))
        currency = intent_data.get('currency', 'usd').upper()
        amount_decimal = cls.from_stripe_amount(amount_received, currency)

        target_trans = None
        if transaction_id:
            from transactions.models import Transaction
            target_trans = Transaction.objects.filter(id=transaction_id).first()

        PaymentGatewayRecord.objects.create(
            transaction=target_trans,
            cliente=getattr(target_trans, 'cliente', None),
            gateway=PaymentGatewayRecord.Gateway.STRIPE,
            payment_intent_id=intent_id,
            monto=amount_decimal,
            moneda=currency,
            estado=PaymentGatewayRecord.Estado.COMPLETADO,
            referencia_externa=ref_code or '',
            datos_evento={'intent': intent_data},
        )
        if target_trans:
            cls._mark_transaction_completed(target_trans, intent_id)

        return 'payment_intent_succeeded_new_record'

    @classmethod
    def _handle_payment_intent_failed(cls, intent_data: Dict[str, Any]) -> str:
        """
        Gestiona el fallo o rechazo de un intento de pago en Stripe.
        """
        intent_id = intent_data.get('id')
        error = intent_data.get('last_payment_error', {})
        err_msg = error.get('message', 'Pago rechazado por el emisor.')

        record = PaymentGatewayRecord.objects.filter(payment_intent_id=intent_id).first()
        if record:
            record.estado = PaymentGatewayRecord.Estado.FALLIDO
            record.error_mensaje = err_msg
            record.save(update_fields=['estado', 'error_mensaje', 'updated_at'])
            return 'payment_intent_failed_recorded'
        return 'payment_intent_failed_unmatched'

    @classmethod
    def _handle_checkout_expired(cls, session_data: Dict[str, Any]) -> str:
        """
        Gestiona la expiración de una sesión de Stripe Checkout.
        """
        session_id = session_data.get('id')
        record = PaymentGatewayRecord.objects.filter(session_id=session_id).first()
        if record and record.estado == PaymentGatewayRecord.Estado.PENDIENTE:
            record.estado = PaymentGatewayRecord.Estado.CANCELADO
            record.error_mensaje = 'La sesión de pago en Stripe expiró.'
            record.save(update_fields=['estado', 'error_mensaje', 'updated_at'])
            return 'checkout_session_expired_recorded'
        return 'checkout_session_expired_unmatched'

    @classmethod
    def _mark_transaction_completed(cls, transaction_obj: Any, external_reference: Optional[str] = None) -> None:
        """
        Transiciona el estado de la transacción a COMPLETADA de forma segura y atómica delegando en TransactionService (SCRUM-94).
        """
        if not transaction_obj:
            return

        from transactions.services import TransactionService
        if transaction_obj.estado == transaction_obj.Estado.PENDIENTE:
            TransactionService.confirm_stripe_payment(
                transaction_obj=transaction_obj,
                payment_reference=external_reference or transaction_obj.codigo_referencia,
                monto=transaction_obj.monto_origen,
                moneda=getattr(transaction_obj.moneda_origen, 'code', 'USD'),
            )
            logger.info('Transacción %s actualizada a COMPLETADA tras cobro en Stripe vía TransactionService.', transaction_obj.codigo_referencia)


class SipapService:
    """
    Servicio de simulación, validación y confirmación bancaria local SIPAP (SCRUM-93 / SCRUM-87).

    Gestiona la interacción con la red interbancaria nacional (Sistema de Pagos del Paraguay):
    - Generación y simulación de transferencias bancarias para entornos operativos y de prueba.
    - Validación de códigos de comprobante, cuentas de origen/destino y montos de depósitos.
    - Conciliación atómica y automática de depósitos bancarios, actualizando registros de pasarela
      y transicionando el estado de la transacción cambiaria a COMPLETADA.
    - Garantía estricta de idempotencia para impedir duplicaciones de acreditación.
    """

    DEFAULT_BANCO_DESTINO = 'Banco Itaú Paraguay'
    DEFAULT_CUENTA_DESTINO = '900-1234567-01'

    @classmethod
    def generate_transfer_code(cls, prefix: str = 'SIPAP') -> str:
        """
        Genera un código de comprobante interbancario SIPAP con formato SIPAP-YYYYMMDD-XXXXXX.

        :param prefix: Prefijo para el código generado (por defecto 'SIPAP').
        :type prefix: str
        :return: Código único formateado.
        :rtype: str
        """
        now = timezone.now()
        date_str = now.strftime('%Y%m%d')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f'{prefix}-{date_str}-{random_suffix}'

    @classmethod
    def simulate_transfer(
        cls,
        monto: Union[Decimal, float, int, str],
        moneda: str = 'PYG',
        banco_origen: str = 'Banco Itaú',
        cuenta_origen: str = '12345678',
        titular_origen: str = 'Cliente Remitente',
        documento_origen: str = '1234567-8',
        banco_destino: Optional[str] = None,
        cuenta_destino: Optional[str] = None,
        transaction_obj: Optional[Any] = None,
        codigo_transferencia: Optional[str] = None,
        auto_confirm: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SipapTransferRecord:
        """
        Crea un registro de transferencia bancaria simulada en la red SIPAP.

        :param monto: Monto de la transferencia.
        :type monto: decimal.Decimal or str or float or int
        :param moneda: Código ISO de la divisa (ej. 'PYG', 'USD').
        :type moneda: str
        :param banco_origen: Entidad bancaria o cooperativa remitente.
        :type banco_origen: str
        :param cuenta_origen: Número de cuenta bancaria del remitente.
        :type cuenta_origen: str
        :param titular_origen: Nombre completo o razón social del titular origen.
        :type titular_origen: str
        :param documento_origen: Documento de identidad o RUC del titular remitente.
        :type documento_origen: str
        :param banco_destino: Entidad bancaria recaudadora de la casa de cambio.
        :type banco_destino: str or None
        :param cuenta_destino: Número de cuenta recaudadora receptora.
        :type cuenta_destino: str or None
        :param transaction_obj: Transacción cambiaria vinculada (opcional).
        :type transaction_obj: transactions.models.Transaction or None
        :param codigo_transferencia: Código específico o None para autogenerarlo.
        :type codigo_transferencia: str or None
        :param auto_confirm: Si es True, marca la transferencia inmediatamente como confirmada.
        :type auto_confirm: bool
        :param metadata: Carga útil complementaria de la red bancaria.
        :type metadata: dict or None
        :return: Instancia persistida de :class:`~payments.models.SipapTransferRecord`.
        :rtype: payments.models.SipapTransferRecord
        """
        amount_decimal = Decimal(str(monto))
        if amount_decimal <= Decimal('0.00'):
            raise ValidationError('El monto de la transferencia SIPAP debe ser mayor a cero.')

        code = (codigo_transferencia or '').strip() or cls.generate_transfer_code()

        if len(code) < 6:
            raise ValidationError('El código de transferencia SIPAP debe contener al menos 6 caracteres.')

        if SipapTransferRecord.objects.filter(codigo_transferencia=code).exists():
            raise ValidationError(f'El código de transferencia {code} ya se encuentra registrado.')

        estado = SipapTransferRecord.Estado.CONFIRMADA if auto_confirm else SipapTransferRecord.Estado.PENDIENTE
        fecha_conciliacion = timezone.now() if auto_confirm else None

        with transaction.atomic():
            sipap_record = SipapTransferRecord.objects.create(
                codigo_transferencia=code,
                transaction=transaction_obj,
                banco_origen=banco_origen,
                cuenta_origen=cuenta_origen,
                titular_origen=titular_origen,
                documento_origen=documento_origen,
                banco_destino=banco_destino or cls.DEFAULT_BANCO_DESTINO,
                cuenta_destino=cuenta_destino or cls.DEFAULT_CUENTA_DESTINO,
                monto=amount_decimal,
                moneda=(moneda or 'PYG').upper(),
                estado=estado,
                fecha_conciliacion=fecha_conciliacion,
                metadata=metadata or {},
            )

        logger.info('Transferencia SIPAP simulada registrada: %s [%s %s]', code, moneda, amount_decimal)
        return sipap_record

    @classmethod
    def validate_transfer(
        cls,
        codigo_transferencia: str,
        expected_monto: Optional[Union[Decimal, float, str]] = None,
        expected_moneda: Optional[str] = None,
        expected_cuenta_origen: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[SipapTransferRecord]]:
        """
        Valida la existencia e integridad de una transferencia bancaria en SIPAP.

        :param codigo_transferencia: Código de referencia de la transferencia a validar.
        :type codigo_transferencia: str
        :param expected_monto: Monto esperado para verificar coincidencia exacta (opcional).
        :type expected_monto: decimal.Decimal or None
        :param expected_moneda: Moneda esperada (ej. 'PYG', 'USD') (opcional).
        :type expected_moneda: str or None
        :param expected_cuenta_origen: Número de cuenta origen esperado (opcional).
        :type expected_cuenta_origen: str or None
        :return: Tupla (es_valido, mensaje_error, registro).
        :rtype: tuple[bool, str or None, payments.models.SipapTransferRecord or None]
        """
        code = (codigo_transferencia or '').strip()
        if not code:
            return False, 'El código de transferencia no puede estar vacío.', None

        record = SipapTransferRecord.objects.filter(codigo_transferencia=code).first()
        if not record:
            return False, f'No se encontró ninguna transferencia con el código {code}.', None

        if record.estado == SipapTransferRecord.Estado.RECHAZADA:
            return False, f'La transferencia {code} fue rechazada por la entidad bancaria: {record.motivo_rechazo}', record

        if expected_monto is not None:
            expected_dec = Decimal(str(expected_monto))
            if record.monto != expected_dec:
                return (
                    False,
                    f'Discrepancia en el monto transferido: se esperaba {expected_dec} {expected_moneda or ""} pero se recibió {record.monto} {record.moneda}.',
                    record,
                )

        if expected_moneda and record.moneda.upper() != expected_moneda.upper():
            return (
                False,
                f'Discrepancia en la moneda: se esperaba {expected_moneda.upper()} pero la transferencia fue en {record.moneda}.',
                record,
            )

        if expected_cuenta_origen and record.cuenta_origen.strip() != expected_cuenta_origen.strip():
            return (
                False,
                f'Discrepancia en cuenta de origen: se esperaba {expected_cuenta_origen} pero la transferencia provino de {record.cuenta_origen}.',
                record,
            )

        return True, None, record

    @classmethod
    def confirm_deposit(
        cls,
        codigo_transferencia: str,
        transaction_obj: Optional[Any] = None,
        banco_origen: Optional[str] = None,
        cuenta_origen: Optional[str] = None,
        titular_origen: Optional[str] = None,
        documento_origen: Optional[str] = None,
        monto: Optional[Union[Decimal, float, str]] = None,
        moneda: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Concilia y confirma un depósito bancario SIPAP, actualizando transacciones asociadas.

        Aplica control de **idempotencia estricta**:
        Si el comprobante bancario ya fue confirmado y conciliado en el sistema,
        retorna `status='already_processed'` para prevenir dobles acreditaciones.

        Si se suministra una `transaction_obj` o está asociada al registro:
        - Verifica que el monto y la divisa coincidan exactamente con la orden.
        - Transiciona el estado de la transacción de `PENDIENTE` a `COMPLETADA`.

        :param codigo_transferencia: Código de comprobante de la transferencia interbancaria.
        :type codigo_transferencia: str
        :param transaction_obj: Transacción cambiaria a liquidar (:class:`transactions.models.Transaction`).
        :type transaction_obj: transactions.models.Transaction or None
        :param banco_origen: Banco remitente (si se registra por primera vez en la confirmación).
        :type banco_origen: str or None
        :param cuenta_origen: Cuenta remitente.
        :type cuenta_origen: str or None
        :param titular_origen: Titular de la cuenta remitente.
        :type titular_origen: str or None
        :param documento_origen: Documento o RUC del titular.
        :type documento_origen: str or None
        :param monto: Monto transferido (requerido si el registro no existe aún).
        :type monto: decimal.Decimal or None
        :param moneda: Moneda de la transferencia (por defecto 'PYG').
        :type moneda: str or None
        :return: Diccionario con resultado de la conciliación.
        :rtype: dict
        """
        code = (codigo_transferencia or '').strip()
        if not code:
            raise ValidationError('Debe suministrar un código de transferencia válido.')

        # 1. Comprobar idempotencia previa en PaymentGatewayRecord
        existing_gateway = PaymentGatewayRecord.objects.filter(
            gateway=PaymentGatewayRecord.Gateway.SIPAP,
            referencia_externa=code,
            estado=PaymentGatewayRecord.Estado.COMPLETADO,
        ).first()

        if existing_gateway:
            logger.info('Transferencia SIPAP %s ya conciliada previamente. Omitiendo duplicado.', code)
            return {
                'status': 'already_processed',
                'codigo_transferencia': code,
                'gateway_record_id': existing_gateway.id,
                'message': 'El depósito bancario ya fue conciliado con anterioridad.',
            }

        # 2. Localizar o crear SipapTransferRecord
        sipap_record = SipapTransferRecord.objects.filter(codigo_transferencia=code).first()

        if not sipap_record:
            if monto is None or Decimal(str(monto)) <= Decimal('0.00'):
                raise ValidationError('Debe indicar un monto válido para registrar la nueva transferencia SIPAP.')
            sipap_record = cls.simulate_transfer(
                monto=monto,
                moneda=moneda or 'PYG',
                banco_origen=banco_origen or 'Banco Remitente',
                cuenta_origen=cuenta_origen or '00000000',
                titular_origen=titular_origen or 'Titular Remitente',
                documento_origen=documento_origen or '',
                transaction_obj=transaction_obj,
                codigo_transferencia=code,
                auto_confirm=False,
            )

        # 3. Vincular transacción si se especifica
        target_trans = transaction_obj or sipap_record.transaction

        if target_trans:
            # Validar que los montos coincidan
            expected_monto = getattr(target_trans, 'monto_origen', None)
            expected_moneda = getattr(target_trans.moneda_origen, 'code', 'PYG') if hasattr(target_trans, 'moneda_origen') else 'PYG'

            if expected_monto is not None and sipap_record.monto != expected_monto:
                raise ValidationError(
                    f'Discrepancia en monto de conciliación: la transacción requiere {expected_monto} '
                    f'{expected_moneda} pero la transferencia SIPAP acreditó {sipap_record.monto} {sipap_record.moneda}.'
                )

            if expected_moneda and sipap_record.moneda.upper() != expected_moneda.upper():
                raise ValidationError(
                    f'Discrepancia en divisa: la transacción espera {expected_moneda} '
                    f'pero la transferencia SIPAP fue enviada en {sipap_record.moneda}.'
                )

        # 4. Actualización atómica de estados y conciliación
        with transaction.atomic():
            now = timezone.now()
            sipap_record.estado = SipapTransferRecord.Estado.CONFIRMADA
            sipap_record.fecha_conciliacion = now
            if target_trans and not sipap_record.transaction:
                sipap_record.transaction = target_trans

            # Crear o actualizar registro de pasarela PaymentGatewayRecord
            gateway_record, _ = PaymentGatewayRecord.objects.update_or_create(
                gateway=PaymentGatewayRecord.Gateway.SIPAP,
                referencia_externa=code,
                defaults={
                    'cliente': getattr(target_trans, 'cliente', None),
                    'transaction': target_trans,
                    'monto': sipap_record.monto,
                    'moneda': sipap_record.moneda,
                    'estado': PaymentGatewayRecord.Estado.COMPLETADO,
                    'datos_evento': {
                        'codigo_transferencia': code,
                        'banco_origen': sipap_record.banco_origen,
                        'cuenta_origen': sipap_record.cuenta_origen,
                        'titular_origen': sipap_record.titular_origen,
                        'fecha_conciliacion': now.isoformat(),
                    },
                },
            )
            sipap_record.gateway_record = gateway_record
            sipap_record.save()

            # 5. Transición atómica de la transacción cambiaria si aplica (SCRUM-94)
            if target_trans:
                from transactions.services import TransactionService
                if target_trans.estado == target_trans.Estado.PENDIENTE:
                    TransactionService.confirm_sipap_payment(
                        transaction_obj=target_trans,
                        codigo_transferencia=code,
                        monto=sipap_record.monto,
                        moneda=sipap_record.moneda,
                        banco_origen=sipap_record.banco_origen,
                        cuenta_origen=sipap_record.cuenta_origen,
                        titular_origen=sipap_record.titular_origen,
                    )
                    logger.info('Transacción %s completada exitosamente vía SIPAP orquestada por TransactionService.', target_trans.codigo_referencia)

        return {
            'status': 'success',
            'codigo_transferencia': code,
            'gateway_record_id': gateway_record.id,
            'sipap_transfer_id': sipap_record.id,
            'monto': str(sipap_record.monto),
            'moneda': sipap_record.moneda,
            'transaction_id': target_trans.id if target_trans else None,
            'message': 'Depósito bancario SIPAP confirmado y conciliado satisfactoriamente.',
        }

    @classmethod
    def reject_transfer(cls, codigo_transferencia: str, motivo: str = 'Transferencia rechazada') -> Dict[str, Any]:
        """
        Registra el rechazo de una transferencia bancaria SIPAP.

        Si la transferencia estaba vinculada a una transacción cambiaria en estado
        `PENDIENTE`, transiciona dicha orden a `CANCELADA` cumpliendo con las
        reglas de negocio de conciliación bancaria (SCRUM-87 / SCRUM-93 / SCRUM-94).

        :param codigo_transferencia: Código de la transferencia a rechazar.
        :type codigo_transferencia: str
        :param motivo: Explicación del rechazo o discrepancia.
        :type motivo: str
        :return: Diccionario con el resultado.
        :rtype: dict
        """
        code = (codigo_transferencia or '').strip()
        record = SipapTransferRecord.objects.filter(codigo_transferencia=code).first()
        if not record:
            raise ValidationError(f'No se encontró ninguna transferencia con código {code}.')

        from transactions.services import TransactionService

        with transaction.atomic():
            record.estado = SipapTransferRecord.Estado.RECHAZADA
            record.motivo_rechazo = motivo
            record.save(update_fields=['estado', 'motivo_rechazo', 'updated_at'])

            PaymentGatewayRecord.objects.filter(
                gateway=PaymentGatewayRecord.Gateway.SIPAP,
                referencia_externa=code,
            ).update(
                estado=PaymentGatewayRecord.Estado.FALLIDO,
                error_mensaje=motivo,
            )

            # Transicionar a CANCELADA la transacción vinculada si estaba en PENDIENTE
            if record.transaction and record.transaction.estado == record.transaction.Estado.PENDIENTE:
                TransactionService.reject_payment_and_cancel(
                    transaction_obj=record.transaction,
                    gateway='SIPAP',
                    referencia_externa=code,
                    motivo=motivo,
                )

        return {
            'status': 'rejected',
            'codigo_transferencia': code,
            'motivo': motivo,
        }

