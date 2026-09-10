# Documentación Técnica — SCRUM-41: Estandarización de Comandos de Tests y Cobertura

**ID Jira:** SCRUM-41  
**Épica Principal:** SCRUM-34 (Calidad de Software y Automatización de Pruebas)  
**Sprint:** SCRUM Sprint 2  
**Autor:** Pablo Elizeche (con asistencia de IA Antigravity / Gemini)  
**Fecha:** 08/09/2026  
**Rama de trabajo:** `hotfix/SCRUM-41`  

---

## 1. Descripción del Requerimiento

Documentar detalladamente los comandos de ejecución de pruebas con Docker Compose (`docker compose exec web python manage.py test`) y cobertura (`coverage`), validando que la totalidad de tests de `authentication` y `customers` pasen satisfactoriamente sin errores ni fallos.

---

## 2. Diagnóstico y Problemas Identificados

1. **Falta de Documentación en README.md**: El archivo principal `README.md` explicaba el despliegue con Docker y arranque básico, pero carecía de una sección dedicada a la ejecución de tests automatizados y auditoría de cobertura.
2. **Dependencia de `coverage` no formalizada**: El paquete `coverage` no figuraba en `requirements.txt`, lo que obligaba a instalaciones ad-hoc o impedía su uso inmediato en contenedores nuevos.
3. **Aislamiento de la Base de Datos de Pruebas**: Django por defecto intentaba usar la configuración `config.settings.dev` (PostgreSQL) si el desarrollador omitía `--settings=config.settings.test`, provocando fallos por permisos o intentando conectarse a bases de datos operativas en vez de la configuración optimizada e in-memory SQLite (`config.settings.test`).
4. **Artefactos de Cobertura en Git**: Los archivos generados por coverage (`.coverage`, `.coverage.*`, `htmlcov/`) no estaban ignorados explícitamente en `.gitignore` ni en `.dockerignore`.

---

## 3. Solución Implementada con IA

### 3.1. Enrutamiento Inteligente en `manage.py`
Se modificó `manage.py` para detectar si el argumento `test` se encuentra en la línea de comandos (`sys.argv`). Si no se especifica explícitamente una bandera `--settings`, el sistema asigna de forma automática `DJANGO_SETTINGS_MODULE = 'config.settings.test'`.
* **Beneficio**: Permite que tanto `docker compose exec web python manage.py test` como `python manage.py test` funcionen de manera transparente, rápida y sin efectos secundarios en PostgreSQL ni necesidad de flags extensos.

### 3.2. Gestión de Dependencias (`requirements.txt`)
Se agregó `coverage>=7.6.0` al archivo `requirements.txt` para garantizar su presencia tanto en entornos virtuales locales como en el contenedor Docker `web`.

### 3.3. Configuración de Ignorados (`.gitignore` y `.dockerignore`)
Se agregaron las siguientes reglas para evitar ensuciar el control de versiones con reportes temporales:
```gitignore
# Cobertura de pruebas (Coverage)
.coverage
.coverage.*
htmlcov/
*.cover
.pytest_cache/
```

### 3.4. Estandarización de Comandos en `README.md`
Se incorporó la sección **"🧪 Ejecución de Pruebas Unitarias y Cobertura (Testing & Coverage)"**, detallando:
* Comandos completos con Docker Compose para suite global, módulos específicos (`authentication`, `customers`), clases y métodos puntuales.
* Comandos con flags de verbosidad (`-v 2`) y detención al primer fallo (`--failfast`).
* Guía de 3 pasos para auditoría con `coverage`: ejecución (`coverage run`), reporte por consola (`coverage report -m`) y generación del reporte web interactivo (`coverage html`).
* Instrucciones equivalentes para ejecución local en entorno virtual (`venv`).
* Matriz de métricas de calidad y estado actual de las pruebas.

---

## 4. Guía de Ejecución Rápida

### 4.1. Con Docker Compose (Recomendado)
```bash
# 1. Ejecutar toda la suite de pruebas
docker compose exec web python manage.py test

# 2. Ejecutar específicamente authentication y customers
docker compose exec web python manage.py test authentication customers

# 3. Recolectar cobertura de código
docker compose exec web coverage run --source='authentication,customers' manage.py test authentication customers

# 4. Ver reporte en terminal (con líneas faltantes)
docker compose exec web coverage report -m

# 5. Generar reporte interactivo HTML
docker compose exec web coverage html
```

### 4.2. Localmente con Entorno Virtual
```bash
# 1. Activar venv
.\venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate       # Linux/macOS

# 2. Ejecutar pruebas
python manage.py test authentication customers

# 3. Medición de cobertura
coverage run --source='authentication,customers' manage.py test authentication customers
coverage report -m
coverage html
```

---

## 5. Validación y Resultados de Ejecución

### 5.1. Resultados del Test Runner
* **Pruebas ejecutadas:** 69 pruebas.
* **Fallos (failures):** 0
* **Errores (errors):** 0
* **Tiempo de ejecución:** ~1.3 segundos (con SQLite in-memory).
* **Estado:** `OK`.

### 5.2. Métricas de Cobertura Obtenidas
Ejecución del comando:
`coverage report`

```text
Name                                                                              Stmts   Miss  Cover
-----------------------------------------------------------------------------------------------------
authentication/__init__.py                                                            0      0   100%
authentication/backends.py                                                           56      8    86%
authentication/context_processors.py                                                 28      1    96%
authentication/templatetags/__init__.py                                               0      0   100%
authentication/templatetags/auth_tags.py                                             48      4    92%
authentication/tests.py                                                             228      0   100%
authentication/urls.py                                                                4      0   100%
authentication/views.py                                                              24     10    58%
customers/__init__.py                                                                 0      0   100%
customers/admin.py                                                                   10      0   100%
customers/apps.py                                                                     7      0   100%
customers/forms.py                                                                   13      0   100%
customers/migrations/0001_initial.py                                                  5      0   100%
customers/migrations/0002_alter_cliente_options_cliente_keycloak_id_and_more.py       6      0   100%
customers/migrations/__init__.py                                                      0      0   100%
customers/models.py                                                                  24      0   100%
customers/services.py                                                                63      6    90%
customers/signals.py                                                                 24      1    96%
customers/tests.py                                                                  331      2    99%
customers/urls.py                                                                     4      0   100%
customers/views.py                                                                  174     18    90%
-----------------------------------------------------------------------------------------------------
TOTAL                                                                              1049     50    95%
```

* **Cobertura Global Alcanzada:** **95%**
* **Modelos, Formularios y Tests:** **100%** de cobertura en lógica crítica de datos.
