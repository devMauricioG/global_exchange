# Matriz de Casos de Prueba DIS CPR 01 Actualizacion SCRUM 57

## 1. Alcance

Esta matriz agrega los casos de prueba para `rates`, `comisiones`, `cotizador` y `payments`. Los casos se derivan de los requisitos RF28 a RF31 y las reglas RN08 a RN18 de la ERS v3.2.

| Entorno | Configuracion |
|---|---|
| Framework | Django TestCase y cliente de pruebas Django |
| Datos | Monedas USD y PYG activas, cliente con segmento MIN o VIP; usuario autenticado cuando la interfaz lo exige |
| Precision | `Decimal`; USD con 2 decimales y PYG con 0 decimales cuando corresponda |
| Rutas base | `/rates/` y `/payments/` |

## 2. Casos de prueba de monedas y tasas

| ID | Caso | Precondiciones | Pasos | Resultado esperado | Prioridad |
|---|---|---|---|---|---|
| CPR-RAT-001 | Crear moneda valida | Usuario autenticado; codigo no existente | Crear USD con 2 decimales | Se persiste con codigo USD y estado activo | Alta |
| CPR-RAT-002 | Normalizar codigo ISO | No existe moneda `usd` | Guardar codigo con espacios y minusculas | Se almacena `USD` | Alta |
| CPR-RAT-003 | Rechazar codigo ISO invalido | Ninguna | Crear codigo con menos, mas de 3 caracteres o digitos | Error de validacion; no se persiste | Alta |
| CPR-RAT-004 | Rechazar precision fuera de rango | Moneda en creacion | Informar decimales menor a 0 o mayor a 10 | Error de validacion | Media |
| CPR-RAT-005 | Crear tasa y calcular spread | USD y PYG activas | Crear USD/PYG con compra 7000 y venta 7100 | Spread guardado igual a 100 | Critica |
| CPR-RAT-006 | Rechazar par identico | USD activa | Crear USD/USD | Error en moneda destino | Alta |
| CPR-RAT-007 | Rechazar tasa no positiva | Par USD/PYG | Informar compra o venta cero o negativa | Error de validacion | Alta |
| CPR-RAT-008 | Rechazar venta menor que compra | Par USD/PYG | Informar compra 7100 y venta 7000 | Error en venta; no se persiste | Critica |
| CPR-RAT-009 | Validar vigencia cronologica | Par USD/PYG | Informar `valid_to` anterior o igual a `valid_from` | Error de validacion | Alta |
| CPR-RAT-010 | Evaluar tasa vigente | Tasa activa con periodo actual | Consultar `is_current` | Retorna verdadero; una inactiva, futura o vencida retorna falso | Alta |
| CPR-RAT-011 | Seleccionar tasa por operacion | Tasa compra 7000, venta 7100 | Solicitar BUY y SELL | BUY devuelve 7100; SELL devuelve 7000 | Alta |
| CPR-RAT-012 | Consultar historial por periodo | Varias tasas del mismo par | Llamar `/rates/api/history/` con par y periodo validos | JSON contiene solo registros del periodo solicitado | Media |
| CPR-RAT-013 | Rechazar parametros de historial invalidos | Usuario autenticado | Enviar par o periodo invalido | Respuesta 400; no se exponen datos inconsistentes | Media |

## 3. Casos de prueba de comisiones

| ID | Caso | Precondiciones | Pasos | Resultado esperado | Prioridad |
|---|---|---|---|---|---|
| CPR-COM-001 | Crear regla por segmento | Segmento MIN sin regla | Crear regla 1.5%, cargo 1000, descuento 10% | Registro activo persistido | Alta |
| CPR-COM-002 | Impedir segmento duplicado | Existe regla MIN | Intentar crear otra regla MIN | Error de unicidad | Critica |
| CPR-COM-003 | Validar porcentaje de comision | Segmento disponible | Informar -0.01 o 100.01 | Error de validacion | Alta |
| CPR-COM-004 | Validar cargo fijo | Segmento disponible | Informar cargo fijo negativo | Error de validacion | Alta |
| CPR-COM-005 | Validar descuento de spread | Segmento disponible | Informar descuento fuera de 0 a 100 | Error de validacion | Alta |
| CPR-COM-006 | Calcular comision activa | Regla 1.5% y fijo 1000 | Calcular sobre 100000 | Resultado 2500 | Alta |
| CPR-COM-007 | Regla inactiva | Regla inactiva | Calcular sobre monto positivo | Resultado 0; no aplica descuento | Alta |
| CPR-COM-008 | Aplicar descuento de spread | Spread 100 y descuento 10% | Ejecutar metodo de descuento | Spread efectivo 90 | Media |
| CPR-COM-009 | API de lista de comisiones | Existen reglas | GET `/rates/api/commissions/` | JSON con reglas disponibles | Media |
| CPR-COM-010 | API de detalle inexistente | Segmento sin regla | GET detalle con codigo inexistente | Respuesta 404 | Media |

## 4. Casos de prueba del cotizador

| ID | Caso | Precondiciones | Pasos | Resultado esperado | Prioridad |
|---|---|---|---|---|---|
| CPR-COT-001 | Cotizar compra minorista | Tasa USD/PYG vigente; cliente MIN | Cotizar BUY por 100 USD | Retorna tasa de venta, importes brutos, comision y total a pagar | Critica |
| CPR-COT-002 | Cotizar venta VIP con bonificacion | Tasa vigente; regla VIP con descuento | Cotizar SELL por 100 USD | Tasa efectiva superior a compra; monto neto descuenta comision | Critica |
| CPR-COT-003 | Cotizar monto en moneda destino | Tasa vigente | Enviar `is_source_base=false` y monto PYG | Calcula base mediante division y respeta precision de ambas monedas | Alta |
| CPR-COT-004 | Regla neutral sin configuracion | Segmento sin regla activa | Cotizar monto positivo | Comision y descuento son cero; cotizacion se completa | Alta |
| CPR-COT-005 | Rechazar operacion invalida | Tasa vigente | Enviar tipo distinto de BUY o SELL | Respuesta 400 con error de parametro | Alta |
| CPR-COT-006 | Rechazar monto cero o negativo | Tasa vigente | Enviar 0 o monto negativo | Respuesta 400; no se genera resultado | Alta |
| CPR-COT-007 | Tasa no encontrada | No hay tasa activa para el par | Solicitar cotizacion | Respuesta 404 o error controlado de tasa no disponible | Alta |
| CPR-COT-008 | API por GET | Datos validos | GET `/rates/api/calculate/` con parametros | Respuesta 200 JSON y estructura completa | Alta |
| CPR-COT-009 | API por POST JSON | Datos validos | POST JSON a la API | Respuesta 200 JSON y valores equivalentes al GET | Alta |
| CPR-COT-010 | JSON invalido | API disponible | POST con cuerpo no JSON y sin parametros alternativos | Respuesta 404 controlada por falta de cotizacion; no hay error de servidor ni efectos persistentes | Media |
| CPR-COT-011 | Formulario web valido | Usuario autenticado y tasa vigente | POST `/rates/calculator/` | Renderiza resultado de cotizacion | Media |
| CPR-COT-012 | Formulario web invalido | Usuario autenticado | POST con campos invalidos | Renderiza errores y conserva el formulario | Media |

## 5. Casos de prueba de medios de pago

| ID | Caso | Precondiciones | Pasos | Resultado esperado | Prioridad |
|---|---|---|---|---|---|
| CPR-PAY-001 | Crear primer medio | Cliente activo sin medios | Registrar transferencia valida | Se crea activa y predeterminada | Alta |
| CPR-PAY-002 | Crear medio adicional | Cliente con predeterminado | Registrar segunda billetera | Se crea sin quitar preferencia al anterior, salvo seleccion explicita | Alta |
| CPR-PAY-003 | Exclusividad de predeterminado | Cliente con dos medios | Marcar el segundo como predeterminado | El primero pierde la marca en una operacion atomica | Critica |
| CPR-PAY-004 | Impedir predeterminado inactivo | Medio inactivo | Crear o editar con ambas banderas | Error de validacion | Alta |
| CPR-PAY-005 | Desactivar predeterminado | Medio predeterminado activo | POST de cambio de estado | Queda inactivo y deja de ser predeterminado | Alta |
| CPR-PAY-006 | Aislamiento de listado | Dos clientes con medios distintos | Consultar listado con cliente A activo | Solo se muestran medios de A | Critica |
| CPR-PAY-007 | Proteger edicion IDOR | Cliente A activo; medio de B | Solicitar URL de edicion del medio B | Rechazo o 404; no se modifica B | Critica |
| CPR-PAY-008 | Proteger eliminacion IDOR | Cliente A activo; medio de B | Solicitar URL de eliminacion del medio B | Rechazo o 404; no se elimina B | Critica |
| CPR-PAY-009 | API crear medio | Cliente activo | POST JSON valido a `/payments/api/` | Respuesta 201 con medio asociado al cliente activo | Alta |
| CPR-PAY-010 | API actualizar y eliminar | Medio propio existente | PUT/PATCH y luego DELETE al detalle | Respuestas 200 y eliminacion confirmada | Alta |
| CPR-PAY-011 | Validar campos de titularidad | Cliente activo | Enviar entidad, cuenta o titular vacios | Respuesta 400 con errores de campo | Media |

## 6. Criterios de aprobacion

- Todos los casos criticos y altos deben aprobar antes de integrar SCRUM 57.
- Los calculos deben comparar objetos `Decimal` o valores serializados equivalentes, sin tolerancias de punto flotante.
- Los casos de aislamiento deben ejecutarse con dos clientes y dos usuarios para demostrar que no hay fuga horizontal de datos.
- Las pruebas de API deben comprobar codigo HTTP, forma del JSON y ausencia de efectos persistentes en los escenarios de error.
