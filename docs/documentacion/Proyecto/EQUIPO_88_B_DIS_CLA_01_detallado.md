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

Esta clase representa la **asignación entre un cliente y un usuario**.

Por su estructura y por las relaciones del diagrama, funciona como una entidad de asociación entre `Customer` y `User`.

## Atributos

| Atributo | Tipo | Descripción |
|---|---|---|
| `id` | `BigInt` | Identificador de la asignación |
| `is_primary_representative` | `Boolean` | Indica si el usuario es el representante principal |
| `assigned_at` | `DateTime` | Fecha y hora de asignación |

### Representación

```text
CustomerUserAssignment
 ├── id
 ├── is_primary_representative
 └── assigned_at
```

## Relación con `User`

El diagrama muestra:

```text
User 1 ───────── 0..* CustomerUserAssignment
```

Esto significa:

- Un `User` puede tener cero o muchas asignaciones.
- Cada `CustomerUserAssignment` se relaciona con un único `User`.

## Relación con `Customer`

El diagrama muestra:

```text
Customer 1 ────── 0..* CustomerUserAssignment
```

Esto significa:

- Un `Customer` puede tener cero o muchas asignaciones.
- Cada `CustomerUserAssignment` se relaciona con un único `Customer`.

### Modelo conceptual

```text
             1                 0..*
User ───────────── CustomerUserAssignment
                       ▲
                       │
             0..*      │      1
Customer ──────────────┘
```

Esta estructura permite que un cliente pueda estar asociado con varios usuarios y que un usuario pueda estar asociado con varios clientes, utilizando `CustomerUserAssignment` como entidad intermedia.

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
