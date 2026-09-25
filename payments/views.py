"""
Módulo de vistas y controladores para la gestión segura de Medios de Pago (payments).

Implementa la arquitectura dual:

1. **Vistas Basadas en Clases (CBVs)** para interfaz web de usuario con protección de sesión, prevención de Insecure Direct Object References (IDOR) circunscrita a la ficha de cliente del usuario autenticado, validación de estados predeterminados y filtrado interactivo.
2. **Endpoints API REST (JSON)** para consultas programáticas y operaciones seguras.
"""

import json
from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied, ValidationError
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

from customers.models import Cliente
from .forms import PaymentMethodFilterForm, PaymentMethodForm, ReceivingMethodForm
from .models import EntidadFinanciera, PaymentMethod, ReceivingMethod


def get_current_cliente(request: HttpRequest) -> Optional[Cliente]:
    """
    Resuelve de forma segura la instancia de :class:`~customers.models.Cliente`
    asociada a la solicitud y sesión del usuario autenticado.

    Prioridad de resolución:
    1. Atributo dinámico `request.active_customer` (invectado por middleware de cliente activo).
    2. Identificador en sesión `request.session['active_customer_id']`.
    3. Relación directa uno a uno `request.user.cliente`.
    4. Consulta por usuario `Cliente.objects.filter(usuario=request.user).first()`.
    5. Parámetro `cliente_id` en GET/POST sólo para administradores o personal operativo (`is_staff`).

    :param request: Solicitud HTTP entrante.
    :type request: django.http.HttpRequest
    :return: Instancia del cliente asociado o None si no se localiza ninguna ficha.
    :rtype: customers.models.Cliente or None
    """
    if not request.user.is_authenticated:
        return None

    # 1. Atributo inyectado en middleware
    if hasattr(request, 'active_customer') and request.active_customer:
        return request.active_customer

    # 2. Clave en sesión
    session_customer_id = request.session.get('active_customer_id')
    if session_customer_id:
        c = Cliente.objects.filter(id=session_customer_id).first()
        if c:
            return c

    # 3. Asignación en CustomerUserAssignment
    if hasattr(request.user, 'customer_assignments'):
        asig = request.user.customer_assignments.filter(is_active=True).select_related('customer').order_by('-is_primary_representative', '-assigned_at').first()
        if asig:
            return asig.customer

    # 4. Consulta por correo institucional o personal
    if request.user.email:
        cliente_email = Cliente.objects.filter(correo=request.user.email).first()
        if cliente_email:
            return cliente_email

    # 5. Operadores o administradores con selector de cliente
    if request.user.is_staff or request.user.is_superuser:
        cliente_id_param = request.GET.get('cliente_id') or request.POST.get('cliente_id')
        if cliente_id_param:
            return Cliente.objects.filter(id=cliente_id_param).first()
        # Fallback al primer cliente activo en el sistema para permitir pruebas y administración
        return Cliente.objects.filter(is_active=True).first()

    return None


def serialize_payment_method(pm: PaymentMethod) -> Dict[str, Any]:
    """
    Serializa una instancia de :class:`~payments.models.PaymentMethod` en un diccionario estándar JSON.

    :param pm: Instancia del medio de pago.
    :type pm: payments.models.PaymentMethod
    :return: Diccionario con los datos formateados del medio de pago.
    :rtype: dict
    """
    return {
        'id': pm.id,
        'cliente_id': pm.cliente_id,
        'tipo_medio': pm.tipo_medio,
        'tipo_medio_display': pm.get_tipo_medio_display(),
        'entidad_bancaria': pm.entidad_bancaria.nombre if pm.entidad_bancaria else None,
        'entidad_bancaria_id': pm.entidad_bancaria_id,
        'numero_cuenta': pm.numero_cuenta,
        'titular': pm.titular,
        'documento_titular': pm.documento_titular,
        'tarjeta_ultimos_digitos': pm.tarjeta_ultimos_digitos,
        'tarjeta_mes_vencimiento': pm.tarjeta_mes_vencimiento,
        'tarjeta_anio_vencimiento': pm.tarjeta_anio_vencimiento,
        'tipo_cuenta_bancaria': pm.tipo_cuenta_bancaria,
        'telefono_billetera': pm.telefono_billetera,
        'es_predeterminado': pm.es_predeterminado,
        'activo': pm.activo,
        'created_at': pm.created_at.isoformat() if pm.created_at else None,
        'updated_at': pm.updated_at.isoformat() if pm.updated_at else None,
    }


# ==============================================================================
# VISTAS WEB CBV (HTML)
# ==============================================================================

class PaymentMethodListView(LoginRequiredMixin, ListView):
    """
    Vista web para el listado interactivo de medios de pago del cliente autenticado.

    Garantiza aislamiento estricto de datos: cada cliente visualiza exclusivamente
    sus propios medios de pago, previniendo fugas de información financiera.
    """

    model = PaymentMethod
    template_name = 'payments/paymentmethod_list.html'
    context_object_name = 'medios_pago'
    paginate_by = 12

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.cliente = get_current_cliente(request)
        if not self.cliente and not (request.user.is_staff or request.user.is_superuser):
            messages.warning(
                request,
                'Para gestionar medios de pago, debe contar con una ficha de cliente registrada o activa.',
            )
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[PaymentMethod]:
        """
        Retorna los medios de pago asociados al cliente activo aplicando los filtros recibidos.
        """
        if not self.cliente:
            return PaymentMethod.objects.none()

        queryset = PaymentMethod.objects.filter(cliente=self.cliente)
        self.filter_form = PaymentMethodFilterForm(self.request.GET)

        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get('q')
            tipo_medio = self.filter_form.cleaned_data.get('tipo_medio')
            activo = self.filter_form.cleaned_data.get('activo')

            if q:
                queryset = queryset.filter(
                    Q(entidad_bancaria__icontains=q)
                    | Q(numero_cuenta__icontains=q)
                    | Q(titular__icontains=q)
                    | Q(documento_titular__icontains=q)
                )

            if tipo_medio:
                queryset = queryset.filter(tipo_medio=tipo_medio)

            if activo == 'true':
                queryset = queryset.filter(activo=True)
            elif activo == 'false':
                queryset = queryset.filter(activo=False)

        return queryset.order_by('-es_predeterminado', '-created_at')

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.cliente
        context['filter_form'] = getattr(self, 'filter_form', PaymentMethodFilterForm(self.request.GET))
        if self.cliente:
            all_pm = PaymentMethod.objects.filter(cliente=self.cliente)
            context['total_count'] = all_pm.count()
            context['activos_count'] = all_pm.filter(activo=True).count()
            context['predeterminado_pm'] = all_pm.filter(es_predeterminado=True).first()
        else:
            context['total_count'] = 0
            context['activos_count'] = 0
            context['predeterminado_pm'] = None
        return context


class PaymentMethodCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Vista web para registrar un nuevo medio de pago asociado al cliente activo.
    """

    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'payments/paymentmethod_form.html'
    success_url = reverse_lazy('payments:paymentmethod-list')
    success_message = 'El medio de pago fue registrado con éxito.'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.cliente = get_current_cliente(request)
        if not self.cliente:
            messages.error(
                request,
                'No se localizó una ficha de cliente activa para asociar el nuevo medio de pago.',
            )
            return redirect('payments:paymentmethod-list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: PaymentMethodForm) -> HttpResponse:
        form.instance.cliente = self.cliente
        # Si es el primer medio de pago registrado para el cliente, se define como predeterminado por conveniencia
        if not PaymentMethod.objects.filter(cliente=self.cliente).exists():
            form.instance.es_predeterminado = True
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.cliente
        context['action'] = 'Registrar'
        context['is_create'] = True
        return context


class PaymentMethodUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Vista web para editar los datos de un medio de pago existente.

    Seguridad: `get_queryset` asegura que únicamente el titular del medio de pago
    o personal autorizado pueda acceder a la modificación (protección IDOR).
    """

    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'payments/paymentmethod_form.html'
    success_url = reverse_lazy('payments:paymentmethod-list')
    success_message = 'El medio de pago fue actualizado satisfactoriamente.'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.cliente = get_current_cliente(request)
        if not self.cliente:
            raise PermissionDenied('No tiene un cliente asociado para editar este medio de pago.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[PaymentMethod]:
        if self.request.user.is_superuser:
            return PaymentMethod.objects.all()
        return PaymentMethod.objects.filter(cliente=self.cliente)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.cliente
        context['action'] = 'Actualizar'
        context['is_create'] = False
        return context


class PaymentMethodDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    """
    Vista web para eliminar de manera segura un medio de pago con pantalla de confirmación.

    Seguridad: La consulta queda restringida al cliente autenticado.
    """

    model = PaymentMethod
    template_name = 'payments/paymentmethod_confirm_delete.html'
    success_url = reverse_lazy('payments:paymentmethod-list')
    success_message = 'El medio de pago fue eliminado correctamente.'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.cliente = get_current_cliente(request)
        if not self.cliente:
            raise PermissionDenied('No cuenta con autorización para eliminar este medio de pago.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[PaymentMethod]:
        if self.request.user.is_superuser:
            return PaymentMethod.objects.all()
        return PaymentMethod.objects.filter(cliente=self.cliente)

    def delete(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        messages.success(request, self.success_message)
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.cliente
        return context


class PaymentMethodSetDefaultView(LoginRequiredMixin, View):
    """
    Acción POST para marcar un medio de pago como el predeterminado para operaciones del cliente.
    """

    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cliente = get_current_cliente(request)
        if not cliente:
            raise PermissionDenied('Acceso no autorizado.')

        qs = PaymentMethod.objects.all() if request.user.is_superuser else PaymentMethod.objects.filter(cliente=cliente)
        payment_method = get_object_or_404(qs, pk=pk)

        payment_method.activo = True
        payment_method.es_predeterminado = True
        payment_method.save()

        messages.success(
            request,
            f'"{payment_method.entidad_bancaria}" ha sido establecido como su medio de pago predeterminado.',
        )
        return redirect('payments:paymentmethod-list')


class PaymentMethodToggleActiveView(LoginRequiredMixin, View):
    """
    Acción POST para alternar el estado activo/inactivo de un medio de pago.
    """

    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cliente = get_current_cliente(request)
        if not cliente:
            raise PermissionDenied('Acceso no autorizado.')

        qs = PaymentMethod.objects.all() if request.user.is_superuser else PaymentMethod.objects.filter(cliente=cliente)
        payment_method = get_object_or_404(qs, pk=pk)

        nuevo_estado = not payment_method.activo
        payment_method.activo = nuevo_estado
        if not nuevo_estado and payment_method.es_predeterminado:
            payment_method.es_predeterminado = False
        payment_method.save()

        estado_texto = 'habilitado' if nuevo_estado else 'inhabilitado'
        messages.info(
            request,
            f'El medio de pago "{payment_method.entidad_bancaria}" fue {estado_texto} correctamente.',
        )
        return redirect('payments:paymentmethod-list')

class ReceivingMethodListView(LoginRequiredMixin, ListView):
    """
    Vista web para el listado de cuentas de acreditación de fondos del cliente activo.
    """
    model = ReceivingMethod
    template_name = 'payments/receivingmethod_list.html'
    context_object_name = 'medios_acreditacion'
    paginate_by = 12

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.cliente = get_current_cliente(request)
        if not self.cliente and not (request.user.is_staff or request.user.is_superuser):
            messages.warning(request, 'Para gestionar cuentas de acreditación, debe contar con una ficha de cliente activa.')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[ReceivingMethod]:
        if not self.cliente:
            return ReceivingMethod.objects.none()
        return ReceivingMethod.objects.filter(cliente=self.cliente).order_by('-es_predeterminado', '-created_at')

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.cliente
        return context


class ReceivingMethodCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Vista web para registrar una nueva cuenta de acreditación de fondos.
    """
    model = ReceivingMethod
    form_class = ReceivingMethodForm
    template_name = 'payments/receivingmethod_form.html'
    success_url = reverse_lazy('payments:receivingmethod-list')
    success_message = 'La cuenta de acreditación fue registrada con éxito.'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.cliente = get_current_cliente(request)
        if not self.cliente:
            messages.error(request, 'No se localizó una ficha de cliente activa para asociar la nueva cuenta.')
            return redirect('payments:receivingmethod-list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: ReceivingMethodForm) -> HttpResponse:
        form.instance.cliente = self.cliente
        if not ReceivingMethod.objects.filter(cliente=self.cliente).exists():
            form.instance.es_predeterminado = True
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.cliente
        context['action'] = 'Registrar'
        context['is_create'] = True
        return context


class ReceivingMethodUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Vista web para editar una cuenta de acreditación existente.
    """
    model = ReceivingMethod
    form_class = ReceivingMethodForm
    template_name = 'payments/receivingmethod_form.html'
    success_url = reverse_lazy('payments:receivingmethod-list')
    success_message = 'La cuenta de acreditación fue actualizada satisfactoriamente.'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.cliente = get_current_cliente(request)
        if not self.cliente:
            raise PermissionDenied('No tiene un cliente asociado para editar esta cuenta.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[ReceivingMethod]:
        if self.request.user.is_superuser:
            return ReceivingMethod.objects.all()
        return ReceivingMethod.objects.filter(cliente=self.cliente)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.cliente
        context['action'] = 'Actualizar'
        context['is_create'] = False
        return context


class ReceivingMethodToggleActiveView(LoginRequiredMixin, View):
    """
    Acción POST para el borrado lógico (activar/desactivar) de una cuenta de acreditación.
    """
    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cliente = get_current_cliente(request)
        if not cliente:
            raise PermissionDenied('Acceso no autorizado.')

        qs = ReceivingMethod.objects.all() if request.user.is_superuser else ReceivingMethod.objects.filter(cliente=cliente)
        rm = get_object_or_404(qs, pk=pk)

        nuevo_estado = not rm.activo
        rm.activo = nuevo_estado
        if not nuevo_estado and rm.es_predeterminado:
            rm.es_predeterminado = False
        rm.save()

        estado_texto = 'habilitada' if nuevo_estado else 'inhabilitada'
        messages.info(request, f'La cuenta de acreditación fue {estado_texto} correctamente.')
        return redirect('payments:receivingmethod-list')


class ReceivingMethodSetDefaultView(LoginRequiredMixin, View):
    """
    Acción POST para marcar una cuenta como predeterminada para acreditaciones.
    """
    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cliente = get_current_cliente(request)
        if not cliente:
            raise PermissionDenied('Acceso no autorizado.')

        qs = ReceivingMethod.objects.all() if request.user.is_superuser else ReceivingMethod.objects.filter(cliente=cliente)
        rm = get_object_or_404(qs, pk=pk)

        rm.activo = True
        rm.es_predeterminado = True
        rm.save()

        messages.success(request, f'"{rm}" ha sido establecida como su cuenta de acreditación predeterminada.')
        return redirect('payments:receivingmethod-list')



# ==============================================================================
# ENDPOINTS API REST (JSON)
# ==============================================================================

class PaymentMethodListCreateAPIView(LoginRequiredMixin, View):
    """
    Endpoint REST para listar (GET) y dar de alta (POST) medios de pago en formato JSON.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        cliente = get_current_cliente(request)
        if not cliente:
            return JsonResponse({'error': 'Cliente no encontrado o no asociado al usuario actual.'}, status=400)

        queryset = PaymentMethod.objects.filter(cliente=cliente).order_by('-es_predeterminado', '-created_at')
        tipo = request.GET.get('tipo_medio')
        if tipo:
            queryset = queryset.filter(tipo_medio=tipo)

        activo = request.GET.get('activo')
        if activo is not None and activo != '':
            queryset = queryset.filter(activo=activo.lower() in ['true', '1', 'yes'])

        data = [serialize_payment_method(pm) for pm in queryset]
        return JsonResponse({'results': data, 'count': len(data)}, status=200)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        cliente = get_current_cliente(request)
        if not cliente:
            return JsonResponse({'error': 'Cliente no encontrado o no asociado al usuario actual.'}, status=400)

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Cuerpo de solicitud JSON inválido.'}, status=400)

        entidad = payload.get('entidad_bancaria')
        if isinstance(entidad, str) and not entidad.isdigit():
            ent_obj = EntidadFinanciera.objects.filter(nombre__iexact=entidad.strip()).first()
            if ent_obj:
                payload['entidad_bancaria'] = ent_obj.id

        form = PaymentMethodForm(payload)
        if form.is_valid():
            pm: PaymentMethod = form.save(commit=False)
            pm.cliente = cliente
            try:
                pm.save()
            except ValidationError as exc:
                return JsonResponse({'errors': exc.message_dict}, status=400)
            return JsonResponse(serialize_payment_method(pm), status=201)

        return JsonResponse({'errors': form.errors}, status=400)


class PaymentMethodDetailAPIView(LoginRequiredMixin, View):
    """
    Endpoint REST para consultar detalle (GET), actualizar (PUT/PATCH) o eliminar (DELETE) un medio de pago.
    """

    def _get_object(self, request: HttpRequest, pk: int) -> PaymentMethod:
        cliente = get_current_cliente(request)
        if not cliente:
            raise Http404('Cliente no asociado.')
        qs = PaymentMethod.objects.all() if request.user.is_superuser else PaymentMethod.objects.filter(cliente=cliente)
        return get_object_or_404(qs, pk=pk)

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        pm = self._get_object(request, pk)
        return JsonResponse(serialize_payment_method(pm), status=200)

    def put(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        return self._update(request, pk, partial=False)

    def patch(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        return self._update(request, pk, partial=True)

    def _update(self, request: HttpRequest, pk: int, partial: bool = False) -> JsonResponse:
        pm = self._get_object(request, pk)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'JSON inválido.'}, status=400)

        entidad = payload.get('entidad_bancaria')
        if isinstance(entidad, str) and not entidad.isdigit():
            ent_obj = EntidadFinanciera.objects.filter(nombre__iexact=entidad.strip()).first()
            if ent_obj:
                entidad = ent_obj.id
            else:
                entidad = pm.entidad_bancaria_id
        elif entidad is None:
            entidad = pm.entidad_bancaria_id

        data = {
            'tipo_medio': payload.get('tipo_medio', pm.tipo_medio),
            'entidad_bancaria': entidad,
            'numero_cuenta': payload.get('numero_cuenta', pm.numero_cuenta),
            'titular': payload.get('titular', pm.titular),
            'documento_titular': payload.get('documento_titular', pm.documento_titular),
            'tarjeta_ultimos_digitos': payload.get('tarjeta_ultimos_digitos', pm.tarjeta_ultimos_digitos),
            'tarjeta_mes_vencimiento': payload.get('tarjeta_mes_vencimiento', pm.tarjeta_mes_vencimiento),
            'tarjeta_anio_vencimiento': payload.get('tarjeta_anio_vencimiento', pm.tarjeta_anio_vencimiento),
            'tipo_cuenta_bancaria': payload.get('tipo_cuenta_bancaria', pm.tipo_cuenta_bancaria),
            'telefono_billetera': payload.get('telefono_billetera', pm.telefono_billetera),
            'es_predeterminado': payload.get('es_predeterminado', pm.es_predeterminado),
            'activo': payload.get('activo', pm.activo),
        }

        form = PaymentMethodForm(data, instance=pm)
        if form.is_valid():
            try:
                updated_pm = form.save()
                return JsonResponse(serialize_payment_method(updated_pm), status=200)
            except ValidationError as exc:
                return JsonResponse({'errors': exc.message_dict}, status=400)

        return JsonResponse({'errors': form.errors}, status=400)

    def delete(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        pm = self._get_object(request, pk)
        pm_id = pm.id
        pm.delete()
        return JsonResponse({'deleted': True, 'id': pm_id}, status=200)
