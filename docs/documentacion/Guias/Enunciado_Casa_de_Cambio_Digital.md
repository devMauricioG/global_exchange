# Enunciado para el Proyecto de la Materia de Ingeniería de Software 1-2026

## Global Exchange

Juan Pérez siempre había soñado con modernizar su negocio. Durante años, su casa de cambio, Global Exchange, había operado de manera tradicional: clientes que llegaban con billetes en mano, empleados verificando las tasas de cambio en pizarras y largas filas para realizar una simple transacción.

Sin embargo, Juan entendía que los tiempos habían cambiado. Cada vez más clientes preferían gestionar sus operaciones desde internet, sin necesidad de desplazarse a una sucursal. Querían consultar tasas en tiempo real, comprar y vender divisas de forma digital y recibir sus fondos directamente en una billetera electrónica o cuenta bancaria.

Uno de los mayores desafíos de Juan era la constante fluctuación de las tasas de cambio. A diario, recibía múltiples llamadas de clientes ansiosos por saber si el valor del dólar había subido o bajado. Para mejorar la experiencia del usuario, el sistema debía mostrar las tasas en tiempo real y permitir simulaciones de conversión antes de concretar una operación de compra o venta. Además, Juan necesitaba la flexibilidad de ajustar manualmente las tasas según la estrategia de su negocio.

Para garantizar una experiencia completamente digital, los clientes debían poder comprar y vender divisas. El proceso debía ser simple: elegir la moneda, ingresar el monto y recibir la confirmación de la transacción al instante. Si adquirían divisas, los fondos se acreditarían automáticamente en su billetera electrónica o cuenta bancaria. Si, en cambio, vendían divisas, se podría retirar el dinero de una cuenta bancaria o billetera digital. Juan también quería segmentar a los clientes en diferentes categorías, como minoristas, corporativos y VIP. Los clientes podrían ser personas físicas o jurídicas.

Los usuarios del sistema podrían auto registrarse a través de un formulario en línea y se validará la identidad del usuario mediante un correo de verificación.

Desde la administración del sistema, los usuarios podrán ser asociados a clientes previamente registrados. Un cliente puede tener uno o más usuarios asociados que pueden operar en su nombre. Un usuario que tenga más de un cliente asociado deberá seleccionar el cliente en nombre del cual operará dentro del sistema antes de realizar cualquier acción. El usuario podrá cambiar de cliente en la misma sesión mediante un selector en la interfaz.

Los usuarios que no estén asociados a ningún cliente sólo podrán realizar acciones de consulta, como la visualización de las tasas de cambio y la evolución de las mismas en diferentes periodos de tiempo. Esta evolución podría visualizarse en gráficos de líneas o barras para un análisis más detallado. Para realizar operaciones de compra o venta de divisas, el usuario deberá estar asociado a al menos un cliente.

Juan quería que el sistema aceptara pagos digitales, permitiendo a los clientes abonar con distintos medios de pago. Además, para mayor claridad en el proceso, cada transacción debía contar con un estado que indicara si estaba pendiente, pagada, cancelada o anulada. Una transacción se encuentra pendiente hasta que sea pagada o cancelada, y en caso de haberse realizado el pago, podría anularse.

Otra necesidad clave era la generación automática de reportes y facturas electrónicas. El sistema debía permitir a los clientes descargar su historial de transacciones en PDF o Excel y recibir facturas electrónicas de cada transacción directamente en su correo electrónico. Las facturas electrónicas podrían estar en estado: emitidas, aprobadas o rechazadas.

Juan necesitaría monitorear en tiempo real las ganancias generadas por la casa de cambio. Se podría desglosar la información de las ganancias por tipo de moneda (USD, EUR, PYG, etc.) o de manera global (ganancia total del negocio). También le interesa enviar notificaciones a sus clientes sobre las actualizaciones en tasas de cambio.

Asimismo, Juan requería un módulo de configuración para administrar aspectos fundamentales como las monedas admitidas (USD, EUR, PYG, BRL, etc.), las tasas de cambio, los métodos de pago habilitados y la seguridad y autenticación de usuarios.

Por último, Juan comprendió que necesitaba delegar algunas funciones operativas sin comprometer la seguridad del sistema. Por ello, uno de sus empleados o analista cambiario debería tener acceso para modificar las tasas de cambio y monitorear las ganancias, pero sin privilegios administrativos sobre la plataforma.

Con estas mejoras, Global Exchange dejaría atrás los métodos tradicionales y se consolidaría como una plataforma digital moderna, segura, rápida, accesible y confiable, lista para enfrentar los desafíos del mercado cambiario actual.

---

## Sistema para Casa de Cambio Digital

El objetivo del proyecto es que los estudiantes diseñen y modelen un sistema para la gestión de una Casa de Cambio Digital que permita la compra y venta de divisas, la gestión de clientes y la integración con plataformas de pago.

El sistema deberá contar con los siguientes módulos mínimos:

### 1. Gestión de Usuarios y Seguridad
- Administración de usuarios y autenticación (auto-registro)
- Gestión de roles y permisos

### 2. Gestión de Clientes
- Registro y mantenimiento de clientes
- Segmentación de clientes por categorías (Ej: minoristas, corporativos, VIP)
- Asociación de clientes a sus usuarios representantes

### 3. Gestión de Operaciones Cambiarias
- Simulación de tasas de cambio en tiempo real
- Compra y venta de divisas en múltiples monedas
- Integración con una plataforma de pago para cargar fondos en la billetera electrónica del cliente
- Registro del historial de transacciones de los clientes
- Visualización gráfica donde los usuarios podrán ver la evolución de las tasas de cambio en diferentes periodos de tiempo (día, semana, mes, año)

### 4. Gestión de Documentos Electrónicos (Facturación Electrónica)
- Generación de documentos electrónicos (facturas, notas de crédito)
- Integración con API para Facturación electrónica

### 5. Reportes y Gráficos para Monitoreo de Ganancias
- Historial de transacciones en PDF o Excel
- Visualizar reportes (gráficas) en tiempo real de las ganancias generadas por la casa de cambio. Se podrá desglosar la información de las ganancias:
  - Por tipo de moneda (USD, EUR, PYG, etc.)
  - De manera global (ganancia total del negocio)

### 6. Notificaciones
- Notificaciones sobre actualizaciones en tasas de cambio

### 7. Configuraciones
- **Monedas admitidas:** qué monedas serán manejadas en la casa de cambio (Ej: USD, EUR, GBP, ARS, PYG, BRL, etc.)
- **Operaciones admitidas:** qué operaciones serán manejadas en la casa de cambio (compra de divisas, venta de divisas, etc.)
- **Tasas de cambio:** a ser definidas de manera manual por el administrador del sistema
- **Métodos de pago admitidos**
