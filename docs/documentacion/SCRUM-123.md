# SCRUM-123: Orquestación Transaccional Atómica de Operaciones en Efectivo con Caja y Facturación

## Información General

| Campo | Valor |
|-------|-------|
| **Ticket** | SCRUM-123 |
| **Título** | Orquestación transaccional atómica de operaciones en efectivo con caja y facturación |
| **Rama** | `feature/SCRUM-123` |
| **Base** | `develop` |
| **Responsable** | Mauricio González |
| **Fecha** | 2026-11-05 |
| **Resuelto con IA** | Sí (Antigravity / Claude) |

---

## Descripción del Trabajo

Extender `apps/transactions/services.py` con `TransactionService.process_cash_payment()` para vincular el cobro/pago en efectivo con el turno de caja activo, generar el MovimientoCaja correspondiente, transicionar la transacción a COMPLETADA y disparar de forma atómica la emisión de la Factura Electrónica.

---

## Archivos Modificados

### 1. `transactions/services.py`
- **Nuevo método:** `TransactionService.process_cash_payment()` (~200 líneas)
- Implementa la orquestación atómica completa:
  1. Resolución e integridad de la Transacción Cambiaria con `select_for_update()`.
  2. Validación de estados previos (COMPLETADA, CANCELADA, no-PENDIENTE).
  3. Resolución del Operador/Cajero y Keycloak User ID para auditoría.
  4. Resolución y validación del Turno de Caja (CashShift) con soporte para:
     - Instancia directa de `CashShift`.
     - Instancia de `CashRegister` (toma el turno abierto actual).
     - ID numérico o shift_number como string.
     - Inferencia automática del turno abierto del cajero.
  5. Registro atómico de Movimientos de Efectivo (IN/OUT) vía `CashService.register_transaction_cash()`.
  6. Transición irreversible del estado a COMPLETADA con pasarela `EFECTIVO` y referencia `CASH-{caja}-{txId}`.
  7. Emisión atómica del Documento Tributario Electrónico:
     - `apps.invoicing` → `FacturaElectronica` SIFEN.
     - `transactions.kude_service` → `ElectronicInvoice` KuDE.
  8. Soporte para desglose de denominaciones de billetes (entrada/salida).
  9. Docstrings Sphinx completos con `:param`, `:type`, `:return`, `:raises`.

### 2. `apps/cash/models.py`
- **Nuevo alias:** `MovimientoCaja = CashMovement` para integración de dominio.

### 3. `apps/cash/services.py`
- **Extensión de firma:** `register_transaction_cash()` ahora acepta parámetros opcionales `denominations_in` y `denominations_out` para propagar el desglose de billetes a los movimientos individuales.

### 4. `apps/invoicing/providers/mock.py`
- **Fix defensivo:** `ruc_cliente_full` con fallback a `'44444401-7'` cuando `documento_ruc` es `None`.

### 5. `apps/__init__.py`
- **Registro de módulos:** Mapeo `apps.transactions.models` y `apps.transactions.services` en `sys.modules` para resolución de namespace.

### 6. `transactions/tests_cash_orchestration.py` (NUEVO)
- Suite completa de 11 pruebas unitarias/integración que cubren:
  - Alias `MovimientoCaja` disponible.
  - Ciclo de vida exitoso completo (IN, OUT, COMPLETADA, FacturaElectronica, ElectronicInvoice KuDE).
  - Rollback atómico por fondos insuficientes (`InsufficientCashBalanceError`).
  - Rechazo de transacciones ya completadas.
  - Rechazo de transacciones canceladas.
  - Fallo por turno de caja cerrado.
  - Inferencia automática de turno abierto.
  - Resolución por `CashRegister` e ID numérico.
  - Omisión de factura con `emitir_factura=False`.
  - IDs de transacción inválidos o inexistentes.
  - Acceso vía namespace `transactions.services`.

### 7. `transactions/tests.py`
- Importación del nuevo módulo de tests `tests_cash_orchestration`.

---

## Decisiones de Diseño

1. **Atomicidad ACID:** Todo el flujo está envuelto en `@transaction.atomic`. Si la caja no tiene fondos o el turno está cerrado, se hace rollback completo sin persistir estados inconsistentes.

2. **Patrón de resolución flexible:** `shift` acepta `CashShift`, `CashRegister`, `int`, `str` o `None` (inferencia), facilitando la integración desde vistas, APIs REST y endpoints de kiosco.

3. **Facturación dual:** Se emiten ambas facturas (SIFEN vía `apps.invoicing` y KuDE vía `transactions.kude_service`) para mantener compatibilidad con los dos subsistemas existentes. Errores en facturación se registran en logs pero no bloquean la liquidación.

4. **Denominaciones opcionales:** Se propagó el soporte de desglose de billetes (`denominations_in`/`denominations_out`) a `register_transaction_cash()` para trazabilidad física completa.

---

## Resultado de Tests

```
Ran 11 tests in 0.448s
OK
```

Suite completa del proyecto: sin regresiones.

