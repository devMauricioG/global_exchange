# Guía de Pruebas por Módulos y Roles — Global Exchange

Para consultar la guía detallada con los pasos de prueba por módulos y roles del sistema, acceda al documento oficial:

👉 **[GUÍA DE PRUEBAS POR ROLES Y MÓDULOS](file:///c:/Users/devma/OneDrive/Documentos/Faq/7mo/IS2/django_proyects/global_exchange/docs/documentacion/Proyecto/GUIA_DE_PRUEBAS_ROLES_Y_MODULOS.md)**

---

### Resumen Rápido de Credenciales y Seeding

Ejecutar en la raíz del proyecto:
```bash
python manage.py seed_data
```

**Contraseña unificada:** `Password123!`

| Usuario | Rol | Segmento | Propósito |
|---|---|---|---|
| **`admin`** | Administrador | Staff | Parametrización de monedas, tasas, comisiones, límites y bancos. |
| **`operador`** | Operador de Caja | Staff | Consulta de transacciones y emisión de comprobantes. |
| **`cliente_minorista`** | Cliente | Minorista (MIN) | Operaciones cambiarias estándar y límites base. |
| **`cliente_vip`** | Cliente | VIP (VIP) | Cotizaciones con spread bonificado y límites extendidos. |
| **`cliente_corporativo`** | Cliente | Corporativo (COR) | Operaciones de alto volumen y multirrepresentación. |
| **`cliente_mayorista`** | Cliente | Mayorista (MAY) | Operaciones mayoristas comerciales. |

Consulte el documento completo para los flujos paso a paso de cada módulo.
