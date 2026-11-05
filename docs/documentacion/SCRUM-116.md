# Tarea SCRUM-116: Configuración de Rol Cajero, permisos RBAC y blindaje de vistas de tesorería

## Información General
- **Código de Tarea:** SCRUM-116
- **Rama Git:** `feature/SCRUM-116`
- **Responsable:** Pablo Elizeche
- **Fecha:** Noviembre 2026
- **Estado:** Finalizado y Verificado

---

## Descripción de la Tarea

> **Título:** Configuración de Rol Cajero, permisos RBAC y blindaje de vistas de tesorería.  
> **Objetivo:** Incorporar en Keycloak y en `authentication/permissions.py` el rol Cajero y los mixins `@cajero_required` / `CashierRequiredMixin` para restringir el acceso a los módulos de apertura, cobranza y arqueo exclusivamente a operadores autorizados, aislando los turnos por usuario.

---

## Alineación con Requerimientos y Normativa

- **RN05 (Gestión de Cajas):** Las operaciones de cobro o entrega de efectivo exigen que el usuario posea una caja en estado "Abierta" y cuente con el rol Cajero (o superior) en su token JWT / grupos de Django. Un cajero no puede operar turnos concurrentes ni manipular turnos ajenos.
- **RF-22 (Apertura y Asignación de Cajas Presenciales):** Restricción de la apertura de ventanilla exclusivamente a usuarios autorizados con rol `cajero`, `operator` o `admin`.
- **RF-23 (Cierre y Arqueo de Caja Físico):** Blindaje del arqueo ciego para que ningún cajero pueda consultar, arquea o cerrar el turno de otro compañero, reservando la supervisión transversal exclusivamente a los roles `operator` y `admin`.
- **RF-24 (Auditoría y Monitoreo de Movimientos de Caja):** Aislamiento de movimientos y estados de sesión por cajero titular, con trazabilidad inmutable mediante su identificador en Keycloak (`keycloak_user_id`).

---

## Arquitectura y Componentes Desarrollados

### 1. Integración con Keycloak (`keycloak/imports/realm-export.json`)
- Creación y exportación del rol de realm **`cajero`** con descripción formal: `"Cajero / Cashier role for physical branch tellers and cash management"`.
- Creación directa en la instancia activa de Keycloak mediante `kcadm.sh` (`GlobalExchangeRealm`).
- Configuración en `authentication/backends.py` para mapear automáticamente el claim `realm_roles` (incluyendo variantes y sinónimos como `cashier`) al grupo nativo de Django `'cajero'`.

### 2. Permisos y Jerarquía RBAC (`authentication/permissions.py`)
- **Normalización de Roles (`normalize_roles`):**
  - Soporte de sinónimos (`cashier` normalizado a `cajero`).
- **Jerarquía de Privilegios (`has_role`):**
  - `Admin` $\ge$ `Operator` $\ge$ `Cajero` $\ge$ `User`.
  - Superusuarios y administradores adquieren implícitamente los privilegios de cajero y operador.
  - Los operadores adquieren implícitamente privilegios de cajero para cobertura o supervisión de ventanilla.
  - Los cajeros heredan el rol `user`, pero no pueden acceder a configuraciones reservadas a administradores u operadores (ej. tasas, límites, comisiones).
  - Usuarios estándar (`user`) no poseen permisos de caja bajo ninguna circunstancia.
- **Función de Aislamiento de Turnos (`verify_shift_ownership`):**
  - Valida si el usuario autenticado es el propietario (`cashier`) del turno consultado o cuenta con permisos de supervisión (`admin` u `operator`).
- **Decorador para FBVs (`@cajero_required`):**
  - Exige rol `cajero`, `operator` o `admin`. Soporta redirección personalizada o lanzamiento de `PermissionDenied` (HTTP 403).
- **Mixin para CBVs (`CashierRequiredMixin`):**
  - Hereda de `RoleRequiredMixin` configurando `allowed_roles = ['cajero', 'operator', 'admin']`.
- **Mixin de Aislamiento de Turnos (`ShiftOwnershipRequiredMixin`):**
  - Control estricto de acceso por URL o `get_object()`, denegando con HTTP 403 o redirección cuando un cajero intenta acceder a turnos ajenos.

### 3. Procesadores de Contexto y UI (`authentication/context_processors.py` y `auth_tags.py`)
- **`auth_roles`:** Inyecta en todas las plantillas:
  - `is_cajero`: booleano verdadero para cajeros, operadores y administradores.
  - `primary_role`: `'Cajero'` para usuarios cuyo rol principal sea ventanilla.
  - `primary_role_code`: `'cajero'`.
- **`auth_tags.py`:**
  - Soporte para filtros `user|has_role:"cajero"` y `user|has_role:"cashier"`.
  - Badge visual de rol: `<span class="role-badge role-cajero">💵 Cajero</span>`.
- **`templates/base.html`:**
  - Estilos CSS para el badge `.role-cajero` con paleta celeste `#38bdf8`.
  - Enlace de navegación `💵 Cajas` protegido condicionalmente con `{% if is_cajero or is_operator or user|has_any_role:"admin,operator,cajero" %}`, separándolo de las opciones administrativas de comisiones y límites.

### 4. Blindaje y Aislamiento en Vistas de Caja (`apps/cash/views.py`)
- **`CashBaseMixin`:** Ahora hereda de `LoginRequiredMixin` y `CashierRequiredMixin`, aplicando el control RBAC de manera homogénea a las 9 vistas del módulo de caja.
- **`CashShiftCloseView`:** Aplica `verify_shift_ownership`: si un cajero intenta cerrar un turno ajeno vía URL `/cash/shifts/<pk>/close/`, se bloquea con `PermissionDenied` (HTTP 403).
- **`CashShiftDetailView` / `CashShiftReceiptView`:** Sobrescribe `get_object()` con `verify_shift_ownership`, impidiendo que cajeros no autorizados visualicen o impriman actas de arqueo de compañeros.
- **`CashShiftStatusApiView`:** Valida propiedad del turno antes de retornar el JSON de saldos en vivo, bloqueando peticiones no autorizadas con HTTP 403.
- **`CashShiftListView`:** Filtra automáticamente el queryset para que cada cajero vea únicamente su propio historial de turnos (`qs.filter(cashier=request.user)`), salvo que sea supervisor (`admin` u `operator`).

---

## Verificación y Calidad

### Pruebas Automatizadas
1. **`authentication/tests.py`:**
   - Creada suite `CajeroRoleAndShiftIsolationTests` (9 pruebas específicas para RBAC, jerarquía, decoradores, mixins, aislamiento de turnos, tags y mapeo Keycloak).
   - Total módulo `authentication`: **70/70 tests OK** (100% éxito).
2. **`apps/cash/tests.py`:**
   - Creada suite `CashRBACAndShiftIsolationTests` (9 pruebas para verificación de accesos, redirección a clientes estándar, bloqueo HTTP 403 ante intentos de manipulación de turnos ajenos y filtrado multi-inquilino en listas).
   - Total módulo `apps.cash`: **45/45 tests OK** (100% éxito).
3. **Suite Completa del Proyecto:**
   - **554/554 tests OK** (100% de éxito, 0 fallos, 0 errores, sin regresiones).

### Documentación Sphinx
- Compilación HTML limpia sin advertencias ni errores: `build succeeded`.

---

## Archivos Intervenidos

- `keycloak/imports/realm-export.json` (incorporación del rol `cajero` en el realm)
- `authentication/backends.py` (mapeo OIDC de claims `cajero` y `cashier` a grupos de Django)
- `authentication/permissions.py` (jerarquía RBAC, `cajero_required`, `CashierRequiredMixin`, `verify_shift_ownership`, `ShiftOwnershipRequiredMixin`)
- `authentication/context_processors.py` (variables `is_cajero`, `primary_role` y `primary_role_code`)
- `authentication/templatetags/auth_tags.py` (filtros y badges para rol cajero)
- `authentication/tests.py` (suite `CajeroRoleAndShiftIsolationTests`)
- `templates/base.html` (badge `.role-cajero` y navegación condicional para `💵 Cajas`)
- `apps/cash/views.py` (blindaje con `CashierRequiredMixin` y aislamiento estricto de turnos)
- `apps/cash/tests.py` (suite `CashRBACAndShiftIsolationTests`)
- `docs/documentacion/SCRUM-116.md` (documento técnico de la tarea)
- `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md` (registro #24)
- `docs/chat_ia.md` (bitácora de interacción y cambios)
