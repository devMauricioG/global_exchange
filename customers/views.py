"""
Módulo de vistas y controladores para la gestión de Clientes (customers).

Este módulo provee dos capas completas de interacción:
1. **Vistas Basadas en Clases (CBVs)**: Renderizado de plantillas HTML para la interfaz web de usuario con soporte de autenticación, paginación, filtros de segmentación y operaciones CRUD.
2. **Endpoints API REST (JSON)**: Vistas basadas en clases para integración programática que permiten listar, consultar por ID o RUC, crear, actualizar (PUT/PATCH) y eliminar clientes retornando respuestas JSON y códigos de estado HTTP estándar.
"""

import json
from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ClienteFilterForm, ClienteForm
from .models import Cliente, CustomerUserAssignment


def _serialize_cliente(cliente: Cliente) -> Dict[str, Any]:
    """
    Serializa una instancia del modelo :class:`~customers.models.Cliente` a un diccionario primitivo.

    :param cliente: Instancia de Cliente a serializar.
    :type cliente: customers.models.Cliente
    :return: Diccionario con la estructura JSON representativa del cliente.
    :rtype: dict
    """
    rep_principal = cliente.representante_principal
    assignments = [
        {
            'id': a.id,
            'user_id': a.user_id,
            'username': getattr(a.user, 'username', str(a.user)),
            'is_primary_representative': a.is_primary_representative,
            'is_active': a.is_active,
            'assigned_at': a.assigned_at.isoformat() if a.assigned_at else None,
        }
        for a in cliente.assignments.all()
    ]
    return {
        'id': cliente.id,
        'nombre': cliente.nombre,
        'documento_ruc': cliente.documento_ruc,
        'correo': cliente.correo,
        'telefono': cliente.telefono,
        'keycloak_id': cliente.keycloak_id,
        'usuario_id': rep_principal.user_id if rep_principal else None,
        'representante_principal_id': rep_principal.user_id if rep_principal else None,
        'assignments': assignments,
        'segmentacion': cliente.segmentacion,
        'segmentacion_display': cliente.get_segmentacion_display(),
        'is_active': cliente.is_active,
        'created_at': cliente.created_at.isoformat() if cliente.created_at else None,
        'updated_at': cliente.updated_at.isoformat() if cliente.updated_at else None,
    }



# ==============================================================================
# VISTAS BASADAS EN CLASES (CBV) - INTERFAZ WEB
# ==============================================================================

class ClienteListView(LoginRequiredMixin, ListView):
    """
    Vista web para el listado paginado y filtrado interactivo de clientes.

    Soporta filtrado por segmentación comercial (:class:`~customers.models.Cliente.Segmentacion`),
    búsqueda exacta o parcial por RUC/documento, búsqueda textual amplia y estado de actividad.

    :cvar model: Modelo :class:`~customers.models.Cliente`.
    :cvar template_name: Ruta de la plantilla HTML ('customers/cliente_list.html').
    :cvar context_object_name: Nombre de la variable de contexto que contiene la lista ('clientes').
    :cvar paginate_by: Cantidad de clientes por página (10).
    """

    model = Cliente
    template_name = 'customers/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 10

    def get_queryset(self) -> QuerySet[Cliente]:
        """
        Construye el conjunto de datos filtrado de clientes a partir de los parámetros GET recibidos.

        :return: QuerySet de clientes filtrado y ordenado cronológicamente descendente.
        :rtype: django.db.models.QuerySet
        """
        queryset = Cliente.objects.all().order_by('-created_at')
        self.filter_form = ClienteFilterForm(self.request.GET)

        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get('q')
            segmentacion = self.filter_form.cleaned_data.get('segmentacion')
            documento_ruc = self.filter_form.cleaned_data.get('documento_ruc')
            is_active = self.filter_form.cleaned_data.get('is_active')

            if segmentacion:
                queryset = queryset.filter(segmentacion=segmentacion)

            if documento_ruc:
                queryset = queryset.filter(documento_ruc__icontains=documento_ruc)

            if q:
                queryset = queryset.filter(
                    Q(nombre__icontains=q)
                    | Q(documento_ruc__icontains=q)
                    | Q(correo__icontains=q)
                    | Q(telefono__icontains=q)
                )

            if is_active == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active == 'false':
                queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Enriquece el contexto de la plantilla con estadísticas y formularios de filtrado.

        :param kwargs: Argumentos clave adicionales para el contexto.
        :return: Diccionario de contexto con `filter_form`, `total_count`, `active_count` y `querystring`.
        :rtype: dict
        """
        context = super().get_context_data(**kwargs)
        context['filter_form'] = getattr(self, 'filter_form', ClienteFilterForm(self.request.GET))
        context['segment_choices'] = Cliente.Segmentacion.choices
        context['total_count'] = Cliente.objects.count()
        context['active_count'] = Cliente.objects.filter(is_active=True).count()
        context['inactive_count'] = Cliente.objects.filter(is_active=False).count()
        context['count_min'] = Cliente.objects.filter(segmentacion=Cliente.Segmentacion.MINORISTA).count()
        context['count_may'] = Cliente.objects.filter(segmentacion=Cliente.Segmentacion.MAYORISTA).count()
        context['count_cor'] = Cliente.objects.filter(segmentacion=Cliente.Segmentacion.CORPORATIVO).count()
        context['count_vip'] = Cliente.objects.filter(segmentacion=Cliente.Segmentacion.VIP).count()
        context['current_segment'] = self.request.GET.get('segmentacion', '')
        context['current_is_active'] = self.request.GET.get('is_active', '')
        context['current_q'] = self.request.GET.get('q', '')

        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        context['querystring'] = query_params.urlencode()
        return context


class ClienteDetailView(LoginRequiredMixin, DetailView):
    """
    Vista web para consultar la ficha descriptiva detallada de un cliente.

    :cvar model: Modelo :class:`~customers.models.Cliente`.
    :cvar template_name: Ruta de la plantilla HTML ('customers/cliente_detail.html').
    :cvar context_object_name: Nombre de la variable de contexto ('cliente').
    """

    model = Cliente
    template_name = 'customers/cliente_detail.html'
    context_object_name = 'cliente'

    def get_queryset(self) -> QuerySet[Cliente]:
        """
        Retorna el conjunto de datos de clientes optimizado con prefetch de representantes.

        :return: QuerySet de clientes con prefetch de asignaciones y usuarios asociados.
        :rtype: django.db.models.QuerySet[Cliente]
        """
        return super().get_queryset().prefetch_related('assignments__user')


class ClienteCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Vista web basada en clases para registrar nuevos clientes mediante formulario.

    :cvar model: Modelo :class:`~customers.models.Cliente`.
    :cvar form_class: Formulario :class:`~customers.forms.ClienteForm`.
    :cvar template_name: Ruta de la plantilla ('customers/cliente_form.html').
    :cvar success_url: Redirección tras creación exitosa ('customers:cliente-list').
    :cvar success_message: Mensaje de confirmación en pantalla.
    """

    model = Cliente
    form_class = ClienteForm
    template_name = 'customers/cliente_form.html'
    success_url = reverse_lazy('customers:cliente-list')
    success_message = 'Cliente "%(nombre)s" registrado exitosamente.'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Agrega metadatos contextuales (título y acción del formulario).

        :param kwargs: Argumentos clave adicionales.
        :return: Contexto enriquecido.
        :rtype: dict
        """
        context = super().get_context_data(**kwargs)
        context['action'] = 'Crear'
        context['title'] = 'Nuevo Cliente'
        return context


class ClienteUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Vista web basada en clases para modificar los datos de un cliente existente.

    :cvar model: Modelo :class:`~customers.models.Cliente`.
    :cvar form_class: Formulario :class:`~customers.forms.ClienteForm`.
    :cvar template_name: Ruta de la plantilla ('customers/cliente_form.html').
    :cvar success_url: Redirección tras actualización exitosa ('customers:cliente-list').
    :cvar success_message: Mensaje de confirmación en pantalla.
    """

    model = Cliente
    form_class = ClienteForm
    template_name = 'customers/cliente_form.html'
    success_url = reverse_lazy('customers:cliente-list')
    success_message = 'Cliente "%(nombre)s" actualizado exitosamente.'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Agrega metadatos contextuales de edición al contexto.

        :param kwargs: Argumentos clave adicionales.
        :return: Contexto enriquecido con título dinámico.
        :rtype: dict
        """
        context = super().get_context_data(**kwargs)
        context['action'] = 'Actualizar'
        context['title'] = f'Editar Cliente: {self.object.nombre}'
        return context


class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    """
    Vista web basada en clases para la confirmación y eliminación física de un cliente.

    :cvar model: Modelo :class:`~customers.models.Cliente`.
    :cvar template_name: Plantilla de confirmación ('customers/cliente_confirm_delete.html').
    :cvar context_object_name: Nombre de la variable de contexto ('cliente').
    :cvar success_url: Redirección tras borrado ('customers:cliente-list').
    """

    model = Cliente
    template_name = 'customers/cliente_confirm_delete.html'
    context_object_name = 'cliente'
    success_url = reverse_lazy('customers:cliente-list')

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Procesa la eliminación definitiva del cliente y emite un mensaje flash de éxito.

        :param request: Objeto de solicitud HTTP POST.
        :type request: django.http.HttpRequest
        :return: Redirección a la lista de clientes.
        :rtype: django.http.HttpResponse
        """
        cliente = self.get_object()
        nombre = cliente.nombre
        cliente.delete()
        messages.success(request, f'Cliente "{nombre}" eliminado exitosamente.')
        return redirect(self.success_url)


# ==============================================================================
# API VIEWS (ENDPOINTS REST / JSON)
# ==============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class ClienteListCreateAPIView(View):
    """
    Controlador API REST para operaciones de listado y creación masiva/individual de clientes en formato JSON.

    Ruta: ``/customers/api/``

    * **GET**: Recupera la colección de clientes aplicando filtros opcionales de segmentación, RUC, texto o estado.
    * **POST**: Crea un nuevo registro de cliente a partir de un cuerpo JSON estructurado.
    """

    def get(self, request: HttpRequest) -> JsonResponse:
        """
        Maneja solicitudes HTTP GET para listar y filtrar clientes en formato JSON.

        :param request: Objeto de solicitud HTTP. Parámetros de consulta aceptados:
            * ``segmentacion`` (*str*): Código del segmento ('MIN', 'MAY', 'COR', 'VIP').
            * ``documento_ruc`` (*str*): Búsqueda por documento/RUC.
            * ``q`` (*str*): Búsqueda abierta por nombre, email, RUC o teléfono.
            * ``is_active`` (*str*): 'true' o 'false'.
            * ``page`` (*int*, opcional): Número de página para paginación (20 registros/pág).
        :type request: django.http.HttpRequest
        :return: Objeto JsonResponse con la lista de clientes y metadatos de conteo.
        :rtype: django.http.JsonResponse
        """
        queryset = Cliente.objects.all().order_by('-created_at')

        segmentacion = request.GET.get('segmentacion', '').strip()
        documento_ruc = request.GET.get('documento_ruc', '').strip()
        q = request.GET.get('q', '').strip()
        is_active = request.GET.get('is_active', '').strip().lower()

        if segmentacion:
            queryset = queryset.filter(segmentacion=segmentacion)

        if documento_ruc:
            queryset = queryset.filter(documento_ruc__icontains=documento_ruc)

        if q:
            queryset = queryset.filter(
                Q(nombre__icontains=q)
                | Q(documento_ruc__icontains=q)
                | Q(correo__icontains=q)
                | Q(telefono__icontains=q)
            )

        if is_active in ['true', '1']:
            queryset = queryset.filter(is_active=True)
        elif is_active in ['false', '0']:
            queryset = queryset.filter(is_active=False)

        page = request.GET.get('page')
        if page:
            paginator = Paginator(queryset, 20)
            page_obj = paginator.get_page(page)
            results = [_serialize_cliente(c) for c in page_obj]
            return JsonResponse({
                'count': paginator.count,
                'num_pages': paginator.num_pages,
                'current_page': page_obj.number,
                'results': results,
            })

        results = [_serialize_cliente(c) for c in queryset]
        return JsonResponse({'count': len(results), 'results': results}, safe=False)

    def post(self, request: HttpRequest) -> JsonResponse:
        """
        Maneja solicitudes HTTP POST para crear un nuevo cliente vía JSON.

        :param request: Objeto de solicitud HTTP con payload JSON en el body.
        :type request: django.http.HttpRequest
        :return: JsonResponse con el cliente creado (HTTP 201) o detalle de errores (HTTP 400).
        :rtype: django.http.JsonResponse
        """
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {'error': 'Payload JSON inválido.'},
                status=400
            )

        form = ClienteForm(data)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse(
                {
                    'message': 'Cliente creado exitosamente.',
                    'cliente': _serialize_cliente(cliente),
                },
                status=201
            )
        else:
            return JsonResponse(
                {
                    'error': 'Error de validación.',
                    'details': form.errors.get_json_data(),
                },
                status=400
            )


@method_decorator(csrf_exempt, name='dispatch')
class ClienteDetailAPIView(View):
    """
    Controlador API REST para consultar, actualizar y eliminar instancias individuales de :class:`~customers.models.Cliente`.

    Rutas asociadas:
        * ``/customers/api/<int:pk>/``
        * ``/customers/api/documento/<str:documento_ruc>/``
    """

    def _get_object(self, pk: Optional[int] = None, documento_ruc: Optional[str] = None) -> Cliente:
        """
        Obtiene la entidad Cliente correspondiente a la clave primaria o al número de documento/RUC.

        :param pk: Identificador clave primaria del cliente (opcional).
        :type pk: int or None
        :param documento_ruc: Documento de identidad fiscal o civil del cliente (opcional).
        :type documento_ruc: str or None
        :raises django.http.Http404: Si no se encuentra un cliente coincidente.
        :return: Instancia encontrada del cliente.
        :rtype: customers.models.Cliente
        """
        if pk is not None:
            return get_object_or_404(Cliente, pk=pk)
        elif documento_ruc is not None:
            return get_object_or_404(Cliente, documento_ruc=documento_ruc)
        raise Http404('Cliente no encontrado.')

    def get(self, request: HttpRequest, pk: Optional[int] = None, documento_ruc: Optional[str] = None) -> JsonResponse:
        """
        Maneja solicitudes HTTP GET para consultar el detalle de un cliente.

        :param request: Objeto de solicitud HTTP.
        :type request: django.http.HttpRequest
        :param pk: Clave primaria del cliente.
        :type pk: int, optional
        :param documento_ruc: Documento o RUC del cliente.
        :type documento_ruc: str, optional
        :return: JsonResponse con los datos del cliente.
        :rtype: django.http.JsonResponse
        """
        cliente = self._get_object(pk=pk, documento_ruc=documento_ruc)
        return JsonResponse(_serialize_cliente(cliente))

    def put(self, request: HttpRequest, pk: Optional[int] = None, documento_ruc: Optional[str] = None) -> JsonResponse:
        """
        Maneja solicitudes HTTP PUT para la actualización completa de un cliente.

        :param request: Objeto de solicitud HTTP con payload JSON.
        :type request: django.http.HttpRequest
        :param pk: Clave primaria del cliente.
        :type pk: int, optional
        :param documento_ruc: Documento o RUC del cliente.
        :type documento_ruc: str, optional
        :return: JsonResponse con el registro actualizado (HTTP 200) o error de validación (HTTP 400).
        :rtype: django.http.JsonResponse
        """
        cliente = self._get_object(pk=pk, documento_ruc=documento_ruc)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Payload JSON inválido.'}, status=400)

        form = ClienteForm(data, instance=cliente)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse(
                {
                    'message': 'Cliente actualizado exitosamente.',
                    'cliente': _serialize_cliente(cliente),
                },
                status=200
            )
        else:
            return JsonResponse(
                {
                    'error': 'Error de validación.',
                    'details': form.errors.get_json_data(),
                },
                status=400
            )

    def patch(self, request: HttpRequest, pk: Optional[int] = None, documento_ruc: Optional[str] = None) -> JsonResponse:
        """
        Maneja solicitudes HTTP PATCH para la actualización parcial de los atributos de un cliente.

        :param request: Objeto de solicitud HTTP con campos JSON a modificar.
        :type request: django.http.HttpRequest
        :param pk: Clave primaria del cliente.
        :type pk: int, optional
        :param documento_ruc: Documento o RUC del cliente.
        :type documento_ruc: str, optional
        :return: JsonResponse con los datos actualizados (HTTP 200) o error (HTTP 400).
        :rtype: django.http.JsonResponse
        """
        cliente = self._get_object(pk=pk, documento_ruc=documento_ruc)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Payload JSON inválido.'}, status=400)

        current_data = {
            'nombre': cliente.nombre,
            'documento_ruc': cliente.documento_ruc,
            'correo': cliente.correo,
            'telefono': cliente.telefono,
            'segmentacion': cliente.segmentacion,
            'is_active': cliente.is_active,
        }
        current_data.update(data)

        form = ClienteForm(current_data, instance=cliente)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse(
                {
                    'message': 'Cliente actualizado exitosamente.',
                    'cliente': _serialize_cliente(cliente),
                },
                status=200
            )
        else:
            return JsonResponse(
                {
                    'error': 'Error de validación.',
                    'details': form.errors.get_json_data(),
                },
                status=400
            )

    def delete(self, request: HttpRequest, pk: Optional[int] = None, documento_ruc: Optional[str] = None) -> JsonResponse:
        """
        Maneja solicitudes HTTP DELETE para eliminar de forma definitiva a un cliente.

        :param request: Objeto de solicitud HTTP.
        :type request: django.http.HttpRequest
        :param pk: Clave primaria del cliente a eliminar.
        :type pk: int, optional
        :param documento_ruc: Documento o RUC del cliente a eliminar.
        :type documento_ruc: str, optional
        :return: JsonResponse con mensaje de confirmación (HTTP 200).
        :rtype: django.http.JsonResponse
        """
        cliente = self._get_object(pk=pk, documento_ruc=documento_ruc)
        cliente_id = cliente.id
        cliente.delete()
        return JsonResponse(
            {'message': f'Cliente con ID {cliente_id} eliminado exitosamente.'},
            status=200
        )

class SwitchActiveCustomerView(LoginRequiredMixin, View):
    """
    Controlador web para el cambio dinámico del cliente activo en sesión.

    Verifica que el usuario autenticado posea una asignación activa sobre
    el cliente solicitado (:class:`~customers.models.CustomerUserAssignment`)
    antes de actualizar ``active_customer_id`` en ``request.session``,
    y redirige de vuelta a la vista de origen.

    Ruta: ``/customers/cambiar-cliente/<int:customer_id>/``
    """

    def post(self, request: HttpRequest, customer_id: int) -> HttpResponse:
        """
        Procesa el cambio de cliente activo vía solicitud HTTP POST.

        :param request: Objeto de solicitud HTTP.
        :type request: django.http.HttpRequest
        :param customer_id: Identificador del cliente a activar.
        :type customer_id: int
        :raises django.http.Http404: Si el usuario no posee una asignación activa sobre el cliente.
        :return: Redirección a la página de origen (o inicio, si no hay referer).
        :rtype: django.http.HttpResponse
        """
        assignment = get_object_or_404(
            CustomerUserAssignment,
            customer_id=customer_id,
            user=request.user,
            is_active=True,
            customer__is_active=True,
        )

        request.session['active_customer_id'] = assignment.customer_id
        messages.success(request, f'Cliente activo cambiado a "{assignment.customer.nombre}".')

        next_url = request.META.get('HTTP_REFERER', reverse_lazy('home'))
        return redirect(next_url)