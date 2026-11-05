"""
Motor de cálculo matemático y composición de CDC conforme a SIFEN / e-Kuatia (SCRUM-117).

Implementa con exactitud matemática las fórmulas de liquidación del IVA, bases imponibles,
exenciones, subtotales y clave de acceso (CDC de 44 dígitos) especificadas en el manual
técnico 'API de Factura Segura para ESI v01' (páginas 17-21 y 33-40).
"""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union

from django.utils import timezone


def compute_mod11_dv(number_str: str) -> str:
    """
    Calcula el dígito verificador numérico mediante el algoritmo de Módulo 11
    reglamentario de la DNIT / SET de Paraguay para claves de acceso (CDC) y RUC.

    Multiplicadores de derecha a izquierda: 2, 3, 4, 5, 6, 7, 8, 9, 2, 3...

    :param number_str: Cadena de dígitos numéricos de entrada.
    :return: Carácter numérico con el dígito verificador ('0'-'9').
    """
    total = 0
    multiplier = 2
    for char in reversed(str(number_str)):
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
    ruc_emisor: str = '80012345',
    dv_emisor: str = '7',
    establecimiento: str = '001',
    punto_expedicion: str = '001',
    numero_documento: Union[int, str] = 1,
    tipo_contribuyente: str = '2',
    fecha_emision: Optional[datetime] = None,
    tipo_emision: str = '1',
    codigo_seguridad: Optional[str] = None,
) -> str:
    """
    Genera el Código de Control (CDC) / Clave de Acceso oficial de 44 dígitos
    para Documentos Tributarios Electrónicos (DTE) según el manual de SIFEN.

    Composición (44 dígitos exactos):
    1.  Tipo de Documento: 2 dígitos ('01' = Factura Electrónica, '05' = Nota de Crédito).
    2.  RUC Emisor: 8 dígitos numéricos (rellenado con ceros a la izquierda).
    3.  Dígito Verificador RUC Emisor: 1 dígito numérico.
    4.  Establecimiento: 3 dígitos numéricos ('001').
    5.  Punto de Expedición: 3 dígitos numéricos ('001').
    6.  Número de Documento: 7 dígitos numéricos ('0000001').
    7.  Tipo de Contribuyente: 1 dígito ('1' Persona Física, '2' Persona Jurídica).
    8.  Fecha de Emisión: 8 dígitos numéricos en formato YYYYMMDD.
    9.  Tipo de Emisión: 1 dígito ('1' Normal, '2' Contingencia).
    10. Código de Seguridad Aleatorio: 9 dígitos numéricos.
    11. Dígito Verificador del CDC: 1 dígito numérico (Módulo 11 sobre los 43 dígitos previos).

    :return: Clave de acceso CDC de exactamente 44 dígitos numéricos.
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
        seed = f"{ruc}-{num}-{fecha_str}"
        digest = hashlib.sha256(seed.encode('utf-8')).hexdigest()
        codigo_seguridad = ''.join(c for c in digest if c.isdigit())[:9].zfill(9)
    else:
        codigo_seguridad = str(codigo_seguridad).zfill(9)[:9]

    cuerpo_43 = f"{tipo_doc}{ruc}{dv_em}{est}{pto}{num}{contrib}{fecha_str}{emi}{codigo_seguridad}"
    dv_cdc = compute_mod11_dv(cuerpo_43)
    cdc_44 = f"{cuerpo_43}{dv_cdc}"
    return cdc_44


def _to_dec(val: Any) -> Decimal:
    """Convierte un valor numérico o cadena a Decimal de manera segura."""
    if val is None or val == '':
        return Decimal('0')
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    cleaned = str(val).strip().replace(',', '.')
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal('0')


def _round_sifen(val: Decimal, moneda: str = 'PYG') -> Decimal:
    """
    Redondeo reglamentario según moneda (entero para PYG, 2 decimales para USD).
    """
    if moneda.upper() == 'PYG':
        return val.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_de(de_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ejecuta el cálculo completo de totales, bases gravadas e IVA para un Documento Electrónico.

    Aplica las fórmulas oficiales del manual 'API de Factura Segura para ESI v01':
    - dTotBruOpeItem = dPUniProSer * dCantProSer
    - dPorcDesIt = (dDescItem / dPUniProSer) * 100
    - dTotOpeItem = (dPUniProSer - dDescItem - dDescGloItem - dAntPreUniIt - dAntGloPreUniIt) * dCantProSer
    - dBasGravIVA e dLiqIVAItem según iAfecIVA (1=Gravado, 2=Exonerado, 3=Exento, 4=Gravado Parcial)
    - Subtotales: dSubExe, dSubExo, dSub5, dSub10
    - Totales: dTotOpe, dTotDesc, dTotGralOpe, dIVA5, dIVA10, dTotIVA, dBaseGrav5, dBaseGrav10, dTBasGraIVA

    :param de_data: Diccionario con la estructura del DE (resumido o completo).
    :return: Diccionario enriquecido con todos los campos calculados.
    """
    res = deepcopy(de_data)
    moneda = str(res.get('cMoneOpe', 'PYG')).strip().upper()
    es_pyg = (moneda == 'PYG')

    sub_exe = Decimal('0')
    sub_exo = Decimal('0')
    sub_5 = Decimal('0')
    sub_10 = Decimal('0')
    tot_desc = Decimal('0')
    iva_5 = Decimal('0')
    iva_10 = Decimal('0')
    base_grav_5 = Decimal('0')
    base_grav_10 = Decimal('0')

    items = res.get('gCamItem', [])
    calculated_items: List[Dict[str, Any]] = []

    for it in items:
        item = deepcopy(it)
        cant = _to_dec(item.get('dCantProSer', '1'))
        puni = _to_dec(item.get('dPUniProSer', '0'))
        desc_item = _to_dec(item.get('dDescItem', '0'))
        desc_glo = _to_dec(item.get('dDescGloItem', '0'))
        ant_pre = _to_dec(item.get('dAntPreUniIt', '0'))
        ant_glo = _to_dec(item.get('dAntGloPreUniIt', '0'))

        # 1. dTotBruOpeItem
        tot_bru = puni * cant
        item['dTotBruOpeItem'] = str(int(tot_bru)) if es_pyg else str(_round_sifen(tot_bru, moneda))

        # 2. dPorcDesIt
        if puni > Decimal('0'):
            porc_desc = (desc_item / puni) * Decimal('100')
            item['dPorcDesIt'] = str(porc_desc.quantize(Decimal('0.00000001'))).rstrip('0').rstrip('.')
        else:
            item['dPorcDesIt'] = '0'

        # 3. dTotOpeItem
        unit_neto = puni - desc_item - desc_glo - ant_pre - ant_glo
        tot_ope_it = unit_neto * cant
        item['dTotOpeItem'] = str(int(tot_ope_it)) if es_pyg else str(_round_sifen(tot_ope_it, moneda))

        # Acumular descuento del item
        tot_desc += (desc_item * cant)

        # 4. Tratamiento del IVA
        afec_iva = int(item.get('iAfecIVA', '1'))
        prop_iva = _to_dec(item.get('dPropIVA', '100'))
        tasa_iva = _to_dec(item.get('dTasaIVA', '10'))

        bas_grav = Decimal('0')
        liq_iva = Decimal('0')
        bas_exe = Decimal('0')

        if afec_iva in (1, 4):
            # Fórmula: [100 * dTotOpeItem * dPropIVA] / [10000 + (dTasaIVA * dPropIVA)]
            divisor = Decimal('10000') + (tasa_iva * prop_iva)
            if divisor > Decimal('0'):
                raw_bas_grav = (Decimal('100') * tot_ope_it * prop_iva) / divisor
                bas_grav = _round_sifen(raw_bas_grav, moneda)
                raw_liq_iva = bas_grav * (tasa_iva / Decimal('100'))
                liq_iva = _round_sifen(raw_liq_iva, moneda)

        if afec_iva == 4:
            # Fórmula: [100 * dTotOpeItem * (100 – dPropIVA)] / [10000 + (dTasaIVA * dPropIVA)]
            divisor = Decimal('10000') + (tasa_iva * prop_iva)
            if divisor > Decimal('0'):
                raw_bas_exe = (Decimal('100') * tot_ope_it * (Decimal('100') - prop_iva)) / divisor
                bas_exe = _round_sifen(raw_bas_exe, moneda)

        item['dBasGravIVA'] = str(int(bas_grav)) if es_pyg else str(bas_grav)
        item['dLiqIVAItem'] = str(int(liq_iva)) if es_pyg else str(liq_iva)
        item['dBasExe'] = str(int(bas_exe)) if es_pyg else str(bas_exe)
        item['dTotOpeGs'] = ''
        item['dTiCamIt'] = ''
        item['dDescGloItem'] = '0'
        item['dAntPreUniIt'] = '0'
        item['dAntGloPreUniIt'] = '0'

        # Acumuladores de subtotales
        if afec_iva == 3:
            sub_exe += tot_ope_it
        elif afec_iva == 4:
            sub_exe += bas_exe

        if afec_iva == 2:
            sub_exo += tot_ope_it

        if tasa_iva == Decimal('5'):
            if afec_iva == 1:
                sub_5 += tot_ope_it
            elif afec_iva == 4:
                sub_5 += (bas_grav + liq_iva)
            iva_5 += liq_iva
            base_grav_5 += bas_grav

        elif tasa_iva == Decimal('10'):
            if afec_iva == 1:
                sub_10 += tot_ope_it
            elif afec_iva == 4:
                sub_10 += (bas_grav + liq_iva)
            iva_10 += liq_iva
            base_grav_10 += bas_grav

        calculated_items.append(item)

    res['gCamItem'] = calculated_items

    tot_ope = sub_exe + sub_exo + sub_5 + sub_10
    redon = _to_dec(res.get('dRedon', '0'))
    comi = _to_dec(res.get('dComi', '0'))
    tot_gral = tot_ope - redon + comi
    tot_iva = iva_10 + iva_5
    t_bas_gra_iva = base_grav_5 + base_grav_10

    # Formateo de campos globales en el diccionario DE
    res['dSubExe'] = str(int(sub_exe)) if es_pyg else str(sub_exe)
    res['dSubExo'] = str(int(sub_exo)) if es_pyg else str(sub_exo)
    res['dSub5'] = str(int(sub_5)) if es_pyg else str(sub_5)
    res['dSub10'] = str(int(sub_10)) if es_pyg else str(sub_10)
    res['dTotOpe'] = str(int(tot_ope)) if es_pyg else str(tot_ope)
    res['dTotDesc'] = str(int(tot_desc)) if es_pyg else str(tot_desc)
    res['dTotDescGlotem'] = '0'
    res['dTotAntItem'] = '0'
    res['dTotAnt'] = '0'
    res['dPorcDescTotal'] = '0'
    res['dDescTotal'] = str(int(tot_desc)) if es_pyg else str(tot_desc)
    res['dAnticipo'] = '0'
    res['dRedon'] = str(int(redon)) if es_pyg else str(redon)
    res['dComi'] = str(int(comi)) if es_pyg else str(comi)
    res['dTotGralOpe'] = str(int(tot_gral)) if es_pyg else str(tot_gral)
    res['dIVA5'] = str(int(iva_5)) if es_pyg else str(iva_5)
    res['dIVA10'] = str(int(iva_10)) if es_pyg else str(iva_10)
    res['dLiqTotIVA5'] = '0'
    res['dLiqTotIVA10'] = '0'
    res['dIVAComi'] = '0'
    res['dTotIVA'] = str(int(tot_iva)) if es_pyg else str(tot_iva)
    res['dBaseGrav5'] = str(int(base_grav_5)) if es_pyg else str(base_grav_5)
    res['dBaseGrav10'] = str(int(base_grav_10)) if es_pyg else str(base_grav_10)
    res['dTBasGraIVA'] = str(int(t_bas_gra_iva)) if es_pyg else str(t_bas_gra_iva)

    # Conversión a Guaraníes si la moneda no es PYG
    if not es_pyg:
        tc = _to_dec(res.get('dTiCam', '1'))
        res['dTotalGs'] = str(int(tot_gral * tc))
    else:
        res['dTotalGs'] = ''

    return res

