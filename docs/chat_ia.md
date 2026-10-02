# Bitácora de conversaciones con IA — Global Exchange

Este documento registra las consultas realizadas a asistentes de IA durante
el desarrollo del proyecto, según lo requerido por el punto CHIA de la
consigna. Cada integrante agrega su propia entrada al usar una IA.

---

## Felipe Rivas — 30/08/2026 — Claude

**Contexto:** Sprint 1 — Setup del entorno de desarrollo (SCRUM-25, SCRUM-31)

**Resumen:**
- Debugging del entorno Docker: conflicto de puerto 5432 entre Postgres
  dockerizado y dos instancias nativas de Postgres en Windows (postgresql-x64-17
  y postgresql-x64-18) que impedían la conexión de Django a la base de datos.
- Corrección de line endings (CRLF → LF) en `docker/postgres/init-databases.sh`,
  que rompía la inicialización de Postgres al clonar el repo en Windows.
  Se agregó `.gitattributes` para prevenir el problema a futuro en todo el equipo.
- Diseño e implementación del modelo `Cliente` (SCRUM-25) en la app `customers`,
  con `TextChoices` para la segmentación (Minorista, Mayorista, Corporativo, VIP),
  verificado con pruebas manuales en el shell de Django.
- Configuración de Sphinx para documentación automática de código (SCRUM-31):
  instalación, `sphinx-quickstart`, `sphinx-apidoc` sobre la app `customers`,
  y build de HTML navegable a partir de docstrings.
- Definición del flujo de trabajo del equipo con Git Flow (ramas, tags de
  release) y planificación general del Sprint 1 según los puntos de
  evaluación de la cátedra (IDE, SCC, PUN, PDO, AMB, PLA, QA, CHIA).

---

## Pablo Elizeche — 31/08/2026 — Antigravity / Gemini

**Contexto:** Sprint 1 — Vinculación automática de identidades Keycloak con Clientes Django (SCRUM-26) y diagnóstico de entorno local

**Resumen:**
- Diagnóstico y resolución de conflicto de conexión con PostgreSQL en Windows: consulta sobre el comportamiento del mapeo de puertos en Docker Compose al colisionar con el servicio local `postgresql-x64-17` en el puerto 5432, implementando la solución de mapeo al puerto 5433 en `.env`.
- Consulta sobre patrones de diseño en Django para intercepción desacoplada de eventos de autenticación: análisis comparativo entre Middleware vs. Signals (`user_logged_in` y señales personalizadas de aplicación).
- Revisión de la estructura de claims OIDC en `mozilla-django-oidc`: validación de la extracción del claim inmutable `sub` (subject UUID) y claims de perfil (`email`, `given_name`, `family_name`).
- Asistencia en la elaboración de la suite de pruebas unitarias para cubrir casos borde en la vinculación de clientes: sincronización por `sub`, vinculación por `correo` para registros preexistentes, creación automática y tolerancia a fallos.

---

## Pablo Elizeche — 31/08/2026 — Antigravity IDE (Google DeepMind)

**Contexto:** Sprint 1 — Construcción de interfaces gráficas para clientes (SCRUM-29)

**Resumen:**
- Analicé los requisitos de UX del módulo `customers` y definí la arquitectura
  visual: sistema de badges por segmento, avatares con iniciales, paleta de colores
  por tipo de cliente (Minorista, Mayorista, Corporativo, VIP) y layout responsivo.
- Diseñé e implementé el listado interactivo (`cliente_list.html`): tarjetas KPI
  de estadísticas, pestañas de filtrado rápido por segmento, tabla con acciones
  por fila y estado vacío amigable. Usé el asistente de IA para validar opciones
  de estructura CSS y obtener sugerencias de componentes, que luego adapté al
  sistema de diseño del proyecto.
- Implementé el formulario de alta/edición (`cliente_form.html`) dividido en
  secciones, con selector visual de segmentación por tarjetas tipo card y toggle
  de estado. La integración con el `<select>` de Django y la validación visual
  por campo la resolví yo; la IA fue consultada puntualmente para ideas de
  presentación del toggle switch y manejo de errores.
- Rediseñé la ficha de detalle (`cliente_detail.html`) y la pantalla de
  confirmación de eliminación (`cliente_confirm_delete.html`). El diseño de la
  animación de alerta y la jerarquía visual fueron decisiones propias; recurrí
  a la IA para generar variantes de estilos CSS que luego seleccioné y ajusté.
- Verifiqué la integridad de todo el módulo con la suite de pruebas automatizadas
  (`manage.py test`) antes de publicar los cambios.

---

## Pablo Elizeche — 31/08/2026 — Antigravity / Claude & Gemini

**Contexto:** Sprint 1 — Redacción e integración de Pruebas Unitarias (PyUnit) para el CRUD de Clientes y autenticación (SCRUM-30)

**Resumen:**
- Planifiqué y diseñé la estrategia de pruebas unitarias y de integración para alcanzar cobertura completa sobre el ciclo de vida del modelo `Cliente`, reglas de validación de campos, formularios Django y control de acceso basado en roles (RBAC).
- Redacté las suites de prueba `ClienteModelValidationTests`, `ClienteSegmentacionContextTests` y `ClienteFormValidationTests` en `customers/tests.py`, verificando validaciones estrictas de formato, unicidad, límites de caracteres y preservación de estados de filtro. Usé la IA para contrastar casos límite y asegurar que no quedaran reglas de validación sin cubrir.
- Implementé las suites `AuthLoginRedirectTests` y `AuthRoleInheritanceTests` en `authentication/tests.py` para asegurar que las rutas protegidas redirijan correctamente hacia OIDC y que los privilegios de navegación y administración se hereden y apliquen de forma estricta según el rol asignado.
- Ejecuté y depuré las pruebas unitarias automáticas con el runner de pruebas de Django (`manage.py test --settings=config.settings.test`), resolviendo aserciones y asegurando un 100% de aprobación antes de publicar los cambios.

---

## Pablo Elizeche — 08/09/2026 — Antigravity / Gemini

**Contexto:** Sprint 2 — Estandarización de comandos de ejecución de tests y verificación en README.md (SCRUM-41)

**Resumen:**
- Diagnostiqué la discrepancia entre la ejecución de pruebas por defecto en `manage.py` (que intentaba apuntar a PostgreSQL en dev) y el módulo optimizado in-memory `config.settings.test`, implementando en `manage.py` la detección y enrutamiento inteligente para invocaciones del subcomando `test`.
- Incorporé la dependencia formal `coverage>=7.6.0` en `requirements.txt` y configuré las directivas de exclusión de artefactos generados en `.gitignore` y `.dockerignore` (`.coverage`, `htmlcov/`).
- Documenté en `README.md` la guía estandarizada y detallada para pruebas unitarias con Docker Compose (`docker compose exec web python manage.py test`) y mediciones de cobertura de código (`coverage run`, `coverage report -m`, `coverage html`), incluyendo tanto la ejecución dockerizada como la local vía `venv`.
- Ejecuté y validé la totalidad de pruebas de los módulos `authentication` y `customers` (69 pruebas con 100% de aprobación y 95% de cobertura global).
- Estructuré la documentación formal de tareas resueltas con IA en `docs/documentacion/` (`SCRUM-41_ESTANDARIZACION_TESTS.md` y `RESOLUCION_TAREAS_IA.md`).

---

## Pablo Elizeche — 08/09/2026 — Antigravity / Gemini

**Contexto:** Sprint 2 — Actualización de los documentos de diseño UML y especificación de pruebas (SCRUM-42)

**Resumen:**
- Analicé las especificaciones del Sprint 2 y procedí a actualizar integralmente los documentos formales de diseño:
  - `EQUIPO_88_B_DIS_CLA_01`: Detallé la entidad `CustomerUserAssignment` (atributos, restricciones `unique_together`, asignación de representante principal y métodos de ciclo de vida), las clases para la gestión de cliente activo (`ActiveCustomerMiddleware`, context processor, `CustomerSwitchActiveView`) y la vista del visualizador Sphinx (`ServeSphinxDocsView`).
  - `EQUIPO_88_B_DIS_PAQ_01`: Refactoricé la arquitectura de paquetes en `apps.customers`, agregué el flujo de cliente activo, integré el visualizador de documentación en `global_exchange_core`, generé el diagrama Mermaid de capas y sincronicé la matriz de responsabilidades.
  - `EQUIPO_88_B_DIS_CPR_01`: Diseñé e incorporé la Matriz Formal de Casos de Prueba con 18 casos de prueba estructurados (CPR-CUA-001..006, CPR-ACT-001..006, CPR-DOC-001..006).
  - `EQUIPO_08_A_ERS_01`: Actualicé los requerimientos funcionales RF04/RF05, RF-21, incorporé RF-27 (Visualizador Sphinx) y registré la versión ERS v3.1 en el historial de cambios.
- Elaboré los documentos de registro `SCRUM-42_DISENO_UML_Y_CASOS_DE_PRUEBA.md` y `RESOLUCION_TAREAS_IA.md` en `docs/documentacion/` para mantener la trazabilidad ordenada exigida por el equipo.

---

## Pablo Elizeche — 08/09/2026 — Antigravity / Gemini & Claude

**Contexto:** Sprint 2 — Modelo, vistas y formularios para el CRUD de Medios de Pago de Clientes (SCRUM-55)

**Resumen:**
- Diseñé y creé la aplicación Django `payments` con el modelo `PaymentMethod` incorporando los campos requeridos: `cliente`, `tipo_medio`, `entidad_bancaria`, `numero_cuenta`, `titular`, `documento_titular`, `es_predeterminado` y `activo`.
- Diseñé la lógica de negocio de exclusividad para medios predeterminados en `PaymentMethod.save()`, garantizando que únicamente un instrumento por cliente posea la bandera `es_predeterminado=True` de manera atómica, sin interferir con otros clientes.
- Implementé la arquitectura de seguridad y mitigación de vulnerabilidades IDOR (Insecure Direct Object Reference) en las vistas CBV (`PaymentMethodListView`, `PaymentMethodCreateView`, `PaymentMethodUpdateView`, `PaymentMethodDeleteView`, `PaymentMethodSetDefaultView`, `PaymentMethodToggleActiveView`), restringiendo estrictamente las consultas `get_queryset()` al cliente resuelto en sesión/usuario autenticado (`get_current_cliente`).
- Construí los formularios validados `PaymentMethodForm` y `PaymentMethodFilterForm` con clases y directivas del sistema de diseño dark-mode.
- Diseñé las interfaces web (`paymentmethod_list.html`, `paymentmethod_form.html`, `paymentmethod_confirm_delete.html`) con KPIs interactivos, distintivos de estado y acciones rápidas.
- Expuse los endpoints de API REST JSON (`PaymentMethodListCreateAPIView`, `PaymentMethodDetailAPIView`) para integración externa.
- Redacté y ejecuté una suite exhaustiva de 21 pruebas automatizadas en `payments/tests.py`, alcanzando 90 tests aprobados a nivel global y 93% de cobertura.
- Redacté la documentación técnica en `docs/documentacion/SCRUM-55_CRUD_MEDIOS_DE_PAGO.md` y actualicé la bitácora consolidada `RESOLUCION_TAREAS_IA.md`.

---

## Pablo Elizeche — 09/09/2026 — Antigravity / Gemini & Claude

**Contexto:** Sprint 2 — Documentación de docstrings en código fuente y actualización de Sphinx (SCRUM-43)

**Resumen:**
- Realicé una auditoría exhaustiva de docstrings en todo el código fuente del backend (`authentication`, `customers`, `config`), estandarizando el formato Sphinx/Google Style para garantizar una documentación técnica de primer nivel.
- Creación de la configuración de aplicación `AuthenticationConfig` en `authentication/apps.py` e incorporación completa de la documentación del paquete `authentication` al índice maestro de Sphinx (`docs/sphinx/source/authentication.rst` y `authentication.templatetags.rst`).
- Actualización de la estructura de documentación en `docs/sphinx/source/customers.rst`, `modules.rst` e `index.rst`, vinculando todos los submódulos (`admin`, `apps`, `forms`, `models`, `services`, `signals`, `tests`, `urls`, `views`).
- Integración de extensiones Sphinx (`sphinx.ext.viewcode`, `sphinx.ext.napoleon`, `sphinx.ext.autodoc`), corrección de directivas rst de docstrings (formato de roles e indentaciones) y resolución de advertencias de compilación para lograr una salida limpia (0 errores, 0 advertencias).
- Recompilación exitosa del árbol completo de documentación HTML en `docs/sphinx/build/html/` y verificación de consistencia mediante la ejecución de la suite de pruebas automatizadas del proyecto.

---

## Pablo Elizeche — 10/09/2026 — Antigravity / Gemini & Claude

**Contexto:** Sprint 2 — Definición de modelos de datos para Monedas, Tasas de Cambio y Comisiones (SCRUM-50)

**Resumen:**
- Diseñé y creé la aplicación Django `rates` integrándola formalmente en `INSTALLED_APPS` (`config/settings/base.py`).
- Implementé el modelo de catálogo de divisas `Currency` con validación estricta de códigos ISO 4217 de 3 letras alfabéticas mayúsculas, símbolo, decimales y control de activación.
- Desarrollé el modelo de cotizaciones `ExchangeRate` con relaciones `models.PROTECT` para proteger la integridad referencial, validaciones de negocio (`sell_rate >= buy_rate`, tasas positivas, pares distintos, coherencia de vigencia), propiedad dinámica `is_current` y cálculo automático del margen cambiario (`spread = sell_rate - buy_rate`) al persistir.
- Definí el modelo `SegmentCommission` parametrizado con las opciones de segmentación del cliente (`Cliente.Segmentacion`), con porcentajes de comisión, cargos fijos y bonificaciones sobre el spread, e implementé los métodos de cálculo financiero `calculate_commission(amount)` y `apply_spread_discount(original_spread)`.
- Configuré el panel de administración de Django (`rates/admin.py`) con interfaces avanzadas de búsqueda, filtros por fechas y asignación del usuario autenticado en `save_model()`.
- Escribí una suite completa de 21 pruebas unitarias en `rates/tests.py`, elevando la suite general del proyecto a 117 tests con 100% de éxito y logrando una cobertura del 100% en el módulo `rates`.
- Generé la migración inicial de base de datos (`rates/migrations/0001_initial.py`) y redacté la especificación técnica en `docs/documentacion/SCRUM-50_MODELOS_RATES.md`.

---

## Pablo Elizeche — 10/09/2026 — Antigravity / Gemini & Claude

**Contexto:** Sprint 2 — Módulo de parametrización de comisiones por segmento y motor de cálculo de tasas netas (SCRUM-53)

**Resumen:**
- Implementé el motor de cálculo financiero `RateCalculationService` en `rates/services.py`, encargado de computar tasas netas para compra y venta de divisas, aplicar bonificaciones porcentuales sobre el spread comercial, calcular comisiones administrativas (porcentuales y fijas) y liquidar montos netos a pagar o recibir.
- Diseñé la función de resolución de cliente activo `get_active_customer(request)` para integrar fluidamente el middleware de sesión de clientes con los servicios transaccionales.
- Desarrollé los formularios de parametrización y simulación (`SegmentCommissionForm`, `SegmentCommissionFilterForm`, `RateCalculatorForm`) en `rates/forms.py` con validaciones de límites de porcentaje y cargos no negativos.
- Construí el conjunto completo de controladores web CBVs en `rates/views.py` para el CRUD administrativo de comisiones (`SegmentCommissionListView`, `CreateView`, `UpdateView`, `DeleteView`, `DetailView`) y el cotizador interactivo (`RateCalculatorView`).
- Creé endpoints de API REST JSON (`CalculateNetRateApiView`, `SegmentCommissionListApiView`, `SegmentCommissionDetailApiView`) para cotizaciones programáticas en tiempo real vía AJAX/API.
- Diseñé las plantillas HTML con estética corporativa y alertas contextuales en `templates/rates/` y actualicé la barra de navegación en `templates/base.html`.
- Amplié la suite de pruebas automatizadas en `rates/tests.py` con 71 pruebas unitarias y de integración, alcanzando un **97% de cobertura de código** en `rates` y un total de **167 tests exitosos en todo el proyecto**.
- Redacté el walkthrough técnico completo en `docs/documentacion/Proyecto/SCRUM-53.md`.

---

## Mauricio González & Pablo Elizeche — 24/09/2026 — Antigravity IDE (Gemini & Claude)

**Contexto:** Sprint 3 (Hito 5) — Orquestación Transaccional, Medios de Pago/Cobro, Límites Operativos, Seeding Idempotente, Suites de Pruebas Unitarias e Integración, y Documentación Formal UML/Sphinx (SCRUM-70 al SCRUM-86).

**Resumen:**
- **Filtros de Divisas (SCRUM-70):** Implementé la biblioteca `rates.templatetags.currency_filters` con formateadores `currency_format`, `exchange_rate_format` y `percentage_format`, aplicando separación de miles con puntos y decimales con comas según la precisión de cada moneda (PYG sin decimales, USD/EUR con 2 decimales).
- **Entidades y Formularios de Pago (SCRUM-71, 72, 73, 74):** Creé el catálogo parametrizado `EntidadFinanciera` y extendí `PaymentMethod` con formularios especializados (`CreditDebitCardForm`, `BankTransferForm`, `DigitalWalletForm`, `CashBranchForm`) con validación de Luhn, vencimiento futuro, teléfonos móviles y cuentas bancarias, integrando selección dinámica en plantillas.
- **Medios de Acreditación (SCRUM-76):** Desarrollé la entidad `ReceivingMethod` para registrar cuentas y destinos donde el cliente recibe fondos convertidos, incorporando gestión de predeterminado atómico, borrado lógico y protección estricta anti-IDOR.
- **Límites Operativos (SCRUM-77):** Definí el modelo `OperationLimit` (mínimo, máximo, límite diario y mensual) y el servicio `OperationLimitValidationService` para control y bloqueo preventivo de operaciones fuera de topes parametrizados por segmento y moneda.
- **Seeding Automatizado e Idempotente (SCRUM-75):** Diseñé el comando administrativo `python manage.py seed_data` en `apps.customers`, poblando la base de datos con usuarios de prueba, asignaciones de representación multi-usuario, catálogo de divisas, historial de tasas de 30 días, reglas de comisiones, bancos, billeteras, medios de cobro, límites operativos y transacciones de muestra sin generar duplicados en ejecuciones sucesivas.
- **Módulo Transaccional Cambiario (SCRUM-78, 79, 81):** Desarrollé la aplicación `apps.transactions` con el modelo `Transaction`, el orquestador atómico `TransactionService`, vistas CBVs (`TransactionListView`, `CreateView`, `ConfirmView`, `DetailView`) y endpoints REST JSON para órdenes de compra y venta imputadas al cliente activo.
- **Cotización Congelada y Cancelación (SCRUM-80):** Implementé `QuoteFreezeService` con ventana estricta de 5 minutos (`quote_expires_at`), detección reactiva de expiración (`check_and_expire_transaction`) que transiciona a `EXPIRADA`, anulación voluntaria por el cliente (`TransactionCancelView`) y cuenta regresiva sincronizada en JavaScript.
- **Comprobante de Liquidación (SCRUM-82):** Construí la vista y plantilla `TransactionReceiptView` (`receipt.html`) con diseño formal imprimible y exportable conteniendo todos los desgloses de cambio, comisiones, cuentas de origen/destino y sellos de tiempo.
- **Suites de Pruebas Unitarias e Integración (SCRUM-83, 84):** Desarrollé 71 pruebas automatizadas para pagos y límites en `payments/tests.py` y `rates/tests.py`, y 51 pruebas integrales para transacciones en `transactions/tests.py`, alcanzando un total de **289 pruebas exitosas con 100% de aprobación (OK)** en todo el proyecto.
- **Documentación de Diseño y Casos de Prueba (SCRUM-85):** Actualicé los artefactos formales del proyecto: ERS v3.3 (`EQUIPO_08_A_ERS.md` con RF-32 a RF-38 y RN-19 a RN-26), Diagrama de Clases UML (`DIS_CLA_01`), Diagrama de Paquetes UML (`DIS_PAQ_01`) y Matriz de Casos de Prueba (`DIS_CPR_01` con Módulos 8 a 15, CPR-ENT a CPR-SED).
- **Docstrings Sphinx y Cierre de Release (SCRUM-86):** Estandaricé los docstrings Sphinx/Google style en todos los módulos de Sprint 3, incorporé el paquete `transactions` al árbol de documentación en `docs/sphinx/source/transactions.rst` y `modules.rst`, recompilé el sitio HTML en `docs/sphinx/build/html/` con 0 errores y 0 advertencias, y registré la bitácora para el etiquetado del release Hito 5.


