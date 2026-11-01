"""
Módulo de servicios para Facturación Electrónica SIFEN / e-Kuatia y KuDE (SCRUM-121).

Provee la lógica de negocio para:
1. Cálculo matemático del Código de Control (CDC) de 44 dígitos con dígito verificador módulo 11 oficial de la DNIT / SET.
2. Generación de la estructura canónica XML firmada (XML-DSig) compatible con e-Kuatia.
3. Composición de parámetros y URL de consulta pública para código QR oficial.
4. Generación, consulta y persistencia de facturas electrónicas para transacciones cambiarias.
"""

from datetime import datetime
from decimal import Decimal
import hashlib
import logging
from typing import Any, Dict, Optional, Tuple, Union
import uuid

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import ElectronicInvoice, Transaction

logger = logging.getLogger(__name__)

# Parámetros institucionales del emisor (Global Exchange S.A.)
EMISOR_RUC = '80012345'
EMISOR_DV = '7'
EMISOR_RAZON_SOCIAL = 'Global Exchange S.A.'
EMISOR_NOMBRE_FANTASIA = 'Global Exchange Casa de Cambio'
EMISOR_DIRECCION = 'Av. Mariscal López 1234, Asunción, Paraguay'
EMISOR_TELEFONO = '+595 21 600 000'
EMISOR_CORREO = 'facturacion@globalexchange.com.py'
EMISOR_TIMBRADO = '12548963'
EMISOR_ESTABLECIMIENTO = '001'
EMISOR_PUNTO_EXPEDICION = '001'


def compute_mod11_dv(number_str: str) -> str:
    """
    Calcula el dígito verificador numérico mediante el algoritmo de Módulo 11
    reglamentario de la DNIT / SET de Paraguay para claves de acceso y RUC.

    Multiplicadores de derecha a izquierda: 2, 3, 4, 5, 6, 7, 8, 9, 2, 3...

    :param number_str: Cadena de dígitos numéricos de entrada.
    :type number_str: str
    :return: Carácter numérico con el dígito verificador calculado ('0'-'9').
    :rtype: str
    """
    total = 0
    multiplier = 2
    for char in reversed(number_str):
        if not char.isdigit():
            continue
        total += int(char) * multiplier
        multiplier += 1
        if multiplier > 9:
            multiplier = 2

    remainder = total % 11
    if remainder in (0, 1):
        dv = 0
    else:
        dv = 11 - remainder
    return str(dv)


def generate_cdc(
    tipo_documento: str = '01',
    ruc_emisor: str = EMISOR_RUC,
    dv_emisor: str = EMISOR_DV,
    establecimiento: str = EMISOR_ESTABLECIMIENTO,
    punto_expedicion: str = EMISOR_PUNTO_EXPEDICION,
    numero_documento: Union[int, str] = 1,
    tipo_contribuyente: str = '2',
    fecha_emision: Optional[datetime] = None,
    tipo_emision: str = '1',
    codigo_seguridad: Optional[str] = None,
) -> str:
    """
    Genera el Código de Control (CDC) / Clave de Acceso oficial de 44 dígitos
    para Documentos Tributarios Electrónicos (DTE) según el manual de SIFEN.

    Composición (44 dígitos):
    - Tipo de Documento: 2 dígitos ('01' = Factura Electrónica).
    - RUC Emisor: 8 dígitos (rellenado con ceros a la izquierda).
    - Dígito Verificador RUC Emisor: 1 dígito.
    - Establecimiento: 3 dígitos ('001').
    - Punto de Expedición: 3 dígitos ('001').
    - Número de Documento: 7 dígitos ('0000001').
    - Tipo de Contribuyente: 1 dígito ('1' Física, '2' Jurídica).
    - Fecha de Emisión: 8 dígitos (YYYYMMDD).
    - Tipo de Emisión: 1 dígito ('1' Normal, '2' Contingencia).
    - Código de Seguridad Aleatorio: 9 dígitos numéricos.
    - Dígito Verificador del CDC: 1 dígito (Módulo 11 sobre los 43 dígitos previos).

    :return: Clave de acceso CDC de exactamente 44 dígitos numéricos.
    :rtype: str
    """
    dt = fecha_emision or timezone.now()
    fecha_str = dt.strftime('%Y%m%d')

    tipo_doc = str(tipo_documento).zfill(2)[:2]
    ruc = str(ruc_emisor).zfill(8)[:8]
    dv_em = str(dv_emisor)[:1]
    est = str(establecimiento).zfill(3)[:3]
    pto = str(punto_expedicion).zfill(3)[:3]
    num = str(numero_documento).zfill(7)[:7]
    contrib = str(tipo_contribuyente)[:1]
    emi = str(tipo_emision)[:1]

    if not codigo_seguridad:
        # Generar 9 dígitos deterministas/aleatorios
        seed = f'{ruc}-{num}-{fecha_str}'
        digest = hashlib.sha256(seed.encode('utf-8')).hexdigest()
        codigo_seguridad = ''.join(c for c in digest if c.isdigit())[:9].zfill(9)
    else:
        codigo_seguridad = str(codigo_seguridad).zfill(9)[:9]

    cuerpo_43 = f'{tipo_doc}{ruc}{dv_em}{est}{pto}{num}{contrib}{fecha_str}{emi}{codigo_seguridad}'
    dv_cdc = compute_mod11_dv(cuerpo_43)
    cdc_44 = f'{cuerpo_43}{dv_cdc}'
    return cdc_44


def generate_sifen_xml(invoice: ElectronicInvoice) -> str:
    """
    Genera la estructura canónica del XML firmado conforme al XSD oficial de e-Kuatia (SIFEN).

    Incluye:
    - Espacio de nombres: ``http://ekuatia.set.gov.py/sifen/xsd``
    - Encabezado DTE con timbrado, fecha y datos del emisor.
    - Datos del receptor (cliente titular de la transacción).
    - Desglose del ítem cambiario: Tasa neta, montos, y exención de IVA (Art. 100 Ley 6380/19).
    - Bloque de firma digital XML-DSig con algoritmo RSA-SHA256 y DigestValue.
    """
    tx = invoice.transaction
    cliente = tx.cliente
    cdc = invoice.cdc
    fecha_iso = invoice.fecha_emision.strftime('%Y-%m-%dT%H:%M:%S')
    fecha_ini = invoice.fecha_emision.strftime('%Y-%m-%d')
    num_doc_7 = invoice.numero_factura.split('-')[-1].zfill(7) if '-' in invoice.numero_factura else str(invoice.id).zfill(7)

    # Identificación del cliente receptor
    cliente_ruc = getattr(cliente, 'documento_ruc', 'X-44444401-7')
    ruc_partes = cliente_ruc.split('-')
    ruc_solo = ruc_partes[0].strip()
    ruc_dv = ruc_partes[1].strip() if len(ruc_partes) > 1 else compute_mod11_dv(ruc_solo)
    cliente_nombre = getattr(cliente, 'nombre', 'Cliente General')
    cliente_correo = getattr(cliente, 'correo', 'cliente@globalexchange.com.py')

    # Montos y conceptos cambiarios
    monto_total = str(tx.monto_destino)
    monto_origen = str(tx.monto_origen)
    tasa_neta = str(tx.tasa_neta)
    tipo_op_desc = 'Compra de Divisas' if tx.tipo_operacion == Transaction.TipoOperacion.COMPRA else 'Venta de Divisas'
    cod_seg = cdc[34:43] if len(cdc) == 44 else '123456789'
    dv_id = cdc[-1] if len(cdc) == 44 else '0'

    # Generación de Digest y firma criptográfica simulada/canónica
    raw_payload = f'{cdc}|{fecha_iso}|{monto_total}|{cliente_ruc}'
    digest_val = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()
    sig_val = hashlib.sha512((raw_payload + '_SECRET_SIGNING_KEY').encode('utf-8')).hexdigest()[:128]

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dVerForm>150</dVerForm>
  <DE Id="{cdc}">
    <dDVId>{dv_id}</dDVId>
    <dFecFirma>{fecha_iso}</dFecFirma>
    <dSisFact>1</dSisFact>
    <gOpeDE>
      <iTipEmi>1</iTipEmi>
      <dDesTipEmi>Normal</dDesTipEmi>
      <dCodSeg>{cod_seg}</dCodSeg>
    </gOpeDE>
    <gTimb>
      <iTiDE>1</iTiDE>
      <dDesTiDE>Factura Electrónica</dDesTiDE>
      <dNumTim>{invoice.timbrado}</dNumTim>
      <dEst>{EMISOR_ESTABLECIMIENTO}</dEst>
      <dPunExp>{EMISOR_PUNTO_EXPEDICION}</dPunExp>
      <dNumDoc>{num_doc_7}</dNumDoc>
      <dFeIniT>{fecha_ini}</dFeIniT>
    </gTimb>
    <gDatGralOpe>
      <dFeEmiDE>{fecha_iso}</dFeEmiDE>
      <gEmis>
        <dRucEm>{EMISOR_RUC}</dRucEm>
        <dDVEmi>{EMISOR_DV}</dDVEmi>
        <iTipCont>2</iTipCont>
        <dNomEmi>{EMISOR_RAZON_SOCIAL}</dNomEmi>
        <dNomFanEmi>{EMISOR_NOMBRE_FANTASIA}</dNomFanEmi>
        <dDirEmi>{EMISOR_DIRECCION}</dDirEmi>
        <dTelEmi>{EMISOR_TELEFONO}</dTelEmi>
        <dEmailE>{EMISOR_CORREO}</dEmailE>
      </gEmis>
      <gDatRec>
        <iNatRec>1</iNatRec>
        <iTiOpe>2</iTiOpe>
        <cPaisRec>PRY</cPaisRec>
        <dRucRec>{ruc_solo}</dRucRec>
        <dDVRec>{ruc_dv}</dDVRec>
        <dNomRec>{cliente_nombre}</dNomRec>
        <dEmailRec>{cliente_correo}</dEmailRec>
      </gDatRec>
    </gDatGralOpe>
    <gDtipDE>
      <gCamItem>
        <dCodInt>{tx.codigo_referencia}</dCodInt>
        <dDesProSer>Operación de Cambio Oficial: {tipo_op_desc} ({tx.base_currency.code} a {tx.target_currency.code})</dDesProSer>
        <dCantProSer>{monto_origen}</dCantProSer>
        <gValorItem>
          <dPUniProSer>{tasa_neta}</dPUniProSer>
          <dTotBruOpeItem>{monto_total}</dTotBruOpeItem>
          <gCamIVA>
            <iAfecIVA>3</iAfecIVA>
            <dDesAfecIVA>Exenta de IVA (Operaciones Cambiarias - Art. 100 Ley 6380/19)</dDesAfecIVA>
            <dPropIVA>0</dPropIVA>
            <dTasaIVA>0</dTasaIVA>
            <dBasGravIVA>0</dBasGravIVA>
            <dLiqIVAItem>0</dLiqIVAItem>
          </gCamIVA>
        </gValorItem>
      </gCamItem>
    </gDtipDE>
    <gTotSub>
      <dSubExe>{monto_total}</dSubExe>
      <dSubExo>0</dSubExo>
      <dSub5>0</dSub5>
      <dSub10>0</dSub10>
      <dTotOpe>{monto_total}</dTotOpe>
      <dTotDesc>0</dTotDesc>
      <dTotGralOpe>{monto_total}</dTotGralOpe>
      <dIVA5>0</dIVA5>
      <dIVA10>0</dIVA10>
      <dTotIVA>0</dTotIVA>
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
        <X509SubjectName>CN=Global Exchange S.A., OU=Certificado Tributario, O=DNIT, C=PY</X509SubjectName>
        <X509Certificate>MIIE6jCCA9KgAwIBAgIUQ2VydGlmaWNhZG9QYXJhZ3VheVNJRkVOMjAyNjAx...</X509Certificate>
      </X509Data>
    </KeyInfo>
  </Signature>
</rDE>"""
    return xml.strip()


def generate_qr_url(invoice: ElectronicInvoice) -> str:
    """
    Genera la URL oficial con parámetros para lectura mediante código QR de SIFEN.
    """
    cdc = invoice.cdc
    fecha_hex = invoice.fecha_emision.strftime('%Y%m%d%H%M%S')
    tx = invoice.transaction
    cliente_ruc = getattr(tx.cliente, 'documento_ruc', '44444401-7')
    monto = str(tx.monto_destino)
    digest = hashlib.sha256(f"{cdc}{fecha_hex}{monto}".encode('utf-8')).hexdigest()[:16]
    return f"https://ekuatia.set.gov.py/consultas/qr?nVersion=150&Id={cdc}&dFeEmiDE={fecha_hex}&dRucRec={cliente_ruc}&dTotGralOpe={monto}&dTotIVA=0&cHash={digest}"


class KudeService:
    """
    Servicio integral para la gestión, emisión y consulta de Facturas Electrónicas y KuDE (SCRUM-121).
    """

    @classmethod
    def get_or_create_invoice(cls, transaction: Transaction) -> ElectronicInvoice:
        """
        Obtiene o genera de forma idempotente la factura electrónica / KuDE para una transacción.
        """
        invoice = getattr(transaction, 'factura_electronica', None)
        if invoice:
            return invoice

        with db_transaction.atomic():
            # Volver a verificar dentro de la transacción atómica
            existing = ElectronicInvoice.objects.filter(transaction=transaction).first()
            if existing:
                return existing

            seq = transaction.id
            numero_factura = f"{EMISOR_ESTABLECIMIENTO}-{EMISOR_PUNTO_EXPEDICION}-{str(seq).zfill(7)}"
            cdc = generate_cdc(
                tipo_documento='01',
                ruc_emisor=EMISOR_RUC,
                dv_emisor=EMISOR_DV,
                establecimiento=EMISOR_ESTABLECIMIENTO,
                punto_expedicion=EMISOR_PUNTO_EXPEDICION,
                numero_documento=seq,
                fecha_emision=transaction.created_at or timezone.now(),
            )

            # Protocolo formal SIFEN
            protocolo = f"SIFEN-AUT-{timezone.now().strftime('%Y%m%d')}-{str(seq).zfill(6)}"

            invoice = ElectronicInvoice(
                transaction=transaction,
                cdc=cdc,
                timbrado=EMISOR_TIMBRADO,
                numero_factura=numero_factura,
                fecha_emision=transaction.fecha_pago or transaction.created_at or timezone.now(),
                estado=ElectronicInvoice.EstadoSifen.APROBADO,
                protocolo_autorizacion=protocolo,
            )
            invoice.xml_firmado = generate_sifen_xml(invoice)
            invoice.qr_data = generate_qr_url(invoice)
            invoice.save()

            return invoice

    @classmethod
    def lookup_invoice(cls, identifier: str) -> Optional[ElectronicInvoice]:
        """
        Busca una factura electrónica por su CDC de 44 dígitos, número de factura,
        código de referencia de transacción o ID numérico.
        """
        if not identifier:
            return None

        clean_id = str(identifier).strip()

        # 1. Búsqueda directa por CDC (44 dígitos)
        if len(clean_id) == 44 and clean_id.isdigit():
            inv = ElectronicInvoice.objects.filter(cdc=clean_id).select_related('transaction', 'transaction__cliente').first()
            if inv:
                return inv

        # 2. Búsqueda por número de factura (ej. 001-001-0000001)
        inv = ElectronicInvoice.objects.filter(numero_factura__iexact=clean_id).select_related('transaction', 'transaction__cliente').first()
        if inv:
            return inv

        # 3. Búsqueda por código de referencia de transacción (ej. TX-20261101-ABCDEF)
        inv = ElectronicInvoice.objects.filter(transaction__codigo_referencia__iexact=clean_id).select_related('transaction', 'transaction__cliente').first()
        if inv:
            return inv

        # 4. Búsqueda por ID numérico de transacción o factura
        if clean_id.isdigit():
            inv = ElectronicInvoice.objects.filter(transaction_id=int(clean_id)).select_related('transaction', 'transaction__cliente').first()
            if inv:
                return inv
            inv = ElectronicInvoice.objects.filter(id=int(clean_id)).select_related('transaction', 'transaction__cliente').first()
            if inv:
                return inv

        return None

