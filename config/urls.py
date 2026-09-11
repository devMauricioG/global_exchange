"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
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
    re_path(r'^docs/(?P<path>.*)$', serve_sphinx_docs, name='sphinx_docs'),
]


