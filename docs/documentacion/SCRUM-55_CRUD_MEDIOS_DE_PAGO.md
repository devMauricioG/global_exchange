# Documentación Técnica — SCRUM-55: CRUD de Medios de Pago de Clientes (`payments`)

**ID Jira:** SCRUM-55  
**Épica Principal:** SCRUM-49 (Cuentas y Medios de Pago)  
**Sprint:** SCRUM Sprint 2  
**Autor:** Pablo Elizeche (con asistencia de IA Antigravity / Gemini)  
**Fecha:** 08/09/2026  
**Rama de trabajo:** `feature/SCRUM-55`  

---

## 1. Descripción del Requerimiento

Crear la aplicación Django `payments` con el modelo `PaymentMethod` (`cliente`, `tipo_medio`, `entidad_bancaria/billetera`, `numero_cuenta/telefono`, `titular`, `documento_titular`, `es_predeterminado`, `activo`), formularios validados, vistas basadas en clases (CBVs) web y endpoints API REST para la administración integral y segura de instrumentos financieros por parte del cliente.

---

## 2. Arquitectura y Componentes Implementados

### 2.1 Modelo de Datos (`payments/models.py`)

* **Entidad `PaymentMethod`**:
  * `cliente`: Clave foránea (`ForeignKey`) hacia `customers.models.Cliente` con eliminación en cascada (`on_delete=models.CASCADE`) y relación inversa `medios_pago`.
  * `tipo_medio`: Enumeración basada en `TextChoices` (`TRANSFERENCIA`, `BILLETERA`, `TARJETA`, `EFECTIVO`, `OTRO`).
  * `entidad_bancaria`: Nombre del banco, financiera o proveedor móvil (ej. Banco Itaú, Continental, Ueno, Tigo Money, Wally).
  * `numero_cuenta`: Número de cuenta corriente/caja de ahorro o número telefónico de billetera electrónica.
  * `titular`: Nombre completo o razón social del titular registrado.
  * `documento_titular`: Cédula civil o RUC del titular (opcional).
  * `es_predeterminado`: Booleano que define si es el medio de pago preferido para operaciones y liquidaciones.
  * `activo`: Booleano para inhabilitación lógica.
  * `created_at` y `updated_at`: Marcas temporales automáticas.
* **Reglas de Negocio en Modelo**:
  * **Exclusividad atómica de medio predeterminado:** En el método `save()`, si una cuenta es marcada con `es_predeterminado=True`, cualquier otro medio del mismo cliente es automáticamente desmarcado dentro de una transacción atómica (`transaction.atomic()`).
  * **Validación de integridad en `clean()`:** Impide que un medio inactivo sea configurado como predeterminado y valida que los campos de texto no contengan únicamente caracteres en blanco.

### 2.2 Seguridad y Prevención de Vulnerabilidades (IDOR)

* **Resolución de Cliente (`get_current_cliente`)**:
  * Identifica el cliente activo del usuario autenticado a través de su sesión (`request.active_customer`, `request.session['active_customer_id']`, relación directa `request.user.cliente` o correo institucional).
  * Los operadores y administradores (`is_staff`/`is_superuser`) pueden supervisar cualquier cliente mediante el parámetro `cliente_id`.
* **Aislamiento Multi-Tenant**:
  * `PaymentMethodListView` filtra estrictamente por `cliente=get_current_cliente(request)`.
  * En `PaymentMethodUpdateView`, `PaymentMethodDeleteView`, `PaymentMethodSetDefaultView` y `PaymentMethodToggleActiveView`, el método `get_queryset()` restringe las consultas exclusivamente a los medios de pago del cliente autenticado. Si un usuario intenta acceder a la clave primaria (ID) de un medio de otro cliente, el sistema responde con `404 Not Found` / `PermissionDenied`, mitigando de raíz vulnerabilidades de Insecure Direct Object References (IDOR).

### 2.3 Formularios (`payments/forms.py`)

* **`PaymentMethodForm`**: Formulario `ModelForm` estilizado con clases del diseño visual corporativo (`form-input`, `form-select`, `form-checkbox`), tarjetas interactivas para toggles y validación cruzada entre `es_predeterminado` y `activo`.
* **`PaymentMethodFilterForm`**: Formulario de búsqueda en tiempo real por término de texto (`q`), clasificación por `tipo_medio` y filtro por estado `activo`.

### 2.4 Interfaz de Usuario y Plantillas (`templates/payments/`)

* **`paymentmethod_list.html`**:
  * Tablero con métricas clave (KPIs): Total de cuentas registradas, cantidad habilitada y medio predeterminado actual.
  * Selector y buscador interactivo con persistencia de filtros GET.
  * Tarjetas individuales con insignias de tipo de medio, insignia dorada para el medio predeterminado y botones de acción rápida ("Predeterminar", "Habilitar/Inhabilitar", "Editar", "Eliminar").
  * Estado vacío (*empty state*) intuitivo con botón directo a nuevo registro.
* **`paymentmethod_form.html`**:
  * Pantalla de alta y modificación con caja informativa de seguridad financiera y diseño responsive.
  * Selección automática del primer medio registrado como predeterminado por conveniencia del cliente.
* **`paymentmethod_confirm_delete.html`**:
  * Diálogo de confirmación segura con detalle del medio que será revocado.

### 2.5 API REST Programática (`payments/views.py` y `payments/urls.py`)

* `GET /payments/api/`: Retorna el listado serializado de medios de pago del cliente en formato JSON.
* `POST /payments/api/`: Crea un nuevo medio de pago asociado al cliente activo vía payload JSON.
* `GET /payments/api/<pk>/`: Consulta el detalle en formato JSON.
* `PUT / PATCH /payments/api/<pk>/`: Actualización completa o parcial de campos.
* `DELETE /payments/api/<pk>/`: Eliminación controlada de la entidad.

---

## 3. Cobertura de Pruebas Unitarias e Integración

Se construyó una suite con **21 pruebas automatizadas** en `payments/tests.py`, alcanzando un total de **90 tests aprobados** en la suite global del proyecto:

1. **Pruebas de Modelo (`PaymentMethodModelTestCase`)**:
   * Creación exitosa y formato de `__str__`.
   * Exclusividad atómica del método predeterminado para un mismo cliente.
   * Independencia de medios predeterminados entre clientes distintos.
   * Rechazo de medios inactivos como predeterminados (`ValidationError`).
   * Validación de campos en blanco.
2. **Pruebas de Formularios (`PaymentMethodFormTestCase`)**:
   * Validación con datos correctos.
   * Rechazo de configuración inconsistente (inactivo + predeterminado).
   * Validación de filtros de listado.
3. **Pruebas de Vistas Web y Control de Acceso (`PaymentMethodViewsTestCase`)**:
   * Redirección por acceso anónimo.
   * Aislamiento estricto de datos en el listado.
   * Creación exitosa con asociación automática de cliente.
   * Asignación automática de predeterminado en el primer registro.
   * **Mitigación IDOR en Update y Delete:** Respuesta `404 Not Found` al intentar mutar registros ajenos.
   * Acciones rápidas `set_default` y `toggle_active`.
4. **Pruebas de API REST (`PaymentMethodAPITestCase`)**:
   * Verificación de códigos de estado HTTP 200, 201 y 200 (delete) en endpoints JSON.

---

## 4. Archivos Creados e Intervenidos

| Archivo | Acción | Descripción |
|---|---|---|
| `payments/__init__.py` | CREADO | Inicialización del paquete Django `payments`. |
| `payments/apps.py` | CREADO | Configuración de la aplicación `PaymentsConfig`. |
| `payments/models.py` | CREADO | Modelo `PaymentMethod`, enum `TipoMedio` y lógica de exclusividad. |
| `payments/forms.py` | CREADO | Formularios `PaymentMethodForm` y `PaymentMethodFilterForm`. |
| `payments/views.py` | CREADO | CBVs web, seguridad IDOR, helper de cliente y API REST. |
| `payments/urls.py` | CREADO | Mapeo de rutas web y de endpoints API. |
| `payments/admin.py` | CREADO | Registro y personalización del panel de administración Django. |
| `payments/tests.py` | CREADO | Suite de 21 pruebas unitarias e integración. |
| `payments/migrations/0001_initial.py` | CREADO | Migración inicial del modelo `PaymentMethod`. |
| `apps/__init__.py` | CREADO | Adaptador de compatibilidad de importación bajo `apps.payments`. |
| `templates/payments/paymentmethod_list.html` | CREADO | Plantilla interactiva de listado con KPIs y tarjetas. |
| `templates/payments/paymentmethod_form.html` | CREADO | Plantilla de formulario de registro y edición. |
| `templates/payments/paymentmethod_confirm_delete.html` | CREADO | Plantilla de confirmación de eliminación. |
| `config/settings/base.py` | MODIFICADO | Registro de `'payments'` en `INSTALLED_APPS`. |
| `config/urls.py` | MODIFICADO | Enrutamiento de rutas `/payments/`. |
| `templates/base.html` | MODIFICADO | Enlace a Medios de Pago en la barra de navegación superior. |
| `docs/documentacion/SCRUM-55_CRUD_MEDIOS_DE_PAGO.md` | CREADO | Este documento técnico de especificación. |
| `docs/documentacion/Jira workflow/TAREAS.md` | MODIFICADO | Actualización de estado de SCRUM-55 a Finalizado. |
| `docs/chat_ia.md` | MODIFICADO | Bitácora de prompts y decisiones tomadas con IA. |
