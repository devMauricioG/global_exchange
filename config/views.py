import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.static import serve
from django.http import Http404
from django.core.exceptions import SuspiciousFileOperation
from django.utils._os import safe_join

@login_required
def serve_sphinx_docs(request, path):
    """Sirve de forma segura la documentación HTML generada por Sphinx."""
    document_root = os.path.join(settings.BASE_DIR, 'docs', 'sphinx', 'build', 'html')
    path = path.lstrip('/')
    if path == '':
        path = 'index.html'

    try:
        full_path = safe_join(document_root, path)
    except SuspiciousFileOperation as exc:
        raise Http404('Documento no encontrado.') from exc

    if os.path.isdir(full_path):
        path = os.path.join(path, 'index.html')

    return serve(request, path, document_root=document_root)
