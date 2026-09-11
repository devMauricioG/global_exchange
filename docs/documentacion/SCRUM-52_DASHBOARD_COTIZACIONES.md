# SCRUM-52: Dashboard de cotizaciones históricas

## Resultado

Se incorporó un tablero autenticado en `/rates/dashboard/` para el seguimiento operativo de las tasas de cambio.

## Funcionalidades

- Tarjetas KPI para pares vigentes, monedas activas y actualizaciones del día.
- Resumen de la última cotización vigente por cada par de monedas.
- Gráfico lineal interactivo de Chart.js con series de compra y venta.
- Selectores de par de monedas y períodos de 7, 30, 90 días y un año.
- Endpoint autenticado `GET /rates/api/history/?pair=<base_id>:<target_id>&period=<rango>` con validación de parámetros y respuesta JSON.
- Manejo de períodos sin datos y diseño adaptable a pantallas pequeñas.

## Pruebas

La suite `ExchangeRateDashboardTests` cubre la carga del tablero, filtrado temporal del historial, parámetros inválidos y protección de autenticación.
