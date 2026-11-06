# Manual de pruebas funcionales — Global Exchange

Guía de preparación y pruebas manuales para el Hito 7 / Sprint 5. Los datos utilizados son exclusivamente de desarrollo.

## 1. Preparar el entorno

Desde la raíz del proyecto ejecute:

```powershell
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_data
```

`seed_data` es idempotente: puede ejecutarse nuevamente sin duplicar los datos de demostración. Para reiniciar **transacciones, medios de pago, medios de acreditación y asignaciones de clientes**, use `seed_data --reset`. No emplee esa opción si desea conservar pruebas manuales ya realizadas.

| Servicio | Dirección |
|---|---|
| Aplicación | http://localhost:8000/ |
| Administración de Keycloak | http://localhost:8080/admin/ |
| Correo de desarrollo (Mailpit) | http://localhost:8025/ |

## 2. Usuarios de la seed y vínculo con clientes

La contraseña configurada por la seed de Django es `Password123!`. La seed crea los usuarios y sus vínculos de cliente en Django, pero la autenticación web se realiza mediante Keycloak. Por eso, antes de iniciar sesión por primera vez, cree o ajuste en Keycloak un usuario con el mismo **correo electrónico**, nombre de usuario y rol indicados abajo. El primer login sincroniza los datos por correo y guarda el `sub` de Keycloak en la ficha del cliente.

| Usuario | Correo | Rol en Keycloak | Cliente vinculado | Segmento |
|---|---|---|---|---|
| `admin` | `admin@globalexchange.com.py` | `admin` | No aplica | Administración |
| `operador` | `operador@globalexchange.com.py` | `operator` y `cajero` | No aplica | Caja / supervisión |
| `cliente_minorista` | `juan.perez@gmail.com` | `user` | Juan Pérez Gómez | Minorista |
| `cliente_vip` | `victoria.vip@inversiones.com.py` | `user` | Victoria Silveira Inversiones | VIP |
| `cliente_corporativo` | `finanzas@agroexport.com.py` | `user` | Agroexportadora del Este S.A. | Corporativo |
| `cliente_mayorista` | `carlos.mayorista@distribuidora.com.py` | `user` | Distribuidora Mayorista Guaraní S.R.L. | Mayorista |

En Keycloak, entre con `admin` / `admin` (salvo que `.env` lo cambie), abra el realm `GlobalExchangeRealm`, vaya a **Users → Add user**, complete los datos, asigne el rol de realm y defina una contraseña no temporal. Use los mismos correos de la tabla. Si el usuario ya existe en Django, no cree otro correo: la coincidencia exacta de correo es la que conserva la asignación del cliente.

## 3. Caso principal: cliente registrado

Use `cliente_minorista` o `cliente_vip`.

1. Abra http://localhost:8000/ e inicie sesión en Keycloak.
2. Confirme en la barra superior que aparece el cliente activo y su segmento. Si no aparece, cierre sesión, confirme el correo del usuario en Keycloak y vuelva a entrar.
3. Abra **Cotizador** (`/rates/calculator/`), elija `USD/PYG`, operación compra o venta, e ingrese un monto permitido. El resultado debe mostrar tasa, comisión, importe neto y las validaciones de límite.
4. Pruebe un monto menor al mínimo o mayor al máximo. El sistema debe informar la infracción y no debe permitir formalizar una operación inválida.
5. Desde el cotizador continúe a la orden (`/transactions/create/`). Seleccione un medio de pago y una cuenta de acreditación ya sembrados; confirme la orden y compruebe que aparece en **Mis transacciones** (`/transactions/`).
6. Abra el detalle y, si está disponible, el recibo o KuDE. El usuario sólo debe ver transacciones de su propio cliente.
7. En otra sesión de incógnito con `cliente_vip`, intente abrir una URL de transacción o medio de pago de `cliente_minorista`. El resultado esperado es `404` o `403`, nunca acceso a datos ajenos.

Para contrastar reglas comerciales, cotice el mismo importe con `cliente_minorista` y `cliente_vip`: la comisión y/o tasa neta debe variar por segmento.

## 4. Caso principal: cajero / operador

Use `operador`, con roles `operator` y `cajero`. La seed crea las cajas `CAJA-01` y `CAJA-02`, inicialmente cerradas. El operador no representa a un cliente: su prueba se centra en la ventanilla.

1. Inicie sesión y abra **Caja** (`/cash/`). Deben mostrarse las cajas disponibles y los últimos turnos propios.
2. Seleccione **Abrir turno** (`/cash/shifts/open/`), elija una caja y cargue un fondo inicial por moneda. Confirme; el panel debe indicar que el turno está abierto y mostrar los saldos de la caja.
3. Registre un ingreso o egreso manual en **Nuevo movimiento** (`/cash/movements/create/`). Para un egreso, use un importe no superior al saldo disponible. Verifique que el saldo resultante se actualice.
4. Intente abrir un segundo turno con el mismo usuario. Debe ser rechazado o redirigido al turno que ya está abierto.
5. Abra **Cerrar turno** (`/cash/shifts/close/`). Ingrese el conteo físico sin consultar saldos esperados: el arqueo es ciego. Al confirmar, el sistema debe informar conciliación, sobrante o faltante y permitir ver el acta.
6. Con un segundo usuario de rol `cajero`, compruebe que no puede consultar ni cerrar el turno del primer cajero. Un administrador u operador supervisor sí puede realizar esa consulta.

## 5. Nuevo cliente en kiosco

El flujo de autoservicio está disponible sin login en `/kiosk/`.

1. Abra http://localhost:8000/kiosk/ y seleccione una divisa y operación.
2. Ingrese un RUC o documento inexistente cuando el kiosco solicite la identificación. El resultado esperado es ofrecer el registro express.
3. Complete los datos del nuevo cliente y continúe con la cotización.
4. Finalice la operación de demostración y verifique la emisión del recibo o KuDE cuando el flujo lo habilite.

El registro express crea una ficha de cliente para la operación de kiosco; no crea por sí solo una cuenta de acceso OIDC. Para que ese cliente use el portal web, cree después su usuario en Keycloak y conserve el mismo correo.

## 6. Pruebas de administración y datos sembrados

Con `admin`, valide los catálogos en `/rates/currencies/`, `/rates/exchange-rates/`, `/rates/commissions/` y `/rates/limits/`. El usuario `admin` puede administrar; `operador` puede consultar los elementos permitidos por su rol; un cliente no debe poder crear ni editar estas reglas.

La seed añade seis monedas (`PYG`, `USD`, `EUR`, `BRL`, `ARS`, `GBP`), tasas vigentes e históricas, comisiones, límites y cinco transacciones de referencia: `TX-SEED-00001` a `TX-SEED-00005`, en estados completada, pendiente y cancelada. Úselas para validar filtros, aislamiento y comprobantes sin crear nuevas operaciones.

## 7. Criterio de cierre de una prueba manual

Registre para cada caso: usuario/rol, fecha, pasos ejecutados, resultado esperado, resultado observado y evidencia (captura o URL). Si se crea una operación o turno de prueba, anote su referencia para poder revisarla antes de ejecutar cualquier `seed_data --reset`.
