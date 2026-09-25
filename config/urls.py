"""
Configuración global de URLs para el proyecto Global Exchange.

Define el enrutamiento raíz conectando los módulos de autenticación, clientes,
medios de pago, tasas, transacciones y la documentación técnica de Sphinx.
"""
from authentication.views import home_view
from django.contrib import admin
from django.urls import include, path, re_path
from config.views import serve_sphinx_docs

urlpatterns = [
    path('', home_view, name='home'),
    path('admin/', admin.site.urls),
    path('oidc/', include('mozilla_django_oidc.urls')),
    path('auth/', include('authentication.urls')),
    path('customers/', include('customers.urls')),
    path('payments/', include('payments.urls')),
    path('rates/', include('rates.urls')),
    path('transactions/', include('transactions.urls')),
    re_path(r'^docs/(?P<path>.*)$', serve_sphinx_docs, name='sphinx_docs'),
]


