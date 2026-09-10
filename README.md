# Global Exchange

Plataforma de gestión de transacciones. Este repositorio contiene el servicio backend construido en **Django**, integrado con autenticación vía **Keycloak** y persistencia de datos en **PostgreSQL** mediante **Docker Compose**.

---

## 📋 Prerrequisitos del Sistema

Asegúrate de tener instalados los siguientes componentes antes de iniciar:

* **Docker Desktop** (con soporte para WSL2 en Windows) y en ejecución.
* **Git**
* **Python 3.12+** (opcional, solo requerido si ejecutas el proyecto localmente sin Docker).

---

## 🚀 Cómo Levantar el Sistema con Docker Compose (Recomendado)

Sigue estos pasos para inicializar el proyecto en tu entorno local:

### 1. Clonar el repositorio y entrar al directorio
```bash
git clone <url-del-repositorio>
cd global_exchange
```

### 2. Configurar las variables de entorno
Crea tu archivo `.env` a partir de la plantilla proporcionada:

* **En Linux / macOS / Git Bash:**
  ```bash
  cp .env.example .env
  ```
* **En Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
* **En Windows (CMD):**
  ```cmd
  copy .env.example .env
  ```

> [!NOTE]
> Revisa el archivo `.env` generado para ajustar cualquier credencial personalizada si es necesario. Los valores por defecto funcionan directamente con Docker Compose.

### 3. Iniciar Docker Desktop
Asegúrate de que la aplicación **Docker Desktop** esté abierta y con el motor de Docker en ejecución.

### 4. Construir y levantar los contenedores
Ejecuta el siguiente comando para descargar las imágenes, construir el backend y levantar los servicios en segundo plano:

```bash
docker compose up --build -d
```

### 5. Aplicar las migraciones de la base de datos
Una vez que los contenedores estén activos y la base de datos esté saludable, corre las migraciones de Django:

```bash
docker compose exec web python manage.py migrate
```

### 6. Crear un superusuario de Django (Opcional)
Para acceder al panel de administración de Django:

```bash
docker compose exec web python manage.py createsuperuser
```

---

## 💻 Opción Alternativa: Levantar Localmente (Sin Docker)

Si prefieres ejecutar Django directamente en tu máquina host:

1. **Crear y activar el entorno virtual:**
   * *Windows (PowerShell):*
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * *Linux / macOS:*
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

2. **Instalar dependencias:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configurar base de datos en `.env`:**
   Asegúrate de tener un servidor PostgreSQL local en ejecución y que `DB_HOST`, `DB_USER` y `DB_PASSWORD` en tu `.env` coincidan con tus credenciales locales.

4. **Ejecutar migraciones y arrancar el servidor:**
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

---

## 🌐 Puertos y Servicios Disponibles

| Servicio | URL / Host | Credenciales por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| **Django API / Admin** | [http://localhost:8000](http://localhost:8000) / [http://localhost:8000/admin](http://localhost:8000/admin) | *(El superusuario que crees)* | Backend principal |
| **Keycloak Admin** | [http://localhost:8080](http://localhost:8080) | `admin` / `admin` | Servidor de identidad y acceso (IAM) |
| **Mailpit (SMTP Dev)** | [http://localhost:8025](http://localhost:8025) (Web) / `1025` (SMTP) | *(Sin autenticación)* | Servidor de correos simulados en desarrollo |
| **PostgreSQL** | `localhost:5432` | `postgres` / `postgres` (BDs: `global_exchange_db`, `keycloak_db`) | Base de datos relacional |

---

## 🧪 Ejecución de Pruebas Unitarias y Cobertura (Testing & Coverage)

El proyecto cuenta con suites de pruebas unitarias y de integración que cubren los módulos de autenticación (`authentication`), roles dinámicos, gestión y validación de clientes (`customers`).

Las pruebas utilizan la configuración optimizada e in-memory SQLite (`config.settings.test`), que aísla la ejecución, agiliza los tests y previene modificaciones en las bases de datos de desarrollo o producción.

### 🐳 1. Ejecución de Pruebas con Docker Compose (Recomendado)

Con los contenedores en ejecución (`docker compose up -d`), puedes correr las pruebas mediante:

#### A. Ejecutar todas las pruebas del proyecto
```bash
docker compose exec web python manage.py test
```

#### B. Ejecutar pruebas de módulos específicos (`authentication` y `customers`)
```bash
docker compose exec web python manage.py test authentication customers
```

#### C. Ejecutar solo el módulo de Clientes (`customers`)
```bash
docker compose exec web python manage.py test customers
```

#### D. Ejecutar solo el módulo de Autenticación (`authentication`)
```bash
docker compose exec web python manage.py test authentication
```

#### E. Ejecutar clases o métodos de prueba específicos
```bash
# Probar únicamente las validaciones del modelo Cliente
docker compose exec web python manage.py test customers.tests.ClienteModelValidationTests

# Probar la herencia y restricciones de roles de autenticación
docker compose exec web python manage.py test authentication.tests.AuthRoleInheritanceTests

# Probar un método de test puntual
docker compose exec web python manage.py test customers.tests.ClienteModelValidationTests.test_creacion_cliente_valido
```

#### F. Opciones adicionales útiles
* **Modo detallado (Verbosity 2):** muestra cada test individual ejecutado.
  ```bash
  docker compose exec web python manage.py test -v 2
  ```
* **Detención al primer fallo (`--failfast`):**
  ```bash
  docker compose exec web python manage.py test --failfast
  ```

---

### 📊 2. Medición y Reportes de Cobertura de Código (Coverage)

La herramienta `coverage` permite auditar la cobertura de código en las pruebas automatizadas.

#### Paso 1: Ejecutar las pruebas recolectando cobertura
Para medir la cobertura de `authentication` y `customers`:
```bash
docker compose exec web coverage run --source='authentication,customers' manage.py test authentication customers
```

#### Paso 2: Visualizar el reporte consolidado en la terminal
```bash
docker compose exec web coverage report
```
> [!TIP]
> Puedes agregar el parámetro `-m` (`coverage report -m`) para visualizar exactamente los números de línea que no fueron alcanzados por las pruebas.

#### Paso 3: Generar el reporte interactivo en HTML
```bash
docker compose exec web coverage html
```
El reporte HTML se generará en el directorio `htmlcov/`. Puedes abrir `htmlcov/index.html` en cualquier navegador web para inspeccionar la cobertura línea por línea con resaltado visual.

---

### 💻 3. Ejecución Local (Sin Docker, mediante Entorno Virtual)

Si estás ejecutando el entorno directamente en tu máquina host con el entorno virtual activado (`venv`):

```bash
# 1. Ejecución de la suite de pruebas completa
python manage.py test

# 2. Ejecutar únicamente authentication y customers
python manage.py test authentication customers

# 3. Recolectar cobertura sobre los módulos clave
coverage run --source='authentication,customers' manage.py test authentication customers

# 4. Ver reporte en consola con líneas no cubiertas
coverage report -m

# 5. Generar reporte HTML
coverage html
```

---

### ✅ 4. Estado y Métricas de Calidad Actuales

Todas las pruebas de `authentication` y `customers` pasan satisfactoriamente con 0 errores y 0 fallos:

| Módulo / Componente | Tests Totales | Estado | Cobertura de Código |
| :--- | :---: | :---: | :---: |
| **`authentication`** (Tokens JWT, Roles RBAC, Backends, Tags) | 33 tests | `PASS (OK)` | ~95% |
| **`customers`** (Modelos, Validaciones, Segmentación, Forms, Vistas) | 36 tests | `PASS (OK)` | ~95% |
| **Total Combinado** | **69 tests** | **100% Exitoso** | **95% Global** |

---

## 🛠️ Comandos Útiles para el Desarrollo

* **Ver los logs de los contenedores en tiempo real:**
  ```bash
  docker compose logs -f web
  # o de todos los servicios:
  docker compose logs -f
  ```

* **Comprobar el estado de los servicios:**
  ```bash
  docker compose ps
  ```

* **Acceder a la consola dentro del contenedor de Django:**
  ```bash
  docker compose exec web bash
  ```

* **Detener los servicios:**
  ```bash
  docker compose down
  ```

* **Detener los servicios y eliminar volúmenes (reiniciar base de datos desde cero):**
  ```bash
  docker compose down -v
  ```