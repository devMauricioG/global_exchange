"""
Módulo para la generación del documento binario PDF del KuDE (Kuatia'ahekaha Digital Electrónico).

Implementa un generador nativo PDF-1.4 de alta fidelidad sin dependencias externas pesadas,
diseñado específicamente para el formato oficial de Documentos Tributarios Electrónicos
de la DNIT / SIFEN de Paraguay (SCRUM-121).
"""

from datetime import datetime
from decimal import Decimal
import io
from typing import Any, List, Tuple

from .models import ElectronicInvoice, Transaction


def _escape_pdf_text(text: str) -> str:
    """
    Escapa caracteres especiales para el formato de cadenas PDF en WinAnsiEncoding.
    """
    if not text:
        return ""
    # Reemplazar caracteres comunes con sus equivalentes seguros en WinAnsi
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U',
        '₲': 'Gs.', '—': '-', '–': '-', '"': "'",
    }
    cleaned = "".join(replacements.get(c, c) for c in text)
    # Escapar paréntesis y barras invertidas
    cleaned = cleaned.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    return cleaned


class KudePdfGenerator:
    """
    Generador de archivos PDF para la Representación Gráfica KuDE de Facturas Electrónicas.
    """

    @classmethod
    def generate_pdf(cls, invoice: ElectronicInvoice) -> bytes:
        """
        Genera el flujo de bytes del documento PDF oficial del KuDE.

        :param invoice: Instancia de ElectronicInvoice con su transacción vinculada.
        :type invoice: transactions.models.ElectronicInvoice
        :return: Contenido binario del archivo PDF (application/pdf).
        :rtype: bytes
        """
        tx = invoice.transaction
        cliente = tx.cliente

        # Dimensiones de página A4 en puntos (72 ppi): 595.28 x 841.89
        width, height = 595.28, 841.89

        # Construir stream de comandos gráficos PDF
        stream_lines: List[str] = []

        def add_rect(x: float, y: float, w: float, h: float, fill_color: Tuple[float, float, float] = None, stroke_color: Tuple[float, float, float] = None, line_width: float = 1.0):
            if fill_color:
                stream_lines.append(f"{fill_color[0]:.3f} {fill_color[1]:.3f} {fill_color[2]:.3f} rg")
                stream_lines.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
            if stroke_color:
                stream_lines.append(f"{stroke_color[0]:.3f} {stroke_color[1]:.3f} {stroke_color[2]:.3f} RG")
                stream_lines.append(f"{line_width:.2f} w")
                stream_lines.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")

        def add_line(x1: float, y1: float, x2: float, y2: float, stroke_color: Tuple[float, float, float] = (0.7, 0.7, 0.7), line_width: float = 0.8):
            stream_lines.append(f"{stroke_color[0]:.3f} {stroke_color[1]:.3f} {stroke_color[2]:.3f} RG")
            stream_lines.append(f"{line_width:.2f} w")
            stream_lines.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

        def add_text(text: str, x: float, y: float, font: str = "F1", size: float = 10.0, color: Tuple[float, float, float] = (0.1, 0.1, 0.1)):
            stream_lines.append(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg")
            stream_lines.append(f"BT /{font} {size:.1f} Tf {x:.2f} {y:.2f} Td ({_escape_pdf_text(text)}) Tj ET")

        # 1. Fondo de página y marco exterior
        add_rect(20, 20, width - 40, height - 40, stroke_color=(0.15, 0.23, 0.36), line_width=1.5)

        # 2. Encabezado institucional (Banda superior azul oscuro)
        add_rect(25, height - 90, width - 50, 65, fill_color=(0.04, 0.08, 0.16), stroke_color=(0.22, 0.74, 0.97), line_width=1.2)
        add_text("GLOBAL EXCHANGE S.A.", 35, height - 50, font="F2", size=18, color=(0.22, 0.74, 0.97))
        add_text("CASA DE CAMBIO DIGITAL - SISTEMA DE FACTURACION ELECTRONICA NACIONAL", 35, height - 66, font="F1", size=8.5, color=(0.8, 0.85, 0.9))
        add_text("Av. Mariscal Lopez 1234, Asuncion, Paraguay | Tel: +595 21 600 000", 35, height - 79, font="F1", size=7.5, color=(0.6, 0.65, 0.75))

        # Cuadro de Timbrado y Factura (lado derecho superior)
        add_rect(360, height - 88, 200, 61, fill_color=(0.08, 0.12, 0.22), stroke_color=(0.22, 0.74, 0.97), line_width=1.0)
        add_text(f"RUC: 80012345-7", 370, height - 45, font="F2", size=11, color=(1.0, 1.0, 1.0))
        add_text(f"TIMBRADO Nro: {invoice.timbrado}", 370, height - 58, font="F2", size=10, color=(0.95, 0.78, 0.25))
        add_text(f"FACTURA ELECTRONICA (KuDE)", 370, height - 71, font="F2", size=9, color=(0.22, 0.74, 0.97))
        add_text(f"Nro: {invoice.numero_factura}", 370, height - 83, font="F3", size=11, color=(1.0, 1.0, 1.0))

        # 3. Recuadro destacado del CDC (Código de Control / Clave de Acceso de 44 dígitos)
        cdc_y = height - 135
        add_rect(25, cdc_y, width - 50, 38, fill_color=(0.94, 0.97, 1.0), stroke_color=(0.08, 0.35, 0.65), line_width=1.2)
        add_text("CODIGO DE CONTROL (CDC) - CLAVE DE ACCESO SIFEN (44 DIGITOS)", 35, cdc_y + 24, font="F2", size=8, color=(0.08, 0.35, 0.65))
        add_text(invoice.cdc_formatted, 35, cdc_y + 9, font="F3", size=10, color=(0.05, 0.1, 0.2))
        add_text("Consulte la validez de este KuDE en: https://ekuatia.set.gov.py/consultas/", 310, cdc_y + 24, font="F1", size=7, color=(0.3, 0.4, 0.5))

        # 4. Datos del Cliente / Receptor
        cli_y = height - 215
        add_rect(25, cli_y, width - 50, 72, fill_color=(0.98, 0.99, 1.0), stroke_color=(0.75, 0.82, 0.9), line_width=0.8)
        add_rect(25, cli_y + 54, width - 50, 18, fill_color=(0.90, 0.94, 0.98))
        add_text("DATOS DEL RECEPTOR / CLIENTE", 35, cli_y + 59, font="F2", size=8.5, color=(0.1, 0.2, 0.4))

        nombre_cli = getattr(cliente, 'nombre', 'Cliente General')
        ruc_cli = getattr(cliente, 'documento_ruc', 'X-44444401-7')
        correo_cli = getattr(cliente, 'correo', 'N/A')
        seg_cli = getattr(cliente, 'get_segmentacion_display', lambda: 'Minorista')()
        fecha_emi_str = invoice.fecha_emision.strftime('%d/%m/%Y %H:%M:%S')

        add_text("Nombre / Razon Social:", 35, cli_y + 38, font="F2", size=8.5)
        add_text(nombre_cli, 145, cli_y + 38, font="F1", size=9)

        add_text("Documento / RUC:", 35, cli_y + 23, font="F2", size=8.5)
        add_text(ruc_cli, 145, cli_y + 23, font="F3", size=9)

        add_text("Correo Electronico:", 35, cli_y + 8, font="F2", size=8.5)
        add_text(correo_cli, 145, cli_y + 8, font="F1", size=8.5)

        add_text("Fecha de Emision:", 340, cli_y + 38, font="F2", size=8.5)
        add_text(fecha_emi_str, 430, cli_y + 38, font="F1", size=8.5)

        add_text("Segmento Comercial:", 340, cli_y + 23, font="F2", size=8.5)
        add_text(seg_cli, 430, cli_y + 23, font="F1", size=8.5)

        add_text("Estado Autorizacion:", 340, cli_y + 8, font="F2", size=8.5)
        add_text(f"APROBADO SIFEN", 430, cli_y + 8, font="F2", size=8.5, color=(0.06, 0.6, 0.35))

        # 5. Tabla de Liquidación Cambiaria y Detalle de la Operación
        tbl_y = height - 370
        add_rect(25, tbl_y, width - 50, 145, fill_color=(1.0, 1.0, 1.0), stroke_color=(0.75, 0.82, 0.9), line_width=0.8)

        # Cabecera de la tabla
        add_rect(25, tbl_y + 125, width - 50, 20, fill_color=(0.1, 0.2, 0.38))
        add_text("CODIGO", 35, tbl_y + 131, font="F2", size=8, color=(1, 1, 1))
        add_text("DESCRIPCION DE LA OPERACION CAMBIARIA", 110, tbl_y + 131, font="F2", size=8, color=(1, 1, 1))
        add_text("CANTIDAD", 320, tbl_y + 131, font="F2", size=8, color=(1, 1, 1))
        add_text("TASA NETA", 385, tbl_y + 131, font="F2", size=8, color=(1, 1, 1))
        add_text("EXENTAS (Gs)", 470, tbl_y + 131, font="F2", size=8, color=(1, 1, 1))

        # Fila 1: Operación principal
        tipo_op = "Compra" if tx.tipo_operacion == Transaction.TipoOperacion.COMPRA else "Venta"
        desc_line1 = f"Operacion de {tipo_op} de Divisas ({tx.base_currency.code} / {tx.target_currency.code})"
        desc_line2 = f"Referencia: {tx.codigo_referencia} | Tasa Oficial Base: {tx.tasa_base}"
        add_text(tx.codigo_referencia[:10], 35, tbl_y + 105, font="F3", size=8)
        add_text(desc_line1, 110, tbl_y + 105, font="F2", size=8.5)
        add_text(desc_line2, 110, tbl_y + 92, font="F1", size=7.5, color=(0.4, 0.45, 0.5))

        add_text(f"{tx.monto_origen} {tx.moneda_origen.code}", 320, tbl_y + 105, font="F1", size=8.5)
        add_text(f"{tx.tasa_neta}", 385, tbl_y + 105, font="F3", size=8.5)
        add_text(f"{tx.monto_destino}", 470, tbl_y + 105, font="F2", size=9)

        # Fila 2: Comisión de segmento
        add_line(25, tbl_y + 80, width - 25, tbl_y + 80)
        add_text("COM-SEG", 35, tbl_y + 65, font="F3", size=8)
        add_text(f"Comision comercial aplicada ({seg_cli})", 110, tbl_y + 65, font="F1", size=8.5)
        add_text("1.00", 320, tbl_y + 65, font="F1", size=8.5)
        add_text(f"{tx.comision_segmento}", 385, tbl_y + 65, font="F3", size=8.5)
        add_text("0.00", 470, tbl_y + 65, font="F1", size=8.5)

        # Fila de Totales
        add_rect(25, tbl_y, width - 50, 40, fill_color=(0.95, 0.97, 1.0), stroke_color=(0.75, 0.82, 0.9), line_width=0.8)
        add_text("TOTAL OPERACION LIQUIDADA:", 220, tbl_y + 22, font="F2", size=9.5, color=(0.1, 0.2, 0.4))
        add_text(f"{tx.monto_destino} {tx.moneda_destino.code}", 440, tbl_y + 22, font="F2", size=12, color=(0.06, 0.55, 0.3))
        add_text("Operacion cambiaria exenta de IVA de acuerdo con el Art. 100 de la Ley 6380/19", 35, tbl_y + 8, font="F1", size=7.5, color=(0.4, 0.4, 0.5))

        # 6. Liquidación de Impuesto al Valor Agregado (IVA)
        iva_y = height - 440
        add_rect(25, iva_y, width - 50, 60, fill_color=(0.98, 0.99, 1.0), stroke_color=(0.75, 0.82, 0.9), line_width=0.8)
        add_rect(25, iva_y + 42, width - 50, 18, fill_color=(0.90, 0.94, 0.98))
        add_text("LIQUIDACION DEL IMPUESTO AL VALOR AGREGADO (IVA)", 35, iva_y + 47, font="F2", size=8, color=(0.1, 0.2, 0.4))

        add_text("Total Exenta:", 35, iva_y + 25, font="F2", size=8)
        add_text(f"{tx.monto_destino} Gs.", 115, iva_y + 25, font="F1", size=8.5)

        add_text("Gravadas 5%:", 210, iva_y + 25, font="F2", size=8)
        add_text("0 Gs.", 285, iva_y + 25, font="F1", size=8.5)

        add_text("Gravadas 10%:", 350, iva_y + 25, font="F2", size=8)
        add_text("0 Gs.", 435, iva_y + 25, font="F1", size=8.5)

        add_text("Liquidacion IVA 5%:", 35, iva_y + 10, font="F2", size=8)
        add_text("0 Gs.", 115, iva_y + 10, font="F1", size=8.5)

        add_text("Liquidacion IVA 10%:", 210, iva_y + 10, font="F2", size=8)
        add_text("0 Gs.", 285, iva_y + 10, font="F1", size=8.5)

        add_text("TOTAL LIQUIDACION IVA:", 350, iva_y + 10, font="F2", size=8.5, color=(0.1, 0.2, 0.4))
        add_text("0 Gs.", 475, iva_y + 10, font="F2", size=9, color=(0.06, 0.55, 0.3))

        # 7. Información de Seguridad y Trazabilidad SIFEN / e-Kuatia
        sec_y = height - 575
        add_rect(25, sec_y, width - 50, 125, fill_color=(0.97, 0.98, 1.0), stroke_color=(0.22, 0.74, 0.97), line_width=1.0)
        add_rect(25, sec_y + 105, width - 50, 20, fill_color=(0.08, 0.15, 0.28))
        add_text("AUTORIZACION Y CONTROL TRIBUTARIO - SISTEMA SIFEN", 35, sec_y + 111, font="F2", size=8.5, color=(0.22, 0.74, 0.97))

        add_text(f"Protocolo de Autorizacion: {invoice.protocolo_autorizacion}", 35, sec_y + 88, font="F3", size=8.5)
        add_text(f"Fecha de Autorizacion: {fecha_emi_str}", 35, sec_y + 73, font="F1", size=8.5)
        add_text("Firma Digital: XML-DSig con certificado digital de Global Exchange S.A. emitido por Prestador Acreditado.", 35, sec_y + 58, font="F1", size=7.5, color=(0.3, 0.35, 0.45))
        add_text(f"Referencia de Pago: {tx.referencia_externa_pago or 'VENTANILLA / POS KIOSK'} | Pasarela: {tx.pasarela_pago or 'EFECTIVO'}", 35, sec_y + 44, font="F1", size=8)

        # Cuadro QR simulado
        add_rect(440, sec_y + 12, 110, 85, fill_color=(1, 1, 1), stroke_color=(0.2, 0.3, 0.5), line_width=0.8)
        add_text("[ QR SIFEN ]", 465, sec_y + 50, font="F2", size=10, color=(0.1, 0.2, 0.4))
        add_text("Consulte el DTE", 460, sec_y + 35, font="F1", size=7, color=(0.4, 0.45, 0.5))
        add_text(f"Id: {invoice.cdc[:10]}...", 448, sec_y + 20, font="F3", size=6.5, color=(0.2, 0.4, 0.7))

        add_text("Este documento es una representacion grafica oficial de un Documento Tributario Electronico (KuDE)", 35, sec_y + 22, font="F2", size=7.5, color=(0.1, 0.2, 0.35))
        add_text("Emitido bajo el marco normativo de la Ley 6380/19 y reglamentaciones de la DNIT.", 35, sec_y + 10, font="F1", size=7, color=(0.4, 0.45, 0.5))

        # 8. Pie de página
        add_line(25, 45, width - 25, 45, stroke_color=(0.7, 0.7, 0.7), line_width=0.6)
        add_text("GLOBAL EXCHANGE S.A. — Transparencia, Seguridad y Solidez Cambiaria — Pagina 1 de 1", 130, 32, font="F1", size=7.5, color=(0.45, 0.5, 0.55))

        # Ensamblar PDF en memoria
        content_stream = "\n".join(stream_lines).encode("latin1", errors="replace")

        pdf_objects: List[bytes] = []

        # Obj 1: Catalog
        pdf_objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        # Obj 2: Pages
        pdf_objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        # Obj 3: Page
        pdf_objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] "
            b"/Resources << /Font << /F1 4 0 R /F2 5 0 R /F3 6 0 R >> >> "
            b"/Contents 7 0 R >>"
        )
        # Obj 4: Helvetica
        pdf_objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        # Obj 5: Helvetica-Bold
        pdf_objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        # Obj 6: Courier
        pdf_objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
        # Obj 7: Content stream
        stream_len = len(content_stream)
        pdf_objects.append(
            f"<< /Length {stream_len} >>\nstream\n".encode("ascii") + content_stream + b"\nendstream"
        )

        # Construir archivo PDF con tabla XREF
        output = io.BytesIO()
        output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        offsets = []
        for i, obj in enumerate(pdf_objects, start=1):
            offsets.append(output.tell())
            output.write(f"{i} 0 obj\n".encode("ascii"))
            output.write(obj)
            output.write(b"\nendobj\n")

        xref_pos = output.tell()
        output.write(f"xref\n0 {len(pdf_objects) + 1}\n".encode("ascii"))
        output.write(b"0000000000 65535 f \n")
        for offset in offsets:
            output.write(f"{offset:010d} 00000 n \n".encode("ascii"))

        output.write(f"trailer\n<< /Size {len(pdf_objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
        output.write(f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii"))

        return output.getvalue()

