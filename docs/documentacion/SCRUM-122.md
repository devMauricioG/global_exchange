# Tarea SCRUM-122: Protocolo de cuota y cliente real FacturaSeguraClient con reserva blindada de 10 pruebas / KioskCashService

## Información General
- **Código de Tarea:** SCRUM-122
- **Rama Git:** `feature/SCRUM-122` (bifurcada directamente desde `develop`)
- **Responsable:** Mauricio González
- **Fecha:** Noviembre 2026
- **Estado:** Finalizado y Verificado

---

## Descripción de la Tarea

> **Título:** Protocolo de cuota y cliente real FacturaSeguraClient con reserva blindada de 10 pruebas.  
> **Descripción:** Implementar el servicio KioskCashService que simula la aceptación física de billetes y dispensación de divisas en la terminal, validando denominaciones permitidas, disponibilidad de saldo en la caja del tótem y generando el comprobante con código QR.

---

## Solución Integral Desarrollada

Se implementó una solución robusta y exhaustiva que satisface plenamente ambos ejes del requerimiento:

1. **Protocolo de Cuota y Cliente Real `FacturaSeguraClient`:**
   - Cliente formal para integración con el PAC certificado (Proveedor de Autorización y Certificación) FacturaSegura para emisión de facturas electrónicas e-Kuatia (SIFEN / DNIT).
   - **Reserva Blindada de 10 Pruebas:** Mecanismo inviolable que protege 10 unidades de cuota exclusivamente para pruebas de integración automatizadas y suites de QA. Si el saldo comercial se agota, las operaciones ordinarias son bloqueadas (`QuotaShieldExhaustedError`), garantizando que la ejecución de tests nunca se interrumpa.
   - Operaciones de emisión (`emitir_factura`), consulta de estado (`consultar_factura`), auditoría de balance (`consultar_cuota`) y eventos de anulación (`cancelar_factura`).

2. **Servicio de Efectivo en Terminales Kiosco (`KioskCashService`):**
   - Catálogo estricto de denominaciones de billetes de curso legal permitidas por divisa (PYG, USD, EUR, BRL, ARS), con rechazo automático de denominaciones fraudulentas o inexistentes (`InvalidBillDenominationError`).
   - Aceptación física de billetes con control de capacidad en casetes receptores y registro de operaciones `ACEPTACION`.
   - Algoritmo de dispensación física de divisas (Bounded Coin Change / Greedy con backtracking) que minimiza la cantidad de piezas físicas y valida disponibilidad de saldo en la caja del tótem (`InsufficientTotemBalanceError`, `CannotDispenseExactChangeError`).
   - Generador nativo puro de códigos QR en formato SVG (sin dependencias C/C++ externas) y sellos criptográficos de trazabilidad SHA-256.
   - Comprobante imprimible de caja en `templates/kiosk/cash_receipt.html` y endpoints REST.

---

## Arquitectura y Componentes Implementados

### 1. Modelos de Datos (`transactions/models.py`)

- **`FacturaSeguraConfig`:**
  - `api_key`: Token de autenticación del PAC.
  - `api_url`: URL del webservice del PAC (`https://api.facturasegura.com.py/v1`).
  - `total_quota`: Cuota total contratada para el período.
  - `used_quota`: Cuota comercial ordinaria consumida.
  - `test_quota_reserved`: 10 unidades blindadas para QA.
  - `test_quota_used`: Cuota consumida por llamadas de prueba.
  - Propiedades: `operational_quota_available`, `test_quota_available`, `is_operational_quota_exhausted`.
  - Método `consume_quota(is_test=False)` con protección de reserva blindada.

- **`KioskTotem`:**
  - Hardware de terminal: `codigo` (`TOTEM-01`), `nombre`, `ubicacion`, `estado` (`ONLINE`, `OFFLINE`, `MAINTENANCE`, `LOW_CASH`), `ip_address`, `activo`.
  - Métodos de balance y consulta de casetes.

- **`KioskCashVault` (Casete por Denominación):**
  - Almacena el inventario físico de billetes por tótem, moneda y denominación facial (ej. 100.000 Gs, 50.000 Gs, 100 USD).
  - Control de `cantidad` física y `capacidad_maxima` (2.000 billetes).
  - Propiedad calculada `saldo = denominacion * cantidad`.

- **`KioskCashOperation`:**
  - Registro auditable de movimientos físicos: `uuid`, `tipo_operacion` (`ACEPTACION`, `DISPENSACION`, `RECARGA`), `currency`, `monto_total`, `desglose_billetes` (JSON), `total_billetes`, `codigo_qr`, `hash_verificacion` (SHA-256).

- **`ElectronicInvoice` (Extensión):**
  - Incorporación del estado `CANCELADO = 'CANCELADO', 'Cancelado / Anulado'` en `EstadoSifen`.

---

### 2. Cliente Real y Protocolo de Cuota (`transactions/facturasegura_client.py`)

- **Excepciones Especializadas:**
  - `FacturaSeguraError`: Base de excepciones del PAC.
  - `QuotaShieldExhaustedError`: Disparada cuando la cuota comercial se agota y las 10 consultas restantes están blindadas para pruebas.
  - `TestQuotaExhaustedError`: Disparada si se superan las 10 pruebas de la reserva.
  - `FacturaSeguraApiError`: Errores de comunicación HTTP o del PAC.

- **Métodos del Cliente:**
  - `consultar_cuota()`: Inspecciona cuota total, consumida, operativa disponible y reserva blindada.
  - `emitir_factura(transaction, is_test=False)`: Aplica el protocolo de cuota, genera el CDC de 44 dígitos, XML e-Kuatia firmado, URL QR oficial de SIFEN y actualiza `ElectronicInvoice`.
  - `consultar_factura(cdc, is_test=False)`: Verifica estado tributario ante SIFEN.
  - `cancelar_factura(cdc, motivo, is_test=False)`: Envía evento de cancelación al PAC.

---

### 3. Servicio de Efectivo en Tótem (`transactions/kiosk_cash_service.py`)

- **Denominaciones Permitidas:**
  - `PYG`: 100.000, 50.000, 20.000, 10.000, 5.000, 2.000
  - `USD`: 100, 50, 20, 10, 5, 1
  - `EUR`: 200, 100, 50, 20, 10, 5
  - `BRL`: 200, 100, 50, 20, 10, 5, 2
  - `ARS`: 10.000, 2.000, 1.000, 500, 200, 100

- **Operaciones Principales:**
  - `validate_bills(currency_code, bills)`: Valida listas o diccionarios de billetes contra el catálogo oficial.
  - `accept_cash(totem, currency, bills, transaction=None)`: Acepta billetes, incrementa casetes bajo transacción atómica (`select_for_update`) y genera comprobante con hash SHA-256 y QR.
  - `calculate_dispense_breakdown(totem, currency, target_amount)`: Algoritmo voraz con backtracking acotado para componer el monto exacto con el menor número de piezas físicas.
  - `dispense_cash(totem, currency, target_amount, transaction=None)`: Descuenta existencias y genera comprobante con QR.
  - `generate_qr_svg(payload, size=160)`: Generador determinista de código QR en SVG nativo puro en Python.
  - `generate_cash_receipt(operation)`: Genera estructura completa para visualización e impresión.
  - `get_totem_inventory(totem)`: Reporte consolidado de existencias y porcentaje de ocupación por casete.

---

### 4. Vistas, Endpoints y Plantillas

- **Endpoints REST (`transactions/kiosk_urls.py`, `transactions/kiosk_views.py`):**
  - `GET /kiosk/api/cash/status/`: Inventario de efectivo, casetes y catálogo de denominaciones.
  - `POST /kiosk/api/cash/accept/`: Simulación de inserción física de billetes.
  - `POST /kiosk/api/cash/dispense/`: Simulación de dispensación física de divisas.
  - `GET /kiosk/api/cash/receipt/<uuid>/`: Consulta JSON de comprobante y código QR.
  - `GET /kiosk/receipt/<uuid>/`: Vista web del comprobante imprimible con QR.
  - `GET /kiosk/api/facturasegura/cuota/`: Consulta del protocolo de cuota y reserva blindada.
  - `POST /kiosk/api/transact/`: Transacción integral de kiosco que orquesta aceptación de billetes, dispensación de divisas y emisión de factura vía FacturaSegura PAC.

- **Plantillas:**
  - `templates/kiosk/cash_receipt.html`: Diseño formal tipo ticket térmico con desglose por billetes, totales, sellos SHA-256, QR SVG y botón de impresión.
  - `templates/kiosk/kiosk_home.html`: Incorporación de botón para ver/imprimir el comprobante de dispensación de efectivo en el modal de éxito.

---

## Suite de Pruebas Unitarias e Integración (`transactions/tests_kiosk_cash_facturasegura.py`)

Se diseñó e implementó una suite con **25 pruebas automatizadas**:

1. `test_default_config_creation_and_quota_calculation`: Verificación de inicialización de cuotas y reserva de 10 pruebas.
2. `test_consume_operational_quota`: Consumo ordinario de cuota sin afectar la reserva blindada.
3. `test_operational_quota_exhaustion_blocks_with_shield_error`: Bloqueo de llamadas ordinarias con `QuotaShieldExhaustedError` al agotarse el saldo comercial.
4. `test_shielded_10_tests_can_be_executed_when_operational_exhausted`: Ejecución garantizada de las 10 pruebas blindadas con cuota comercial en cero.
5. `test_depleting_all_10_test_units_raises_test_quota_exhausted`: Rechazo con `TestQuotaExhaustedError` al consumir la 11ª prueba.
6. `test_emitir_factura_creates_certified_response_and_updates_model`: Emisión certificada vía PAC y persistencia en `ElectronicInvoice`.
7. `test_consultar_factura_and_cancelar_factura`: Consulta de DTE y evento de anulación con cambio de estado a `CANCELADO`.
8. `test_allowed_denominations_catalog`: Integridad del catálogo de billetes permitidos.
9. `test_validate_bills_valid_inputs`: Normalización y suma en listas y diccionarios de billetes.
10. `test_validate_bills_invalid_denomination_rejected`: Rechazo con `InvalidBillDenominationError` ante billetes ilegales (ej. 3.000 Gs o 3 USD).
11. `test_accept_cash_increments_cassette_and_creates_operation`: Incremento de existencias en casete y hash SHA-256.
12. `test_accept_cash_exceeding_capacity_raises_error`: Rechazo ante casete que excede capacidad máxima de 2.000 piezas.
13. `test_calculate_dispense_breakdown_optimal`: Algoritmo de desglose mínimo de piezas físicas.
14. `test_dispense_cash_decrements_cassette_and_creates_operation`: Descuento de stock en casetes y registro de dispensación.
15. `test_dispense_cash_insufficient_balance_raises_error`: Rechazo con `InsufficientTotemBalanceError` si el saldo es insuficiente.
16. `test_dispense_cash_impossible_change_raises_error`: Rechazo con `CannotDispenseExactChangeError` si no se puede armar el cambio exacto.
17. `test_generate_cash_receipt_structure`: Comprobante con SVG nativo y código QR.
18. `test_get_totem_inventory_structure`: Informe consolidado de inventario.
19. `test_api_cash_status`: Endpoint REST de inventario.
20. `test_api_cash_accept_success`: Endpoint REST de aceptación de billetes.
21. `test_api_cash_accept_invalid_rejected`: Validación HTTP 400 ante billetes inválidos.
22. `test_api_cash_dispense_success`: Endpoint REST de dispensación.
23. `test_api_cash_receipt_json_and_html`: Consulta JSON y plantilla HTML del ticket.
24. `test_api_facturasegura_cuota`: Endpoint REST del protocolo de cuota.
25. `test_kiosk_transact_full_flow_with_cash_and_facturasegura`: Flujo completo integrado de Kiosco con efectivo y FacturaSegura.

---

## Verificación de Calidad y Cero Regresiones

- **Pruebas de la Tarea:** 25/25 tests aprobados (`transactions.tests_kiosk_cash_facturasegura`).
- **Pruebas Totales del Proyecto:**
  ```text
  Ran 500 tests in 9.696s
  OK
  ```
  **500 tests aprobados al 100% de éxito (0 fallos, 0 errores, 0 regresiones).**
- **Documentación Sphinx:**
  ```text
  sphinx-build -W -b html docs/sphinx/source docs/sphinx/build/html
  build succeeded.
  ```
  Compilación 100% limpia sin advertencias (`0 warnings`).
