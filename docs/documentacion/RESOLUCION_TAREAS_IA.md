# Bitácora Consolidada de Resolución de Tareas con Asistencia de Inteligencia Artificial (IA)

**Proyecto:** Global Exchange  
**Equipo:** Equipo 88  
**Sprints:** SCRUM Sprint 1 y Sprint 2  
**Herramientas de IA utilizadas:** Google Antigravity / Gemini / Claude  

---

## Índice de Tareas Resueltas con IA

1. [SCRUM-26: Vinculación automática de identidades Keycloak OIDC con la ficha de Cliente](#1-scrum-26-vinculación-automática-de-identidades-keycloak-oidc-con-la-ficha-de-cliente)
2. [SCRUM-27: Implementación de vistas/endpoints para el CRUD de Clientes con filtros por segmento](#2-scrum-27-implementación-de-vistasedpoints-para-el-crud-de-clientes-con-filtros-por-segmento)
3. [SCRUM-28: Desarrollo de plantilla base con Menú Principal dinámico según roles de JWT](#3-scrum-28-desarrollo-de-plantilla-base-con-menú-principal-dinámico-según-roles-de-jwt)
4. [SCRUM-29: Construcción de interfaces gráficas para el listado, creación y edición de Clientes](#4-scrum-29-construcción-de-interfaces-gráficas-para-el-listado-creación-y-edición-de-clientes)
5. [SCRUM-30: Redacción e integración de Pruebas Unitarias (PyUnit) para CRUD y autenticación](#5-scrum-30-redacción-e-integración-de-pruebas-unitarias-pyunit-para-crud-y-autenticación)
6. [SCRUM-31: Configuración de documentación automática de código y bitácora IA](#6-scrum-31-configuración-de-documentación-automática-de-código-y-bitácora-ia)
7. [SCRUM-41: Estandarización de comandos de ejecución de tests y verificación en README.md](#7-scrum-41-estandarización-de-comandos-de-ejecución-de-tests-y-verificación-en-readmemd)
8. [SCRUM-42: Actualización de documentos de diseño UML y especificación de pruebas (ERS / DIS_CLA / DIS_CPR)](#8-scrum-42-actualización-de-documentos-de-diseño-uml-y-especificación-de-pruebas-ers--dis_cla--dis_cpr)
9. [SCRUM-55: Modelo, vistas y formularios para el CRUD de Medios de Pago de Clientes (payments)](#9-scrum-55-modelo-vistas-y-formularios-para-el-crud-de-medios-de-pago-de-clientes-payments)

---

### 1. SCRUM-26: Vinculación automática de identidades Keycloak OIDC con la ficha de Cliente

* **Objetivo:** Interceptar el login exitoso en Keycloak para vincular automáticamente la ficha del cliente en Django mediante el `sub` (identificador único) y sincronizar los datos de perfil.
* **Aportes y Solución con IA:**
  * Diseño del manejador de señales `user_logged_in` en `customers/signals.py` y `customers/services.py` para desacoplar la lógica de autenticación del modelo de dominio.
  * Estrategia de vinculación bidireccional: búsqueda primaria por `keycloak_id` (`sub`) y secundaria por correo electrónico institucional con fallback controlado.
  * Cobertura de pruebas unitarias automatizadas para casos límite (usuarios preexistentes, nuevos registros, actualización de metadatos).
* **Archivos intervenidos:**
  * `customers/signals.py`
  * `customers/services.py`
  * `customers/apps.py`
  * `customers/tests.py`

---

### 2. SCRUM-27: Implementación de vistas/endpoints para el CRUD de Clientes con filtros por segmento

* **Objetivo:** Construir tanto las vistas basadas en clases (CBVs) como la API REST para listar, crear, consultar detalle, actualizar y eliminar clientes, con filtros avanzados por segmento y búsqueda por documento/RUC.
* **Aportes y Solución con IA:**
  * Implementación de vistas CBVs robustas: `ClienteListView`, `ClienteDetailView`, `ClienteCreateView`, `ClienteUpdateView` y `ClienteDeleteView`.
  * Filtros dinámicos por `segmento` (Minorista, Mayorista, Corporativo, VIP) y búsqueda difusa/exacta por término de texto en `nombre`, `ruc` y `correo`.
  * Exposición de endpoints RESTful con serialización limpia y validación de datos para integración externa.
  * Inclusión de docstrings estructurados compatibles con Sphinx.
* **Archivos intervenidos:**
  * `customers/views.py`
  * `customers/forms.py`
  * `customers/urls.py`
  * `customers/tests.py`

---

### 3. SCRUM-28: Desarrollo de plantilla base con Menú Principal dinámico según roles de JWT

* **Objetivo:** Diseñar la estructura base de interfaz web y programar un motor de renderizado condicional en la barra de navegación basado en los roles y privilegios extraídos del token JWT de Keycloak.
* **Aportes y Solución con IA:**
  * Implementación del Context Processor `auth_roles` (`authentication/context_processors.py`) para inyectar de forma transversal los roles y permisos del usuario activo en todas las plantillas.
  * Creación de Template Tags personalizados (`authentication/templatetags/auth_tags.py`): tags `has_role`, `has_any_role` y filtros de verificación de claims.
  * Maquetación de `templates/base.html` con navbar reactivo, badge de rol de usuario, dropdown de perfil y elementos de navegación visibles exclusivamente a roles autorizados (Admin, Operador, Auditor, Cliente).
* **Archivos intervenidos:**
  * `authentication/context_processors.py`
  * `authentication/templatetags/auth_tags.py`
  * `templates/base.html`
  * `authentication/tests.py`

---

### 4. SCRUM-29: Construcción de interfaces gráficas para el listado, creación y edición de Clientes

* **Objetivo:** Crear las pantallas de usuario (HTML/CSS) para el módulo de clientes, priorizando usabilidad, estética moderna y responsividad.
* **Aportes y Solución con IA:**
  * Diseño del listado interactivo (`cliente_list.html`): métricas clave (KPIs), selector de tabs por segmento, tabla de alta legibilidad con acciones por fila y estados vacíos (*empty states*).
  * Formularios estilizados (`cliente_form.html`): selectores visuales por tarjetas (*radio cards*) para segmentación y toggles de activación.
  * Pantalla de detalle (`cliente_detail.html`) y confirmación modal de eliminación (`cliente_confirm_delete.html`).
* **Archivos intervenidos:**
  * `templates/customers/cliente_list.html`
  * `templates/customers/cliente_form.html`
  * `templates/customers/cliente_detail.html`
  * `templates/customers/cliente_confirm_delete.html`

---

### 5. SCRUM-30: Redacción e integración de Pruebas Unitarias (PyUnit) para CRUD y autenticación

* **Objetivo:** Garantizar la cobertura, confiabilidad y calidad del código de modelos, vistas, formularios y control de acceso.
* **Aportes y Solución con IA:**
  * Suites de prueba completas para validación de formato de RUC, unicidad de correo, reglas de segmentación y ciclos de persistencia en `customers/tests.py`.
  * Pruebas de integración de autenticación en `authentication/tests.py`: redirecciones a OIDC para rutas protegidas, validación de herencia de roles y acceso a vistas por rol.
* **Archivos intervenidos:**
  * `customers/tests.py`
  * `authentication/tests.py`
  * `config/settings/test.py`

---

### 6. SCRUM-31: Configuración de documentación automática de código y bitácora IA

* **Objetivo:** Establecer el estándar de documentación del código fuente con Sphinx y la bitácora de interacción con IA (`docs/chat_ia.md`).
* **Aportes y Solución con IA:**
  * Configuración de extensiones autodoc, napoleon y sphinx_rtd_theme en `docs/sphinx/conf.py`.
  * Registro de conversaciones con asistentes en `docs/chat_ia.md`.
* **Archivos intervenidos:**
  * `docs/sphinx/conf.py`
  * `docs/sphinx/index.rst`
  * `docs/chat_ia.md`

---

### 7. SCRUM-41: Estandarización de comandos de ejecución de tests y verificación en README.md

* **Objetivo:** Documentar exhaustivamente los comandos de ejecución de pruebas con Docker Compose y análisis de cobertura (`coverage`), garantizando que la totalidad de pruebas de `authentication` y `customers` pasen sin fallos.
* **Aportes y Solución con IA:**
  * Detección y corrección del desacople de settings en `manage.py`: enrutamiento automático a `config.settings.test` (SQLite in-memory) al invocar `test`.
  * Inclusión de `coverage>=7.6.0` en `requirements.txt`, `.gitignore` y `.dockerignore`.
  * Redacción de la sección detallada en `README.md` (comandos Docker Compose y local venv, suite completa, módulos y reportes de cobertura).
  * Validación integral con 69 tests aprobados y 95% de cobertura de código.
* **Archivos intervenidos:**
  * `manage.py`
  * `requirements.txt`
  * `README.md`
  * `docs/documentacion/SCRUM-41_ESTANDARIZACION_TESTS.md`

---

### 8. SCRUM-42: Actualización de documentos de diseño UML y especificación de pruebas (ERS / DIS_CLA / DIS_CPR)

* **Objetivo:** Actualizar los documentos formales de diseño de clases (`EQUIPO_88_B_DIS_CLA_01`), diagrama de paquetes (`DIS_PAQ_01`), matriz de casos de prueba (`EQUIPO_88_B_DIS_CPR_01`) y requerimientos (`EQUIPO_08_A_ERS_01`) incorporando la entidad `CustomerUserAssignment`, las reglas de cambio de cliente activo y las pruebas del visualizador de documentación.
* **Aportes y Solución con IA:**
  * Modelado formal de `CustomerUserAssignment` en el diseño de clases: atributos completos, restricciones de unicidad `unique_together`, asignación de representante principal único y métodos de ciclo de vida (`activate()`, `deactivate()`, `clean()`).
  * Especificación detallada de la arquitectura de Cliente Activo: diseño de `ActiveCustomerMiddleware`, context processor `active_customer_context` y vista segura `CustomerSwitchActiveView` con validación de pertenencia y respuesta `HTTP 403 Forbidden` ante intentos de suplantación.
  * Diseño del componente `ServeSphinxDocsView` y mapeo de rutas para el visualizador integrado de documentación Sphinx con prevención de Path Traversal.
  * Actualización del diagrama de paquetes en sintaxis Mermaid y detalle de responsabilidades por capa en `DIS_PAQ_01`.
  * Redacción y anexado de la **Matriz Formal de Casos de Prueba (DIS_CPR_01)** compuesta por 18 casos de prueba estructurados (6 para `CustomerUserAssignment`, 6 para reglas de Cliente Activo y 6 para el Visualizador Sphinx).
  * Refinamiento de requerimientos funcionales en `ERS_01` (RF04/RF05, RF-21, nuevo RF-27 y registro de versión ERS v3.1 en el historial de cambios).
* **Archivos intervenidos:**
  * `docs/documentacion/Proyecto/EQUIPO_88_B_DIS_CLA_01_detallado.md`
  * `docs/documentacion/Proyecto/EQUIPO_88_B_DIS_PAQ_01.md`
  * `docs/documentacion/Proyecto/EQUIPO_88_B_DIS_CPR_01_detallado.md`
  * `docs/documentacion/Proyecto/EQUIPO_08_A_ERS_01.md`
  * `docs/documentacion/SCRUM-42_DISENO_UML_Y_CASOS_DE_PRUEBA.md`
  * `docs/documentacion/Jira workflow/TAREAS.md`
  * `docs/chat_ia.md`

---

### 9. SCRUM-55: Modelo, vistas y formularios para el CRUD de Medios de Pago de Clientes (payments)

* **Objetivo:** Construir la aplicación Django `payments` con el modelo `PaymentMethod`, vistas CBV web protegidas contra IDOR, endpoints API REST (JSON), formularios validados y plantillas dark-mode responsivas para la gestión segura de cuentas bancarias y billeteras de los clientes.
* **Aportes y Solución con IA:**
  * Definición del modelo `PaymentMethod` con clave foránea a `Cliente`, selector de `TipoMedio` (`TRANSFERENCIA`, `BILLETERA`, `TARJETA`, `EFECTIVO`, `OTRO`), datos de entidad bancaria, número de cuenta o teléfono, titular y banderas de predeterminado y activo.
  * Implementación de la exclusividad atómica en `PaymentMethod.save()` para asegurar un único medio de pago predeterminado por cliente sin afectar a otros clientes.
  * Arquitectura de seguridad con resolución de cliente activo (`get_current_cliente`) y filtrado estricto en `get_queryset()` para prevenir vulnerabilidades de Insecure Direct Object References (IDOR), respondiendo `HTTP 404` ante intentos de acceso o manipulación cruzada.
  * Desarrollo de CBVs (`PaymentMethodListView`, `PaymentMethodCreateView`, `PaymentMethodUpdateView`, `PaymentMethodDeleteView`, `PaymentMethodSetDefaultView`, `PaymentMethodToggleActiveView`) y endpoints REST (`PaymentMethodListCreateAPIView`, `PaymentMethodDetailAPIView`).
  * Diseño de interfaces con KPIs en tarjetas, filtros de búsqueda, selector de predeterminado y estados vacíos (*empty states*).
  * Elaboración de 21 tests automatizados que elevan la suite completa a 90 tests aprobados y 93% de cobertura.
* **Archivos intervenidos:**
  * `payments/models.py`
  * `payments/forms.py`
  * `payments/views.py`
  * `payments/urls.py`
  * `payments/admin.py`
  * `payments/apps.py`
  * `payments/tests.py`
  * `payments/migrations/0001_initial.py`
  * `templates/payments/paymentmethod_list.html`
  * `templates/payments/paymentmethod_form.html`
  * `templates/payments/paymentmethod_confirm_delete.html`
  * `config/settings/base.py`
  * `config/urls.py`
  * `templates/base.html`
  * `docs/documentacion/SCRUM-55_CRUD_MEDIOS_DE_PAGO.md`
  * `docs/documentacion/Jira workflow/TAREAS.md`
  * `docs/chat_ia.md`
