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

> **Alcance:** este documento conserva la terminología y los elementos visibles en el PDF. No se agregan puertos, dominios, certificados, endpoints, configuraciones de Gunicorn/Nginx, parámetros de PostgreSQL, detalles internos de Keycloak ni reglas de negocio que no estén representados explícitamente en el diagrama.
