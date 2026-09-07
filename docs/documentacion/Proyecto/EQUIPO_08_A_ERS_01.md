# ESPECIFICACIÓN DE REQUERIMIENTOS DE SOFTWARE (ERS v3.0)

**Proyecto:** Global Exchange – Casa de Cambio Digital e Híbrida

**Estado:** Documento Consolidado (ERS v2.0 + NCR Keycloak IAM)

**Fecha de Actualización:** 17 de Agosto de 2026

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

#### 3.2. Contexto del Producto

El núcleo central omnicanal interactúa con:

- **Keycloak IAM Server:** Proveedor de identidad que autentica usuarios y emite tokens JWT / JWKS.
- **Entidades Financieras / Billeteras:** Procesamiento digital de fondos.
- **Servicio Externo SIFEN / DNIT:** Validación tributaria de comprobantes.
- **Terminales de Caja Presenciales:** Estaciones de ventanilla para operadores de caja.

#### 3.3. Perspectivas futuras del producto

No aplican por el momento.

#### 3.4. Reglas y Funciones de Negocio

- **RN01 (Autenticación Delegada):** Todo usuario debe autenticarse exclusivamente en Keycloak para obtener un token JWT válido.
- **RN02 (Autorización por Token):** Cualquier petición enviada al backend/gateway debe adjuntar un token JWT en el encabezado Authorization: Bearer &lt;token&gt;. Peticiones sin token o con token inválido/expirado serán rechazadas con HTTP 401 Unauthorized o 403 Forbidden.
- **RN03 (Asignación Administrativa de Clientes):** La vinculación entre el identificador de Keycloak (sub) y los perfiles de Clientes (físicos o jurídicos) es realizada únicamente por el Administrador.
- **RN04 (Operatividad por Cliente):** Para transaccionar, el usuario autenticado debe seleccionar un cliente activo al que esté vinculado.
- **RN05 (Gestión de Cajas):** Las operaciones de cobro o entrega de efectivo exigen que el usuario posea una caja en estado "Abierta" y cuente con el rol Cajero en su token JWT.
- **RN06 (Expiración de Cotización):** Cotizaciones en estado "Pendiente" expiran tras 5 minutos sin confirmación de pago.
- **RN07 (Anulaciones y Notas de Crédito):** Toda transacción "Pagada" que sea anulada requiere la emisión obligatoria de una Nota de Crédito Electrónica.

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
- **RF04 y RF05: Selección y Cambio de Cliente Activo**
  - **Descripción:** Tras autenticarse vía Keycloak, si el usuario posee múltiples clientes asignados, se despliega un selector obligatorio para determinar sobre cuál cuenta operará en la sesión.
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
- **RF-21: Módulo Administrativo para Asociación de Usuarios a Clientes**
  - **Descripción:** Interfaz para asociar uno o más usuarios de Keycloak a una cuenta de Cliente.
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

#### 4.3. Requerimientos No Funcionales

- **RNF-SEC-01 (Autenticación Centralizada e Integridad IAM):** La autenticación debe estar delegada en Keycloak mediante OIDC. La contraseña del usuario nunca debe transitar ni guardarse en las bases de datos de la aplicación.
- **RNF-SEC-02 (Validación Stateless y Verificación JWKS):** Cada microservicio o API Gateway debe verificar de forma independiente la firma digital (algoritmo RS256) del token JWT utilizando las claves públicas del endpoint JWKS de Keycloak.
- **RNF-SEC-03 (Protección en Tránsito y PKCE):** Comunicaciones cifradas mediante TLS 1.3 (HTTPS). Es obligatorio el uso de PKCE (_Proof Key for Code Exchange_) en el cliente frontend para proteger el flujo de autenticación.
- **RNF-PERF-01 (Rendimiento de Validación JWT):** La verificación local del token JWT en el backend no debe exceder los 10 ms mediante el almacenamiento en memoria (_caching_) del conjunto de llaves JWKS.
- **RNF-PERF-02 (Tiempos de Respuesta de Negocio):** Actualización de tasas en pantalla \$\\le 2\$ segundos; respuesta del cotizador \$\\le 3\$ segundos.
- **RNF-DISP-01 (Alta Disponibilidad e Integración):** Disponibilidad garantizada del 99.9% mensual. En caso de indisponibilidad de Keycloak, los servicios protegidos responderán por defecto 503 Service Unavailable (_Fail-Closed_).

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