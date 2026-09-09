"""
Configuración de rutas URL para la aplicación de medios de pago (payments).

Define tanto las rutas para la interfaz gráfica web (CBVs) como los endpoints de la API REST.
"""

from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Vistas web CBV
    path('', views.PaymentMethodListView.as_view(), name='paymentmethod-list'),
    path('crear/', views.PaymentMethodCreateView.as_view(), name='paymentmethod-create'),
    path('<int:pk>/editar/', views.PaymentMethodUpdateView.as_view(), name='paymentmethod-update'),
    path('<int:pk>/eliminar/', views.PaymentMethodDeleteView.as_view(), name='paymentmethod-delete'),
    path('<int:pk>/predeterminado/', views.PaymentMethodSetDefaultView.as_view(), name='paymentmethod-set-default'),
    path('<int:pk>/toggle-activo/', views.PaymentMethodToggleActiveView.as_view(), name='paymentmethod-toggle-active'),

    # Endpoints API REST (JSON)
    path('api/', views.PaymentMethodListCreateAPIView.as_view(), name='paymentmethod-api-list'),
    path('api/<int:pk>/', views.PaymentMethodDetailAPIView.as_view(), name='paymentmethod-api-detail'),
]
