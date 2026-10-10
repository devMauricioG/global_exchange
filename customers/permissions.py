"""
Módulo de permisos RBAC y aislamiento de cliente activo para la aplicación de clientes (customers).

Re-exporta las utilidades, decoradores y mixins definidos en :mod:`authentication.permissions`
para su uso directo en la gestión de clientes.
"""

from authentication.permissions import (
    ActiveCustomerRequiredMixin,
    CustomerOwnershipRequiredMixin,
    RoleRequiredMixin,
    active_customer_required,
    customer_ownership_required,
    get_active_customer_from_request,
    has_any_role,
    has_role,
    normalize_roles,
    role_required,
    verify_customer_ownership,
)

__all__ = [
    "normalize_roles",
    "has_role",
    "has_any_role",
    "get_active_customer_from_request",
    "verify_customer_ownership",
    "role_required",
    "active_customer_required",
    "customer_ownership_required",
    "RoleRequiredMixin",
    "ActiveCustomerRequiredMixin",
    "CustomerOwnershipRequiredMixin",
]
