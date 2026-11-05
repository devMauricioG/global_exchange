# SCRUM-118: Modelado de Factura Electrónica y Persistencia de CDC, Estados SIFEN, KuDE PDF y XML

## 📌 Metadatos de la Tarea

* **Ticket:** SCRUM-118
* **Épica:** SCRUM-7 (Módulo de Caja, Terminal de Autoservicio, Simulación de Efectivo y Facturación Electrónica Segura)
* **Historia de Usuario:** SCRUM-110 (Integración de Facturación Electrónica SIFEN con Control Estricto de Cuota)
* **Sprint:** SCRUM Sprint 5
* **Responsable:** Mauricio González
* **Estado:** Finalizado
* **Bloquea:** SCRUM-119, SCRUM-123

---

## 🎯 Objetivo y Alcance

Implementar en el módulo canónico de facturación (`apps/invoicing/`) la capa de persistencia formal para el Documento Tributario Electrónico (DTE) y su representación gráfica KuDE, cumpliendo con los estándares exigidos por la Dirección Nacional de Ingresos Tributarios (**DNIT** / SET) en el marco del **SIFEN** / e-Kuatia y la especificación técnica **"API de Factura Segura para ESI v01"**.

La solución implementada contempla:

1. **Modelo Canónico `FacturaElectronica` (`apps/invoicing/models.py`):**
   * Vinculación `OneToOneField` estricta con `transactions.Transaction` (vía `related_name='factura_sifen'`), garantizando que cada operación cambiaria cuente con a lo sumo un comprobante fiscal.
   * Clave de Acceso / CDC (*Código de Control*) de 44 dígitos numéricos con restricción de unicidad (`unique=True`) e índice de búsqueda acelerada (`db_index=True`).
   * Número legal de comprobante en formato oficial `001-001-0000001` (Establecimiento-PuntoExpedición-Secuencia).
   * Datos fiscales de las partes intervinientes (RUC y Razón Social del emisor y receptor).
   * Condiciones comerciales estandarizadas (`CondicionVenta`: `CONTADO`, `CREDITO`) y valores monetarios con precisión decimal de 4 dígitos.
   * Ciclo de vida y estados oficiales SIFEN (`EstadoSifen`: `EMITIDO`, `APROBADO`, `APROBADO_OBS`, `RECHAZADO`, `CANCELADO`, `INUTILIZADO`, `VERIFICAR_DATOS`, `SOL_APROBACION`, `ENVIADO_A_SIFEN`, `ERROR_SIFEN`).
   * Almacenamiento íntegro de la respuesta del PAC/SIFEN en `JSONField` (`respuesta_sifen_raw`) para auditoría forense y resolución de controversias tributarias.
   * Persistencia dual de artefactos: campo de texto canónico `xml_firmado` y archivos físicos mediante `FileField` para XML firmado (`invoicing/xml/%Y/%m/`) y KuDE en formato PDF binario (`invoicing/kude/%Y/%m/`).
   * Enlace oficial de consulta pública mediante código QR (`qr_data`).
   * Bandera de seguridad y auditoría `es_simulada` (`default=True`) para garantizar que ninguna emisión en desarrollo consuma cuota real o impacte la contabilidad fiscal.
   * Propiedades calculadas: `cdc_formatted` (formato canónico de 11 grupos de 4 dígitos separados por guiones), `is_aprobado`, `is_cancelado`, `is_inutilizado`.
   * Métodos auxiliares de almacenamiento de contenido: `save_xml_content()` y `save_pdf_content()`.

2. **Servicio de Dominio `InvoiceService` (`apps/invoicing/services.py`):**
   * `create_from_response(transaction, invoice_response)`: Orquestación transaccional (`transaction.atomic`) para instanciar, poblar y persistir `FacturaElectronica` con sus archivos binarios XML y KuDE PDF a partir de cualquier proveedor SIFEN (`MockInvoiceProvider` o `FacturaSeguraProvider`).
   * `update_estado(cdc, status_response)`: Actualización atómica de estados y payloads raw ante respuestas asíncronas de consulta o cancelación con bloqueo pesimista (`select_for_update`).
   * `get_or_create_for_transaction(transaction, invoice_response)`: Operación idempotente para evitar duplicación de facturas electrónicas.
   * Normalización y mapeo tolerante de cadenas de estados heterogéneas (`_map_estado`).

3. **Panel de Auditoría Administrativa (`apps/invoicing/admin.py`):**
   * Registro completo de `FacturaElectronica` en el Django Admin como entidad inmutable (`readonly_fields`).
   * Visualización enriquecida con badges de color según el estado tributario SIFEN (`estado_sifen_badge`).
   * Truncamiento visual de CDC en el listado y visualización formateada en el detalle.
   * Filtros multidimensionales (`estado_sifen`, `es_simulada`, `condicion_venta`, `moneda`) y búsqueda por CDC, número, RUC y razón social.

4. **Migración Inicial de Base de Datos:**
   * `apps/invoicing/migrations/0001_initial.py` creada y verificada contra el motor de migraciones de Django.

---

## 📐 Diagrama de Relación y Persistencia

```
┌─────────────────────────────────┐
│     transactions.Transaction    │
│─────────────────────────────────│
│ • id                            │
│ • codigo_referencia             │
│ • cliente                       │
│ • monto_destino                 │
│ • target_currency               │
└───────────────▲─────────────────┘
                │ 1
                │ (OneToOneField)
                │ 1
┌───────────────┴─────────────────┐
│        FacturaElectronica       │
│─────────────────────────────────│
│ • cdc (44 dígitos, UNIQUE)      │
│ • numero_factura (001-001-...)  │
│ • timbrado, ruc_emisor/receptor │
│ • condicion_venta (CONTADO/...) │
│ • monto_total, moneda           │
│ • estado_sifen (APROBADO/...)   │
│ • respuesta_sifen_raw (JSON)    │
│ • xml_firmado (TextField)       │
│ • archivo_xml (FileField)       │
│ • archivo_pdf (FileField)       │
│ • qr_data (TextField)           │
│ • es_simulada (BooleanField)    │
│ • fecha_emision, created_at     │
└─────────────────────────────────┘
```

---

## 📋 Detalle de Archivos Creados e Intervenidos

| Archivo | Rol / Contenido |
| :--- | :--- |
| `apps/invoicing/models.py` | Definición del modelo canónico `FacturaElectronica`, `CondicionVenta`, `EstadoSifen`, propiedades y métodos. |
| `apps/invoicing/migrations/0001_initial.py` | Migración inicial de Django con la creación de la tabla y los 4 índices de optimización. |
| `apps/invoicing/admin.py` | Panel de auditoría de Django Admin con badges HTML de colores y campos de solo lectura. |
| `apps/invoicing/services.py` | Capa de servicio de dominio `InvoiceService` (`create_from_response`, `update_estado`, `get_or_create_for_transaction`). |
| `apps/invoicing/__init__.py` | Exportaciones y carga diferida (`__getattr__`) para `FacturaElectronica` e `InvoiceService`. |
| `apps/invoicing/tests.py` | 25 nuevas pruebas unitarias y de integración para el modelo y el servicio (totalizando 50 tests en la app). |
| `docs/sphinx/source/invoicing.rst` | Documentación técnica Sphinx actualizada con módulos `models`, `services` y `admin`. |
| `docs/documentacion/SCRUM-118.md` | Memoria técnica detallada de la tarea. |
| `docs/documentacion/Jira workflow/TAREAS.md` | Actualización de estado del ticket a `Finalizado`. |
| `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md` | Registro de resolución en la bitácora consolidada de IA (#26). |
| `docs/chat_ia.md` | Bitácora de diálogo con el asistente para trazabilidad de equipo. |

---

## 🧪 Pruebas Unitarias y Cobertura

Se incorporaron **25 pruebas unitarias** específicas para SCRUM-118, organizadas en dos clases de prueba:

### `FacturaElectronicaModelTests` (15 pruebas):
* `test_create_minimal_factura`: Persistencia exitosa con campos obligatorios.
* `test_str_representation`: Formato descriptivo `Factura {numero} ({cdc[:8]}...) - {estado} [SIMULADA]`.
* `test_cdc_formatted_property`: Formateo correcto en 11 bloques de 4 dígitos.
* `test_cdc_formatted_blank`: Manejo defensivo ante CDC nulo o vacío.
* `test_is_aprobado_property`: Predicado booleano para estados `APROBADO` y `APROBADO_OBS`.
* `test_is_cancelado_property`: Predicado booleano para estado `CANCELADO`.
* `test_is_inutilizado_property`: Predicado booleano para estado `INUTILIZADO`.
* `test_es_simulada_default_true`: Garantía de valor `True` por defecto para prevención de consumo de cuota.
* `test_unique_cdc_constraint`: Disparo de `IntegrityError` ante colisión de CDC de 44 dígitos.
* `test_one_to_one_relation_with_transaction`: Relación bidireccional mediante `transaction.factura_sifen`.
* `test_respuesta_sifen_raw_json`: Serialización y recuperación íntegra de diccionario en `JSONField`.
* `test_save_xml_content`: Generación y persistencia simultánea en `TextField` y `FileField`.
* `test_save_pdf_content`: Persistencia binaria del KuDE PDF en disco.
* `test_created_at_updated_at_auto`: Asignación automática de marcas temporales.
* `test_estado_sifen_choices` y `test_condicion_venta_choices`: Integridad de enumeraciones `TextChoices`.

### `InvoiceServiceTests` (10 pruebas):
* `test_create_from_response_creates_factura`: Creación completa a partir de `InvoiceResponse`.
* `test_create_from_response_persists_xml`: Persistencia del XML firmado provisto por el proveedor.
* `test_create_from_response_persists_pdf`: Persistencia del KuDE PDF binario.
* `test_create_from_response_estado_aprobado`: Verificación del estado aprobado tras emisión mock.
* `test_update_estado`: Transición de estado a cancelado y persistencia de nuevo payload raw.
* `test_get_or_create_returns_existing`: Idempotencia de consulta/creación por transacción.
* `test_map_estado_normalizes_aprobado`: Normalización de variantes textuales de 'Aprobado'.
* `test_map_estado_normalizes_cancelado`: Normalización de variantes textuales de 'Cancelado'.
* `test_map_estado_unknown_defaults_to_emitido`: Fallback seguro a `EMITIDO` ante cadenas no reconocidas.

### Resultados Globales de la Suite:
* **Pruebas en `apps.invoicing`:** 50/50 pasadas satisfactoriamente (0 fallos, 0 errores).
* **Pruebas del proyecto global:** 631/631 pasadas satisfactoriamente (100% OK, sin regresiones).
