"""
Implementación simulada de alta fidelidad: MockInvoiceProvider (SCRUM-117).

Garantiza la ejecución del 100% de las pruebas unitarias y el desarrollo local
sin consumir cuota real de la API de Factura Segura PAC ni del SIFEN.
Retorna CDCs válidos de 44 dígitos con Módulo 11 oficial, estados SIFEN Aprobado
y documentos KuDE (PDF) y XML locales representativos de la normativa paraguaya.
"""

from datetime import datetime
from decimal import Decimal
import hashlib
import json
import logging
from typing import Any, Dict, Optional, Tuple, Union
import uuid

from django.conf import settings
from django.utils import timezone

from ..calculators import calculate_de, compute_mod11_dv, generate_cdc
from ..exceptions import InvoiceNotFoundError, InvoiceValidationError
from ..types import EstadoSifenEnum, InvoiceResponse, StatusResponse
from .base import InvoiceProvider

logger = logging.getLogger(__name__)


def _generate_minimal_pdf(title: str, cdc: str, ruc: str, total: str, moneda: str) -> bytes:
    """
    Genera un archivo PDF 1.4 binario válido y autónomo representativo del KuDE.
    No requiere librerías binarias externas y es compatible con visualizadores PDF estándar.
    """
    content_lines = [
        "BT",
        "/F1 16 Tf",
        "50 780 Td",
        f"({title}) Tj",
        "/F1 10 Tf",
        "0 -25 Td",
        f"(RUC Emisor: {ruc} | Global Exchange S.A.) Tj",
        "0 -18 Td",
        f"(CDC SIFEN: {cdc}) Tj",
        "0 -18 Td",
        f"(Monto Total Liquidado: {total} {moneda}) Tj",
        "0 -18 Td",
        f"(Estado SIFEN: 0260 - Aprobado | KuDE Representativo) Tj",
        "0 -18 Td",
        f"(Fecha de Emision: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}) Tj",
        "0 -30 Td",
        "(Documento Tributario Electronico generado bajo entorno simulado MockInvoiceProvider) Tj",
        "ET",
    ]
    stream_data = "\n".join(content_lines).encode("latin1")
    stream_len = len(stream_data)

    objects = []
    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3: Page
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
    )
    # 4: Font
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    # 5: Contents
    objects.append(
        f"<< /Length {stream_len} >>\nstream\n".encode("latin1")
        + stream_data
        + b"\nendstream"
    )

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode("latin1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin1"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n".encode("latin1")
    )
    return bytes(pdf)


def _generate_canonical_xml(
    cdc: str,
    de_data: Dict[str, Any],
    fecha_iso: str,
) -> str:
    """
    Genera la estructura representativa XML firmada conforme al XSD de e-Kuatia (SIFEN).
    """
    timbrado = de_data.get('dNumTim', '12548963')
    num_doc = de_data.get('dNumDoc', '0000001')
    est = de_data.get('dEst', '001')
    pto = de_data.get('dPunExp', '001')
    ruc_em = de_data.get('dRucEm', '80012345')
    dv_em = de_data.get('dDVEmi', '7')
    nom_em = de_data.get('dNomEmi', 'GLOBAL EXCHANGE S.A.')
    ruc_rec = de_data.get('dRucRec', '44444401')
    dv_rec = de_data.get('dDVRec', '7')
    nom_rec = de_data.get('dNomRec', 'CLIENTE GLOBAL EXCHANGE')
    email_rec = de_data.get('dEmailRec', 'cliente@globalexchange.com.py')
    tot_gral = de_data.get('dTotGralOpe', '0')
    moneda = de_data.get('cMoneOpe', 'PYG')

    raw_sign = f"{cdc}|{fecha_iso}|{tot_gral}|{ruc_rec}"
    digest_val = hashlib.sha256(raw_sign.encode('utf-8')).hexdigest()
    sig_val = hashlib.sha512((raw_sign + "_MOCK_SECRET_KEY").encode('utf-8')).hexdigest()[:128]

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dVerForm>150</dVerForm>
  <DE Id="{cdc}">
    <dDVId>{cdc[-1] if len(cdc) == 44 else '0'}</dDVId>
    <dFecFirma>{fecha_iso}</dFecFirma>
    <dSisFact>1</dSisFact>
    <gOpeDE>
      <iTipEmi>1</iTipEmi>
      <dDesTipEmi>Normal</dDesTipEmi>
      <dCodSeg>{cdc[34:43] if len(cdc) == 44 else '123456789'}</dCodSeg>
    </gOpeDE>
    <gTimb>
      <iTiDE>1</iTiDE>
      <dDesTiDE>Factura Electrónica</dDesTiDE>
      <dNumTim>{timbrado}</dNumTim>
      <dEst>{est}</dEst>
      <dPunExp>{pto}</dPunExp>
      <dNumDoc>{num_doc}</dNumDoc>
      <dFeIniT>{fecha_iso[:10]}</dFeIniT>
    </gTimb>
    <gDatGralOpe>
      <dFeEmiDE>{fecha_iso}</dFeEmiDE>
      <gEmis>
        <dRucEm>{ruc_em}</dRucEm>
        <dDVEmi>{dv_em}</dDVEmi>
        <iTipCont>2</iTipCont>
        <dNomEmi>{nom_em}</dNomEmi>
        <dDirEmi>{de_data.get('dDirEmi', 'Av. Mariscal Lopez 1234')}</dDirEmi>
        <dEmailE>{de_data.get('dEmailE', 'facturacion@globalexchange.com.py')}</dEmailE>
      </gEmis>
      <gDatRec>
        <iNatRec>{de_data.get('iNatRec', '1')}</iNatRec>
        <iTiOpe>{de_data.get('iTiOpe', '1')}</iTiOpe>
        <cPaisRec>{de_data.get('cPaisRec', 'PRY')}</cPaisRec>
        <dRucRec>{ruc_rec}</dRucRec>
        <dDVRec>{dv_rec}</dDVRec>
        <dNomRec>{nom_rec}</dNomRec>
        <dEmailRec>{email_rec}</dEmailRec>
      </gDatRec>
    </gDatGralOpe>
    <gTotSub>
      <dSubExe>{de_data.get('dSubExe', '0')}</dSubExe>
      <dSubExo>{de_data.get('dSubExo', '0')}</dSubExo>
      <dSub5>{de_data.get('dSub5', '0')}</dSub5>
      <dSub10>{de_data.get('dSub10', '0')}</dSub10>
      <dTotOpe>{de_data.get('dTotOpe', tot_gral)}</dTotOpe>
      <dTotDesc>{de_data.get('dTotDesc', '0')}</dTotDesc>
      <dTotGralOpe>{tot_gral}</dTotGralOpe>
      <dIVA5>{de_data.get('dIVA5', '0')}</dIVA5>
      <dIVA10>{de_data.get('dIVA10', '0')}</dIVA10>
      <dTotIVA>{de_data.get('dTotIVA', '0')}</dTotIVA>
      <cMoneOpe>{moneda}</cMoneOpe>
    </gTotSub>
  </DE>
  <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
    <SignedInfo>
      <CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
      <SignatureMethod Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
      <Reference URI="#{cdc}">
        <DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
        <DigestValue>{digest_val}</DigestValue>
      </Reference>
    </SignedInfo>
    <SignatureValue>{sig_val}</SignatureValue>
    <KeyInfo>
      <X509Data>
        <X509SubjectName>CN=GLOBAL EXCHANGE S.A., OU=Certificado Mock SIFEN, C=PY</X509SubjectName>
      </X509Data>
    </KeyInfo>
  </Signature>
</rDE>"""
    return xml.strip()


class MockInvoiceProvider(InvoiceProvider):
    """
    Proveedor simulado para Facturación Electrónica e-Kuatia / SIFEN.

    Diseñado para pruebas automatizadas y desarrollo local:
    - 0 consumo de cuota comercial o de pruebas en el PAC.
    - Respuestas sincrónicas instantáneas.
    - Registro en memoria de documentos emitidos y cancelados para verificación en tests.
    """

    def __init__(self):
        # Almacén en memoria para CDC -> metadatos (útil para aserciones de tests)
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._cancelled_cdcs: set = set()
        self._voided_documents: set = set()

    def reset_registry(self) -> None:
        """Limpia el registro de facturas emitidas y estados simulados."""
        self._registry.clear()
        self._cancelled_cdcs.clear()
        self._voided_documents.clear()

    def calcular_de(self, de_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula los campos numéricos e impositivos utilizando el motor matemático SIFEN.
        """
        if not isinstance(de_data, dict):
            raise InvoiceValidationError("El parámetro de_data debe ser un diccionario JSON válido.")
        return calculate_de(de_data)

    def generar_de(self, de_data: Dict[str, Any], is_test: bool = False) -> InvoiceResponse:
        """
        Genera un DTE simulado retornando un CDC de 44 dígitos estrictamente válido.
        """
        if not isinstance(de_data, dict):
            raise InvoiceValidationError("de_data debe ser un diccionario.")

        # Asegurar cálculo de campos matemáticos
        calculated = self.calcular_de(de_data)

        # Generar CDC si no viene especificado o si es '0'
        cdc = calculated.get('CDC')
        if not cdc or cdc == '0' or len(str(cdc)) != 44:
            cdc = generate_cdc(
                tipo_documento=calculated.get('iTiDE', '01'),
                ruc_emisor=calculated.get('dRucEm', '80012345'),
                dv_emisor=calculated.get('dDVEmi', '7'),
                establecimiento=calculated.get('dEst', '001'),
                punto_expedicion=calculated.get('dPunExp', '001'),
                numero_documento=calculated.get('dNumDoc', '0000001'),
                tipo_contribuyente=calculated.get('iTipCont', '2'),
                tipo_emision=calculated.get('iTipEmi', '1'),
            )
            calculated['CDC'] = cdc

        num_doc = str(calculated.get('dNumDoc', '0000001')).zfill(7)
        est = str(calculated.get('dEst', '001')).zfill(3)
        pto = str(calculated.get('dPunExp', '001')).zfill(3)
        numero_factura = f"{est}-{pto}-{num_doc}"

        now = timezone.now()
        fecha_iso = now.strftime('%Y-%m-%dT%H:%M:%S')
        protocolo = f"SIFEN-MOCK-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        xml_firmado = _generate_canonical_xml(cdc, calculated, fecha_iso)
        kude_bytes = _generate_minimal_pdf(
            title="KuDE - Factura Electronica",
            cdc=cdc,
            ruc=calculated.get('dRucEm', '80012345'),
            total=calculated.get('dTotGralOpe', '0'),
            moneda=calculated.get('cMoneOpe', 'PYG'),
        )
        qr_url = f"https://ekuatia.set.gov.py/consultas/qr?nVersion=150&Id={cdc}&dTotGralOpe={calculated.get('dTotGralOpe', '0')}"

        resp = InvoiceResponse(
            cdc=cdc,
            numero_factura=numero_factura,
            estado='APROBADO',
            estado_sifen=EstadoSifenEnum.APROBADO.value,
            desc_sifen='0260 - Aprobado',
            protocolo=protocolo,
            fecha_emision=now,
            xml_firmado=xml_firmado,
            kude_pdf_bytes=kude_bytes,
            qr_data=qr_url,
            raw_response={
                'code': 0,
                'description': 'OK',
                'operation_info': {'id': str(uuid.uuid4())},
                'results': [{'CDC': cdc}],
            },
            es_simulada=True,
        )

        # Almacenar en registro en memoria
        self._registry[cdc] = {
            'response': resp,
            'de_data': calculated,
            'fecha_registro': now,
        }

        logger.info("MockInvoiceProvider: DTE simulado generado exitosamente. CDC=%s", cdc)
        return resp

    def get_estado_sifen(self, cdc: str, ruc_emisor: Optional[str] = None) -> StatusResponse:
        """
        Retorna el estado de aprobación en SIFEN para el CDC consultado.
        """
        cdc_clean = str(cdc).strip()
        now_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

        if cdc_clean in self._cancelled_cdcs:
            return StatusResponse(
                cdc=cdc_clean,
                estado_sifen=EstadoSifenEnum.CANCELADO.value,
                desc_sifen='Documento Cancelado en SIFEN',
                fch_sifen=now_str,
                estado_can='Aprobado',
                desc_can='Evento de cancelacion aprobado',
                fch_can=now_str,
                raw_response={
                    'code': 0,
                    'description': 'OK',
                    'operation_info': {'id': str(uuid.uuid4())},
                    'results': [{
                        'estado_sifen': EstadoSifenEnum.CANCELADO.value,
                        'desc_sifen': 'Documento Cancelado',
                        'estado_can': 'Aprobado',
                        'fch_sifen': now_str,
                    }],
                },
            )

        return StatusResponse(
            cdc=cdc_clean,
            estado_sifen=EstadoSifenEnum.APROBADO.value,
            desc_sifen='0260 - Aprobado',
            fch_sifen=now_str,
            estado_can='',
            desc_can='',
            estado_inu='',
            desc_inu='',
            raw_response={
                'code': 0,
                'description': 'OK',
                'operation_info': {'id': str(uuid.uuid4())},
                'results': [{
                    'estado_sifen': 'Aprobado',
                    'desc_sifen': '0260 - Aprobado',
                    'error_sifen': '',
                    'fch_sifen': now_str,
                    'estado_can': '',
                    'desc_can': '',
                    'estado_inu': '',
                    'desc_inu': '',
                }],
            },
        )

    def sol_cancelacion(
        self,
        cdc: str,
        motivo: str = '',
        ruc_emisor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Registra la cancelación simulada del documento electrónico.
        """
        cdc_clean = str(cdc).strip()
        self._cancelled_cdcs.add(cdc_clean)
        if cdc_clean in self._registry:
            self._registry[cdc_clean]['response'].estado = 'CANCELADO'
            self._registry[cdc_clean]['response'].estado_sifen = EstadoSifenEnum.CANCELADO.value

        return {
            'code': 0,
            'description': 'OK',
            'operation_info': {'id': str(uuid.uuid4())},
            'results': [],
        }

    def sol_inutilizacion(
        self,
        ruc_emisor: str,
        timbrado: str,
        est: str,
        pun_exp: str,
        num_doc: str,
        tipo_de: str = '1',
    ) -> Dict[str, Any]:
        """
        Registra la solicitud de inutilización de un rango de comprobantes en el simulador.
        """
        doc_key = f"{ruc_emisor}-{timbrado}-{est}-{pun_exp}-{num_doc}"
        self._voided_documents.add(doc_key)
        return {
            'code': 0,
            'description': 'OK',
            'operation_info': {'id': str(uuid.uuid4())},
            'results': [],
        }

    def dwn_kude(self, cdc: str, ruc_emisor: Optional[str] = None) -> bytes:
        """
        Retorna los bytes representativos del archivo KuDE PDF.
        """
        cdc_clean = str(cdc).strip()
        if cdc_clean in self._registry:
            return self._registry[cdc_clean]['response'].kude_pdf_bytes

        # Si no fue emitido en esta sesión, generar PDF bajo demanda con el CDC recibido
        return _generate_minimal_pdf(
            title="KuDE - Factura Electronica",
            cdc=cdc_clean,
            ruc=ruc_emisor or '80012345',
            total='0',
            moneda='PYG',
        )

    def dwn_xml(self, cdc: str, ruc_emisor: Optional[str] = None) -> str:
        """
        Retorna el archivo XML firmado correspondiente al CDC.
        """
        cdc_clean = str(cdc).strip()
        if cdc_clean in self._registry:
            return self._registry[cdc_clean]['response'].xml_firmado

        # Generar XML bajo demanda representativo
        mock_de = {
            'CDC': cdc_clean,
            'dRucEm': ruc_emisor or '80012345',
            'dDVEmi': compute_mod11_dv(ruc_emisor or '80012345'),
            'dNumDoc': cdc_clean[17:24] if len(cdc_clean) == 44 else '0000001',
            'dEst': cdc_clean[11:14] if len(cdc_clean) == 44 else '001',
            'dPunExp': cdc_clean[14:17] if len(cdc_clean) == 44 else '001',
            'dTotGralOpe': '0',
            'cMoneOpe': 'PYG',
        }
        return _generate_canonical_xml(cdc_clean, mock_de, timezone.now().strftime('%Y-%m-%dT%H:%M:%S'))

    def emitir_factura(self, transaction_or_data: Any, is_test: bool = False) -> InvoiceResponse:
        """
        Emite una factura electrónica mapeando los campos desde una Transacción o diccionario.
        """
        # Si es un diccionario, delegar directamente a generar_de
        if isinstance(transaction_or_data, dict):
            return self.generar_de(transaction_or_data, is_test=is_test)

        # Mapeo desde modelo Transaction de Django
        tx = transaction_or_data
        cliente = getattr(tx, 'cliente', None)

        ruc_cliente_full = getattr(cliente, 'documento_ruc', '44444401-7')
        if '-' in ruc_cliente_full:
            ruc_rec, dv_rec = ruc_cliente_full.split('-', 1)
        else:
            ruc_rec = ruc_cliente_full
            dv_rec = compute_mod11_dv(ruc_rec)

        moneda_cod = getattr(tx.target_currency, 'code', 'PYG')
        monto_total = str(tx.monto_destino)
        tasa_neta = str(tx.tasa_neta)
        seq_num = str(tx.id).zfill(7)

        de_data = {
            'iTipEmi': '1',
            'iTiDE': '1',
            'dNumTim': getattr(settings, 'FACTURA_SEGURA_EMISOR_TIMBRADO', '12548963'),
            'dEst': '001',
            'dPunExp': '001',
            'dNumDoc': seq_num,
            'cMoneOpe': moneda_cod if moneda_cod in ('PYG', 'USD') else 'PYG',
            'dTiCam': str(getattr(tx, 'tasa_neta', '1')),
            'dRucEm': getattr(settings, 'FACTURA_SEGURA_EMISOR_RUC', '80012345'),
            'dDVEmi': getattr(settings, 'FACTURA_SEGURA_EMISOR_DV', '7'),
            'dNomEmi': 'GLOBAL EXCHANGE S.A.',
            'dDirEmi': 'Av. Mariscal Lopez 1234, Asuncion',
            'dRucRec': ruc_rec,
            'dDVRec': dv_rec,
            'dNomRec': getattr(cliente, 'nombre', 'Cliente Consumidor Final'),
            'dEmailRec': getattr(cliente, 'correo', 'cliente@globalexchange.com.py'),
            'iCondOpe': '1',
            'gPaConEIni': [
                {
                    'iTiPago': '1',
                    'dMonTiPag': monto_total,
                    'cMoneTiPag': moneda_cod if moneda_cod in ('PYG', 'USD') else 'PYG',
                    'dTiCamTiPag': '1',
                }
            ],
            'gCamItem': [
                {
                    'dCodInt': getattr(tx, 'codigo_referencia', f'TX-{seq_num}'),
                    'dDesProSer': f'Operacion cambiaria {getattr(tx, "tipo_operacion", "CAMBIO")}',
                    'cUniMed': '77',
                    'dCantProSer': '1',
                    'dPUniProSer': monto_total,
                    'dDescItem': '0',
                    'iAfecIVA': '3',  # Exenta para cambio de divisas según Art 100 Ley 6380
                    'dPropIVA': '0',
                    'dTasaIVA': '0',
                }
            ],
        }

        return self.generar_de(de_data, is_test=is_test)
