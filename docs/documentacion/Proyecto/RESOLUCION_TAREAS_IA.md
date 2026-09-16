# Registro de Tareas Resueltas con Asistencia de IA

Este documento recopila de manera ordenada las tareas desarrolladas con asistencia de herramientas de Inteligencia Artificial (Antigravity IDE / Gemini / Claude) para los Hitos 1 y 2 del proyecto **Global Exchange**, cumpliendo con los lineamientos de transparencia técnica y buenas prácticas de ingeniería de software.

---

## 📑 Índice de Tareas Desarrolladas

| Ticket Jira | Título de la Tarea | Sprint | Responsable / Rol | Estado |
| :--- | :--- | :---: | :--- | :---: |
| **SCRUM-26** | Vinculación automática de ID Keycloak a Ficha Cliente | Sprint 1 | Pablo Elizeche | Finalizado |
| **SCRUM-27** | Vistas y Endpoints para CRUD de Clientes con Filtros | Sprint 1 | Pablo Elizeche | Finalizado |
| **SCRUM-28** | Plantilla Base y Menú Dinámico según Roles JWT | Sprint 1 | Pablo Elizeche | Finalizado |
| **SCRUM-29** | Interfaces Gráficas para Gestión de Clientes | Sprint 1 | Pablo Elizeche | Finalizado |
| **SCRUM-30** | Pruebas Unitarias para CRUD de Clientes y Autenticación | Sprint 1 | Pablo Elizeche | Finalizado |
| **SCRUM-31** | Configuración de Sphinx y Bitácora IA (docs/chat_ia.md) | Sprint 1 | Felipe Rivas / Pablo Elizeche | Finalizado |
| **SCRUM-41** | Estandarización de Comandos de Tests y Cobertura en README | Sprint 2 | Pablo Elizeche | Finalizado |
| **SCRUM-42** | Actualización de Documentos de Diseño UML y Casos de Prueba | Sprint 2 | Pablo Elizeche | Finalizado |
| **SCRUM-43** | Documentación de Docstrings en Código Fuente y Sphinx | Sprint 2 | Pablo Elizeche | Finalizado |
| **SCRUM-55** | CRUD de Medios de Pago de Clientes (payments) | Sprint 2 | Pablo Elizeche | Finalizado |
| **SCRUM-50** | Modelos de Datos para Monedas, Tasas de Cambio y Comisiones (rates) | Sprint 2 | Pablo Elizeche | Finalizado |
| **SCRUM-56** | Suite de Pruebas Unitarias e Integración para Monedas, Cotizaciones, Comisiones, Medios de Pago, Usuarios y Clientes | Sprint 2 | Equipo de Desarrollo | Finalizado |

---

## 🛠️ Detalle Ordenado por Tarea

---

### 1. SCRUM-26: Lógica de vinculación automática de ID de Keycloak a la ficha de Cliente en Django

* **Objetivo:** Interceptar el inicio de sesión exitoso vía Keycloak OIDC para sincronizar o crear automáticamente la ficha de cliente en Django mediante el identificador único inmutable (`sub`).
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
  * Detección y corrección del desacople de settings en `manage.py`: enrutamiento automático a `config.settings.test` (SQLite in-memory) al invocar `test`, eliminando la necesidad de parámetros largos y evitando conflictos con PostgreSQL.
  * Inclusión formal del paquete `coverage>=7.6.0` en `requirements.txt`.
  * Configuración de exclusiones en `.gitignore` y `.dockerignore` (`.coverage`, `htmlcov/`).
  * Redacción de la sección detallada en `README.md`: guía paso a paso para Docker Compose, comandos para pruebas por módulo/clase/método, auditoría de cobertura por consola y reportes web interactivos en HTML, más instrucciones para entornos locales.
  * Validación integral: 69 tests ejecutados con 100% de éxito y 95% de cobertura global de código.
  * Redacción del documento técnico específico en `docs/documentacion/SCRUM-41_ESTANDARIZACION_TESTS.md`.
* **Archivos intervenidos:**
  * `manage.py`
  * `requirements.txt`
  * `.gitignore`
  * `.dockerignore`
  * `README.md`
  * `docs/documentacion/SCRUM-41_ESTANDARIZACION_TESTS.md`
  * `docs/documentacion/RESOLUCION_TAREAS_IA.md`
  * `docs/chat_ia.md`

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

### 9. SCRUM-43: Documentación de docstrings en código fuente y actualización de Sphinx

* **Objetivo:** Redactar y estandarizar los docstrings estructurados (formato Sphinx/Google style) en las nuevas clases, servicios, context processors y vistas desarrolladas en el Sprint 2, actualizando la bitácora en `docs/chat_ia.md` y compilando el árbol HTML de Sphinx sin advertencias.
* **Aportes y Solución con IA:**
  * Creación de `AuthenticationConfig` con docstrings formales en `authentication/apps.py` e incorporación autodoc para el paquete `authentication`.
  * Normalización de directivas reStructuredText y formato de listas en `customers/services.py` y `customers/urls.py` para prevenir errores de parsing en docutils.
  * Configuración de la extensión `sphinx.ext.viewcode` en `docs/sphinx/source/conf.py` para vincular el código fuente con la documentación generada.
  * Actualización de los archivos `.rst` del árbol de Sphinx (`authentication.rst`, `authentication.templatetags.rst`, `customers.rst`, `modules.rst`, `index.rst`).
  * Validación de compilación limpia de la documentación HTML y actualización de la bitácora IA.
* **Archivos intervenidos:**
  * `authentication/__init__.py`
  * `authentication/apps.py`
  * `authentication/urls.py`
  * `customers/__init__.py`
  * `customers/services.py`
  * `customers/urls.py`
  * `docs/sphinx/source/conf.py`
  * `docs/sphinx/source/index.rst`
  * `docs/sphinx/source/modules.rst`
  * `docs/sphinx/source/authentication.rst`
  * `docs/sphinx/source/authentication.templatetags.rst`
  * `docs/sphinx/source/customers.rst`
  * `docs/chat_ia.md`
  * `docs/documentacion/RESOLUCION_TAREAS_IA.md`

---

### 10. SCRUM-55: Modelo, vistas y formularios para el CRUD de Medios de Pago de Clientes (payments)

* **Objetivo:** Construir la aplicación Django `payments` con el modelo `PaymentMethod`, vistas CBV web protegidas contra IDOR, endpoints API REST (JSON), formularios validados y plantillas dark-mode responsivas para la gestión segura de cuentas bancarias y billeteras de los clientes.
* **Aportes y Solución con IA:**
  * Definición del modelo `PaymentMethod` con clave foránea a `Cliente`, selector de `TipoMedio` (`TRANSFERENCIA`, `BILLETERA`, `TARJETA`, `EFECTIVO`, `OTRO`), datos de entidad bancaria, número de cuenta o teléfono, titular y banderas de predeterminado y activo.
  * Implementación de la exclusividad atómica en `PaymentMethod.save()` para asegurar un único medio de pago predeterminado por cliente sin afectar a otros clientes.
  * Arquitectura de seguridad con resolución de cliente activo (`get_current_cliente`) y filtrado estricto en `get_queryset()` para prevenir vulnerabilidades de Insecure Direct Object References (IDOR), respondiendo `HTTP 404` ante intentos de acceso o manipulación cruzada.
  * Desarrollo de CBVs (`PaymentMethodListView`, `PaymentMethodCreateView`, `PaymentMethodUpdateView`, `PaymentMethodDeleteView`, `PaymentMethodSetDefaultView`, `PaymentMethodToggleActiveView`) y endpoints REST (`PaymentMethodListCreateAPIView`, `PaymentMethodDetailAPIView`).
  * Diseño de interfaces con KPIs en tarjetas, filtros de búsqueda, selector de predeterminado y estados vacíos (*empty states*).
  * Elaboración de 21 tests automatizados que elevan la suite completa a 96 tests aprobados y alta cobertura.
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

---

### 11. SCRUM-50: Modelos de Datos para Monedas, Tasas de Cambio y Comisiones (rates)

* **Objetivo:** Crear la aplicación Django `rates` y definir las entidades del motor financiero transaccional: catálogo de divisas (`Currency`), cotizaciones con cálculo automático de spread (`ExchangeRate`) y reglas tarifarias/bonificaciones por segmento de cliente (`SegmentCommission`), con administración Django y pruebas unitarias con cobertura del 100%.
* **Aportes y Solución con IA:**
  * Creación y registro de la aplicación `rates` en `config/settings/base.py`.
  * Definición del modelo `Currency` con validación estricta de códigos ISO 4217 de 3 caracteres alfabéticos, normalización en mayúsculas, símbolo y precisión decimal.
  * Definición del modelo `ExchangeRate` con claves foráneas protegidas (`models.PROTECT`), validaciones financieras de consistencia (`sell_rate >= buy_rate`, tasas positivas, pares distintos, coherencia de vigencia) y cálculo automático de `spread = sell_rate - buy_rate` al persistir.
  * Definición del modelo `SegmentCommission` vinculado a las opciones de `Cliente.Segmentacion` con campos de porcentaje (0 a 100%), cargo fijo, descuento sobre el spread y métodos auxiliares `calculate_commission()` y `apply_spread_discount()`.
  * Configuración del panel de administración Django (`rates/admin.py`) con filtros, búsquedas, jerarquía de fechas y asignación automática de usuario operador en `save_model()`.
  * Desarrollo de 21 pruebas unitarias completas en `rates/tests.py`, elevando la suite general del proyecto a 117 tests con 100% de éxito y 100% de cobertura en el nuevo módulo.
* **Archivos intervenidos:**
  * `rates/__init__.py`
  * `rates/apps.py`
  * `rates/models.py`
  * `rates/admin.py`
  * `rates/tests.py`
  * `rates/migrations/0001_initial.py`
  * `config/settings/base.py`
  * `docs/documentacion/SCRUM-50_MODELOS_RATES.md`
  * `docs/documentacion/RESOLUCION_TAREAS_IA.md`
  * `docs/documentacion/Jira workflow/TAREAS.md`
  * `docs/chat_ia.md`

---

### 12. SCRUM-53: Parametrización de Comisiones por Segmento y Motor de Cálculo de Tasas Netas

* **Objetivo:** Desarrollar la lógica de negocio, motor financiero transaccional, vistas administrativas CBVs, simulador de cotizaciones y endpoints API REST JSON para configurar las reglas de comisión por segmento de cliente (Minorista, Mayorista, Corporativo, VIP) e integrar el calculador de tasas netas aplicables según el cliente activo.
* **Aportes y Solución con IA:**
  * Implementación de `RateCalculationService` en `rates/services.py` para resolución dinámica de cliente activo, obtención de reglas tarifarias por segmento y liquidación matemática de cotizaciones (bonificación sobre el spread, comisiones porcentuales y fijas, importes brutos y netos finales).
  * Desarrollo de formularios `SegmentCommissionForm`, `SegmentCommissionFilterForm` y `RateCalculatorForm` con validaciones de límites en `rates/forms.py`.
  * Creación de controladores CBVs para CRUD de comisiones (`SegmentCommissionListView`, `CreateView`, `UpdateView`, `DeleteView`, `DetailView`) y cotizador interactivo (`RateCalculatorView`) en `rates/views.py`.
  * Implementación de endpoints API REST JSON: `CalculateNetRateApiView` (`/rates/api/calculate/`), `SegmentCommissionListApiView` y `SegmentCommissionDetailApiView`.
  * Diseño de plantillas HTML responsivas con estética corporativa y alertas contextuales en `templates/rates/` y actualización del menú en `templates/base.html`.
  * Creación de 71 pruebas unitarias en `rates/tests.py` alcanzando un **97% de cobertura de código** en `rates` y elevando la suite general del proyecto a **167 tests exitosos (100% OK)**.
* **Archivos intervenidos:**
  * `rates/services.py`
  * `rates/forms.py`
  * `rates/views.py`
  * `rates/urls.py`
  * `rates/models.py`
  * `rates/tests.py`
  * `config/urls.py`
  * `templates/rates/commission_list.html`
  * `templates/rates/commission_form.html`
  * `templates/rates/commission_detail.html`
  * `templates/rates/commission_confirm_delete.html`
  * `templates/rates/rate_calculator.html`
  * `templates/base.html`
  * `docs/documentacion/Proyecto/SCRUM-53.md`
  * `docs/documentacion/RESOLUCION_TAREAS_IA.md`
  * `docs/documentacion/Jira workflow/TAREAS.md`
  * `docs/chat_ia.md`

---

### 13. SCRUM-56: Suite de Pruebas Unitarias e Integración para los módulos de negocio

* **Objetivo:** Consolidar la validación automatizada de los módulos de monedas, cotizaciones, comisiones, medios de pago, clientes y autenticación de usuarios mediante pruebas unitarias e integración con Django `TestCase`.
* **Aportes y Solución con IA:**
  * Verificación de creación, normalización y validación de monedas; cálculo automático de spread; y reglas de comisión segmentadas, incluyendo descuentos sobre el spread.
  * Cobertura de los flujos CRUD web y API de clientes y medios de pago, con validación de aislamiento por cliente y de medio predeterminado.
  * Pruebas de autenticación, vinculación de usuarios OIDC/Keycloak y cierre de sesión, comprobando la invalidación de la sesión local y la redirección SSO.
  * Se corrigió la selección de cotizaciones para que el cotizador descarte tasas expiradas y tasas cuya vigencia aún no inició. Las pruebas de integración verifican que el endpoint de cálculo responda `404` si no hay una cotización vigente.
  * Ejecución integral de la suite: **182 pruebas aprobadas**.
* **Archivos intervenidos:**
  * `rates/services.py`
  * `rates/tests.py`
  * `authentication/tests.py`
  * `docs/documentacion/RESOLUCION_TAREAS_IA.md`

