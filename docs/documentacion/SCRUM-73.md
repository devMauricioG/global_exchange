# Tarea SCRUM-73: Componente visual de formulario dinámico e interactivo en JavaScript para medios de pago

## Descripción de la tarea
Diseñar en la plantilla `templates/payments/paymentmethod_form.html` un selector de pestañas o radio cards que reconfigure dinámicamente los campos mostrados en el DOM según el instrumento financiero elegido, aplicando máscaras de entrada (input masks) para tarjetas, vencimientos y teléfonos.

## Trabajos Realizados

### 1. Creación de Selector de Opciones (Radio Cards)
- Se sustituyó el campo select convencional `tipo_medio` por un componente visual de tarjetas (radio cards) interactivas para elegir el tipo de medio de pago (Transferencia, Billetera, Tarjeta, Efectivo, Otro).
- Se aplicaron estilos CSS modernos utilizando flexbox/grid, efectos hover, transiciones y un resalte claro para la opción seleccionada.

### 2. Comportamiento Dinámico del DOM (JavaScript)
- Se implementó la función `selectPaymentType` que muestra u oculta grupos de campos (inputs) en función del método de pago elegido.
- Para "Transferencia" se solicita Banco, Tipo de cuenta, Nro de cuenta.
- Para "Billetera" se solicita Proveedor, y el input de teléfono.
- Para "Tarjeta" se exponen inputs personalizados (número de tarjeta y vencimiento).
- Para "Efectivo" no se requieren datos adicionales más allá del titular.

### 3. Máscaras de Entrada (Input Masks)
- **Teléfono Móvil (Billetera):** Se aplica un formato separando grupos de números (ej. `0981 123 456`) en tiempo real mientras el usuario tipea.
- **Número de Tarjeta:** Se divide en bloques de 4 dígitos (ej. `0000 0000 0000 0000`). El sistema extrae en segundo plano solo los últimos 4 dígitos reales (`tarjeta_ultimos_digitos`) y enmascara la variable primaria para no enviar al backend el número sensible íntegro.
- **Vencimiento de Tarjeta:** Se implementó una máscara (MM/AA) que divide y autocompleta con una barra, asignando transparentemente el mes y el año a los campos del formulario ocultos (`tarjeta_mes_vencimiento` y `tarjeta_anio_vencimiento`) listos para el clean() de Django.

### 4. Adaptación a ModelForm de Django
- Se mapeó dinámicamente la entrada para que cumpla con los campos obligatorios de validación en el Backend (como el campo de texto libre `numero_cuenta`), completándose con 'N/A' en medios como Tarjeta y Efectivo, previniendo errores de validación sin perder flexibilidad.

## Resultados Esperados
El formulario de carga o modificación de medios de pago ahora es más limpio e intuitivo, mejorando notablemente la experiencia de usuario (UX) mediante reconfiguración dinámica y asistiendo al ingreso de datos con un formateo automático en el frontend (máscaras).
