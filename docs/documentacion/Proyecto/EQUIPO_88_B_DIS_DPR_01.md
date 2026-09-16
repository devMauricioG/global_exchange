# Detalle del archivo PDF --- `EQUIPO_88_B_DIS_DPR_01.pdf`

## 1. Descripción general

El PDF contiene un diagrama de arquitectura de una aplicación web
orientada a una **capa de cliente/ventanilla**, un **servidor
web/frontend**, un **servidor de aplicación** y una **capa de servicios,
datos y API externa**.

El flujo principal representado es:

``` text
Cliente / Ventanilla
        ↓ HTTPS (Port 443)
Servidor Web / Frontend
        ↓ Unix Socket / HTTP (Port 8000)
Servidor de Aplicación
        ↓
Capa de Servicios, Datos y API Externa
```

La arquitectura incluye autenticación mediante **JWT/JWKS**, consultas
SQL sobre **PostgreSQL** y envío de facturas en formato XML hacia
servicios externos del **Gobierno / DNIT**.

------------------------------------------------------------------------

## 2. Componentes principales

### 2.1 Capa de Cliente / Ventanilla

Es la capa superior del diagrama y representa el punto de acceso
utilizado por el usuario.

Contiene:

**Navegador Web / Terminal Caja Presencial**

Este componente se comunica con el servidor web mediante:

``` text
HTTPS (Port 443)
```

Por lo tanto, el acceso del cliente hacia la aplicación se representa
mediante HTTPS utilizando el puerto estándar `443`.

------------------------------------------------------------------------

### 2.2 Servidor Web / Frontend

El diagrama identifica este componente como:

**Servidor Web / Frontend (Linux VPS)**

Dentro de esta capa se encuentra:

**Nginx Reverse Proxy**

Configurado mediante:

``` text
Port 443 - SSL/HTTPS
```

El Nginx Reverse Proxy recibe las solicitudes HTTPS provenientes de la
capa cliente y las deriva hacia el servidor de aplicación.

La comunicación hacia el servidor de aplicación se representa como:

``` text
Unix Socket / HTTP (Port 8000)
```

------------------------------------------------------------------------

### 2.3 Servidor de Aplicación

Esta capa contiene el componente principal de ejecución de la
aplicación:

**Gunicorn WSGI + Django Core**

El diagrama identifica específicamente:

``` text
(GlobalExchange.wsgi)
```

Por lo tanto, el servidor de aplicación está compuesto por:

-   Gunicorn
-   Interfaz WSGI
-   Django Core
-   `GlobalExchange.wsgi`

Su función dentro de la arquitectura es procesar las solicitudes
provenientes del frontend/reverse proxy y coordinar las operaciones con
los servicios, datos y APIs externas.

------------------------------------------------------------------------

## 3. Comunicaciones desde el servidor de aplicación

Desde **Gunicorn WSGI + Django Core** salen tres flujos principales.

### 3.1 Validación JWT / JWKS

El primer flujo está identificado como:

``` text
1. Valida JWT / JWKS
   (HTTPS)
```

Este flujo se dirige hacia la capa de servicios, datos y API externa,
donde se encuentra:

**Servidor IAM Dedicado (Keycloak - OIDC / JWKS)**

La arquitectura, por tanto, contempla un mecanismo de validación de
tokens JWT utilizando información JWKS y un servidor IAM dedicado basado
en Keycloak.

------------------------------------------------------------------------

### 3.2 Consultas SQL

El segundo flujo está identificado como:

``` text
2. Consultas SQL (Port 5432)
```

Este flujo se dirige hacia:

**Base de Datos (PostgreSQL Prod DB)**

La comunicación utiliza el puerto:

``` text
5432
```

El diagrama identifica explícitamente la base de datos como una
instancia de:

``` text
PostgreSQL Prod DB
```

------------------------------------------------------------------------

### 3.3 Envío XML de facturas

El tercer flujo está identificado como:

``` text
3. Envío XML Facturas
   (HTTPS)
```

Este flujo se dirige hacia:

**Gobierno / DNIT**

El componente externo se describe como:

``` text
API SIFEN - XML Web Services
```

Por lo tanto, el servidor de aplicación envía las facturas en formato
XML mediante HTTPS hacia los servicios web de la API SIFEN del Gobierno
/ DNIT.

------------------------------------------------------------------------

## 4. Capa de Servicios, Datos y API Externa

Esta capa concentra tres componentes principales:

1.  **Servidor IAM Dedicado**
2.  **Base de Datos**
3.  **Gobierno / DNIT**

### 4.1 Servidor IAM Dedicado

Identificación en el diagrama:

``` text
Servidor IAM Dedicado
(Keycloak - OIDC / JWKS)
```

Su función dentro de la arquitectura está asociada con la
autenticación/autorización y la validación de tokens mediante JWT/JWKS.

El servidor de aplicación realiza el flujo:

``` text
Gunicorn WSGI + Django Core
        ↓
Valida JWT / JWKS (HTTPS)
        ↓
Keycloak - OIDC / JWKS
```

------------------------------------------------------------------------

### 4.2 Base de Datos

El diagrama representa la base de datos mediante un componente
cilíndrico:

``` text
Base de Datos
(PostgreSQL Prod DB)
```

El servidor de aplicación realiza consultas SQL utilizando:

``` text
Port 5432
```

Flujo:

``` text
Gunicorn WSGI + Django Core
        ↓
Consultas SQL (Port 5432)
        ↓
PostgreSQL Prod DB
```

------------------------------------------------------------------------

### 4.3 Gobierno / DNIT

El componente externo está identificado como:

``` text
Gobierno / DNIT
(API SIFEN - XML Web Services)
```

La aplicación utiliza este servicio para el:

``` text
Envío XML Facturas (HTTPS)
```

Flujo:

``` text
Gunicorn WSGI + Django Core
        ↓
Envío XML Facturas (HTTPS)
        ↓
Gobierno / DNIT
API SIFEN - XML Web Services
```

------------------------------------------------------------------------

## 5. Flujo completo de la arquitectura

El recorrido principal de una solicitud puede representarse de la
siguiente manera:

``` text
┌─────────────────────────────────────┐
│ Capa de Cliente / Ventanilla        │
│ Navegador Web / Terminal Caja       │
└──────────────────┬──────────────────┘
                   │
                   │ HTTPS (Port 443)
                   ▼
┌─────────────────────────────────────┐
│ Servidor Web / Frontend             │
│ Linux VPS                           │
│                                     │
│ Nginx Reverse Proxy                 │
│ Port 443 - SSL/HTTPS                │
└──────────────────┬──────────────────┘
                   │
                   │ Unix Socket / HTTP
                   │ Port 8000
                   ▼
┌─────────────────────────────────────┐
│ Servidor de Aplicación              │
│                                     │
│ Gunicorn WSGI + Django Core         │
│ (GlobalExchange.wsgi)               │
└───────────────┬─────────┬───────────┘
                │         │
       JWT/JWKS  │         │ SQL
        HTTPS    │         │ Port 5432
                ▼         ▼
       ┌────────────┐  ┌─────────────────┐
       │  Keycloak  │  │ PostgreSQL      │
       │ OIDC/JWKS  │  │ Prod DB         │
       └────────────┘  └─────────────────┘
                │
                │ HTTPS
                │ XML Facturas
                ▼
       ┌──────────────────────────────┐
       │ Gobierno / DNIT              │
       │ API SIFEN                    │
       │ XML Web Services              │
       └──────────────────────────────┘
```

------------------------------------------------------------------------

## 6. Puertos y protocolos

  -------------------------------------------------------------------------
  Componente /     Protocolo                       Puerto Uso indicado
  conexión                                                
  ---------------- ---------------- --------------------- -----------------
  Cliente → Nginx  HTTPS / SSL                      `443` Acceso web

  Nginx →          Unix Socket /                   `8000` Comunicación con
  Aplicación       HTTP                                   Gunicorn/Django

  Aplicación →     SQL                             `5432` Consultas a la
  PostgreSQL                                              base de datos

  Aplicación →     HTTPS            No especificado en el Validación
  Keycloak                                       diagrama JWT/JWKS

  Aplicación →     HTTPS            No especificado en el Envío XML de
  Gobierno/DNIT                                  diagrama facturas
  -------------------------------------------------------------------------

> El PDF no especifica un puerto para las conexiones HTTPS de Keycloak
> ni de Gobierno/DNIT.

------------------------------------------------------------------------

## 7. Tecnologías identificadas

El diagrama menciona explícitamente las siguientes tecnologías y
estándares:

### Frontend / servidor web

-   Linux VPS
-   Nginx
-   Reverse Proxy
-   SSL
-   HTTPS

### Servidor de aplicación

-   Gunicorn
-   WSGI
-   Django Core
-   `GlobalExchange.wsgi`

### Autenticación e identidad

-   Keycloak
-   OIDC
-   JWT
-   JWKS
-   HTTPS

### Base de datos

-   PostgreSQL
-   SQL
-   Puerto `5432`

### Facturación electrónica / servicios externos

-   Gobierno / DNIT
-   API SIFEN
-   XML Web Services
-   HTTPS

------------------------------------------------------------------------

## 8. Responsabilidades por capa

  -----------------------------------------------------------------------
  Capa                    Componente              Responsabilidad
                                                  representada
  ----------------------- ----------------------- -----------------------
  Cliente                 Navegador Web /         Acceso e interacción
                          Terminal Caja           con la aplicación
                          Presencial              

  Web                     Nginx Reverse Proxy     Recepción HTTPS y proxy
                                                  hacia la aplicación

  Aplicación              Gunicorn + Django Core  Procesamiento de la
                                                  lógica de aplicación

  IAM                     Keycloak                OIDC/JWKS y validación
                                                  JWT

  Datos                   PostgreSQL Prod DB      Persistencia y
                                                  consultas SQL

  API externa             Gobierno / DNIT         Servicios SIFEN para
                                                  envío de XML de
                                                  facturas
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 9. Flujo de autenticación

El esquema de autenticación representado es:

``` text
Cliente
   ↓
HTTPS
   ↓
Nginx
   ↓
Gunicorn + Django
   ↓
Valida JWT / JWKS
   ↓ HTTPS
Keycloak
(OIDC / JWKS)
```

El diagrama muestra específicamente que la aplicación valida los tokens
JWT mediante JWKS y que el servidor IAM dedicado utiliza Keycloak con
OIDC/JWKS.

------------------------------------------------------------------------

## 10. Flujo de acceso a datos

``` text
Cliente
   ↓
Nginx
   ↓
Gunicorn + Django
   ↓
Consultas SQL
   ↓
Port 5432
   ↓
PostgreSQL Prod DB
```

La base de datos se encuentra dentro de la capa denominada **Servicios,
Datos y API Externa**.

------------------------------------------------------------------------

## 11. Flujo de facturación electrónica

El flujo relacionado con las facturas es:

``` text
Cliente / Ventanilla
        ↓
Nginx
        ↓
Gunicorn + Django
        ↓
Envío XML Facturas
        ↓ HTTPS
Gobierno / DNIT
        ↓
API SIFEN - XML Web Services
```

El diagrama especifica que el intercambio con Gobierno/DNIT se realiza
mediante **HTTPS** y que el servicio externo corresponde a **API SIFEN -
XML Web Services**.

------------------------------------------------------------------------

## 12. Puntos de entrada y salida

### Entrada

El punto de entrada de la aplicación es:

``` text
Navegador Web / Terminal Caja Presencial
        ↓
HTTPS Port 443
        ↓
Nginx Reverse Proxy
```

### Procesamiento

El procesamiento se realiza mediante:

``` text
Gunicorn WSGI + Django Core
(GlobalExchange.wsgi)
```

### Salidas principales

La aplicación tiene tres destinos principales:

1.  **Keycloak** para validación JWT/JWKS.
2.  **PostgreSQL** para consultas SQL.
3.  **Gobierno/DNIT** para envío XML de facturas.

------------------------------------------------------------------------

## 13. Resumen ejecutivo

`EQUIPO_88_B_DIS_DPR_01.pdf` representa una arquitectura web de varias
capas.

El usuario accede mediante un **Navegador Web / Terminal Caja
Presencial** utilizando **HTTPS por el puerto 443**. Las solicitudes
llegan a un **Nginx Reverse Proxy** instalado en un **Linux VPS**, que
las deriva mediante **Unix Socket / HTTP por el puerto 8000** hacia un
servidor de aplicación compuesto por **Gunicorn WSGI + Django Core**,
utilizando `GlobalExchange.wsgi`.

La aplicación mantiene tres integraciones principales:

-   **Identidad:** validación de JWT/JWKS mediante un **Keycloak
    dedicado con OIDC/JWKS**.
-   **Datos:** consultas SQL contra una **base PostgreSQL de
    producción** mediante el puerto `5432`.
-   **Facturación:** envío de XML de facturas mediante HTTPS hacia
    **Gobierno / DNIT**, específicamente la **API SIFEN - XML Web
    Services**.

La arquitectura separa claramente la interfaz de usuario, el servidor
web, la lógica de aplicación, la identidad, la persistencia de datos y
la integración externa con los servicios gubernamentales.

------------------------------------------------------------------------

## 14. Información no especificada en el PDF

El diagrama no proporciona, entre otros, los siguientes datos:

-   Dirección IP o dominio del Linux VPS.
-   Nombre de dominio utilizado por Nginx.
-   Ruta concreta del Unix Socket.
-   Puerto HTTPS específico de Keycloak.
-   URL/endpoints de Keycloak.
-   Nombre de la base de datos PostgreSQL.
-   Usuario de conexión a PostgreSQL.
-   Credenciales.
-   Esquema o tablas de PostgreSQL.
-   Endpoint específico de SIFEN.
-   Métodos concretos de la API SIFEN.
-   Estructura del XML de factura.
-   Versiones de Django, Gunicorn, Nginx, PostgreSQL o Keycloak.
-   Detalles de firewall, balanceo, backups o alta disponibilidad.

Estos aspectos no deben inferirse únicamente a partir del contenido
visual del PDF.
