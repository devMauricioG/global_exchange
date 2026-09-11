# SCRUM-51: Vistas y Lógica de Negocio para el CRUD de Monedas y Tasas de Cambio

## Descripción de la tarea
Implementar los controladores y formularios en Django para listar, crear, editar y cambiar el estado de monedas, así como registrar y actualizar cotizaciones con cálculo automático de spread y validaciones de negocio (venta > compra).

## Cambios realizados

1. **Formularios (rates/forms.py)**:
   - Se crearon los formularios `CurrencyForm` y `ExchangeRateForm` basados en los modelos respectivos, mapeando las validaciones y aplicando las clases CSS estándar del proyecto (`form-input`, `form-select`, etc.).
   - Se crearon formularios de filtrado (`CurrencyFilterForm` y `ExchangeRateFilterForm`) para ser usados en las vistas de lista.

2. **Vistas Basadas en Clases (rates/views.py)**:
   - **Monedas**: Se crearon `CurrencyListView`, `CurrencyCreateView`, `CurrencyUpdateView` y `CurrencyToggleStatusView` (para cambiar la propiedad `is_active`).
   - **Cotizaciones**: Se crearon `ExchangeRateListView`, `ExchangeRateCreateView`, `ExchangeRateUpdateView` y `ExchangeRateToggleStatusView`. Todas protegidas por `LoginRequiredMixin`.
   - En la creación y edición de Tasas de Cambio, se inyecta dinámicamente el `request.user` en el campo `updated_by`.

3. **Rutas (rates/urls.py y config/urls.py)**:
   - Se configuraron los endpoints necesarios dentro de la app `rates` utilizando el namespace `rates`.
   - Se registró la ruta principal `/rates/` en `config/urls.py`.

4. **Plantillas HTML (templates/rates/)**:
   - `currency_list.html`: Vista de catálogo de monedas con tabla, buscador por término y estado, y tarjetas de estadísticas KPI.
   - `currency_form.html`: Formulario para registrar/editar monedas, con visualización de errores y diseño acorde a la estética general.
   - `exchangerate_list.html`: Vista del historial y vigencia de tasas de cambio (visualizando compra, venta, spread).
   - `exchangerate_form.html`: Formulario de captura para cotizaciones de tipos de cambio.

## Archivos Creados/Modificados
- `rates/forms.py` (Creado)
- `rates/views.py` (Modificado/Creado)
- `rates/urls.py` (Creado)
- `config/urls.py` (Modificado)
- `templates/rates/currency_list.html` (Creado)
- `templates/rates/currency_form.html` (Creado)
- `templates/rates/exchangerate_list.html` (Creado)
- `templates/rates/exchangerate_form.html` (Creado)
