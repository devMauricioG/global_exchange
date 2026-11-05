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
from apps.invoicing.exceptions import (
    InvoiceNotFoundError,
    InvoiceProviderError,
    InvoiceValidationError,
    LiveModeDisabledError,
    QuotaExhaustedError,
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
