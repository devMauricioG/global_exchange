# SCRUM-56 — Guía de Pruebas Funcionales Interactivas por Rol

Esta guía permite comprobar manualmente, desde el navegador, los flujos cubiertos por la suite automatizada de SCRUM-56. No modifica datos de producción: usar una base de desarrollo o de pruebas y cuentas creadas específicamente para esta ejecución.

## 1. Preparación

1. Levantar la plataforma con `docker compose up --build -d` y aplicar migraciones con `docker compose exec web python manage.py migrate`.
2. Ingresar a Keycloak y crear las cuentas de prueba siguientes, verificando que el *protocol mapper* incluya los roles del realm en el token.
3. Iniciar sesión una vez con cada cuenta para que Django sincronice el usuario y su ficha de cliente. Cerrar sesión entre pruebas de roles diferentes.
4. Cargar los datos de prueba de esta tabla desde `/admin/` o mediante las pantallas del sistema.

| Alias | Rol de Keycloak/Django | Datos necesarios |
|---|---|---|
| `admin.qa` | `admin` / superusuario | Acceso administrativo y, opcionalmente, dos clientes para supervisión. |
| `operador.qa` | `operator` / `is_staff` | Puede crear y administrar catálogos, cotizaciones, comisiones y clientes. |
| `cliente.a.qa` | `user` | Cliente A activo, con dos medios de pago y una asignación activa. |
| `cliente.b.qa` | `user` | Cliente B activo, con al menos un medio de pago. No debe pertenecer a `cliente.a.qa`. |
| `multicliente.qa` | `user` | Dos asignaciones activas: una como representante de Cliente A y otra de Cliente B. |

Crear también estas entidades para las pruebas:

| Entidad | Datos de ejemplo |
|---|---|
| Monedas | `USD` (2 decimales), `PYG` (0 decimales) y `EUR` (2 decimales). |
| Cotización vigente | `USD/PYG`, compra `7400`, venta `7500`, activa, `valid_from` anterior a la hora actual y sin `valid_to`. |
| Cotización expirada | `USD/EUR`, activa, pero con `valid_to` anterior a la hora actual. |
| Comisiones | `MIN`: 1 % y cargo fijo 5000; `VIP`: 0,20 % y descuento de spread 40 %. |
| Medios de Cliente A | Transferencia Banco A y billetera A. Marcar inicialmente la transferencia como predeterminada. |
| Medio de Cliente B | Transferencia Banco B. |

Las rutas se muestran para el servidor local `http://localhost:8000`; reemplazar el host si se prueba en otro entorno.

## 2. Criterio de registro

Para cada caso, registrar fecha, cuenta utilizada, evidencia (captura o respuesta JSON), resultado observado y estado `PASS`/`FAIL`.

Un caso es `PASS` cuando la pantalla, el mensaje y los datos persistidos coinciden con el resultado esperado. Los casos marcados como **seguridad** también son `PASS` únicamente si no exponen ni permiten modificar datos fuera del alcance del usuario.

## 3. Matriz de visibilidad esperada

| Funcionalidad | Invitado | Usuario/cliente | Operador | Administrador |
|---|:---:|:---:|:---:|:---:|
| Inicio | Redirección a OIDC | Sí | Sí | Sí |
| Medios de pago propios | Redirección a OIDC | Sí | Sí, según cliente activo | Sí |
| Cotizador y tablero de cotizaciones | Redirección a OIDC | Sí | Sí | Sí |
| Clientes | No visible | No visible | Sí | Sí |
| Comisiones por segmento | No visible | No visible | Sí | Sí |
| Panel `/admin/` | No | No | Según permisos de staff | Sí |
| Catálogo de monedas y tasas | No | Sólo si se autoriza explícitamente | Sí | Sí |

> Importante: la visibilidad de un enlace no sustituye la autorización del servidor. Ejecutar también los casos de acceso directo de la sección 8; una URL oculta que responda con una pantalla de edición a un rol no autorizado es un hallazgo de seguridad.

## 4. Casos comunes de autenticación

| ID | Pasos | Resultado esperado |
|---|---|---|
| `PF-COM-01` | En una ventana privada abrir `/`, `/customers/`, `/payments/` y `/rates/calculator/`. | Cada recurso protegido redirige al inicio de sesión OIDC; no se muestran datos internos. |
| `PF-COM-02` | Autenticarse con cualquiera de las cuentas. Observar la insignia de rol de la barra superior. | Se muestra `Administrador`, `Operador` o `Usuario`, según los grupos sincronizados desde Keycloak. |
| `PF-COM-03` | Abrir `/auth/logout/` y volver con el botón Atrás del navegador. | La sesión local se invalida, se redirige al cierre SSO de Keycloak y no se recupera contenido protegido sin autenticar de nuevo. |
| `PF-COM-04` | Iniciar sesión con una cuenta que no posea ficha de cliente. Abrir `/payments/`. | Se muestra un aviso y se vuelve al inicio; no se crea ni lista un medio de pago sin cliente activo. |

## 5. Casos del administrador

Ejecutar con `admin.qa`.

| ID | Pasos | Resultado esperado |
|---|---|---|
| `PF-ADM-01` | Abrir Inicio y revisar navegación. | Están visibles Clientes, Medios de Pago, Cotizador, Cotizaciones, Comisiones, Panel Admin y Documentación. |
| `PF-ADM-02` | Abrir `/rates/currencies/`, crear `BRL` con símbolo `R$` y 2 decimales; editarlo y alternar su estado. | El código se guarda en mayúsculas, se ve en el listado y el cambio de activo/inactivo persiste. Un código de menos de tres letras, con números o más de 10 decimales se rechaza. |
| `PF-ADM-03` | Abrir `/rates/exchange-rates/create/`, registrar una tasa `USD/PYG` con compra 7400 y venta 7500. | Se guarda con spread 100 y el usuario actual queda como actualizador. Intentar guardar venta menor que compra, tasa no positiva, mismo par de monedas o `valid_to` anterior a `valid_from`. | Cada combinación inválida muestra error y no se persiste. |
| `PF-ADM-04` | Abrir `/rates/commissions/`; crear o editar la comisión `VIP` con 0,20 %, cargo 0 y descuento 40 %. | El detalle muestra los valores guardados. Porcentajes fuera de 0–100 o cargo fijo negativo son rechazados. |
| `PF-ADM-05` | Abrir `/customers/`, filtrar por segmento, RUC, texto y estado. Crear un cliente, editarlo y eliminar el registro creado. | Los filtros devuelven sólo coincidencias; las operaciones CRUD muestran mensaje de éxito y los cambios persisten. |
| `PF-ADM-06` | Abrir `/payments/?cliente_id=<id-cliente-a>` y gestionar un medio de pago. | Puede consultar y, como superusuario, editar/eliminar medios de otros clientes de forma supervisada. Al establecer uno como predeterminado, los demás del mismo cliente se desmarcan. |
| `PF-ADM-07` | Abrir `/rates/dashboard/` y cambiar el período de la gráfica. | Se muestran únicamente pares vigentes, métricas y el historial solicitado; las tasas expiradas o futuras no aparecen como vigentes. |

## 6. Casos del operador

Ejecutar con `operador.qa`.

| ID | Pasos | Resultado esperado |
|---|---|---|
| `PF-OPE-01` | Abrir Inicio. | Se muestran Clientes y Comisiones, pero no el enlace Panel Admin. |
| `PF-OPE-02` | En `/customers/`, crear un cliente corporativo; buscarlo por RUC, editar el teléfono y eliminar el registro de prueba. | Las operaciones se completan y dejan mensajes de confirmación. Un correo o RUC repetidos se rechazan. |
| `PF-OPE-03` | En `/rates/commissions/`, cambiar la regla de `MIN`; abrir `/rates/calculator/` y cotizar 100 USD para `MIN`. | El cálculo usa la comisión y el cargo fijo configurados; el desglose presenta tasa oficial, spread, comisión y monto neto. |
| `PF-OPE-04` | Registrar una nueva cotización vigente desde `/rates/exchange-rates/create/`, editarla y alternar su estado. | El spread se recalcula y una tasa desactivada deja de estar disponible para el cotizador. |
| `PF-OPE-05` | Ir a `/admin/`. | Si la cuenta no tiene permisos Django de administrador, no puede modificar recursos administrativos. Registrar cualquier pantalla de acceso inesperada como defecto de permisos. |
| `PF-OPE-06` | Usar el selector de cliente activo, si tiene asignaciones, y abrir `/payments/`. | La lista y las acciones se aplican al cliente activo seleccionado, no a datos de otro cliente. |

## 7. Casos del usuario/cliente

Ejecutar con `cliente.a.qa`, salvo que se indique otra cuenta.

| ID | Pasos | Resultado esperado |
|---|---|---|
| `PF-USU-01` | Abrir Inicio. | Se muestran Medios de Pago, Cotizador, Cotizaciones y Documentación; no se muestran Clientes, Comisiones ni Panel Admin. |
| `PF-USU-02` | Abrir `/payments/`. Crear una billetera válida. | El nuevo medio queda asociado a Cliente A. Si era el primer medio, queda predeterminado automáticamente. |
| `PF-USU-03` | Marcar la billetera como predeterminada. | Sólo ese medio de Cliente A queda predeterminado; el anterior se desmarca. |
| `PF-USU-04` | Inhabilitar el medio predeterminado y luego volver a habilitarlo. | Al inhabilitarlo deja de ser predeterminado. No se permite guardar un medio inactivo marcado como predeterminado. |
| `PF-USU-05` | Filtrar los medios por entidad, tipo y estado. | Se muestran sólo los medios propios que coinciden con cada filtro. |
| `PF-USU-06` | Abrir `/rates/calculator/`. Cotizar compra de 100 USD para Cliente A y luego venta de 100 USD. | Se muestra el desglose de compra/venta, moneda origen/destino, comisión, tasa efectiva y monto neto. No se acepta monto cero, negativo ni tipo de operación inválido. |
| `PF-USU-07` | En el resultado del cotizador seleccionar **Congelar Cotización por 5 Minutos**. Refrescar la página. | Aparece el token `QTZ-...`, contador regresivo y los mismos datos congelados mientras el token sea válido. |
| `PF-USU-08` | Esperar cinco minutos desde el congelamiento y refrescar el cotizador, o usar la opción de descongelar antes. | El token expirado ya no se acepta como cotización activa; el contador llega a cero. Al descongelar, desaparece el estado congelado. |
| `PF-USU-09` | Abrir `/rates/dashboard/` y seleccionar períodos disponibles. | Puede consultar el tablero, pero no se le presentan tasas vencidas como cotizaciones vigentes. |

## 8. Pruebas de aislamiento y acceso directo

Estas pruebas requieren conocer IDs reales, visibles en la URL al abrir un registro. Son obligatorias porque el menú condicional sólo controla la interfaz.

| ID | Cuenta y pasos | Resultado esperado |
|---|---|---|
| `PF-SEG-01` | Con `cliente.a.qa`, copiar el ID de un medio de Cliente B. Abrir `/payments/<id-b>/editar/` y `/payments/<id-b>/eliminar/`. Intentar también `GET`, `PUT`, `PATCH` y `DELETE` sobre `/payments/api/<id-b>/`. | Respuesta 404/denegada. Cliente A nunca ve, edita, predetermina, activa ni elimina el medio de Cliente B. |
| `PF-SEG-02` | Con `cliente.a.qa`, enviar un `POST` al cambio de cliente de Cliente B en `/customers/cambiar-cliente/<id-b>/`. | Respuesta 404/denegada; el cliente activo de la sesión no cambia. |
| `PF-SEG-03` | Con `multicliente.qa`, cambiar de Cliente A a Cliente B desde el selector y abrir `/payments/` antes y después. | El mensaje confirma el cambio y los medios listados corresponden exclusivamente al cliente seleccionado. |
| `PF-SEG-04` | Con `cliente.a.qa`, intentar directamente `/customers/`, `/customers/nuevo/`, `/rates/commissions/`, `/rates/currencies/create/` y `/rates/exchange-rates/create/`. | Debe respetarse la política de autorización definida por el equipo. Si una pantalla administrativa se abre para un rol cliente, registrar el caso como hallazgo de control de acceso aunque el enlace esté oculto. |
| `PF-SEG-05` | Con una sesión distinta o después de cerrar sesión, intentar consultar o descongelar un token `QTZ-...` copiado desde Cliente A. | No se recupera ni reutiliza la cotización congelada de otra sesión. |

## 9. Verificaciones opcionales de API desde el navegador

Usar DevTools, Postman o `curl` con una sesión autenticada. Estas comprobaciones complementan, pero no sustituyen, los flujos de la interfaz.

| Caso | Solicitud | Resultado esperado |
|---|---|---|
| Listar medios propios | `GET /payments/api/` | HTTP 200 y sólo medios del cliente activo. |
| Crear medio | `POST /payments/api/` con JSON válido | HTTP 201 y asociación al cliente activo. JSON inválido o datos incompletos: HTTP 400. |
| Cotizar tasa vigente | `GET /rates/api/calculate/?base_currency=USD&target_currency=PYG&amount=100` | HTTP 200 con `success: true` y desglose de cálculo. |
| Cotizar tasa expirada | Repetir con un par cuya única tasa tenga `valid_to` vencido. | HTTP 404; el cotizador no entrega una tasa expirada. |
| Congelar cotización | `POST /rates/api/freeze/` con `exchange_rate_id` y monto válidos | HTTP 201 con token y duración de 300 segundos. |
| Consultar estado congelado | `GET /rates/api/frozen-quote/` | HTTP 200 mientras sea vigente; tras expiración o descongelamiento, HTTP 404. |

## 10. Cierre de la ejecución

1. Eliminar o desactivar los datos creados sólo para pruebas, sin borrar registros de otros equipos.
2. Adjuntar las evidencias de los casos fallidos al ticket, incluyendo rol, URL, ID del registro y hora de ejecución.
3. Reportar por separado todo fallo de `PF-SEG-*`: son incidencias de seguridad o aislamiento de datos y requieren prioridad de revisión.
