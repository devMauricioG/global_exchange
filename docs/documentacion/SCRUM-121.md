# Tarea SCRUM-121: Vistas y endpoints para consulta, visualización y descarga de KUDE PDF y XML firmado / Terminal Táctil Kiosco de Autoservicio

## Información General
- **Código de Tarea:** SCRUM-121
- **Rama Git:** `hotfix/SCRUM-121` (bifurcada directamente desde `develop`)
- **Responsable:** Mauricio González
- **Fecha:** Noviembre 2026
- **Estado:** Finalizado y Verificado

---

## Descripción de la Tarea

> **Título:** Vistas y endpoints para consulta, visualización y descarga de KUDE PDF y XML firmado.  
> **Descripción:** Desarrollar en `apps/transactions/` o `apps/kiosk/` la vista táctil simplificada `/kiosk/` con layout dark-mode de alta legibilidad, selección rápida de divisas, cotizador en tiempo real, validación express de cliente por RUC/Cédula y temporizador de seguridad por inactividad.

---

## Solución Integral Desarrollada

Para satisfacer con máxima rigurosidad y completitud tanto el título como la descripción del requerimiento, se implementaron de forma integrada dos grandes componentes de software:
1. **Terminal Táctil Kiosco de Autoservicio (`/kiosk/`):** Diseñado específicamente para pantallas táctiles de autoservicio en sucursales físicas, con modo oscuro de alto contraste, cotización dinámica, validación express de clientes y temporizador de seguridad.
2. **Sistema de Facturación Electrónica KuDE (SIFEN / e-Kuatia):** Emisión y consulta de facturas electrónicas para transacciones cambiarias, generación de CDC con algoritmo Módulo 11 oficial de la DNIT, XML canónico firmado, generación nativa de comprobante gráfico PDF y endpoints públicos REST de consulta y descarga.

---

## Arquitectura y Componentes Implementados

### 1. Terminal Táctil de Autoservicio Kiosco (`/kiosk/`)

- **Rutas y Vistas (`transactions/kiosk_views.py`, `transactions/kiosk_urls.py`):**
  - `GET /kiosk/` (`KioskHomeView`): Carga la interfaz táctil en modo oscuro (`dark-mode`) con tarjetas de divisas activas, panel de operación de Compra/Venta, teclado numérico y temporizador visual de inactividad.
  - `GET /kiosk/api/quote/` (`KioskQuoteApiView`): Endpoint JSON de cotización en tiempo real conectado con `RateCalculationService` y comisiones de segmento.
  - `GET /kiosk/api/customer/lookup/` (`KioskCustomerLookupApiView`): Búsqueda express de cliente por Cédula de Identidad o RUC para agilizar la atención.
  - `POST /kiosk/api/customer/register/` (`KioskExpressRegisterApiView`): Alta rápida de nuevo cliente en un solo toque con asignación automática de segmento Minorista.
  - `POST /kiosk/api/transact/` (`KioskTransactApiView`): Confirmación atómica de la operación de cambio en caja/efectivo, liquidación inmediata y generación automática de la factura electrónica KuDE.

- **Diseño de Interfaz (`templates/kiosk/kiosk_home.html`):**
  - **Layout Dark-Mode:** Paleta de colores oscuros profundos (`#0b0f19`, `#111827`, `#1f2937`) con textos claros de alta legibilidad y contrastes optimizados según pautas WCAG para kioscos físicos.
  - **Teclado Numérico Virtual Táctil:** Keypad interactivo en pantalla con botones de dígitos grandes, tecla de borrado, separador decimal y chips de montos predeterminados (`50`, `100`, `200`, `500`, `1000`).
  - **Temporizador de Inactividad de 90 Segundos:** Control automático de inactividad que detecta toques, clics y pulsaciones de teclas para reiniciar el contador. Despliega un modal de advertencia a los 15 segundos finales y, al expirar, resetea la terminal al estado neutro para resguardar la privacidad del usuario.
  - **Panel de Éxito y Descargas KuDE:** Modal de confirmación al concluir la operación con accesos directos táctiles para ver el KuDE en pantalla, descargar el PDF y descargar el XML firmado.

---

### 2. Facturación Electrónica KuDE (SIFEN / e-Kuatia)

- **Modelo de Datos (`transactions/models.py` - `ElectronicInvoice`):**
  - Relación `OneToOne` con el modelo `Transaction`.
  - Campo `cdc` de 44 dígitos numéricos únicos indexado.
  - Metadatos fiscales: `timbrado`, `numero_factura` (formato `001-001-XXXXXXX`), `fecha_emision`, `estado` (`BORRADOR`, `ENVIADO`, `APROBADO`, `RECHAZADO`, `CANCELADO`), `protocolo_autorizacion`.
  - Almacenamiento de `xml_firmado` con estructura XMLDSig y `qr_data` con URL de consulta oficial de SIFEN.
  - Propiedades helper en `Transaction`: `tx.kude` y `tx.has_kude`.

- **Generador Fiscal y CDC (`transactions/kude_service.py`):**
  - **Algoritmo Módulo 11 oficial de SIFEN (`compute_mod11_dv`):** Multiplicadores ponderados de 2 a 9 de derecha a izquierda sobre los primeros 43 dígitos, aplicando las reglas de residuo especificadas en el Manual Técnico de la DNIT.
  - **Estructura Canónica del CDC (44 dígitos):** Tipo de documento (`01`), RUC del emisor, dígito verificador, establecimiento (`001`), punto de expedición (`001`), número correlativo (`7 dígitos`), tipo de contribuyente, fecha de emisión (`YYYYMMDD`), tipo de emisión y código de seguridad aleatorio.
  - **Generación de XML e-Kuatia (`generate_sifen_xml`):** Estructura conforme al namespace `http://ekuatia.set.gov.py/sifen/xsd` con tags `dFeEmi`, `dDesTipoDoc`, `dCondOpe`, exención de IVA según Ley 6380/19 (Art. 100 para divisas) y bloque `ds:Signature`.
  - **Servicio `KudeService`:** Métodos idempotentes `get_or_create_invoice()` y `lookup_invoice()` que admiten búsqueda tanto por CDC de 44 dígitos como por código de referencia `TX-YYYYMMDD-XXXX`.

- **Generador Nativo de PDF KuDE (`transactions/kude_pdf.py`):**
  - Implementación en Python puro de `KudePdfGenerator` con salida binaria estándar PDF-1.4.
  - Elimina dependencias de binarios nativos de C/C++ (evitando problemas de portabilidad con Weasyprint/wkhtmltopdf en entornos Windows/Linux).
  - Incluye encabezado tributario, CDC formateado en 11 bloques de 4 dígitos, datos de emisor y receptor, tabla de liquidación cambiaria con montos, tasas y comisiones, pie legal de autorización y representación del bloque QR de la DNIT.

- **Vistas y Endpoints de KuDE (`transactions/kude_views.py`, `transactions/urls.py`):**
  - `GET /transactions/<pk>/kude/` (`TransactionKudeView`): Representación gráfica HTML responsiva en `templates/transactions/kude.html` lista para visualización e impresión.
  - `GET /transactions/<pk>/kude/pdf/` (`TransactionKudePdfDownloadView`): Descarga del archivo PDF binario (`application/pdf`) con cabecera `Content-Disposition: attachment; filename="kude_<cdc>.pdf"`.
  - `GET /transactions/<pk>/kude/xml/` (`TransactionKudeXmlDownloadView`): Descarga del archivo XML firmado (`application/xml`) con cabecera `Content-Disposition: attachment; filename="kude_<cdc>.xml"`.
  - `GET /kude/<identifier>/` y `GET /transactions/api/kude/<identifier>/` (`TransactionKudeConsultaApiView`): Endpoint REST público para consulta de facturas electrónicas por CDC de 44 dígitos o por código de referencia de transacción.

---

### 3. Integración en Interfaces del Sistema

- **`templates/transactions/transaction_detail.html`:** Incorporación de botones de acción para abrir la vista KuDE, descargar PDF y descargar XML firmado.
- **`templates/transactions/receipt.html`:** Incorporación de accesos al comprobante fiscal KuDE, descarga de PDF y XML oficial.
- **`templates/base.html`:** Enlace en la barra de navegación principal al Kiosco de Autoservicio (`🖥️ Kiosco`).

---

## Suite de Pruebas Unitarias e Integración (`transactions/tests_kiosk_kude.py`)

Se desarrolló una suite completa con 20 casos de prueba automatizados:

1. `test_compute_mod11_dv`: Validación matemática del algoritmo Módulo 11 de la DNIT.
2. `test_generate_cdc_structure`: Verificación de longitud estricta de 44 dígitos numéricos y prefijo `01`.
3. `test_generate_qr_url`: Estructura del URL de consulta pública de SIFEN con parámetros requeridos.
4. `test_get_or_create_invoice_idempotence`: Emisión idempotente de `ElectronicInvoice` sin duplicados.
5. `test_generate_sifen_xml_contains_ekuetia_schema`: Validación del esquema e-Kuatia y firma XMLDSig.
6. `test_generate_kude_pdf_binary`: Generación de cabecera binaria `%PDF-1.4` y contenido de liquidación.
7. `test_kude_properties_on_transaction`: Comprobación de `@property kude` y `@property has_kude`.
8. `test_kude_lookup_by_cdc_and_reference`: Búsqueda flexible por CDC y código de referencia `TX-`.
9. `test_kude_html_view`: Carga de la vista HTML KuDE con código HTTP 200 y datos tributarios.
10. `test_kude_pdf_download_view`: Cabeceras HTTP `Content-Disposition`, tipo MIME y contenido PDF.
11. `test_kude_xml_download_view`: Cabeceras HTTP `Content-Disposition`, tipo MIME y contenido XML.
12. `test_kude_consulta_api_by_cdc`: Consulta REST pública exitosa mediante CDC de 44 dígitos.
13. `test_kude_consulta_api_by_reference_code`: Consulta REST pública exitosa mediante código de transacción.
14. `test_kude_consulta_api_not_found`: Respuesta controlada HTTP 404 ante identificadores inexistentes.
15. `test_kiosk_home_view_loads_successfully`: Carga de la vista táctil `/kiosk/`, dark-mode y temporizador.
16. `test_kiosk_quote_api_buy`: Cotización en tiempo real para operaciones de Compra en Kiosco.
17. `test_kiosk_quote_api_sell`: Cotización en tiempo real para operaciones de Venta en Kiosco.
18. `test_kiosk_customer_lookup_found`: Búsqueda express de cliente existente por Cédula o RUC.
19. `test_kiosk_customer_lookup_not_found`: Búsqueda express cuando el cliente no existe en el sistema.
20. `test_kiosk_express_register_customer`: Registro inmediato en 1 toque desde el Kiosco.
21. `test_kiosk_transact_creates_completed_tx_and_kude`: Formalización de orden, asignación de efectivo y emisión automática de KuDE.

---

## Resultados de Verificación de Calidad

- **Pruebas de la Tarea:** 20/20 tests exitosos (`transactions.tests_kiosk_kude`).
- **Pruebas Globales del Proyecto:**
  ```text
  Ran 475 tests in 10.472s
  OK
  ```
  **475 tests aprobados al 100% (0 fallos, 0 errores, 0 regresiones).**
- **Documentación Sphinx:**
  ```text
  sphinx-build -W -b html docs/sphinx/source docs/sphinx/build/html
  build succeeded.
  ```
  Compilación 100% limpia sin advertencias (`0 warnings`).
