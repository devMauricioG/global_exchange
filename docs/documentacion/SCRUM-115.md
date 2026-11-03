# Tarea SCRUM-115: Vistas y formularios para Apertura, Registro de Efectivo y Cierre con Arqueo de Caja

## Información General
- **Código de Tarea:** SCRUM-115
- **Rama Git:** `feature/SCRUM-114`
- **Responsable:** Pablo Elizeche
- **Fecha:** Noviembre 2026
- **Estado:** Finalizado y Verificado

---

## Descripción de la Tarea

> **Título:** Vistas y formularios para Apertura, Registro de Efectivo y Cierre con Arqueo de Caja en `apps/cash/`.  
> **Objetivo:** Desarrollar las vistas basadas en clases (CBV), formularios especializados con soporte multidivisa y plantillas web responsivas para la gestión presencial de ventanilla: apertura formal de turnos con declaración de fondo inicial (RF-22, RN05), panel operativo y consulta del estado de caja en tiempo real, registro de movimientos manuales de efectivo (RF-24) y protocolo de cierre con arqueo ciego contrastando el saldo contable contra el físico y determinando sobrantes o faltantes (RF-23).

---

## Alineación con Requerimientos y Normativa

- **RN05 (Gestión de Cajas):** Las vistas exigen que el usuario esté autenticado y cuente con los roles pertinentes (`admin`, `operator`, `cajero`). La apertura valida que la caja seleccionada no esté abierta ni deshabilitada, y que el cajero no posea turnos activos concurrentes.
- **RF-22 (Apertura y Asignación de Cajas Presenciales):** Formulario dinámico `CashShiftOpenForm` que genera campos para cada divisa activa en el sistema (`initial_<DIVISA>`), persistiendo los fondos iniciales y registrando el `keycloak_user_id` de la sesión Keycloak.
- **RF-23 (Cierre y Arqueo de Caja Físico):** Flujo de cierre con arqueo ciego mediante `BlindReconciliationForm` y `CashShiftCloseView`. La plantilla de arqueo no revela los saldos calculados por el sistema al cajero para evitar sesgos. Al procesar el arqueo, el sistema computa las diferencias exactas (`difference_balances_json`) y emite el acta de arqueo formal (`CashShiftDetailView` / `CashShiftReceiptView`).
- **RF-24 (Auditoría y Monitoreo de Movimientos de Caja):** Formulario `CashMovementForm` y vista `CashMovementCreateView` para registrar aportes, remesas a tesorería y ajustes, validando saldo suficiente en tiempo real para evitar saldos negativos.

---

## Arquitectura y Componentes Desarrollados

### 1. Formularios Especializados (`apps/cash/forms.py`)
- **`CashShiftOpenForm`:**
  - Selección de caja disponible (`CashRegister` activa y cerrada).
  - Generación dinámica de campos de fondo inicial por cada divisa activa en base de datos (`initial_PYG`, `initial_USD`, etc.) con step y decimales correspondientes.
  - Validación de caja habilitada y no ocupada.
  - Integración con `CashService.open_shift()`.
- **`CashMovementForm`:**
  - Registro de movimientos manuales con tipos: aporte manual (dotación), retiro manual (remesa), ajuste por sobrante y ajuste por faltante.
  - Selección de divisa, importe, concepto y número de recibo/remito opcional.
  - Validación preventiva de fondos para egresos (`is_outflow`), impidiendo descubiertos antes de impactar el modelo inmutable.
- **`BlindReconciliationForm`:**
  - Implementación del protocolo de arqueo ciego.
  - Genera campos dinámicos `counted_<DIVISA>` únicamente para las monedas con actividad en el turno.
  - No expone saldos teóricos al operador en la interfaz de conteo.
  - Cierre formal mediante `CashService.close_shift()`.

### 2. Vistas Basadas en Clases (`apps/cash/views.py`)
- **`CashDashboardView`:** Panel principal de control con métricas del turno activo del cajero, saldos en tiempo real por divisa, últimos movimientos registrados, listado de cajas de la sucursal y accesos rápidos a apertura, movimientos y arqueo.
- **`CashShiftOpenView`:** Formulario de apertura de turno presencial con asignación de caja física y fondo inicial por divisa.
- **`CashMovementCreateView`:** Formulario de registro de movimientos manuales de efectivo con verificación de turno activo.
- **`CashShiftCloseView`:** Interfaz protegida para arqueo ciego de caja física y confirmación de cierre.
- **`CashShiftDetailView`:** Acta detallada del turno con resumen de saldos iniciales, movimientos clasificados (entradas/salidas), saldos esperados vs contados físicos, desglose de diferencias (sobrante/faltante/cuadrado), bitácora inmutable y firmas de conformidad.
- **`CashShiftReceiptView`:** Comprobante de cierre y acta de arqueo con diseño optimizado para impresión térmica o estándar.
- **`CashShiftListView`:** Historial de turnos con filtros por estado (`OPEN`, `CLOSED`, `RECONCILED`, `DISCREPANCY`), caja física y rango de fechas.
- **`CashRegisterListView`:** Monitoreo y estado de operatividad de todas las cajas registradoras de la sucursal.
- **`CashShiftStatusApiView`:** Endpoint JSON que provee saldos en vivo del turno actual para actualizaciones asíncronas en ventanilla.

### 3. Enrutamiento (`apps/cash/urls.py` y `config/urls.py`)
- Rutas registradas bajo el prefijo `/cash/` con namespace `cash`:
  - `cash:dashboard` (`/cash/`)
  - `cash:shift_open` (`/cash/shifts/open/`)
  - `cash:movement_create` (`/cash/movements/add/`)
  - `cash:shift_close` (`/cash/shifts/<int:pk>/close/`)
  - `cash:shift_detail` (`/cash/shifts/<int:pk>/`)
  - `cash:shift_receipt` (`/cash/shifts/<int:pk>/receipt/`)
  - `cash:shift_list` (`/cash/shifts/`)
  - `cash:register_list` (`/cash/registers/`)
  - `cash:shift_status_api` (`/cash/api/shifts/current-status/`)

### 4. Plantillas Web Responsivas (`templates/cash/`)
- `dashboard.html`: Panel operativo con tarjetas de saldos, alerta de turno activo o invitación a apertura, tabla de movimientos recientes y estado de ventanillas.
- `shift_open.html`: Formulario de apertura con grilla multidivisa para carga del fondo de gaveta.
- `movement_create.html`: Formulario para dotaciones y remesas con advertencia de impacto contable inmutable.
- `shift_close.html`: Interfaz de arqueo ciego con protocolo de auditoría RF-23 y tarjetas de conteo físico.
- `shift_detail.html`: Acta formal de arqueo con badges de estado, tabla comparativa (Esperado vs Físico vs Diferencia), bitácora de movimientos y bloque de firmas.
- `shift_list.html`: Tabla paginada de auditoría de turnos con filtros.
- `register_list.html`: Vista de tarjetas de cajas físicas y su estado operativo.
- Modificación en `templates/base.html` incorporando el enlace directo `💵 Cajas` en la barra de navegación superior para operadores y administradores.

---

## Verificación y Calidad

### Pruebas Automatizadas (`apps/cash/tests.py`)
Se expandió la suite de pruebas del módulo de 18 a **36 pruebas unitarias e integradas**, cubriendo:
- `CashFormsTests`: Validación y comportamiento dinámico de `CashShiftOpenForm`, `CashMovementForm` (prevención de descubiertos) y `BlindReconciliationForm`.
- `CashViewsTests`:
  - `CashDashboardView`: Renderizado con y sin turno activo.
  - `CashShiftOpenView`: GET y POST con creación atómica de turno y movimientos de fondo inicial.
  - `CashMovementCreateView`: Registro de aportes y validación de saldo insuficiente en extracciones.
  - `CashShiftCloseView`: Protocolo de arqueo ciego (omisión de saldo esperado en UI), cierre cuadrado (`RECONCILED`) y cierre con descuadre (`DISCREPANCY`).
  - `CashShiftDetailView` y `CashShiftReceiptView`: Renderizado de acta de arqueo y comparación física vs contable.
  - `CashShiftListView` y `CashRegisterListView`: Listados y permisos de rol.
  - `CashShiftStatusApiView`: Endpoint JSON con saldo en vivo.

### Resultados de Ejecución de Pruebas
- **`apps.cash`:** **36/36 tests OK** (100% de éxito).
- **Suite global del proyecto:** **536/536 tests OK** (100% de éxito, 0 fallos, 0 errores).

### Documentación Técnica Sphinx
- `docs/sphinx/source/cash.rst` actualizado con `apps.cash.forms`, `apps.cash.views` y `apps.cash.urls`.
- Compilación HTML limpia sin errores: `build succeeded`.

---

## Archivos Intervenidos

- `apps/cash/forms.py` (nuevo)
- `apps/cash/views.py` (nuevo)
- `apps/cash/urls.py` (nuevo)
- `templates/cash/dashboard.html` (nuevo)
- `templates/cash/shift_open.html` (nuevo)
- `templates/cash/movement_create.html` (nuevo)
- `templates/cash/shift_close.html` (nuevo)
- `templates/cash/shift_detail.html` (nuevo)
- `templates/cash/shift_list.html` (nuevo)
- `templates/cash/register_list.html` (nuevo)
- `apps/cash/tests.py` (actualizado y ampliado a 36 tests)
- `config/urls.py` (enrutamiento de `apps.cash.urls`)
- `templates/base.html` (acceso a Cajas en navbar)
- `docs/sphinx/source/cash.rst` (autodoc Sphinx para forms, views y urls)
- `docs/documentacion/SCRUM-115.md` (documento técnico de la tarea)
- `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md` (registro de resolución #23)
- `docs/chat_ia.md` (bitácora de interacción y cambios)

