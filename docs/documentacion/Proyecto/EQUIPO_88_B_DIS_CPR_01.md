# Detalle de la Infraestructura de Producción — EQUIPO 88 B DIS CPR 01

> Última actualización: Hito 5 (SCRUM-85) — incorpora los casos de prueba para Entidades Financieras (CPR-ENT), Medios de Cobro (CPR-REC), Límites Operativos (CPR-LIM), Filtros de Formato de Moneda (CPR-FLT), Transacciones Cambiarias y Orquestación (CPR-TXN), Expiración y Cancelación (CPR-EXP), Comprobante de Transacción (CPR-RCP) y Sembrado Idempotente (CPR-SED), derivados de RF-32 a RF-38 y RN-19 a RN-26 de la ERS v3.3.

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

> **Alcance:** este documento conserva la terminología y los elementos visibles en el PDF inicial e incorpora formalmente la especificación y matriz de casos de prueba del sistema conforme a los requerimientos del Sprint 2 (SCRUM-42) y del SCRUM 57 (rates, comisiones, cotizador y payments).

---

# 28. MATRIZ FORMAL DE CASOS DE PRUEBA DE SOFTWARE (DIS_CPR_01)

Esta sección consolida la **Matriz de Casos de Prueba (CPR)** para las funcionalidades críticas del sistema: la entidad intermedia de multi-representación `CustomerUserAssignment`, las reglas de negocio para la gestión y cambio dinámico de Cliente Activo en sesión, las pruebas del Visualizador de Documentación Técnica integrada (Sphinx), y los módulos de `rates` (monedas, tasas, comisiones, cotizador) y `payments` (medios de pago).

| Entorno | Configuración |
|---|---|
| Framework | Django TestCase y cliente de pruebas Django |
| Datos | Monedas USD y PYG activas, cliente con segmento MIN o VIP; usuario autenticado cuando la interfaz lo exige |
| Precisión | `Decimal`; USD con 2 decimales y PYG con 0 decimales cuando corresponda |
| Rutas base | `/rates/` y `/payments/` |

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

---

## 28.4. Módulo 4: Pruebas de Monedas y Tasas de Cambio (`rates`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-RAT-001** | Crear moneda válida | Usuario autenticado; código no existente | Crear USD con 2 decimales | Se persiste con código USD y estado activo | Alta |
| **CPR-RAT-002** | Normalizar código ISO | No existe moneda `usd` | Guardar código con espacios y minúsculas | Se almacena `USD` | Alta |
| **CPR-RAT-003** | Rechazar código ISO inválido | Ninguna | Crear código con menos, más de 3 caracteres o dígitos | Error de validación; no se persiste | Alta |
| **CPR-RAT-004** | Rechazar precisión fuera de rango | Moneda en creación | Informar decimales menor a 0 o mayor a 10 | Error de validación | Media |
| **CPR-RAT-005** | Crear tasa y calcular spread | USD y PYG activas | Crear USD/PYG con compra 7000 y venta 7100 | Spread guardado igual a 100 | Crítica |
| **CPR-RAT-006** | Rechazar par idéntico | USD activa | Crear USD/USD | Error en moneda destino | Alta |
| **CPR-RAT-007** | Rechazar tasa no positiva | Par USD/PYG | Informar compra o venta cero o negativa | Error de validación | Alta |
| **CPR-RAT-008** | Rechazar venta menor que compra | Par USD/PYG | Informar compra 7100 y venta 7000 | Error en venta; no se persiste | Crítica |
| **CPR-RAT-009** | Validar vigencia cronológica | Par USD/PYG | Informar `valid_to` anterior o igual a `valid_from` | Error de validación | Alta |
| **CPR-RAT-010** | Evaluar tasa vigente | Tasa activa con periodo actual | Consultar `is_current` | Retorna verdadero; una inactiva, futura o vencida retorna falso | Alta |
| **CPR-RAT-011** | Seleccionar tasa por operación | Tasa compra 7000, venta 7100 | Solicitar BUY y SELL | BUY devuelve 7100; SELL devuelve 7000 | Alta |
| **CPR-RAT-012** | Consultar historial por periodo | Varias tasas del mismo par | Llamar `/rates/api/history/` con par y periodo válidos | JSON contiene solo registros del periodo solicitado | Media |
| **CPR-RAT-013** | Rechazar parámetros de historial inválidos | Usuario autenticado | Enviar par o periodo inválido | Respuesta 400; no se exponen datos inconsistentes | Media |

---

## 28.5. Módulo 5: Pruebas de Comisiones por Segmento (`rates.SegmentCommission`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-COM-001** | Crear regla por segmento | Segmento MIN sin regla | Crear regla 1.5%, cargo 1000, descuento 10% | Registro activo persistido | Alta |
| **CPR-COM-002** | Impedir segmento duplicado | Existe regla MIN | Intentar crear otra regla MIN | Error de unicidad | Crítica |
| **CPR-COM-003** | Validar porcentaje de comisión | Segmento disponible | Informar -0.01 o 100.01 | Error de validación | Alta |
| **CPR-COM-004** | Validar cargo fijo | Segmento disponible | Informar cargo fijo negativo | Error de validación | Alta |
| **CPR-COM-005** | Validar descuento de spread | Segmento disponible | Informar descuento fuera de 0 a 100 | Error de validación | Alta |
| **CPR-COM-006** | Calcular comisión activa | Regla 1.5% y fijo 1000 | Calcular sobre 100000 | Resultado 2500 | Alta |
| **CPR-COM-007** | Regla inactiva | Regla inactiva | Calcular sobre monto positivo | Resultado 0; no aplica descuento | Alta |
| **CPR-COM-008** | Aplicar descuento de spread | Spread 100 y descuento 10% | Ejecutar método de descuento | Spread efectivo 90 | Media |
| **CPR-COM-009** | API de lista de comisiones | Existen reglas | GET `/rates/api/commissions/` | JSON con reglas disponibles | Media |
| **CPR-COM-010** | API de detalle inexistente | Segmento sin regla | GET detalle con código inexistente | Respuesta 404 | Media |

---

## 28.6. Módulo 6: Pruebas del Cotizador (`rates.RateCalculationService`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-COT-001** | Cotizar compra minorista | Tasa USD/PYG vigente; cliente MIN | Cotizar BUY por 100 USD | Retorna tasa de venta, importes brutos, comisión y total a pagar | Crítica |
| **CPR-COT-002** | Cotizar venta VIP con bonificación | Tasa vigente; regla VIP con descuento | Cotizar SELL por 100 USD | Tasa efectiva superior a compra; monto neto descuenta comisión | Crítica |
| **CPR-COT-003** | Cotizar monto en moneda destino | Tasa vigente | Enviar `is_source_base=false` y monto PYG | Calcula base mediante división y respeta precisión de ambas monedas | Alta |
| **CPR-COT-004** | Regla neutral sin configuración | Segmento sin regla activa | Cotizar monto positivo | Comisión y descuento son cero; cotización se completa | Alta |
| **CPR-COT-005** | Rechazar operación inválida | Tasa vigente | Enviar tipo distinto de BUY o SELL | Respuesta 400 con error de parámetro | Alta |
| **CPR-COT-006** | Rechazar monto cero o negativo | Tasa vigente | Enviar 0 o monto negativo | Respuesta 400; no se genera resultado | Alta |
| **CPR-COT-007** | Tasa no encontrada | No hay tasa activa para el par | Solicitar cotización | Respuesta 404 o error controlado de tasa no disponible | Alta |
| **CPR-COT-008** | API por GET | Datos válidos | GET `/rates/api/calculate/` con parámetros | Respuesta 200 JSON y estructura completa | Alta |
| **CPR-COT-009** | API por POST JSON | Datos válidos | POST JSON a la API | Respuesta 200 JSON y valores equivalentes al GET | Alta |
| **CPR-COT-010** | JSON inválido | API disponible | POST con cuerpo no JSON y sin parámetros alternativos | Respuesta 404 controlada por falta de cotización; no hay error de servidor ni efectos persistentes | Media |
| **CPR-COT-011** | Formulario web válido | Usuario autenticado y tasa vigente | POST `/rates/calculator/` | Renderiza resultado de cotización | Media |
| **CPR-COT-012** | Formulario web inválido | Usuario autenticado | POST con campos inválidos | Renderiza errores y conserva el formulario | Media |

---

## 28.7. Módulo 7: Pruebas de Medios de Pago (`payments`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-PAY-001** | Crear primer medio | Cliente activo sin medios | Registrar transferencia válida | Se crea activa y predeterminada | Alta |
| **CPR-PAY-002** | Crear medio adicional | Cliente con predeterminado | Registrar segunda billetera | Se crea sin quitar preferencia al anterior, salvo selección explícita | Alta |
| **CPR-PAY-003** | Exclusividad de predeterminado | Cliente con dos medios | Marcar el segundo como predeterminado | El primero pierde la marca en una operación atómica | Crítica |
| **CPR-PAY-004** | Impedir predeterminado inactivo | Medio inactivo | Crear o editar con ambas banderas | Error de validación | Alta |
| **CPR-PAY-005** | Desactivar predeterminado | Medio predeterminado activo | POST de cambio de estado | Queda inactivo y deja de ser predeterminado | Alta |
| **CPR-PAY-006** | Aislamiento de listado | Dos clientes con medios distintos | Consultar listado con cliente A activo | Solo se muestran medios de A | Crítica |
| **CPR-PAY-007** | Proteger edición IDOR | Cliente A activo; medio de B | Solicitar URL de edición del medio B | Rechazo o 404; no se modifica B | Crítica |
| **CPR-PAY-008** | Proteger eliminación IDOR | Cliente A activo; medio de B | Solicitar URL de eliminación del medio B | Rechazo o 404; no se elimina B | Crítica |
| **CPR-PAY-009** | API crear medio | Cliente activo | POST JSON válido a `/payments/api/` | Respuesta 201 con medio asociado al cliente activo | Alta |
| **CPR-PAY-010** | API actualizar y eliminar | Medio propio existente | PUT/PATCH y luego DELETE al detalle | Respuestas 200 y eliminación confirmada | Alta |
| **CPR-PAY-011** | Validar campos de titularidad | Cliente activo | Enviar entidad, cuenta o titular vacíos | Respuesta 400 con errores de campo | Media |

---

## 28.8. Módulo 8: Pruebas de Entidades Financieras (`payments.EntidadFinanciera`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-ENT-001** | Crear entidad financiera válida | Catálogo abierto | Crear entidad con nombre "Banco Continental", código "CONTINENTAL", tipo "BANCO", RUC válido y activo | Registro persistido correctamente con campos obligatorios | Alta |
| **CPR-ENT-002** | Impedir código duplicado | Existe entidad con código "ITAU" | Intentar registrar otra entidad con código "ITAU" | Error de integridad/unicidad en campo `code` | Crítica |
| **CPR-ENT-003** | Validar tipo de entidad permitido | Catálogo disponible | Intentar registrar con tipo no listado en opciones (`BANCO`, `FINANCIERA`, `COOPERATIVA`, `BILLETERA`, `OTRO`) | Rechazo por validación de opciones (choices) | Alta |
| **CPR-ENT-004** | Filtrado de entidades activas | Existen entidades activas e inactivas | Consultar selector de entidades para medios de pago o cobro | Solo se listan aquellas con `is_active=True` | Alta |
| **CPR-ENT-005** | Desactivación lógica de entidad | Entidad vinculada a medios de pago | Marcar entidad como inactiva | La entidad permanece para integridad histórica pero se excluye de nuevos registros | Media |

---

## 28.9. Módulo 9: Pruebas de Medios de Cobro / Recepción (`payments.ReceivingMethod`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-REC-001** | Crear primer medio de cobro | Cliente activo sin medios de cobro | Registrar cuenta bancaria con entidad financiera, número y titular | Registro creado activo y marcado como predeterminado automáticamente | Alta |
| **CPR-REC-002** | Crear segundo medio de cobro | Cliente con un medio predeterminado | Registrar billetera electrónica sin tildar predeterminado | Se crea activo sin desplazar al predeterminado existente | Alta |
| **CPR-REC-003** | Exclusividad atómica de predeterminado | Cliente con dos medios de cobro | Marcar el segundo medio como predeterminado | El segundo queda predeterminado y el primero pierde la marca atómicamente | Crítica |
| **CPR-REC-004** | Impedir predeterminado inactivo | Medio de cobro inactivo | Intentar guardar con `is_active=False` e `is_default=True` | Error de validación; no se permite predeterminado inactivo | Alta |
| **CPR-REC-005** | Desactivar medio predeterminado | Medio de cobro predeterminado activo | Desactivar mediante formulario o vista de toggle | Queda inactivo y se desmarca de predeterminado | Alta |
| **CPR-REC-006** | Aislamiento de listado de cobro | Clientes A y B con cuentas registradas | Acceder a `/payments/receiving-methods/` con cliente A activo | Solo se listan los medios de cobro pertenecientes al cliente A | Crítica |
| **CPR-REC-007** | Proteger edición IDOR de medio de cobro | Cliente A activo; medio de cobro de B | Enviar POST de actualización a la URL del medio de B | Respuesta 404 o 403; los datos del cliente B no sufren modificaciones | Crítica |
| **CPR-REC-008** | Proteger eliminación IDOR de medio de cobro | Cliente A activo; medio de cobro de B | Solicitar eliminación o borrado del medio de B | Rechazo con 404/403; registro de B intacto | Crítica |
| **CPR-REC-009** | Validación de formularios especializados | Cliente activo | Enviar `BankTransferForm` o `DigitalWalletForm` con datos requeridos incompletos | Errores de validación en campos específicos y formulario no procesado | Media |

---

## 28.10. Módulo 10: Pruebas de Límites Operativos (`rates.OperationLimit` y `OperationLimitValidationService`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-LIM-001** | Crear límite operativo válido | Parámetros del sistema | Crear límite para segmento MIN y moneda USD con mín 10.00, máx 5000.00 y límite diario 15000.00 | Registro persistido correctamente | Alta |
| **CPR-LIM-002** | Impedir mínimo mayor a máximo | Parámetros del sistema | Intentar crear límite con `min_amount = 1000.00` y `max_amount = 500.00` | Error de validación de modelo/formulario | Crítica |
| **CPR-LIM-003** | Unicidad por segmento y divisa | Existe límite MIN en USD | Intentar registrar otro límite para segmento MIN y divisa USD | Error de restricción única (`unique_together`) | Alta |
| **CPR-LIM-004** | Validar monto dentro de límites | Límite MIN USD [10, 5000] | Validar monto de 500 USD mediante `OperationLimitValidationService` | Validación exitosa, operación autorizada | Alta |
| **CPR-LIM-005** | Rechazar monto inferior al mínimo | Límite MIN USD [10, 5000] | Validar monto de 5 USD | Retorna `is_valid=False` con mensaje claro de monto inferior al mínimo | Crítica |
| **CPR-LIM-006** | Rechazar monto superior al máximo | Límite MIN USD [10, 5000] | Validar monto de 6000 USD | Retorna `is_valid=False` con mensaje indicando superación del tope permitido | Crítica |
| **CPR-LIM-007** | Fallback sin límite configurado | Segmento o moneda sin regla registrada | Validar monto positivo en divisa no restringida | Operación admitida por defecto o sujeta a tope global de plataforma | Media |

---

## 28.11. Módulo 11: Pruebas de Filtros de Formato de Moneda (`rates.templatetags.currency_filters`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-FLT-001** | Formato de guaraníes (PYG) | Valor numérico o Decimal `1500000` | Aplicar filtro `currency_format:'PYG'` | Retorna `"1.500.000"` sin decimales y con separador de miles | Alta |
| **CPR-FLT-002** | Formato de divisa con decimales (USD) | Valor Decimal `1234.5` | Aplicar filtro `currency_format:'USD'` | Retorna `"1.234,50"` o formato estándar con dos cifras decimales | Alta |
| **CPR-FLT-003** | Formato de tipo de cambio | Tasa Decimal `7450.2500` | Aplicar filtro `exchange_rate_format` | Retorna formato amigable respetando precisión requerida | Media |
| **CPR-FLT-004** | Formato de porcentaje | Valor Decimal `1.50` | Aplicar filtro `percentage_format` | Retorna `"1,50%"` | Media |
| **CPR-FLT-005** | Manejo de valores vacíos o nulos | Valor `None` o cadena vacía | Aplicar filtros de formato de moneda | Retorna `"-"` o string vacío sin generar excepciones 500 | Media |

---

## 28.12. Módulo 12: Pruebas de Transacciones Cambiarias y Orquestación (`transactions.Transaction` y `TransactionService`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-TXN-001** | Crear orden de compra (COMPRA) | Cliente activo con medios válidos; tasa USD/PYG vigente | Ejecutar `TransactionService.create_transaction_order` para COMPRA de 100 USD | Transacción persistida en estado `PENDIENTE`, montos y comisión congelados, `quote_expires_at` fijado a `now + 5 min` | Crítica |
| **CPR-TXN-002** | Crear orden de venta (VENTA) | Cliente activo; tasa vigente | Solicitar VENTA de 200 USD acreditando en cuenta bancaria | Transacción persistida en estado `PENDIENTE` con desglose exacto de cambio y comisión | Crítica |
| **CPR-TXN-003** | Confirmar transacción vigente | Transacción `PENDIENTE` dentro de los 5 minutos | Invocar `TransactionService.confirm_transaction(tx, user)` | Estado cambia a `CONFIRMADA`, se sella `confirmed_at` con timestamp actual | Crítica |
| **CPR-TXN-004** | Impedir re-confirmación | Transacción ya en estado `CONFIRMADA` | Intentar ejecutar nuevamente confirmación | Error de validación o excepción; estado y timestamps permanecen inmutables | Alta |
| **CPR-TXN-005** | Validar pertenencia de medios | Cliente A activo | Intentar crear transacción vinculando `PaymentMethod` perteneciente a cliente B | Error de validación en formulario o servicio; orden rechazada | Crítica |
| **CPR-TXN-006** | Formulario `TransactionOrderForm` | Datos de prueba válidos | Instanciar formulario con cliente activo y datos completos | Formulario válido; los QuerySets de medios de pago y cobro se restringen al cliente activo | Alta |
| **CPR-TXN-007** | Listado de transacciones paginado | Cliente A con 15 transacciones | Acceder a `/transactions/` autenticado con cliente A | Listado muestra solo transacciones de A, con paginación y filtros operativos | Alta |
| **CPR-TXN-008** | Detalle de transacción propio | Transacción perteneciente a cliente A | Acceder a `/transactions/<pk>/` con cliente A activo | Respuesta 200 con visualización completa del detalle y trazabilidad | Alta |
| **CPR-TXN-009** | Proteger detalle IDOR | Transacción perteneciente a cliente B | Intentar acceder a `/transactions/<pk_B>/` con cliente A activo | Respuesta 404 Not Found; se evita fuga de información | Crítica |
| **CPR-TXN-010** | API REST crear orden de transacción | Cliente activo autenticado | Enviar POST JSON a `/transactions/api/create/` con payload válido | Respuesta 201 Created con UUID de la transacción, estado `PENDIENTE` y vigencia | Alta |
| **CPR-TXN-011** | Exactitud decimal financiera | Tasa y comisiones con múltiples decimales | Calcular y persistir transacción | Montos finales calculados con objetos `Decimal`, sin imprecisión de punto flotante | Crítica |

---

## 28.13. Módulo 13: Pruebas de Expiración a 5 Minutos y Cancelación (`transactions` y `QuoteFreezeService`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-EXP-001** | Ventana de cotización congelada | Orden creada | Verificar `quote_expires_at` respecto a `created_at` | La diferencia temporal es exactamente de 300 segundos (5 minutos) | Alta |
| **CPR-EXP-002** | Rechazo de confirmación por expiración | Transacción `PENDIENTE` con `quote_expires_at` vencido | Intentar confirmar mediante servicio o vista web | Transacción pasa automáticamente a estado `EXPIRADA`; se rechaza la confirmación con mensaje descriptivo | Crítica |
| **CPR-EXP-003** | Cancelación voluntaria de orden | Transacción `PENDIENTE` | POST a `/transactions/<pk>/cancel/` indicando motivo | Estado transiciona a `CANCELADA`, registrando usuario que cancela y motivo | Alta |
| **CPR-EXP-004** | API REST cancelar orden | Transacción `PENDIENTE` del cliente activo | Enviar POST JSON a `/transactions/api/<pk>/cancel/` con motivo | Respuesta 200 OK con confirmación de estado `CANCELADA` | Alta |
| **CPR-EXP-005** | Impedir cancelación de transacción confirmada | Transacción en estado `CONFIRMADA` | Intentar cancelar mediante servicio o API | Rechazo de operación; las transacciones liquidadas no pueden anularse arbitrariamente | Crítica |
| **CPR-EXP-006** | Cuenta regresiva en pantalla de confirmación | Transacción `PENDIENTE` | Renderizar `TransactionConfirmView` | Template incluye script y elemento de cuenta regresiva sincronizado con `quote_expires_at` | Media |

---

## 28.14. Módulo 14: Pruebas de Comprobante de Transacción (`TransactionReceiptView`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-RCP-001** | Emisión de comprobante confirmado | Transacción en estado `CONFIRMADA` | Acceder a `/transactions/<pk>/receipt/` | Respuesta 200 con comprobante oficial conteniendo código de transacción, importes, tasas y datos fiscales | Alta |
| **CPR-RCP-002** | Denegar comprobante en orden no confirmada | Transacción en estado `PENDIENTE` o `CANCELADA` | Intentar acceder a la URL del comprobante | Redirección o error 400/404 informando que no existe comprobante disponible para órdenes no liquidadas | Alta |
| **CPR-RCP-003** | Aislamiento IDOR de comprobante | Transacción confirmada de cliente B | Intentar acceder al comprobante con cliente A activo | Respuesta 404 Not Found; denegación estricta de comprobantes ajenos | Crítica |
| **CPR-RCP-004** | Formato de impresión amigable | Vista de comprobante | Evaluar hoja de estilos de impresión en template | Dispone de reglas `@media print` para ocultar botones de navegación y optimizar impresión/PDF | Media |

---

## 28.15. Módulo 15: Pruebas de Comando de Sembrado Idempotente (`customers.seed_data`)

| ID Caso | Nombre del Caso de Prueba | Precondiciones | Pasos de Ejecución | Resultado Esperado | Prioridad |
|---|---|---|---|---|:---:|
| **CPR-SED-001** | Ejecución inicial de sembrado | Base de datos limpia o inicializada | Ejecutar `python manage.py seed_data` | Catálogos de monedas (`USD`, `EUR`, `BRL`, `ARS`, `PYG`), bancos, tasas, comisiones, límites y clientes creados exitosamente | Alta |
| **CPR-SED-002** | Idempotencia en ejecuciones sucesivas | Base de datos ya sembrada | Ejecutar `python manage.py seed_data` por segunda vez | Comando finaliza sin errores, actualiza o mantiene registros sin generar duplicados | Crítica |
| **CPR-SED-003** | Verificación de límites y asignaciones sembradas | Post-ejecución de sembrado | Consultar instancias de `OperationLimit` y `CustomerUserAssignment` | Existen límites válidos para cada segmento y los usuarios de prueba tienen clientes asignados | Alta |

---

## 29. Criterios de Aprobación

- Todos los casos críticos y altos deben aprobar antes de integrar cada Sprint.
- Los cálculos deben comparar objetos `Decimal` o valores serializados equivalentes, sin tolerancias de punto flotante.
- Los casos de aislamiento deben ejecutarse con dos clientes y dos usuarios para demostrar que no hay fuga horizontal de datos.
- Las pruebas de API deben comprobar código HTTP, forma del JSON y ausencia de efectos persistentes en los escenarios de error.

