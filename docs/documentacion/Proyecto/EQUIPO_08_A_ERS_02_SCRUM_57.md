# ESPECIFICACION DE REQUERIMIENTOS DE SOFTWARE ERS v3.2

## Actualizacion Hito 4 SCRUM 57

### 1. Identificacion

| Campo | Valor |
|---|---|
| Proyecto | Global Exchange |
| Artefacto base | EQUIPO 08 A ERS 01, version 3.1 |
| Version logica | 3.2 |
| Fecha | 11/09/2026 |
| Cambio | Incorporacion de rates, payments, comisiones y cotizador |
| Alcance | Parametrizacion financiera, medios de pago y simulacion de cotizaciones netas |

### 2. Proposito de la actualizacion

Esta actualizacion formaliza las capacidades ya incorporadas en el sistema para administrar el catalogo de divisas, las cotizaciones entre pares de monedas, las reglas de comision por segmento, los medios de pago de cada cliente y la simulacion de una cotizacion neta. Los nuevos requisitos se ejecutan en el contexto del cliente activo y no sustituyen la confirmacion ni la liquidacion de una transaccion.

### 3. Definiciones adicionales

| Termino | Definicion |
|---|---|
| Moneda | Divisa del catalogo identificada por un codigo ISO 4217 de tres letras. |
| Tasa de cambio | Precio de una moneda base expresado en una moneda destino, con valores de compra y venta. |
| Spread | Diferencia calculada entre la tasa de venta y la tasa de compra. |
| Comision por segmento | Regla comercial aplicable a un segmento de cliente; combina porcentaje, cargo fijo y descuento sobre el spread. |
| Cotizacion neta | Resultado informativo que expone tasa efectiva, importes brutos, comisiones y monto final. |
| Medio de pago | Instrumento de cobro o liquidacion registrado por el cliente: transferencia, billetera, tarjeta, efectivo u otro. |

### 4. Alcance funcional

El sistema incluye los siguientes componentes:

- `rates`: catalogo de monedas, tasas de cambio, tablero historico y motor de calculo.
- `comisiones`: administracion de una regla activa por segmento de cliente dentro de `rates`.
- `cotizador`: interfaz web y API que usan una tasa vigente y la regla del segmento para simular el resultado neto.
- `payments`: registro y administracion aislada de medios de pago pertenecientes al cliente activo.

El cotizador no reserva ni congela una tasa en la implementacion de este hito. La vigencia temporal se determina al consultar la tasa; la reserva de cinco minutos prevista en RF07 requiere el ciclo transaccional posterior.

### 5. Reglas de negocio incorporadas

| ID | Regla |
|---|---|
| RN08 | El codigo de moneda debe contener exactamente tres caracteres alfabeticos; el sistema lo normaliza a mayusculas. |
| RN09 | Una tasa solo puede relacionar monedas distintas y debe tener tasas de compra y venta estrictamente positivas. |
| RN10 | La tasa de venta no puede ser inferior a la tasa de compra; el spread se calcula como `sell_rate - buy_rate`. |
| RN11 | Si una tasa define fin de vigencia, este debe ser posterior al inicio. Una tasa usable debe estar activa y vigente. |
| RN12 | Cada segmento puede tener una unica regla de comision. Porcentajes de comision y descuento deben estar entre 0 y 100; el cargo fijo no puede ser negativo. |
| RN13 | El cotizador aplica la tasa de venta cuando el cliente compra la moneda base y la tasa de compra cuando la vende. |
| RN14 | La bonificacion se aplica sobre el spread. En compra reduce la tasa efectiva y en venta la incrementa antes de calcular cargos. |
| RN15 | La comision total es la suma del componente porcentual sobre el monto bruto y el cargo fijo. En compra se suma al monto a pagar; en venta se resta del monto a recibir, sin producir un monto neto negativo. |
| RN16 | Una regla inactiva o ausente no agrega cargos ni descuentos; el sistema usa una regla neutral para el segmento correspondiente. |
| RN17 | Cada medio de pago pertenece a un solo cliente. Solo puede existir un medio predeterminado por cliente y este debe estar activo. |
| RN18 | Un cliente solo puede consultar o modificar sus propios medios de pago. El primer medio registrado se establece como predeterminado. |

### 6. Requerimientos funcionales

#### RF28 Gestion de monedas y tasas de cambio

El usuario autenticado debe poder listar, filtrar, crear, editar y activar o desactivar monedas y tasas de cambio. Cada tasa debe conservar las monedas base y destino, compra, venta, spread calculado, intervalo de vigencia, estado y responsable de la actualizacion.

**Criterios de aceptacion:**

- Las monedas inactivas no se consideran disponibles para una cotizacion.
- El sistema rechaza pares de la misma moneda, importes no positivos y venta menor que compra.
- El listado permite filtrar tasas por par, estado y vigencia.
- El tablero permite revisar el historial de compra y venta por par y por periodo.

#### RF29 Gestion de comisiones por segmento

El usuario autenticado debe poder crear, consultar, editar y eliminar reglas de comision para los segmentos definidos en `Cliente.Segmentacion`.

**Criterios de aceptacion:**

- La regla identifica un segmento unico y conserva porcentaje, cargo fijo, descuento de spread y estado.
- El sistema valida los limites de los tres valores antes de persistirlos.
- La API expone la lista de reglas y el detalle de una regla por codigo de segmento.

#### RF30 Cotizador de tasas netas

El Cliente autenticado debe poder simular una compra o venta entre dos monedas activas mediante una tasa vigente. La simulacion debe usar el cliente activo para resolver el segmento comercial, salvo que un operador autorizado indique un cliente explicito.

**Criterios de aceptacion:**

- La entrada admite monto, moneda base, moneda destino, tipo de operacion `BUY` o `SELL` e indicacion de la moneda en que se expresa el monto.
- El resultado presenta tasa oficial, spread oficial y efectivo, tasa efectiva, importes base y destino, comision porcentual, cargo fijo, total de comision, monto neto y ahorro por spread.
- Los montos se redondean con la precision configurada para cada moneda.
- La interfaz web esta disponible en `/rates/calculator/`; la API de calculo acepta `GET` y `POST` en `/rates/api/calculate/`.
- Ante un par inexistente, monto no positivo, tipo de operacion invalido o JSON invalido, el sistema debe informar un error sin generar una transaccion.

#### RF31 Gestion de medios de pago

El Cliente autenticado debe poder crear, listar, filtrar, editar, activar, desactivar, eliminar y seleccionar su medio de pago predeterminado. El sistema debe admitir transferencia, billetera, tarjeta, efectivo y otros medios autorizados.

**Criterios de aceptacion:**

- Cada registro conserva tipo, entidad o billetera, cuenta o telefono, titular, documento opcional, estado y preferencia.
- Las vistas y los endpoints JSON restringen los registros al cliente activo, evitando el acceso directo a recursos de otro cliente.
- Al seleccionar un medio como predeterminado, el sistema desmarca atomicamente los anteriores del mismo cliente.
- Al desactivar el medio predeterminado, se elimina su marca de preferencia.

### 7. Requerimientos no funcionales complementarios

| ID | Requerimiento |
|---|---|
| RNF-DAT-01 | Los importes monetarios deben calcularse con `Decimal`; no se admite aritmetica financiera basada en punto flotante. |
| RNF-SEC-04 | Las interfaces HTML de `rates` y todas las interfaces de `payments` requieren autenticacion. Los recursos de pagos deben filtrar por cliente activo para prevenir acceso horizontal no autorizado. |
| RNF-INT-01 | La API de cotizacion y las APIs de medios de pago deben responder JSON valido, con codigos 200, 201, 400 o 404 segun corresponda. |
| RNF-MAN-01 | La logica de calculo debe estar desacoplada en `RateCalculationService` para ser reutilizable por el cotizador y futuras transacciones. |

### 8. Trazabilidad de implementacion

| Requisito | Componentes principales |
|---|---|
| RF28 | `rates.models.Currency`, `rates.models.ExchangeRate`, vistas y tablero de `rates` |
| RF29 | `rates.models.SegmentCommission`, formularios, vistas y API de comisiones |
| RF30 | `rates.services.RateCalculationService`, `RateCalculatorView`, `CalculateNetRateApiView` |
| RF31 | `payments.models.PaymentMethod`, vistas web y API de `payments` |

### 9. Fuera de alcance de SCRUM 57

- Confirmacion o persistencia de una cotizacion como transaccion.
- Congelamiento o reserva temporal de tasa.
- Ejecucion bancaria, conciliacion o integracion con proveedores de billetera.
- Cifrado o tokenizacion de datos de cuentas; esta proteccion debe definirse antes de manejar datos financieros sensibles en produccion.

### 10. Historia de cambios

| Fecha | Version logica | Descripcion | Autor |
|---|---:|---|---|
| 20/03/2026 | 1.0 | Borrador inicial de la ERS. | Equipo IS2 |
| 16/08/2026 | 2.0 | NCR, cajas, clientes, monedas y operaciones hibridas. | Equipo IS2 |
| 17/08/2026 | 3.0 | Integracion de autenticacion y autorizacion con Keycloak. | Equipo IS2 |
| 08/09/2026 | 3.1 | Cliente activo, multi representacion y visualizador Sphinx. | Equipo IS2 |
| 11/09/2026 | 3.2 | Hito 4 SCRUM 57: rates, comisiones, cotizador y payments. | Equipo IS2 |
