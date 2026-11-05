# SCRUM-120: Protocolo de Cuota y Cliente Real FacturaSeguraClient con Reserva Blindada de 10 Pruebas

## 📌 Metadatos de la Tarea

* **Ticket:** SCRUM-120
* **Épica:** SCRUM-7 (Módulo de Caja, Terminal de Autoservicio, Simulación de Efectivo y Facturación Electrónica Segura)
* **Historia de Usuario:** SCRUM-110 (Integración de Facturación Electrónica SIFEN con Control Estricto de Cuota)
* **Sprint:** SCRUM Sprint 5
* **Responsable:** Mauricio González
* **Estado:** Finalizado
* **Bloquea:** SCRUM-125

---

## 🎯 Objetivo y Alcance

Implementar en el módulo canónico de facturación electrónica (`apps/invoicing/`) el cliente HTTP real `FacturaSeguraClient` conectando al endpoint PAC oficial (`https://apitest.facturasegura.com.py/` para Sandbox / homologación y `https://portal.facturasegura.com.py/` para Producción), soportando el estándar formal de interoperabilidad **"API de Factura Segura para ESI (External Systems Interoperation) v01"**.

La implementación está condicionada de manera inviolable a la bandera de entorno `FACTURA_SEGURA_LIVE_ENABLED=True` e integra un **contador estricto y protocolo de cuota con reserva blindada de 10 llamadas**, protegiendo el saldo presupuestario de peticiones y garantizando que las últimas 10 llamadas queden reservadas exclusivamente para la presentación en vivo y pruebas finales de acreditación.

---

## 🏗️ Arquitectura de la Solución

### 1. Cliente HTTP Formal `FacturaSeguraClient` (`apps/invoicing/client.py`)

* **Autenticación Oficial ESI:**
  * Método `login(email, password)`: ejecuta `POST {api_url}/login?include_auth_token` con carga útil JSON.
  * Caching y reutilización automática del token de sesión mediante cabecera `Authentication-Token: <token>`.
  * Método `get_auth_token()` con lazy initialization.

* **Operaciones Tributarias Homologadas (ESI v01):**
  * `calcular_de(de_data)`: Despacha la operación `calcular_de` con el envelope `{"operation": "calcular_de", "params": {"DE": de_data}}`, retornando el DTE enriquecido con los cálculos de IVA (5%, 10%, Exenta), bases imponibles y liquidación total.
  * `generar_de(de_data)`: Despacha la operación `generar_de` para validación, firma digital en el PAC y envío a SIFEN, retornando el envelope estructurado con el CDC de 44 dígitos generado.
  * `get_estado_sifen(cdc, ruc_emisor)`: Consulta el estado tributario del documento en SIFEN mediante envelope `get_estado_sifen` con parámetros `CDC` y `dRucEm`.
  * `dwn_kude(cdc, ruc_emisor)`: Descarga el KuDE en formato PDF binario vía `GET /misife00/v1/esi/dwn_kude/{dRucEm}/{CDC}` con cabecera `Authentication-Token`.
  * `dwn_xml(cdc, ruc_emisor)`: Descarga el XML firmado digitalmente vía `GET /misife00/v1/esi/dwn_xml/{dRucEm}/{CDC}` con cabecera `Authentication-Token`.
  * `sol_cancelacion(cdc, motivo, ruc_emisor)`: Despacha evento formal de cancelación con motivo justificado a SIFEN.
  * `sol_inutilizacion(ruc_emisor, timbrado, est, pun_exp, num_doc, tipo_de)`: Despacha evento de inutilización de numeración timbrada.

### 2. Protocolo de Cuota y Reserva Blindada de 10 Pruebas

* **Blindaje Presupuestario:**
  * Cada petición externa al PAC consume unidades del balance de cuota asignado.
  * Se establece de forma inalterable una **reserva blindada de 10 llamadas** (`test_quota_reserved = 10`).
  * **Llamadas Ordinarias / Comerciales (`is_test=False`, `is_presentation=False`):**
    * Consumen de la cuota operativa: `operational_quota_available = total_quota - used_quota - test_quota_reserved`.
    * Cuando `operational_quota_available <= 0`, el cliente **bloquea inmediatamente la petición** antes de realizar cualquier llamada de red, disparando `QuotaShieldExhaustedError`:
      > *"Cuota comercial ordinaria agotada (...). Las 10 llamadas restantes se encuentran blindadas exclusivamente para la presentación en vivo y QA."*
  * **Llamadas de Presentación / QA (`is_presentation=True` o `is_test=True`):**
    * Consumen de la reserva blindada de 10 unidades: `test_quota_available = test_quota_reserved - test_quota_used`.
    * Cuando se agotan las 10 unidades, dispara `TestQuotaExhaustedError` / `PresentationQuotaExhaustedError`.

* **Concurrencia y Persistencia:**
  * Contadores protegidos por exclusión mutua mediante `threading.Lock` para evitar condiciones de carrera.
  * Sincronización bidireccional automática con el modelo persistente `FacturaSeguraConfig` en base de datos cuando está disponible, y fallback thread-safe en memoria.
  * Métodos de auditoría y gestión: `consultar_cuota()`, `reset_quotas(total)` y `replenish_quota(amount)`.

### 3. Guardián de Modo Live (`FACTURA_SEGURA_LIVE_ENABLED`)

* Si `FACTURA_SEGURA_LIVE_ENABLED=False` (predeterminado en desarrollo local y suites de tests):
  * Cualquier invocación a métodos de red lanza inmediatamente `LiveModeDisabledError`.
  * Se preserva el 100% de la cuota real para la defensa y presentación.

### 4. Integración con el Patrón Adapter (`FacturaSeguraProvider`)

* `FacturaSeguraProvider` en `apps/invoicing/providers/facturasegura.py` delega sus llamadas HTTP y validación de cuota a `FacturaSeguraClient`.
* Mantiene la interfaz canónica `InvoiceProvider` retornando objetos estructurados `InvoiceResponse` y `StatusResponse`.
* Se expone `FacturaSeguraClient` a través de `apps.invoicing` y `apps.invoicing.client`.

---

## 🧪 Pruebas Unitarias y Automatizadas

Se diseñó la clase de prueba `FacturaSeguraClientAndQuotaProtocolTests` en `apps/invoicing/tests.py` con **17 pruebas exhaustivas**:

1. `test_client_initialization_and_properties`: Verificación de configuración, endpoints y balance inicial (100 total, 90 operativas, 10 blindadas).
2. `test_client_blocks_live_calls_when_live_disabled`: Verificación del guardián `LiveModeDisabledError` en todos los métodos (`login`, `calcular_de`, `generar_de`, `get_estado_sifen`, `dwn_kude`, `dwn_xml`, `sol_cancelacion`, `sol_inutilizacion`).
3. `test_client_login_success`: Autenticación con mock HTTP y extracción de `authentication_token`.
4. `test_client_login_missing_credentials`: Validación de rechazo con código 401 ante credenciales ausentes.
5. `test_client_calcular_de_flow`: Validación del cálculo y retorno del DE enriquecido.
6. `test_client_generar_de_flow`: Validación de generación del CDC de 44 dígitos.
7. `test_client_get_estado_sifen_flow`: Validación de consulta tributaria en SIFEN.
8. `test_client_dwn_kude_flow`: Validación de descarga de KuDE PDF binario (`%PDF-1.4`).
9. `test_client_dwn_xml_flow`: Validación de descarga de XML firmado (`<rDE>`).
10. `test_client_sol_cancelacion_and_inutilizacion`: Validación de eventos de cancelación e inutilización.
11. `test_quota_protocol_operational_consumption`: Verificación del decremento de cuota comercial.
12. `test_quota_protocol_shield_strictly_blocks_at_threshold`: Verificación de bloqueo con `QuotaShieldExhaustedError` al alcanzar el umbral de 10 reservas.
13. `test_quota_protocol_presentation_calls_allowed_within_shield`: Verificación de que llamadas de presentación (`is_presentation=True` / `is_test=True`) consumen de la reserva blindada.
14. `test_quota_protocol_presentation_exhaustion_raises_error`: Verificación de `TestQuotaExhaustedError` al agotar las 10 llamadas de la reserva.
15. `test_quota_consultar_cuota_metrics`: Verificación de las métricas retornadas por `consultar_cuota()`.
16. `test_quota_reset_and_replenish`: Verificación de reinicio e incremento de cuotas.
17. `test_provider_enforces_shield_via_client`: Verificación de que `FacturaSeguraProvider` delega en `FacturaSeguraClient` y respeta el blindaje.

### Resultados de Ejecución

* **`apps.invoicing`:** **78/78 tests aprobados (100% OK)** en 0.784s.
* **Suite Global del Sistema:** **659/659 tests aprobados (100% OK)**, 0 fallos, 0 errores, sin regresiones.
* **Documentación Sphinx:** Compilación limpia HTML (`build succeeded`, 0 warnings, 0 errors).
