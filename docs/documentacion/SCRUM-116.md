# Tarea SCRUM-116: Configuración de Rol Cajero, permisos RBAC, blindaje de vistas e Inventario de Billetes por Denominación

## Información General
- **Código de Tarea:** SCRUM-116
- **Rama Git:** `feature/SCRUM-116`
- **Responsable:** Pablo Elizeche
- **Fecha:** Noviembre 2026
- **Estado:** Finalizado y Verificado

---

## Descripción de la Tarea

> **Título:** Configuración de Rol Cajero, permisos RBAC, blindaje de vistas de tesorería y Módulo de Inventario de Billetes por Denominación.  
> **Objetivo:** 
> 1. Incorporar en Keycloak y en `authentication/permissions.py` el rol Cajero y los mixins `@cajero_required` / `CashierRequiredMixin` para restringir el acceso a los módulos de apertura, cobranza y arqueo exclusivamente a operadores autorizados, aislando los turnos por usuario.
> 2. Diseñar e implementar el **Módulo de Inventario Físico de Billetes por Denominación**, controlando las existencias tanto en el inventario central (bóveda) como en cada caja, con apertura, operación presencial y cierre con arqueo y control administrativo.

---

## Alineación con Requerimientos y Normativa

- **RN05 (Gestión de Cajas):** Las operaciones de cobro o entrega de efectivo exigen que el usuario posea una caja en estado "Abierta" y cuente con el rol Cajero (o superior) en su token JWT / grupos de Django. Un cajero no puede operar turnos concurrentes ni manipular turnos ajenos.
- **RF-22 (Apertura y Asignación de Cajas Presenciales):** Restricción de la apertura de ventanilla exclusivamente a usuarios autorizados con rol `cajero`, `operator` o `admin`. Retiro de dotación inicial por denominación desde la bóveda central según reglas configurables y tasas activas.
- **RF-23 (Cierre y Arqueo de Caja Físico):** Blindaje del arqueo ciego para que ningún cajero pueda consultar o manipular el turno de otro compañero. Arqueo físico por denominación con flujo en dos pasos: declaración física del cajero (`PENDING_REVIEW` / `PENDING_CONTROL`) y resolución por el Administrador (Aprobar, Rechazar o Aprobar con Ajuste) transfiriendo el inventario a la bóveda central al cerrar.
- **RF-24 (Auditoría y Monitoreo de Movimientos de Caja):** Aislamiento de movimientos y estados de sesión por cajero titular, con trazabilidad inmutable mediante su identificador en Keycloak (`keycloak_user_id`). Auditoría inmutable de transferencias físicas de billetes (`BanknoteMovement`).

---

# PARTE 1: Rol Cajero, Permisos RBAC y Blindaje de Vistas

### 1. Integración con Keycloak (`keycloak/imports/realm-export.json`)
- Creación y exportación del rol de realm **`cajero`** con descripción formal: `"Cajero / Cashier role for physical branch tellers and cash management"`.
- Creación directa en la instancia activa de Keycloak mediante `kcadm.sh` (`GlobalExchangeRealm`).
- Configuración en `authentication/backends.py` para mapear automáticamente el claim `realm_roles` (incluyendo variantes y sinónimos como `cashier`) al grupo nativo de Django `'cajero'`.

### 2. Permisos y Jerarquía RBAC (`authentication/permissions.py`)
- **Normalización de Roles (`normalize_roles`):** Soporte de sinónimos (`cashier` normalizado a `cajero`).
- **Jerarquía de Privilegios (`has_role`):** `Admin` $\ge$ `Operator` $\ge$ `Cajero` $\ge$ `User`.
  - Superusuarios y administradores adquieren implícitamente los privilegios de cajero y operador.
  - Los operadores adquieren implícitamente privilegios de cajero para cobertura o supervisión de ventanilla.
  - Los cajeros heredan el rol `user`, pero no pueden acceder a configuraciones reservadas a administradores u operadores.
  - Usuarios estándar (`user`) no poseen permisos de caja bajo ninguna circunstancia.
- **Función de Aislamiento de Turnos (`verify_shift_ownership`):** Valida si el usuario autenticado es el propietario (`cashier`) del turno consultado o cuenta con permisos de supervisión (`admin` u `operator`).
- **Decorador para FBVs (`@cajero_required`):** Exige rol `cajero`, `operator` o `admin`.
- **Mixin para CBVs (`CashierRequiredMixin`):** Hereda de `RoleRequiredMixin` configurando `allowed_roles = ['cajero', 'operator', 'admin']`.
- **Mixin de Aislamiento de Turnos (`ShiftOwnershipRequiredMixin`):** Control estricto de acceso por URL o `get_object()`, denegando con HTTP 403 o redirección cuando un cajero intenta acceder a turnos ajenos.

### 3. Procesadores de Contexto y UI (`authentication/context_processors.py` y `auth_tags.py`)
- **`auth_roles`:** Inyecta en todas las plantillas `is_cajero`, `primary_role` (`'Cajero'`) y `primary_role_code` (`'cajero'`).
- **`auth_tags.py`:** Filtros `user|has_role:"cajero"` y badge visual de rol: `<span class="role-badge role-cajero">💵 Cajero</span>`.
- **`templates/base.html`:** Estilos CSS para el badge `.role-cajero` (`#38bdf8`) y enlace `💵 Cajas` protegido condicionalmente.

### 4. Blindaje y Aislamiento en Vistas de Caja (`apps/cash/views.py`)
- **`CashBaseMixin`:** Hereda de `LoginRequiredMixin` y `CashierRequiredMixin`.
- **`CashShiftCloseView`:** Aplica `verify_shift_ownership`, bloqueando intentos de cierre de turnos ajenos con `PermissionDenied` (HTTP 403).
- **`CashShiftDetailView` / `CashShiftReceiptView`:** Sobrescribe `get_object()` con `verify_shift_ownership`.
- **`CashShiftStatusApiView`:** Valida propiedad del turno antes de retornar el JSON de saldos en vivo (HTTP 403).
- **`CashShiftListView`:** Filtra automáticamente el queryset para que cada cajero vea únicamente su propio historial de turnos.

---

# PARTE 2: Módulo de Inventario de Billetes por Denominación

### 1. Modelo de Datos y Entidades (`apps/cash/inventory_models.py`)

1. **`Vault` (Bóveda Central):** Almacenamiento central de efectivo por sucursal (`code`, `name`, `branch_name`, `is_active`). Método `get_stock(denomination)`.
2. **`CurrencyDenomination` (Denominación de Moneda):** Denominaciones oficiales por divisa (`currency`, `value`, `is_coin`, `is_active`, `order`). `unique_together = ('currency', 'value')`.
3. **`BanknoteInventory` (Inventario Físico de Billetes):** Stock físico (`location_type`: VAULT/REGISTER, `vault`, `cash_register`, `currency`, `denomination`, `quantity` $\ge 0$). Validación estricta en `clean()` contra cantidades negativas. Propiedad `total_amount`.
4. **`InitialFloatConfig` (Configuración de Dotación Inicial):** Reglas configurables por el admin (`currency`, `denomination`, `default_quantity`, `allow_partial_fill`, `is_active`).
5. **`BanknoteMovement` (Auditoría Forense Inmutable):** Registro inmutable (`movement_type`, `created_at`, `user`, `shift`, `transaction`, `currency`, `denomination`, `quantity`, `source_location_type`, `target_location_type`, `resulting_source_qty`, `resulting_target_qty`, `reference`). Sobrescribe `save()` y `delete()` bloqueando modificaciones.
6. **`ShiftDenominationCount` (Arqueo Físico por Turno):** Conciliación detallada (`shift`, `currency`, `denomination`, `opening_quantity`, `operations_in`, `operations_out`, `system_expected_quantity`, `counted_quantity`, `difference_quantity`, `difference_amount`, `admin_adjusted_quantity`, `admin_notes`). Métodos: `calculate_expected()`, `update_reconciliation(counted_qty)`.

#### Diagrama de Estados

```
CashRegister:  CLOSED ──(Apertura)──> OPEN ──(Arqueo)──> PENDING_CONTROL ──(Aprobación)──> CLOSED
                                                               │
                                                               └──(Rechazo)──> OPEN

CashShift:     OPEN ──(Cajero declara conteo)──> PENDING_REVIEW ──(Admin aprueba sin diff)──> RECONCILED
                                                                 ──(Admin aprueba con diff/ajuste)──> DISCREPANCY
                                                                 ──(Admin rechaza)──> OPEN
```

### 2. Capa de Servicios (`apps/cash/inventory_services.py`)

- **`InventoryService.open_shift_inventory()`:**
  - Valida turno en estado `OPEN`.
  - Filtra divisas que tengan tasas de cambio activas (`ExchangeRate.objects.filter(is_active=True)`).
  - Consulta `InitialFloatConfig` para cada denominación.
  - Utiliza `select_for_update()` para evitar condiciones de carrera.
  - Si falta stock en bóveda: si `allow_partial_fill=True`, transfiere lo disponible con advertencia; si es `False`, lanza `InsufficientVaultStockError`.
  - Descuenta de bóveda, acredita en caja, genera `BanknoteMovement(SHIFT_OPENING)` y crea `ShiftDenominationCount`.
- **`InventoryService.register_exchange_operation()`:**
  - Valida stock en caja antes de confirmar egresos (`InsufficientRegisterStockError`).
  - Actualiza `BanknoteInventory` en caja para entradas y salidas.
  - Actualiza `operations_in` y `operations_out` en `ShiftDenominationCount`.
  - Registra movimientos inmutables `EXCHANGE_IN` y `EXCHANGE_OUT`.
- **`InventoryService.submit_cashier_count()`:**
  - Registra el conteo físico del cajero por denominación sin ver los valores teóricos.
  - Calcula `difference_quantity` y `difference_amount`.
  - Transiciona turno a `PENDING_REVIEW` y caja a `PENDING_CONTROL`.
  - Protegido contra doble arqueo (`InvalidShiftStateError`).
- **`InventoryService.approve_reconciliation()`:**
  - Si `APPROVE`: transfiere inventario de caja a bóveda (`SHIFT_CLOSING`), cierra turno (`RECONCILED` o `DISCREPANCY`) y caja (`CLOSED`).
  - Si `REJECT`: resetea conteos a `None`, devuelve turno y caja a `OPEN`.
  - Si `APPROVE_WITH_ADJUSTMENT`: valida motivo obligatorio en `notes` y cantidades ajustadas; transfiere a bóveda y cierra como `DISCREPANCY`.
- **`InventoryService.get_register_stock_summary()` / `get_vault_stock_summary()`:**
  - Consultas optimizadas con desglose de billetes, faciales y montos totales.
- **`InventoryService.vault_deposit()`:**
  - Depósito externo de billetes en bóveda con auditoría `VAULT_DEPOSIT`.

### 3. Vistas, Enrutamiento y Plantillas

| URL | Vista | Rol Requerido | Plantilla |
|-----|-------|---------------|-----------|
| `/cash/vault/` | `VaultDashboardView` | `admin` | `cash/vault_dashboard.html` |
| `/cash/vault/deposit/` | `VaultDepositView` | `admin` | `cash/vault_deposit.html` |
| `/cash/shifts/<pk>/inventory/` | `ShiftInventoryView` | `cajero`, `operator`, `admin` | `cash/shift_inventory.html` |
| `/cash/shifts/<pk>/denomination-count/` | `CashierDenominationCountView` | `cajero` (titular) | `cash/cashier_denomination_count.html` |
| `/cash/admin/reconciliation/` | `AdminReconciliationListView` | `admin` | `cash/admin_reconciliation_list.html` |
| `/cash/admin/reconciliation/<pk>/` | `AdminReconciliationActionView` | `admin` | `cash/admin_reconciliation_detail.html` |

### 4. Historias de Usuario con Criterios de Aceptación (Gherkin)

- **US-01:** Depósito de billetes en bóveda central por el Administrador.
- **US-02:** Apertura de turno con dotación automática de billetes por denominación (solo divisas con tasa activa).
- **US-03:** Alerta de dotación parcial por stock insuficiente en bóveda / bloqueo si no se permite parcial.
- **US-04:** Operación cambiaria actualiza inventario de caja en tiempo real.
- **US-05:** Bloqueo de operaciones cambiarias si la caja no posee billetes suficientes de la denominación a entregar.
- **US-06:** Cajero declara arqueo físico por denominación bajo protocolo de arqueo ciego.
- **US-07:** Administrador aprueba arqueo y transfiere inventario físico de caja a bóveda.
- **US-08:** Administrador rechaza arqueo devolviendo el turno a estado ABIERTO para reconteo.
- **US-09:** Administrador aprueba con ajuste manual documentando motivo obligatorio.
- **US-10:** Auditoría forense inmutable: movimientos de billetes protegidos contra edición y eliminación.

---

## Verificación y Calidad

### Pruebas Automatizadas
1. **`authentication/tests.py`:**
   - Suite `CajeroRoleAndShiftIsolationTests`: **70/70 tests OK** (100%).
2. **`apps/cash/tests.py`:**
   - Suite `CashRBACAndShiftIsolationTests`: **45/45 tests OK** (100%).
3. **`apps/cash/tests_inventory.py`:**
   - 27 pruebas específicas para modelos, inmutabilidad, servicios de apertura, dotación parcial, operaciones, stock insuficiente, arqueo, aprobación, rechazo, ajuste y depósitos en bóveda: **27/27 tests OK** (100%).
4. **Suite Completa del Proyecto:**
   - **581/581 tests OK** (100% de éxito, 0 fallos, 0 errores, sin regresiones).

---

## Archivos Intervenidos en SCRUM-116

### Autenticación y RBAC
- `keycloak/imports/realm-export.json`
- `authentication/backends.py`
- `authentication/permissions.py`
- `authentication/context_processors.py`
- `authentication/templatetags/auth_tags.py`
- `authentication/tests.py`
- `templates/base.html`

### Módulo de Caja e Inventario
- `apps/cash/models.py` (estados `PENDING_CONTROL` y `PENDING_REVIEW`)
- `apps/cash/inventory_models.py` (modelos `Vault`, `CurrencyDenomination`, `BanknoteInventory`, `InitialFloatConfig`, `BanknoteMovement`, `ShiftDenominationCount`)
- `apps/cash/inventory_services.py` (`InventoryService`, excepciones de dominio)
- `apps/cash/inventory_views.py` (6 vistas basadas en clases)
- `apps/cash/inventory_urls.py` (enrutamiento de inventario)
- `apps/cash/urls.py` (inclusión de rutas de inventario)
- `apps/cash/admin.py` (registro de 6 modelos e inline de arqueo por denominación)
- `apps/cash/migrations/0002_vault_alter_cashregister_status_and_more.py` (migración de DB)
- `apps/cash/views.py` (blindaje con `CashierRequiredMixin` y aislamiento estricto)
- `apps/cash/tests.py` (suite de pruebas RBAC)
- `apps/cash/tests_inventory.py` (suite de 27 pruebas de inventario)

### Plantillas
- `templates/cash/vault_dashboard.html`
- `templates/cash/vault_deposit.html`
- `templates/cash/shift_inventory.html`
- `templates/cash/cashier_denomination_count.html`
- `templates/cash/admin_reconciliation_list.html`
- `templates/cash/admin_reconciliation_detail.html`

### Documentación
- `docs/documentacion/SCRUM-116.md`
- `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md`
- `docs/chat_ia.md`
