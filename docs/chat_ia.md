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

---

## Mauricio González — 08/10/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 4 — Modelado de pasarela y servicio de webhook de Stripe en `payments/` (SCRUM-92)

**Resumen:**
- Diseñé e implementé las entidades `PaymentGatewayRecord` y `PaymentWebhookEvent` en `payments/models.py` para almacenar intentos de pago, Checkout Sessions, PaymentIntents y registro inmutable de webhooks garantizando idempotencia.
- Desarrollé el servicio de pasarela `StripeService` en `payments/services.py` con soporte para:
  - Creación de sesiones de Stripe Checkout (`create_checkout_session`) con cálculo y normalización de montos para divisas tradicionales (centavos) y divisas de cero decimales (PYG).
  - Creación directa de PaymentIntents (`create_payment_intent`).
  - Validación criptográfica de firmas HMAC-SHA256 (`verify_webhook_signature`) con manejo riguroso de excepciones `SignatureVerificationError`.
  - Procesamiento transaccional e idempotente de eventos de webhook (`process_webhook_event`), reconociendo `checkout.session.completed`, `payment_intent.succeeded`, `payment_intent.payment_failed` y `checkout.session.expired`.
- Expuse el endpoint HTTP `@csrf_exempt` `stripe_webhook` en `payments/views.py` y `payments/urls.py` (`/payments/webhook/stripe/`), junto con la vista `StripeCreateCheckoutSessionView` (`/payments/stripe/checkout/<int:transaction_id>/`).
- Registré las entidades en el panel administrativo de Django (`payments/admin.py`) y configuré las variables de entorno en `config/settings/base.py` y `.env.example`.
- Generé la migración de base de datos `payments/migrations/0007_paymentwebhookevent_paymentgatewayrecord.py`.
- Incorporé `stripe>=16.0.0` a `requirements.txt` y actualicé `docs/sphinx/source/payments.rst` para indexar `payments.services`.
- Redacté una suite de pruebas automatizadas con 24 tests específicos en `payments/tests.py` que cubren conversiones de moneda, mocks de la API de Stripe, validación de firmas, procesamiento idempotente y llamadas HTTP, elevando la suite del proyecto a **313 tests aprobados con 100% de éxito (OK)**.

---

## Mauricio González — 08/10/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 4 — Servicio de simulación y confirmación bancaria local SIPAP (SCRUM-93 / SCRUM-87)

**Resumen:**
- Diseñé y modelé la entidad `SipapTransferRecord` en `payments/models.py`, capturando transferencias de la red SIPAP (Sistema de Pagos del Paraguay) con código de comprobante interbancario único, cuentas bancarias origen y destino, titularidad, montos, moneda y estados (`PENDIENTE`, `CONFIRMADA`, `RECHAZADA`, `REVERTIDA`).
- Implementé el servicio `SipapService` en `payments/services.py`:
  - `generate_transfer_code`: generador de códigos estándar con formato `SIPAP-YYYYMMDD-XXXXXX`.
  - `simulate_transfer`: simulación y persistencia de transferencias bancarias para entornos operativos y de desarrollo.
  - `validate_transfer`: validación de existencia, integridad de montos, monedas y cuentas de origen.
  - `confirm_deposit`: conciliación y confirmación automática con **idempotencia estricta**, actualizando el registro de pasarela `PaymentGatewayRecord` a `COMPLETADO` y la orden cambiaria a `COMPLETADA` sin duplicar acreditaciones ante reintentos.
  - `reject_transfer`: registro de rechazos bancarios con anulación atómica de órdenes pendientes (`CANCELADA`), cumpliendo con los criterios de aceptación de SCRUM-87.
- Implementé los endpoints HTTP en `payments/views.py` y `payments/urls.py`:
  - `sipap_confirm_deposit` (`/payments/sipap/confirmar/`): endpoint POST `@csrf_exempt` para confirmación y conciliación automática.
  - `sipap_simulate_transfer` (`/payments/sipap/simular/`): endpoint POST `@csrf_exempt` para inyección de comprobantes de prueba.
  - `sipap_query_status` (`/payments/sipap/consultar/<str:codigo>/`): endpoint GET para consulta de estado de transferencias.
  - `sipap_reject_transfer` (`/payments/sipap/rechazar/`): endpoint POST `@csrf_exempt` para registro de rechazos.
- Registré `SipapTransferRecord` en el panel de administración de Django (`payments/admin.py`).
- Generé la migración de base de datos `payments/migrations/0008_sipaptransferrecord.py`.
- Desarrollé una suite de pruebas automatizadas con 17 tests específicos (`SipapServiceTestCase` y `SipapEndpointsTestCase`) en `payments/tests.py`, elevando la suite del proyecto a **330 tests aprobados al 100% de éxito (OK)**.
- Actualicé el estado de la tarea en `docs/documentacion/Jira workflow/TAREAS.md` y documenté la solución en `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md`.

---

## Mauricio González — 08/10/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 4 — Orquestación en TransactionService para transición atómica de pago y liquidación (SCRUM-94 / SCRUM-87)

**Resumen:**
- Extendí el modelo `Transaction` en `transactions/models.py` agregando los campos `fecha_pago` (marca temporal exacta de confirmación), `referencia_externa_pago` (identificador devuelto por Stripe o comprobante SIPAP) y `pasarela_pago` (`STRIPE`, `SIPAP`, `EFECTIVO`), actualizando `mark_as_completed` para persistir atómicamente estos valores junto a las observaciones de auditoría.
- Generé la migración de base de datos `transactions/migrations/0002_transaction_fecha_pago_transaction_pasarela_pago_and_more.py`.
- Actualicé el panel de administración `TransactionAdmin` en `transactions/admin.py` con filtros y visualización de pasarela, fecha de pago y referencias externas.
- Implementé la orquestación centralizada en `TransactionService` (`transactions/services.py`):
  - `process_payment_confirmation`: método atómico maestro con verificación de estado previo (no cancelada ni terminal), control estricto de **idempotencia** (retorna la orden sin duplicar operaciones si ya fue liquidada con la misma referencia), validación matemática del monto de pago frente a `monto_origen`, comprobación de correspondencia de moneda frente a `moneda_origen`, registro de auditoría y actualización coordinada con `PaymentGatewayRecord`.
  - `confirm_stripe_payment`: método helper para liquidación de sesiones y PaymentIntents de Stripe.
  - `confirm_sipap_payment`: método helper para conciliación y acreditación de transferencias bancarias SIPAP.
  - `reject_payment_and_cancel`: método atómico para anular transacciones pendientes (`CANCELADA`) y asentar registros de error ante rechazos en pasarela.
- Conecté `StripeService` y `SipapService` en `payments/services.py` para delegar la transición atómica de las transacciones cambiarias en `TransactionService`.
- Escribí 9 pruebas unitarias exhaustivas en `TransactionPaymentOrchestrationTest` dentro de `transactions/tests.py`, elevando la suite del proyecto a **339 tests aprobados al 100% de éxito (OK)**.
- Actualicé `TAREAS.md`, `RESOLUCION_TAREAS_IA.md` y `chat_ia.md`.

---

## Mauricio González — 08/10/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 4 — Vistas e interfaces de usuario para pago en línea y confirmación bancaria (SCRUM-95 / SCRUM-87)

**Resumen:**
- Diseñé y construí la vista web `TransactionPaymentCheckoutView` en `transactions/views.py`:
  - Implementación con `DetailView` y `LoginRequiredMixin`, incorporando protección anti-IDOR para restringir el acceso exclusivamente al cliente titular o administradores.
  - Comprobaciones exhaustivas de estado: detección de órdenes ya completadas (con redirección al detalle), órdenes canceladas, y auto-cancelación por expiración de cotización congelada (5 minutos).
  - Manejo de métodos `POST` y `AJAX` para confirmación manual de comprobantes SIPAP (`action='confirm_sipap'`) y simulación asistida de transferencias (`action='simulate_sipap'`), invocando a `TransactionService.confirm_sipap_payment`.
- Diseñé y creé la plantilla responsive `templates/transactions/payment_checkout.html` respetando la guía de estilos de Global Exchange:
  - Resumen financiero de la orden: Monto a entregar destacado, tasa congelada, desglose de comisiones, monto neto a recibir y medio de acreditación destino.
  - Temporizador regresivo dinámico en JavaScript que alerta sobre el tiempo restante de cotización congelada.
  - Panel de Stripe Checkout con botón de redirección segura a `payments:stripe-create-checkout` y sellos de seguridad SSL/PCI-DSS.
  - Panel de SIPAP con datos de la cuenta recaudadora institucional (Banco Continental / BCP, RUC, N° de Cuenta, Titular y código de concepto copiable al portapapeles).
  - Modales interactivos para carga manual de comprobante SIPAP y simulación asistida para entornos de prueba.
- Actualicé las rutas en `transactions/urls.py` agregando `payment-checkout` y el alias `payment_checkout`.
- Mejoré `templates/transactions/transaction_detail.html` agregando botón CTA "Pagar Ahora" para órdenes pendientes, banner informativo ante retornos exitosos de Stripe y bloque de visualización de pasarela de pago y referencia externa en órdenes liquidadas.
- Escribí una suite de 13 pruebas unitarias e integración en `TransactionPaymentCheckoutViewTest` (`transactions/tests.py`), alcanzando un total de **352 tests aprobados con 100% de éxito (OK)**.
- Actualicé el estado de la tarea en `TAREAS.md`, `RESOLUCION_TAREAS_IA.md` y `chat_ia.md`.

---

## Mauricio González — 12/10/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 4 — Suite de Pruebas Unitarias automatizadas para Pagos, MFA, Notificaciones y RBAC (SCRUM-104)

**Resumen:**
- Implementé y consolidé la suite integral de pruebas unitarias automatizadas con PyUnit cubriendo los módulos requeridos (`apps/payments/tests/`, `apps/transactions/tests/`, `apps/rates/tests/`, `apps/authentication/tests/`).
- **Módulo de Pagos (`payments/tests.py`):**
  - Mocks exhaustivos de webhooks de Stripe (`checkout.session.completed`), validación de firmas criptográficas inválidas con retorno HTTP 400 y pruebas de idempotencia con el modelo `PaymentWebhookEvent`.
  - Pruebas del servicio bancario `SipapService` simulando transferencias, confirmación de depósitos y rechazos controlados.
  - Pruebas de persistencia y ciclo de vida de `PaymentGatewayRecord`.
- **Módulo de Cotizaciones y Notificaciones (`rates/tests.py`):**
  - Pruebas para la señal `post_save` de `ExchangeRate` evaluando alertas `ExchangeAlert` (condiciones de umbral mayor o menor).
  - Verificación del despacho de notificaciones a través de `NotificationService`.
- **Módulo de Autenticación y RBAC (`authentication/tests.py`):**
  - Verificación de políticas RBAC con validación de código HTTP 403 o redirección para usuarios con roles no autorizados en vistas administrativas.
  - Validación de redirección segura a `/oidc/authenticate/` para usuarios anónimos en transacciones y medios de pago.
- **Módulo de Transacciones (`transactions/tests.py`):**
  - Pruebas de mitigación IDOR en vistas de detalle, cancelación y comprobante formal de liquidación cambiaria (`TransactionReceiptView`).
  - Restricción de cancelación sobre transacciones ya completadas.
- **Enrutamiento dinámico `apps.*` (`apps/__init__.py`):**
  - Configuración en `sys.modules` para permitir la importación y ejecución de tests con la convención `apps.<app>.tests`.
- **Resultados:** 455 tests totales del proyecto aprobados al 100% de éxito (`OK`), sin regresiones.

---

## Mauricio González — 12/10/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 4 — Actualización de Documentación de Diseño UML y ERS v3.4 (SCRUM-105)

**Resumen:**
- Actualicé integralmente los documentos formales de ingeniería de software para reflejar los desarrollos del Sprint 4:
  - **ERS v3.4 (`docs/documentacion/Proyecto/EQUIPO_08_A_ERS.md`):** Formalización de requerimientos funcionales RF-39 a RF-45 (Stripe Checkout, Webhooks, SIPAP, orquestación en TransactionService, checkout interactivo, MFA TOTP, alertas y RBAC con menú dinámico), requerimientos no funcionales RNF-SEC-05 a 07 (firma criptográfica, idempotencia y menor privilegio) y tabla histórica de cambios v3.4.
  - **Diagrama de Clases UML (`docs/documentacion/Proyecto/EQUIPO_88_B_DIS_CLA_01.md`):** Modelado de `PaymentWebhookEvent`, `PaymentGatewayRecord`, `SipapTransferRecord`, `StripeService`, `SipapService`, `ExchangeAlert`, `NotificationService`, campos extendidos de `Transaction` y diagrama Mermaid consolidado.
  - **Diagrama de Paquetes (`docs/documentacion/Proyecto/EQUIPO_88_B_DIS_PAQ_01.md`):** Actualización de las capas de `payments`, `transactions`, `rates`, `authentication`, interfaces expuestas y matriz de dependencias.
  - **Casos de Prueba (`docs/documentacion/Proyecto/EQUIPO_88_B_DIS_CPR_01.md`):** 31 nuevos casos de prueba estructurados (Módulos 16 a 20: CPR-STR, CPR-SIP, CPR-ALT, CPR-RBC, CPR-ORQ).
  - **Documento de Tarea:** Creación de `docs/documentacion/SCRUM-105.md` y actualización de `RESOLUCION_TAREAS_IA.md`.
- Verifiqué la batería completa de pruebas: 455/455 tests aprobados al 100% de éxito (`OK`), certificando ausencia de regresiones.

---

## Mauricio González — 12/10/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 4 — Generación de docstrings Sphinx, actualización de docs/chat_ia.md y etiquetado Git Tag v4.0.0-sprint4 (SCRUM-106)

**Resumen:**
- Realicé la auditoría y depuración exhaustiva de la documentación técnica y docstrings Sphinx (reStructuredText / PEP 257) en los módulos nuevos y actualizados del Sprint 4:
  - En `authentication/permissions.py`: Corrección de errores de indentación inesperada en listas de directivas y mixins de control de acceso RBAC.
  - En `payments/models.py` y `payments/services.py`: Corrección de advertencias por targets desconocidos encapsulando prefijos de prueba (`cs_test_...`, `pi_...`, `sk_test_...`, `whsec_...`) en formato literal monoespaciado (`` ````).
  - En `transactions/views.py` y `transactions/services.py`: Corrección de espaciados y saltos de línea reglamentarios en bloques de listas numeradas y viñetas.
- Actualicé la arquitectura del árbol Sphinx en `docs/sphinx/`:
  - Creación de la carpeta estática `docs/sphinx/source/_static/` para suprimir advertencias de Alabaster.
  - Incorporación de los submódulos `rates.signals` y `authentication.permissions` en sus respectivos archivos `.rst`.
- Ejecuté la compilación del sitio de documentación Sphinx en modo estricto (`sphinx-build -W -b html`), logrando una compilación totalmente limpia con **0 advertencias y 0 errores** (`build succeeded`), generando los artefactos HTML en `docs/sphinx/build/html/`.
- Verifiqué la suite integral de pruebas automatizadas (`manage.py test`): **455 tests aprobados al 100% de éxito (OK)**, certificando ausencia total de regresiones.
- Redacté el documento de trazabilidad de la tarea en `docs/documentacion/SCRUM-106.md` y actualicé `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md`.
- Generé el Git Tag oficial anotado `v4.0.0-sprint4` para la entrega formal del Hito 6 / Cierre del Sprint 4.


---

## Mauricio González — 01/11/2026 — Antigravity IDE (Gemini)

**Contexto:** Hotfix / Sprint 4 — Terminal táctil /kiosk/ y endpoints para consulta, visualización y descarga de KuDE PDF y XML firmado (SCRUM-121)

**Resumen:**
- Diseñé e implementé la solución técnica integral para responder al requerimiento dual de terminal táctil de autoservicio y facturación electrónica KuDE de la SET/DNIT:
- **Terminal Táctil Kiosco de Autoservicio (`/kiosk/`):**
  - Desarrollé la vista interactiva `KioskHomeView` (`templates/kiosk/kiosk_home.html`) con diseño dark-mode de alta visibilidad, panel táctil de selección de divisas (USD, EUR, etc.), cotizador en tiempo real y teclado numérico virtual.
  - Implementé el temporizador de seguridad de 90 segundos con reinicio dinámico ante toques/teclado, modal preventivo de expiración y retorno automático al estado inicial neutro para protección de datos personales.
  - Expuse endpoints JSON: cotización en tiempo real (`/kiosk/api/quote/`), validación express de clientes por RUC o Cédula (`/kiosk/api/customer/lookup/`), registro rápido en un toque (`/kiosk/api/customer/register/`) y formalización instantánea con emisión de KuDE (`/kiosk/api/transact/`).
- **Facturación Electrónica KuDE (SIFEN / e-Kuatia):**
  - Creé el modelo `ElectronicInvoice` en `transactions/models.py` vinculado a `Transaction` para almacenar CDC de 44 dígitos, timbrado, numeración legal `001-001-XXXXXXX`, XML firmado y datos del código QR.
  - Implementé en `transactions/kude_service.py` el algoritmo oficial Módulo 11 de la DNIT (`compute_mod11_dv`), generación matemática del CDC de 44 dígitos y generación canónica de XML conforme al esquema e-Kuatia con firma XMLDSig.
  - Creé el generador nativo en Python de comprobantes KuDE PDF-1.4 (`transactions/kude_pdf.py`), eliminando dependencias externas de librerías binarias C/C++ y garantizando portabilidad multiplataforma.
  - Implementé las vistas de visualización HTML responsiva (`/transactions/<pk>/kude/`), descarga de PDF binario (`/transactions/<pk>/kude/pdf/`), descarga de XML firmado (`/transactions/<pk>/kude/xml/`) y endpoint de consulta pública (`/kude/<identifier>/`).
  - Integré accesos al KuDE en las plantillas `transaction_detail.html`, `receipt.html` y agregué el acceso al Kiosco en la barra de navegación principal `base.html`.
- **Suite de Pruebas Unitarias e Integración (`transactions/tests_kiosk_kude.py`):**
  - Escribí 20 pruebas automáticas cubriendo el algoritmo Módulo 11, estructura del CDC, generación de XML/QR/PDF, ciclo de vida del modelo `ElectronicInvoice`, endpoints de descarga, API pública y todas las funcionalidades de la terminal táctil Kiosco.
- **Verificación de Calidad:**
  - Ejecución de la suite completa de tests del proyecto: **475 tests aprobados al 100% de éxito (OK)**, 0 fallos, 0 errores, sin regresiones.
  - Compilación limpia de documentación Sphinx con `-W` (0 advertencias, `build succeeded`).
  - Redacción del reporte detallado en `docs/documentacion/SCRUM-121.md` y actualización del catálogo general en `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md`.

---

## Mauricio González — 01/11/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 4 / Kiosco — Protocolo de cuota y cliente real FacturaSeguraClient con reserva blindada de 10 pruebas / KioskCashService (SCRUM-122)

**Resumen:**
- Implementé de manera integral el subsistema de gestión física de efectivo en terminales de autoservicio y la integración certificada con el PAC FacturaSegura:
- **Protocolo de Cuota y Cliente Real `FacturaSeguraClient` (`transactions/facturasegura_client.py`):**
  - Creé el modelo `FacturaSeguraConfig` en `transactions/models.py` para parametrizar el consumo de cuotas, el balance operativo y la reserva blindada inviolable de 10 pruebas (`test_quota_reserved = 10`).
  - Diseñé el protocolo de blindaje: si la cuota comercial ordinaria se agota (`operational_quota_available == 0`), el sistema bloquea cualquier emisión ordinaria con `QuotaShieldExhaustedError`, preservando las 10 consultas restantes exclusivamente para la suite de pruebas automatizadas y QA.
  - Implementé las operaciones `emitir_factura`, `consultar_factura`, `consultar_cuota` y `cancelar_factura`, actualizando el estado del modelo `ElectronicInvoice`.
- **Servicio de Efectivo en Terminales Kiosco `KioskCashService` (`transactions/kiosk_cash_service.py`):**
  - Modelé el hardware de la terminal `KioskTotem`, los casetes de billetes por denominación `KioskCashVault` y el registro de movimientos físicos `KioskCashOperation`.
  - Definí el catálogo oficial de denominaciones permitidas (`DENOMINACIONES_PERMITIDAS`) para PYG, USD, EUR, BRL y ARS, con validación estricta y rechazo de billetes ilícitos o no estándar (`InvalidBillDenominationError`).
  - Desarrollé la aceptación física de billetes con control de capacidad en casetes y registro transaccional atómico (`accept_cash`).
  - Implementé el algoritmo de dispensación óptima (`calculate_dispense_breakdown` y `dispense_cash`) basado en Bounded Coin Change con backtracking, minimizando la cantidad de piezas físicas despachadas y controlando saldo en tótem (`InsufficientTotemBalanceError`, `CannotDispenseExactChangeError`).
  - Construí un generador determinista nativo de códigos QR en formato SVG (`generate_qr_svg`), eliminando librerías binarias externas, y sellos de trazabilidad criptográfica SHA-256.
- **Vistas, Endpoints y Plantillas:**
  - Diseñé la plantilla imprimible de ticket térmico `templates/kiosk/cash_receipt.html` con desglose de billetes, totales, sellos y código QR SVG.
  - Expuse endpoints REST para consulta de inventario (`/kiosk/api/cash/status/`), aceptación (`/kiosk/api/cash/accept/`), dispensación (`/kiosk/api/cash/dispense/`), comprobantes (`/kiosk/api/cash/receipt/<uuid>/`) y estado de cuota (`/kiosk/api/facturasegura/cuota/`).
  - Integré la aceptación, dispensación y emisión certificada en la transacción de autoservicio `/kiosk/api/transact/` y actualicé `templates/kiosk/kiosk_home.html`.
- **Suite de Pruebas Automatizadas (`transactions/tests_kiosk_cash_facturasegura.py`):**
  - Escribí 25 casos de prueba unitarios e integrados cubriendo la validación de billetes, aceptación física, dispensación óptima, casos de saldo insuficiente y cambio imposible, protocolo de cuota, reserva blindada de 10 pruebas, consultas y flujo completo de transacción.
- **Verificación de Calidad:**
  - Suite completa del sistema: **500 tests ejecutados y aprobados al 100% de éxito (OK)**, 0 fallos, 0 errores, sin regresiones.
  - Compilación limpia de documentación Sphinx en modo estricto (`sphinx-build -W -b html`) con 0 advertencias.
  - Redacción del informe formal en `docs/documentacion/SCRUM-122.md` y actualización de `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md`.

---

## Pablo Elizeche — 03/11/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 5 / Cajas — Modelado de datos para Cajas, Turnos y Movimientos de Efectivo en `apps/cash/` (SCRUM-114)

**Resumen:**
- Diseñé e implementé la arquitectura de datos y la capa de servicios de dominio para la gestión presencial de ventanilla en sucursales dentro de la aplicación `apps/cash/`, dando cumplimiento formal a las normativas de la plataforma (RF-22, RF-23, RF-24 y RN05):
  - **Puestos de Atención Física (`CashRegister` / alias `Caja`):**
    - Modelo para administración de ventanillas y terminales físicas con identificador único (`register_code`), asignación de sucursal (`branch_name`), estado operativo (`CLOSED`, `OPEN`, `MAINTENANCE`, `INACTIVE`), cajero activo y saldos iniciales y finales históricos.
    - Regla de validación que bloquea la apertura de cajas dadas de baja o inactivas.
  - **Sesiones y Turnos de Caja (`CashShift` / alias `TurnoCaja`):**
    - Ciclo de vida completo del turno: apertura con dotación de fondo inicial en efectivo por divisa (`initial_balances_json`, RF-22) y vinculación inmutable al `keycloak_user_id` del cajero (RN05).
    - Métodos para cálculo en tiempo real de saldos disponibles (`calculate_current_balance`), determinación de saldos teóricos esperados (`calculate_expected_balances`) y proceso formal de arqueo físico (`close_and_reconcile`, RF-23).
    - Detección matemática de sobrantes o faltantes en el conteo de billetes (`difference_balances_json`), clasificando el cierre como Cuadrado (`RECONCILED`) o Con Discrepancias (`DISCREPANCY`).
  - **Auditoría Inmutable de Movimientos de Efectivo (`CashMovement` / alias `MovimientoEfectivo`):**
    - Registro inmutable de transacciones físicas de efectivo para auditoría forense (RF-24), tipificado en 8 categorías formales (apertura, cobro, entrega, dotación, remesa, ajustes y cierre) y flujos `IN`/`OUT`.
    - Blindaje estricto de inmutabilidad: validación en `clean()`, `save()` y `delete()` impidiendo cualquier alteración o supresión de movimientos registrados.
  - **Capa de Servicios de Dominio (`apps/cash/services.py`):**
    - `CashService`: Orquestación atómica de apertura de turnos (`open_shift`), registro de movimientos con validación de saldo disponible para evitar descubiertos (`InsufficientCashBalanceError`), integración con transacciones cambiarias presenciales (`register_transaction_cash`), conciliación y arqueo (`close_shift`) y resumen consolidado (`get_shift_summary`).
  - **Administración y Documentación:**
    - Panel de administración Django (`apps/cash/admin.py`) con badges por color, filtros y modo estricto de solo lectura para auditoría.
    - Incorporación del módulo en Sphinx (`docs/sphinx/source/cash.rst` y `modules.rst`), logrando compilación limpia (`build succeeded`).
  - **Suite de Pruebas Unitarias e Integración (`apps/cash/tests.py`):**
    - 18 pruebas automáticas cubriendo modelos, unicidad, validaciones, ciclo de vida de turnos, arqueos con/sin descuadre, control de saldo, inmutabilidad y formalización con transacciones cambiarias (100% OK).
  - **Verificación de Calidad:**
    - Suite completa del proyecto: **518 tests aprobados al 100% de éxito (OK)**, 0 fallos, 0 errores, sin regresiones.
    - Generación de informe técnico en `docs/documentacion/SCRUM-114.md` y actualización de `RESOLUCION_TAREAS_IA.md`.



---

## Pablo Elizeche — 03/11/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 5 / Cajas — Vistas y formularios para Apertura, Registro de Efectivo y Cierre con Arqueo de Caja (SCRUM-115)

**Resumen:**
- Desarrollé en `apps/cash/` el subsistema de vistas basadas en clases (CBV), formularios especializados y plantillas visuales responsivas para la interacción de cajeros y supervisores en ventanilla física, asegurando el cumplimiento de RF-22, RF-23, RF-24 y RN05:
  - **Formularios Dinámicos con Validación Estricta (`apps/cash/forms.py`):**
    - `CashShiftOpenForm`: Selección de caja cerrada y habilitada, con generación dinámica de campos para dotación de fondo inicial en cada divisa activa (`initial_<DIVISA>`) y asociación del `keycloak_user_id` del cajero.
    - `CashMovementForm`: Formulario de registro de movimientos manuales (aportes de tesorería, remesas de seguridad y ajustes) con control de saldo disponible previo al impacto contable para evitar descubiertos.
    - `BlindReconciliationForm`: Protocolo de arqueo ciego que no revela los saldos contables del sistema al operador y recoge el conteo físico de billetes y monedas por divisa.
  - **Vistas Basadas en Clases (`apps/cash/views.py`):**
    - Implementación de 9 CBVs protegidas con `LoginRequiredMixin` y `RoleRequiredMixin` (`admin`, `operator`, `cajero`): `CashDashboardView`, `CashShiftOpenView`, `CashMovementCreateView`, `CashShiftCloseView`, `CashShiftDetailView`, `CashShiftReceiptView`, `CashShiftListView`, `CashRegisterListView` y el endpoint JSON `CashShiftStatusApiView`.
    - Presentación de métricas financieras de apertura, movimientos acumulados por sentido de flujo (`IN`/`OUT`) y saldos actuales.
    - Generación y renderizado del acta de arqueo formal con determinación matemática de sobrantes, faltantes o cuadre exacto (`RECONCILED`/`DISCREPANCY`).
  - **Plantillas Web e Integración en Navbar (`templates/cash/` y `templates/base.html`):**
    - 7 plantillas HTML responsivas (`dashboard.html`, `shift_open.html`, `movement_create.html`, `shift_close.html`, `shift_detail.html`, `shift_list.html`, `register_list.html`) diseñadas con la paleta oscura de la plataforma, estados visuales, badges por divisa y sección de firmas para impresión.
    - Incorporación de acceso directo `💵 Cajas` en el navbar superior para operadores y administradores.
  - **Rutas (`apps/cash/urls.py` y `config/urls.py`):**
    - Configuración integral bajo el namespace `cash` con prefijo `/cash/`.
  - **Documentación Técnica Sphinx:**
    - Actualización de `docs/sphinx/source/cash.rst` integrando los módulos `forms`, `views` y `urls`. Compilación de Sphinx limpia (`build succeeded`).
  - **Verificación y Calidad de Software:**
    - Suite de pruebas de `apps.cash` ampliada de 18 a **36 tests unitarios e integrados** (`apps/cash/tests.py`) al 100% de éxito.
    - Suite completa del proyecto: **536 tests aprobados al 100% de éxito (OK)**, 0 fallos, 0 errores, sin regresiones.
    - Generación de informe técnico detallado en `docs/documentacion/SCRUM-115.md` y actualización de `RESOLUCION_TAREAS_IA.md`.

---

## Pablo Elizeche — 05/11/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 5 / Cajas — Configuración de Rol Cajero, permisos RBAC y blindaje de vistas de tesorería (SCRUM-116)

**Resumen:**
- Implementé el blindaje integral de control de acceso basado en roles (RBAC) y aislamiento multi-usuario para el módulo de Cajas y Tesorería en sucursales, en estricto cumplimiento de RN05, RF-22, RF-23 y RF-24:
  - **Integración con Keycloak:**
    - Declaré el rol de realm `cajero` en `keycloak/imports/realm-export.json` y creé la entidad correspondiente en el realm `GlobalExchangeRealm` en ejecución vía `kcadm.sh`.
    - Actualicé `KeycloakOIDCAuthenticationBackend` para mapear los claims `cajero` y `cashier` al grupo nativo de Django `'cajero'`.
  - **Jerarquía RBAC y Mixins de Permisos (`authentication/permissions.py`):**
    - Establecí la jerarquía estricta de privilegios: `Admin` $\ge$ `Operator` $\ge$ `Cajero` $\ge$ `User`.
    - Desarrollé el decorador `@cajero_required` para FBVs y el mixin `CashierRequiredMixin` para CBVs.
    - Desarrollé la función `verify_shift_ownership(user, shift)` y el mixin `ShiftOwnershipRequiredMixin` para validar la titularidad de los turnos de caja.
  - **Contexto Global, Filtros y UI:**
    - Agregué `is_cajero` y `primary_role='Cajero'` en `authentication/context_processors.py`.
    - Añadí filtros de plantilla `has_role:"cajero"` y badge visual `.role-cajero` (`💵 Cajero`) en `auth_tags.py` y `templates/base.html`.
    - Hilité el acceso `💵 Cajas` en la barra superior condicionado a `{% if is_cajero or is_operator or user|has_any_role:"admin,operator,cajero" %}`.
  - **Blindaje de Vistas y Aislamiento de Turnos (`apps/cash/views.py`):**
    - Actualicé `CashBaseMixin` para heredar de `CashierRequiredMixin`.
    - Apliqué aislamiento de turnos en `CashShiftCloseView`, `CashShiftDetailView`, `CashShiftReceiptView` y `CashShiftStatusApiView`, arrojando `PermissionDenied` (HTTP 403) ante intentos no autorizados de acceso a turnos ajenos.
    - Aseguré que `CashShiftListView` filtre por cajero titular para operadores de ventanilla, reservando la visualización global para supervisores y administradores.
  - **Verificación y Pruebas Automatizadas:**
    - Desarrollé 9 pruebas en `authentication/tests.py` (`CajeroRoleAndShiftIsolationTests`) -> 70 tests OK.
    - Desarrollé 9 pruebas en `apps/cash/tests.py` (`CashRBACAndShiftIsolationTests`) -> 45 tests OK.
    - Suite global del proyecto: **554 tests aprobados al 100% de éxito (OK)**, 0 fallos, 0 errores, sin regresiones.
    - Compilación de Sphinx limpia (`build succeeded`).
    - Elaboración del informe técnico en `docs/documentacion/SCRUM-116.md` y registro en `RESOLUCION_TAREAS_IA.md`.

---

### Entrada #25: Incorporación del Módulo de Inventario de Billetes por Denominación en SCRUM-116

**Usuario:** Todo lo del scrum 117, debe entrar como scrum 116, que todavía no se commiteó, cualquier cosa que creaste como rama u otra cosa, distinta al del scrum 116, elimina. Y mete todo lo que hiciste del 117 al 116.

**Resumen:**
- Unifiqué todo el alcance del módulo de inventario de billetes por denominación y control de bóveda central dentro de la rama y tarea `feature/SCRUM-116`:
  - **Eliminación y Limpieza:**
    - Eliminé la rama git `feature/SCRUM-117` retornando al branch activo `feature/SCRUM-116`.
    - Eliminé los archivos temporales y documentos separados de SCRUM-117, unificando especificaciones e historias Gherkin en `docs/documentacion/SCRUM-116.md`.
    - Actualicé todos los docstrings y comentarios en `apps/cash/*.py` para alinearlos a SCRUM-116.
  - **Modelos de Datos y Migración (`apps/cash/inventory_models.py`, `models.py`):**
    - `Vault`: Bóvedas centrales de efectivo por sucursal.
    - `CurrencyDenomination`: Denominaciones oficiales reconocidas por cada divisa activa con restricción `unique_together = ('currency', 'value')`.
    - `BanknoteInventory`: Existencias físicas no negativas en bóveda o caja con validación en `clean()` y propiedad calculada `total_amount`.
    - `InitialFloatConfig`: Reglas configurables de dotación inicial por denominación con soporte de dotación parcial (`allow_partial_fill`).
    - `BanknoteMovement`: Registro forense inmutable de transferencias físicas con protección en `save()` y `delete()`.
    - `ShiftDenominationCount`: Arqueo físico por turno con métodos `calculate_expected()` y `update_reconciliation()`.
    - Nuevos estados en `apps/cash/models.py`: `CashRegisterStatus.PENDING_CONTROL` y `ShiftStatus.PENDING_REVIEW`.
    - Migración aplicada en base de datos: `apps/cash/migrations/0002_vault_alter_cashregister_status_and_more.py`.
  - **Capa de Servicios de Dominio (`apps/cash/inventory_services.py`):**
    - `InventoryService.open_shift_inventory()`: Transferencia atómica bóveda $\to$ caja para divisas con tasa de cambio activa, select_for_update y advertencia de dotación parcial.
    - `InventoryService.register_exchange_operation()`: Actualización de stock de caja en tiempo real y validación previa de existencias (`InsufficientRegisterStockError`).
    - `InventoryService.submit_cashier_count()`: Protocolo de arqueo ciego donde el cajero declara el conteo físico, transicionando a `PENDING_REVIEW` / `PENDING_CONTROL`.
    - `InventoryService.approve_reconciliation()`: Resolución del Administrador con acciones `APPROVE` (transferencia caja $\to$ bóveda y cierre), `REJECT` (reapertura para reconteo) y `APPROVE_WITH_ADJUSTMENT` (con motivo obligatorio y cantidades ajustadas).
    - `InventoryService.get_register_stock_summary()`, `get_vault_stock_summary()` y `vault_deposit()`.
  - **Vistas CBV, Rutas y Plantillas Web (`apps/cash/inventory_views.py`, `inventory_urls.py`, `templates/cash/`):**
    - `VaultDashboardView` y `VaultDepositView` (acceso exclusivo administrador).
    - `ShiftInventoryView` (stock físico del puesto de atención para cajero/operador con `verify_shift_ownership`).
    - `CashierDenominationCountView` (formulario de arqueo ciego por denominación para el cajero titular).
    - `AdminReconciliationListView` y `AdminReconciliationActionView` (revisión y aprobación/ajuste/rechazo de arqueos por el administrador).
    - Plantillas responsivas diseñadas bajo el tema oscuro del proyecto: `vault_dashboard.html`, `vault_deposit.html`, `shift_inventory.html`, `cashier_denomination_count.html`, `admin_reconciliation_list.html` y `admin_reconciliation_detail.html`.
  - **Panel de Administración (`apps/cash/admin.py`):**
    - Registro de `VaultAdmin`, `CurrencyDenominationAdmin`, `BanknoteInventoryAdmin`, `InitialFloatConfigAdmin`, `BanknoteMovementAdmin` y el inline `ShiftDenominationCountInline` en `CashShiftAdmin`.
  - **Pruebas Automatizadas y Calidad:**
    - Creada suite `apps/cash/tests_inventory.py` con 27 pruebas unitarias e integración que verifican modelos, servicios, concurrencia, dotaciones parciales, excepciones de dominio, inmutabilidad y arqueos.
    - Suite completa del proyecto: **581/581 tests OK** (100% éxito, 0 fallos, 0 errores).
    - Compilación limpia de documentación Sphinx.

---

## Mauricio González — 05/11/2026 — Antigravity IDE (Gemini)

**Contexto:** Sprint 5 / Invoicing — Arquitectura desacoplada para Facturación Electrónica (InvoiceProvider y MockInvoiceProvider) (SCRUM-117)

**Resumen:**
- Diseñé e implementé en la nueva aplicación `apps/invoicing/` el patrón Strategy / Adapter para la integración con Facturación Electrónica SIFEN / e-Kuatia, rigurosamente basado en la especificación técnica oficial del PDF *"API de Factura Segura para ESI (External Systems Interoperation) v01"*:
  - **Patrón Strategy / Adapter y Contratos Formales (`apps/invoicing/providers/` y `types.py`):**
    - Interfaz abstracta base `InvoiceProvider` (`apps/invoicing/providers/base.py`) que estandariza las 8 operaciones oficiales del manual ESI: `calcular_de`, `generar_de`, `get_estado_sifen`, `sol_cancelacion`, `sol_inutilizacion`, `dwn_kude`, `dwn_xml` y la fachada `emitir_factura`.
    - DTOs inmutables con dataclasses en `apps/invoicing/types.py` (`InvoiceResponse`, `StatusResponse`, `CalculationResult`, `EstadoSifenEnum`).
    - Jerarquía de excepciones en `apps/invoicing/exceptions.py` (`InvoiceProviderError`, `QuotaExhaustedError`, `LiveModeDisabledError`, `InvoiceValidationError`).
  - **Motor Matemático SIFEN Canónico (`apps/invoicing/calculators.py`):**
    - Implementación del algoritmo oficial de Módulo 11 (`compute_mod11_dv`) para RUC y claves de acceso.
    - Generador de CDC oficial de 44 dígitos (`generate_cdc`) con tipo de documento, RUC emisor, DV, establecimiento, punto de expedición, número correlativo, tipo de contribuyente, fecha YYYYMMDD, tipo de emisión, código de seguridad de 9 dígitos y DV Módulo 11 final.
    - Motor de cálculo matemático `calculate_de` que reproduce con exactitud las fórmulas de las páginas 17 a 21 del manual ESI para ítems gravados (10% y 5%), gravado parcial (proporción gravada y base exenta), exentos y exonerados, con liquidación de IVA y cálculo de subtotales.
  - **Simulador de Alta Fidelidad (`MockInvoiceProvider`):**
    - Generación de CDCs de 44 dígitos válidos y estado SIFEN `0260 - Aprobado`.
    - Generador autónomo de PDF binario KuDE 1.4 sin dependencias externas.
    - Generador de XML firmado canónico bajo esquema `rDE` (`http://ekuatia.set.gov.py/sifen/xsd`).
    - Almacén en memoria para registro de CDC emitidos, cancelaciones simuladas e inutilizaciones, garantizando **0 consumo de cuota real de la API de Factura Segura**.
  - **Adaptador Real y Blindaje de Seguridad (`FacturaSeguraProvider` y `factory.py`):**
    - Implementación del protocolo envelope ESI (`/misife00/v1/esi`), autenticación `/login?include_auth_token` y header `Authentication-Token`.
    - Guardián estricto que dispara `LiveModeDisabledError` ante cualquier intento de llamada externa cuando `FACTURA_SEGURA_LIVE_ENABLED=False` (configurado por defecto).
    - Fábrica `get_invoice_provider()` con selección automática según entorno e inyección de mocks para tests.
  - **Documentación Técnica Sphinx y Calidad:**
    - Documentación completa en `docs/sphinx/source/invoicing.rst` integrada en `modules.rst`. Compilación limpia de Sphinx (`build succeeded`).
    - Suite de **25 pruebas unitarias e integración en `apps/invoicing/tests.py`** con **93% de cobertura**.
    - Suite completa del proyecto: **561 tests aprobados al 100% de éxito (OK)**, 0 fallos, 0 errores, sin regresiones.
    - Redacción del reporte de ingeniería en `docs/documentacion/SCRUM-117.md` y actualización de `TAREAS.md` y `RESOLUCION_TAREAS_IA.md`.
