# Manual de Usuario - Global Exchange

Este documento sirve como guía de referencia rápida para probar las distintas funcionalidades del sistema Global Exchange. A continuación se detallan los módulos principales y las rutas o acciones necesarias para validar el correcto funcionamiento de cada componente.

## 0. Preparación del Entorno (Comandos Iniciales)
Antes de probar las funciones en el navegador, asegúrese de tener el entorno de desarrollo y los servicios requeridos corriendo. Abra su terminal o consola en la raíz del proyecto y ejecute los siguientes comandos:

1. **Levantar los servicios de infraestructura (Base de datos y Keycloak)**:
   El proyecto requiere que PostgreSQL y Keycloak estén en ejecución. Puede levantarlos usando Docker:
   ```bash
   docker-compose up -d db keycloak mailpit
   ```
   *(Nota: si lo prefiere, puede levantar todo el proyecto con `docker-compose up -d` y saltarse los pasos 4 y 5, pero los pasos a continuación aplican si desea correr Django localmente en su entorno virtual).*

2. **Instalar las dependencias** (si es la primera vez):
   ```bash
   pip install -r requirements.txt
   ```

3. **Aplicar las migraciones** de base de datos (vital por los nuevos módulos de comisiones y cotizaciones):
   ```bash
   python manage.py migrate
   ```

4. **Crear un superusuario local** (Solo para el panel de administración de Django `/admin/`):
   ```bash
   python manage.py createsuperuser
   ```
   *(Importante: Estas credenciales locales no sirven para la pantalla principal de Iniciar Sesión de Keycloak. Para probar la app como un usuario normal, deberá usar el botón "Register" en la pantalla de inicio de sesión).*

5. **Levantar el servidor local**:
   ```bash
   python manage.py runserver
   ```

Una vez que el servidor esté en ejecución, puede ingresar a la página abriendo su navegador y dirigiéndose a: **http://127.0.0.1:8000/** o **http://localhost:8000/**.

---

## 1. Autenticación y Acceso
El sistema utiliza Single Sign-On (SSO) integrado con Keycloak a través de OIDC.

- **Iniciar Sesión**: Al ingresar a la ruta raíz `/`, si el usuario no está autenticado, será redirigido al portal de inicio de sesión de Keycloak. Al ingresar credenciales válidas, retornará a la aplicación de Django.
- **Registro de Usuarios y Verificación de Correo (Mailpit)**: Si crea un usuario nuevo en la pantalla de Keycloak, el sistema le pedirá verificar su correo. **No le llegará un correo real.** Como estamos en un entorno de desarrollo, todos los correos son interceptados por una herramienta llamada **Mailpit**. Para ver el correo de verificación y hacer clic en el enlace, ingrese a **http://localhost:8025** en su navegador.
- **Cerrar Sesión**: Se puede probar el cierre de sesión unificado dirigiéndose a `/auth/logout/`. Esto finalizará la sesión local en Django y también en Keycloak.

## 2. Gestión de Clientes (`/customers/`)
Este módulo permite la administración integral del directorio de clientes y el manejo del cliente "activo" en la sesión actual.

- **Listado de clientes** (`/customers/`): Muestra la grilla o lista de todos los clientes registrados.
- **Creación de cliente** (`/customers/nuevo/`): Formulario para dar de alta a un cliente nuevo. Se pueden probar los campos obligatorios como el RUC o documento.
- **Detalle de cliente** (`/customers/<id>/`): Vista en detalle de un cliente específico.
- **Edición y Eliminación**: 
  - Para editar, acceda a `/customers/<id>/editar/`.
  - Para eliminar, acceda a `/customers/<id>/eliminar/` y confirme la acción.
- **Cliente Activo en Sesión**: Funcionalidad clave para operar en nombre de un cliente. Puede probar cambiarse de cliente activo mediante la ruta `/customers/cambiar-activo/<id>/`.

## 3. Medios de Pago (`/payments/`)
Gestión de los métodos de pago aceptados y su disponibilidad.

- **Listado de Medios de Pago** (`/payments/`): Listado general.
- **Alta, Baja y Modificación**: 
  - Creación: `/payments/crear/`
  - Edición: `/payments/<id>/editar/`
  - Eliminación: `/payments/<id>/eliminar/`
- **Marcar como Predeterminado**: Accediendo a `/payments/<id>/predeterminado/`, probar configurar un método base.
- **Activar/Desactivar**: La ruta `/payments/<id>/toggle-activo/` permite habilitar o deshabilitar un método de pago sin eliminarlo.

## 4. Tasas de Cambio, Comisiones y Cotizaciones (`/rates/`)
Este es el motor central (Core) de la plataforma, donde se configuran las divisas, las tasas y se calculan las operaciones.

### 4.1. Configuración Base
- **Monedas (Currencies)** (`/rates/currencies/`): Acceda a esta vista para listar las divisas soportadas (ej: USD, EUR, PYG). Pruebe crear una nueva desde `/rates/currencies/create/` o habilitar/deshabilitar una con `/rates/currencies/<id>/toggle/`.
- **Tasas de Cambio (Exchange Rates)** (`/rates/exchange-rates/`): Lista el valor de conversión entre las distintas monedas. Se pueden agregar nuevos pares desde `/rates/exchange-rates/create/`.
- **Comisiones por Segmento** (`/rates/commissions/`): Visualice las reglas de comisión según el segmento (Minorista, Corporativo, etc.). Agregue nuevas reglas en `/rates/commissions/add/`.

### 4.2. Dashboards y Simulador (Core Business)
- **Dashboard de Cotizaciones Históricas** (`/rates/dashboard/`): Panel para visualizar el histórico y la evolución de las tasas de cambio de los distintos pares de monedas configurados.
- **Simulador / Calculadora de Tasas** (`/rates/calculator/`): 
  - **Prueba Principal**: Ingrese al simulador. Seleccione una moneda de origen, una moneda de destino y el monto. 
  - El sistema deberá calcular el monto neto utilizando la tasa de cambio vigente y aplicando las comisiones configuradas para el segmento del cliente seleccionado.

## Endpoints de API REST (Para pruebas con Postman/cURL)
Si se requiere probar el backend de forma programática (vía JSON), la plataforma expone varios endpoints:
- **Clientes**: `/customers/api/` (GET/POST) y `/customers/api/documento/<ruc>/`
- **Pagos**: `/payments/api/` (GET/POST)
- **Cálculo de Cotización (Motor)**: `/rates/api/calculate/` (POST enviando origen, destino, segmento, monto).
- **Congelamiento de Tasas**: `/rates/api/freeze/` (Para reservar una tasa por un tiempo determinado) y `/rates/api/unfreeze/`.

## Resumen de Flujo Completo Recomendado para Pruebas (End-to-End)
1. Ingresar a la aplicación e **iniciar sesión** mediante Keycloak.
2. Ir a **Monedas** y asegurar que existan al menos dos (ej. USD y PYG).
3. Ir a **Tasas de Cambio** y configurar la paridad de la fecha (ej. 1 USD = 7500 PYG).
4. Ir a **Clientes** y crear un cliente asignándole un segmento (Ej. "VIP").
5. Ir a **Comisiones** y crear una comisión (Ej. 1% para el segmento "VIP").
6. Marcar al cliente creado como **Cliente Activo**.
7. Ir a la **Calculadora de Cotizaciones** (`/rates/calculator/`), ingresar 100 USD para comprar PYG, y verificar que el monto final considere la tasa de cambio oficial menos la comisión del 1%.
