# Descripción detallada del diagrama de arquitectura

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

Este módulo administra clientes y su relación con las operaciones del sistema.

### Componentes

- `models.py (Customer, Assignment)`: contiene los modelos de cliente y de asignación. `Assignment` podría representar la asignación de clientes a usuarios, responsables, cuentas u otros recursos del sistema.
- `views.py (Customer Management)`: agrupa las vistas para crear, consultar, actualizar o administrar clientes.

### Relación principal

La aplicación se conecta con `apps.authentication`, lo que sugiere que la administración de clientes requiere usuarios autenticados y control de acceso.

## 6. Aplicación `apps.cash_register`

Este módulo gestiona la apertura, arqueo y cierre de cajas registradoras.

### Componentes

- `models.py (CashRegister)`: define la entidad que representa una caja registradora o sesión de caja.
- `views.py (Apertura, Arqueo, Cierre)`: implementa las operaciones de apertura de caja, arqueo y cierre.

### Relaciones

`apps.cash_register` se relaciona con `apps.transactions`, dado que las operaciones de compra y venta deben afectar una caja o quedar asociadas a ella. También se conecta con `apps.authentication`, probablemente para validar el usuario responsable de cada operación y aplicar permisos.

## 7. Aplicación `apps.rates`

Este módulo administra las tasas de cambio utilizadas por el sistema.

### Componentes

- `models.py (ExchangeRate)`: define el modelo de tasa de cambio.
- `views.py (Rates & Dashboard)`: proporciona vistas para consultar o administrar tasas y visualizar un panel o dashboard.

### Relación principal

La conexión con `apps.transactions` indica que las tasas de cambio son utilizadas durante la cotización, compra o venta.

## 8. Aplicación `apps.authentication`

Este módulo centraliza la autenticación y la autorización de las solicitudes.

### Componentes

- `middlewares.py (JWT Bearer Validation)`: implementa un middleware para validar tokens JWT enviados mediante el esquema Bearer. Su función es interceptar solicitudes y verificar la identidad del solicitante antes de permitir el acceso a los recursos protegidos.
- `backends.py (Keycloak OIDC)`: integra el sistema con Keycloak utilizando OpenID Connect. Este backend permite delegar la autenticación y posiblemente la obtención de roles o claims a Keycloak.

### Relación con el núcleo global

`apps.authentication` se comunica con `global_exchange_core`, específicamente con la configuración OIDC/Keycloak y el enrutamiento principal de Django.

## 9. Paquete `global_exchange_core`

Este paquete contiene la configuración transversal del proyecto Django.

### Componentes

- `settings.py (OIDC/Keycloak Config)`: contiene la configuración general del proyecto y los parámetros de integración con OpenID Connect/Keycloak.
- `urls.py (Root Routing)`: define el enrutamiento raíz y conecta las rutas globales con las aplicaciones del proyecto.
- `wsgi.py / asgi.py`: proporcionan los puntos de entrada para desplegar la aplicación mediante servidores compatibles con WSGI y ASGI, respectivamente.

Este paquete funciona como la capa de composición del sistema: configura Django, registra aplicaciones, establece autenticación y expone las rutas y puntos de entrada de ejecución.

## 10. Flujo funcional inferido

El flujo general representado por el diagrama puede describirse así:

1. Un usuario autenticado accede al sistema mediante JWT Bearer.
2. La autenticación puede delegarse o validarse mediante Keycloak usando OIDC.
3. El usuario utiliza las vistas de clientes, transacciones, caja o tasas.
4. Una operación de compra, venta o cotización se procesa en `apps.transactions`.
5. La transacción puede asociarse con un cliente de `apps.customers`.
6. La operación puede utilizar una tasa de cambio proporcionada por `apps.rates`.
7. El resultado puede registrarse en una caja administrada por `apps.cash_register`.
8. Cuando corresponde, la transacción puede generar o consultar un documento electrónico a través de `apps.electronic_docs` y la API de SIFEN/DNIT.
9. Las solicitudes son dirigidas por `global_exchange_core.urls.py` y la aplicación se ejecuta mediante WSGI o ASGI.

## 11. Responsabilidades por capa

| Área | Responsabilidad |
|---|---|
| Modelos de dominio | Persistir clientes, transacciones, cajas, tasas y documentos electrónicos. |
| Vistas | Exponer las operaciones de negocio y las interfaces de gestión. |
| Integraciones | Comunicarse con SIFEN/DNIT y Keycloak. |
| Seguridad | Validar JWT Bearer y aplicar autenticación OIDC. |
| Configuración | Centralizar parámetros de Django, OIDC y Keycloak. |
| Enrutamiento | Resolver las rutas principales del proyecto. |
| Despliegue | Proporcionar entradas WSGI y ASGI. |

## 12. Observaciones de arquitectura

- La separación en aplicaciones Django favorece la modularidad y delimita las responsabilidades del dominio.
- `apps.transactions` parece actuar como coordinador de los principales procesos operativos.
- La autenticación está desacoplada de las aplicaciones de negocio mediante middleware y backend propios.
- Keycloak proporciona un mecanismo centralizado de identidad, mientras que JWT permite proteger las solicitudes de la API.
- La integración con SIFEN/DNIT está aislada en un cliente específico, lo que facilita el mantenimiento y las pruebas.
- La presencia simultánea de WSGI y ASGI permite soportar despliegues tradicionales y escenarios compatibles con ejecución asíncrona.

## 13. Conclusión

El diagrama describe una arquitectura Django modular para una plataforma de intercambio o gestión financiera denominada **Global Exchange**. El sistema integra operaciones de compra y venta, clientes, cajas registradoras, tasas de cambio y documentos electrónicos, con autenticación centralizada mediante Keycloak/OIDC y validación JWT. El paquete `global_exchange_core` articula la configuración y exposición de todas las aplicaciones.
