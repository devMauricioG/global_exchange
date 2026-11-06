"""Contrato SCRUM-125: las pruebas de facturación no deben abrir conexiones HTTP."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.invoicing.providers import MockInvoiceProvider, get_invoice_provider


class NoInvoiceApiCallsTests(SimpleTestCase):
    """Pruebas puras contra el provider local; cualquier HTTP las hace fallar."""

    def setUp(self):
        self.provider = MockInvoiceProvider()
        self.provider.reset_registry()

    @override_settings(FACTURA_SEGURA_LIVE_ENABLED=False)
    @patch('urllib.request.urlopen', side_effect=AssertionError('La suite no puede usar HTTP'))
    @patch('requests.sessions.Session.request', side_effect=AssertionError('La suite no puede usar HTTP'))
    def test_factory_and_mock_emit_without_network(self, request, urlopen):
        self.assertIsInstance(get_invoice_provider(), MockInvoiceProvider)

        response = self.provider.emitir_factura({
            'dNumDoc': '0000125',
            'cMoneOpe': 'PYG',
            'gCamItem': [{
                'dCantProSer': '1',
                'dPUniProSer': '125000',
                'iAfecIVA': '3',
            }],
        })

        self.assertTrue(response.es_simulada)
        self.assertTrue(response.cdc.isdigit())
        self.assertEqual(len(response.cdc), 44)
        request.assert_not_called()
        urlopen.assert_not_called()

    @patch('urllib.request.urlopen', side_effect=AssertionError('La suite no puede usar HTTP'))
    @patch('requests.sessions.Session.request', side_effect=AssertionError('La suite no puede usar HTTP'))
    def test_mock_downloads_are_generated_locally(self, request, urlopen):
        cdc = '01800123457001001000000122026110511234567890'

        self.assertTrue(self.provider.dwn_kude(cdc).startswith(b'%PDF-1.4'))
        self.assertIn(cdc, self.provider.dwn_xml(cdc))
        request.assert_not_called()
        urlopen.assert_not_called()
