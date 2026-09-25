# Guía Exhaustiva de Pruebas del Sistema por Módulos y Roles

> **Global Exchange** — Sistema Digital de Operaciones Cambiarias y Gestión Financiera  
> **Versión del Sistema:** v3.0.0 (Hito 5 / Sprint 3)  
> **Fecha:** Septiembre 2026

---

## 1. Introducción y Enfoque de Pruebas

Esta guía detalla el procedimiento paso a paso para la verificación funcional y validación de calidad de **Global Exchange**. El documento está estructurado para que desarrolladores, evaluadores de cátedra y equipos de QA puedan comprobar el comportamiento del sistema según los **roles de usuario**, los **segmentos de clientes** y los **módulos funcionales**.

---

## 2. Preparación Rápida del Entorno y Datos de Prueba

Antes de iniciar la navegación interactiva, inicialice la base de datos con los fixtures y catálogos estándar mediante el comando automatizado:

```bash
# 1. Aplicar migraciones
python manage.py migrate

# 2. Sembrar datos de prueba completos e idempotentes (SCRUM-75)
python manage.py seed_data
```

> [!NOTE]
> El comando `seed_data` crea automáticamente usuarios, roles, clientes segmentados, monedas (`USD`, `EUR`, `BRL`, `ARS`, `PYG`), tasas de cambio vigentes con 30 días de historial, reglas de comisión, entidades financieras, medios de pago y acreditación, límites operativos y transacciones de ejemplo.

### Credenciales de Acceso Rápido

Todos los usuarios de prueba poseen la misma contraseña unificada: **`Password123!`**

| Usuario | Rol / Grupo | Cliente Representado | Segmento | Propósito en la Prueba |
|---|---|---|---|---|
| **`admin`** | Administrador (`admin`, `operator`) | Superusuario Global | Staff | Parametrización completa, divisas, tasas, comisiones, límites, bancos y Django Admin. |
| **`operador`** | Operador de Caja (`operator`) | Operador Central | Staff | Consulta de transacciones, supervisión operativa y comprobantes de liquidación. |
| **`cliente_minorista`** | Cliente (`user`) | Juan Pérez Gómez | **Minorista (MIN)** | Operaciones estándar en taquilla/web, límites menores, comisiones base. |
| **`cliente_vip`** | Cliente (`user`) | Victoria Silveira Inversiones | **VIP (VIP)** | Bonificación preferencial sobre spread, comisiones reducidas y límites altos. |
| **`cliente_corporativo`** | Cliente (`user`) | Agroexport S.A. | **Corporativo (COR)** | Volúmenes elevados, multirrepresentación y cuentas de liquidación empresarial. |
| **`cliente_mayorista`** | Cliente (`user`) | Distribuidora Mayorista | **Mayorista (MAY)** | Descuento comercial por volumen y transferencias bancarias de alto porte. |

---

## 3. Matriz de Roles y Capacidades

| Módulo / Funcionalidad | Administrador (`admin`) | Operador (`operador`) | Cliente (`cliente_*`) |
|---|:---:|:---:|:---:|
| **Panel Django (`/admin/`)** | Total | Restringido | Denegado (403/Login) |
| **Monedas y Tasas (`/rates/`)** | CRUD Completo | Consulta / Monitor | Solo Consulta |
| **Comisiones por Segmento** | Configurar / Editar | Solo Consulta | No aplica |
| **Límites Operativos** | Configurar / Editar | Solo Consulta | Validación activa |
| **Entidades Financieras** | Administrar Catálogo | Consulta | Dropdowns de selección |
| **Medios de Pago y Cobro** | Auditoría | Consulta | CRUD Propio (Anti-IDOR) |
| **Simulador de Cotizaciones** | Acceso Libre | Acceso Libre | Cotización con Segmento |
| **Crear Transacción Cambiaria** | Habilitado | Asistido | Operación propia |
| **Confirmación (Cotización 5 min)**| Supervisión | Asistencia | Confirmación de Orden |
| **Cancelación de Transacción** | Administrativa | Operativa | Cancelación Voluntaria |
| **Comprobante de Liquidación** | Descarga / Impresión | Descarga / Impresión | Descarga Propia |
| **Docs Sphinx (`/docs/`)** | Lectura | Lectura | Lectura |

---

## 4. Guía de Pruebas Paso a Paso por Módulo

### Módulo 1: Autenticación y Resolución de Cliente Activo

1. Ingrese a la URL raíz del sistema: `http://localhost:8000/`.
2. Inicie sesión con el usuario **`cliente_vip`** y contraseña `Password123!`.
3. **Verificación visual del Navbar:**
   - Observe en la esquina superior derecha la tarjeta o badge del **Cliente Activo**: *"Victoria Silveira Inversiones"* y su segmento *"VIP"*.
   - Compruebe que las opciones del menú superior (`Cotizador`, `Mis Medios de Pago`, `Mis Cuentas de Cobro`, `Mis Transacciones`) están disponibles.
4. **Alternancia de Cliente Activo:**
   - Inicie sesión como **`cliente_corporativo`** (representa a varias razones sociales).
   - Haga clic en el selector desplegable de cliente en el navbar.
   - Seleccione otra razón social autorizada.
   - Verifique que la pantalla se actualiza automáticamente y todas las operaciones subsecuentes se imputan al nuevo cliente seleccionado.

---

### Módulo 2: Configuración de Monedas y Tasas de Cambio (`rates`)

> **Rol Requerido:** Iniciar sesión con **`admin`**.

1. **Gestión de Monedas (`/rates/currencies/`):**
   - Navegue a `http://localhost:8000/rates/currencies/`.
   - Compruebe la presencia de `USD`, `EUR`, `BRL`, `ARS` y `PYG`.
   - Haga clic en **"Nueva Moneda"** (`/rates/currencies/create/`) y pruebe registrar una divisa de prueba (ej: `GBP` - Libra Esterlina, Símbolo: `£`, Decimales: `2`).
   - Pruebe el toggle de activación/desactivación sobre una moneda de prueba.
2. **Tasas de Cambio (`/rates/exchange-rates/`):**
   - Navegue a `http://localhost:8000/rates/exchange-rates/`.
   - Verifique que el par `USD/PYG` tiene cotización vigente (ej. Compra: `7.400`, Venta: `7.500`, Spread: `100`).
   - Haga clic en **"Crear Tasa"** (`/rates/exchange-rates/create/`) y registre una actualización para `USD/PYG`.
   - **Prueba de Validación:** Intente ingresar una tasa de venta menor a la de compra (ej: Compra 7500, Venta 7400). Compruebe que el sistema bloquea el registro con un mensaje de validación claro.
3. **Tablero Histórico (`/rates/dashboard/`):**
   - Acceda a `http://localhost:8000/rates/dashboard/`.
   - Seleccione el par `USD/PYG` y el rango de 30 días.
   - Compruebe el gráfico interactivo de fluctuación de compra y venta sembrado por `seed_data`.

---

### Módulo 3: Comisiones por Segmento y Bonificación de Spread (`rates`)

> **Rol Requerido:** Iniciar sesión con **`admin`**.

1. Acceda al listado de comisiones: `http://localhost:8000/rates/commissions/`.
2. Verifique la existencia de reglas para los segmentos:
   - **Minorista (MIN):** Comisión `1.5%`, Cargo fijo `0 PYG`, Descuento de spread `0%`.
   - **VIP (VIP):** Comisión `0.5%`, Cargo fijo `0 PYG`, Descuento de spread `50%`.
   - **Corporativo (COR):** Comisión `0.75%`, Cargo fijo `5.000 PYG`, Descuento de spread `30%`.
3. Ingrese a la regla VIP (`/rates/commissions/<id>/edit/`):
   - Modifique temporalmente el descuento de spread o cargo fijo y guarde los cambios.
   - Verifique que el detalle refleja los nuevos valores con precisión decimal.

---

### Módulo 4: Parámetros y Validación de Límites Operativos (`rates.OperationLimit`)

> **Rol Requerido:** Iniciar sesión con **`admin`** para configurar; **`cliente_*`** para validar.

1. Navegue a `http://localhost:8000/rates/limits/`.
2. Compruebe la matriz de topes operativos configurados por `seed_data`:
   - **Minorista - USD:** Mínimo: `10 USD`, Máximo: `5.000 USD`, Diario: `10.000 USD`.
   - **VIP - USD:** Mínimo: `100 USD`, Máximo: `50.000 USD`, Diario: `100.000 USD`.
   - **Corporativo - USD:** Mínimo: `500 USD`, Máximo: `200.000 USD`, Diario: `500.000 USD`.
3. **Prueba de Creación de Límite:**
   - Ingrese a `/rates/limits/add/`.
   - Seleccione segmento **Mayorista**, moneda **EUR**, monto mínimo `50`, máximo `30.000`. Guarde y verifique la persistencia.
4. **Validación de Regla:** Intente crear un límite donde el mínimo sea mayor al máximo (`mínimo: 5000`, `máximo: 1000`). Verifique el rechazo inmediato del formulario.

---

### Módulo 5: Catálogo Financiero y Medios de Pago del Cliente (`payments`)

> **Rol Requerido:** Iniciar sesión con **`cliente_minorista`**.

1. **Catálogo de Entidades Bancarias y Billeteras:**
   - Ingrese a `http://localhost:8000/payments/crear/`.
   - Observe los dropdowns de selección: compruebe que no son campos de texto libre, sino que muestran bancos reconocidos (*Banco Itaú, Continental, BNF, GNB, Ueno Bank*) y billeteras electrónicas (*Tigo Money, Personal, Wally, Zimple*).
2. **Formulario Dinámico Interactivo por Instrumento:**
   - **Pestaña Tarjeta de Crédito/Débito:** Ingrese número de tarjeta (con algoritmo de Luhn válido), fecha de expiración y CVV. Verifique el enmascaramiento automático de los primeros 12 dígitos (`**** **** **** 1234`).
   - **Pestaña Transferencia Bancaria:** Seleccione Banco, Tipo de Cuenta (Ahorro/Corriente), Número de Cuenta y Titular.
   - **Pestaña Billetera Móvil:** Seleccione Proveedor (ej: Tigo Money) e ingrese número de teléfono celular paraguayo (`0981xxxxxx`).
   - **Pestaña Efectivo:** Seleccione la sucursal de pago presencial autorizada.
3. **Exclusividad de Medio Predeterminado:**
   - En la lista `http://localhost:8000/payments/`, marque un medio como **Predeterminado**.
   - Verifique que cualquier otro medio predeterminado anterior pierde dicha marca de forma atómica.
4. **Protección Anti-IDOR:**
   - Copie la URL de edición de un medio de pago (`/payments/<id>/editar/`).
   - Inicie sesión en otra ventana de incógnito con **`cliente_vip`** y pegue la URL.
   - **Resultado esperado:** Respuesta `HTTP 404 Not Found` o `403 Forbidden`. No se permite visualizar ni alterar medios de pago de otro cliente.

---

### Módulo 6: Cuentas y Destinos de Acreditación de Fondos (`payments.ReceivingMethod`)

> **Rol Requerido:** Iniciar sesión con **`cliente_minorista`** o **`cliente_vip`**.

1. Ingrese a `http://localhost:8000/payments/acreditacion/`.
2. Compruebe las cuentas de acreditación existentes (donde el cliente recibe las divisas o guaraníes convertidos).
3. Haga clic en **"Registrar Cuenta de Acreditación"** (`/payments/acreditacion/crear/`):
   - Seleccione Entidad Financiera (ej: *Banco Continental*).
   - Elija Tipo de Cuenta (*Caja de Ahorro*).
   - Ingrese Número de Cuenta bancaria o Alias SIPAP.
   - Ingrese Nombre del Titular y marque como predeterminada.
4. Verifique que la cuenta se lista con un badge de *"Predeterminada"* y que la acción de borrado es una inactivación lógica (soft-delete) que preserva la integridad de transacciones pasadas.

---

### Módulo 7: Simulador y Cotizador en Vivo con Segmentación (`rates`)

> **Rol Requerido:** Iniciar sesión con **`cliente_vip`**, luego comparar con **`cliente_minorista`**.

1. Ingrese a `http://localhost:8000/rates/calculator/`.
2. **Prueba de Cotización VIP:**
   - Operación: **COMPRA** (El cliente compra USD y entrega PYG).
   - Par: Moneda base `USD`, Moneda destino `PYG`.
   - Ingrese Monto: `1.000 USD`.
   - Compruebe el desglose en tiempo real:
     - Tasa oficial base vs. Tasa preferencial VIP (con spread bonificado).
     - Comisión reducida del segmento VIP (`0.5%`).
     - Monto neto final a entregar en guaraníes.
3. **Prueba de Infracción de Límites:**
   - Ingrese un monto inferior al mínimo (ej: `5 USD`). Verifique la alerta de advertencia indicando que el monto es menor al mínimo permitido (`100 USD`).
   - Ingrese un monto superior al tope diario (ej: `200.000 USD`). Verifique la advertencia de límite excedido.

---

### Módulo 8: Emisión y Formalización de Transacción Cambiaria (`transactions`)

> **Rol Requerido:** Iniciar sesión con **`cliente_minorista`**.

1. Desde el Cotizador o navegando a `http://localhost:8000/transactions/create/`:
   - Seleccione Operación: **COMPRA**.
   - Par: `USD` a `PYG`.
   - Ingrese Monto: `200 USD`.
   - Seleccione **Medio de Pago Origen** (ej: *Transferencia Banco Itaú*).
   - Seleccione **Medio de Acreditación Destino** (ej: *Caja de Ahorro Banco Familiar*).
   - Haga clic en **"Solicitar Cotización y Continuar"**.
2. **Creación de la Orden:**
   - El sistema genera la orden en estado `PENDIENTE`.
   - La cotización queda formalmente congelada por exactamente **5 minutos (300 segundos)** con marca de tiempo `quote_expires_at`.
   - El sistema redirige automáticamente a la pantalla de confirmación.

---

### Módulo 9: Pantalla de Confirmación con Temporizador de 5 Minutos (`transactions`)

1. Observe la pantalla de confirmación (`/transactions/confirm/`):
   - **Temporizador en Vivo:** Verifique el reloj con cuenta regresiva en formato `04:59`, `04:58`...
   - **Desglose Transaccional:** Compruebe la tasa congelada, el importe a pagar en moneda origen, el desglose de comisiones y el importe líquido a recibir.
2. **Escenario A — Confirmación Exitosa:**
   - Haga clic en el botón verde **"Confirmar y Formalizar Transacción"** antes de que el temporizador llegue a 00:00.
   - **Resultado:** La transacción cambia atómicamente a estado **`CONFIRMADA`** (`COMPLETADA`), sellando el timestamp `confirmed_at`.
   - Se muestra un mensaje de éxito con el código correlativo único (ej: `TX-20260924-00001`).

---

### Módulo 10: Cancelación por Expiración y Cancelación Manual (`transactions`)

1. **Escenario B — Cancelación Voluntaria:**
   - Cree una nueva orden de cambio de `100 USD`.
   - En la pantalla de confirmación, haga clic en el botón rojo **"Cancelar Operación"**.
   - Ingrese un motivo (ej: *"Cambio de opinión sobre el monto"*).
   - **Resultado:** La orden pasa inmediatamente a estado **`CANCELADA`**, registrando el usuario y el motivo de la cancelación.
2. **Escenario C — Expiración Automática:**
   - Cree otra orden y permanezca en la pantalla hasta que el temporizador llegue a `00:00` (o simule el vencimiento temporal).
   - Al llegar a 0, la interfaz bloquea el botón de confirmación e informa que la cotización ha caducado.
   - Cualquier intento de confirmación extemporánea es rechazado por el backend, marcando la orden como **`EXPIRADA`** y obligando a recotizar con tasas actualizadas.

---

### Módulo 11: Historial, Filtros y Comprobante Oficial de Liquidación (`transactions`)

1. **Historial de Operaciones (`/transactions/`):**
   - Acceda a `http://localhost:8000/transactions/`.
   - Verifique la tabla paginada con las transacciones realizadas.
   - Pruebe los filtros:
     - Por Estado: filtre por `COMPLETADA` o `CANCELADA`.
     - Por Rango de Fechas: seleccione fecha desde/hasta.
     - Por Moneda: filtre por `USD`.
   - Compruebe que cada fila exhibe un badge de color según su estado (Verde: Confirmada, Amarillo: Pendiente, Rojo: Cancelada/Expirada).
2. **Detalle de Transacción (`/transactions/<id>/`):**
   - Haga clic en el botón de ver detalle de una orden completada.
   - Observe la ficha técnica completa con todos los hashes, cuentas involucradas y auditoría temporal.
3. **Comprobante de Transacción Cambiaria (`/transactions/<id>/receipt/`):**
   - En una transacción `CONFIRMADA`, haga clic en el botón **"Ver Comprobante"** o **"Imprimir Recibo"**.
   - Verifique el comprobante formal de liquidación con diseño corporativo:
     - Encabezado con datos fiscales de Global Exchange (RUC, dirección, teléfono).
     - Código de referencia correlativo y sello temporal.
     - Datos completos del cliente titular (RUC, razón social, segmento).
     - Desglose contable (Monto entregado, Tipo de cambio aplicado, Comisión por segmento, Monto neto recibido).
     - Cuentas financieras de débito y crédito.
   - Pruebe la función de impresión del navegador (`Ctrl + P`): observe que el template cuenta con estilos `@media print` que ocultan botones de navegación y formatean el comprobante para hoja tamaño A4 o recibo térmico.

---

### Módulo 12: Visualización de Documentación Técnica Sphinx (`config`)

1. Ingrese en el navegador a `http://localhost:8000/docs/`.
2. Compruebe que se carga la documentación técnica HTML autogenerada de Sphinx.
3. Navegue por el árbol de módulos:
   - `authentication`: backends OIDC, middlewares y templatetags.
   - `customers`: modelo `Cliente`, asignación `CustomerUserAssignment`, middleware y comando `seed_data`.
   - `payments`: `EntidadFinanciera`, `PaymentMethod`, `ReceivingMethod` y formularios.
   - `rates`: `Currency`, `ExchangeRate`, `SegmentCommission`, `OperationLimit` y servicios.
   - `transactions`: `Transaction`, `TransactionService`, vistas CBVs y APIs.
4. Verifique que los diagramas de clases, firmas de métodos y docstrings están completamente indexados.

---

## 5. Pruebas de Seguridad y Casos Borde (Checklist de Aprobación QA)

| # | Prueba de Seguridad / Caso Borde | Acción a Ejecutar | Resultado Esperado |
|---|---|---|---|
| **SEC-01** | **Prevención IDOR en Medios de Pago** | `cliente_minorista` intenta acceder a `/payments/<id_de_vip>/editar/`. | HTTP 404 / 403. Sin acceso a datos ajenos. |
| **SEC-02** | **Prevención IDOR en Transacciones** | `cliente_vip` intenta ver detalle `/transactions/<id_de_minorista>/`. | HTTP 404. Transacción aislada por cliente activo. |
| **SEC-03** | **Prevención IDOR en Comprobantes** | Usuario intenta descargar recibo `/transactions/<id_ajeno>/receipt/`. | HTTP 404. No se emite comprobante de terceros. |
| **LIM-01** | **Monto inferior al mínimo** | Cotizar orden con monto inferior a `min_amount`. | Alerta interactiva y bloqueo de confirmación. |
| **LIM-02** | **Monto superior al máximo** | Cotizar orden con monto que supere `max_amount` o tope diario. | Rechazo explícito con mensaje de límite excedido. |
| **TIME-01**| **Expiración de cotización (5 min)** | Intentar confirmar orden tras vencer `quote_expires_at`. | Estado cambia a `EXPIRADA`. Confirmación rechazada. |
| **DATA-01**| **Idempotencia de Seeding** | Ejecutar `python manage.py seed_data` dos veces consecutivas. | 0 errores de clave única. Catálogo intacto y actualizado. |
| **PREC-01**| **Precisión Decimal Financiera** | Revisar campos monetarios de transacciones en BD. | Tipo `Decimal` estricto, sin distorsión de coma flotante. |

---

## 6. Conclusión y Criterios de Aceptación Globales

Para certificar la entrega del sistema en el **Hito 5**, deben cumplirse las siguientes condiciones:

1. **Suite de Pruebas Unitarias:** 100% de aprobación (`Ran 289 tests in ~3.3s ... OK`).
2. **Documentación Sphinx:** Compilación limpia sin errores ni advertencias (`build succeeded`).
3. **Flujo Transaccional:** Registro, cotización congelada a 5 minutos, confirmación y comprobante funcionando de punta a punta.
4. **Seguridad Multi-Inquilino:** Aislamiento total por cliente activo verificado en todas las vistas y APIs.
