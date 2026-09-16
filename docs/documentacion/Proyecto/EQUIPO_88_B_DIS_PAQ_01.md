# Descripción detallada del diagrama de arquitectura

> Última actualización: SCRUM 57 — incorpora la estructura real de los módulos `rates` y `payments`, y precisa que `comisiones` y `cotizador` pertenecen a `rates`.

## 1. Identificación general

El documento presenta un diagrama de arquitectura de software para el proyecto **Django (Global Exchange)**. La solución está organizada como un proyecto Django compuesto por varias aplicaciones funcionales y un núcleo central de configuración y enrutamiento.

El diagrama muestra módulos, archivos principales y relaciones de dependencia o comunicación entre ellos. La arquitectura separa responsabilidades de negocio, autenticación, integración externa y configuración global.

> Nota: el PDF está compuesto por una imagen y no contiene texto seleccionable; la descripción se elaboró a partir de la información visible en el diagrama.

## 2. Estructura general

El proyecto se divide visualmente en los siguientes componentes:

- `apps.electronic_docs`.
- `apps.transactions`.
- `apps.customers`.
- `apps.cash_register`.
- `apps.rates`.
- `apps.authentication`.
- `global_exchange_core`.

La aplicación `apps.transactions` aparece como el punto central de interacción del dominio operativo. Se relaciona con clientes, cajas registradoras y tasas de cambio, mientras que también recibe información o servicios asociados a documentos electrónicos.

## 3. Aplicación `apps.electronic_docs`

Este módulo concentra la gestión de documentos electrónicos y la comunicación con servicios externos relacionados con SIFEN/DNIT.

### Componentes

- `models.py (ElectronicDocument)`: define el modelo de datos utilizado para representar documentos electrónicos.
- `sifen_client.py (API SIFEN/DNIT)`: encapsula la integración con la API de SIFEN/DNIT. Su responsabilidad probable es enviar, consultar o procesar documentos electrónicos frente al servicio tributario externo.

### Relación principal

`apps.electronic_docs` se conecta con `apps.transactions`, lo que indica que las transacciones pueden generar, asociar o requerir documentos electrónicos.

## 4. Aplicación `apps.transactions`

Este módulo representa el núcleo del flujo comercial o financiero de la aplicación.

### Componentes

- `models.py (Transaction)`: define la entidad persistente que representa una transacción.
- `views.py (Compra/Venta, Cotizador)`: contiene las vistas relacionadas con operaciones de compra, venta y cotización.

### Relaciones

Desde `apps.transactions` se observan conexiones hacia:

- `apps.customers`, para asociar las operaciones con clientes.
- `apps.cash_register`, para registrar o controlar operaciones de caja.
- `apps.rates`, para utilizar tasas o tipos de cambio.
- `apps.electronic_docs`, para vincular transacciones con documentos electrónicos.

Por su posición en el diagrama, este módulo coordina buena parte del proceso de negocio.

## 5. Aplicación `apps.customers`

Este módulo administra clientes, la multi-representación de usuarios y la contextualización del cliente activo para las operaciones del sistema.

### Componentes

- `models.py (Customer, CustomerUserAssignment)`:
  - `Customer`: entidad que representa a la persona física o jurídica (Minorista, Mayorista, Corporativo, VIP).
  - `CustomerUserAssignment`: entidad asociativa intermedia que materializa la relación N:M entre `User` y `Customer`. Registra `user`, `customer`, `is_primary_representative`, `assigned_at`, `is_active` y el rol corporativo, posibilitando que un usuario opere en nombre de varios clientes y que una empresa tenga múltiples representantes autorizados.
- `middlewares.py (ActiveCustomerMiddleware)`: intercepta cada petición HTTP, evalúa el `active_customer_id` en la sesión del usuario, valida que exista una asignación activa en `CustomerUserAssignment` e inyecta la instancia `request.active_customer`. Aplica selección automática por defecto (representante principal) si no hay selección explícita.
- `context_processors.py (active_customer_context)`: inyecta en el contexto global de las plantillas el cliente activo actual (`active_customer`) y la lista de clientes disponibles (`user_assigned_customers`) para alimentar el selector dinámico del navbar.
- `views.py (Customer Management & Switch Active)`:
  - Vistas CBVs para el ciclo de vida del cliente (listado con filtros por segmento, creación, detalle, edición y baja).
  - `CustomerSwitchActiveView`: endpoint seguro que valida permisos de asignación activa y actualiza el cliente activo en sesión, retornando `HTTP 403 Forbidden` si un usuario intenta operar un cliente no asignado.

### Relaciones del paquete

- **Con `apps.authentication`**: vincula identidades de usuarios autenticados con sus clientes representados a través de `CustomerUserAssignment`.
- **Con `global_exchange_core`**: registra el middleware y el context processor en el pipeline de ejecución de Django.
- **Con `apps.transactions`**: suministra el cliente activo bajo el cual se registran y facturan las cotizaciones y operaciones cambiarias.

## 6. Aplicación `apps.cash_register`

Este módulo gestiona la apertura, arqueo y cierre de cajas registradoras.

### Componentes

- `models.py (CashRegister)`: define la entidad que representa una caja registradora o sesión de caja.
- `views.py (Apertura, Arqueo, Cierre)`: implementa las operaciones de apertura de caja, arqueo y cierre.

### Relaciones

`apps.cash_register` se relaciona con `apps.transactions`, dado que las operaciones de compra y venta deben afectar una caja o quedar asociadas a ella. También se conecta con `apps.authentication`, probablemente para validar el usuario responsable de cada operación y aplicar permisos.

## 7. Aplicación `apps.rates`

Gestiona parámetros financieros y simulaciones: monedas, tasas de cambio, histórico, comisiones por segmento y cotizador neto.

### Componentes

| Componente | Responsabilidad |
| --- | --- |
| `models.py` | Define `Currency`, `ExchangeRate` y `SegmentCommission` con validaciones financieras. |
| `services.py` | Resuelve el cliente activo, consulta la tasa vigente y calcula la cotización neta. |
| `forms.py` | Valida datos de monedas, tasas, comisiones y parámetros del cotizador. |
| `views.py` | Implementa CRUD, tablero, cotizador y endpoints JSON. |
| `urls.py` | Expone rutas bajo `/rates/`. |
| `admin.py` | Facilita la parametrización administrativa y asigna el usuario que actualiza tasas. |
| `tests.py` | Cubre modelo, servicio, formularios, vistas y APIs. |

### Submódulo conceptual: comisiones

No existe como aplicación Django separada. Se implementa mediante `SegmentCommission` y las vistas `SegmentCommission*` dentro de `rates`. Depende de `customers.Cliente.Segmentacion` para obtener los segmentos autorizados.

### Submódulo conceptual: cotizador

Tampoco es una aplicación independiente. Usa `RateCalculationService`, la vista `RateCalculatorView` y `CalculateNetRateApiView`. Recibe datos de `ExchangeRate` y `SegmentCommission`, pero no persiste una transacción ni cambia una tasa.

### Relaciones

- **Con `apps.customers`**: `SegmentCommission` usa las opciones de segmentación de `Cliente`; `RateCalculationService` resuelve el cliente activo y el segmento comercial.
- **Con `apps.transactions`**: las tasas de cambio y el resultado del cotizador son utilizados durante la cotización, compra o venta.

## 7b. Aplicación `apps.payments`

Administra medios de pago de los clientes sin ejecutar la liquidación financiera. La propiedad del recurso se resuelve con el cliente activo y protege las vistas contra acceso horizontal no autorizado.

### Componentes

| Componente | Responsabilidad |
| --- | --- |
| `models.py` | Define `PaymentMethod` y garantiza un medio predeterminado activo por cliente. |
| `forms.py` | Valida datos obligatorios y la consistencia entre predeterminado y activo. |
| `views.py` | Ofrece CRUD web, acciones de estado y API JSON. |
| `urls.py` | Expone rutas bajo `/payments/`. |
| `tests.py` | Verifica integridad, formularios, aislamiento por cliente e interfaces API. |

### Relaciones

- **Con `apps.customers`**: `PaymentMethod` pertenece a un cliente; las vistas filtran por cliente activo en cada operación.
- **Con `global_exchange_core`**: el paquete `config` incluye las rutas de `payments`.

> **Nota:** No se permite que `payments` dependa del motor de cotización para su CRUD actual. Si una transacción futura necesita ambos paquetes, el orquestador debe ubicarse en `transactions` para evitar acoplamiento circular.

## 8. Aplicación `apps.authentication`

Este módulo centraliza la autenticación, autorización y resolución de privilegios basada en roles JWT.

### Componentes

- `middlewares.py (JWT Bearer Validation)`: intercepta solicitudes API y valida tokens JWT enviados mediante esquema Bearer.
- `backends.py (Keycloak OIDC)`: integra el sistema con Keycloak mediante OpenID Connect, gestionando la sincronización de identidades y claims del usuario.
- `context_processors.py (auth_roles)`: inyecta en plantillas los roles extraídos del token JWT (`is_admin`, `is_operator`, `is_auditor`, etc.).
- `templatetags/auth_tags.py`: etiquetas personalizadas (`has_role`, `has_any_role`) para renderizado condicional de componentes en `templates/base.html`.

### Relación con el núcleo global

`apps.authentication` se comunica con `global_exchange_core`, proveyendo los backends de autenticación y los middlewares de seguridad.

## 9. Paquete `global_exchange_core`

Este paquete contiene la configuración transversal del proyecto Django y servicios globales de plataforma.

### Componentes

- `settings.py (Configuración Multientorno)`:
  - `base.py`: configuración común, registro de aplicaciones, middlewares y context processors.
  - `dev.py` / `prod.py`: entornos de persistencia con PostgreSQL y Keycloak.
  - `test.py`: entorno optimizado in-memory SQLite para ejecución rápida de tests unitarios y cobertura.
- `urls.py (Root Routing)`: define el enrutamiento raíz conectando las rutas de autenticación, clientes, transacciones y documentación.
- `views.py (ServeSphinxDocsView)`: vista especializada para servir de manera integrada y protegida la documentación técnica generada por Sphinx (`docs/sphinx/build/html/`), con verificación de tipos MIME y mitigación de Path Traversal.
- `wsgi.py / asgi.py`: puntos de entrada para servidores de producción (Gunicorn / Uvicorn).

```mermaid
graph TD
    subgraph ClientLayer [Capa de Presentación / Cliente]
        Browser[Navegador Web / HTTPS]
    end

    subgraph Core [global_exchange_core]
        RootURLs[urls.py]
        DocsView[views.py - ServeSphinxDocsView]
        Settings[settings/]
    end

    subgraph AuthApp [apps.authentication]
        OIDCBackend[backends.py - Keycloak OIDC]
        AuthContext[context_processors.py - auth_roles]
        AuthTags[templatetags - auth_tags]
    end

    subgraph CustomerApp [apps.customers]
        CustomerModel[models.py - Customer]
        AssignmentModel[models.py - CustomerUserAssignment]
        ActiveMiddleware[middlewares.py - ActiveCustomerMiddleware]
        ActiveContext[context_processors.py - active_customer]
        CustomerViews[views.py - CRUD & SwitchActive]
    end

    subgraph RatesApp [apps.rates]
        RatesModels[models.py - Currency ExchangeRate SegmentCommission]
        RatesServices[services.py - RateCalculationService]
        RatesViews[views.py - CRUD Dashboard Cotizador API]
    end

    subgraph PaymentsApp [apps.payments]
        PaymentsModels[models.py - PaymentMethod]
        PaymentsViews[views.py - CRUD & API JSON]
    end

    subgraph DomainApps [Módulos de Dominio Operativo]
        Transactions[apps.transactions]
        CashRegister[apps.cash_register]
        ElectronicDocs[apps.electronic_docs]
    end

    subgraph TemplatesLayer [Plantillas]
        Templates[templates - rates y payments]
    end

    subgraph SphinxDocs [Documentación Sphinx]
        HTMLTree[docs/sphinx/build/html/]
    end

    DB[(Base de datos)]

    Browser --> RootURLs
    RootURLs --> DocsView
    DocsView --> HTMLTree
    RootURLs --> AuthApp
    RootURLs --> CustomerApp
    RootURLs --> RatesApp
    RootURLs --> PaymentsApp
    RootURLs --> DomainApps

    ActiveMiddleware --> AssignmentModel
    ActiveMiddleware --> CustomerModel
    CustomerViews --> AssignmentModel
    CustomerViews --> CustomerModel
    DomainApps --> CustomerModel

    RatesServices --> RatesModels
    RatesServices --> CustomerModel
    RatesViews --> RatesServices
    RatesViews --> Templates
    PaymentsViews --> Templates
    RatesModels --> DB
    PaymentsModels --> DB
    CustomerModel --> DB
    AuthApp --> CustomerApp
    CustomerApp --> PaymentsApp
    CustomerApp --> RatesApp
```

## 10. Dependencias permitidas entre paquetes

| Origen | Destino | Motivo |
| --- | --- | --- |
| `rates.models` | `customers.models` | `SegmentCommission` usa las opciones de segmentación de `Cliente`. |
| `rates.services` | `customers.models` | Resuelve el cliente activo y el segmento comercial. |
| `rates.views` | `rates.services` | Delega la matemática de cotización al servicio. |
| `payments.models` | `customers.models` | `PaymentMethod` pertenece a un cliente. |
| `payments.views` | `customers` | Filtra por cliente activo en cada operación. |
| `config` | `rates`, `payments` | Incluye rutas de ambas aplicaciones. |

## 11. Interfaces expuestas

| Paquete | Interfaz | Propósito |
| --- | --- | --- |
| `rates` | `/rates/calculator/` | Cotizador web autenticado. |
| `rates` | `/rates/api/calculate/` | Cálculo JSON por GET o POST. |
| `rates` | `/rates/api/commissions/` | Lista de reglas de comisión. |
| `rates` | `/rates/api/commissions/<segment>/` | Detalle de una regla por segmento. |
| `rates` | `/rates/dashboard/` y `/rates/api/history/` | Visualización e historial de cotizaciones. |
| `payments` | `/payments/` | Gestión web de medios de pago. |
| `payments` | `/payments/api/` y `/payments/api/<pk>/` | API JSON de medios de pago. |

## 12. Flujo funcional inferido

El flujo general del sistema incorpora la multi-representación, la consulta técnica y la interacción entre `rates` y `payments`:

1. **Autenticación e Identidad:** El usuario inicia sesión vía Keycloak OIDC. El backend valida el token JWT y extrae los roles y el UUID (`sub`).
2. **Resolución de Cliente Activo:**
   - `ActiveCustomerMiddleware` verifica las asignaciones en `CustomerUserAssignment`.
   - Si el usuario representa a varios clientes, se inyecta la lista de representados en el selector del navbar (`base.html`).
   - El usuario puede alternar de cliente en cualquier momento mediante `CustomerSwitchActiveView`, actualizando la sesión de forma atómica.
3. **Cotización y parametrización (`rates`):** El cotizador obtiene el segmento del cliente activo y solicita a `rates.models` la tasa vigente y la regla de comisión aplicable. `RateCalculationService` entrega un resultado informativo a la vista o API de `rates`.
4. **Medios de pago (`payments`):** De forma independiente, el mismo cliente puede registrar o elegir un medio de pago para una futura liquidación.
5. **Operativa Comercial Contextualizada:** Las compras, ventas y cotizaciones en `apps.transactions` se imputan automáticamente al cliente activo en la sesión.
6. **Futuro módulo transaccional:** Un módulo `transactions` posterior podrá usar el resultado confirmado y un medio de pago elegido sin alterar los paquetes de parametrización.
7. **Acceso a Documentación Técnica:** A través del menú superior, los usuarios autorizados o desarrolladores pueden acceder a `/docs/`, donde `ServeSphinxDocsView` sirve los documentos HTML autogenerados.

## 13. Responsabilidades por capa

| Área | Componentes Clave | Responsabilidad |
| --- | --- | --- |
| **Multi-Representación** | `CustomerUserAssignment`, `ActiveCustomerMiddleware` | Gestionar relaciones N:M usuario-cliente y mantener el cliente activo en sesión. |
| **Modelos de Dominio** | `Customer`, `Transaction`, `CashRegister`, `ExchangeRate`, `Currency`, `SegmentCommission`, `PaymentMethod`, `ElectronicDocument` | Persistir entidades de negocio y reglas de consistencia de datos. |
| **Vistas e Interfaces** | `CustomerViews`, `CustomerSwitchActiveView`, `RatesViews`, `PaymentsViews`, `base.html` | Exponer interfaces responsivas, selectores dinámicos y endpoints REST/JSON. |
| **Servicios de Dominio** | `RateCalculationService` | Encapsular lógica de cálculo de cotización neta desacoplada de vistas. |
| **Documentación Integrada** | `ServeSphinxDocsView`, `docs/sphinx/` | Servir la documentación técnica del código de forma segura y accesible. |
| **Seguridad y Roles** | `Keycloak OIDC`, `auth_roles`, `JWT Bearer` | Centralizar identidades y gobernar permisos por rol en backend y frontend. |
| **Configuración y Rutas** | `global_exchange_core` | Coordinar settings por ambiente (dev/prod/test) y resolver el árbol de URLs. |
| **Integraciones Externas** | `sifen_client.py`, `Keycloak OIDC` | Comunicarse con servicios tributarios (SIFEN/DNIT) y servidor IAM. |
| **Despliegue y Ejecución** | `wsgi.py`, `asgi.py`, `Docker` | Proveer puntos de entrada para servidores WSGI/ASGI y orquestación. |

## 14. Observaciones de arquitectura

- La separación en aplicaciones Django favorece la modularidad y delimita las responsabilidades del dominio.
- `apps.transactions` actúa como coordinador de los principales procesos operativos.
- `apps.rates` consolida monedas, tasas, comisiones y cotizador en un único paquete con separación interna (models/services/views), evitando aplicaciones Django fragmentadas.
- `apps.payments` gestiona medios de pago de forma independiente, sin acoplamiento al motor de cotización.
- La capa de servicios (`RateCalculationService`) desacopla la lógica de negocio de las vistas, facilitando pruebas unitarias y reutilización.
- La autenticación está desacoplada de las aplicaciones de negocio mediante middleware y backend propios.
- Keycloak proporciona un mecanismo centralizado de identidad, mientras que JWT permite proteger las solicitudes de la API.
- La integración con SIFEN/DNIT está aislada en un cliente específico, lo que facilita el mantenimiento y las pruebas.
- La presencia simultánea de WSGI y ASGI permite soportar despliegues tradicionales y escenarios compatibles con ejecución asíncrona.

## 15. Conclusión

El diagrama describe una arquitectura Django modular para una plataforma de intercambio o gestión financiera denominada **Global Exchange**. El sistema integra operaciones de compra y venta, clientes, cajas registradoras, tasas de cambio (con comisiones por segmento y cotizador neto), medios de pago y documentos electrónicos, con autenticación centralizada mediante Keycloak/OIDC y validación JWT. El paquete `global_exchange_core` articula la configuración y exposición de todas las aplicaciones.
