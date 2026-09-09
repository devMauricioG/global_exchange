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
