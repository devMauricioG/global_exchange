"""
Pruebas Unitarias y de Integración para Kiosco Táctil de Autoservicio y Facturación Electrónica KuDE (SCRUM-121).

Cubre:
1. Generación matemática y validación del CDC de 44 dígitos (algoritmo Módulo 11 de SIFEN).
2. Generación canónica del XML firmado e-Kuatia (DNIT) y cadena de verificación QR.
3. Ciclo de vida y consultas del modelo `ElectronicInvoice`.
4. Vistas de visualización, descarga de PDF binario y descarga de XML firmado.
5. Endpoint API REST de consulta pública de comprobantes KuDE por CDC y código de referencia.
6. Vista táctil `/kiosk/` con layout dark-mode y temporizador de inactividad.
7. Endpoints de cotización en tiempo real, validación express por RUC/Cédula y formalización de orden en Kiosco.
"""

from decimal import Decimal
import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate, SegmentCommission
from transactions.kude_pdf import KudePdfGenerator
from transactions.kude_service import (
    KudeService,
    compute_mod11_dv,
    generate_cdc,
    generate_qr_url,
    generate_sifen_xml,
)
from transactions.models import ElectronicInvoice, Transaction

User = get_user_model()


class KudeServiceAndModelTests(TestCase):
    """
    Pruebas para el cálculo de CDC, generación de XML firmado, QR y modelo ElectronicInvoice.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='operador_kude', email='op@kude.com')
        self.cliente = Cliente.objects.create(
            nombre='Comercial San Cayetano S.A.',
            documento_ruc='80098765-4',
            correo='contacto@sancayetano.com.py',
            segmentacion=Cliente.Segmentacion.CORPORATIVO,
            is_active=True,
        )
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní Paraguayo', symbol='Gs', decimals=0, is_active=True)
        self.usd = Currency.objects.create(code='USD', name='Dólar Estadounidense', symbol='$', decimals=2, is_active=True)

        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.00'),
            sell_rate=Decimal('7900.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )
        self.entidad = EntidadFinanciera.objects.create(
            nombre='Banco Nacional de Prueba',
            tipo=EntidadFinanciera.TipoEntidad.BANCO,
            activo=True
        )
        self.medio_pago = PaymentMethod.objects.create(
            cliente=self.cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.AHORRO,
            entidad_bancaria=self.entidad,
            numero_cuenta='11223344',
            titular='Comercial San Cayetano S.A.',
            activo=True,
        )
        self.medio_acred = ReceivingMethod.objects.create(
            cliente=self.cliente,
            entidad_bancaria=self.entidad,
            tipo_cuenta=ReceivingMethod.TipoCuenta.CORRIENTE,
            numero_cuenta='55667788',
            titular='Comercial San Cayetano S.A.',
            activo=True,
        )
        self.tx = Transaction.objects.create(
            cliente=self.cliente,
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
            base_currency=self.usd,
            target_currency=self.pyg,
            exchange_rate=self.rate,
            tasa_base=Decimal('7900.00'),
            comision_segmento=Decimal('0.00'),
            tasa_neta=Decimal('7900.00'),
            monto_origen=Decimal('100.00'),
            monto_destino=Decimal('790000.00'),
            medio_pago_origen=self.medio_pago,
            medio_acreditacion_destino=self.medio_acred,
            estado=Transaction.Estado.COMPLETADA,
            fecha_pago=timezone.now(),
        )

    def test_compute_mod11_dv(self):
        """Valida que el cálculo de dígito verificador Módulo 11 de la DNIT retorne un dígito válido (0-9)."""
        dv = compute_mod11_dv("0180012345700100100000012202611011123456789")
        self.assertTrue(dv.isdigit())
        self.assertEqual(len(dv), 1)

    def test_generate_cdc_structure(self):
        """Valida que el CDC generado cumpla estrictamente con 44 dígitos numéricos."""
        cdc = generate_cdc(numero_documento=1, fecha_emision=timezone.now())
        self.assertEqual(len(cdc), 44)
        self.assertTrue(cdc.isdigit())
        # Primeros 2 dígitos deben ser 01 (Factura Electrónica)
        self.assertEqual(cdc[:2], '01')

    def test_get_or_create_invoice_idempotence(self):
        """Verifica que la emisión de factura electrónica sea idempotente."""
        inv1 = KudeService.get_or_create_invoice(self.tx)
        self.assertIsNotNone(inv1)
        self.assertEqual(len(inv1.cdc), 44)
        self.assertEqual(inv1.estado, ElectronicInvoice.EstadoSifen.APROBADO)
        self.assertIn("001-001-", inv1.numero_factura)

        # Segunda llamada debe retornar la misma factura sin duplicar registros
        inv2 = KudeService.get_or_create_invoice(self.tx)
        self.assertEqual(inv1.id, inv2.id)
        self.assertEqual(inv1.cdc, inv2.cdc)

    def test_generate_sifen_xml_contains_ekuetia_schema(self):
        """Verifica que el XML contenga los esquemas oficiales de e-Kuatia, namespaces y firma XMLDSig."""
        inv = KudeService.get_or_create_invoice(self.tx)
        xml = inv.xml_firmado
        self.assertIn('<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd"', xml)
        self.assertIn(f'<DE Id="{inv.cdc}">', xml)
        self.assertIn('<dDesTiDE>Factura Electrónica</dDesTiDE>', xml)
        self.assertIn('<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">', xml)
        self.assertIn(self.cliente.nombre, xml)

    def test_generate_qr_url(self):
        """Verifica que la URL del código QR apunte al portal oficial de SIFEN con los parámetros requeridos."""
        inv = KudeService.get_or_create_invoice(self.tx)
        qr_url = inv.qr_data
        self.assertTrue(qr_url.startswith("https://ekuatia.set.gov.py/consultas/qr"))
        self.assertIn(f"Id={inv.cdc}", qr_url)

    def test_kude_pdf_generator_creates_valid_pdf(self):
        """Verifica que KudePdfGenerator produzca un archivo PDF-1.4 binario válido."""
        inv = KudeService.get_or_create_invoice(self.tx)
        pdf_bytes = KudePdfGenerator.generate_pdf(inv)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4"))
        self.assertTrue(b"%%EOF" in pdf_bytes)
        self.assertGreater(len(pdf_bytes), 500)

    def test_electronic_invoice_model_helpers(self):
        """Verifica los métodos auxiliares y propiedades del modelo ElectronicInvoice."""
        inv = KudeService.get_or_create_invoice(self.tx)
        self.assertTrue(inv.is_aprobado)
        self.assertIn('-', inv.cdc_formatted)
        self.assertIn(inv.numero_factura, str(inv))
        # Propiedades en Transaction
        self.assertTrue(self.tx.has_kude)
        self.assertEqual(self.tx.kude.id, inv.id)


class KudeViewsAndEndpointsTests(TestCase):
    """
    Pruebas para las vistas web de visualización KuDE, descarga de PDF, XML y consulta API REST.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='cliente_test', password='password123')
        self.cliente = Cliente.objects.create(
            nombre='Persona Física Test',
            documento_ruc='1234567-8',
            correo='persona@test.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=True,
        )
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní Paraguayo', symbol='Gs', decimals=0, is_active=True)
        self.usd = Currency.objects.create(code='USD', name='Dólar Estadounidense', symbol='$', decimals=2, is_active=True)

        self.rate = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.00'),
            sell_rate=Decimal('7900.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )
        self.entidad = EntidadFinanciera.objects.create(nombre='Banco Test', tipo=EntidadFinanciera.TipoEntidad.BANCO, activo=True)
        self.medio_pago = PaymentMethod.objects.create(
            cliente=self.cliente, tipo_medio=PaymentMethod.TipoMedio.EFECTIVO,
            entidad_bancaria=self.entidad, numero_cuenta='001', titular='Persona Test', activo=True
        )
        self.medio_acred = ReceivingMethod.objects.create(
            cliente=self.cliente, entidad_bancaria=self.entidad,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO, numero_cuenta='002', titular='Persona Test', activo=True
        )
        self.tx = Transaction.objects.create(
            cliente=self.cliente,
            tipo_operacion=Transaction.TipoOperacion.VENTA,
            base_currency=self.usd,
            target_currency=self.pyg,
            exchange_rate=self.rate,
            tasa_base=Decimal('7800.00'),
            comision_segmento=Decimal('0.00'),
            tasa_neta=Decimal('7800.00'),
            monto_origen=Decimal('50.00'),
            monto_destino=Decimal('390000.00'),
            medio_pago_origen=self.medio_pago,
            medio_acreditacion_destino=self.medio_acred,
            estado=Transaction.Estado.COMPLETADA,
            fecha_pago=timezone.now(),
        )
        self.invoice = KudeService.get_or_create_invoice(self.tx)

    def test_kude_html_view(self):
        """Verifica que la vista web interactiva del KuDE retorne código HTTP 200 con la plantilla."""
        url = reverse('transactions:kude', kwargs={'pk': self.tx.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/kude.html')
        self.assertContains(response, self.invoice.numero_factura)
        self.assertContains(response, self.invoice.cdc_formatted)
        self.assertContains(response, 'APROBADO EN SIFEN')

    def test_kude_pdf_download_view(self):
        """Verifica que el endpoint de descarga retorne un archivo application/pdf con Content-Disposition."""
        url = reverse('transactions:kude_pdf', kwargs={'pk': self.tx.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF-1.4'))

    def test_kude_xml_download_view(self):
        """Verifica que el endpoint de descarga retorne el archivo XML con Content-Disposition."""
        url = reverse('transactions:kude_xml', kwargs={'pk': self.tx.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('xml', response['Content-Type'])
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn(b'<rDE', response.content)

    def test_kude_consulta_api_by_cdc(self):
        """Verifica la consulta pública de la API REST mediante el CDC de 44 dígitos."""
        url = reverse('transactions:kude_api', kwargs={'identifier': self.invoice.cdc})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cdc'], self.invoice.cdc)
        self.assertEqual(data['estado_sifen'], 'APROBADO')
        self.assertEqual(data['transaccion']['codigo_referencia'], self.tx.codigo_referencia)

    def test_kude_consulta_api_by_reference_code(self):
        """Verifica la consulta pública de la API REST mediante el código de referencia de transacción."""
        url = reverse('transactions:kude_api', kwargs={'identifier': self.tx.codigo_referencia})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['numero_factura'], self.invoice.numero_factura)

    def test_kude_consulta_api_not_found(self):
        """Verifica que ante un identificador inexistente retorne HTTP 404 con mensaje estructurado."""
        url = reverse('transactions:kude_api', kwargs={'identifier': '00000000000000000000000000000000000000000000'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data['success'])


class KioskTerminalTests(TestCase):
    """
    Pruebas para la interfaz táctil /kiosk/ y sus servicios de cotización, validación y transacciones.
    """

    def setUp(self):
        self.client = Client()
        self.pyg = Currency.objects.create(code='PYG', name='Guaraní Paraguayo', symbol='Gs', decimals=0, is_active=True)
        self.usd = Currency.objects.create(code='USD', name='Dólar Estadounidense', symbol='$', decimals=2, is_active=True)
        self.eur = Currency.objects.create(code='EUR', name='Euro', symbol='€', decimals=2, is_active=True)

        self.rate_usd = ExchangeRate.objects.create(
            base_currency=self.usd,
            target_currency=self.pyg,
            buy_rate=Decimal('7800.00'),
            sell_rate=Decimal('7900.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )
        self.rate_eur = ExchangeRate.objects.create(
            base_currency=self.eur,
            target_currency=self.pyg,
            buy_rate=Decimal('8400.00'),
            sell_rate=Decimal('8600.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )
        self.comm_min = SegmentCommission.objects.create(
            segment=Cliente.Segmentacion.MINORISTA,
            commission_percentage=Decimal('1.00'),
            fixed_fee=Decimal('0.00'),
            spread_discount_percentage=Decimal('0.00'),
            is_active=True,
        )
        self.cliente = Cliente.objects.create(
            nombre='Juan Pérez Kiosco',
            documento_ruc='4567890-1',
            correo='juan.kiosk@test.com',
            segmentacion=Cliente.Segmentacion.MINORISTA,
            is_active=True,
        )

    def test_kiosk_home_view_loads_successfully(self):
        """Verifica que la vista principal táctil /kiosk/ cargue con status 200, dark-mode y timeout."""
        response = self.client.get(reverse('kiosk:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'kiosk/kiosk_home.html')
        self.assertContains(response, 'Terminal de Autoservicio Kiosco')
        self.assertContains(response, 'USD')
        self.assertContains(response, 'EUR')
        self.assertContains(response, 'timerText')

    def test_kiosk_quote_api_buy(self):
        """Verifica el cálculo de cotización en tiempo real para COMPRA de divisas en Kiosco."""
        url = reverse('kiosk:api_quote')
        response = self.client.get(url, {
            'currency': 'USD',
            'amount': '100',
            'operation_type': 'BUY',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['base_currency'], 'USD')
        self.assertEqual(data['operation_type'], 'BUY')
        self.assertEqual(data['tasa_base'], '7900.000000')
        self.assertGreater(float(data['monto_destino']), 0)

    def test_kiosk_quote_api_sell(self):
        """Verifica el cálculo de cotización en tiempo real para VENTA de divisas en Kiosco."""
        url = reverse('kiosk:api_quote')
        response = self.client.get(url, {
            'currency': 'USD',
            'amount': '100',
            'operation_type': 'SELL',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['operation_type'], 'SELL')
        self.assertEqual(data['tasa_base'], '7800.000000')

    def test_kiosk_customer_lookup_found(self):
        """Verifica la búsqueda express de cliente por Cédula/RUC cuando existe en la base de datos."""
        url = reverse('kiosk:api_customer_lookup')
        response = self.client.get(url, {'doc': '4567890'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['found'])
        self.assertEqual(data['nombre'], self.cliente.nombre)

    def test_kiosk_customer_lookup_not_found(self):
        """Verifica la respuesta cuando un cliente no se encuentra registrado en el sistema."""
        url = reverse('kiosk:api_customer_lookup')
        response = self.client.get(url, {'doc': '9999999'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['found'])

    def test_kiosk_express_register_customer(self):
        """Verifica el registro express de un cliente en un solo toque desde el Kiosco."""
        url = reverse('kiosk:api_customer_register')
        response = self.client.post(url, {
            'nombre': 'Nuevo Cliente Kiosco',
            'documento_ruc': '5544332-1',
            'telefono': '0981999888',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['nombre'], 'Nuevo Cliente Kiosco')

        # Verificar persistencia en base de datos
        nuevo = Cliente.objects.filter(documento_ruc='5544332-1').first()
        self.assertIsNotNone(nuevo)
        self.assertEqual(nuevo.segmentacion, Cliente.Segmentacion.MINORISTA)

    def test_kiosk_transact_creates_completed_tx_and_kude(self):
        """Verifica que la confirmación en Kiosco formalice la transacción y emita inmediatamente el KuDE."""
        url = reverse('kiosk:api_transact')
        response = self.client.post(url, {
            'currency': 'USD',
            'amount': '200',
            'operation_type': 'BUY',
            'customer_id': self.cliente.id,
            'customer_ruc': self.cliente.documento_ruc,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('TX-', data['codigo_referencia'])
        self.assertEqual(len(data['cdc']), 44)
        self.assertIn('001-001-', data['numero_factura'])

        # Verificar registro en base de datos
        tx = Transaction.objects.get(id=data['transaction_id'])
        self.assertEqual(tx.estado, Transaction.Estado.COMPLETADA)
        self.assertEqual(tx.pasarela_pago, 'KIOSK_EFECTIVO')
        self.assertTrue(tx.has_kude)
        self.assertEqual(tx.kude.cdc, data['cdc'])
