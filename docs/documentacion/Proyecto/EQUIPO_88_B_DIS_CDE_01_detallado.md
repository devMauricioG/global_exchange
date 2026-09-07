# Detalle de la arquitectura — EQUIPO 88 B DIS CDE 01

## 1. Descripción general

El PDF presenta un **diagrama de arquitectura de una estación de trabajo de desarrollo local** basada en Python/Django, con integración de:

- Un entorno de desarrollo local.
- Un servidor de desarrollo de Django.
- Un middleware de autenticación **django-oidc / Keycloak**.
- Un driver de PostgreSQL mediante **psycopg2**.
- Un servicio local de **PostgreSQL**.
- Una instancia local de **Keycloak IAM**, indicada como ejecutándose localmente o mediante Docker.
- Herramientas de desarrollo y prueba: **VS Code / PyCharm**, navegador web y Postman.

El flujo general puede resumirse como:

```text
IDE / Navegador / Postman
          |
          v
   Entorno virtual Python (venv)
          |
          v
   Django Development Server
       /           \
      v             v
Middleware OIDC   psycopg2
      |             |
      v             v
   Keycloak      PostgreSQL
```

---

## 2. Estación de Trabajo Desarrollador (PC Local)

La parte superior del diagrama representa la **estación de trabajo del desarrollador**.

### 2.1 IDE — VS Code / PyCharm

El desarrollador utiliza un IDE, indicado en el diagrama como:

- **VS Code**
- **PyCharm**

Su función principal es editar y mantener el código fuente de la aplicación.

El flujo señalado es:

```text
IDE
 |
 | Edita Código Fuente
 v
Django Dev Server
```

Esto representa el ciclo habitual de desarrollo local: el programador modifica el código fuente y el servidor de desarrollo de Django ejecuta la aplicación para poder probarla.

### 2.2 Navegador Web / Postman

El segundo componente de la estación de trabajo es:

- **Navegador Web**
- **Postman**

Estas herramientas actúan como clientes de la aplicación.

El diagrama indica el protocolo y dirección:

```text
HTTP / Localhost:8000
```

Por lo tanto, las solicitudes de prueba se realizan contra el servidor local de Django mediante HTTP y el puerto **8000**.

Ejemplo conceptual:

```text
Navegador / Postman
        |
        | HTTP
        v
localhost:8000
        |
        v
Servidor Django
```

---

## 3. Entorno Virtual Python — `venv`

Dentro de la estación de desarrollo aparece un:

**Entorno Virtual Python (venv)**

El `venv` permite aislar las dependencias Python utilizadas por el proyecto.

Dentro de este entorno se encuentra el servidor de desarrollo de Django y los componentes Python necesarios para que la aplicación funcione.

Conceptualmente:

```text
PC Local
└── Entorno Virtual Python (venv)
    ├── Django
    ├── django-oidc / Keycloak Middleware
    └── psycopg2
```

### Ventajas del `venv`

El uso de un entorno virtual permite:

1. Mantener separadas las dependencias del proyecto.
2. Evitar conflictos entre versiones de paquetes.
3. Instalar las librerías necesarias sin afectar otros proyectos Python.
4. Reproducir de manera más controlada el entorno de desarrollo.

---

# 4. Django Development Server

El componente central del diagrama es:

**Django Dev Server**

y se indica explícitamente el comando:

```bash
manage.py runserver
```

Este servidor recibe las solicitudes HTTP provenientes del navegador o Postman.

Flujo:

```text
Navegador / Postman
        |
        | HTTP / localhost:8000
        v
Django Dev Server
```

El servidor también se comunica con los otros componentes de la arquitectura.

Según el diagrama existen dos flujos principales:

```text
Django Dev Server
   |
   +----> Intercepta Requests
   |             |
   |             v
   |      django-oidc / Keycloak Middleware
   |
   +----> Consulta ORM
                 |
                 v
            psycopg2 DB Driver
```

---

# 5. Middleware `django-oidc / Keycloak`

El diagrama muestra un componente denominado:

**django-oidc / Keycloak Middleware**

Su función dentro de la arquitectura es interceptar las solicitudes antes de que continúen hacia la lógica correspondiente de la aplicación.

El flujo indicado es:

```text
Django Dev Server
        |
        | Intercepta Requests
        v
django-oidc / Keycloak Middleware
        |
        | Valida JWT / OIDC Local
        v
Keycloak IAM
```

## 5.1 Intercepción de solicitudes

La etiqueta:

**Intercepta Requests**

indica que el middleware participa en el procesamiento de las solicitudes HTTP recibidas por Django.

Su ubicación permite realizar controles relacionados con autenticación/autorización antes de continuar con el procesamiento de la aplicación.

## 5.2 Validación JWT / OIDC

El diagrama indica:

**Valida JWT / OIDC Local**

Esto significa que el mecanismo de autenticación utiliza conceptos de:

- **JWT (JSON Web Token)**
- **OIDC (OpenID Connect)**
- **Keycloak**

El diagrama específicamente representa una validación contra una instancia local de Keycloak.

---

# 6. Keycloak IAM

En la parte inferior aparece:

**Keycloak IAM (Instancia Local / Docker)**

Este componente representa el sistema de gestión de identidad y acceso utilizado en el entorno local.

La arquitectura lo conecta directamente con el middleware:

```text
django-oidc / Keycloak Middleware
              |
              | Valida JWT / OIDC Local
              v
       Keycloak IAM
```

La indicación:

```text
Instancia Local / Docker
```

muestra que Keycloak puede ejecutarse como una instancia local, incluyendo un escenario basado en Docker.

## 6.1 Rol dentro de la arquitectura

En el contexto del diagrama, Keycloak está asociado principalmente con:

- Autenticación.
- Gestión de identidad.
- Validación relacionada con OIDC.
- Emisión/validación de tokens utilizados por las solicitudes autenticadas.

---

# 7. ORM y acceso a base de datos

El segundo flujo importante que sale del servidor Django está identificado como:

**Consulta ORM**

El flujo es:

```text
Django Dev Server
        |
        | Consulta ORM
        v
psycopg2 DB Driver
        |
        | SQL / Port 5432
        v
PostgreSQL
```

## 7.1 ORM

ORM significa:

**Object-Relational Mapping**

Django utiliza su ORM para permitir que la aplicación trabaje con datos de la base de datos utilizando modelos y operaciones de Python.

El diagrama no especifica modelos concretos ni consultas concretas, por lo que no deben inferirse tablas o entidades adicionales a partir del documento.

---

# 8. `psycopg2` DB Driver

El diagrama muestra:

**psycopg2 DB Driver**

Este componente actúa como driver de conexión entre Django/Python y PostgreSQL.

Flujo:

```text
Django
  |
  | Consulta ORM
  v
psycopg2
  |
  | SQL / Port 5432
  v
PostgreSQL
```

## 8.1 Función

En términos de arquitectura, `psycopg2` permite que la aplicación Python establezca comunicación con PostgreSQL.

El flujo representado distingue dos niveles:

1. **ORM:** Django construye y gestiona las operaciones de acceso a datos.
2. **Driver:** `psycopg2` proporciona la comunicación Python ↔ PostgreSQL.

---

# 9. PostgreSQL — Servicio Local

La base de datos representada en el diagrama es:

**PostgreSQL (Servicio Local)**

Se encuentra en la parte inferior de la arquitectura.

La conexión desde `psycopg2` está indicada como:

```text
SQL / Port 5432
```

Por lo tanto, el diagrama establece que PostgreSQL utiliza el puerto:

```text
5432
```

## 9.1 Flujo de acceso

El flujo completo de datos es:

```text
Aplicación Django
       |
       | Consulta ORM
       v
    psycopg2
       |
       | SQL / TCP
       | Puerto 5432
       v
 PostgreSQL
```

---

# 10. Flujo completo de una solicitud

A partir del diagrama, se puede representar el recorrido principal de una solicitud de la siguiente manera:

```text
┌──────────────────────────────┐
│ Navegador Web / Postman      │
└──────────────┬───────────────┘
               │
               │ HTTP / localhost:8000
               v
┌──────────────────────────────┐
│ Django Development Server   │
│ manage.py runserver          │
└──────────────┬───────────────┘
               │
               │ Intercepta Requests
               v
┌──────────────────────────────┐
│ django-oidc / Keycloak       │
│ Middleware                   │
└──────────────┬───────────────┘
               │
               │ Valida JWT / OIDC Local
               v
┌──────────────────────────────┐
│ Keycloak IAM                 │
│ Instancia Local / Docker     │
└──────────────────────────────┘
```

Para las operaciones de persistencia:

```text
┌──────────────────────────────┐
│ Django Dev Server            │
└──────────────┬───────────────┘
               │
               │ Consulta ORM
               v
┌──────────────────────────────┐
│ psycopg2 DB Driver           │
└──────────────┬───────────────┘
               │
               │ SQL / Port 5432
               v
┌──────────────────────────────┐
│ PostgreSQL                   │
│ Servicio Local               │
└──────────────────────────────┘
```

---

# 11. Componentes y responsabilidades

| Componente | Función representada |
|---|---|
| VS Code / PyCharm | Edición del código fuente |
| Navegador Web | Cliente para probar la aplicación mediante HTTP |
| Postman | Cliente para realizar pruebas HTTP/API |
| Python `venv` | Aislamiento del entorno y dependencias Python |
| Django Dev Server | Ejecuta la aplicación durante el desarrollo y recibe solicitudes |
| `manage.py runserver` | Comando utilizado para iniciar el servidor de desarrollo |
| django-oidc / Keycloak Middleware | Intercepta solicitudes y participa en la validación de autenticación |
| Keycloak IAM | Gestión de identidad/autenticación mediante OIDC |
| Django ORM | Capa de acceso a datos utilizada por Django |
| psycopg2 | Driver para comunicación con PostgreSQL |
| PostgreSQL | Servicio local de base de datos |
| Puerto 8000 | Endpoint HTTP local indicado para Django |
| Puerto 5432 | Puerto indicado para PostgreSQL |

---

# 12. Protocolos, puertos y mecanismos mencionados

## HTTP

El diagrama muestra:

```text
HTTP / Localhost:8000
```

Esto corresponde al acceso de las herramientas de prueba hacia el servidor Django.

### Punto de acceso

```text
localhost:8000
```

---

## SQL

Entre `psycopg2` y PostgreSQL aparece:

```text
SQL / Port 5432
```

Esto representa el intercambio de operaciones SQL con el servidor PostgreSQL mediante el puerto indicado.

### Puerto

```text
5432
```

---

## JWT

El middleware muestra la operación:

```text
Valida JWT
```

JWT es el formato de token mencionado explícitamente en el diagrama para el flujo de autenticación.

---

## OIDC

El diagrama también indica:

```text
OIDC Local
```

OIDC (OpenID Connect) aparece asociado al middleware y a Keycloak.

---

# 13. Flujo de desarrollo

El escenario representado puede entenderse como un entorno de desarrollo completamente local.

### Paso 1 — Edición

El desarrollador modifica el código desde:

```text
VS Code / PyCharm
```

### Paso 2 — Ejecución

El proyecto Django se ejecuta utilizando:

```bash
python manage.py runserver
```

El diagrama identifica específicamente:

```text
manage.py runserver
```

### Paso 3 — Prueba HTTP

El desarrollador utiliza:

```text
Navegador Web / Postman
```

para enviar solicitudes a:

```text
localhost:8000
```

### Paso 4 — Autenticación

Las solicitudes pasan por:

```text
django-oidc / Keycloak Middleware
```

que participa en la validación:

```text
JWT / OIDC Local
```

contra:

```text
Keycloak IAM
```

### Paso 5 — Acceso a datos

Cuando la aplicación necesita consultar información persistida, el flujo representado es:

```text
Django ORM
    ↓
psycopg2
    ↓
SQL
    ↓
PostgreSQL :5432
```

---

# 14. Dependencias lógicas entre componentes

La arquitectura tiene dos subsistemas principales.

## 14.1 Subsistema de autenticación

```text
Cliente
   ↓
Django
   ↓
Middleware OIDC
   ↓
Keycloak
```

Su objetivo dentro del diagrama es controlar la parte relacionada con identidad/autenticación.

## 14.2 Subsistema de persistencia

```text
Django
   ↓
ORM
   ↓
psycopg2
   ↓
PostgreSQL
```

Su objetivo es permitir que la aplicación consulte y almacene información en la base de datos.

---

# 15. Vista conceptual completa

```text
                         PC LOCAL
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ┌─────────────────┐          ┌────────────────────────┐   │
│   │ VS Code /       │          │ Navegador / Postman    │   │
│   │ PyCharm         │          │                        │   │
│   └────────┬────────┘          └───────────┬────────────┘   │
│            │                               │                │
│            │ Edita código                  │ HTTP           │
│            │                               │ localhost:8000 │
│            v                               v                │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Python Virtual Environment             │   │
│   │                       (venv)                        │   │
│   │                                                     │   │
│   │       ┌─────────────────────────────────────┐       │   │
│   │       │ Django Dev Server                   │       │   │
│   │       │ manage.py runserver                 │       │   │
│   │       └──────────────┬──────────────────────┘       │   │
│   │                      │                              │   │
│   │          ┌───────────┴────────────┐                 │   │
│   │          │                        │                 │   │
│   │          v                        v                 │   │
│   │  ┌──────────────────┐    ┌──────────────────┐      │   │
│   │  │ django-oidc /    │    │ psycopg2         │      │   │
│   │  │ Keycloak         │    │ DB Driver        │      │   │
│   │  │ Middleware       │    └────────┬─────────┘      │   │
│   │  └────────┬─────────┘             │                │   │
│   └───────────┼───────────────────────┼────────────────┘   │
│               │                       │                    │
│               │ JWT / OIDC             │ SQL / 5432        │
│               v                       v                    │
│       ┌──────────────────┐    ┌──────────────────────┐    │
│       │ Keycloak IAM     │    │ PostgreSQL           │    │
│       │ Local / Docker   │    │ Servicio Local       │    │
│       └──────────────────┘    └──────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

# 16. Resumen de arquitectura

La arquitectura mostrada en el PDF corresponde a un **entorno local de desarrollo de una aplicación Django**.

Los elementos principales son:

1. **Desarrollo:** VS Code o PyCharm.
2. **Entorno Python:** `venv`.
3. **Servidor:** Django Development Server mediante `manage.py runserver`.
4. **Acceso:** navegador web o Postman.
5. **HTTP:** `localhost:8000`.
6. **Autenticación:** middleware `django-oidc / Keycloak`.
7. **Identidad:** Keycloak IAM local/Docker.
8. **Autenticación basada en tokens:** JWT/OIDC.
9. **Acceso a datos:** Django ORM.
10. **Driver de base de datos:** `psycopg2`.
11. **Base de datos:** PostgreSQL local.
12. **Puerto PostgreSQL:** `5432`.

## Flujo resumido

```text
DESARROLLADOR
     │
     ├── VS Code / PyCharm
     │
     ▼
CÓDIGO DJANGO
     │
     ▼
Python venv
     │
     ▼
Django Dev Server
     │
     ├───────────────► Middleware OIDC ─────► Keycloak
     │                       │
     │                       └── JWT / OIDC
     │
     └───────────────► Django ORM
                             │
                             ▼
                          psycopg2
                             │
                             └── SQL / 5432 ───► PostgreSQL
```

> **Nota:** Este documento describe únicamente los elementos y relaciones visibles en el PDF. El diagrama no proporciona detalles adicionales sobre modelos Django, tablas PostgreSQL, endpoints específicos, configuración de Keycloak, realms, clientes, scopes, secretos, credenciales ni código fuente.
