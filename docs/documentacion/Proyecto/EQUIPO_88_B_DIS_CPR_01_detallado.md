# Detalle de la Infraestructura de Producción — EQUIPO 88 B DIS CPR 01

## 1. Descripción general

El PDF presenta un diagrama titulado **“Infraestructura de Producción”**.

La arquitectura muestra una aplicación **Django** desplegada en producción detrás de **Nginx**, utilizando **Gunicorn** como servidor de aplicación WSGI. La aplicación se integra con:

- Un módulo de validación de tokens JWT.
- Un servidor **Keycloak IAM** para obtener/sincronizar claves públicas JWKS.
- Un conjunto de conexiones SQL hacia un **cluster PostgreSQL**.
- Un generador/cliente XML para emisión fiscal.
- Sistemas externos mediante una **API SOAP/REST XML**.
- El sistema externo identificado como **API SIFEN / DNIT**.

El flujo principal representado es:

```text
Cliente HTTPS
     |
     v
Nginx Web Server / Reverse Proxy
     |
     | HTTPS -> WSGI
     v
Gunicorn Process Manager
     |
     | Ejecuta Worker Processes
     v
Django Core App
     |
     +----> Security JWT Validator Module
     |              |
     |              | JWKS Public Keys Sync
     |              v
     |       Keycloak IAM Server
     |
     +----> PostgreSQL DB Cluster
     |
     +----> SIFEN XML Generator & Client
                    |
                    | SOAP/REST XML API
                    v
              API SIFEN / DNIT
```

---

# 2. Infraestructura de Producción

El contenedor exterior del diagrama se denomina:

```text
Infraestructura de Producción
```

Dentro de él se encuentran los principales componentes de ejecución de la aplicación:

1. Nginx.
2. Gunicorn.
3. Django Core App.
4. Security JWT Validator Module.
5. SIFEN XML Generator & Client.
6. Keycloak IAM Server.
7. PostgreSQL DB Cluster.

Fuera de este bloque aparece:

```text
Sistemas Externos
```

que contiene:

```text
API SIFEN / DNIT
```

---

# 3. Nginx Web Server / Reverse Proxy

El primer componente de la infraestructura es:

**Nginx Web Server / Reverse Proxy**

Su función representada en el diagrama es actuar como **Reverse Proxy** delante del servidor de aplicación.

La conexión hacia la aplicación está etiquetada como:

```text
Reverse Proxy (HTTPS -> WSGI)
```

Por lo tanto, Nginx recibe tráfico HTTPS y lo dirige hacia el servidor WSGI de la aplicación.

## Flujo

```text
HTTPS
  |
  v
Nginx
  |
  | HTTPS -> WSGI
  v
Gunicorn
```

### Responsabilidad dentro de este diagrama

Nginx constituye la puerta de entrada de la aplicación de producción y realiza el papel de proxy inverso hacia el servidor WSGI.

> El PDF no especifica certificados, dominios, puertos de escucha de Nginx ni reglas concretas de configuración.

---

# 4. Gunicorn Process Manager

Debajo de Nginx aparece:

**Gunicorn Process Manager**

La conexión está identificada como:

```text
WSGI Application Server
```

y posteriormente:

```text
Ejecuta Worker Processes
```

Esto representa el servidor de aplicaciones que ejecuta los procesos trabajadores encargados de atender las solicitudes de Django.

## Flujo

```text
Nginx
  |
  | WSGI
  v
Gunicorn Process Manager
  |
  | Ejecuta Worker Processes
  v
Django Core App
```

## Función

Gunicorn actúa como servidor WSGI entre Nginx y la aplicación Django.

El diagrama separa claramente:

- **Nginx:** Reverse Proxy.
- **Gunicorn:** WSGI Application Server / Process Manager.
- **Django:** aplicación principal.

---

# 5. Django Core App

El núcleo de la arquitectura es:

**Django Core App**

Es la aplicación central que recibe las solicitudes provenientes de Gunicorn y se comunica con los demás componentes.

El diagrama muestra tres flujos importantes desde Django:

```text
Django Core App
    |
    +----> Security JWT Validator Module
    |
    +----> PostgreSQL DB Cluster
    |
    +----> SIFEN XML Generator & Client
```

Las operaciones indicadas explícitamente son:

```text
Verifica Bearer Token
```

y:

```text
Invoca Emisión Fiscal
```

---

# 6. Security JWT Validator Module

Este módulo aparece conectado directamente con Django.

La relación está indicada como:

```text
Verifica Bearer Token
```

Por lo tanto, su función dentro de la arquitectura es validar el token Bearer asociado a la solicitud.

El flujo es:

```text
Django Core App
       |
       | Verifica Bearer Token
       v
Security JWT Validator Module
```

---

# 7. JWT y Bearer Token

El diagrama utiliza explícitamente los conceptos:

```text
Bearer Token
JWT
```

La aplicación Django envía la solicitud al módulo de seguridad para realizar la verificación del Bearer Token.

Conceptualmente:

```text
HTTP Request
     |
     | Authorization: Bearer <token>
     v
Django
     |
     v
JWT Validator
```

> El PDF no especifica el formato exacto del header HTTP ni las reglas internas de validación del JWT. La representación anterior muestra únicamente la relación conceptual indicada por el texto “Verifica Bearer Token”.

---

# 8. JWKS Public Keys Sync

Desde el módulo de validación JWT sale una conexión denominada:

```text
JWKS Public Keys Sync
```

que apunta a:

**Keycloak IAM Server (Realm Production)**

El flujo es:

```text
Security JWT Validator Module
             |
             | JWKS Public Keys Sync
             v
Keycloak IAM Server
(Realm Production)
```

## 8.1 JWKS

JWKS significa **JSON Web Key Set**.

En el contexto del diagrama, las claves públicas utilizadas para la validación de tokens están relacionadas con Keycloak mediante la sincronización de claves públicas JWKS.

## 8.2 Realm Production

El servidor aparece identificado como:

```text
Keycloak IAM Server (Realm Production)
```

Por lo tanto, el diagrama especifica explícitamente que se trata del realm de producción.

> No se especifica en el PDF la URL del endpoint JWKS, frecuencia de sincronización, mecanismo de caché ni configuración de rotación de claves.

---

# 9. Keycloak IAM Server

El componente de identidad es:

**Keycloak IAM Server (Realm Production)**

Está conectado exclusivamente, según lo visible en el diagrama, con:

```text
Security JWT Validator Module
```

mediante:

```text
JWKS Public Keys Sync
```

Su función dentro de esta arquitectura está asociada con la infraestructura de identidad utilizada para la validación de JWT.

### Flujo

```text
Keycloak IAM
      ^
      |
JWKS Public Keys Sync
      |
      |
JWT Validator
      ^
      |
Django
```

---

# 10. Conexión con PostgreSQL

Django también se conecta al:

**PostgreSQL DB Cluster**

La conexión está identificada en el diagrama como:

```text
SQL Connections Pool
```

El flujo es:

```text
Django Core App
       |
       | SQL Connections Pool
       v
PostgreSQL DB Cluster
```

## 10.1 Connection Pool

El texto:

```text
SQL Connections Pool
```

indica que la arquitectura contempla un conjunto/pool de conexiones SQL hacia PostgreSQL.

Esto representa una capa de gestión de conexiones entre la aplicación y el cluster de base de datos.

> El PDF no proporciona detalles sobre tamaño del pool, número de conexiones, configuración de timeout, balanceo ni mecanismo concreto utilizado para el pooling.

---

# 11. PostgreSQL DB Cluster

La base de datos aparece como:

**PostgreSQL DB Cluster**

Está representada como un cluster, no simplemente como una única instancia local.

El flujo indicado es:

```text
Django
  |
  | SQL Connections Pool
  v
PostgreSQL DB Cluster
```

La arquitectura, por lo tanto, diferencia claramente el entorno de producción del entorno local mostrado en otros diagramas.

---

# 12. SIFEN XML Generator & Client

El segundo componente especializado conectado con Django es:

**SIFEN XML Generator & Client**

La conexión está etiquetada:

```text
Invoca Emisión Fiscal
```

El flujo es:

```text
Django Core App
       |
       | Invoca Emisión Fiscal
       v
SIFEN XML Generator & Client
```

Este componente tiene dos funciones expresadas directamente en su nombre:

1. Generación de XML relacionado con SIFEN.
2. Cliente para comunicación con el sistema externo.

---

# 13. Emisión Fiscal

Django realiza una operación identificada como:

```text
Invoca Emisión Fiscal
```

Esto dirige la operación hacia:

```text
SIFEN XML Generator & Client
```

El flujo conceptual es:

```text
Django
  |
  | Invoca Emisión Fiscal
  v
Generador/Cliente XML
  |
  | SOAP/REST XML API
  v
Sistemas Externos
```

---

# 14. SOAP/REST XML API

La conexión entre el componente de emisión fiscal y los sistemas externos está indicada como:

```text
SOAP/REST XML API
```

Esto significa que el diagrama contempla una comunicación mediante una API que utiliza:

- SOAP y/o REST.
- XML como formato de intercambio.

El flujo es:

```text
SIFEN XML Generator & Client
             |
             | SOAP/REST XML API
             v
       Sistemas Externos
```

---

# 15. Sistemas Externos

Fuera del bloque principal de producción aparece:

**Sistemas Externos**

Dentro de este bloque se encuentra:

```text
API SIFEN / DNIT
```

Por lo tanto, la arquitectura representa la API de SIFEN/DNIT como un sistema externo a la infraestructura de producción de la aplicación.

### Flujo completo

```text
Django
  |
  v
SIFEN XML Generator & Client
  |
  | SOAP/REST XML API
  v
Sistemas Externos
  |
  v
API SIFEN / DNIT
```

---

# 16. Flujo completo de una solicitud

Una representación general del recorrido de una solicitud sería:

```text
┌──────────────────────────────────────┐
│        Cliente / Internet            │
└──────────────────┬───────────────────┘
                   │
                   │ HTTPS
                   v
┌──────────────────────────────────────┐
│ Nginx Web Server / Reverse Proxy     │
└──────────────────┬───────────────────┘
                   │
                   │ HTTPS -> WSGI
                   v
┌──────────────────────────────────────┐
│ Gunicorn Process Manager             │
│ WSGI Application Server              │
└──────────────────┬───────────────────┘
                   │
                   │ Worker Processes
                   v
┌──────────────────────────────────────┐
│ Django Core App                      │
└──────────────┬───────────┬───────────┘
               │           │
               │           │
               │           └──────────────┐
               │                          │
               v                          v
┌────────────────────────┐    ┌──────────────────────────┐
│ Security JWT Validator │    │ PostgreSQL DB Cluster    │
│ Module                 │    │                          │
└────────────┬───────────┘    └──────────────────────────┘
             │
             │ JWKS Public Keys Sync
             v
┌──────────────────────────────┐
│ Keycloak IAM Server          │
│ Realm Production             │
└──────────────────────────────┘
```

Para la emisión fiscal:

```text
Django Core App
       |
       | Invoca Emisión Fiscal
       v
┌────────────────────────────────┐
│ SIFEN XML Generator & Client   │
└───────────────┬────────────────┘
                │
                │ SOAP/REST XML API
                v
┌────────────────────────────────┐
│ Sistemas Externos              │
│                                │
│   API SIFEN / DNIT             │
└────────────────────────────────┘
```

---

# 17. Arquitectura por capas

El diagrama puede dividirse en varias capas.

## Capa 1 — Entrada

```text
Nginx
```

Responsable del Reverse Proxy.

---

## Capa 2 — Servidor WSGI

```text
Gunicorn
```

Responsable de ejecutar los worker processes de la aplicación.

---

## Capa 3 — Aplicación

```text
Django Core App
```

Es el núcleo de la lógica de la aplicación.

---

## Capa 4 — Seguridad

```text
Security JWT Validator Module
```

Verifica los Bearer Tokens y sincroniza claves públicas JWKS con Keycloak.

---

## Capa 5 — Persistencia

```text
PostgreSQL DB Cluster
```

Recibe las conexiones SQL desde la aplicación mediante un pool de conexiones.

---

## Capa 6 — Integración fiscal

```text
SIFEN XML Generator & Client
```

Genera/gestiona XML y realiza la comunicación necesaria para la emisión fiscal.

---

## Capa 7 — Sistemas externos

```text
API SIFEN / DNIT
```

Es el sistema externo con el que se establece comunicación mediante SOAP/REST XML.

---

# 18. Componentes y responsabilidades

| Componente | Función representada |
|---|---|
| Nginx Web Server / Reverse Proxy | Punto de entrada y Reverse Proxy |
| Gunicorn Process Manager | Servidor WSGI y administración de procesos |
| Django Core App | Aplicación central |
| Security JWT Validator Module | Verificación de Bearer Token |
| Keycloak IAM Server | Proveedor de claves públicas JWKS para validación |
| PostgreSQL DB Cluster | Persistencia de datos |
| SQL Connections Pool | Gestión/conjunto de conexiones SQL hacia PostgreSQL |
| SIFEN XML Generator & Client | Generación XML y cliente para emisión fiscal |
| Sistemas Externos | Entorno externo a la infraestructura |
| API SIFEN / DNIT | API externa para la integración fiscal |

---

# 19. Protocolos y tecnologías mencionadas

| Tecnología / protocolo | Uso indicado |
|---|---|
| HTTPS | Comunicación de entrada hacia Nginx |
| WSGI | Comunicación entre Reverse Proxy y servidor de aplicación |
| Gunicorn | Servidor WSGI |
| Django | Aplicación principal |
| JWT | Mecanismo de token validado |
| Bearer Token | Token verificado por el módulo de seguridad |
| JWKS | Sincronización de claves públicas |
| Keycloak | IAM / origen de claves para validación |
| SQL | Acceso a PostgreSQL |
| PostgreSQL | Base de datos de producción |
| SOAP | Posible protocolo de API fiscal |
| REST | Posible protocolo de API fiscal |
| XML | Formato utilizado en la integración fiscal |

---

# 20. Flujo de autenticación

El flujo de autenticación mostrado puede representarse como:

```text
Solicitud
    |
    | Bearer Token
    v
Django Core App
    |
    | Verifica Bearer Token
    v
Security JWT Validator
    |
    | JWKS Public Keys Sync
    v
Keycloak IAM
    |
    | Claves públicas
    v
Security JWT Validator
    |
    | Validación
    v
Django Core App
```

El diagrama no especifica explícitamente qué sucede ante un token inválido, expirado o ausente.

---

# 21. Flujo de acceso a base de datos

El acceso a datos se representa como:

```text
Django Core App
       |
       | SQL Connections Pool
       v
PostgreSQL DB Cluster
```

De forma conceptual:

```text
Request
   |
   v
Django
   |
   | SQL
   v
Connection Pool
   |
   v
PostgreSQL Cluster
```

El PDF no especifica las consultas SQL, tablas, esquema, replicación ni mecanismo de failover del cluster.

---

# 22. Flujo de emisión fiscal

La emisión fiscal tiene tres etapas principales:

### Etapa 1

Django inicia la operación:

```text
Invoca Emisión Fiscal
```

### Etapa 2

La solicitud llega al:

```text
SIFEN XML Generator & Client
```

### Etapa 3

El cliente se comunica con:

```text
API SIFEN / DNIT
```

mediante:

```text
SOAP/REST XML API
```

Representación:

```text
Django
  |
  | Invoca Emisión Fiscal
  v
SIFEN XML Generator & Client
  |
  | SOAP/REST XML API
  v
API SIFEN / DNIT
```

---

# 23. Flujo completo de infraestructura

La arquitectura completa puede resumirse como:

```text
                         PRODUCCIÓN
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│  ┌───────────────────────────────┐                            │
│  │ Nginx                         │                            │
│  │ Web Server / Reverse Proxy    │                            │
│  └──────────────┬────────────────┘                            │
│                 │ HTTPS -> WSGI                               │
│                 v                                             │
│  ┌───────────────────────────────┐                            │
│  │ Gunicorn                      │                            │
│  │ Process Manager              │                            │
│  └──────────────┬────────────────┘                            │
│                 │ Worker Processes                            │
│                 v                                             │
│  ┌───────────────────────────────┐                            │
│  │ Django Core App               │                            │
│  └───────┬───────────┬───────────┘                            │
│          │            │                                       │
│          │            └──────────────┐                        │
│          │                           │                        │
│          v                           v                        │
│  ┌────────────────────┐    ┌──────────────────────┐           │
│  │ Security JWT       │    │ PostgreSQL DB Cluster │           │
│  │ Validator Module   │    └──────────────────────┘           │
│  └─────────┬──────────┘                                       │
│            │                                                   │
│            │ JWKS Public Keys Sync                             │
│            v                                                   │
│  ┌────────────────────────────┐                               │
│  │ Keycloak IAM Server        │                               │
│  │ Realm Production           │                               │
│  └────────────────────────────┘                               │
│                                                               │
│  ┌────────────────────────────┐                               │
│  │ SIFEN XML Generator &      │                               │
│  │ Client                     │                               │
│  └──────────────┬─────────────┘                               │
│                 │ SOAP/REST XML API                           │
└─────────────────┼─────────────────────────────────────────────┘
                  │
                  v
       ┌──────────────────────────────┐
       │ Sistemas Externos            │
       │                              │
       │ API SIFEN / DNIT             │
       └──────────────────────────────┘
```

---

# 24. Diferencia entre componentes internos y externos

## Componentes internos

Están dentro del bloque **Infraestructura de Producción**:

- Nginx.
- Gunicorn.
- Django.
- Security JWT Validator.
- Keycloak IAM.
- PostgreSQL.
- SIFEN XML Generator & Client.

## Componente externo

Está fuera de la infraestructura:

- Sistemas Externos.
- API SIFEN / DNIT.

La separación es importante porque representa un límite entre los servicios controlados por la infraestructura de producción y el sistema externo con el cual se integra.

---

# 25. Comparación conceptual con un entorno de desarrollo

La arquitectura de producción presentada utiliza una estructura más robusta que un servidor de desarrollo.

La cadena de producción es:

```text
Nginx
  ↓
Gunicorn
  ↓
Django
```

Mientras que un entorno de desarrollo puede ejecutar directamente el servidor de desarrollo de Django.

En este diagrama de producción, Django está detrás de:

```text
Nginx + Gunicorn
```

Esto permite separar:

- Reverse Proxy.
- Servidor WSGI.
- Aplicación.

---

# 26. Puntos importantes para estudiar

## Nginx

Recordar:

```text
Web Server / Reverse Proxy
```

y:

```text
HTTPS -> WSGI
```

---

## Gunicorn

Recordar:

```text
WSGI Application Server
```

y:

```text
Ejecuta Worker Processes
```

---

## Django

Es el:

```text
Django Core App
```

y funciona como núcleo de la arquitectura.

---

## Seguridad

El:

```text
Security JWT Validator Module
```

realiza:

```text
Verifica Bearer Token
```

y utiliza:

```text
JWKS Public Keys Sync
```

con:

```text
Keycloak IAM Server (Realm Production)
```

---

## Base de datos

Django utiliza:

```text
SQL Connections Pool
```

para comunicarse con:

```text
PostgreSQL DB Cluster
```

---

## Emisión fiscal

Django:

```text
Invoca Emisión Fiscal
```

al:

```text
SIFEN XML Generator & Client
```

que se comunica con:

```text
API SIFEN / DNIT
```

mediante:

```text
SOAP/REST XML API
```

---

# 27. Resumen final

La infraestructura representada en el PDF puede resumirse en cuatro grandes flujos:

### Entrada

```text
HTTPS
 ↓
Nginx
 ↓
Gunicorn
 ↓
Django
```

### Seguridad

```text
Django
 ↓
JWT Validator
 ↓
JWKS
 ↓
Keycloak
```

### Persistencia

```text
Django
 ↓
SQL Connections Pool
 ↓
PostgreSQL DB Cluster
```

### Emisión fiscal

```text
Django
 ↓
SIFEN XML Generator & Client
 ↓
SOAP/REST XML API
 ↓
API SIFEN / DNIT
```

## Arquitectura resumida

```text
                 ┌──────────────┐
                 │    Nginx     │
                 │ Reverse Proxy│
                 └──────┬───────┘
                        │
                      WSGI
                        │
                        v
                 ┌──────────────┐
                 │   Gunicorn   │
                 └──────┬───────┘
                        │
                   Workers
                        │
                        v
                 ┌──────────────┐
                 │    Django    │
                 └───┬────┬─────┘
                     │    │
          ┌──────────┘    └─────────────┐
          │                             │
          v                             v
   ┌───────────────┐              ┌─────────────┐
   │ JWT Validator │              │ PostgreSQL  │
   └───────┬───────┘              │   Cluster   │
           │                      └─────────────┘
         JWKS
           │
           v
      ┌─────────┐
      │Keycloak │
      └─────────┘

                 Django
                    │
                    │ Emisión Fiscal
                    v
          ┌─────────────────────┐
          │ SIFEN XML Generator │
          │ & Client            │
          └──────────┬──────────┘
                     │
                  SOAP/REST
                     │ XML
                     v
             ┌───────────────┐
             │ API SIFEN/DNIT│
             └───────────────┘
```

> **Alcance:** este documento conserva la terminología y los elementos visibles en el PDF inicial e incorpora formalmente la especificación y matriz de casos de prueba del sistema conforme a los requerimientos del Sprint 2 (SCRUM-42).

---

# 28. MATRIZ FORMAL DE CASOS DE PRUEBA DE SOFTWARE (DIS_CPR_01)

Esta sección consolida la **Matriz de Casos de Prueba (CPR)** para las funcionalidades críticas incorporadas en el Sprint 2: la entidad intermedia de multi-representación `CustomerUserAssignment`, las reglas de negocio para la gestión y cambio dinámico de Cliente Activo en sesión, y las pruebas del Visualizador de Documentación Técnica integrada (Sphinx).

---

## 28.1. Módulo 1: Pruebas de la Entidad `CustomerUserAssignment` (Multi-Representación)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-CUA-001** | Creación exitosa de asignación Usuario ↔ Cliente | Usuario registrado en Keycloak/Django y Cliente registrado en `customers`. | 1. Instanciar `CustomerUserAssignment` con `user`, `customer`, `is_primary_representative=True`.<br>2. Ejecutar `save()`. | La asignación se persiste correctamente en base de datos con `is_active=True`, fecha `assigned_at` autogenerada y clave primaria única. | Alta |
| **CPR-CUA-002** | Validación de unicidad de asignación (`unique_together`) | Existe previamente una asignación activa entre `user_1` y `customer_A`. | 1. Intentar registrar una segunda asignación con la misma tupla `(user_1, customer_A)`.<br>2. Ejecutar `save()`. | El sistema dispara una excepción de integridad `IntegrityError` impidiendo la duplicación del vínculo. | Crítica |
| **CPR-CUA-003** | Regla de único Representante Principal por Cliente | Existe `user_1` asignado como `is_primary_representative=True` para `customer_A`. | 1. Registrar a `user_2` para `customer_A` marcándolo como `is_primary_representative=True`.<br>2. Invocar `save()` o `set_as_primary()`. | La asignación de `user_2` pasa a ser principal y automáticamente la asignación de `user_1` pasa a `is_primary_representative=False`. | Alta |
| **CPR-CUA-004** | Soporte de Multi-Representación (Usuario con N Clientes) | Usuario `user_1` y tres clientes distintos `customer_A`, `customer_B`, `customer_C`. | 1. Crear asignación para `customer_A` (principal).<br>2. Crear asignación para `customer_B` y `customer_C` (secundarios). | Las 3 asignaciones coexisten de forma independiente permitiendo al usuario operar en nombre de cualquiera de ellos. | Alta |
| **CPR-CUA-005** | Desactivación lógica de asignación (`is_active=False`) | Asignación activa entre `user_1` y `customer_A`. | 1. Invocar método `deactivate()`.<br>2. Verificar estado persistido. | El registro permanece en base de datos para fines de auditoría pero `is_active=False`, revocando de inmediato las facultades de operación. | Media |
| **CPR-CUA-006** | Integridad referencial en cascada (`ON DELETE CASCADE`) | Asignación existente entre `user_1` y `customer_A`. | 1. Eliminar el registro del cliente `customer_A`. | Los registros dependientes en `CustomerUserAssignment` se eliminan automáticamente sin dejar claves huérfanas. | Alta |

---

## 28.2. Módulo 2: Pruebas de Reglas de Cambio de Cliente Activo en Sesión

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-ACT-001** | Selección automática de Cliente Principal al iniciar sesión | Usuario autenticado con asignación principal sobre `customer_A`. Clave `active_customer_id` no existe en sesión. | 1. Enviar solicitud HTTP a cualquier vista protegida.<br>2. Interceptar con `ActiveCustomerMiddleware`. | El middleware detecta la ausencia de cliente activo y asigna automáticamente `request.active_customer = customer_A` y persiste su ID en sesión. | Alta |
| **CPR-ACT-002** | Cambio exitoso de Cliente Activo por usuario autorizado | Usuario autenticado con asignaciones válidas sobre `customer_A` (actual) y `customer_B`. | 1. Enviar petición `POST /customers/switch-active/<customer_B.id>/`. | El endpoint valida que existe asignación activa, actualiza `request.session['active_customer_id'] = customer_B.id` y redirige con HTTP 302 a la URL de origen. | Crítica |
| **CPR-ACT-003** | Intento de cambio a Cliente no asignado (Protección IDOR) | Usuario autenticado `user_1`. Existe en el sistema `customer_X` sobre el cual `user_1` no tiene asignación. | 1. Enviar petición `POST /customers/switch-active/<customer_X.id>/`. | El controlador rechaza la solicitud de inmediato con código de estado **`HTTP 403 Forbidden`**, registrando advertencia de seguridad. | Crítica |
| **CPR-ACT-004** | Intento de cambio a Cliente con asignación inactiva | `user_1` posee asignación sobre `customer_B` pero con `is_active=False`. | 1. Enviar petición `POST /customers/switch-active/<customer_B.id>/`. | La solicitud es denegada con **`HTTP 403 Forbidden`** al no encontrarse vigente la representación. | Alta |
| **CPR-ACT-005** | Persistencia del Cliente Activo durante la navegación | Cliente activo establecido en `customer_B`. | 1. El usuario navega entre diferentes módulos (cotizaciones, clientes, tasas). | Todas las solicitudes conservan `request.active_customer = customer_B` sin requerir reelección. | Alta |
| **CPR-ACT-006** | Inyección en plantillas mediante Context Processor | Usuario autenticado con 2 clientes asignados y `customer_B` activo. | 1. Renderizar `templates/base.html`. | El context processor inyecta `active_customer`, `user_assigned_customers` con 2 elementos y `has_multiple_customers=True`, desplegando el selector interactivo. | Media |

---

## 28.3. Módulo 3: Pruebas del Visualizador de Documentación (Sphinx HTML)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-DOC-001** | Acceso a la página principal de Documentación Técnica | Servidor web activo con documentación Sphinx compilada en `docs/sphinx/build/html/`. | 1. Enviar solicitud `GET /docs/` o `GET /docs/index.html`. | Respuesta **`HTTP 200 OK`**, cabecera `Content-Type: text/html` y cuerpo con el índice navegable de Sphinx. | Alta |
| **CPR-DOC-002** | Servido de recursos estáticos asociados (CSS, JS, imágenes) | La página principal de Sphinx referencia `_static/css/theme.css` y `_static/js/theme.js`. | 1. Enviar solicitud `GET /docs/_static/css/theme.css`.<br>2. Enviar solicitud `GET /docs/_static/js/theme.js`. | Respuestas **`HTTP 200 OK`** con cabeceras `Content-Type: text/css` y `application/javascript` respectivamente. | Alta |
| **CPR-DOC-003** | Prevención de ataques de Directory Traversal | Servidor ejecutando `ServeSphinxDocsView`. | 1. Enviar solicitud maliciosa `GET /docs/../../../../etc/passwd` o `GET /docs/..%2F..%2Fsettings.py`. | El validador de rutas normaliza el path y bloquea el escape del directorio base, retornando **`HTTP 404 Not Found`** o **`HTTP 403 Forbidden`**. | Crítica |
| **CPR-DOC-004** | Manejo de archivo inexistente en documentación | Documentación compilada. | 1. Enviar solicitud `GET /docs/modulo_inexistente.html`. | El controlador captura `FileNotFoundError` y devuelve una respuesta limpia **`HTTP 404 Not Found`**. | Media |
| **CPR-DOC-005** | Presencia y navegación del enlace en Menú Principal | Usuario visualiza cualquier página basada en `templates/base.html`. | 1. Inspeccionar la barra de navegación.<br>2. Hacer clic en el enlace "Documentación Técnica". | El enlace a `/docs/` está visible, estilizado acorde a la paleta institucional y redirige exitosamente a la documentación. | Media |
| **CPR-DOC-006** | Control de acceso por roles (Auditor / Administrador) | Vista de documentación configurada con restricción de acceso. | 1. Usuario anónimo intenta acceder a `/docs/`.<br>2. Usuario con rol autorizado accede a `/docs/`. | El usuario anónimo es redirigido a login OIDC; el usuario autorizado accede transparentemente a la documentación. | Alta |

