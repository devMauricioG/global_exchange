import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.static import serve
from django.http import Http404

@login_required
def serve_sphinx_docs(request, path):
    document_root = os.path.join(settings.BASE_DIR, 'docs', 'sphinx', 'build', 'html')
    path = path.lstrip('/')
    if path == '':
        path = 'index.html'
    
    full_path = os.path.join(document_root, path)
    if os.path.isdir(full_path):
        path = os.path.join(path, 'index.html')
        
    return serve(request, path, document_root=document_root)
