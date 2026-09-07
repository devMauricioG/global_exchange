**NOTA DE CAMBIO DE REQUERIMIENTOS (NCR)**

**Proyecto:** Global Exchange – Casa de Cambio Digital e Híbrida

**Documento Base:** Especificación de Requerimientos de Software (ERS v1.0)

**Documento de Referencia:** Nuevo Enunciado para Casa de Cambio Digital e Integración de Seguridad IAM con Keycloak

**1\. Requerimientos Nuevos**

- **RF-17. Registro y Mantenimiento de Clientes**
  - **Descripción:** El sistema contará con un módulo administrativo para el registro, actualización y segmentación de datos de clientes (minoristas, corporativos o VIP). Cada cliente estará vinculado en la base de datos de negocio al identificador de usuario único (sub) asignado por Keycloak.
  - **Justificación:** Permite gestionar la información comercial y legal de clientes de forma independiente, desacoplándola de la gestión de identidades y credenciales de acceso.
- **RF-18. Emisión de Documentos Electrónicos – Notas de Crédito**
  - **Descripción:** Generación, compilación XML y emisión automática de Notas de Crédito Electrónicas integradas con la API de SIFEN/DNIT para vinculación con transacciones anuladas o ajustadas.
  - **Justificación:** Ampliación del alcance de facturación electrónica especificando la emisión de facturas y notas de crédito.
- **RF-19. Configuración de Operaciones Admitidas**
  - **Descripción:** Habilitación o deshabilitación independiente de los tipos de operaciones ofrecidas (compra, venta en efectivo o saldo virtual) por parte del Administrador.
  - **Justificación:** Requerimiento explícito del Módulo de Configuraciones para brindar flexibilidad operativa al negocio.
- **RF-20. Ampliación del Catálogo de Monedas Admitidas**
  - **Descripción:** Gestión nativa de monedas regionales e internacionales adicionales (USD, EUR, PYG, BRL, ARS y GBP).
  - **Justificación:** Soporte explícito a una oferta extendida de divisas clave del mercado cambiario.
- **RF-21. Módulo Administrativo para Asociación de Usuarios a Clientes**
  - **Descripción:** Interfaz exclusiva para el Administrador que le permite seleccionar un cliente registrado y asociarle uno o más usuarios autenticados en Keycloak mediante su _User ID_ (sub).
  - **Justificación:** Centralización de la gestión de permisos de representación corporativa y legal desde la administración del sistema.
- **RF-22. Apertura y Asignación de Cajas Presenciales**
  - **Descripción:** El Cajero realizará la Apertura de Caja registrando el fondo inicial por divisa. Para habilitar la estación de trabajo, el sistema validará que el usuario cuente con una sesión activa y un token JWT emitido por Keycloak con el rol Cajero.
  - **Justificación:** Requerimiento operativo para respaldar el cobro y entrega de dinero físico en ventanilla bajo autorización explícita.
- **RF-23. Cierre y Arqueo de Caja Físico**
  - **Descripción:** Ejecución del cierre de caja al finalizar el turno con la declaración del conteo físico de billetes, cálculo automático del saldo esperado y emisión del reporte de arqueo.
  - **Justificación:** Requerimiento fundamental para el control contable, la conciliación diaria y la prevención de irregularidades en ventanilla.
- **RF-24. Auditoría y Monitoreo de Movimientos de Caja**
  - **Descripción:** Registro inmutable de operaciones de caja asociando el Keycloak User ID, marca temporal (_timestamp_), ID de transacción y estación de trabajo para consulta de auditores y administradores.
  - **Justificación:** Garantiza trazabilidad legal y control interno de operaciones con dinero en efectivo.
- **RF-25. Autenticación Centralizada y Autorización Stateless (Keycloak IAM)**
  - **Descripción:** Integración de **Keycloak** como Proveedor de Identidad (IdP) único. La autenticación se realizará mediante OpenID Connect (_Authorization Code Flow con PKCE_) y la autorización en el backend/gateway se resolverá evaluando las _claims_ de roles contenidos en el token JWT.
  - **Justificación:** Establece un estándar robusto de ciberseguridad que desacopla la autenticación de la lógica de negocio y evita almacenar contraseñas en la aplicación.

**2\. Requerimientos Cambiados**

- **Sección 2.1.3 (Restricciones del Sistema)**
  - **Versión original:** Modelo 100% digital que prohíbe el manejo de efectivo, arqueos y sucursales.
  - **Versión modificada:** Se excluyen únicamente la logística de caudales, el control biométrico de RRHH y la contabilidad general. Se incluye formalmente la gestión de cajas presenciales, recepción/entrega de dinero físico por cajeros, arqueo, apertura y cierre.
- **RF03. Asignación de Representación de Clientes desde la Administración**
  - **Versión original:** Auto-solicitud de representación por parte del usuario con validación por token vía correo (expiración de 48 horas).
  - **Versión modificada:** Vinculación directa desde el panel administrativo relacionando la entidad Cliente con el usuario de Keycloak (Keycloak User ID).
- **RF06. Visualización Gráfica de la Evolución de Tasas**
  - **Versión original:** Gráficos de velas o líneas con rangos estrictos de 24h, 7d, 30d y 1 año.
  - **Versión modificada:** Sección gráfica interactiva mediante gráficos de líneas o barras con filtros de periodo por día, semana, mes y año.
- **RF08 y RF09. Procesamiento Híbrido de Operaciones Cambiarias**
  - **Versión original:** Cobro y acreditación 100% digitales mediante integraciones bancarias o billeteras.
  - **Versión modificada:** Operatoria omnicanal que permite pagar o recibir divisas tanto en efectivo en ventanilla (vía Cajero) como a través de transferencias en cuentas bancarias o billeteras virtuales.
- **RF14. Notificaciones sobre Actualizaciones de Tasas de Cambio**
  - **Versión original:** Alertas de precio configuradas exclusivamente por el cliente.
  - **Versión modificada:** Envíos automáticos de notificaciones informando las fluctuaciones de tasas efectuadas por la casa de cambio, manteniendo la opción de alertas configurables.
- **RF15. Módulo de Configuración General**
  - **Versión original:** CRUD de monedas, métodos de pago y márgenes de seguridad.
  - **Versión modificada:** Panel de administración integral para: 1) Monedas; 2) Operaciones admitidas; 3) Tasas manuales; 4) Métodos de pago (incluyendo efectivo); y 5) Parámetros de conexión con Keycloak (URL del Realm, Client ID, Client Secret, tiempo de vida del JWT y endpoint de llaves publicas JWKS).
- **RF16. Permisos y Delimitación de Roles Operativos (Keycloak RBAC)**
  - **Versión original:** Delimitación de roles interna sin estándar de autenticación definido.
  - **Versión modificada:** Asignación y control de accesos centralizado en Keycloak mediante _Realm Roles_:
    - **Administrador:** Configuración global, parámetros Keycloak y asociación de usuarios a clientes.
    - **Analista Cambiario:** Actualización de tasas de pizarra, monitoreo de ganancias y transacciones en curso. Sin acceso a cobro en ventanilla.
    - **Cajero:** Apertura/cierre de caja, cobro/entrega de efectivo presencial y arqueo. Prohibido modificar tasas de cambio o configuraciones.
    - **Cliente:** Solicitud de operaciones de cambio y consulta de comprobantes.
- **Sección 2.1.2 (Alcance del Producto)**
  - **Versión original:** Definición estructurada en 5 bloques generales.
  - **Versión modificada:** Cobertura organizada en 8 módulos mínimos obligatorios: 1. Gestión de Usuarios, Autenticación OIDC y Autorización RBAC (Keycloak IAM) 2. Gestión de Clientes 3. Gestión de Operaciones Cambiarias Híbridas (Físicas y Virtuales) 4. Gestión de Cajas y Cajeros (Apertura, Arqueo, Cierre y Auditoría) 5. Gestión de Documentos Electrónicos (Facturas y Notas de Crédito SIFEN) 6. Reportes y Gráficos para Monitoreo 7. Notificaciones 8. Configuraciones Generales

**3\. Requerimientos Eliminados**

- **Prohibición de Manejo de Efectivo y Arqueo de Caja Físico:** Se descarta la restricción de operar bajo un modelo exclusivamente digital para habilitar la atención en ventanilla.
- **Flujo de Auto-solicitud de Representación mediante Token de Correo:** Eliminado al transferir la responsabilidad de asignación al perfil Administrador.
- **Almacenamiento Local de Credenciales y Hash de Contraseñas:** Se prohíbe el guardado de claves en la base de datos propia de la aplicación, delegando el 100% de la gestión de credenciales y seguridad a Keycloak.