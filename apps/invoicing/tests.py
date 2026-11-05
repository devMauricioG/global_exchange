"""
Suite de pruebas unitarias para la arquitectura de Facturación Electrónica SIFEN (SCRUM-117).

Verifica exhaustivamente:
1. Patrón Strategy/Adapter: Interfaz abstracta InvoiceProvider.
2. Motor de cálculo matemático: Fórmulas SIFEN e-Kuatia según ESI v01 (IVA 5%, 10%, Exenta, Exonerada).
3. Algoritmo Módulo 11 oficial y generación de CDC de 44 dígitos.
4. Implementación simulada MockInvoiceProvider (CDCs válidos, KuDE PDF representativo, XML firmado, 0 cuota real).
5. Adaptador real FacturaSeguraProvider con guardián LiveModeDisabledError y protocolo de comunicación ESI v01.
6. Fábrica get_invoice_provider con inyección de dependencias y selector de entorno.
"""

from decimal import Decimal
import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.invoicing.calculators import (
    calculate_de,
    compute_mod11_dv,
    generate_cdc,
)
from apps.invoicing.client import FacturaSeguraClient
from apps.invoicing.exceptions import (
    InvoiceNotFoundError,
    InvoiceProviderError,
    InvoiceValidationError,
    LiveModeDisabledError,
    PresentationQuotaExhaustedError,
    QuotaExhaustedError,
    QuotaShieldExhaustedError,
    TestQuotaExhaustedError,
)
from apps.invoicing.providers import (
    FacturaSeguraProvider,
    InvoiceProvider,
    MockInvoiceProvider,
    get_invoice_provider,
    reset_invoice_provider,
    set_invoice_provider,
)
from apps.invoicing.types import (
    EstadoSifenEnum,
    InvoiceResponse,
    StatusResponse,
)


class InvoiceProviderInterfaceTests(TestCase):
    """Verifica que InvoiceProvider sea una clase abstracta pura (Strategy/Adapter)."""

    def test_cannot_instantiate_abstract_provider(self):
        """Verifica que la interfaz abstracta no pueda ser instanciada directamente."""
        with self.assertRaises(TypeError):
            InvoiceProvider()

    def test_subclass_must_implement_all_methods(self):
        """Verifica que una subclase incompleta no pueda ser instanciada."""
        class IncompleteProvider(InvoiceProvider):
            def calcular_de(self, de_data):
                return {}

        with self.assertRaises(TypeError):
            IncompleteProvider()


class SifenCalculatorsTests(TestCase):
    """
    Verifica los cálculos matemáticos de SIFEN y la generación de CDC conforme
    al documento 'API de Factura Segura para ESI v01' (páginas 17-21 y 33-40).
    """

    def test_compute_mod11_dv_official(self):
        """Verifica el cálculo de Módulo 11 con vectores de prueba oficiales de la DNIT / SET."""
        # RUC 80012345 -> DV 0 (resto 1 -> DV 0 según regla SIFEN)
        self.assertEqual(compute_mod11_dv('80012345'), '0')
        # RUC 80002247 -> DV 5 (del ejemplo oficial del manual ESI)
        self.assertEqual(compute_mod11_dv('80002247'), '5')
        # RUC 2595733 -> DV 3 (del ejemplo del receptor en manual ESI)
        self.assertEqual(compute_mod11_dv('2595733'), '3')

    def test_generate_cdc_format_and_length(self):
        """Verifica que el CDC generado cumpla con los 44 dígitos y su dígito verificador."""
        cdc = generate_cdc(
            tipo_documento='01',
            ruc_emisor='80012345',
            dv_emisor='7',
            establecimiento='001',
            punto_expedicion='001',
            numero_documento=123,
            tipo_contribuyente='2',
            tipo_emision='1',
            codigo_seguridad='123456789',
        )
        self.assertEqual(len(cdc), 44)
        self.assertTrue(cdc.isdigit())
        # Verificar que el dígito 44 corresponda al Módulo 11 de los 43 dígitos previos
        cuerpo_43 = cdc[:43]
        dv_calculado = compute_mod11_dv(cuerpo_43)
        self.assertEqual(cdc[-1], dv_calculado)

    def test_calculate_de_exact_manual_esi_example(self):
        """
        Verifica el cálculo matemático con el conjunto de 5 ítems exactos
        especificados en las páginas 17 a 21 del documento 'API de Factura Segura para ESI v01'.
        """
        de_input = {
            'cMoneOpe': 'PYG',
            'dRedon': '0',
            'dComi': '0',
            'gCamItem': [
                # Item 1: Linternas Maglite B (3 u a 150.000, desc 50.000, IVA 5%)
                {
                    'dCodInt': 'SP32012B',
                    'dDesProSer': 'Linternas Mini Maglite LED 2 Cell AAA, Negra en caja B',
                    'cUniMed': '77',
                    'dCantProSer': '3',
                    'dPUniProSer': '150000',
                    'dDescItem': '50000',
                    'iAfecIVA': '1',
                    'dPropIVA': '100',
                    'dTasaIVA': '5',
                },
                # Item 2: Linternas Maglite A (20 u a 80.000, desc 10.000, IVA 10%)
                {
                    'dCodInt': 'SP32012A',
                    'dDesProSer': 'Linternas Mini Maglite LED 2 Cell AAA, Negra en caja A',
                    'cUniMed': '77',
                    'dCantProSer': '20',
                    'dPUniProSer': '80000',
                    'dDescItem': '10000',
                    'iAfecIVA': '1',
                    'dPropIVA': '100',
                    'dTasaIVA': '10',
                },
                # Item 3: Muestras (1 u a 25.000, Gravado Parcial 25%, IVA 10%)
                {
                    'dCodInt': 'YXD',
                    'dDesProSer': 'MUESTRAS',
                    'cUniMed': '77',
                    'dCantProSer': '1',
                    'dPUniProSer': '25000',
                    'dDescItem': '0',
                    'iAfecIVA': '4',
                    'dPropIVA': '25',
                    'dTasaIVA': '10',
                },
                # Item 4: Producto exento (3 u a 34.000, IVA Exento)
                {
                    'dCodInt': 'ABC',
                    'dDesProSer': 'producto exento',
                    'cUniMed': '77',
                    'dCantProSer': '3',
                    'dPUniProSer': '34000',
                    'dDescItem': '0',
                    'iAfecIVA': '3',
                    'dPropIVA': '0',
                    'dTasaIVA': '0',
                },
                # Item 5: Producto exonerado (5 u a 12.000, IVA Exonerado)
                {
                    'dCodInt': 'EDF',
                    'dDesProSer': 'producto exonerado',
                    'cUniMed': '77',
                    'dCantProSer': '5',
                    'dPUniProSer': '12000',
                    'dDescItem': '0',
                    'iAfecIVA': '2',
                    'dPropIVA': '0',
                    'dTasaIVA': '0',
                },
            ],
        }

        calc = calculate_de(de_input)
        items = calc['gCamItem']

        # Verificación Item 1 (IVA 5%)
        self.assertEqual(items[0]['dTotBruOpeItem'], '450000')
        self.assertEqual(items[0]['dTotOpeItem'], '300000')
        self.assertEqual(items[0]['dBasGravIVA'], '285714')
        self.assertEqual(items[0]['dLiqIVAItem'], '14286')
        self.assertEqual(items[0]['dBasExe'], '0')

        # Verificación Item 2 (IVA 10%)
        self.assertEqual(items[1]['dTotBruOpeItem'], '1600000')
        self.assertEqual(items[1]['dTotOpeItem'], '1400000')
        self.assertEqual(items[1]['dBasGravIVA'], '1272727')
        self.assertEqual(items[1]['dLiqIVAItem'], '127273')
        self.assertEqual(items[1]['dBasExe'], '0')

        # Verificación Item 3 (Gravado Parcial 25% gravado / 75% exento, IVA 10%)
        self.assertEqual(items[2]['dTotBruOpeItem'], '25000')
        self.assertEqual(items[2]['dTotOpeItem'], '25000')
        self.assertEqual(items[2]['dBasGravIVA'], '6098')
        self.assertEqual(items[2]['dLiqIVAItem'], '610')
        self.assertEqual(items[2]['dBasExe'], '18293')

        # Verificación Item 4 (Exento)
        self.assertEqual(items[3]['dTotBruOpeItem'], '102000')
        self.assertEqual(items[3]['dTotOpeItem'], '102000')
        self.assertEqual(items[3]['dBasGravIVA'], '0')
        self.assertEqual(items[3]['dLiqIVAItem'], '0')
        self.assertEqual(items[3]['dBasExe'], '0')

        # Verificación Item 5 (Exonerado)
        self.assertEqual(items[4]['dTotBruOpeItem'], '60000')
        self.assertEqual(items[4]['dTotOpeItem'], '60000')
        self.assertEqual(items[4]['dBasGravIVA'], '0')
        self.assertEqual(items[4]['dLiqIVAItem'], '0')
        self.assertEqual(items[4]['dBasExe'], '0')

        # Verificación de Subtotales globales (página 20 del manual ESI)
        self.assertEqual(calc['dSubExe'], '120293')     # 102.000 + 18.293
        self.assertEqual(calc['dSubExo'], '60000')      # 60.000
        self.assertEqual(calc['dSub5'], '300000')       # 300.000
        self.assertEqual(calc['dSub10'], '1406708')     # 1.400.000 + 6.098 + 610
        self.assertEqual(calc['dTotOpe'], '1887001')

        # Verificación de Descuentos y Totales Generales (página 21)
        self.assertEqual(calc['dTotDesc'], '350000')
        self.assertEqual(calc['dDescTotal'], '350000')
        self.assertEqual(calc['dTotGralOpe'], '1887001')

        # Verificación de Liquidación Global de IVA (página 21)
        self.assertEqual(calc['dIVA5'], '14286')
        self.assertEqual(calc['dIVA10'], '127883')
        self.assertEqual(calc['dTotIVA'], '142169')
        self.assertEqual(calc['dBaseGrav5'], '285714')
        self.assertEqual(calc['dBaseGrav10'], '1278825')
        self.assertEqual(calc['dTBasGraIVA'], '1564539')

    def test_calculate_de_usd_currency_conversion(self):
        """Verifica el cálculo de dTotalGs cuando la moneda de la operación es USD."""
        de_usd = {
            'cMoneOpe': 'USD',
            'dTiCam': '7450',
            'gCamItem': [
                {
                    'dCantProSer': '1',
                    'dPUniProSer': '100.00',
                    'dDescItem': '0',
                    'iAfecIVA': '3',  # Exento
                    'dPropIVA': '0',
                    'dTasaIVA': '0',
                }
            ],
        }
        calc = calculate_de(de_usd)
        self.assertEqual(calc['dTotGralOpe'], '100.00')
        self.assertEqual(calc['dTotalGs'], '745000')


class MockInvoiceProviderTests(TestCase):
    """Verifica el comportamiento de MockInvoiceProvider para testing y desarrollo local."""

    def setUp(self):
        self.provider = MockInvoiceProvider()
        self.provider.reset_registry()

    def test_generar_de_success(self):
        """Verifica la generación de un DTE simulado con CDC de 44 dígitos y estado SIFEN Aprobado."""
        de_sample = {
            'dNumDoc': '0000100',
            'dRucEm': '80012345',
            'dDVEmi': '7',
            'dEst': '001',
            'dPunExp': '001',
            'cMoneOpe': 'PYG',
            'gCamItem': [
                {
                    'dCodInt': 'TX-TEST-01',
                    'dDesProSer': 'Compra de Divisas',
                    'cUniMed': '77',
                    'dCantProSer': '1',
                    'dPUniProSer': '500000',
                    'dDescItem': '0',
                    'iAfecIVA': '3',
                }
            ],
        }

        resp = self.provider.generar_de(de_sample)

        self.assertIsInstance(resp, InvoiceResponse)
        self.assertEqual(len(resp.cdc), 44)
        self.assertTrue(resp.cdc.isdigit())
        self.assertTrue(resp.is_approved)
        self.assertEqual(resp.estado_sifen, EstadoSifenEnum.APROBADO.value)
        self.assertEqual(resp.desc_sifen, '0260 - Aprobado')
        self.assertTrue(resp.es_simulada)
        self.assertEqual(resp.numero_factura, '001-001-0000100')

        # Verificación del KuDE PDF
        self.assertTrue(resp.kude_pdf_bytes.startswith(b'%PDF-1.4'))
        self.assertIn(b'%%EOF', resp.kude_pdf_bytes)

        # Verificación del XML firmado representativo
        self.assertIn('<rDE', resp.xml_firmado)
        self.assertIn(f'Id="{resp.cdc}"', resp.xml_firmado)
        self.assertIn('<Signature', resp.xml_firmado)
        self.assertIn('</rDE>', resp.xml_firmado)

    def test_get_estado_sifen_approved(self):
        """Verifica que la consulta get_estado_sifen retorne Aprobado por defecto."""
        status = self.provider.get_estado_sifen('01800123457001001000000122026110511234567890')
        self.assertIsInstance(status, StatusResponse)
        self.assertTrue(status.is_approved)
        self.assertEqual(status.estado_sifen, 'Aprobado')
        self.assertEqual(status.desc_sifen, '0260 - Aprobado')

    def test_sol_cancelacion_flow(self):
        """Verifica la solicitud de cancelación simulada y la transición de estado en SIFEN."""
        cdc = '01800123457001001000000122026110511234567890'
        res = self.provider.sol_cancelacion(cdc, motivo='Error de facturación')
        self.assertEqual(res['code'], 0)
        self.assertEqual(res['description'], 'OK')

        # Al consultar nuevamente, debe reportar Cancelado
        status = self.provider.get_estado_sifen(cdc)
        self.assertTrue(status.is_cancelled)
        self.assertEqual(status.estado_sifen, EstadoSifenEnum.CANCELADO.value)
        self.assertEqual(status.estado_can, 'Aprobado')

    def test_sol_inutilizacion(self):
        """Verifica la respuesta de inutilización conforme al manual ESI."""
        res = self.provider.sol_inutilizacion(
            ruc_emisor='80012345',
            timbrado='12548963',
            est='001',
            pun_exp='001',
            num_doc='0000005',
        )
        self.assertEqual(res['code'], 0)
        self.assertEqual(res['description'], 'OK')

    def test_download_kude_and_xml(self):
        """Verifica la descarga de KuDE PDF y XML firmado para un CDC dado."""
        cdc = '01800123457001001000000122026110511234567890'
        kude_pdf = self.provider.dwn_kude(cdc)
        self.assertTrue(kude_pdf.startswith(b'%PDF-1.4'))

        xml_str = self.provider.dwn_xml(cdc)
        self.assertIn('<rDE', xml_str)
        self.assertIn(cdc, xml_str)

    def test_emitir_factura_with_dict(self):
        """Verifica la emisión de factura pasando un diccionario directamente."""
        payload = {
            'dNumDoc': '0000002',
            'cMoneOpe': 'PYG',
            'gCamItem': [{'dPUniProSer': '100000', 'dCantProSer': '1', 'iAfecIVA': '3'}],
        }
        resp = self.provider.emitir_factura(payload)
        self.assertEqual(len(resp.cdc), 44)
        self.assertTrue(resp.is_approved)


class FacturaSeguraProviderTests(TestCase):
    """Verifica el adaptador FacturaSeguraProvider y su blindaje de seguridad."""

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=False)
    def test_live_disabled_guards(self):
        """Verifica que se dispare LiveModeDisabledError si FACTURA_SEGURA_LIVE_ENABLED=False."""
        provider = FacturaSeguraProvider(email='test@example.com', password='pass')

        with self.assertRaises(LiveModeDisabledError):
            provider.calcular_de({'test': 1})

        with self.assertRaises(LiveModeDisabledError):
            provider.generar_de({'test': 1})

        with self.assertRaises(LiveModeDisabledError):
            provider.get_estado_sifen('01800123457001001000000122026110511234567890')

        with self.assertRaises(LiveModeDisabledError):
            provider.sol_cancelacion('01800123457001001000000122026110511234567890')

        with self.assertRaises(LiveModeDisabledError):
            provider.dwn_kude('01800123457001001000000122026110511234567890')

        with self.assertRaises(LiveModeDisabledError):
            provider.dwn_xml('01800123457001001000000122026110511234567890')

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_live_login_and_generar_de_with_mocks(self):
        """
        Verifica el flujo HTTP estándar (Login y generar_de) simulando las respuestas
        del webservice ESI conforme al protocolo del manual Factura Segura.
        """
        provider = FacturaSeguraProvider(
            api_url='https://apitest.facturasegura.com.py',
            email='test@example.com',
            password='secret_password',
            emisor_ruc='80012345',
        )

        mock_login_resp = json.dumps({
            'meta': {'code': 200},
            'response': {
                'user': {'authentication_token': 'test_auth_token_xyz_123'},
            },
        }).encode('utf-8')

        mock_generar_resp = json.dumps({
            'code': 0,
            'description': 'OK',
            'operation_info': {'id': 'test-op-uuid'},
            'results': [{'CDC': '01800123457001001000000122026110511234567890'}],
        }).encode('utf-8')

        def mock_urlopen(request, timeout=15):
            url = request.get_full_url()
            cm = MagicMock()
            if 'login' in url:
                cm.read.return_value = mock_login_resp
            elif 'misife00/v1/esi' in url:
                cm.read.return_value = mock_generar_resp
            elif 'dwn_kude' in url:
                cm.read.return_value = b'%PDF-1.4 simulated'
            elif 'dwn_xml' in url:
                cm.read.return_value = b'<rDE>simulated</rDE>'
            cm.__enter__.return_value = cm
            return cm

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            resp = provider.generar_de({'dNumDoc': '0000001', 'dRucEm': '80012345'})

            self.assertEqual(resp.cdc, '01800123457001001000000122026110511234567890')
            self.assertEqual(resp.protocolo, 'test-op-uuid')
            self.assertFalse(resp.es_simulada)
            self.assertEqual(provider.get_auth_token(), 'test_auth_token_xyz_123')

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_live_negative_code_raises_provider_error(self):
        """Verifica que un código de retorno negativo en la respuesta dispare InvoiceProviderError."""
        provider = FacturaSeguraProvider(auth_token='valid_token')

        mock_error_resp = json.dumps({
            'code': -10001,
            'description': 'El valor del campo iTiOpe no es permitido',
            'operation_info': {'id': 'err-op-id'},
            'results': [{'Exception': 'Longitud de campo incorrecta'}],
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = mock_error_resp
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            with self.assertRaises(InvoiceProviderError) as ctx:
                provider.calcular_de({'test': 'invalid'})
            self.assertEqual(ctx.exception.status_code, -10001)
            self.assertIn('El valor del campo iTiOpe no es permitido', str(ctx.exception))

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_live_quota_exhausted_error(self):
        """Verifica que si la respuesta contiene un error de cuota agotada se dispare QuotaExhaustedError."""
        provider = FacturaSeguraProvider(auth_token='valid_token')

        mock_error_resp = json.dumps({
            'code': -10099,
            'description': 'Cuota agotada en Factura Segura',
            'operation_info': {'id': 'quota-id'},
            'results': [],
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = mock_error_resp
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            with self.assertRaises(QuotaExhaustedError):
                provider.generar_de({'test': 1})

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_live_get_estado_sifen(self):
        """Verifica la consulta de estado en Factura Segura vía get_estado_sifen."""
        provider = FacturaSeguraProvider(auth_token='valid_token')

        mock_resp = json.dumps({
            'code': 0,
            'description': 'OK',
            'operation_info': {'id': 'op-123'},
            'results': [{
                'estado_sifen': 'Aprobado',
                'desc_sifen': '0260 - Aprobado',
                'error_sifen': '',
                'fch_sifen': '2026-11-05 14:00:00',
            }],
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = mock_resp
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            status = provider.get_estado_sifen('01800123457001001000000122026110511234567890')
            self.assertEqual(status.estado_sifen, 'Aprobado')
            self.assertTrue(status.is_approved)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_live_sol_cancelacion_and_inutilizacion(self):
        """Verifica sol_cancelacion y sol_inutilizacion contra la API ESI."""
        provider = FacturaSeguraProvider(auth_token='valid_token')

        mock_resp = json.dumps({
            'code': 0,
            'description': 'OK',
            'operation_info': {'id': 'op-can'},
            'results': [],
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = mock_resp
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            res_can = provider.sol_cancelacion('01800123457001001000000122026110511234567890', 'Error')
            self.assertEqual(res_can['code'], 0)

            res_inu = provider.sol_inutilizacion('80012345', '12548963', '001', '001', '0000002')
            self.assertEqual(res_inu['code'], 0)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_live_dwn_kude_and_xml(self):
        """Verifica la descarga de KuDE PDF y XML firmado mediante GET."""
        provider = FacturaSeguraProvider(auth_token='valid_token')

        def mock_urlopen(req, timeout=15):
            url = req.get_full_url()
            cm = MagicMock()
            if 'dwn_kude' in url:
                cm.read.return_value = b'%PDF-1.4 KUDE_BYTES'
            elif 'dwn_xml' in url:
                cm.read.return_value = b'<rDE><DE>XML_DATA</DE></rDE>'
            cm.__enter__.return_value = cm
            return cm

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            pdf_bytes = provider.dwn_kude('01800123457001001000000122026110511234567890')
            self.assertEqual(pdf_bytes, b'%PDF-1.4 KUDE_BYTES')

            xml_str = provider.dwn_xml('01800123457001001000000122026110511234567890')
            self.assertIn('<rDE>', xml_str)

    def test_mock_emitir_factura_with_mock_transaction(self):
        """Verifica la emisión de factura con un objeto transacción simulado."""
        mock_cliente = MagicMock()
        mock_cliente.documento_ruc = '2595733-3'
        mock_cliente.nombre = 'GUILLERMO GONZALEZ'
        mock_cliente.correo = 'receptor@gmail.com'

        mock_target_currency = MagicMock()
        mock_target_currency.code = 'PYG'

        mock_tx = MagicMock()
        mock_tx.id = 999
        mock_tx.cliente = mock_cliente
        mock_tx.target_currency = mock_target_currency
        mock_tx.monto_destino = Decimal('1500000')
        mock_tx.tasa_neta = Decimal('1')
        mock_tx.codigo_referencia = 'TX-20261105-001'
        mock_tx.tipo_operacion = 'COMPRA'

        provider = MockInvoiceProvider()
        resp = provider.emitir_factura(mock_tx)

        self.assertEqual(len(resp.cdc), 44)
        self.assertTrue(resp.is_approved)
        self.assertEqual(resp.numero_factura, '001-001-0000999')
        resp_dict = resp.to_dict()
        self.assertEqual(resp_dict['cdc'], resp.cdc)

    def test_status_response_predicates(self):
        """Verifica los métodos auxiliares de StatusResponse."""
        st_void = StatusResponse(cdc='1234', estado_sifen='Inutilizado', estado_inu='Aprobado')
        self.assertTrue(st_void.is_voided)
        self.assertFalse(st_void.is_approved)
        d = st_void.to_dict()
        self.assertTrue(d['is_voided'])


class InvoiceProviderFactoryTests(TestCase):
    """Verifica la fábrica get_invoice_provider y la inyección dinámica de proveedores."""

    def tearDown(self):
        reset_invoice_provider()

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=False)
    def test_factory_returns_mock_by_default(self):
        """Verifica que la fábrica retorne MockInvoiceProvider si el flag LIVE es falso."""
        provider = get_invoice_provider()
        self.assertIsInstance(provider, MockInvoiceProvider)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_factory_returns_real_when_live_enabled(self):
        """Verifica que la fábrica retorne FacturaSeguraProvider si LIVE está habilitado."""
        provider = get_invoice_provider()
        self.assertIsInstance(provider, FacturaSeguraProvider)

    def test_factory_explicit_type(self):
        """Verifica la selección explícita mediante parámetro."""
        p_mock = get_invoice_provider('mock')
        self.assertIsInstance(p_mock, MockInvoiceProvider)

        p_real = get_invoice_provider('facturasegura')
        self.assertIsInstance(p_real, FacturaSeguraProvider)

    def test_factory_override_and_reset(self):
        """Verifica la sobreescritura de proveedor para inyección de mocks."""
        custom_mock = MockInvoiceProvider()
        set_invoice_provider(custom_mock)
        self.assertIs(get_invoice_provider(), custom_mock)

        reset_invoice_provider()
        self.assertIsNot(get_invoice_provider(), custom_mock)


# =============================================================================
# SCRUM-118 — Tests del modelo FacturaElectronica y servicio InvoiceService
# =============================================================================

from decimal import Decimal as D
import tempfile

from customers.models import Cliente
from payments.models import EntidadFinanciera, PaymentMethod, ReceivingMethod
from rates.models import Currency, ExchangeRate
from transactions.models import Transaction

from apps.invoicing.models import FacturaElectronica
from apps.invoicing.services import InvoiceService


class FacturaElectronicaModelMixin:
    """
    Mixin con datos maestros mínimos para tests de FacturaElectronica.
    Reutiliza la misma estrategia del TransactionTestMixin de transactions.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usd = Currency.objects.create(
            code='TST', name='Test Currency', symbol='T', decimals=2, is_active=True
        )
        cls.pyg = Currency.objects.create(
            code='TSG', name='Test Guarani', symbol='G', decimals=0, is_active=True
        )
        cls.banco, _ = EntidadFinanciera.objects.get_or_create(
            nombre='Banco Test Invoicing',
            defaults={'tipo': EntidadFinanciera.TipoEntidad.BANCO, 'activo': True},
        )
        cls.cliente = Cliente.objects.create(
            nombre='Test Receptor',
            documento_ruc='2595733-3',
            correo='receptor@test.com',
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        cls.user = User.objects.create_user(
            username='test_inv_user',
            email='receptor@test.com',
            password='Password123!',
        )
        from customers.models import CustomerUserAssignment
        CustomerUserAssignment.objects.create(
            customer=cls.cliente,
            user=cls.user,
            is_primary_representative=True,
            is_active=True,
        )
        cls.medio_pago = PaymentMethod.objects.create(
            cliente=cls.cliente,
            tipo_medio=PaymentMethod.TipoMedio.TRANSFERENCIA,
            entidad_bancaria=cls.banco,
            numero_cuenta='11112222',
            titular='Test Receptor',
            documento_titular='2595733-3',
            tipo_cuenta_bancaria=PaymentMethod.TipoCuentaBancaria.AHORRO,
            es_predeterminado=True,
            activo=True,
        )
        cls.medio_acred = ReceivingMethod.objects.create(
            cliente=cls.cliente,
            entidad_bancaria=cls.banco,
            tipo_cuenta=ReceivingMethod.TipoCuenta.AHORRO,
            numero_cuenta='22221111',
            titular='Test Receptor',
            documento_titular='2595733-3',
            es_predeterminado=True,
            activo=True,
        )
        cls.tasa = ExchangeRate.objects.create(
            base_currency=cls.usd,
            target_currency=cls.pyg,
            buy_rate=D('7500.00'),
            sell_rate=D('7600.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            is_active=True,
        )
        cls.tx = Transaction.objects.create(
            cliente=cls.cliente,
            usuario=cls.user,
            tipo_operacion=Transaction.TipoOperacion.COMPRA,
            base_currency=cls.usd,
            target_currency=cls.pyg,
            tasa_base=D('7600.000000'),
            comision_segmento=D('0.00'),
            tasa_neta=D('7600.000000'),
            monto_origen=D('760000.00'),
            monto_destino=D('100.00'),
            medio_pago_origen=cls.medio_pago,
            medio_acreditacion_destino=cls.medio_acred,
            estado=Transaction.Estado.COMPLETADA,
        )

    @staticmethod
    def _make_cdc(suffix='0001'):
        """Genera un CDC de 44 dígitos de prueba único por sufijo."""
        base = '01800123457001001000000120261105'
        pad = suffix.zfill(12)
        raw = base + pad
        assert len(raw) == 44, f"CDC mal formado ({len(raw)} dígitos)"
        return raw


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class FacturaElectronicaModelTests(FacturaElectronicaModelMixin, TestCase):
    """
    Tests del modelo FacturaElectronica (SCRUM-118).

    Verifica persistencia, restricciones, propiedades y métodos de utilidad
    del modelo FacturaElectronica en apps/invoicing/models.py.
    """

    def _make_factura(self, **kwargs):
        """Helper para crear una FacturaElectronica con valores mínimos válidos."""
        defaults = dict(
            transaction=self.tx,
            cdc=self._make_cdc(),
            numero_factura='001-001-0000001',
            ruc_receptor='2595733-3',
            estado_sifen=FacturaElectronica.EstadoSifen.APROBADO,
            es_simulada=True,
        )
        defaults.update(kwargs)
        return FacturaElectronica.objects.create(**defaults)

    def test_create_minimal_factura(self):
        """Verifica la creación de una FacturaElectronica con campos mínimos."""
        f = self._make_factura()
        self.assertIsNotNone(f.pk)
        self.assertEqual(len(f.cdc), 44)
        self.assertTrue(f.cdc.isdigit())
        self.assertEqual(f.estado_sifen, FacturaElectronica.EstadoSifen.APROBADO)
        self.assertTrue(f.es_simulada)

    def test_str_representation(self):
        """Verifica __str__ incluye número de factura y estado."""
        f = self._make_factura()
        s = str(f)
        self.assertIn('001-001-0000001', s)
        self.assertIn('Aprobado', s)
        self.assertIn('[SIMULADA]', s)

    def test_cdc_formatted_property(self):
        """Verifica que cdc_formatted retorne 11 grupos de 4 dígitos separados por guiones."""
        f = self._make_factura()
        formatted = f.cdc_formatted
        parts = formatted.split('-')
        self.assertEqual(len(parts), 11)
        for part in parts:
            self.assertEqual(len(part), 4)
            self.assertTrue(part.isdigit())

    def test_cdc_formatted_blank(self):
        """Verifica que cdc_formatted retorne cadena vacía si cdc está vacío."""
        f = FacturaElectronica.__new__(FacturaElectronica)
        f.cdc = ''
        self.assertEqual(f.cdc_formatted, '')

    def test_is_aprobado_property(self):
        """Verifica la propiedad is_aprobado para estados aprobados y no aprobados."""
        f = self._make_factura(cdc=self._make_cdc('0002'))
        f.estado_sifen = FacturaElectronica.EstadoSifen.APROBADO
        self.assertTrue(f.is_aprobado)

        f.estado_sifen = FacturaElectronica.EstadoSifen.APROBADO_OBS
        self.assertTrue(f.is_aprobado)

        f.estado_sifen = FacturaElectronica.EstadoSifen.RECHAZADO
        self.assertFalse(f.is_aprobado)

    def test_is_cancelado_property(self):
        """Verifica la propiedad is_cancelado."""
        f = self._make_factura(cdc=self._make_cdc('0003'))
        f.estado_sifen = FacturaElectronica.EstadoSifen.CANCELADO
        self.assertTrue(f.is_cancelado)

        f.estado_sifen = FacturaElectronica.EstadoSifen.APROBADO
        self.assertFalse(f.is_cancelado)

    def test_is_inutilizado_property(self):
        """Verifica la propiedad is_inutilizado."""
        f = self._make_factura(cdc=self._make_cdc('0004'))
        f.estado_sifen = FacturaElectronica.EstadoSifen.INUTILIZADO
        self.assertTrue(f.is_inutilizado)

        f.estado_sifen = FacturaElectronica.EstadoSifen.APROBADO
        self.assertFalse(f.is_inutilizado)

    def test_es_simulada_default_true(self):
        """Verifica que es_simulada tenga default=True (seguridad: nunca real por defecto)."""
        f = FacturaElectronica(
            transaction=self.tx,
            cdc=self._make_cdc('0005'),
            numero_factura='001-001-0000005',
            ruc_receptor='2595733-3',
        )
        self.assertTrue(f.es_simulada)

    def test_unique_cdc_constraint(self):
        """Verifica que dos facturas no puedan tener el mismo CDC."""
        from django.db import IntegrityError
        cdc = self._make_cdc('0006')
        self._make_factura(cdc=cdc, numero_factura='001-001-0000006')
        with self.assertRaises(IntegrityError):
            # Crear otra tx para evitar conflicto OneToOne
            tx2 = Transaction.objects.create(
                cliente=self.cliente,
                tipo_operacion=Transaction.TipoOperacion.VENTA,
                base_currency=self.usd,
                target_currency=self.pyg,
                tasa_base=D('7600.000000'),
                comision_segmento=D('0.00'),
                tasa_neta=D('7600.000000'),
                monto_origen=D('100.00'),
                monto_destino=D('760000.00'),
                medio_pago_origen=self.medio_pago,
                medio_acreditacion_destino=self.medio_acred,
                estado=Transaction.Estado.COMPLETADA,
            )
            FacturaElectronica.objects.create(
                transaction=tx2,
                cdc=cdc,  # CDC duplicado → IntegrityError
                numero_factura='001-001-0000066',
                ruc_receptor='2595733-3',
            )

    def test_one_to_one_relation_with_transaction(self):
        """Verifica que la relación OneToOne a Transaction funcione correctamente."""
        f = self._make_factura(cdc=self._make_cdc('0007'))
        self.assertEqual(f.transaction_id, self.tx.pk)
        # Acceso inverso desde la transacción
        self.assertEqual(self.tx.factura_sifen, f)

    def test_respuesta_sifen_raw_json(self):
        """Verifica el almacenamiento y recuperación de un dict en respuesta_sifen_raw."""
        payload = {'code': 0, 'description': 'OK', 'cdc': self._make_cdc('0008')}
        f = self._make_factura(
            cdc=payload['cdc'],
            numero_factura='001-001-0000008',
            respuesta_sifen_raw=payload,
        )
        f.refresh_from_db()
        self.assertEqual(f.respuesta_sifen_raw['code'], 0)
        self.assertEqual(f.respuesta_sifen_raw['description'], 'OK')

    def test_save_xml_content(self):
        """Verifica que save_xml_content rellene xml_firmado y archivo_xml."""
        f = self._make_factura(cdc=self._make_cdc('0009'), numero_factura='001-001-0000009')
        xml_content = '<rDE Id="test"><Signature/></rDE>'
        f.save_xml_content(xml_content, filename='test_sifen.xml')

        self.assertEqual(f.xml_firmado, xml_content)
        self.assertTrue(bool(f.archivo_xml))

    def test_save_pdf_content(self):
        """Verifica que save_pdf_content persista el archivo KuDE PDF."""
        f = self._make_factura(cdc=self._make_cdc('0010'), numero_factura='001-001-0000010')
        pdf_bytes = b'%PDF-1.4 test content %%EOF'
        f.save_pdf_content(pdf_bytes, filename='test_kude.pdf')

        self.assertTrue(bool(f.archivo_pdf))

    def test_created_at_updated_at_auto(self):
        """Verifica que created_at y updated_at se rellenen automáticamente."""
        f = self._make_factura(cdc=self._make_cdc('0011'), numero_factura='001-001-0000011')
        self.assertIsNotNone(f.created_at)
        self.assertIsNotNone(f.updated_at)

    def test_estado_sifen_choices(self):
        """Verifica que todos los EstadoSifen sean valores válidos del TextChoices."""
        valid = {c[0] for c in FacturaElectronica.EstadoSifen.choices}
        for estado in FacturaElectronica.EstadoSifen:
            self.assertIn(estado.value, valid)

    def test_condicion_venta_choices(self):
        """Verifica los CondicionVenta TextChoices."""
        self.assertEqual(FacturaElectronica.CondicionVenta.CONTADO, 'CONTADO')
        self.assertEqual(FacturaElectronica.CondicionVenta.CREDITO, 'CREDITO')


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class InvoiceServiceTests(FacturaElectronicaModelMixin, TestCase):
    """
    Tests del servicio InvoiceService (SCRUM-118).

    Verifica create_from_response, update_estado y get_or_create_for_transaction
    usando el MockInvoiceProvider para generar InvoiceResponse reales.
    """

    def setUp(self):
        self.provider = MockInvoiceProvider()
        self.provider.reset_registry()

    def _emit_response(self, num_doc='0000001'):
        """Helper: emite una factura simulada con el MockProvider."""
        return self.provider.emitir_factura({
            'dNumDoc': num_doc,
            'dRucEm': '80012345',
            'dDVEmi': '0',
            'dEst': '001',
            'dPunExp': '001',
            'cMoneOpe': 'PYG',
            'gCamItem': [{
                'dCodInt': 'TX-001',
                'dDesProSer': 'Compra de Divisas Test',
                'cUniMed': '77',
                'dCantProSer': '1',
                'dPUniProSer': '500000',
                'dDescItem': '0',
                'iAfecIVA': '3',
            }],
        })

    def test_create_from_response_creates_factura(self):
        """Verifica que create_from_response cree una FacturaElectronica en BD."""
        response = self._emit_response('1000001')
        factura = InvoiceService.create_from_response(self.tx, response)

        self.assertIsNotNone(factura.pk)
        self.assertEqual(factura.cdc, response.cdc)
        self.assertEqual(factura.transaction, self.tx)
        self.assertTrue(factura.es_simulada)

    def test_create_from_response_persists_xml(self):
        """Verifica que el XML firmado se almacene en xml_firmado."""
        response = self._emit_response('1000002')
        factura = InvoiceService.create_from_response(self.tx, response)

        self.assertIn('<rDE', factura.xml_firmado)
        self.assertIn(response.cdc, factura.xml_firmado)

    def test_create_from_response_persists_pdf(self):
        """Verifica que el KuDE PDF se persista en archivo_pdf."""
        response = self._emit_response('1000003')
        factura = InvoiceService.create_from_response(self.tx, response)

        self.assertTrue(bool(factura.archivo_pdf))

    def test_create_from_response_estado_aprobado(self):
        """Verifica que el estado sea APROBADO después de emitir con MockProvider."""
        response = self._emit_response('1000004')
        factura = InvoiceService.create_from_response(self.tx, response)

        self.assertTrue(factura.is_aprobado)

    def test_update_estado(self):
        """Verifica update_estado cambia el estado_sifen y persiste respuesta_raw."""
        response = self._emit_response('1000005')
        factura = InvoiceService.create_from_response(self.tx, response)

        # Simular cancelación
        self.provider.sol_cancelacion(factura.cdc)
        status = self.provider.get_estado_sifen(factura.cdc)

        updated = InvoiceService.update_estado(factura.cdc, status)

        self.assertEqual(updated.estado_sifen, FacturaElectronica.EstadoSifen.CANCELADO)
        self.assertIn('estado_sifen', updated.respuesta_sifen_raw)

    def test_get_or_create_returns_existing(self):
        """Verifica que get_or_create_for_transaction retorne la factura existente."""
        response = self._emit_response('1000006')
        f1 = InvoiceService.create_from_response(self.tx, response)

        response2 = self._emit_response('1000007')
        f2, created = InvoiceService.get_or_create_for_transaction(self.tx, response2)

        self.assertFalse(created)
        self.assertEqual(f1.pk, f2.pk)

    def test_map_estado_normalizes_aprobado(self):
        """Verifica que _map_estado normalice correctamente 'Aprobado' a APROBADO."""
        result = InvoiceService._map_estado('Aprobado')
        self.assertEqual(result, FacturaElectronica.EstadoSifen.APROBADO)

    def test_map_estado_normalizes_cancelado(self):
        """Verifica que _map_estado normalice 'Cancelado'."""
        result = InvoiceService._map_estado('Cancelado')
        self.assertEqual(result, FacturaElectronica.EstadoSifen.CANCELADO)

    def test_map_estado_unknown_defaults_to_emitido(self):
        """Verifica que un estado desconocido retorne EMITIDO."""
        result = InvoiceService._map_estado('Estado Desconocido XYZ')
        self.assertEqual(result, FacturaElectronica.EstadoSifen.EMITIDO)


# =============================================================================
# SCRUM-119 — Tests de Vistas y Endpoints KuDE PDF, XML y SIFEN Sync AJAX
# =============================================================================

from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class InvoicingViewsTests(FacturaElectronicaModelMixin, TestCase):
    """
    Tests de vistas y endpoints de KuDE PDF, XML y sincronización AJAX (SCRUM-119).
    """

    def setUp(self):
        self.provider = MockInvoiceProvider()
        self.provider.reset_registry()
        set_invoice_provider(self.provider)

        # Crear otro usuario para validaciones de permisos / IDOR
        self.otro_user = User.objects.create_user(
            username='otro_usuario_invoicing',
            email='otro@test.com',
            password='Password123!',
        )

        # Crear una FacturaElectronica vinculada a self.tx
        resp = self.provider.emitir_factura(self.tx)
        self.factura = InvoiceService.create_from_response(self.tx, resp)

    def tearDown(self):
        reset_invoice_provider()

    def test_factura_detail_view_authenticated_owner(self):
        """Verifica que el titular de la transacción pueda visualizar el KuDE en HTML."""
        self.client.force_login(self.user)
        url = reverse('invoicing:detail', kwargs={'pk': self.factura.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/kude.html')
        self.assertIn('invoice', response.context)
        self.assertEqual(response.context['invoice'].pk, self.factura.pk)

    def test_factura_detail_view_unauthenticated_forbidden(self):
        """Verifica que un usuario anónimo no pueda acceder a la factura."""
        url = reverse('invoicing:detail', kwargs={'pk': self.factura.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_factura_detail_view_other_user_forbidden(self):
        """Verifica prevención IDOR: un usuario ajeno no puede ver la factura."""
        self.client.force_login(self.otro_user)
        url = reverse('invoicing:detail', kwargs={'pk': self.factura.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_factura_pdf_download_view(self):
        """Verifica la descarga directa del KuDE PDF binario."""
        self.client.force_login(self.user)
        url = reverse('invoicing:pdf', kwargs={'pk': self.factura.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF-1.4'))

    def test_factura_xml_download_view(self):
        """Verifica la descarga directa del archivo XML firmado digitalmente."""
        self.client.force_login(self.user)
        url = reverse('invoicing:xml', kwargs={'pk': self.factura.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response['Content-Type'])
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn(b'<rDE', response.content)
        self.assertIn(self.factura.cdc.encode('utf-8'), response.content)

    def test_factura_sifen_sync_ajax_success(self):
        """Verifica la sincronización AJAX del estado SIFEN vía POST."""
        self.client.force_login(self.user)
        url = reverse('invoicing:sync_sifen', kwargs={'pk': self.factura.pk})
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cdc'], self.factura.cdc)
        self.assertEqual(data['estado_sifen'], FacturaElectronica.EstadoSifen.APROBADO)
        self.assertTrue(data['is_approved'])
        self.assertIn('badge_html', data)

    def test_factura_sifen_sync_ajax_updates_cancelled_state(self):
        """Verifica que tras anular en el provider, el endpoint AJAX actualice la BD."""
        self.client.force_login(self.user)

        # Cancelar en el Mock provider
        self.provider.sol_cancelacion(self.factura.cdc, motivo='Error de facturación')

        url = reverse('invoicing:sync_sifen', kwargs={'pk': self.factura.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['estado_sifen'], FacturaElectronica.EstadoSifen.CANCELADO)
        self.assertTrue(data['is_cancelled'])

        # Verificar actualización en base de datos
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.estado_sifen, FacturaElectronica.EstadoSifen.CANCELADO)

    def test_factura_consulta_api_by_cdc(self):
        """Verifica la consulta pública vía REST API con CDC."""
        url = reverse('invoicing:consulta_api', kwargs={'identifier': self.factura.cdc})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cdc'], self.factura.cdc)
        self.assertEqual(data['numero_factura'], self.factura.numero_factura)
        self.assertIn('pdf_url', data['urls'])
        self.assertIn('xml_url', data['urls'])

    def test_factura_consulta_api_not_found(self):
        """Verifica 404 cuando no se encuentra el documento solicitado."""
        non_existent_cdc = '01800123457001001000000120261105999999999999'
        url = reverse('invoicing:consulta_api', kwargs={'identifier': non_existent_cdc})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data['success'])

    def test_transaction_kude_sync_sifen_endpoint(self):
        """Verifica el endpoint de sincronización SIFEN a nivel de transacción."""
        self.client.force_login(self.user)
        url = reverse('transactions:kude_sync_sifen', kwargs={'pk': self.tx.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cdc'], self.factura.cdc)
        self.assertIn('badge_html', data)

    def test_transaction_detail_renders_kude_integrated_card(self):
        """Verifica que el detalle de la transacción renderice la card integrada de KuDE."""
        self.client.force_login(self.user)
        url = reverse('transactions:detail', kwargs={'pk': self.tx.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Factura Electrónica e-Kuatia (KuDE)', content)
        self.assertIn(self.factura.numero_factura, content)
        self.assertIn('Descargar PDF', content)
        self.assertIn('Descargar XML', content)
        self.assertIn('btnSyncSifen', content)
        self.assertIn('copyCdcToClipboard', content)
        self.assertIn('syncSifenStatus', content)


class FacturaSeguraClientAndQuotaProtocolTests(TestCase):
    """
    Suite de pruebas para FacturaSeguraClient y Protocolo de Cuota con Reserva Blindada (SCRUM-120).
    """

    def setUp(self):
        super().setUp()
        self.client_fs = FacturaSeguraClient(
            api_url='https://apitest.facturasegura.com.py',
            email='demo@facturasegura.com.py',
            password='secret_password',
            emisor_ruc='80012345',
            timeout=10,
        )
        self.client_fs.reset_quotas(total=100)

    def tearDown(self):
        self.client_fs.reset_quotas(total=100)
        super().tearDown()

    def test_client_initialization_and_properties(self):
        """Verifica la configuración y propiedades por defecto de FacturaSeguraClient."""
        self.assertEqual(self.client_fs.api_url, 'https://apitest.facturasegura.com.py')
        self.assertEqual(self.client_fs.email, 'demo@facturasegura.com.py')
        self.assertEqual(self.client_fs.emisor_ruc, '80012345')
        self.assertEqual(self.client_fs.timeout, 10)
        self.assertEqual(self.client_fs.test_quota_reserved, 10)
        self.assertEqual(self.client_fs.total_quota, 100)
        self.assertEqual(self.client_fs.used_quota, 0)
        self.assertEqual(self.client_fs.test_quota_used, 0)
        self.assertEqual(self.client_fs.operational_quota_available, 90)
        self.assertEqual(self.client_fs.test_quota_available, 10)
        self.assertFalse(self.client_fs.is_operational_quota_exhausted)
        self.assertFalse(self.client_fs.is_test_quota_exhausted)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=False)
    def test_client_blocks_live_calls_when_live_disabled(self):
        """Verifica que todas las operaciones lancen LiveModeDisabledError si FACTURA_SEGURA_LIVE_ENABLED=False."""
        self.assertFalse(self.client_fs.is_live_enabled)

        with self.assertRaises(LiveModeDisabledError):
            self.client_fs.login()

        with self.assertRaises(LiveModeDisabledError):
            self.client_fs.calcular_de({'test': 1})

        with self.assertRaises(LiveModeDisabledError):
            self.client_fs.generar_de({'test': 1})

        with self.assertRaises(LiveModeDisabledError):
            self.client_fs.get_estado_sifen('01800123457001001000000122026110511234567890')

        with self.assertRaises(LiveModeDisabledError):
            self.client_fs.dwn_kude('01800123457001001000000122026110511234567890')

        with self.assertRaises(LiveModeDisabledError):
            self.client_fs.dwn_xml('01800123457001001000000122026110511234567890')

        with self.assertRaises(LiveModeDisabledError):
            self.client_fs.sol_cancelacion('01800123457001001000000122026110511234567890')

        with self.assertRaises(LiveModeDisabledError):
            self.client_fs.sol_inutilizacion(
                ruc_emisor='80012345',
                timbrado='12548963',
                est='001',
                pun_exp='001',
                num_doc='0000001',
            )

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_client_login_success(self):
        """Verifica la autenticación exitosa vía POST /login?include_auth_token."""
        login_resp = json.dumps({
            'meta': {'code': 200},
            'response': {
                'user': {'authentication_token': 'auth_token_mock_abc_123'},
            },
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = login_resp
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            token = self.client_fs.login()
            self.assertEqual(token, 'auth_token_mock_abc_123')
            self.assertEqual(self.client_fs.get_auth_token(), 'auth_token_mock_abc_123')

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_client_login_missing_credentials(self):
        """Verifica que login sin credenciales dispare InvoiceProviderError con código 401."""
        client_no_creds = FacturaSeguraClient(email='', password='')
        with self.assertRaises(InvoiceProviderError) as ctx:
            client_no_creds.login()
        self.assertEqual(ctx.exception.status_code, 401)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_client_calcular_de_flow(self):
        """Verifica la invocación formal de calcular_de y retorno del DE enriquecido."""
        self.client_fs._auth_token = 'token_test_123'
        resp_data = json.dumps({
            'code': 0,
            'description': 'OK',
            'results': [{'DE': {'dNumDoc': '0000001', 'dTotOpe': 550000, 'dTotIVA': 50000}}],
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = resp_data
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            res = self.client_fs.calcular_de({'dNumDoc': '0000001'})
            self.assertEqual(res['dTotOpe'], 550000)
            self.assertEqual(res['dTotIVA'], 50000)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_client_generar_de_flow(self):
        """Verifica la invocación formal de generar_de y obtención del CDC."""
        self.client_fs._auth_token = 'token_test_123'
        resp_data = json.dumps({
            'code': 0,
            'description': 'OK',
            'operation_info': {'id': 'fs-op-999'},
            'results': [{'CDC': '01800123457001001000000122026110511234567890'}],
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = resp_data
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            res = self.client_fs.generar_de({'dNumDoc': '0000001'})
            self.assertEqual(res['code'], 0)
            self.assertEqual(res['results'][0]['CDC'], '01800123457001001000000122026110511234567890')

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_client_get_estado_sifen_flow(self):
        """Verifica la consulta get_estado_sifen y deserialización del estado SIFEN."""
        self.client_fs._auth_token = 'token_test_123'
        resp_data = json.dumps({
            'code': 0,
            'description': 'OK',
            'results': [{
                'estado_sifen': 'Aprobado',
                'desc_sifen': '0260 - Aprobado',
                'error_sifen': '',
                'fch_sifen': '2026-11-05T12:00:00',
            }],
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = resp_data
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            res = self.client_fs.get_estado_sifen('01800123457001001000000122026110511234567890')
            self.assertEqual(res['code'], 0)
            self.assertEqual(res['results'][0]['estado_sifen'], 'Aprobado')

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_client_dwn_kude_flow(self):
        """Verifica la descarga de KuDE PDF vía GET."""
        self.client_fs._auth_token = 'token_test_123'
        cm = MagicMock()
        cm.read.return_value = b'%PDF-1.4 official KuDE bytes stream'
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            pdf_bytes = self.client_fs.dwn_kude('01800123457001001000000122026110511234567890')
            self.assertTrue(pdf_bytes.startswith(b'%PDF-1.4'))
            self.assertIn(b'official KuDE', pdf_bytes)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_client_dwn_xml_flow(self):
        """Verifica la descarga de XML firmado vía GET."""
        self.client_fs._auth_token = 'token_test_123'
        cm = MagicMock()
        cm.read.return_value = b'<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd"><dFecFirma>2026-11-05</dFecFirma></rDE>'
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            xml_str = self.client_fs.dwn_xml('01800123457001001000000122026110511234567890')
            self.assertIn('<rDE', xml_str)
            self.assertIn('http://ekuatia.set.gov.py/sifen/xsd', xml_str)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_client_sol_cancelacion_and_inutilizacion(self):
        """Verifica sol_cancelacion y sol_inutilizacion contra el PAC."""
        self.client_fs._auth_token = 'token_test_123'
        resp_data = json.dumps({'code': 0, 'description': 'OK'}).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = resp_data
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            res_can = self.client_fs.sol_cancelacion('01800123457001001000000122026110511234567890', motivo='Cancelación de prueba')
            self.assertEqual(res_can['code'], 0)

            res_inu = self.client_fs.sol_inutilizacion(
                ruc_emisor='80012345',
                timbrado='12548963',
                est='001',
                pun_exp='001',
                num_doc='0000001',
            )
            self.assertEqual(res_inu['code'], 0)

    # -------------------------------------------------------------------------
    # Pruebas del Protocolo de Cuota y Reserva Blindada (SCRUM-120)
    # -------------------------------------------------------------------------

    def test_quota_protocol_operational_consumption(self):
        """Verifica que el consumo de cuota comercial ordinaria descuente del saldo disponible."""
        # Total: 100, Reserva: 10 -> Inicialmente disponible: 90
        rem = self.client_fs.consume_quota(is_test=False)
        self.assertEqual(rem, 89)
        self.assertEqual(self.client_fs.used_quota, 1)
        self.assertEqual(self.client_fs.operational_quota_available, 89)
        self.assertEqual(self.client_fs.test_quota_available, 10)

    def test_quota_protocol_shield_strictly_blocks_at_threshold(self):
        """
        Verifica que al alcanzar el umbral presupuestario comercial (consumidas 90 de 100),
        las operaciones ordinarias sean estrictamente bloqueadas con QuotaShieldExhaustedError,
        blindando las 10 llamadas restantes para la presentación en vivo.
        """
        self.client_fs.reset_quotas(total=100)
        cfg = self.client_fs.get_db_config()
        if cfg:
            cfg.used_quota = 90
            cfg.save()
        else:
            FacturaSeguraClient._in_memory_used_quota = 90

        self.assertEqual(self.client_fs.operational_quota_available, 0)
        self.assertTrue(self.client_fs.is_operational_quota_exhausted)
        self.assertEqual(self.client_fs.test_quota_available, 10)

        with self.assertRaises(QuotaShieldExhaustedError) as ctx:
            self.client_fs.consume_quota(is_test=False)
        self.assertIn("blindadas exclusivamente para la presentación en vivo", str(ctx.exception))

    def test_quota_protocol_presentation_calls_allowed_within_shield(self):
        """
        Verifica que cuando la cuota operativa está agotada, las llamadas con
        is_presentation=True o is_test=True sean permitidas consumiendo de las 10 blindadas.
        """
        self.client_fs.reset_quotas(total=100)
        cfg = self.client_fs.get_db_config()
        if cfg:
            cfg.used_quota = 90
            cfg.save()
        else:
            FacturaSeguraClient._in_memory_used_quota = 90

        self.assertEqual(self.client_fs.operational_quota_available, 0)
        self.assertEqual(self.client_fs.test_quota_available, 10)

        rem = self.client_fs.consume_quota(is_presentation=True)
        self.assertEqual(rem, 9)
        self.assertEqual(self.client_fs.test_quota_used, 1)
        self.assertEqual(self.client_fs.test_quota_available, 9)

        rem2 = self.client_fs.consume_quota(is_test=True)
        self.assertEqual(rem2, 8)
        self.assertEqual(self.client_fs.test_quota_used, 2)
        self.assertEqual(self.client_fs.test_quota_available, 8)

    def test_quota_protocol_presentation_exhaustion_raises_error(self):
        """Verifica que al agotarse las 10 llamadas blindadas de presentación se dispare TestQuotaExhaustedError."""
        self.client_fs.reset_quotas(total=100)
        cfg = self.client_fs.get_db_config()
        if cfg:
            cfg.test_quota_used = 10
            cfg.save()
        else:
            FacturaSeguraClient._in_memory_test_used = 10

        self.assertEqual(self.client_fs.test_quota_available, 0)
        self.assertTrue(self.client_fs.is_test_quota_exhausted)

        with self.assertRaises(TestQuotaExhaustedError) as ctx:
            self.client_fs.consume_quota(is_presentation=True)
        self.assertIn("Reserva blindada de 10", str(ctx.exception))

    def test_quota_consultar_cuota_metrics(self):
        """Verifica que consultar_cuota() retorne todas las métricas requeridas."""
        data = self.client_fs.consultar_cuota()
        self.assertIn('total_quota', data)
        self.assertIn('used_quota', data)
        self.assertIn('operational_quota_available', data)
        self.assertIn('test_quota_reserved', data)
        self.assertIn('test_quota_used', data)
        self.assertIn('test_quota_available', data)
        self.assertIn('is_operational_quota_exhausted', data)
        self.assertIn('is_test_quota_exhausted', data)
        self.assertIn('shield_active', data)
        self.assertTrue(data['shield_active'])
        self.assertEqual(data['test_quota_reserved'], 10)

    def test_quota_reset_and_replenish(self):
        """Verifica reset_quotas y replenish_quota."""
        self.client_fs.consume_quota(is_test=False)
        self.client_fs.consume_quota(is_presentation=True)

        self.client_fs.reset_quotas(total=200)
        self.assertEqual(self.client_fs.total_quota, 200)
        self.assertEqual(self.client_fs.used_quota, 0)
        self.assertEqual(self.client_fs.test_quota_used, 0)
        self.assertEqual(self.client_fs.operational_quota_available, 190)

        self.client_fs.replenish_quota(50)
        self.assertEqual(self.client_fs.total_quota, 250)
        self.assertEqual(self.client_fs.operational_quota_available, 240)

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=True)
    def test_provider_enforces_shield_via_client(self):
        """
        Verifica que FacturaSeguraProvider aplique el blindaje de cuota y bloquee
        emisiones comerciales ordinarias cuando se alcanza el umbral de las 10 llamadas reservadas.
        """
        provider = FacturaSeguraProvider(
            email='test@example.com',
            password='pass',
            client=self.client_fs,
        )
        self.client_fs._auth_token = 'token_test_123'

        cfg = self.client_fs.get_db_config()
        if cfg:
            cfg.used_quota = 90
            cfg.save()
        else:
            FacturaSeguraClient._in_memory_used_quota = 90

        with self.assertRaises(QuotaShieldExhaustedError):
            provider.generar_de({'dNumDoc': '0000001'}, is_test=False)

        resp_data = json.dumps({
            'code': 0,
            'description': 'OK',
            'operation_info': {'id': 'fs-op-test'},
            'results': [{'CDC': '01800123457001001000000122026110511234567890'}],
        }).encode('utf-8')

        cm = MagicMock()
        cm.read.return_value = resp_data
        cm.__enter__.return_value = cm

        with patch('urllib.request.urlopen', return_value=cm):
            resp = provider.generar_de({'dNumDoc': '0000001'}, is_test=True)
            self.assertEqual(resp.cdc, '01800123457001001000000122026110511234567890')
            # generar_de + dwn_xml + dwn_kude ejecutan 3 llamadas al PAC
            self.assertEqual(self.client_fs.test_quota_used, 3)

