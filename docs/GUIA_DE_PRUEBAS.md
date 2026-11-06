# Guía de Pruebas por Módulos y Roles — Global Exchange

Para consultar la guía actualizada con la preparación de Keycloak, los datos de
la seed, el flujo de cliente, cajero y kiosco, acceda al documento oficial:

👉 **[Manual de pruebas funcionales](documentacion/Proyecto/MANUAL_DE_USUARIO.md)**

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
