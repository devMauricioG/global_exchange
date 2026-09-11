"""
Módulo de enrutamiento y definición de URLs para la aplicación de clientes.

Define las rutas para la navegación web basada en clases (CBVs) y los endpoints
de la API REST (JSON).

Rutas Web:
    * ``/customers/`` (nombre: ``cliente-list``): Listado y filtros de clientes.
    * ``/customers/nuevo/`` (nombre: ``cliente-create``): Formulario de creación.
    * ``/customers/<pk>/`` (nombre: ``cliente-detail``): Detalle del cliente.
    * ``/customers/<pk>/editar/`` (nombre: ``cliente-update``): Formulario de edición.
    * ``/customers/<pk>/eliminar/`` (nombre: ``cliente-delete``): Confirmación y borrado.
    * ``/customers/cambiar-activo/<int:customer_id>/`` (nombre: ``switch-active-customer``): Cambia el cliente activo en sesión.

Rutas API REST:
    * ``/customers/api/`` (nombre: ``api-cliente-list-create``): Listar y crear vía JSON.
    * ``/customers/api/<pk>/`` (nombre: ``api-cliente-detail``): Consulta, edición y borrado por PK.
    * ``/customers/api/documento/<documento_ruc>/`` (nombre: ``api-cliente-by-doc``): Consulta por RUC.

"""

from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # Vistas Web (CBVs)
    path('', views.ClienteListView.as_view(), name='cliente-list'),
    path('nuevo/', views.ClienteCreateView.as_view(), name='cliente-create'),
    path('<int:pk>/', views.ClienteDetailView.as_view(), name='cliente-detail'),
    path('<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente-update'),
    path('<int:pk>/eliminar/', views.ClienteDeleteView.as_view(), name='cliente-delete'),

     # Gestión de Cliente Activo en Sesión
    path('cambiar-activo/<int:customer_id>/', views.SwitchActiveCustomerView.as_view(), name='switch-active-customer'),

    # Endpoints API REST (JSON)
    path('api/', views.ClienteListCreateAPIView.as_view(), name='api-cliente-list-create'),
    path('api/<int:pk>/', views.ClienteDetailAPIView.as_view(), name='api-cliente-detail'),
    path('api/documento/<str:documento_ruc>/', views.ClienteDetailAPIView.as_view(), name='api-cliente-by-doc'),
]
