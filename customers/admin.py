"""
Módulo de administración de Django para la aplicación de clientes.

Registra y personaliza el modelo :class:`~customers.models.Cliente` y la entidad
de asignación :class:`~customers.models.CustomerUserAssignment` en el panel de control
de administración de Django con columnas informativas, filtros por segmento y estado,
herramientas de búsqueda y edición rápida.
"""

from django.contrib import admin
from .models import Cliente, CustomerUserAssignment


class CustomerUserAssignmentInline(admin.TabularInline):
    """
    Formulario tabular en línea para gestionar representantes asociados a un cliente.
    """
    model = CustomerUserAssignment
    extra = 1
    fields = ('user', 'is_primary_representative', 'is_active', 'assigned_at')
    readonly_fields = ('assigned_at',)
    autocomplete_fields = ('user',)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración de Django para el modelo :class:`~customers.models.Cliente`.

    :cvar list_display: Campos visualizados en la tabla del listado de clientes.
    :cvar list_filter: Filtros laterales para segmentación, estado activo y fecha de creación.
    :cvar search_fields: Campos indexados para la barra de búsqueda del panel admin.
    :cvar ordering: Orden de visualización por defecto (fecha de creación descendente).
    :cvar list_editable: Campos editables directamente desde la tabla de listado.
    """

    list_display = (
        'id',
        'nombre',
        'documento_ruc',
        'correo',
        'telefono',
        'segmentacion',
        'keycloak_id',
        'get_representante_principal',
        'is_active',
        'created_at',
    )
    list_filter = ('segmentacion', 'is_active', 'created_at')
    search_fields = ('nombre', 'documento_ruc', 'correo', 'telefono', 'keycloak_id', 'assignments__user__username')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    list_editable = ('segmentacion', 'is_active')
    inlines = [CustomerUserAssignmentInline]

    @admin.display(description='Representante Principal')
    def get_representante_principal(self, obj: Cliente) -> str:
        """Retorna el nombre de usuario del representante principal activo o un guion."""
        rep = obj.representante_principal
        return str(rep.user) if rep else '-'


@admin.register(CustomerUserAssignment)
class CustomerUserAssignmentAdmin(admin.ModelAdmin):
    """
    Configuración del panel de administración para la entidad :class:`~customers.models.CustomerUserAssignment`.
    """

    list_display = (
        'id',
        'customer',
        'user',
        'is_primary_representative',
        'is_active',
        'assigned_at',
    )
    list_filter = ('is_primary_representative', 'is_active', 'assigned_at')
    search_fields = ('customer__nombre', 'customer__documento_ruc', 'user__username', 'user__email')
    readonly_fields = ('assigned_at',)
    ordering = ('-assigned_at',)
    list_editable = ('is_primary_representative', 'is_active')

