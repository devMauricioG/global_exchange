"""
Middleware para la gestión del cliente activo en la sesión del usuario.
"""

from django.utils.deprecation import MiddlewareMixin
from .models import CustomerUserAssignment


class ActiveCustomerMiddleware(MiddlewareMixin):
    """
    Mantiene válida la clave ``active_customer_id`` en ``request.session``.

    En cada request de un usuario autenticado, verifica que el cliente
    actualmente activo en sesión siga correspondiendo a una asignación
    válida (activa) del usuario. Si no hay un cliente activo válido,
    selecciona automáticamente el representante principal o, en su
    defecto, el primer cliente disponible para ese usuario.
    """

    def process_request(self, request):
        if not request.user.is_authenticated:
            return

        assignments = CustomerUserAssignment.objects.filter(
            user=request.user,
            is_active=True,
            customer__is_active=True,
        ).select_related('customer')

        valid_ids = set(assignments.values_list('customer_id', flat=True))
        active_id = request.session.get('active_customer_id')

        if active_id not in valid_ids:
            default = assignments.filter(is_primary_representative=True).first() or assignments.first()
            request.session['active_customer_id'] = default.customer_id if default else None