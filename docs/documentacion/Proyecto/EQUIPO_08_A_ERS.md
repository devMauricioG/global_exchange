# ESPECIFICACIÓN DE REQUERIMIENTOS DE SOFTWARE (ERS v3.3)

**Proyecto:** Global Exchange – Casa de Cambio Digital e Híbrida

**Estado:** Documento Consolidado (ERS v3.2 + Hito 5 SCRUM 85)

**Fecha de Actualización:** 24 de Septiembre de 2026

### TABLA DE CONTENIDOS

1. Introducción  
   1.1. Propósito  
   1.2. Definiciones, Acrónimos y Abreviaturas  
   1.3. Alcance  
   1.4. Referencias
2. Presentación del Producto  
   2.1. Propósito del Sistema  
   2.1.1. Objetivo  
   2.1.2. Alcance  
   2.1.3. El Sistema no contempla  
   2.2. Restricciones y Supuestos
3. Descripción General  
   3.1. Listado de la Funcionalidad del Sistema  
   3.2. Contexto del Producto  
   3.3. Perspectivas futuras del producto  
   3.4. Reglas y Funciones de Negocio
4. Descripción Detallada de Requerimientos  
   4.1. Actores  
   4.2. Requerimientos Funcionales  
   4.3. Requerimientos No Funcionales
5. Requerimientos de Licencia
6. Observaciones
7. Historia de Cambios

### 1\. Introducción

#### 1.1. Propósito

El presente documento constituye la Especificación de Requerimientos de Software (ERS v3.0) consolidada para el sistema de gestión digital e híbrido de la casa de cambio Global Exchange. Su propósito es describir de manera formal, completa y sin ambigüedades los requerimientos funcionales y no funcionales que deberá cumplir el software a desarrollar, integrando la gestión operativa omnicanal (digital y presencial) con la infraestructura de seguridad, autenticación y autorización centralizada basada en **Keycloak IAM**.

Este documento representa la base técnica definitiva para las etapas de arquitectura, desarrollo, pruebas y validación del producto bajo los estándares de la cátedra.

#### 1.2. Definiciones, Acrónimos y Abreviaturas

| **Término**        | **Definición**                                                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------------------------------- |
| **ERS**            | Especificación de Requerimientos de Software.                                                                       |
| ---                | ---                                                                                                                 |
| **RF / RNF**       | Requerimiento Funcional / Requerimiento No Funcional.                                                               |
| ---                | ---                                                                                                                 |
| **Keycloak**       | Servidor de gestión de identidades y accesos (IAM) de código abierto para SSO, autenticación y autorización.        |
| ---                | ---                                                                                                                 |
| **IdP**            | Identity Provider (Proveedor de Identidad). Servidor central encargado de autenticar usuarios y emitir tokens.      |
| ---                | ---                                                                                                                 |
| **OIDC**           | OpenID Connect. Capa de identidad basada en el protocolo OAuth 2.0 utilizada para autenticar usuarios.              |
| ---                | ---                                                                                                                 |
| **JWT**            | JSON Web Token. Estándar abierto (RFC 7519) utilizado para transmitir información de identidades y claims firmados. |
| ---                | ---                                                                                                                 |
| **PKCE**           | Proof Key for Code Exchange. Extensión de OAuth 2.0 para prevenir ataques de interceptación en clientes públicos.   |
| ---                | ---                                                                                                                 |
| **RBAC**           | Role-Based Access Control. Control de acceso basado en roles asignados a los usuarios.                              |
| ---                | ---                                                                                                                 |
| **SLO**            | Single Logout (Cierre de Sesión Único). Revocación centralizada de sesiones y tokens en el IdP.                     |
| ---                | ---                                                                                                                 |
| **JWKS**           | JSON Web Key Set. Conjunto de claves públicas expuestas por el IdP para la verificación de firmas JWT.              |
| ---                | ---                                                                                                                 |
| **Casa de Cambio** | Entidad financiera dedicada a la compra y venta de divisas extranjeras.                                             |
| ---                | ---                                                                                                                 |
| **Divisa**         | Moneda extranjera utilizada en transacciones (USD, EUR, PYG, BRL, ARS, GBP).                                        |
| ---                | ---                                                                                                                 |
| **Arqueo de Caja** | Proceso de conteo y verificación del efectivo físico frente al saldo contable esperado al cierre de turno.          |
| ---                | ---                                                                                                                 |
| **SIFEN / DNIT**   | Sistema Integrado de Facturación Electrónica Nacional de la Dirección Nacional de Ingresos Tributarios.             |
| ---                | ---                                                                                                                 |
| **Moneda**         | Divisa del catálogo identificada por un código ISO 4217 de tres letras.                                             |
| ---                | ---                                                                                                                 |
| **Tasa de cambio** | Precio de una moneda base expresado en una moneda destino, con valores de compra y venta.                           |
| ---                | ---                                                                                                                 |
| **Spread**         | Diferencia calculada entre la tasa de venta y la tasa de compra.                                                    |
| ---                | ---                                                                                                                 |
| **Comisión por segmento** | Regla comercial aplicable a un segmento de cliente; combina porcentaje, cargo fijo y descuento sobre el spread. |
| ---                | ---                                                                                                                 |
| **Cotización neta** | Resultado informativo que expone tasa efectiva, importes brutos, comisiones y monto final.                         |
| ---                | ---                                                                                                                 |
| **Medio de pago**  | Instrumento de cobro o liquidación registrado por el cliente: transferencia, billetera, tarjeta, efectivo u otro.   |
| ---                | ---                                                                                                                 |

#### 1.3. Alcance

Cubre la especificación de los requerimientos funcionales y no funcionales para la construcción de la plataforma omnicanal de Global Exchange. Abarca las reglas de negocio, los actores, la gestión de cajas presenciales, la integración tributaria (SIFEN) y la integración con Keycloak mediante OIDC y OAuth 2.0.

#### 1.4. Referencias

| **Archivo / Documento** | **Título del Documento**                                           | **Organización que lo Publica**            |
| ----------------------- | ------------------------------------------------------------------ | ------------------------------------------ |
| Enunciado_IS1_2026.pdf  | Enunciado del Trabajo Práctico – IS1 2026                          | Cátedra de Ingeniería de Software I        |
| ---                     | ---                                                                | ---                                        |
| NCR_Global_Exchange.pdf | Nota de Cambio de Requerimientos (NCR v1.0 e integración Keycloak) | Equipo de Ingeniería de Software / Cátedra |
| ---                     | ---                                                                | ---                                        |
| IEEE Std 830-1998       | IEEE Recommended Practice for Software Requirements Specifications | IEEE                                       |
| ---                     | ---                                                                | ---                                        |
| RFC 6749 / RFC 7636     | The OAuth 2.0 Authorization Framework / PKCE Extension             | IETF (Internet Engineering Task Force)     |
| ---                     | ---                                                                | ---                                        |

### 2\. Presentación del Producto

#### 2.1. Propósito del Sistema

##### 2.1.1. Objetivo

Evolucionar la casa de cambio "Global Exchange" hacia un modelo omnicanal híbrido mediante un software seguro desacoplado, donde la gestión de credenciales e identidades sea provista de manera centralizada por Keycloak, permitiendo operaciones fluidas tanto digitales como presenciales.

##### 2.1.2. Alcance

El producto abarcará 8 módulos mínimos obligatorios:

1. **Gestión de Usuarios, Autenticación OIDC y Autorización RBAC (Keycloak IAM):** Registro delegado, login SSO vía Authorization Code con PKCE, emisión y validación de tokens JWT.
2. **Gestión de Clientes:** Registro, mantenimiento, segmentación (Minoristas, Corporativos, VIP) y vinculación con la entidad de identidad de Keycloak.
3. **Gestión de Operaciones Cambiarias:** Cotizaciones en tiempo real, congelamiento de tasa, procesamientos digitales y presenciales.
4. **Gestión de Cajas y Cajeros:** Apertura con fondo inicial, cobro/entrega de efectivo, arqueo de caja y auditoría inmutable asociada al ID de usuario Keycloak.
5. **Gestión de Documentos Electrónicos:** Emisión e integración con SIFEN/DNIT de Facturas y Notas de Crédito Electrónicas.
6. **Reportes y Gráficos para Monitoreo de Ganancias:** Visualización en tiempo real del spread comercial y exportación de datos.
7. **Notificaciones:** Alertas automáticas por fluctuaciones de tasas y alertas de precio para clientes.
8. **Configuraciones:** Parámetros de monedas, operaciones, métodos de pago y endpoints/credenciales de conexión con Keycloak.

##### 2.1.3. El Sistema no contempla

- Logística de transporte de caudales, control biométrico de RRHH, ni contabilidad general.
- Otorgamiento de créditos o préstamos.
- Almacenamiento ni procesamiento local de contraseñas de usuarios (delegado 100% a Keycloak).

#### 2.2. Restricciones y Supuestos

- **Servidor IAM:** Es obligatorio contar con un servidor o contenedor de Keycloak operativo accesible vía HTTPS.
- **Prohibición de Credenciales Locales:** La base de datos de la aplicación no debe almacenar hashes de contraseñas bajo ninguna circunstancia.
- **Restricción de Edad:** Validación estricta de edad mayor a 18 años para operar en la plataforma.
- **Normativa Fiscal:** Generación de Facturas y Notas de Crédito conforme a las especificaciones XML del SIFEN/DNIT.

### 3\. Descripción General

#### 3.1. Listado de la Funcionalidad del Sistema

- Autenticación centralizada y Single Sign-On (SSO) mediante Keycloak con soporte para PKCE.
- Autorización de peticiones en backend/gateway mediante lectura apátrida de claims y roles (realm_access.roles) en tokens JWT.
- Registro delegado e integración del ciclo de vida de usuario con Keycloak.
- Cierre de sesión único (Single Logout - SLO) para invalidación centralizada de refresh tokens.
- Registro, mantenimiento y segmentación administrativa de clientes asociados a usuarios de Keycloak (Keycloak User ID / sub).
- Visualización gráfica de evolución de tasas (líneas/barras) con filtros temporales.
- Cotizador interactivo con congelamiento de tasa por 5 minutos.
- Procesamiento de compra/venta de divisas (efectivo en ventanilla o medios digitales).
- Gestión presencial de cajas: apertura, cobro, entrega, cierre y arqueo con verificación de rol Cajero.
- Auditoría inmutable de movimientos de caja enlazada al ID de Keycloak del operador.
- Emisión e integración de Facturas y Notas de Crédito Electrónicas (SIFEN/DNIT).
- Panel de administración de parámetros Keycloak, monedas, operaciones y métodos de pago.
- Gestión de catálogo de divisas con validación ISO 4217, activación y desactivación de monedas.
- Administración de tasas de cambio por par de monedas con intervalo de vigencia, spread calculado y operador responsable.
- Tablero histórico de evolución de tasas de compra y venta por par y por periodo.
- Gestión de comisiones por segmento de cliente: porcentaje, cargo fijo y descuento de spread.
- Cotizador de tasas netas con simulación de compra o venta, resolución de segmento y cálculo de monto final.
- Registro, consulta, edición y eliminación de medios de pago del cliente activo con selección de predeterminado.

#### 3.2. Contexto del Producto

El núcleo central omnicanal interactúa con:

- **Keycloak IAM Server:** Proveedor de identidad que autentica usuarios y emite tokens JWT / JWKS.
- **Entidades Financieras / Billeteras:** Procesamiento digital de fondos.
- **Servicio Externo SIFEN / DNIT:** Validación tributaria de comprobantes.
- **Terminales de Caja Presenciales:** Estaciones de ventanilla para operadores de caja.

#### 3.3. Perspectivas futuras del producto

- Confirmación o persistencia de una cotización como transacción.
- Congelamiento o reserva temporal de tasa (5 minutos).
- Ejecución bancaria, conciliación o integración con proveedores de billetera.
- Cifrado o tokenización de datos de cuentas antes de manejar datos financieros sensibles en producción.

#### 3.4. Reglas y Funciones de Negocio

- **RN01 (Autenticación Delegada):** Todo usuario debe autenticarse exclusivamente en Keycloak para obtener un token JWT válido.
- **RN02 (Autorización por Token):** Cualquier petición enviada al backend/gateway debe adjuntar un token JWT en el encabezado Authorization: Bearer &lt;token&gt;. Peticiones sin token o con token inválido/expirado serán rechazadas con HTTP 401 Unauthorized o 403 Forbidden.
- **RN03 (Asignación Administrativa de Clientes):** La vinculación entre el identificador de Keycloak (sub) y los perfiles de Clientes (físicos o jurídicos) es realizada únicamente por el Administrador.
- **RN04 (Operatividad por Cliente):** Para transaccionar, el usuario autenticado debe seleccionar un cliente activo al que esté vinculado.
- **RN05 (Gestión de Cajas):** Las operaciones de cobro o entrega de efectivo exigen que el usuario posea una caja en estado "Abierta" y cuente con el rol Cajero en su token JWT.
- **RN06 (Expiración de Cotización):** Cotizaciones en estado "Pendiente" expiran tras 5 minutos sin confirmación de pago.
- **RN07 (Anulaciones y Notas de Crédito):** Toda transacción "Pagada" que sea anulada requiere la emisión obligatoria de una Nota de Crédito Electrónica.
- **RN08 (Código de Moneda):** El código de moneda debe contener exactamente tres caracteres alfabéticos; el sistema lo normaliza a mayúsculas.
- **RN09 (Par de Monedas):** Una tasa solo puede relacionar monedas distintas y debe tener tasas de compra y venta estrictamente positivas.
- **RN10 (Spread):** La tasa de venta no puede ser inferior a la tasa de compra; el spread se calcula como `sell_rate - buy_rate`.
- **RN11 (Vigencia de Tasa):** Si una tasa define fin de vigencia, este debe ser posterior al inicio. Una tasa usable debe estar activa y vigente.
- **RN12 (Unicidad de Comisión):** Cada segmento puede tener una única regla de comisión. Porcentajes de comisión y descuento deben estar entre 0 y 100; el cargo fijo no puede ser negativo.
- **RN13 (Dirección de Tasa):** El cotizador aplica la tasa de venta cuando el cliente compra la moneda base y la tasa de compra cuando la vende.
- **RN14 (Bonificación de Spread):** La bonificación se aplica sobre el spread. En compra reduce la tasa efectiva y en venta la incrementa antes de calcular cargos.
- **RN15 (Comisión Total):** La comisión total es la suma del componente porcentual sobre el monto bruto y el cargo fijo. En compra se suma al monto a pagar; en venta se resta del monto a recibir, sin producir un monto neto negativo.
- **RN16 (Regla Neutral):** Una regla inactiva o ausente no agrega cargos ni descuentos; el sistema usa una regla neutral para el segmento correspondiente.
- **RN17 (Medio de Pago Único):** Cada medio de pago pertenece a un solo cliente. Solo puede existir un medio predeterminado por cliente y este debe estar activo.
- **RN18 (Aislamiento de Medios de Pago):** Un cliente solo puede consultar o modificar sus propios medios de pago. El primer medio registrado se establece como predeterminado.

### 4\. Descripción Detallada de Requerimientos

#### 4.1. Actores

- **Keycloak IAM (Servidor Externo/IdP):** Proveedor de Identidad responsable de la autenticación, emisión de tokens y gestión de credenciales.
- **Cliente / Usuario Representante:** Usuario autenticado con rol Cliente que opera en nombre de una cuenta personal o corporativa.
- **Administrador:** Usuario autenticado con el Realm Role Administrador habilitado para parametrización global, configuración Keycloak y asignación de clientes.
- **Analista Cambiario:** Usuario autenticado con el Realm Role Analista_Cambiario autorizado para ajustar tasas de pizarra y consultar métricas de negocio.
- **Cajero:** Usuario autenticado con el Realm Role Cajero habilitado para la operativa presencial de caja, cobro/entrega de efectivo y arqueo.
- **Servicio SIFEN / DNIT:** Sistema tributario externo integrado vía API REST/SOAP.

#### 4.2. Requerimientos Funcionales

- **RF01: Registro de Usuarios Sincronizado con Keycloak**
  - **Descripción:** Los usuarios ingresan sus datos de registro. El sistema delega la creación del usuario en el Realm de Keycloak, asignando por defecto la acción requerida de verificación de correo (_Verify Email_) y el rol base Cliente.
- **RF03: Asignación de Representación de Clientes desde la Administración**
  - **Descripción:** Interfaz exclusiva para que el Administrador vincule un registro de Cliente (persona física o jurídica) con el identificador único del usuario en Keycloak (Keycloak User ID / sub).
- **RF04 y RF05: Selección y Cambio Dinámico de Cliente Activo en Sesión**
  - **Descripción:** Tras autenticarse vía Keycloak, si el usuario posee múltiples clientes asignados en `CustomerUserAssignment`, el sistema despliega un menú interactivo en la barra de navegación para alternar el cliente activo. Las reglas operativas son:
    - `ActiveCustomerMiddleware` intercepta cada solicitud, lee `active_customer_id` de la sesión y valida que el usuario posea una asignación activa vigente.
    - Si no existe selección previa, asigna automáticamente como cliente activo al representante principal (`is_primary_representative=True`).
    - Al cambiar de cliente en el selector, el endpoint valida la pertenencia y actualiza la sesión; en caso de intento de acceso a un cliente no asignado, el sistema deniega el cambio retornando código **`HTTP 403 Forbidden`**.
    - Todas las transacciones, cotizaciones y consultas operativas se ejecutan contextualizadas al cliente activo seleccionado.
- **RF06: Visualización Gráfica de la Evolución de Tasas**
  - **Descripción:** Gráficos interactivos de líneas o barras para analizar tendencias de divisas por día, semana, mes y año.
- **RF07: Simulación de Conversión (Cotizador)**
  - **Descripción:** Calculadora de divisas que congela la cotización pactada durante un plazo exacto de 5 minutos al iniciar el proceso de compra/venta.
- **RF08 y RF09: Procesamiento Híbrido de Operaciones Cambiarias**
  - **Descripción:** Ejecución de operaciones omnicanal con liquidación mediante dinero físico en ventanilla (vía Cajero) o acreditación/pago digital en cuentas bancarias/billeteras.
- **RF10: Máquina de Estados de la Transacción**
  - **Descripción:** Control de estados: Pendiente, Pagada/Completada, Cancelada y Anulada (con emisión de Nota de Crédito).
- **RF11: Exportación de Historial**
  - **Descripción:** Generación de reportes filtrados por fecha en PDF y CSV/Excel.
- **RF12: Facturación Electrónica (SIFEN/DNIT)**
  - **Descripción:** Generación, compilación XML y transmisión automática de Facturas Electrónicas al pasar operaciones a estado "Pagada".
- **RF13: Monitoreo de Ganancias (Spread)**
  - **Descripción:** Panel en tiempo real para visualizar el margen de ganancia por divisa acumulado diario y mensual.
- **RF14: Notificaciones sobre Actualizaciones de Tasas de Cambio**
  - **Descripción:** Envío de alertas por variaciones de cotizaciones y alertas personalizadas de precio configuradas por el usuario.
- **RF15: Módulo de Configuración General**
  - **Descripción:** Panel de administración para: 1) Monedas; 2) Operaciones admitidas; 3) Tasas manuales; 4) Métodos de pago; y 5) Parámetros Keycloak (URL Realm, Client ID, Client Secret, JWT TTL y URL de JWKS).
- **RF16: Permisos y Delimitación de Roles Operativos (Keycloak RBAC)**
  - **Descripción:** Control de acceso derivado de los _Realm Roles_ del JWT:
    - Analista_Cambiario: Actualización de tasas de pizarra y lectura de métricas.
    - Cajero: Apertura, cobro/entrega presencial, cierre y arqueo de caja.
    - Administrador: Parámetros globales y vinculación de clientes.
- **RF-17: Registro y Mantenimiento de Clientes**
  - **Descripción:** Módulo para la administración y segmentación de datos comerciales/legales de clientes (Minoristas, Corporativos, VIP).
- **RF-18: Emisión de Documentos Electrónicos – Notas de Crédito**
  - **Descripción:** Generación y transmisión XML de Notas de Crédito Electrónicas (SIFEN/DNIT) para anulación o reajuste de operaciones.
- **RF-19: Configuración de Operaciones Admitidas**
  - **Descripción:** Habilitación/deshabilitación independiente de compra/venta de divisas por modalidades.
- **RF-20: Ampliación del Catálogo de Monedas Admitidas**
  - **Descripción:** Soporte para USD, EUR, PYG, BRL, ARS y GBP.
- **RF-21: Multi-Representación y Asignación de Usuarios a Clientes (CustomerUserAssignment)**
  - **Descripción:** Modelo de datos asociativo intermedio que formaliza la relación muchos-a-muchos ($N:M$) entre usuarios autenticados y entidades `Customer`:
    - Permite que un usuario represente a múltiples clientes y que un cliente corporativo tenga múltiples representantes autorizados.
    - Campos obligatorios: `user`, `customer`, `is_primary_representative` (máximo uno activo por cliente), `assigned_at`, `is_active` y rol corporativo.
    - Restricción de unicidad estricta para evitar asignaciones duplicadas `unique_together = ('user', 'customer')`.
- **RF-22: Apertura y Asignación de Cajas Presenciales**
  - **Descripción:** Registro de fondo inicial en efectivo por divisa por parte del Cajero autenticado.
- **RF-23: Cierre y Arqueo de Caja Físico**
  - **Descripción:** Conteo físico de billetes, cálculo de diferencias y emisión del reporte de arqueo.
- **RF-24: Auditoría y Monitoreo de Movimientos de Caja**
  - **Descripción:** Registro inmutable de operaciones de caja asociando el Keycloak User ID, timestamp, estación de trabajo e ID de transacción.
- **RF-25: Autenticación Centralizada y Autorización Stateless (Keycloak IAM)**
  - **Descripción:** La aplicación redirigirá las solicitudes de login a Keycloak utilizando OpenID Connect (_Authorization Code Flow con PKCE_). Tras la autenticación exitosa, el backend/gateway validará el token JWT de forma apátrida contra el endpoint JWKS.
- **RF-26: Cierre de Sesión Único (Single Logout - SLO)**
  - **Descripción:** Al presionar "Cerrar Sesión", el sistema invocará el endpoint de logout de Keycloak (/openid-connect/logout) enviando el refresh_token, invalidando la sesión centralizada del usuario.
- **RF-27: Visualizador Integrado de Documentación Técnica (Sphinx HTML)**
  - **Descripción:** El sistema debe servir y exponer de manera integrada y segura la documentación técnica del código autogenerada por Sphinx desde la ruta `/docs/`:
    - Entrega de páginas HTML y recursos estáticos (`.css`, `.js`, imágenes) con resolución de tipos MIME adecuados.
    - Mitigación de vulnerabilidades de _Path Traversal_ sobre el árbol de compilación `docs/sphinx/build/html/`.
    - Integración del acceso directo mediante enlace visible en la barra de navegación (`templates/base.html`).
- **RF28: Gestión de Monedas y Tasas de Cambio**
  - **Descripción:** El usuario autenticado debe poder listar, filtrar, crear, editar y activar o desactivar monedas y tasas de cambio. Cada tasa debe conservar las monedas base y destino, compra, venta, spread calculado, intervalo de vigencia, estado y responsable de la actualización.
  - **Criterios de aceptación:**
    - Las monedas inactivas no se consideran disponibles para una cotización.
    - El sistema rechaza pares de la misma moneda, importes no positivos y venta menor que compra.
    - El listado permite filtrar tasas por par, estado y vigencia.
    - El tablero permite revisar el historial de compra y venta por par y por periodo.
- **RF29: Gestión de Comisiones por Segmento**
  - **Descripción:** El usuario autenticado debe poder crear, consultar, editar y eliminar reglas de comisión para los segmentos definidos en `Cliente.Segmentación`.
  - **Criterios de aceptación:**
    - La regla identifica un segmento único y conserva porcentaje, cargo fijo, descuento de spread y estado.
    - El sistema valida los límites de los tres valores antes de persistirlos.
    - La API expone la lista de reglas y el detalle de una regla por código de segmento.
- **RF30: Cotizador de Tasas Netas**
  - **Descripción:** El Cliente autenticado debe poder simular una compra o venta entre dos monedas activas mediante una tasa vigente. La simulación debe usar el cliente activo para resolver el segmento comercial, salvo que un operador autorizado indique un cliente explícito.
  - **Criterios de aceptación:**
    - La entrada admite monto, moneda base, moneda destino, tipo de operación `BUY` o `SELL` e indicación de la moneda en que se expresa el monto.
    - El resultado presenta tasa oficial, spread oficial y efectivo, tasa efectiva, importes base y destino, comisión porcentual, cargo fijo, total de comisión, monto neto y ahorro por spread.
    - Los montos se redondean con la precisión configurada para cada moneda.
    - La interfaz web está disponible en `/rates/calculator/`; la API de cálculo acepta `GET` y `POST` en `/rates/api/calculate/`.
    - Ante un par inexistente, monto no positivo, tipo de operación inválido o JSON inválido, el sistema debe informar un error sin generar una transacción.
- **RF31: Gestión de Medios de Pago**
  - **Descripción:** El Cliente autenticado debe poder crear, listar, filtrar, editar, activar, desactivar, eliminar y seleccionar su medio de pago predeterminado. El sistema debe admitir transferencia, billetera, tarjeta, efectivo y otros medios autorizados.
  - **Criterios de aceptación:**
    - Cada registro conserva tipo, entidad o billetera, cuenta o teléfono, titular, documento opcional, estado y preferencia.
    - Las vistas y los endpoints JSON restringen los registros al cliente activo, evitando el acceso directo a recursos de otro cliente.
    - Al seleccionar un medio como predeterminado, el sistema desmarca atómicamente los anteriores del mismo cliente.
    - Al desactivar el medio predeterminado, se elimina su marca de preferencia.
- **RF-32: Gestión de Medios de Acreditación de Fondos (ReceivingMethod)**
  - **Descripción:** El cliente autenticado debe poder registrar, listar, editar, desactivar y seleccionar sus cuentas bancarias o billeteras de destino para la recepción de fondos convertidos.
  - **Criterios de aceptación:**
    - Admite cuentas bancarias (Ahorro/Corriente) y billeteras móviles vinculadas a entidades financieras autorizadas.
    - Validación de titularidad asegurando coincidencia con la ficha del cliente activo.
    - Exclusividad de cuenta de acreditación predeterminada por cliente.
    - Restricción estricta contra accesos directos IDOR.
- **RF-33: Catálogo Parametrizado de Entidades Bancarias y Financieras (EntidadFinanciera)**
  - **Descripción:** El sistema debe proveer un catálogo normalizado y parametrizado de entidades bancarias y proveedoras de billeteras electrónicas del sistema financiero paraguayo para alimentar los selectores (dropdowns) de medios de pago y acreditación.
  - **Criterios de aceptación:**
    - Catálogo diferenciado por tipo (BANCO, BILLETERA) con orden de visualización y estado activo.
    - Los formularios no admiten texto libre para la entidad, garantizando consistencia relacional.
- **RF-34: Límites Operativos por Moneda y Segmento Comercial (OperationLimit)**
  - **Descripción:** El Administrador de riesgos debe poder parametrizar y el sistema debe validar en tiempo real los límites financieros por divisa y segmento de cliente (Minorista, Mayorista, Corporativo, VIP).
  - **Criterios de aceptación:**
    - Parámetros: Monto mínimo por operación, Monto máximo por operación, Límite diario acumulado y Límite mensual acumulado.
    - Jerarquía de consistencia: $\text{monto\_minimo} \le \text{monto\_maximo} \le \text{limite\_diario} \le \text{limite\_mensual}$.
    - Validación preventiva en el simulador y bloqueante al formalizar transacciones de compra/venta.
- **RF-35: Operación y Liquidación de Compra y Venta de Divisas (Transaction)**
  - **Descripción:** El cliente autenticado con cliente activo asignado debe poder formalizar transacciones cambiarias aplicando tasas en vivo o congeladas, comisiones por segmento, medio de pago origen y medio de acreditación destino.
  - **Criterios de aceptación:**
    - Generación atómica con código correlativo único `TX-YYYYMMDD-XXXXX`.
    - Registro de tasa base, comisión de segmento, tasa neta, importe origen e importe destino.
    - Validación de que los instrumentos financieros pertenezcan al cliente titular de la orden.
    - Estado inicial `PENDIENTE`.
- **RF-36: Cancelación Automática por Expiración de Cotización y Anulación Manual**
  - **Descripción:** Las órdenes pendientes con cotización congelada deben cancelarse de forma automática si transcurren más de 5 minutos (300 segundos) desde su creación sin confirmación de liquidación, permitiendo asimismo su anulación manual voluntaria.
  - **Criterios de aceptación:**
    - Servicio programado o reactivo que detecta órdenes vencidas y transiciona su estado a `CANCELADA`.
    - Botón y endpoint REST para anulación manual con registro de motivo de auditoría.
    - Bloqueo de anulación sobre transacciones ya completadas.
- **RF-37: Comprobante Formal de Liquidación Cambiaria (Receipt)**
  - **Descripción:** El sistema debe generar y exponer un comprobante de liquidación cambiaria formal, imprimible y descargable con todos los datos legales y financieros de la operación.
  - **Criterios de aceptación:**
    - Layout responsivo y preparado para impresión en `/transactions/<pk>/receipt/`.
    - Presenta datos de Global Exchange, cliente, código único, sellos temporales, desglose de monedas, tasa aplicada y cuentas utilizadas.
- **RF-38: Carga Inicial de Datos y Fixtures Idempotentes (seed_data)**
  - **Descripción:** El sistema debe disponer de un comando de gestión automatizado (`python manage.py seed_data`) para poblar la base de datos con fixtures de prueba completos de todos los módulos sin intervención manual.
  - **Criterios de aceptación:**
    - Carga idempotente de usuarios, clientes, monedas, cotizaciones históricas, comisiones, entidades, medios de pago, límites y transacciones.
    - Opción `--clean` / `--reset` para reinicio completo y seguro de datos.


#### 4.3. Requerimientos No Funcionales

- **RNF-SEC-01 (Autenticación Centralizada e Integridad IAM):** La autenticación debe estar delegada en Keycloak mediante OIDC. La contraseña del usuario nunca debe transitar ni guardarse en las bases de datos de la aplicación.
- **RNF-SEC-02 (Validación Stateless y Verificación JWKS):** Cada microservicio o API Gateway debe verificar de forma independiente la firma digital (algoritmo RS256) del token JWT utilizando las claves públicas del endpoint JWKS de Keycloak.
- **RNF-SEC-03 (Protección en Tránsito y PKCE):** Comunicaciones cifradas mediante TLS 1.3 (HTTPS). Es obligatorio el uso de PKCE (_Proof Key for Code Exchange_) en el cliente frontend para proteger el flujo de autenticación.
- **RNF-SEC-04 (Aislamiento de Datos por Cliente):** Las interfaces HTML de `rates` y todas las interfaces de `payments` requieren autenticación. Los recursos de pagos deben filtrar por cliente activo para prevenir acceso horizontal no autorizado.
- **RNF-PERF-01 (Rendimiento de Validación JWT):** La verificación local del token JWT en el backend no debe exceder los 10 ms mediante el almacenamiento en memoria (_caching_) del conjunto de llaves JWKS.
- **RNF-PERF-02 (Tiempos de Respuesta de Negocio):** Actualización de tasas en pantalla $\le 2$ segundos; respuesta del cotizador $\le 3$ segundos.
- **RNF-DISP-01 (Alta Disponibilidad e Integración):** Disponibilidad garantizada del 99.9% mensual. En caso de indisponibilidad de Keycloak, los servicios protegidos responderán por defecto 503 Service Unavailable (_Fail-Closed_).
- **RNF-DAT-01 (Aritmética Financiera):** Los importes monetarios deben calcularse con `Decimal`; no se admite aritmética financiera basada en punto flotante.
- **RNF-INT-01 (API JSON):** La API de cotización y las APIs de medios de pago deben responder JSON válido, con códigos 200, 201, 400 o 404 según corresponda.
- **RNF-MAN-01 (Desacoplamiento del Cotizador):** La lógica de cálculo debe estar desacoplada en `RateCalculationService` para ser reutilizable por el cotizador y futuras transacciones.

### 5\. Requerimientos de Licencia

- **Identity Provider (IAM):** Keycloak distribuido bajo licencia Apache License 2.0 (Open Source).
- **Base de Datos:** Motor relacional Open Source (PostgreSQL o MySQL).
- **Librerías de Exportación:** Librerías Apache 2.0 / MIT (iText, ReportLab).
- **Infraestructura Cloud:** Despliegue en la nube (AWS, Azure o GCP) según acuerdos SLA.

### 6\. Observaciones

- **Dependencia Crítica del IdP:** La disponibilidad del flujo de login depende directamente del servicio de Keycloak, por lo que este debe desplegarse en un esquema redundante de alta disponibilidad.
- **Trazabilidad Normativa y Auditabilidad:** Todas las transacciones comerciales, arqueos de caja y eventos de seguridad mantendrán una correlación unívoca entre el Keycloak User ID (sub) y la base de datos fiscal SIFEN/DNIT.
- **Protección del Margen Comercial:** Bloqueo automático ante configuraciones que generen ganancia negativa (spread negativo).

### 7\. Historia de Cambios

| **Fecha**  | **Versión Física** | **Versión Lógica** | **Descripción**                                                                                                                                                                                                                                                            | **Autor**                                                        |
| ---------- | ------------------ | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 20/03/2026 | \-                 | 1.0                | Borrador inicial de la ERS.                                                                                                                                                                                                                                                | Mauricio Gonzalez, Armando Machuca, Pablo Elizeche, Felipe Rivas |
| ---        | ---                | ---                | ---                                                                                                                                                                                                                                                                        | ---                                                              |
| 16/08/2026 | \-                 | 2.0                | Implementación de la NCR v1.0. Cobertura híbrida (operaciones en efectivo y presenciales), Módulo de Cajas (RF-22 a RF-24), Clientes (RF-17), Notas de Crédito (RF-18), ampliación de monedas (RF-20), asociación de usuarios (RF-03, RF-21) y estructuración a 8 módulos. | Equipo de Ingeniería de Software / Cátedra                       |
| ---        | ---                | ---                | ---                                                                                                                                                                                                                                                                        | ---                                                              |
| 17/08/2026 | \-                 | 3.0                | Incorporación de la Nota de Cambio de Requerimientos (NCR) para Autenticación y Autorización Delegada en Keycloak IAM (OIDC, OAuth 2.0, JWT, PKCE, RBAC, Single Logout). Eliminación del almacenamiento local de contraseñas e inclusión de RF-25, RF-26 y RNF-SEC.        | Equipo de Ingeniería de Software / Cátedra                       |
| ---        | ---                | ---                | ---                                                                                                                                                                                                                                                                        | ---                                                              |
| 08/09/2026 | \-                 | 3.1                | Actualización Sprint 2 (SCRUM-42): formalización de la entidad intermedia CustomerUserAssignment (RF-21), reglas de selección y cambio de Cliente Activo en sesión (RF-04/05) e inclusión del Visualizador de Documentación Técnica Sphinx en portal web (RF-27).        | Pablo Elizeche / Equipo IS2                                      |
| ---        | ---                | ---                | ---                                                                                                                                                                                                                                                                        | ---                                                              |
| 11/09/2026 | \-                 | 3.2                | Hito 4 SCRUM 57: Gestión de monedas y tasas de cambio (RF-28), comisiones por segmento (RF-29), cotizador de tasas netas (RF-30), medios de pago (RF-31), reglas de negocio RN08-RN18 y RNF complementarios (DAT-01, SEC-04, INT-01, MAN-01).                              | Equipo IS2                                                       |
| ---        | ---                | ---                | ---                                                                                                                                                                                                                                                                        | ---                                                              |
| 24/09/2026 | \-                 | 3.3                | Hito 5 SCRUM-85: Módulo de Transacciones de Compra/Venta (RF-35), Cuentas de Acreditación (RF-32), Catálogo de Entidades Financieras (RF-33), Límites Operativos (RF-34), Cancelación y Expiración (RF-36), Comprobantes (RF-37) y Comando de Seeding (RF-38).        | Equipo IS2                                                       |