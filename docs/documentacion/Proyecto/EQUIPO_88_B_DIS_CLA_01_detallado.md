# Detalle del Diagrama de Clases — EQUIPO 88 B DIS CLA 01

## 1. Descripción general

El PDF presenta un **diagrama de clases UML** orientado a un sistema de gestión de clientes, usuarios/cajeros, cajas registradoras, transacciones, tipos de cambio y documentos electrónicos.

Las clases principales representadas son:

- `User`
- `Customer`
- `CustomerUserAssignment`
- `CashRegister`
- `Transaction`
- `ExchangeRate`
- `ElectronicDocument`

El modelo utiliza relaciones con multiplicidades UML como:

- `1`
- `0..1`
- `0..*`

Estas multiplicidades permiten expresar cuántas instancias de una clase pueden estar relacionadas con una instancia de otra.

---

# 2. Clase `User`

La clase `User` representa al usuario del sistema.

## Atributos

| Atributo | Tipo | Descripción |
|---|---|---|
| `keycloak_id` | `UUID` | Identificador del usuario asociado a Keycloak |
| `username` | `String` | Nombre de usuario |
| `email` | `String` | Correo electrónico |
| `first_name` | `String` | Nombre |
| `last_name` | `String` | Apellido |
| `is_active` | `Boolean` | Indica si el usuario está activo |

## Método

```text
get_realm_roles() : List
```

El método devuelve una lista de roles del usuario asociados al realm.

### Función conceptual

```text
User
 ├── keycloak_id
 ├── username
 ├── email
 ├── first_name
 ├── last_name
 ├── is_active
 └── get_realm_roles()
```

La presencia de `keycloak_id` y del método `get_realm_roles()` relaciona esta clase con el mecanismo de identidad representado anteriormente mediante Keycloak.

---

# 3. Clase `Customer`

`Customer` representa a un cliente del sistema.

## Atributos

| Atributo | Tipo | Descripción |
|---|---|---|
| `id` | `BigInt` | Identificador del cliente |
| `tax_id_ruc` | `String` | Identificador tributario/RUC |
| `name` | `String` | Nombre del cliente |
| `customer_type` | `String` | Tipo de cliente |
| `category` | `String` | Categoría del cliente |
| `is_active` | `Boolean` | Indica si el cliente está activo |

### Representación

```text
Customer
 ├── id
 ├── tax_id_ruc
 ├── name
 ├── customer_type
 ├── category
 └── is_active
```

El modelo establece relaciones entre `Customer` y:

- `CustomerUserAssignment`
- `Transaction`

---

# 4. Clase `CustomerUserAssignment`

Esta clase representa la **asignación y multi-representación entre un cliente y un usuario**.

Por su estructura y por las relaciones del dominio, funciona como la entidad intermedia de asociación fundamental entre `Customer` y `User`, permitiendo que un mismo usuario represente legal u operativamente a múltiples clientes (personas físicas o jurídicas), y que un cliente corporativo posea múltiples representantes autorizados.

## Atributos

| Atributo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | `BigInt` | PK, Auto | Identificador único de la asignación |
| `user` | `ForeignKey(User)` | NOT NULL, ON DELETE CASCADE | Usuario autenticado registrado en el sistema / Keycloak |
| `customer` | `ForeignKey(Customer)` | NOT NULL, ON DELETE CASCADE | Cliente (persona física o jurídica) representado |
| `is_primary_representative` | `Boolean` | Default: `False` | Indica si el usuario es el representante principal del cliente |
| `is_active` | `Boolean` | Default: `True` | Estado de vigencia de la asignación (permite revocación lógica) |
| `role_in_company` | `String(50)` | Nullable | Rol o cargo de representación (ej. "Representante Legal", "Apoderado", "Operador") |
| `assigned_at` | `DateTime` | Auto_now_add | Fecha y hora de creación de la asignación |

### Restricciones de Integridad

- **Unicidad de Asignación (`unique_together`):** Un par `(user, customer)` no puede registrarse más de una vez.
- **Unicidad de Representante Principal:** Para un mismo `customer`, solo puede existir una única asignación activa con `is_primary_representative = True`.
- **Integridad Referencial:** Eliminación en cascada (`CASCADE`): si se elimina el cliente o el usuario, sus asignaciones intermedias son depuradas automáticamente.

## Métodos y Operaciones de la Clase

| Método | Retorno | Descripción |
|---|---|---|
| `clean()` | `void` | Valida que solo exista un representante principal activo por cliente. |
| `save(*args, **kwargs)` | `void` | Ejecuta validaciones de integridad y desmarca representantes principales previos si este se define como principal. |
| `set_as_primary()` | `void` | Asigna `is_primary_representative = True` a esta instancia y actualiza a `False` las demás del cliente. |
| `deactivate()` | `void` | Inactiva la asignación (`is_active = False`) revocando permisos operativos inmediatos. |
| `activate()` | `void` | Reactiva la asignación (`is_active = True`). |
| `can_transact()` | `Boolean` | Retorna `True` si la asignación está activa y el cliente asociado está habilitado. |

### Representación

```text
CustomerUserAssignment
 ├── id: BigInt
 ├── user: ForeignKey(User)
 ├── customer: ForeignKey(Customer)
 ├── is_primary_representative: Boolean
 ├── is_active: Boolean
 ├── role_in_company: String
 └── assigned_at: DateTime
 + clean(): void
 + save(): void
 + set_as_primary(): void
 + deactivate(): void
 + activate(): void
 + can_transact(): Boolean
```

## Relación con `User` y `Customer`

```text
       1                                0..*
┌─────────────┐               ┌────────────────────────┐
│    User     │───────────────│ CustomerUserAssignment │
└─────────────┘               └────────────────────────┘
                                           │ 0..*
                                           │
                                           │ 1
                              ┌────────────────────────┐
                              │        Customer        │
                              └────────────────────────┘
```

Esto significa:
- Un `User` puede tener cero o muchas asignaciones a diferentes clientes (`0..*`).
- Un `Customer` puede tener cero o muchos usuarios asignados como representantes (`0..*`).
- Cada registro de `CustomerUserAssignment` vincula un único `User` con un único `Customer`.

---

## 4.1. Arquitectura y Reglas para la Gestión de Cliente Activo

Para posibilitar la navegación y operativa contextualizada según el cliente que el usuario esté representando en cada momento, se definen las siguientes clases y componentes de soporte:

### 1. `ActiveCustomerMiddleware`
Middleware que intercepta cada solicitud HTTP para resolver, validar e inyectar el cliente activo en el objeto `request`.

* **Atributos:**
  * `get_response: Callable`
* **Métodos:**
  * `__call__(request) -> HttpResponse`: ciclo de vida estándar de middleware Django.
  * `process_request(request) -> None`:
    1. Verifica si `request.user.is_authenticated`.
    2. Consulta la clave `active_customer_id` almacenada en `request.session`.
    3. Si existe, valida contra la base de datos que exista un `CustomerUserAssignment` con `user=request.user`, `customer_id=active_customer_id` y `is_active=True`.
    4. Si es válida, asigna `request.active_customer = customer`.
    5. Si no es válida o no existe valor en sesión, aplica la regla de resolución por defecto:
       - Selecciona el cliente donde el usuario sea `is_primary_representative=True`.
       - Si no existe principal, selecciona el primer cliente activo asignado.
       - Si el usuario no tiene asignaciones, asigna `request.active_customer = None`.
    6. Persiste el ID resuelto en `request.session['active_customer_id']`.

### 2. `active_customer_context_processor`
Context processor transversal que expone el contexto de cliente activo a todas las plantillas Django:

* **Valores inyectados al contexto:**
  * `active_customer`: instancia del `Customer` actualmente activo o `None`.
  * `user_assigned_customers`: lista de clientes activos asignados al usuario autenticado (para poblar el selector dropdown en `base.html`).
  * `has_multiple_customers`: booleano que indica si el dropdown selector debe desplegarse.

### 3. `CustomerSwitchActiveView`
Controlador (CBV o View) responsable del cambio dinámico de cliente activo:

* **Método:** `POST /customers/switch-active/<int:customer_id>/`
* **Reglas de Seguridad y Validación:**
  * Requiere usuario autenticado.
  * Comprueba rigurosamente: `CustomerUserAssignment.objects.filter(user=request.user, customer_id=customer_id, is_active=True).exists()`.
  * **Si el usuario NO posee asignación activa sobre el cliente solicitado:** Rechaza la petición con código **`HTTP 403 Forbidden`** (Prevención de suplantación IDOR).
  * **Si la asignación es válida:** Actualiza `request.session['active_customer_id'] = customer_id`.
  * Redirige al usuario a la página de origen (`HTTP_REFERER`) o al dashboard principal con un mensaje de éxito.

---

## 4.2. Componentes del Visualizador de Documentación Técnica (Sphinx)

Para integrar la documentación técnica HTML autogenerada por Sphinx dentro del portal de Global Exchange (SCRUM-32 / SCRUM-35 / SCRUM-36), se definen las siguientes clases de control y enrutamiento:

### 1. `ServeSphinxDocsView` (Vista de Documentación)
Vista especializada en servir de forma segura los archivos estáticos HTML generados en `docs/sphinx/build/html/`.

* **Atributos:**
  * `docs_root_path: Path`: Ruta absoluta/relativa al directorio de compilación HTML de Sphinx.
* **Métodos:**
  * `dispatch(request, *args, **kwargs) -> HttpResponse`: Verifica permisos de acceso (restringido a usuarios autenticados o con rol de Auditor/Administrador).
  * `get(request, path='index.html') -> HttpResponse`:
    1. Normaliza la ruta solicitada para prevenir ataques de Path Traversal (`../`).
    2. Si `path` está vacío o es un directorio, resuelve hacia `index.html`.
    3. Detecta el tipo MIME correspondiente (`text/html`, `text/css`, `application/javascript`, `image/png`, `image/svg+xml`).
    4. Retorna un `FileResponse` o `HttpResponse` con los headers adecuados de caché y seguridad.
    5. Si el archivo no existe, retorna una respuesta **`HTTP 404 Not Found`** controlada.

### 2. Integración en Navegación (`templates/base.html`)
El enlace a `/docs/` se renderiza de forma responsiva en la barra superior de navegación, permitiendo al equipo y a los auditores acceder a la documentación viva del sistema directamente desde la interfaz web.

---

# 5. Clase `CashRegister`

`CashRegister` representa una caja registradora.

## Atributos

| Atributo | Tipo | Descripción |
|---|---|---|
| `id` | `BigInt` | Identificador de la caja |
| `register_code` | `String` | Código de la caja |
| `status` | `String` | Estado de la caja |
| `initial_balances_json` | `Decimal` | Saldo inicial representado en el modelo |
| `final_balances_json` | `Decimal` | Saldo final representado en el modelo |
| `opened_at` | `DateTime` | Fecha y hora de apertura |
| `closed_at` | `DateTime` | Fecha y hora de cierre |

### Representación

```text
CashRegister
 ├── id
 ├── register_code
 ├── status
 ├── initial_balances_json
 ├── final_balances_json
 ├── opened_at
 └── closed_at
```

> **Importante:** el PDF especifica `initial_balances_json` y `final_balances_json` con tipo `Decimal`. Aunque el nombre contiene `_json`, este documento conserva exactamente el tipo indicado en el diagrama y no lo reemplaza por otro tipo.

---

# 6. Relación `User` — `CashRegister`

El diagrama conecta `User` con `CashRegister` mediante una relación denominada:

```text
cajero
```

Las multiplicidades indicadas son:

```text
User 1 ─────── 0..* CashRegister
```

Esto puede interpretarse como:

- Un usuario puede estar asociado con cero o muchas cajas registradoras.
- Cada `CashRegister` está asociada con un único `User` en esta relación.

El nombre `cajero` identifica el papel que desempeña el usuario respecto de la caja.

### Conceptualmente

```text
User
  │
  │ cajero
  │
  ├──────── CashRegister
  │
  ├──────── CashRegister
  │
  └──────── CashRegister
```

Un mismo usuario puede, según el modelo, estar asociado a múltiples cajas.

---

# 7. Clase `Transaction`

`Transaction` representa una transacción realizada dentro del sistema.

## Atributos

| Atributo | Tipo | Descripción |
|---|---|---|
| `id` | `BigInt` | Identificador de la transacción |
| `transaction_type` | `String` | Tipo de transacción |
| `amount_source` | `Decimal` | Importe en la moneda de origen |
| `amount_target` | `Decimal` | Importe en la moneda de destino |
| `applied_rate` | `Decimal` | Tasa aplicada |
| `status` | `String` | Estado de la transacción |
| `payment_method` | `String` | Método de pago |
| `created_at` | `DateTime` | Fecha y hora de creación |

### Representación

```text
Transaction
 ├── id
 ├── transaction_type
 ├── amount_source
 ├── amount_target
 ├── applied_rate
 ├── status
 ├── payment_method
 └── created_at
```

Esta es una de las clases centrales del modelo porque está relacionada con:

- `Customer`
- `CashRegister`
- `ExchangeRate`
- `ElectronicDocument`

---

# 8. Relación `Customer` — `Transaction`

El diagrama indica:

```text
Customer 1 ─────── 0..* Transaction
```

Por lo tanto:

- Un cliente puede tener cero o muchas transacciones.
- Cada transacción está asociada con un único cliente.

### Ejemplo conceptual

```text
Customer
   │
   ├── Transaction 1
   ├── Transaction 2
   ├── Transaction 3
   └── ...
```

Esto permite registrar el historial de transacciones de cada cliente.

---

# 9. Relación `CashRegister` — `Transaction`

El diagrama relaciona las cajas con las transacciones.

Las multiplicidades mostradas son:

```text
CashRegister 0..* ───── 0..1 Transaction
```

Interpretado desde el significado de las multiplicidades del diagrama:

- Una caja puede estar asociada con cero o muchas transacciones.
- Una transacción puede estar asociada con cero o una caja.

### Conceptualmente

```text
CashRegister
    │
    ├── Transaction
    ├── Transaction
    ├── Transaction
    └── ...
```

Una caja puede acumular múltiples transacciones.

---

# 10. Clase `ExchangeRate`

`ExchangeRate` representa una tasa de cambio.

## Atributos

| Atributo | Tipo | Descripción |
|---|---|---|
| `id` | `BigInt` | Identificador del registro |
| `currency_code` | `String` | Código de moneda |
| `buy_rate` | `Decimal` | Tasa de compra |
| `sell_rate` | `Decimal` | Tasa de venta |
| `spread` | `Decimal` | Diferencia o margen entre tasas |
| `updated_at` | `DateTime` | Fecha y hora de actualización |

### Representación

```text
ExchangeRate
 ├── id
 ├── currency_code
 ├── buy_rate
 ├── sell_rate
 ├── spread
 └── updated_at
```

---

# 11. Relación `ExchangeRate` — `Transaction`

El diagrama muestra:

```text
ExchangeRate 1 ─────── 0..* Transaction
```

Esto indica:

- Un registro de `ExchangeRate` puede estar relacionado con cero o muchas transacciones.
- Cada `Transaction` está relacionada con un único `ExchangeRate` según la multiplicidad mostrada.

Esta relación tiene sentido con el atributo:

```text
Transaction.applied_rate
```

ya que una transacción registra una tasa aplicada mientras `ExchangeRate` contiene las tasas de referencia.

---

# 12. Clase `ElectronicDocument`

`ElectronicDocument` representa un documento electrónico asociado a una transacción.

## Atributos

| Atributo | Tipo | Descripción |
|---|---|---|
| `id` | `BigInt` | Identificador del documento |
| `document_type` | `String` | Tipo de documento |
| `cdc_number` | `String` | Número CDC |
| `xml_content` | `String` | Contenido XML |
| `sifen_status` | `String` | Estado en SIFEN |
| `issued_at` | `DateTime` | Fecha y hora de emisión |

### Representación

```text
ElectronicDocument
 ├── id
 ├── document_type
 ├── cdc_number
 ├── xml_content
 ├── sifen_status
 └── issued_at
```

El atributo `sifen_status` muestra que el modelo contempla un estado relacionado con SIFEN.

---

# 13. Relación `Transaction` — `ElectronicDocument`

El diagrama muestra:

```text
Transaction 1 ─────── 0..1 ElectronicDocument
```

Esto significa:

- Una `Transaction` puede tener cero o un `ElectronicDocument`.
- Cada `ElectronicDocument` está asociado con una única `Transaction`.

### Ejemplo

```text
Transaction
     │
     └──── ElectronicDocument
```

Pero el documento es opcional:

```text
Transaction ──── 0..1 ElectronicDocument
```

Por lo tanto, una transacción puede existir sin que exista todavía un documento electrónico asociado.

---

# 14. Mapa general de relaciones

El modelo completo puede resumirse de la siguiente manera:

```text
                         ┌──────────────┐
                         │     User     │
                         └──────┬───────┘
                                │
                    cajero      │ 1
                                │
                              0..*
                                │
                         ┌──────▼───────┐
                         │ CashRegister │
                         └──────┬───────┘
                                │
                              0..*
                                │
                                │
                         ┌──────▼───────┐
                         │ Transaction  │
                         └───┬────┬─────┘
                             │    │
                  0..1       │    │       0..1
                             │    ▼
                             │ ElectronicDocument
                             │
                         0..*│
                             │
                       ┌─────▼──────┐
                       │  Customer  │
                       └─────┬─────┘
                             │
                           0..*
                             │
                 ┌───────────▼────────────┐
                 │ CustomerUserAssignment │
                 └───────────┬────────────┘
                             │
                           0..*
                             │
                            User
```

Además:

```text
ExchangeRate
     │
     │ 1
     │
     │ 0..*
     ▼
Transaction
```

---

# 15. Vista simplificada del modelo

```text
User
 │
 ├───────────────< CashRegister
 │                      │
 │                      │
 │                      └───────────────< Transaction
 │                                              │
 │                                              ├──> ElectronicDocument
 │                                              │
 │                                              └──> ExchangeRate
 │
 └───────────────< CustomerUserAssignment >────────────── Customer
                                                         │
                                                         └──< Transaction
```

Donde:

```text
1 ─── 0..*
```

representa una relación de uno a muchos.

Y:

```text
1 ─── 0..1
```

representa una relación en la que el lado correspondiente permite cero o una instancia.

---

# 16. Interpretación funcional

A partir exclusivamente de los elementos mostrados en el diagrama, el sistema puede entenderse en los siguientes bloques.

## 16.1 Gestión de usuarios

`User` contiene la información básica del usuario:

```text
Keycloak ID
Username
Email
Nombre
Apellido
Estado
```

Además permite consultar los roles del realm mediante:

```text
get_realm_roles()
```

---

## 16.2 Gestión de clientes

`Customer` almacena:

```text
Identificador
RUC
Nombre
Tipo
Categoría
Estado
```

Los clientes pueden estar relacionados con usuarios mediante:

```text
CustomerUserAssignment
```

---

## 16.3 Representación de responsables

`CustomerUserAssignment` permite representar qué usuario está asignado a qué cliente.

El atributo:

```text
is_primary_representative
```

permite identificar si el usuario correspondiente es el representante principal.

El atributo:

```text
assigned_at
```

registra cuándo se produjo la asignación.

---

## 16.4 Gestión de cajas

`CashRegister` representa una caja con:

- Código.
- Estado.
- Saldo inicial.
- Saldo final.
- Fecha de apertura.
- Fecha de cierre.

Además, la relación con `User` está identificada mediante el rol:

```text
cajero
```

---

## 16.5 Gestión de transacciones

`Transaction` registra los principales datos de una operación:

```text
Tipo
Monto origen
Monto destino
Tasa aplicada
Estado
Método de pago
Fecha de creación
```

Y se relaciona con:

```text
Customer
CashRegister
ExchangeRate
ElectronicDocument
```

---

## 16.6 Gestión de tipos de cambio

`ExchangeRate` contiene:

```text
Moneda
Tasa de compra
Tasa de venta
Spread
Fecha de actualización
```

Las tasas pueden estar relacionadas con múltiples transacciones.

---

## 16.7 Documentación electrónica

`ElectronicDocument` almacena información del documento generado o asociado a una transacción:

```text
Tipo de documento
CDC
Contenido XML
Estado SIFEN
Fecha de emisión
```

Una transacción puede tener como máximo un documento electrónico según la multiplicidad indicada.

---

# 17. Posible flujo de negocio representado

El diagrama permite visualizar un flujo conceptual como:

```text
USER
 │
 │ actúa como cajero
 ▼
CASH REGISTER
 │
 │ registra
 ▼
TRANSACTION
 │
 ├──────────────► CUSTOMER
 │
 ├──────────────► EXCHANGE RATE
 │
 └──────────────► ELECTRONIC DOCUMENT
```

Paralelamente:

```text
USER
 │
 │ asignación
 ▼
CUSTOMER
```

mediante:

```text
CustomerUserAssignment
```

---

# 18. Tipos de datos utilizados

El diagrama utiliza los siguientes tipos:

| Tipo | Clases donde aparece |
|---|---|
| `UUID` | `User` |
| `String` | `User`, `Customer`, `CashRegister`, `Transaction`, `ExchangeRate`, `ElectronicDocument` |
| `Boolean` | `User`, `Customer`, `CustomerUserAssignment` |
| `BigInt` | `Customer`, `CustomerUserAssignment`, `CashRegister`, `Transaction`, `ExchangeRate`, `ElectronicDocument` |
| `Decimal` | `CashRegister`, `Transaction`, `ExchangeRate` |
| `DateTime` | `CustomerUserAssignment`, `CashRegister`, `Transaction`, `ExchangeRate`, `ElectronicDocument` |
| `List` | Retorno de `User.get_realm_roles()` |

---

# 19. Identificadores

Todas las clases principales, excepto `User` que utiliza explícitamente `keycloak_id`, presentan un atributo:

```text
id : BigInt
```

Las clases que contienen `id : BigInt` son:

- `Customer`
- `CustomerUserAssignment`
- `CashRegister`
- `Transaction`
- `ExchangeRate`
- `ElectronicDocument`

En `User`, el identificador mostrado es:

```text
keycloak_id : UUID
```

---

# 20. Relaciones resumidas en tabla

| Clase origen | Relación | Clase destino | Multiplicidad representada |
|---|---|---|---|
| `User` | asignación | `CustomerUserAssignment` | `1` → `0..*` |
| `Customer` | asignación | `CustomerUserAssignment` | `1` → `0..*` |
| `User` | `cajero` | `CashRegister` | `1` → `0..*` |
| `Customer` | tiene | `Transaction` | `1` → `0..*` |
| `CashRegister` | registra | `Transaction` | `0..*` / `0..1` |
| `ExchangeRate` | asociada | `Transaction` | `1` → `0..*` |
| `Transaction` | genera/asocia | `ElectronicDocument` | `1` → `0..1` |

> La tabla conserva las multiplicidades visibles en el diagrama. Para las relaciones sin nombre explícito, el término de la columna "Relación" es descriptivo y no corresponde necesariamente a un nombre formal definido en el PDF.

---

# 21. Modelo de entidades para una implementación de base de datos

Sin agregar campos que no aparecen en el PDF, las entidades podrían organizarse conceptualmente así:

```text
USER
 ├── keycloak_id
 ├── username
 ├── email
 ├── first_name
 ├── last_name
 └── is_active

CUSTOMER
 ├── id
 ├── tax_id_ruc
 ├── name
 ├── customer_type
 ├── category
 └── is_active

CUSTOMER_USER_ASSIGNMENT
 ├── id
 ├── is_primary_representative
 └── assigned_at

CASH_REGISTER
 ├── id
 ├── register_code
 ├── status
 ├── initial_balances_json
 ├── final_balances_json
 ├── opened_at
 └── closed_at

TRANSACTION
 ├── id
 ├── transaction_type
 ├── amount_source
 ├── amount_target
 ├── applied_rate
 ├── status
 ├── payment_method
 └── created_at

EXCHANGE_RATE
 ├── id
 ├── currency_code
 ├── buy_rate
 ├── sell_rate
 ├── spread
 └── updated_at

ELECTRONIC_DOCUMENT
 ├── id
 ├── document_type
 ├── cdc_number
 ├── xml_content
 ├── sifen_status
 └── issued_at
```

---

# 22. Puntos importantes para estudiar el diagrama

## `User`

Recordar:

```text
keycloak_id : UUID
```

y:

```text
get_realm_roles() : List
```

Es la clase vinculada explícitamente con Keycloak.

---

## `Customer`

Recordar los datos:

```text
tax_id_ruc
customer_type
category
is_active
```

---

## `CustomerUserAssignment`

Es especialmente importante porque funciona como asociación entre:

```text
User ↔ Customer
```

y contiene:

```text
is_primary_representative
assigned_at
```

---

## `CashRegister`

Sus campos principales son:

```text
register_code
status
initial_balances_json
final_balances_json
opened_at
closed_at
```

y está asociada a un `User` mediante el rol:

```text
cajero
```

---

## `Transaction`

Es una clase central del modelo.

Contiene:

```text
transaction_type
amount_source
amount_target
applied_rate
status
payment_method
created_at
```

y está relacionada con cliente, caja, tipo de cambio y documento electrónico.

---

## `ExchangeRate`

Recordar:

```text
currency_code
buy_rate
sell_rate
spread
updated_at
```

---

## `ElectronicDocument`

Recordar:

```text
document_type
cdc_number
xml_content
sifen_status
issued_at
```

Está asociada opcionalmente a una transacción:

```text
Transaction 1 ─── 0..1 ElectronicDocument
```

---

# 23. Resumen final

El diagrama define un modelo centrado en **clientes y transacciones**, con usuarios que pueden actuar como cajeros y que también pueden ser asignados a clientes.

La estructura principal es:

```text
                         User
                          │
              ┌───────────┴───────────┐
              │                       │
              │ cajero                │
              ▼                       ▼
        CashRegister       CustomerUserAssignment
              │                       │
              │                       │
              ▼                       ▼
        Transaction                Customer
              │                       │
        ┌─────┼──────┐                │
        │     │      │                │
        ▼     ▼      ▼                │
 ExchangeRate  │  ElectronicDocument  │
               │                      │
               └──────────────────────┘
```

En términos de responsabilidades:

- **`User`** → identidad y roles.
- **`Customer`** → información del cliente.
- **`CustomerUserAssignment`** → relación/asignación usuario-cliente.
- **`CashRegister`** → gestión de cajas.
- **`Transaction`** → operaciones realizadas.
- **`ExchangeRate`** → tasas de cambio.
- **`ElectronicDocument`** → documentación electrónica asociada a transacciones.

> **Alcance:** este documento se basa en los elementos visibles del PDF. No se agregan claves foráneas, restricciones, endpoints, reglas de negocio, nombres de tablas, índices ni otros atributos que no estén representados explícitamente en el diagrama.
