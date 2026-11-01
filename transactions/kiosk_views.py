"""
Vistas y endpoints para la terminal de autoservicio táctil /kiosk/ (SCRUM-121).

Provee:
1. `KioskHomeView`: Interfaz táctil dark-mode de alta legibilidad con selección rápida de divisas,
   cotizador en tiempo real con teclado numérico táctil en pantalla y temporizador de seguridad por inactividad.
2. `KioskQuoteApiView`: Endpoint para cálculo de cotizaciones instantáneas en vivo.
3. `KioskCustomerLookupApiView`: Validación express de clientes por RUC o Cédula de Identidad.
4. `KioskExpressRegisterApiView`: Registro express en 1 toque para clientes no preexistentes.
5. `KioskTransactApiView`: Formalización y liquidación express con emisión inmediata de KuDE.
"""

from decimal import Decimal
import json
import logging
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate, OperationLimit
from rates.services import RateCalculationService
from .kude_service import KudeService
from .models import ElectronicInvoice, Transaction

logger = logging.getLogger(__name__)


def get_or_create_kiosk_methods(cliente: Cliente) -> tuple[PaymentMethod, ReceivingMethod]:
    """
    Garantiza que el cliente cuente con medios de pago y acreditación de tipo Efectivo / Caja
    para operar en terminales táctiles de autoservicio (Kiosk).
    """
    entidad, _ = EntidadFinanciera.objects.get_or_create(
        nombre='Caja Kiosco Central',
        defaults={'tipo': EntidadFinanciera.TipoEntidad.BANCO, 'activo': True, 'orden': 99}
    )

    # Medio de pago en efectivo
    medio_pago = PaymentMethod.objects.filter(
        cliente=cliente,
        tipo_medio=PaymentMethod.TipoMedio.EFECTIVO,
        activo=True
    ).first()
    if not medio_pago:
        medio_pago = PaymentMethod.objects.create(
            cliente=cliente,
            tipo_medio=PaymentMethod.TipoMedio.EFECTIVO,
            entidad_bancaria=entidad,
            numero_cuenta='VENTANILLA-KIOSK',
            titular=cliente.nombre,
            documento_titular=cliente.documento_ruc,
            es_predeterminado=False,
            activo=True,
        )

    # Medio de acreditación
    medio_acred = ReceivingMethod.objects.filter(
        cliente=cliente,
        activo=True
    ).first()
    if not medio_acred:
        medio_acred = ReceivingMethod.objects.create(
            cliente=cliente,
            entidad_bancaria=entidad,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO,
            numero_cuenta='VENTANILLA-KIOSK',
            titular=cliente.nombre,
            documento_titular=cliente.documento_ruc,
            es_predeterminado=False,
            activo=True,
        )

    return medio_pago, medio_acred


class KioskHomeView(View):
    """
    Vista táctil simplificada /kiosk/ con layout dark-mode de alta legibilidad (SCRUM-121).

    Características ergonómicas:
    - Paleta dark-mode de alto contraste (#0b0f19, #111827, #38bdf8, #10b981) óptima para terminales.
    - Botonera táctil de gran escala (touch-friendly targets > 56px).
    - Tarjetas de selección rápida de divisas con cotización actual en vivo.
    - Teclado numérico táctil interactivo en pantalla.
    - Temporizador de seguridad con cuenta regresiva regresiva por inactividad.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # Divisa local de referencia
        pyg_currency = Currency.objects.filter(code='PYG', is_active=True).first()

        # Obtener divisas activas (excluyendo PYG)
        currencies = Currency.objects.filter(is_active=True).exclude(code='PYG').order_by('code')

        # Obtener cotizaciones vigentes contra PYG
        rates_data = []
        now = timezone.now()
        for curr in currencies:
            rate = ExchangeRate.objects.filter(
                base_currency=curr,
                target_currency__code='PYG',
                is_active=True,
                valid_from__lte=now
            ).order_by('-valid_from', '-created_at').first()

            if rate:
                rates_data.append({
                    'currency': curr,
                    'buy_rate': rate.buy_rate,
                    'sell_rate': rate.sell_rate,
                    'spread': rate.spread,
                    'symbol': curr.symbol,
                    'rate_id': rate.id,
                })

        context = {
            'rates_data': rates_data,
            'pyg_currency': pyg_currency,
            'default_timeout_seconds': 90,
            'warning_timeout_seconds': 20,
            'current_time': timezone.now(),
        }
        return render(request, 'kiosk/kiosk_home.html', context)


class KioskQuoteApiView(View):
    """
    Endpoint AJAX/JSON para cotizaciones en tiempo real en la interfaz táctil del Kiosco.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        return self._handle_quote(request)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        return self._handle_quote(request)

    def _handle_quote(self, request: HttpRequest) -> JsonResponse:
        currency_code = (request.POST.get('currency') or request.GET.get('currency') or 'USD').upper().strip()
        amount_raw = request.POST.get('amount') or request.GET.get('amount') or '100'
        op_type = (request.POST.get('operation_type') or request.GET.get('operation_type') or 'BUY').upper().strip()
        customer_ruc = request.POST.get('customer_ruc') or request.GET.get('customer_ruc') or ''

        try:
            amount = Decimal(str(amount_raw))
            if amount <= Decimal('0'):
                return JsonResponse({'success': False, 'error': 'El monto debe ser estrictamente positivo.'}, status=400)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Formato numérico de monto inválido.'}, status=400)

        # Resolver cotización oficial
        now = timezone.now()
        rate = ExchangeRate.objects.filter(
            base_currency__code=currency_code,
            target_currency__code='PYG',
            is_active=True,
            valid_from__lte=now
        ).order_by('-valid_from', '-created_at').first()

        if not rate:
            return JsonResponse({'success': False, 'error': f'No existe cotización vigente para {currency_code}/PYG.'}, status=404)

        # Resolver cliente por RUC si fue validado previamente
        cliente = None
        segment = Cliente.Segmentacion.MINORISTA
        if customer_ruc:
            cliente = Cliente.objects.filter(documento_ruc=customer_ruc.strip(), is_active=True).first()
            if cliente:
                segment = cliente.segmentacion

        try:
            quotation = RateCalculationService.calculate_quotation(
                exchange_rate=rate,
                segment_or_customer=cliente or segment,
                amount=amount,
                operation_type=op_type,
                is_source_base=(op_type == 'SELL'),
                validate_limits=True,
                raise_on_limit_violation=False,
            )
        except ValidationError as err:
            return JsonResponse({'success': False, 'error': str(err)}, status=400)

        # En BUY: entrega monto_origen (PYG) y recibe monto_destino (divisa base)
        # En SELL: entrega monto_origen (divisa base) y recibe monto_destino (PYG)
        if op_type == 'BUY':
            monto_origen = quotation['net_target_amount']
            monto_destino = quotation['base_amount']
            moneda_origen = rate.target_currency.code
            moneda_destino = rate.base_currency.code
        else:
            monto_origen = quotation['base_amount']
            monto_destino = quotation['net_target_amount']
            moneda_origen = rate.base_currency.code
            moneda_destino = rate.target_currency.code

        limits_data = quotation.get('limits', {})
        data = {
            'success': True,
            'base_currency': rate.base_currency.code,
            'base_symbol': rate.base_currency.symbol,
            'target_currency': rate.target_currency.code,
            'target_symbol': rate.target_currency.symbol,
            'operation_type': op_type,
            'amount_input': str(amount),
            'buy_rate': str(rate.buy_rate),
            'sell_rate': str(rate.sell_rate),
            'tasa_base': str(quotation['official_rate']),
            'comision': str(quotation['total_commission']),
            'tasa_neta': str(quotation['final_effective_rate']),
            'monto_origen': str(monto_origen),
            'monto_destino': str(monto_destino),
            'moneda_origen': moneda_origen,
            'moneda_destino': moneda_destino,
            'segment': segment,
            'limits': {
                'is_valid': limits_data.get('is_valid', True),
                'errors': limits_data.get('errors', []),
                'warnings': limits_data.get('warnings', []),
                'min_amount': str(limits_data.get('monto_minimo', '0.00')),
                'max_amount': str(limits_data.get('monto_maximo', '0.00')),
            }
        }
        return JsonResponse(data)


class KioskCustomerLookupApiView(View):
    """
    Endpoint para validación express de clientes por Cédula de Identidad o RUC en el Kiosco.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        doc = (request.GET.get('doc') or request.GET.get('ruc') or request.GET.get('q') or '').strip()
        if not doc:
            return JsonResponse({'success': False, 'error': 'Debe ingresar un número de Cédula o RUC.'}, status=400)

        # Limpiar documento de puntos
        clean_doc = doc.replace('.', '').strip()

        # Buscar por coincidencia exacta o por inicio de RUC sin dígito verificador
        cliente = Cliente.objects.filter(documento_ruc__iexact=clean_doc, is_active=True).first()
        if not cliente and '-' not in clean_doc:
            cliente = Cliente.objects.filter(documento_ruc__startswith=f"{clean_doc}-", is_active=True).first()

        if cliente:
            return JsonResponse({
                'success': True,
                'found': True,
                'id': cliente.id,
                'nombre': cliente.nombre,
                'documento_ruc': cliente.documento_ruc,
                'correo': cliente.correo,
                'segmento': cliente.segmentacion,
                'segmento_display': cliente.get_segmentacion_display(),
            })

        return JsonResponse({
            'success': True,
            'found': False,
            'message': 'Cliente no registrado. Puede realizar un registro express rápido para continuar.'
        })


class KioskExpressRegisterApiView(View):
    """
    Endpoint para registro express de clientes en el Kiosco de autoservicio en un solo toque.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        nombre = request.POST.get('nombre', '').strip()
        doc = request.POST.get('documento_ruc', '').strip().replace('.', '')
        correo = request.POST.get('correo', '').strip()
        telefono = request.POST.get('telefono', '').strip()

        if not nombre:
            return JsonResponse({'success': False, 'error': 'Debe ingresar su Nombre completo.'}, status=400)
        if not doc:
            return JsonResponse({'success': False, 'error': 'Debe ingresar su Documento / RUC.'}, status=400)

        # Si no ingresó correo, generar uno express para el kiosco
        if not correo:
            correo = f"cliente.{doc}@kiosk.globalexchange.com.py"

        # Verificar si ya existe
        cliente = Cliente.objects.filter(documento_ruc=doc).first()
        if cliente:
            return JsonResponse({
                'success': True,
                'id': cliente.id,
                'nombre': cliente.nombre,
                'documento_ruc': cliente.documento_ruc,
                'segmento': cliente.segmentacion,
                'segmento_display': cliente.get_segmentacion_display(),
                'message': 'Cliente preexistente recuperado.',
            })

        # Evitar colisión de correo
        if Cliente.objects.filter(correo=correo).exists():
            correo = f"kiosk.{doc}.{timezone.now().strftime('%H%M%S')}@globalexchange.com.py"

        cliente = Cliente.objects.create(
            nombre=nombre,
            documento_ruc=doc,
            correo=correo,
            telefono=telefono or '0981000000',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=True,
        )

        return JsonResponse({
            'success': True,
            'id': cliente.id,
            'nombre': cliente.nombre,
            'documento_ruc': cliente.documento_ruc,
            'segmento': cliente.segmentacion,
            'segmento_display': cliente.get_segmentacion_display(),
            'message': 'Registro express exitoso.',
        })


class KioskTransactApiView(View):
    """
    Endpoint para formalización y liquidación express de operaciones desde el Kiosco.
    Emite inmediatamente la factura electrónica y su correspondiente KuDE.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        currency_code = (request.POST.get('currency') or 'USD').upper().strip()
        amount_raw = request.POST.get('amount') or '100'
        op_type = (request.POST.get('operation_type') or 'BUY').upper().strip()
        customer_id = request.POST.get('customer_id')
        customer_doc = request.POST.get('customer_ruc')

        try:
            amount = Decimal(str(amount_raw))
            if amount <= Decimal('0'):
                return JsonResponse({'success': False, 'error': 'El monto debe ser estrictamente positivo.'}, status=400)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Monto inválido.'}, status=400)

        # Resolver cliente
        cliente = None
        if customer_id:
            cliente = Cliente.objects.filter(id=customer_id, is_active=True).first()
        if not cliente and customer_doc:
            cliente = Cliente.objects.filter(documento_ruc=customer_doc.strip(), is_active=True).first()

        if not cliente:
            return JsonResponse({'success': False, 'error': 'Debe validar o registrar un cliente antes de operar.'}, status=400)

        # Resolver cotización vigente
        now = timezone.now()
        rate = ExchangeRate.objects.filter(
            base_currency__code=currency_code,
            target_currency__code='PYG',
            is_active=True,
            valid_from__lte=now
        ).order_by('-valid_from', '-created_at').first()

        if not rate:
            return JsonResponse({'success': False, 'error': 'No existe cotización disponible.'}, status=400)

        # Calcular cotización neta
        try:
            quotation = RateCalculationService.calculate_quotation(
                exchange_rate=rate,
                segment_or_customer=cliente,
                amount=amount,
                operation_type=op_type,
                is_source_base=(op_type == 'SELL'),
                validate_limits=True,
                raise_on_limit_violation=True,
            )
        except ValidationError as err:
            return JsonResponse({'success': False, 'error': str(err)}, status=400)

        # Asegurar medios de pago / cobro para el cliente en el kiosco
        medio_pago, medio_acred = get_or_create_kiosk_methods(cliente)

        if op_type == 'BUY':
            monto_origen = quotation['net_target_amount']
            monto_destino = quotation['base_amount']
        else:
            monto_origen = quotation['base_amount']
            monto_destino = quotation['net_target_amount']

        with db_transaction.atomic():
            tipo_transaccion = Transaction.TipoOperacion.COMPRA if op_type == 'BUY' else Transaction.TipoOperacion.VENTA
            tx = Transaction(
                cliente=cliente,
                tipo_operacion=tipo_transaccion,
                base_currency=rate.base_currency,
                target_currency=rate.target_currency,
                exchange_rate=rate,
                tasa_base=quotation['official_rate'],
                comision_segmento=quotation['total_commission'],
                tasa_neta=quotation['final_effective_rate'],
                monto_origen=monto_origen,
                monto_destino=monto_destino,
                medio_pago_origen=medio_pago,
                medio_acreditacion_destino=medio_acred,
                estado=Transaction.Estado.COMPLETADA,
                fecha_pago=now,
                referencia_externa_pago=f"KIOSK-POS-{now.strftime('%Y%m%d%H%M%S')}",
                pasarela_pago='KIOSK_EFECTIVO',
                observaciones='Operación realizada y liquidada a través de terminal de autoservicio Kiosk.',
            )
            tx.save()

            # Emitir inmediatamente la Factura Electrónica y KuDE
            invoice = KudeService.get_or_create_invoice(tx)

        data = {
            'success': True,
            'transaction_id': tx.id,
            'codigo_referencia': tx.codigo_referencia,
            'tipo_operacion': tx.get_tipo_operacion_display(),
            'moneda_origen': tx.moneda_origen.code,
            'monto_origen': str(tx.monto_origen),
            'moneda_destino': tx.moneda_destino.code,
            'monto_destino': str(tx.monto_destino),
            'tasa_neta': str(tx.tasa_neta),
            'fecha': tx.created_at.strftime('%d/%m/%Y %H:%M:%S'),
            'cdc': invoice.cdc,
            'cdc_formatted': invoice.cdc_formatted,
            'numero_factura': invoice.numero_factura,
            'timbrado': invoice.timbrado,
            'kude_view_url': reverse('transactions:kude', kwargs={'pk': tx.id}) + '?source=kiosk',
            'kude_pdf_url': reverse('transactions:kude_pdf', kwargs={'pk': tx.id}),
            'kude_xml_url': reverse('transactions:kude_xml', kwargs={'pk': tx.id}),
            'receipt_url': reverse('transactions:receipt', kwargs={'pk': tx.id}),
        }
        return JsonResponse(data)
