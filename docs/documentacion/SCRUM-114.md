# Tarea SCRUM-114: Modelado de datos para Cajas, Turnos y Movimientos de Efectivo en apps/cash/

## Información General
- **Código de Tarea:** SCRUM-114
- **Rama Git:** `feature/SCRUM-114`
- **Responsable:** Pablo Elizeche
- **Fecha:** Noviembre 2026
- **Estado:** Finalizado y Verificado

---

## Descripción de la Tarea

> **Título:** Modelado de datos para Cajas, Turnos y Movimientos de Efectivo en `apps/cash/`.  
> **Objetivo:** Diseñar e implementar el modelo de dominio para la gestión presencial de ventanilla en sucursales de Global Exchange, contemplando el ciclo de vida de los puestos de atención física (Cajas), las sesiones de trabajo de cajeros con fondo de apertura y arqueo (Turnos), y la trazabilidad inmutable de entradas y salidas de efectivo (Movimientos).

---

## Alineación con Requerimientos y Normativa

La implementación cumple estrictamente con los requerimientos y reglas del sistema:
- **RN05 (Gestión de Cajas):** Las operaciones de cobro o entrega de efectivo exigen que el usuario posea una caja en estado "Abierta" y cuente con el rol Cajero en su token JWT. Un cajero no puede tener dos turnos abiertos simultáneamente.
- **RF-22 (Apertura y Asignación de Cajas Presenciales):** Registro formal de apertura de sesión asignando al cajero autenticado y registrando la dotación de fondo inicial en efectivo por divisa (`initial_balances_json`).
- **RF-23 (Cierre y Arqueo de Caja Físico):** Conteo físico de billetes, cálculo automático de saldos teóricos esperados (`expected_balances_json`), registro de saldos contados (`final_balances_json`) y cálculo matemático de diferencias (`difference_balances_json`) tipificando el cierre como Cuadrado (`RECONCILED`) o Con Discrepancias (`DISCREPANCY`).
- **RF-24 (Auditoría y Monitoreo de Movimientos de Caja):** Registro inmutable de cada transacción física de efectivo con asociación obligatoria del identificador de usuario Keycloak (`keycloak_user_id`), marca temporal inmutable, sentido de flujo (`IN`/`OUT`), divisa, montos, saldos anteriores y resultantes, e ID de la transacción cambiaria formalizada.

---

## Arquitectura y Componentes Desarrollados

### 1. Estructura del Módulo `apps/cash/`
Se estructuró la aplicación Django bajo `apps/cash/`:
```text
apps/cash/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── services.py
├── tests.py
└── migrations/
    ├── __init__.py
    └── 0001_initial.py
```

### 2. Modelos de Dominio (`apps/cash/models.py`)

#### A. `CashRegister` (Alias: `Caja`)
- Representa el puesto físico de atención o terminal en ventanilla.
- **Campos:** `register_code` (único, ej. `CAJA-01`), `name`, `branch_name`, `status` (`CLOSED`, `OPEN`, `MAINTENANCE`, `INACTIVE`), `current_cashier` (FK User), `initial_balances_json`, `final_balances_json`, `opened_at`, `closed_at`, `is_active`.
- **Propiedades:** `is_open`, `current_shift`.
- **Validaciones:** Validación estricta que impide abrir cajas deshabilitadas o inactivas.

#### B. `CashShift` (Alias: `TurnoCaja`)
- Representa el ciclo de vida de la jornada o sesión operativa del cajero.
- **Campos:** `cash_register`, `cashier`, `keycloak_user_id`, `shift_number` (único, ej. `SHIFT-20261103-CAJA01-0001`), `status` (`OPEN`, `CLOSED`, `RECONCILED`, `DISCREPANCY`), `opened_at`, `closed_at`, `initial_balances_json`, `expected_balances_json`, `final_balances_json`, `difference_balances_json`, `denominations_breakdown_json`, `opening_notes`, `closing_notes`, `closed_by`.
- **Métodos Financieros:**
  - `get_initial_balance(currency_code)`: Extrae el fondo inicial de la divisa solicitada.
  - `calculate_current_balance(currency_code)`: Calcula en tiempo real el saldo neto (Fondo Inicial + Ingresos - Egresos).
  - `calculate_expected_balances()`: Determina los saldos teóricos esperados al cierre para todas las divisas con movimientos.
  - `close_and_reconcile(counted_balances, closed_by, closing_notes, denominations_breakdown)`: Ejecuta el arqueo físico, contrasta con los saldos esperados, sella diferencias, clasifica el estado del turno y libera la caja física.

#### C. `CashMovement` (Alias: `MovimientoEfectivo`)
- Registro inmutable de transacciones físicas de efectivo para auditoría forense (RF-24).
- **Tipos de Movimiento (`MovementType`):** `INITIAL_FLOAT`, `TRANSACTION_IN`, `TRANSACTION_OUT`, `MANUAL_DEPOSIT`, `MANUAL_WITHDRAWAL`, `SURPLUS_ADJUSTMENT`, `SHORTAGE_ADJUSTMENT`, `FINAL_WITHDRAWAL`.
- **Flujos (`MovementFlow`):** `IN` (Ingreso/Entrada), `OUT` (Egreso/Salida).
- **Campos:** `shift`, `movement_type`, `flow`, `currency` (FK `rates.Currency`), `amount`, `previous_balance`, `resulting_balance`, `transaction` (FK `transactions.Transaction`), `concept`, `receipt_number`, `denominations_json`, `cashier`, `keycloak_user_id`, `created_at`, `is_immutable`.
- **Garantía de Inmutabilidad:** `clean()`, `save()` y `delete()` bloquean cualquier intento de modificación o borrado de movimientos registrados.

---

### 3. Capa de Servicios (`apps/cash/services.py`)

- **`CashService.open_shift(...)`:** Apertura atómica con validación de caja disponible, verificación de cajero sin turnos paralelos y generación de movimientos de dotación de fondo inicial.
- **`CashService.register_movement(...)`:** Registro atómico con validación de turno abierto, control de importe positivo y verificación de saldo disponible en caja para prevenir egresos en descubierto (`InsufficientCashBalanceError`).
- **`CashService.register_transaction_cash(...)`:** Integración con transacciones de compra/venta cambiaria, generando automáticamente los movimientos de cobro y entrega en efectivo.
- **`CashService.close_shift(...)`:** Cierre formal con arqueo y cálculo de diferencias.
- **`CashService.get_shift_summary(...)`:** Reporte financiero consolidado por divisa.

---

### 4. Panel de Administración Django (`apps/cash/admin.py`)

- **`CashRegisterAdmin`:** Visualización de cajas con badges de estado dinámico por color, filtros por sucursal y campos de auditoría de solo lectura.
- **`CashShiftAdmin`:** Monitoreo de turnos con badges (`OPEN`, `CLOSED`, `RECONCILED`, `DISCREPANCY`), desglose de saldos y trazabilidad de usuario Keycloak.
- **`CashMovementAdmin`:** Auditoría de movimientos con indicador visual de flujo (`▲ IN` / `▼ OUT`), campos completamente en solo lectura y prohibición explícita de creación/eliminación manual vía panel.

---

### 5. Suite de Pruebas Unitarias e Integración (`apps/cash/tests.py`)

Se diseñaron 18 pruebas automatizadas que cubren exhaustivamente:
1. `CashRegisterModelTests`: Representación de cadena, unicidad de código, bloqueo de apertura en cajas inactivas y verificación de alias en español.
2. `CashShiftLifecycleTests`: Apertura de turno con fondo inicial, impedimento de apertura múltiple en la misma caja, impedimento de turnos concurrentes para el mismo cajero, arqueo cuadrado (`RECONCILED`), arqueo con diferencias (`DISCREPANCY`) y rechazo de doble cierre.
3. `CashMovementTests`: Depósito manual, retiro manual, prevención de saldo insuficiente (`InsufficientCashBalanceError`), rechazo de importes negativos o cero, inmutabilidad estricta ante modificaciones (`save`) y ante intentos de borrado (`delete`).
4. `CashTransactionIntegrationTests`: Formalización de cobro y entrega en efectivo vinculados a una `Transaction` cambiaria, y verificación del reporte consolidado de turnos.

**Resultado:** 18/18 pruebas aprobadas (100% OK).  
**Suite Global:** 518/518 pruebas aprobadas sin regresiones.

---

### 6. Documentación Técnica (Sphinx)
- Creación de `docs/sphinx/source/cash.rst` con autodoc para `apps.cash.admin`, `apps.cash.apps`, `apps.cash.models`, `apps.cash.services` y `apps.cash.tests`.
- Integración en `docs/sphinx/source/modules.rst`.
- Compilación limpia con `sphinx-build -b html` (0 errores, 0 advertencias).

