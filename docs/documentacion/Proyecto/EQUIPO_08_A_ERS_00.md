**ESPECIFICACIÓN DE REQUERIMIENTOS**

**TABLA DE CONTENIDOS**

[1\.](#_heading=h.4vkg51dvtdv9) Introducción 3

[1.1.](#_heading=h.dsm5vbono8ju) Propósito 3

[1.2.](#_heading=h.d8xqz5b4eel4) Definiciones, Acrónimos y Abreviaturas 3

[1.3.](#_heading=h.bnmm2ysnhl1g) Alcance 3

[1.4.](#_heading=h.879tj8y7s6r5) Referencias 3

[2\.](#_heading=h.ww5dvto6afee) Presentación del Producto 4

[2.1.](#_heading=h.tfkpvqen4yy2) Propósito del Sistema 4

[2.1.1.](#_heading=h.c186dgz4wv39) Objetivo: 4

[2.1.2.](#_heading=h.5wv29usang2w) Alcance: 4

[2.1.3.](#_heading=h.ucmadqroe8cw) El Sistema no contempla: 4

[2.2.](#_heading=h.43vu63a6k2q0) Restricciones y Supuestos: 4

[3\.](#_heading=h.7qnoppx0budp) Descripción General 4

[3.1.](#_heading=h.k76vncvy1zkk) Listado de la Funcionalidad del Sistema 4

[3.2.](#_heading=h.lob21rv6ilqn) Contexto del Producto 4

[3.3.](#_heading=h.vsqas929sfh7) Perspectivas futuras del producto 5

[3.4.](#_heading=h.cqa3isbl2v74) Reglas y Funciones de Negocio 5

[4\.](#_heading=h.rzu6z58f25lg) Descripción Detallada de Requerimientos 5

[4.1.](#_heading=h.x29vhtjzhlb8) Actores 5

[4.2.](#_heading=h.apoo88xpp94e) Requerimientos Funcionales 5

[Diagrama/s de Caso de Uso 5](#_heading=h.wtx20ycp9guq)

[Listado de Casos de Uso 5](#_heading=h.9vz91lyzwp48)

[Requerimientos funcionales 5](#_heading=h.6k3c67irwukg)

[4.3.](#_heading=h.rmaiiyk7xw2t) Requerimientos No Funcionales 6

[5\.](#_heading=h.ei1s5hn8q1d1) Requerimientos de Licencia 6

[6\.](#_heading=h.3ewtj2aj13ie) Observaciones 6

[7\.](#_heading=h.9umy4tjco2vv) Historia de Cambios 6

# Introducción

## Propósito

_El presente documento constituye la Especificación de Requerimientos de Software (ERS) para el sistema de gestión digital de la casa de cambio_ **_Global Exchange_**_. Su propósito es describir de manera formal, completa y sin ambigüedades los requerimientos funcionales y no funcionales que deberá cumplir el software a desarrollar, sirviendo como referencia principal entre el equipo de desarrollo y los interesados del proyecto._

_Este documento representa un modelo del problema bajo consideración y define el conjunto de funciones, restricciones y comportamientos esperados del sistema, constituyendo la base para las etapas de diseño, implementación, pruebas y validación del producto._

## Definiciones, Acrónimos y Abreviaturas

| **_Término_**           | **_Definición_**                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| _ERS_                   | _Especificación de Requerimientos de Software_                                           |
| ---                     | ---                                                                                      |
| _RF_                    | _Requerimiento Funcional_                                                                |
| ---                     | ---                                                                                      |
| _RNF_                   | _Requerimiento No Funcional_                                                             |
| ---                     | ---                                                                                      |
| _Casa de Cambio_        | _Entidad financiera dedicada a la compra y venta de divisas extranjeras_                 |
| ---                     | ---                                                                                      |
| _Divisa_                | _Moneda extranjera utilizada en transacciones financieras internacionales_               |
| ---                     | ---                                                                                      |
| _Tasa de Cambio_        | _Valor al que una moneda puede ser cambiada por otra_                                    |
| ---                     | ---                                                                                      |
| _Transacción_           | _Operación de compra o venta de divisas registrada en el sistema_                        |
| ---                     | ---                                                                                      |
| _Factura Electrónica_   | _Documento fiscal digital generado automáticamente por el sistema tras cada transacción_ |
| ---                     | ---                                                                                      |
| _Billetera Electrónica_ | _Medio de pago digital que permite almacenar y transferir fondos de forma virtual_       |
| ---                     | ---                                                                                      |
| _Cliente Minorista_     | _Persona física que realiza operaciones de cambio de manera individual_                  |
| ---                     | ---                                                                                      |
| _Cliente Corporativo_   | _Empresa o persona jurídica que opera con el sistema_                                    |
| ---                     | ---                                                                                      |
| _Cliente VIP_           | _Categoría especial de cliente con condiciones preferenciales_                           |
| ---                     | ---                                                                                      |
| _Usuario Asociado_      | _Usuario del sistema vinculado a uno o más perfiles de cliente_                          |
| ---                     | ---                                                                                      |
| _Usuario No Asociado_   | _Usuario registrado en el sistema sin vinculación a un cliente_                          |
| ---                     | ---                                                                                      |
| _Administrador_         | _Perfil con acceso completo a la configuración y administración del sistema_             |
| ---                     | ---                                                                                      |
| _Analista Cambiario_    | _Perfil operativo con permisos para gestionar tasas y monitorear ganancias_              |
| ---                     | ---                                                                                      |
| _IS1_                   | _Ingeniería de Software 1_                                                               |
| ---                     | ---                                                                                      |

## Alcance

Este documento abarca exclusivamente la especificación detallada de los requerimientos funcionales y no funcionales para la construcción del sistema de gestión digital de la casa de cambio Global Exchange. El alcance de este documento cubre la definición de las reglas de negocio, los actores involucrados y las restricciones técnicas necesarias para el proyecto. Es de aplicación directa y obligatoria para el equipo de desarrollo de software responsable de la implementación, sirviendo como contrato técnico fundamental. Asimismo, está dirigido a los docentes evaluadores del proyecto en el marco de la asignatura Ingeniería de Software 1 (IS1), y a cualquier otra parte interesada involucrada en las fases de diseño, prueba y validación del sistema.

## Referencias

| **Archivo de Documento** | **Título del Documento**                                             | **Organización que lo Publica**       |
| ------------------------ | -------------------------------------------------------------------- | ------------------------------------- |
| _Enunciado_IS1_2026.pdf_ | _Enunciado del Trabajo Práctico – Ingeniería de Software I 2026_     | _Cátedra de Ingeniería de Software I_ |
| ---                      | ---                                                                  | ---                                   |
| _Plantilla_ERS.docx_     | _Plantilla de Especificación de Requerimientos de Software_          | _Cátedra de Ingeniería de Software I_ |
| ---                      | ---                                                                  | ---                                   |
| _IEEE Std 830-1998_      | _IEEE Recommended Practice for Software Requirements Specifications_ |                                       |
| ---                      | ---                                                                  | ---                                   |

# Presentación del Producto

## Propósito del Sistema

### Objetivo

_El objetivo de este sistema es modernizar la casa de cambio "Global Exchange", transformándola de un modelo operativo tradicional basado en sucursales físicas a una plataforma digital moderna, segura, rápida, accesible y confiable. El sistema permitirá a los clientes gestionar sus operaciones cambiarias a través de internet, mejorando su experiencia mediante la disponibilidad de servicios en tiempo real y la automatización de procesos financieros._

### Alcance

_El producto de software abarcará los siguientes módulos y funcionalidades principales:_

- _Gestión de Usuarios y Clientes: Auto-registro en línea con verificación por correo electrónico, segmentación de clientes (minoristas, corporativos, VIP) y asociación de múltiples usuarios a clientes para operar en su nombre._
- _Operaciones de Divisas: Visualización de tasas de cambio en tiempo real con gráficos de evolución, simuladores de conversión y ejecución de operaciones de compra y venta de divisas de manera 100% digital._
- _Transacciones y Pagos: Integración de múltiples métodos de pago digitales, acreditación o retiro automatizado hacia billeteras electrónicas o cuentas bancarias, y gestión de estados de transacción (Pendiente, Pagada, Cancelada, Anulada)._
- _Reportes y Facturación Electrónica: Generación y descarga de historial de transacciones en PDF o Excel, emisión de facturas electrónicas con trazabilidad de estados (Emitida, Aprobada, Rechazada) y envío automatizado por correo electrónico._
- _Administración, Monitoreo y Configuración: Panel de control para el ajuste manual de tasas, gestión de monedas admitidas (USD, EUR, PYG, BRL, etc.), monitoreo de ganancias en tiempo real (global y por moneda), envío de notificaciones, y manejo de roles de acceso (Administrador, Analista cambiario)_

### El Sistema no contempla

- **_Gestión operativa de sucursales físicas:_** _El sistema no incluye módulos para arqueo de caja físico, gestión de tesorería (conteo o traslado de billetes físicos), logística de transporte de caudales, ni control de asistencia del personal de atención en sucursal. Todo el enfoque es 100% digital._
- _Un módulo de contabilidad general o recursos humanos para la casa de cambio; el sistema se limitará al registro de ganancias por operaciones cambiarias y la facturación de las mismas._
- _Otorgamiento de créditos, préstamos o servicios financieros ajenos a la compra y venta de divisas._

## Restricciones y Supuestos

- **Supuestos:** Se asume que los clientes disponen de cuentas bancarias o billeteras electrónicas válidas y operativas de terceros para operar. Se da por hecho que los usuarios tienen conexión a internet y un correo electrónico activo.
- **Restricciones de Negocio:**
  - **Restricción de Edad:** El sistema validará estrictamente que todo usuario registrado o cliente asociado sea mayor de 18 años de edad para poder operar en la plataforma.
- **Restricciones Legales/Técnicas:**
  - **Facturación SIFEN:** El módulo de facturación electrónica deberá ceñirse estrictamente a los estándares técnicos, manuales y diccionarios de datos exigidos por el Sistema Integrado de Facturación Electrónica Nacional (SIFEN) de la DNIT.

# Descripción General

## Listado de la Funcionalidad del Sistema

- Registro y validación de identidad de nuevos usuarios.
- Visualización de tasas de cambio en tiempo real y gráficos de evolución histórica.
- Simulación de conversión de divisas.
- Asociación y gestión de múltiples perfiles de clientes para un mismo usuario.
- Ejecución de operaciones de compra y venta de divisas de forma digital.
- Procesamiento de pagos digitales con múltiples medios de pago.
- Generación automática y envío de facturas electrónicas por correo electrónico.
- Exportación del historial de transacciones en formatos PDF y Excel.
- Monitoreo de ganancias en tiempo real (global y por tipo de moneda).
- Envío de notificaciones sobre actualizaciones en las tasas de cambio.
- Módulo de configuración para administrar monedas, tasas, métodos de pago y seguridad.

## Contexto del Producto

El producto es una plataforma digital para la casa de cambio Global Exchange que **opera en estrecha dependencia e integración con sistemas de terceros**. Específicamente, el ecosistema del producto depende de:

1. **Entidades Financieras y Pasarelas de Pago:** Para la acreditación de fondos y el procesamiento de cobros digitales.
2. **Ente Tributario (DNIT):** Integración obligatoria con los servicios web gubernamentales para la firma, envío, validación y retorno de estado (Aprobada/Rechazada) de los Documentos Tributarios Electrónicos (DTE). El sistema actuará como el núcleo central que orquesta estas integraciones para proveer una experiencia unificada al cliente.

## Perspectivas futuras del producto

No aplican por el momento

## Reglas y Funciones de Negocio

- Los clientes pueden ser clasificados como minoristas, corporativos o VIP, y pueden ser personas físicas o jurídicas.
- Un usuario debe estar asociado a al menos un cliente para poder realizar operaciones de compra o venta de divisas.
- Los usuarios sin asociación a un cliente tienen restringidas sus acciones únicamente a la consulta de tasas y su evolución.
- Si un usuario está asociado a múltiples clientes, es obligatorio que seleccione en nombre de qué cliente operará antes de realizar cualquier acción.
- Una transacción adquiere el estado "pendiente" hasta ser pagada o cancelada.
- Una transacción únicamente puede ser "anulada" si previamente se ha realizado el pago de la misma.
- Las facturas electrónicas pueden tener los estados: emitidas, aprobadas o rechazadas.

# Descripción Detallada de Requerimientos

## Actores

## Requerimientos Funcionales

- **RF01:** El sistema deberá permitir el auto-registro de usuarios mediante un formulario web. El formulario exigirá obligatoriamente los siguientes datos: _Nombre Completo, Cédula de Identidad, Fecha de Nacimiento (aplicando la restricción de >18 años), Correo Electrónico y Contraseña._

**RF01.1 (Flujo de Registro y Validación):** La cadena de registro seguirá el siguiente flujo exacto:

1. El usuario completa y envía el formulario.
2. El sistema valida en la base de datos que el Correo Electrónico y la Cédula no se encuentren registrados previamente.
3. El sistema crea el registro del usuario con el estado inicial "Inactivo".
4. El sistema genera un _token_ único de un solo uso y envía automáticamente un enlace de verificación al correo del usuario (con una validez máxima de 24 horas).
5. Al hacer clic en el enlace, el sistema cambia el estado del usuario a "Activo" y lo redirige a la pantalla de inicio de sesión.

- **RF03: Solicitud y Validación de Representación de Personas Jurídicas:** Como parte del flujo de auto-registro (o en el panel de control del usuario recién registrado), el sistema deberá permitir al usuario especificar y solicitar la vinculación a una o más Personas Jurídicas (empresas) para operar en su nombre. Esta vinculación estará sujeta a una validación estricta de identidad corporativa vía correo electrónico.
- **Datos requeridos en la solicitud:** RUC de la entidad, Razón Social, Cargo/Rol del solicitante, y Correo Electrónico oficial de la empresa o del Representante Legal.
- **Reglas de negocio:** Un usuario no podrá visualizar fondos, simular ni ejecutar operaciones en nombre de la empresa hasta que la solicitud de asociación cambie al estado "Aprobada". Por seguridad, el enlace de validación enviado por correo tendrá una expiración máxima de 48 horas.
- **Flujo exacto de validación:**
  - - El usuario ingresa al módulo de "Asociación de Entidades" y selecciona "Solicitar representación de Persona Jurídica".
      - El usuario ingresa el RUC, la Razón Social y el correo de contacto de la entidad.
      - El sistema crea una solicitud de vinculación en la base de datos con el estado **"Pendiente de Autorización"**.
      - El sistema genera y envía automáticamente un correo electrónico a la dirección corporativa de la entidad. Este correo debe contener: _Nombre completo y Cédula del usuario solicitante, un resumen de los permisos que obtendrá, y dos botones de acción con enlaces tokenizados de un solo uso ("Aprobar Representación" y "Rechazar")._
      - El receptor del correo corporativo (Representante Legal o Gerencia) revisa los datos y hace clic en "Aprobar Representación".
      - El sistema recibe la confirmación, cambia el estado de la vinculación a **"Activa"** y envía un correo notificando al usuario que ya está habilitado para operar en nombre de la Persona Jurídica.
- **RF04 y RF05: Selección y Cambio de Cliente Activo:** Gestión de contexto de sesión para usuarios vinculados a múltiples clientes (ej. un contador que maneja varias empresas).
  - **Regla de interfaz:** Si el usuario tiene más de un cliente asociado, al iniciar sesión el sistema desplegará un _modal_ obligatorio para seleccionar la cuenta a operar.
  - **Flujo:** El sistema mantendrá un selector visible en la barra de navegación superior (Header) que permitirá al usuario cambiar de cliente sin necesidad de cerrar sesión.
- **RF06: Evolución de Tasas de Cambio:** El sistema mostrará un _Dashboard_ con gráficos de velas o líneas para las monedas habilitadas.
  - **Filtros de tiempo obligatorios:** El usuario podrá filtrar el histórico de la tasa en rangos de: 24 horas, 7 días, 30 días y 1 año.
  - **Datos mostrados:** Eje X (Fecha/Hora), Eje Y (Valor de la divisa frente a la moneda local).
- **RF07: Simulación de Conversión (Cotizador):** Herramienta interactiva previa a la transacción.
  - **Flujo:** 1) Usuario selecciona "Moneda Origen" y "Moneda Destino". 2) Ingresa el "Monto". 3) El sistema calcula en tiempo real usando la tasa vigente.
  - **Regla crítica:** Al hacer clic en "Ejecutar Operación", el sistema "congelará" la tasa de cambio cotizada durante un máximo de **5 minutos** para que el usuario complete el pago sin sufrir fluctuaciones.
- **RF08 y RF09: Procesamiento de Pagos y Acreditación:** Ejecución de la compra/venta y movimiento de fondos.
  - **Flujo de Compra de Divisas:**
    - El usuario acepta la cotización del RF07.
    - El sistema despliega los métodos de pago (Ej: Transferencia Bancaria SIPAP, Tarjeta de Crédito, Billetera Tigo/Zimple).
    - El usuario realiza el pago mediante la pasarela integrada.
    - El sistema recibe el _Webhook_ (confirmación) de pago exitoso de la pasarela.
    - El sistema ejecuta la API del banco/billetera del cliente para acreditarle automáticamente las divisas compradas.
- **RF10: Máquina de Estados de la Transacción:** Toda operación generará un código de seguimiento y transitará por estados estrictos.
- **Transiciones permitidas:**
  - - **Pendiente:** Creada, esperando pago (expira a los 5 minutos).
      - **Pagada/Completada:** Pago confirmado y fondos acreditados.
      - **Cancelada:** El pago falló o el tiempo expiró.
      - **Anulada:** Solo ejecutable por el Administrador sobre una operación "Pagada" (implica un proceso manual de reverso de fondos).
- **RF11: Exportación de Historial:** Descarga de reportes por parte del cliente.
- **Datos obligatorios a exportar:** ID Transacción, Fecha/Hora, Tipo (Compra/Venta), Moneda, Tasa Aplicada, Monto Total, Método de Pago y Estado. Formatos: PDF y CSV/Excel.
- **RF12: Facturación Electrónica (SIFEN/DNIT):** Tras pasar la transacción al estado "Pagada", el sistema compilará el XML con el Documento Tributario Electrónico (DTE) y lo enviará al SIFEN.
- **Estados de Factura:** "Emitida" (Enviada a DNIT), "Aprobada" (Sello recibido), "Rechazada" (Error en DNIT).
- **Acción:** Una vez "Aprobada", se envía automáticamente el KuDE (representación gráfica en PDF) al correo del cliente.
- **RF13: Monitoreo de Ganancias (Spread):** Panel exclusivo para Administradores y Analistas.
  - **Cálculo:** El sistema calculará la ganancia de cada operación basada en la diferencia (_Spread_) entre el costo de adquisición de la casa de cambio y la tasa de venta al cliente. Mostrará totales diarios y mensuales por divisa (USD, EUR, BRL).
- **RF14: Notificaciones de Mercado:** Alertas automáticas o manuales.
  - **Regla:** El cliente podrá configurar "Alertas de Precio". Ej: "Avisarme al correo si el Dólar baja de 7.200". El sistema disparará el correo automáticamente al cumplirse la condición.
- **RF15: Módulo de Configuración Base:** Interfaz CRUD (Crear, Leer, Actualizar, Borrar) para el Administrador.
  - **Funciones:** Habilitar/Deshabilitar pares de monedas, encender/apagar métodos de pago por mantenimiento, y configurar márgenes mínimos de seguridad para evitar ventas a pérdida.
- **RF16: Permisos del Analista Cambiario (Empleado):** Delimitación estricta de roles.
  - **Permisos habilitados:** Actualizar manualmente las tasas de cambio de pizarra, visualizar transacciones en curso y ver el panel de ganancias.
  - **Permisos denegados:** No podrá anular transacciones, no podrá crear usuarios internos, ni modificar parámetros del sistema. Toda actualización de tasa registrará su ID de usuario y _timestamp_ por auditoría.

## Requerimientos No Funcionales

**RNF01: Rendimiento y Tiempos de Respuesta** Este requerimiento reemplaza la ambigüedad de mostrar datos en "tiempo real".

- El sistema deberá actualizar los valores de las tasas de cambio en la interfaz del usuario con un retraso máximo de 2 segundos desde el momento en que son modificadas en la base de datos.
- El tiempo de respuesta del servidor para calcular y devolver la simulación de una conversión de divisas no deberá superar los 3 segundos bajo condiciones de tráfico normal.
- La pantalla del panel de monitoreo de ganancias deberá cargar la información consolidada en un tiempo máximo de 5 segundos.

**RNF02: Seguridad y Estándares de Accesibilidad** Este requerimiento detalla lo que significa ser una plataforma "moderna, segura, rápida y accesible".

- Todas las comunicaciones entre el navegador del cliente y los servidores del sistema deberán estar cifradas utilizando el protocolo TLS 1.2 o superior (HTTPS).
- Las contraseñas de los usuarios se almacenarán obligatoriamente en la base de datos utilizando algoritmos de hash criptográfico unidireccional (como bcrypt o Argon2), prohibiendo el almacenamiento en texto plano.
- La interfaz web debe tener un diseño adaptable (Responsive Web Design) para funcionar correctamente en dispositivos móviles y de escritorio.
- La plataforma deberá cumplir con las pautas de accesibilidad web WCAG 2.1 (Nivel AA) para garantizar su uso por personas con discapacidades visuales o motrices.

**RNF03: Disponibilidad, Integración y Estándares de Documentos** Este requerimiento define las reglas exactas para la generación automática de reportes y facturas.

- El módulo de facturación deberá generar y estructurar los documentos en formato XML, cumpliendo estrictamente con el manual técnico y el diccionario de datos vigente del Sistema Integrado de Facturación Electrónica Nacional (SIFEN) de la DNIT.
- Los reportes del historial de transacciones exportados por el usuario deberán generarse en formato PDF estándar (legible por cualquier visor moderno) y formato CSV con codificación UTF-8.
- El sistema web deberá garantizar una disponibilidad (Uptime) del 99.9% mensual, excluyendo las ventanas de mantenimiento programadas y notificadas previamente a los usuarios.

# Requerimientos de Licencia

- 1. **Motor de Base de Datos:** Se utilizará un sistema gestor de bases de datos de código abierto (por ejemplo, PostgreSQL o MySQL) bajo licencia Open Source, por lo que no incurrirá en costos de licenciamiento comercial.
  2. **Generación de Documentos (PDF y Excel):** Para cumplir con la exportación del historial de transacciones, se emplearán librerías de uso libre (como iText para Java o ReportLab para Python) bajo sus respectivas licencias permisivas (MIT o Apache 2.0).
  3. **Infraestructura y Hosting:** El despliegue del sistema digital moderno requerirá servicios en la nube (ej. AWS, Google Cloud o Microsoft Azure), sujetos a los acuerdos de nivel de servicio (SLA) y facturación por consumo del proveedor elegido.

# Observaciones

- Dependencia de Sistemas Externos (APIs): El éxito de las operaciones digitales de la plataforma depende en gran medida de la disponibilidad y correcto funcionamiento de pasarelas de pago externas y servicios bancarios. Además, la facturación electrónica requerirá muy probablemente la integración con los servicios web del ente tributario nacional (SET/DNIT u homólogo) para la validación y cambio de estado de las facturas (Aprobada/Rechazada). Se debe prever un manejo robusto de errores en caso de caída de estos servicios externos.
- ​Seguridad y Prevención de Fraudes Internos: Dado que el sistema permite la manipulación manual de las tasas de cambio por parte de los empleados (Analista cambiario), es imperativo que el sistema de auditoría interna (logs) registre qué usuario, en qué fecha y a qué hora exacta modificó una tasa. Esto es vital para evitar irregularidades financieras y garantizar la transparencia exigida por el negocio.
- ​Volatilidad y Concurrencia de Datos: La naturaleza del mercado cambiario exige que las tasas de cambio se muestren en "tiempo real" y fluctúen constantemente. El equipo de desarrollo debe considerar una arquitectura que soporte alta concurrencia (múltiples clientes consultando y simulando transacciones al mismo tiempo) sin que el sistema se ralentice ni muestre información desactualizada al momento de concretar un pago.
- ​Validaciones de Negocio Estrictas: Tal como se debatió en las definiciones de negocio, el sistema no debe permitir bajo ninguna circunstancia que la configuración de tasas preferenciales (para clientes VIP o corporativos) resulte en un margen de ganancia negativo para la casa de cambio en comparación con su costo de adquisición de la divisa.
- ​Trazabilidad Legal: Al ser una plataforma que maneja compra y venta de divisas de forma digital, el registro de usuarios (que incluye la validación de identidad por correo) y la asociación a clientes físicos o jurídicos podría estar sujeta en el futuro a normativas legales de prevención de lavado de dinero (KYC/AML). El modelo de datos debe estar preparado para escalar e incorporar carga de documentos de identidad si la legislación lo requiere más adelante.

# Historia de Cambios

| **Fecha**  | **Versión Física** | **Versión Lógica** | **Descripción** | **Autor**                                                                          |
| ---------- | ------------------ | ------------------ | --------------- | ---------------------------------------------------------------------------------- |
| 20/03/2004 |                    | 1.0                | Borrador        | Mauricio Gonzalez<br><br>Armando Machuca<br><br>Pablo Elizeche<br><br>Felipe Rivas |
| ---        | ---                | ---                | ---             | ---                                                                                |