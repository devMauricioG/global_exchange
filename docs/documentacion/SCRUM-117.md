# SCRUM-117: Arquitectura Desacoplada para Facturación Electrónica (InvoiceProvider y MockInvoiceProvider)

## 📌 Metadatos de la Tarea

* **Ticket:** SCRUM-117
* **Épica:** SCRUM-7 (Módulo de Caja, Terminal de Autoservicio, Simulación de Efectivo y Facturación Electrónica Segura)
* **Historia de Usuario:** SCRUM-110 (Integración de Facturación Electrónica SIFEN con Control Estricto de Cuota)
* **Sprint:** SCRUM Sprint 5
* **Responsable:** Mauricio González
* **Estado:** Finalizado
* **Bloquea:** SCRUM-118, SCRUM-119, SCRUM-125

---

## 🎯 Objetivo y Alcance

Diseñar e implementar en la nueva aplicación modular `apps/invoicing/` el patrón **Strategy / Adapter** para la integración con el Sistema Integrado de Facturación Electrónica Nacional (**SIFEN** / e-Kuatia) y Proveedores de Autorización y Certificación (**PAC**), fundamentado rigurosamente en la especificación técnica oficial **"API de Factura Segura para ESI (External Systems Interoperation) v01"**.

La arquitectura garantiza:

1. **Desacoplamiento Absoluto:** La lógica de negocio transaccional interactúa exclusivamente contra la interfaz base `InvoiceProvider`.
2. **Preservación Inviolable de Cuota:** La implementación `MockInvoiceProvider` atiende el 100% de los entornos de desarrollo local y suites de pruebas automatizadas (0 peticiones a la API comercial de Factura Segura).
3. **Cálculo Matemático SIFEN Canónico:** Implementación exacta de las fórmulas de bases imponibles gravadas, exentas, exoneradas, liquidación del IVA (5% y 10%) y clave de acceso (CDC de 44 dígitos con Módulo 11 oficial de la DNIT).
4. **Representación Gráfica y XML:** Generación local de KuDE en PDF binario 1.4 y XML firmado con estructura canónica e-Kuatia (`rDE`).
5. **Cliente Real y Blindaje:** Adaptador `FacturaSeguraProvider` con guardián `FACTURA_SEGURA_LIVE_ENABLED=False` por defecto y soporte completo del protocolo envelope ESI (`calcular_de`, `generar_de`, `get_estado_sifen`, `sol_cancelacion`, `sol_inutilizacion`, `dwn_kude`, `dwn_xml`).

---

## 📐 Diseño Arquitectónico

### Patrón Strategy / Adapter

```
              ┌─────────────────────────────┐
              │       InvoiceProvider       │  (Interface / Abstract Base Class)
              │─────────────────────────────│
              │ + calcular_de(de_data)      │
              │ + generar_de(de_data)       │
              │ + get_estado_sifen(cdc)     │
              │ + sol_cancelacion(cdc)      │
              │ + sol_inutilizacion(...)    │
              │ + dwn_kude(cdc)             │
              │ + dwn_xml(cdc)              │
              │ + emitir_factura(tx_or_data)│
              └──────────────▲──────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
┌─────────────────────────────┐ ┌─────────────────────────────┐
│     MockInvoiceProvider     │ │    FacturaSeguraProvider    │
│─────────────────────────────│ │─────────────────────────────│
│ • CDCs 44 dígitos (Módulo11)│ │ • Conexión HTTP /misife00/v1│
│ • SIFEN Aprobado / Cancelado│ │ • Token /login?include_auth │
│ • KuDE PDF 1.4 binario local│ │ • Guardián LIVE_ENABLED=False│
│ • XML firmado e-Kuatia rDE  │ │ • Protocolo ESI Envelope    │
│ • 0 consumo de cuota real   │ │ • QuotaExhaustedError check │
└─────────────────────────────┘ └─────────────────────────────┘
              ▲                             ▲
              └──────────────┬──────────────┘
                             │
              ┌──────────────┴──────────────┐
              │    get_invoice_provider()   │  (Factory Selector)
              └─────────────────────────────┘
```

---

## 📋 Detalle de Archivos Creados e Intervenidos

| Archivo | Rol / Contenido |
| :--- | :--- |
| `apps/invoicing/apps.py` | Configuración de la aplicación `apps.invoicing` (`InvoicingConfig`). |
| `apps/invoicing/exceptions.py` | Jerarquía formal de excepciones (`InvoiceProviderError`, `QuotaExhaustedError`, `LiveModeDisabledError`, `InvoiceValidationError`, `InvoiceNotFoundError`). |
| `apps/invoicing/types.py` | Data Transfer Objects (`InvoiceResponse`, `StatusResponse`, `CalculationResult`, `EstadoSifenEnum`). |
| `apps/invoicing/calculators.py` | Algoritmo Módulo 11 oficial, generador de CDC de 44 dígitos y motor matemático `calculate_de` (IVA 5%, 10%, gravado parcial, exento y exonerado). |
| `apps/invoicing/providers/base.py` | Contrato abstracto `InvoiceProvider` (patrón Strategy). |
| `apps/invoicing/providers/mock.py` | Simulador `MockInvoiceProvider` con generador autónomo de PDF KuDE y XML firmado. |
| `apps/invoicing/providers/facturasegura.py` | Cliente real y adaptador `FacturaSeguraProvider` para webservice REST ESI v01. |
| `apps/invoicing/providers/factory.py` | Fábrica `get_invoice_provider()` con soporte para inyección de mocks y selector por configuración. |
| `apps/invoicing/providers/__init__.py` | Exportación limpia del subpaquete de proveedores. |
| `apps/invoicing/__init__.py` | Exportaciones principales y registro en el espacio de nombres. |
| `apps/invoicing/tests.py` | Suite de 25 pruebas unitarias y de integración (cobertura del 93%). |
| `apps/__init__.py` | Resolución dinámica de `apps.invoicing` y `invoicing`. |
| `config/settings/base.py` | Inclusión de `apps.invoicing` en `INSTALLED_APPS` y variables de configuración `FACTURA_SEGURA_*`. |
| `config/settings/test.py` | Blindaje explícito `FACTURA_SEGURA_LIVE_ENABLED = False`. |
| `docs/sphinx/source/invoicing.rst` | Módulo de documentación técnica Sphinx con directivas autodoc. |
| `docs/sphinx/source/modules.rst` | Vinculación del paquete `invoicing` en el árbol de documentación. |

---

## 🧪 Pruebas Unitarias y Validación

Se diseñó e integró una suite completa de **25 pruebas unitarias** en `apps/invoicing/tests.py`:

1. **Pruebas de Interfaz (`InvoiceProviderInterfaceTests`):**
   * Verificación de que `InvoiceProvider` no puede instanciarse directamente.
   * Verificación de obligatoriedad de implementar todos los métodos abstractos.
2. **Pruebas de Cálculos Matemáticos SIFEN (`SifenCalculatorsTests`):**
   * Validación del Módulo 11 con vectores oficiales: RUC `80012345` (DV 0), `80002247` (DV 5), `2595733` (DV 3).
   * Generación y validación estructural de CDC de 44 dígitos.
   * Verificación de los 5 ítems del manual ESI (páginas 17-21):
     * Item 1 (IVA 5%): Base Gravada `285714`, Liquidación IVA `14286`.
     * Item 2 (IVA 10%): Base Gravada `1272727`, Liquidación IVA `127273`.
     * Item 3 (Gravado Parcial 25%): Base Gravada `6098`, IVA `610`, Base Exenta `18293`.
     * Item 4 (Exento): Total `102000`, Base Gravada `0`, IVA `0`.
     * Item 5 (Exonerado): Total `60000`, Base Gravada `0`, IVA `0`.
     * Subtotales exactos: `dSubExe=120293`, `dSubExo=60000`, `dSub5=300000`, `dSub10=1406708`, `dTotOpe=1887001`.
     * Totales de IVA: `dIVA5=14286`, `dIVA10=127883`, `dTotIVA=142169`, `dTBasGraIVA=1564539`.
   * Conversión cambiaria en USD (`dTotalGs`).
3. **Pruebas del Simulador Mock (`MockInvoiceProviderTests`):**
   * Emisión con CDC de 44 dígitos, estado `0260 - Aprobado`, KuDE PDF binario válido y XML firmado.
   * Consulta `get_estado_sifen` y ciclo de vida de cancelación (`sol_cancelacion`).
   * Inutilización de numeración (`sol_inutilizacion`).
   * Descarga independiente de KuDE y XML.
   * Emisión a partir de transacciones cambiarias simuladas.
4. **Pruebas del Adaptador Real (`FacturaSeguraProviderTests`):**
   * Disparo inmediato de `LiveModeDisabledError` ante cualquier intento de llamada externa cuando `FACTURA_SEGURA_LIVE_ENABLED=False`.
   * Simulación HTTP con login (`/login?include_auth_token`), envelope ESI y obtención de CDC.
   * Manejo de errores de webservice (códigos negativos) y detección de cuota agotada (`QuotaExhaustedError`).
   * Operaciones GET `dwn_kude` y `dwn_xml`.
5. **Pruebas de la Fábrica (`InvoiceProviderFactoryTests`):**
   * Retorno de `MockInvoiceProvider` por defecto en entornos de desarrollo y testing.
   * Activación de `FacturaSeguraProvider` al habilitar el flag LIVE.
   * Inyección de dependencias (`set_invoice_provider`, `reset_invoice_provider`).

### Resultados de Ejecución

* **Suite Local Invoicing:** 25/25 tests aprobados (100% OK), cobertura del **93%**.
* **Suite Global del Proyecto:** **561 tests aprobados (100% OK)**, 0 fallos, 0 regresiones.
* **Compilación Sphinx:** Compilación limpia y exitosa (`build succeeded`).
