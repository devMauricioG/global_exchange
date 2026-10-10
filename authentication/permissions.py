"""
Módulo de permisos RBAC, decoradores y Mixins para el control de acceso en Django.

Provee mecanismos declarativos de control de acceso basado en roles (RBAC)
y verificación de pertenencia / aislamiento multi-inquilino de cliente activo:
  - Funciones auxiliares: :func:`has_role`, :func:`has_any_role`, :func:`verify_customer_ownership`, :func:`get_active_customer_from_request`.
  - Decoradores para vistas basadas en función (FBVs): :func:`role_required`, :func:`active_customer_required`, :func:`customer_ownership_required`.
  - Mixins para vistas basadas en clases (CBVs): :class:`RoleRequiredMixin`, :class:`ActiveCustomerRequiredMixin`, :class:`CustomerOwnershipRequiredMixin`.
"""

from functools import wraps
import logging
from typing import Any, Callable, Iterable, List, Optional, Set, Union

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)
User = get_user_model()


def normalize_roles(roles_input: Union[str, Iterable[str]]) -> Set[str]:
    """
    Normaliza el argumento de roles a un conjunto de cadenas en minúsculas.

    Soporta:
      - Cadena única o separada por comas: ``"admin,operator"`` -> ``{"admin", "operator"}``.
      - Colección (lista/tupla/set): ``["admin", "operator"]`` -> ``{"admin", "operator"}``.

    :param roles_input: Roles especificadas en formato texto o colección.
    :type roles_input: str or Iterable[str]
    :return: Conjunto de códigos de roles normalizados.
    :rtype: set[str]
    """
    if not roles_input:
        return set()
    if isinstance(roles_input, str):
        return {r.strip().lower() for r in roles_input.split(",") if r.strip()}
    return {str(r).strip().lower() for r in roles_input if str(r).strip()}


def has_role(user: Any, allowed_roles: Union[str, Iterable[str]]) -> bool:
    """
    Verifica si el usuario autenticado cuenta con al menos uno de los roles autorizados.

    Jerarquía y equivalencias de roles:
      - ``is_superuser`` otorga implícitamente los roles ``admin`` y ``operator``.
      - ``is_staff`` otorga implícitamente el rol ``operator``.
      - Los roles de grupo Django asignados (``admin``, ``operator``, ``user``) se evalúan de forma directa.

    :param user: Instancia del usuario en Django (o AnonymousUser).
    :type user: django.contrib.auth.models.AbstractBaseUser
    :param allowed_roles: Cadena o colección con los roles requeridos.
    :type allowed_roles: str or Iterable[str]
    :return: Verdadero si el usuario cuenta con algún rol permitido.
    :rtype: bool
    """
    if not user or not user.is_authenticated:
        return False

    required_roles = normalize_roles(allowed_roles)
    if not required_roles:
        return True

    user_roles: Set[str] = set()

    # Grupos asignados en Django
    for group in user.groups.all():
        user_roles.add(group.name.lower())

    # Atributo realm_roles si se inyectó desde OIDC
    if hasattr(user, "realm_roles") and isinstance(user.realm_roles, (list, tuple, set)):
        for r in user.realm_roles:
            user_roles.add(str(r).lower())

    # Privilegios elevados y herencia de roles (Admin > Operator > User)
    if getattr(user, "is_superuser", False):
        user_roles.add("admin")
        user_roles.add("operator")
        user_roles.add("user")

    if getattr(user, "is_staff", False):
        user_roles.add("operator")
        user_roles.add("user")

    # Si el usuario es admin, tiene implícitamente operator y user
    if "admin" in user_roles:
        user_roles.add("operator")
        user_roles.add("user")

    # Si el usuario es operator, tiene implícitamente user
    if "operator" in user_roles:
        user_roles.add("user")

    # Si no tiene ningún rol explícito pero está autenticado, asigna rol 'user'
    if not user_roles:
        user_roles.add("user")

    return bool(required_roles.intersection(user_roles))


def has_any_role(user: Any, *roles: str) -> bool:
    """
    Auxiliar para comprobar si el usuario tiene cualquiera de los roles indicados.
    """
    return has_role(user, roles)


def get_active_customer_from_request(request: HttpRequest) -> Optional[Any]:
    """
    Obtiene el cliente activo de la sesión o solicitud HTTP.
    Intenta resolver primero mediante middleware o mediante el servicio de rates.
    """
    if hasattr(request, "active_customer") and request.active_customer:
        return request.active_customer

    try:
        from rates.services import get_active_customer
        return get_active_customer(request)
    except Exception as exc:
        logger.debug("Error al resolver cliente activo en permisos: %s", exc)

    if hasattr(request, "session") and request.session:
        session_id = request.session.get("active_customer_id")
        if session_id:
            from customers.models import Cliente
            return Cliente.objects.filter(id=session_id, is_active=True).first()

    return None


def verify_customer_ownership(user: Any, customer_or_id: Union[Any, int, str]) -> bool:
    """
    Verifica si un usuario tiene permisos de acceso sobre una ficha de cliente específica.

    Reglas de aislamiento:
      - Administradores y Operadores pueden acceder a cualquier cliente activo.
      - Usuarios estándar ('user') solo pueden acceder a los clientes donde tengan una asignación
        activa en :class:`~customers.models.CustomerUserAssignment`.

    :param user: Usuario autenticado.
    :param customer_or_id: Instancia de Cliente o su ID numérico/Keycloak ID.
    :return: Verdadero si la operación está autorizada.
    :rtype: bool
    """
    if not user or not user.is_authenticated:
        return False

    if has_role(user, "admin,operator"):
        return True

    if not customer_or_id:
        return False

    from customers.models import Cliente, CustomerUserAssignment

    customer_id = customer_or_id.id if isinstance(customer_or_id, Cliente) else customer_or_id

    # Comprobación de asignación activa
    if isinstance(customer_id, int) or (isinstance(customer_id, str) and customer_id.isdigit()):
        return CustomerUserAssignment.objects.filter(
            user=user,
            customer_id=int(customer_id),
            is_active=True,
            customer__is_active=True,
        ).exists()

    if isinstance(customer_id, str):
        return CustomerUserAssignment.objects.filter(
            user=user,
            customer__keycloak_id=customer_id,
            is_active=True,
            customer__is_active=True,
        ).exists()

    return False


# ==============================================================================
# DECORADORES PARA VISTAS BASADAS EN FUNCIÓN (FBVs)
# ==============================================================================

def role_required(
    allowed_roles: Union[str, Iterable[str]],
    redirect_url: Optional[str] = None,
    raise_exception: bool = False,
    message: str = "No posee los permisos requeridos para acceder a este recurso.",
) -> Callable:
    """
    Decorador para proteger Vistas Basadas en Función (FBVs) por roles RBAC.

    :param allowed_roles: Roles permitidos (ej. "admin,operator" o ["admin"]).
    :param redirect_url: URL o nombre de ruta a redirigir si no está autorizado (opcional).
    :param raise_exception: Si es True, lanza PermissionDenied (403) en lugar de redirigir.
    :param message: Mensaje de alerta a mostrar al usuario si es redirigido.
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not request.user.is_authenticated:
                if raise_exception:
                    raise PermissionDenied("Debe estar autenticado para acceder.")
                return redirect(getattr(settings, "LOGIN_URL", "/oidc/authenticate/"))

            if not has_role(request.user, allowed_roles):
                if raise_exception:
                    raise PermissionDenied(message)
                if message:
                    messages.warning(request, message)
                target_url = redirect_url or getattr(settings, "ROLE_REQUIRED_REDIRECT_URL", "home")
                try:
                    return redirect(target_url)
                except Exception:
                    return redirect("home")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def active_customer_required(
    redirect_url: Optional[str] = None,
    raise_exception: bool = False,
    message: str = "Debe contar con un cliente activo en sesión para realizar esta operación.",
) -> Callable:
    """
    Decorador para asegurar que la solicitud cuente con un cliente activo asignado.
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not request.user.is_authenticated:
                if raise_exception:
                    raise PermissionDenied("Debe estar autenticado.")
                return redirect(getattr(settings, "LOGIN_URL", "/oidc/authenticate/"))

            customer = get_active_customer_from_request(request)
            if not customer:
                if raise_exception:
                    raise PermissionDenied(message)
                if message:
                    messages.warning(request, message)
                target = redirect_url or "home"
                return redirect(target)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def customer_ownership_required(
    customer_id_param: str = "pk",
    redirect_url: Optional[str] = None,
    raise_exception: bool = False,
    message: str = "No tiene autorización para acceder a los datos de este cliente.",
) -> Callable:
    """
    Decorador para garantizar el aislamiento multi-inquilino de clientes.
    Verifica que el usuario tenga representación activa sobre el cliente especificado en los parámetros URL.
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not request.user.is_authenticated:
                if raise_exception:
                    raise PermissionDenied("Debe estar autenticado.")
                return redirect(getattr(settings, "LOGIN_URL", "/oidc/authenticate/"))

            target_customer_id = kwargs.get(customer_id_param) or request.GET.get(customer_id_param) or request.POST.get(customer_id_param)

            if not verify_customer_ownership(request.user, target_customer_id):
                if raise_exception:
                    raise PermissionDenied(message)
                if message:
                    messages.error(request, message)
                target = redirect_url or "home"
                return redirect(target)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# ==============================================================================
# MIXINS PARA VISTAS BASADAS EN CLASES (CBVs)
# ==============================================================================

class RoleRequiredMixin(AccessMixin):
    """
    Mixin para Vistas Basadas en Clases (CBVs) que exige roles específicos.

    Atributos configurables:
      - ``allowed_roles`` (*str | list[str]*): Roles autorizados (ej. ``['admin', 'operator']``).
      - ``redirect_url`` (*str*): Nombre de ruta a redirigir en caso de denegación (opcional).
      - ``raise_exception`` (*bool*): Lanzar HTTP 403 si es True.
      - ``permission_denied_message`` (*str*): Mensaje explicativo.
    """
    allowed_roles: Union[str, Iterable[str]] = []
    redirect_url: Optional[str] = None
    raise_exception: bool = False
    permission_denied_message: str = "No posee los permisos requeridos para acceder a este recurso."

    def get_allowed_roles(self) -> Union[str, Iterable[str]]:
        """Devuelve la lista o conjunto de roles requeridos."""
        return self.allowed_roles

    def has_permission(self) -> bool:
        """Comprueba si el usuario autenticado tiene alguno de los roles permitidos."""
        user = self.request.user
        return user.is_authenticated and has_role(user, self.get_allowed_roles())

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not self.has_permission():
            if self.raise_exception:
                raise PermissionDenied(self.permission_denied_message)
            if self.permission_denied_message:
                messages.warning(request, self.permission_denied_message)
            target = self.redirect_url or getattr(settings, "ROLE_REQUIRED_REDIRECT_URL", "home")
            try:
                return redirect(target)
            except Exception:
                return redirect("home")

        return super().dispatch(request, *args, **kwargs)


class ActiveCustomerRequiredMixin(AccessMixin):
    """
    Mixin para CBVs que exige la presencia de un cliente activo en sesión.
    """
    redirect_url: Optional[str] = None
    raise_exception: bool = False
    permission_denied_message: str = "Debe seleccionar un cliente activo para continuar."

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        customer = get_active_customer_from_request(request)
        if not customer:
            if self.raise_exception:
                raise PermissionDenied(self.permission_denied_message)
            if self.permission_denied_message:
                messages.warning(request, self.permission_denied_message)
            target = self.redirect_url or "home"
            return redirect(target)

        return super().dispatch(request, *args, **kwargs)


class CustomerOwnershipRequiredMixin(AccessMixin):
    """
    Mixin para CBVs que valida la pertenencia y aislamiento del cliente accedido.
    """
    customer_id_param: str = "pk"
    redirect_url: Optional[str] = None
    raise_exception: bool = False
    permission_denied_message: str = "No tiene autorización para acceder a este cliente."

    def get_target_customer_id(self) -> Optional[Any]:
        """Obtiene el ID del cliente de los kwargs de la vista o del objeto de la vista."""
        if hasattr(self, "kwargs") and self.customer_id_param in self.kwargs:
            return self.kwargs[self.customer_id_param]
        if hasattr(self, "get_object"):
            try:
                obj = self.get_object()
                return getattr(obj, "customer_id", getattr(obj, "id", None))
            except Exception:
                pass
        return None

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        target_customer_id = self.get_target_customer_id()
        if not verify_customer_ownership(request.user, target_customer_id):
            if self.raise_exception:
                raise PermissionDenied(self.permission_denied_message)
            if self.permission_denied_message:
                messages.error(request, self.permission_denied_message)
            target = self.redirect_url or "home"
            return redirect(target)

        return super().dispatch(request, *args, **kwargs)
