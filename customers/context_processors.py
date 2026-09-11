"""
Procesador de contexto para exponer el cliente activo y sus alternativas.
"""

from typing import Any, Dict
from django.http import HttpRequest
from .models import CustomerUserAssignment


def active_customer(request: HttpRequest) -> Dict[str, Any]:
    """
    Inyecta en el contexto de las plantillas el cliente activo en sesión
    y la lista de clientes disponibles para el usuario autenticado.

    :return: ``active_customer`` (Cliente o None) y ``available_customers`` (list[Cliente]).
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'active_customer': None, 'available_customers': []}

    assignments = CustomerUserAssignment.objects.filter(
        user=request.user,
        is_active=True,
        customer__is_active=True,
    ).select_related('customer').order_by('-is_primary_representative', 'customer__nombre')

    available_customers = [a.customer for a in assignments]
    active_id = request.session.get('active_customer_id')
    active = next((c for c in available_customers if c.id == active_id), None)

    return {'active_customer': active, 'available_customers': available_customers}