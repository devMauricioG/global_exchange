# SCRUM-35: Configuración de ruta y vista en Django para servir la documentación Sphinx autogenerada.

## Descripción de la tarea
Implementar una vista en Django y configurar las rutas en config/urls.py para servir los archivos estáticos HTML generados por Sphinx en docs/sphinx/build/html/, permitiendo su visualización protegida o integrada en el portal web.

## Cambios realizados
1. **Creación de vista para servir documentación estática**:
   Se creó el archivo `config/views.py` e implementó la función `serve_sphinx_docs`, la cual utiliza `django.views.static.serve` para servir los archivos HTML de Sphinx (ubicados en `docs/sphinx/build/html`).
2. **Protección de la ruta**:
   La vista fue protegida mediante el decorador `@login_required`, asegurando que solo usuarios autenticados puedan acceder a la documentación.
3. **Manejo de directorio raíz (Index)**:
   Se agregó lógica a la vista para que, si el path solicitado está vacío o apunta a un directorio (como la raíz de la documentación), automáticamente sirva el archivo `index.html`.
4. **Configuración de rutas (URLs)**:
   Se modificó el archivo `config/urls.py` para incluir una ruta mediante expresiones regulares `re_path(r'^docs/(?P<path>.*)$')` que redirige el tráfico hacia la nueva vista.

## Archivos Modificados / Creados
* `config/views.py` (Creado)
* `config/urls.py` (Modificado)
