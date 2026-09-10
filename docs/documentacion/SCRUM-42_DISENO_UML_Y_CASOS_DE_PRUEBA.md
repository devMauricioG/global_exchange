# Documentación Técnica — SCRUM-42: Actualización de Diseño UML y Casos de Prueba

**ID Jira:** SCRUM-42  
**Épica Principal:** SCRUM-33 (Multi-Representación de Clientes y Selector de Cliente Activo)  
**Sprint:** SCRUM Sprint 2  
**Autor:** Pablo Elizeche (con asistencia de IA Antigravity / Gemini)  
**Fecha:** 08/09/2026  
**Rama de trabajo:** `feature/SCRUM-42`  

---

## 1. Descripción del Requerimiento

Actualizar los documentos formales de diseño de clases (`EQUIPO_88_B_DIS_CLA_01`), diagrama de paquetes (`DIS_PAQ_01`) y matriz de casos de prueba (`EQUIPO_88_B_DIS_CPR_01`), complementando la especificación de requerimientos de software (`EQUIPO_08_A_ERS_01`), incorporando de manera rigurosa:
1. La entidad intermedia `CustomerUserAssignment` para multi-representación Usuario ↔ Clientes.
2. Las reglas de negocio, ciclo de vida y seguridad para la selección y cambio dinámico de Cliente Activo en sesión.
3. Las especificaciones de diseño y la matriz de casos de prueba para el Visualizador Integrado de Documentación Técnica autogenerada por Sphinx.

---

## 2. Diagnóstico de la Documentación Preexistente

1. **DIS_CLA_01 (Diseño de Clases):** La clase `CustomerUserAssignment` figuraba únicamente con 3 atributos preliminares (`id`, `is_primary_representative`, `assigned_at`), sin especificar claves foráneas hacia `User` y `Customer`, restricciones de unicidad (`unique_together`), métodos de validación ni las clases y componentes para la gestión del cliente activo (`ActiveCustomerMiddleware`, `CustomerSwitchActiveView`) y el visualizador de Sphinx (`ServeSphinxDocsView`).
2. **DIS_PAQ_01 (Arquitectura de Paquetes):** El paquete `apps.customers` se describía con una referencia tentativa (`Assignment`), sin reflejar la relación con el middleware de cliente activo, el context processor transversal, ni la interacción con el núcleo `global_exchange_core` para servir la documentación técnica HTML generada por Sphinx.
3. **DIS_CPR_01 (Casos de Prueba):** El documento original contenía la transcripción de la infraestructura de producción, pero carecía de la **Matriz Formal de Casos de Prueba de Software (CPR)** requerida para validar la multi-representación, la prevención de suplantación en cambio de cliente activo (IDOR) y el comportamiento del visualizador web de documentación.
4. **ERS_01 (Requerimientos de Software):** Los requerimientos funcionales RF04/RF05 y RF-21 requerían alineación con la implementación del Sprint 2 y no existía un requerimiento formal (RF-27) que contemplara la disponibilidad integrada de la documentación técnica Sphinx en el portal.

---

## 3. Modificaciones y Actualizaciones Realizadas

### 3.1. Diseño Detallado de Clases (`EQUIPO_88_B_DIS_CLA_01_detallado.md`)
* **Entidad `CustomerUserAssignment`**:
  * Atributos completos: `id` (PK BigInt), `user` (FK User CASCADE), `customer` (FK Customer CASCADE), `is_primary_representative` (Boolean), `is_active` (Boolean), `role_in_company` (String) y `assigned_at` (DateTime auto_now_add).
  * Restricciones de integridad: `unique_together = ('user', 'customer')` y validación de único representante principal activo por cliente.
  * Métodos de dominio: `clean()`, `save()`, `set_as_primary()`, `deactivate()`, `activate()` y `can_transact()`.
* **Componentes de Cliente Activo**:
  * `ActiveCustomerMiddleware`: ciclo de vida HTTP, resolución de `active_customer_id` en sesión, verificación de pertenencia e inyección en `request.active_customer` con fallback automático.
  * `active_customer_context_processor`: inyección global en plantillas de `active_customer` y `user_assigned_customers`.
  * `CustomerSwitchActiveView`: endpoint seguro que valida permisos de asignación activa y devuelve código **`HTTP 403 Forbidden`** ante intentos no autorizados.
* **Componentes del Visualizador de Documentación (Sphinx)**:
  * `ServeSphinxDocsView`: vista para servir de forma segura el árbol HTML de `docs/sphinx/build/html/` con tipificado de tipos MIME y mitigación contra Path Traversal.

### 3.2. Diagrama y Arquitectura de Paquetes (`EQUIPO_88_B_DIS_PAQ_01.md`)
* Se formalizó `apps.customers` incorporando `CustomerUserAssignment`, `ActiveCustomerMiddleware`, `active_customer_context` y `CustomerSwitchActiveView`.
* Se integró en `global_exchange_core` el componente `ServeSphinxDocsView` y su mapeo de rutas `/docs/` en `urls.py`.
* Se incorporó un diagrama de paquetes en sintaxis **Mermaid** visualizando el flujo entre cliente web, núcleo, capas de autenticación, gestión de clientes, dominio transaccional y el árbol estático de Sphinx.
* Se actualizaron las matrices de flujo funcional y responsabilidades por capa.

### 3.3. Matriz Formal de Casos de Prueba (`EQUIPO_88_B_DIS_CPR_01_detallado.md`)
Se estructuraron y anexaron 18 casos de prueba formales organizados en 3 matrices exhaustivas:
1. **Módulo 1: `CustomerUserAssignment` (CPR-CUA-001 a CPR-CUA-006):**
   - Creación válida, unicidad `(user, customer)`, único representante principal por cliente, multi-representación simultánea, desactivación lógica y cascada referencial.
2. **Módulo 2: Reglas de Cambio de Cliente Activo (CPR-ACT-001 a CPR-ACT-006):**
   - Selección automática tras login, cambio dinámico exitoso, rechazo por falta de asignación (**HTTP 403 Forbidden**), rechazo por asignación inactiva, persistencia en sesión e inyección en plantillas mediante context processor.
3. **Módulo 3: Visualizador de Documentación Sphinx (CPR-DOC-001 a CPR-DOC-006):**
   - Acceso a `/docs/` (HTTP 200 OK y `text/html`), entrega de recursos estáticos (`.css`, `.js`), mitigación de Directory Traversal (`../../`), manejo de errores 404 controlados, integración de enlace en `base.html` y control de acceso por roles.

### 3.4. Especificación de Requerimientos de Software (`EQUIPO_08_A_ERS_01.md`)
* Se refinaron los requerimientos **RF04 / RF05** (Selección y cambio de cliente activo en sesión) y **RF-21** (Multi-representación con `CustomerUserAssignment`).
* Se incorporó **RF-27** (Visualizador Integrado de Documentación Técnica Sphinx HTML).
* Se asentó la versión **ERS v3.1** en la tabla de Historia de Cambios.

---

## 4. Trazabilidad con Tareas de Jira

| Tarea Jira | Componente Documentado | Documento Principal Modificado |
|---|---|---|
| **SCRUM-37** | Modelo `CustomerUserAssignment` | `DIS_CLA_01`, `DIS_PAQ_01`, `ERS_01`, `DIS_CPR_01` |
| **SCRUM-38** | `ActiveCustomerMiddleware` y Context Processor | `DIS_CLA_01`, `DIS_PAQ_01`, `DIS_CPR_01` |
| **SCRUM-39** | Endpoint y Vista `switch_active_customer` | `DIS_CLA_01`, `DIS_PAQ_01`, `DIS_CPR_01` |
| **SCRUM-40** | Componente visual Dropdown en `base.html` | `DIS_CLA_01`, `DIS_PAQ_01`, `DIS_CPR_01` |
| **SCRUM-35** | Vista de Documentación Sphinx en Django | `DIS_CLA_01`, `DIS_PAQ_01`, `DIS_CPR_01` |
| **SCRUM-36** | Enlace de Documentación en Navbar (`base.html`) | `DIS_PAQ_01`, `DIS_CPR_01`, `ERS_01` |
| **SCRUM-42** | Consolidación y actualización integral de diseño | Todos los documentos anteriores |
