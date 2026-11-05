# SCRUM-119: Vistas y Endpoints para Consulta, Visualización y Descarga de KuDE PDF y XML Firmado

## 📌 Metadatos de la Tarea

* **Ticket:** SCRUM-119
* **Épica:** SCRUM-7 (Módulo de Caja, Terminal de Autoservicio, Simulación de Efectivo y Facturación Electrónica Segura)
* **Historia de Usuario:** SCRUM-110 (Integración de Facturación Electrónica SIFEN con Control Estricto de Cuota)
* **Sprint:** SCRUM Sprint 5
* **Responsable:** Mauricio González
* **Estado:** Finalizado
* **Bloquea:** SCRUM-125, SCRUM-126

---

## 🎯 Objetivo y Alcance

Diseñar e implementar en el sistema las vistas interactivas, endpoints de servicio y componentes de interfaz gráfica para la visualización integrada, consulta, descarga y sincronización en tiempo real del Documento Tributario Electrónico (DTE) y su representación gráfica KuDE (Kuatia'ahekaha Digital Electrónico), cumpliendo estrictamente con los lineamientos técnicos de la Dirección Nacional de Ingresos Tributarios (**DNIT** / SIFEN / e-Kuatia) y la especificación técnica **"API de Factura Segura para ESI v01"**.

La solución comprende:

1. **Card Integrada de Factura Electrónica en el Detalle de Transacción (`templates/transactions/transaction_detail.html`):**
   * Panel visual de alta fidelidad integrado en la vista de comprobante cambiario (`TransactionDetailView`).
   * Visualización del Número Legal de Factura (`001-001-XXXXXXX`) y Timbrado Oficial (`12548963`).
   * Despliegue de la Clave de Acceso / CDC de 44 dígitos en formato canónico (11 grupos de 4 dígitos) con botón interactivo de 1-click para copiado al portapapeles (`copyCdcToClipboard()`) con feedback visual temporal.
   * Badges de estado SIFEN en tiempo real (Aprobado, Aprobado con Observación, Rechazado, Cancelado, Inutilizado, etc.) con indicador de entorno (`⚡ Simulador SIFEN / 0 Cuota` o `🏛️ e-Kuatia Oficial`).
   * Botones de acción directa:
     * 📥 **Descargar PDF:** Enlace con atributo `download` para la obtención directa del KuDE PDF binario.
     * 💾 **Descargar XML:** Enlace con atributo `download` para la descarga directa del XML firmado digitalmente (XML-DSig).
     * 🔄 **Actualizar SIFEN (AJAX):** Botón dinámico que invoca la API asíncrona de consulta, mostrando spinner animado y actualizando el badge, protocolo y mensaje de trazabilidad en el DOM sin recargar la página.
     * 👁️ **Ver KuDE Completo:** Acceso a la vista formal completa de la factura e-Kuatia.

2. **Endpoints Modulares en `apps/invoicing/` (`views.py` y `urls.py`):**
   * `FacturaElectronicaDetailView`: Vista web para visualización formal de la factura e-Kuatia y KuDE.
   * `FacturaElectronicaPdfDownloadView`: Endpoint de streaming para descarga directa del KuDE en formato PDF binario (`application/pdf`) con cabecera `Content-Disposition: attachment`.
   * `FacturaElectronicaXmlDownloadView`: Endpoint de streaming para descarga directa del XML firmado digitalmente (`application/xml; charset=utf-8`) con cabecera `Content-Disposition: attachment`.
   * `FacturaElectronicaSifenSyncAjaxView`: Endpoint AJAX (`POST`/`GET`) que consulta al proveedor configurado (`InvoiceProvider`), actualiza el estado en base de datos mediante `InvoiceService.update_estado()`, y retorna un JSON con el nuevo estado, metadatos y fragmento HTML del badge (`badge_html`).
   * `FacturaConsultaApiView`: Endpoint REST JSON público de verificación tributaria por CDC de 44 dígitos, número de factura o ID de transacción.

3. **Endpoints de Integración en `transactions/` (`kude_views.py` y `urls.py`):**
   * `TransactionSifenSyncAjaxView` (`/transactions/<int:pk>/kude/sync-sifen/`): Endpoint AJAX a nivel de transacción para sincronización inmediata con SIFEN.
   * Adaptación de `TransactionKudePdfDownloadView` y `TransactionKudeXmlDownloadView` para priorizar el modelo canónico `FacturaElectronica` (`apps.invoicing`).
   * Enriquecimiento de `TransactionDetailView.get_context_data` para inyectar automáticamente la instancia de factura correspondiente.

4. **Seguridad y Prevención IDOR (`InvoicingAccessMixin` / `BaseKudeAccessMixin`):**
   * Control de acceso estricto: administradores, operadores, cajeros titulares y cliente propietario de la transacción mediante verificación de asignación activa (`CustomerUserAssignment`).
   * Bloqueo con HTTP 403 / `PermissionDenied` ante intentos de acceso no autorizado.

---

## 📐 Diagrama de Flujo e Integración AJAX

```
  ┌─────────────────────────┐
  │   Cliente en Navegador  │
  │ (transaction_detail.html│
  └────────────┬────────────┘
               │ 1. Click "Actualizar SIFEN"
               ▼
  ┌─────────────────────────┐
  │   syncSifenStatus(txId) │  (JavaScript fetch API con X-CSRFToken)
  └────────────┬────────────┘
               │ 2. POST /transactions/<pk>/kude/sync-sifen/
               ▼
  ┌─────────────────────────────────────────────────────────┐
  │               TransactionSifenSyncAjaxView              │
  │─────────────────────────────────────────────────────────│
  │ • Valida permisos (InvoicingAccessMixin)                │
  │ • Obtiene FacturaElectronica                            │
  │ • Invoca get_invoice_provider().get_estado_sifen(cdc)   │
  │ • Actualiza estado: InvoiceService.update_estado(...)   │
  │ • Construye badge_html coloreado y JSON estructurado    │
  └────────────┬────────────────────────────────────────────┘
               │ 3. Retorna JSON { success: true, estado_sifen, badge_html, ... }
               ▼
  ┌─────────────────────────┐
  │   Actualización DOM     │
  │ - Badge coloreado       │
  │ - Texto de Protocolo    │
  │ - Mensaje temporal OK   │
  └─────────────────────────┘
```

---

## 📋 Detalle de Archivos Creados e Intervenidos

| Archivo | Rol / Contenido |
| :--- | :--- |
| `apps/invoicing/views.py` | Implementación de las 5 vistas y endpoints de facturación (`FacturaElectronicaDetailView`, `FacturaElectronicaPdfDownloadView`, `FacturaElectronicaXmlDownloadView`, `FacturaElectronicaSifenSyncAjaxView`, `FacturaConsultaApiView`). |
| `apps/invoicing/urls.py` | Definición de rutas del módulo `invoicing` (`facturas/<pk>/`, `pdf/`, `xml/`, `sync-sifen/`, `api/consulta/`). |
| `config/urls.py` | Registro de `apps.invoicing.urls` bajo el prefijo `invoicing/`. |
| `transactions/kude_views.py` | Incorporación de `TransactionSifenSyncAjaxView` y soporte de modelo canónico `FacturaElectronica` en vistas de descarga. |
| `transactions/urls.py` | Registro de ruta `transactions:<pk>:kude_sync_sifen`. |
| `transactions/views.py` | Enriquecimiento de `TransactionDetailView.get_context_data` con la factura electrónica asociada. |
| `templates/transactions/transaction_detail.html` | Inclusión de la Card Integrada de KuDE, botones de descarga directa, botón AJAX de actualización de estado y scripts de interacción. |
| `templates/transactions/kude.html` | Incorporación de botón y función AJAX de actualización SIFEN en la barra de herramientas del KuDE. |
| `apps/invoicing/__init__.py` | Exportación de vistas en el paquete `apps.invoicing`. |
| `apps/invoicing/providers/mock.py` | Almacén en memoria compartido entre instancias de mock para coherencia en pruebas asíncronas de sincronización. |
| `apps/invoicing/tests.py` | 11 nuevas pruebas unitarias e integración en `InvoicingViewsTests` (totalizando 61 pruebas en la app). |
| `docs/sphinx/source/invoicing.rst` | Documentación técnica Sphinx actualizada con `apps.invoicing.views` y `apps.invoicing.urls`. |
| `docs/documentacion/SCRUM-119.md` | Reporte técnico y memoria de ingeniería del ticket. |
| `docs/documentacion/Jira workflow/TAREAS.md` | Actualización de estado del ticket a `Finalizado`. |
| `docs/documentacion/Proyecto/RESOLUCION_TAREAS_IA.md` | Registro de resolución en la bitácora consolidada (#27). |
| `docs/chat_ia.md` | Bitácora de diálogo con el asistente para trazabilidad de equipo. |

---

## 🧪 Pruebas Unitarias y Cobertura

Se incorporó la clase de prueba `InvoicingViewsTests` en `apps/invoicing/tests.py` con **11 pruebas automatizadas**:

1. `test_factura_detail_view_authenticated_owner`: Visualización HTML del KuDE con usuario titular autenticado (200 OK).
2. `test_factura_detail_view_unauthenticated_forbidden`: Bloqueo con HTTP 403 para usuarios anónimos.
3. `test_factura_detail_view_other_user_forbidden`: Verificación de aislamiento de datos y prevención IDOR (403 para usuarios no autorizados).
4. `test_factura_pdf_download_view`: Descarga de archivo binario PDF (`application/pdf`, encabezado de archivo y firma `%PDF-1.4`).
5. `test_factura_xml_download_view`: Descarga de archivo XML firmado (`application/xml`, estructura `<rDE` y presencia del CDC).
6. `test_factura_sifen_sync_ajax_success`: Sincronización exitosa vía POST AJAX (retorno de JSON con `success: True`, estado y `badge_html`).
7. `test_factura_sifen_sync_ajax_updates_cancelled_state`: Verificación de actualización en base de datos al estado `CANCELADO` tras anulación en el proveedor.
8. `test_factura_consulta_api_by_cdc`: Consulta pública REST API mediante CDC de 44 dígitos (200 OK con metadatos y URLs de descarga).
9. `test_factura_consulta_api_not_found`: Respuesta controlada HTTP 404 ante CDC inexistente o no encontrado.
10. `test_transaction_kude_sync_sifen_endpoint`: Sincronización SIFEN exitosa a través del endpoint transaccional `/transactions/<pk>/kude/sync-sifen/`.
11. `test_transaction_detail_renders_kude_integrated_card`: Verificación de que `transaction_detail.html` renderice la card integrada de KuDE con todos sus controles.

### Resultados Globales de la Suite:
* **Pruebas en `apps.invoicing`:** 61/61 pruebas aprobadas al 100% de éxito (OK).
* **Pruebas del proyecto global:** 642/642 pruebas aprobadas al 100% de éxito (0 fallos, 0 errores, sin regresiones).

