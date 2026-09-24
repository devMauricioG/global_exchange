# Tarea SCRUM-81: Interfaz gráfica y vistas para el Historial de Transacciones con filtros y trazabilidad

## Descripción de la tarea
Construir las plantillas `templates/transactions/transaction_list.html` y `transaction_detail.html` con tabla paginada de operaciones, filtros por fecha, moneda y estado con badges de estado, y modal de trazabilidad completa.

## Trabajos Realizados

### 1. Refactorización de Vistas (views.py)
- Se extendió el `TransactionListView` para capturar y procesar filtros avanzados mediante parámetros GET:
  - `fecha_desde` y `fecha_hasta` (filtrado por la fecha `created_at` usando parse_date).
  - `moneda` (buscando de forma insensible a mayúsculas si el código de moneda enviado coincide con `base_currency` o `target_currency` de la transacción).
- Se pasaron los nuevos parámetros y la lista de divisas activas (`currencies`) al contexto para popular el formulario de la plantilla interactiva.

### 2. Filtros de Búsqueda Avanzados
- En la plantilla `transaction_list.html` se agregaron los siguientes inputs y selectores:
  - Selector de "Moneda" poblado iterativamente con el modelo de divisas activo.
  - Inputs HTML5 de tipo "date" para establecer rangos de fechas (Desde y Hasta).
- Todos los inputs respetan la selección previa almacenada para asegurar una buena UX.
- Se incorporaron las nuevas variables en la URL de la botonera del paginador nativo de Django, logrando persistir los filtros elegidos en el salto de páginas.

### 3. Badges de Estado
- Las insignias de estado ya fueron incorporadas mediante validación de Django Templates, luciendo colores y diseños acordes según sea estado de compra/venta o pendiente/completado/cancelado.

### 4. Modal Dinámico de Trazabilidad
- Se incorporó un componente `div` oculto (Modal) en `transaction_list.html` junto a un set de funciones en JavaScript puro (`openTrazabilidadModal` y `closeTrazabilidadModal`).
- Se introdujo un nuevo botón "📜 Trazabilidad" en las acciones por registro. Al hacer clic, se pasan parámetros variables (Código, Fechas exactas de Alta y Modificación, Usuario Operador, Token de congelamiento y Observaciones).
- Se garantiza la integridad de escape del string mediante escapejs en Django para las observaciones, evitando vulnerabilidades y permitiendo consultar detalles finos sin abandonar o recargar el listado, facilitando el escrutinio de la auditoría operativa.

## Resultados Esperados
El módulo de listado de transacciones ofrece un potente sistema de filtros multiparámetros, persistencia de variables en paginación, listado claro con insignias y una ventana modal que mejora la experiencia del auditor u operador al visualizar los registros precisos y metadatos de las transacciones efectuadas.
