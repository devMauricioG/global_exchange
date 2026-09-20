# Tarea SCRUM-70: Filtros personalizados de template (templatetags) y formateadores JS

## Descripción de la tarea
Implementar la librería de tags en Django (`templatetags/currency_filters.py`) con filtros como `format_currency` y `format_number` que apliquen separadores de miles con puntos (.) y decimales con comas (,), contemplando la precisión propia de cada divisa (ej. PYG sin decimales, USD/EUR con 2 decimales) e integrando formateo en tiempo real con JavaScript en las calculadoras.

## Trabajos Realizados

### 1. Creación de Template Tags en Django (Backend)
- Se inicializó el módulo `rates/templatetags/` (con su respectivo `__init__.py`).
- Se creó el archivo `rates/templatetags/currency_filters.py`.
- Se implementaron los filtros:
  - `format_number`: Para formatear cualquier número dado a una cantidad fija de decimales.
  - `format_currency`: Para formatear montos usando la precisión configurada en la base de datos (modelo `Currency`) y añadir su símbolo correspondiente.
  - `format_rate`: Para formatear dinámicamente tasas de compra/venta asegurando que los números muy pequeños conserven su precisión.

### 2. Creación de Utilitario JS (Frontend)
- Se creó el archivo JS `static/js/currency_filters.js`.
- Este módulo expone en `window.GXCurrency` métodos compatibles con la lógica de Django: `formatMoney`, `formatCurrency` y `formatRate`.
- Incorpora formateo automático y un enlazador (`bindInputFormatter`) para formatear montos en tiempo real sobre elementos interactivos (útil para campos de input numéricos en calculadoras).

### 3. Integración y Habilitación de Estáticos
- En `config/settings/base.py`, se descomentó la ruta a la carpeta estática del proyecto:
  ```python
  STATICFILES_DIRS = [
      BASE_DIR / 'static',
  ]
  ```

### 4. Actualización de Plantillas HTML
- **Cotizador (`rates/rate_calculator.html`)**: Se agregaron los nuevos filtros `format_currency` y `format_rate` al resumen de resultados y a los importes bases, netos, comisiones, cargo fijo y tasas efectivas mostradas, y se enlazó el archivo script `currency_filters.js`.
- **Listado de Comisiones (`rates/commission_list.html`)**: Se aplicó el filtro `format_number:2` a la columna de cargo fijo.
- **Dashboard (`rates/exchange_rate_dashboard.html`) y Listado de Tasas (`rates/exchangerate_list.html`)**: Se agregaron las etiquetas de carga `{% load currency_filters %}` y se actualizaron los montos exhibidos con el nuevo estilo paraguayo (miles por puntos, decimales por coma).

## Resultados Esperados
Los usuarios ahora visualizarán las cifras financieras de forma mucho más amigable, estandarizada y libre de ambigüedades. Las tasas sin centavos innecesarios se ven más limpias (ej: 7.500) y las extranjeras retienen sus decimales (ej: 1.250,50).
