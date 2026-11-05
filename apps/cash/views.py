"""
Vistas basadas en clases para la gestión de Cajas, Turnos y Arqueos (apps.cash.views).

Provee la interfaz de usuario web y endpoints para:
- Dashboard de caja en tiempo real y consulta de balances por divisa.
- Apertura de turno con registro de fondo inicial (RF-22, RN05).
- Registro de movimientos manuales de caja con control de saldo físico (RF-24).
- Flujo guiado de Cierre con Arqueo Ciego y cálculo de diferencias (RF-23).
- Acta y comprobante oficial de arqueo imprimible.
- Historial de turnos y estado de terminales físicas.
"""

from decimal import Decimal
import json
import logging
from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from authentication.permissions import CashierRequiredMixin, RoleRequiredMixin, has_role, verify_shift_ownership
from rates.models import Currency
from .forms import (
    BlindReconciliationForm,
    CashMovementForm,
    CashShiftOpenForm,
)
from .models import (
    CashMovement,
    CashRegister,
    CashRegisterStatus,
    CashShift,
    MovementFlow,
    MovementType,
    ShiftStatus,
)
from .services import (
    CashError,
    CashRegisterError,
    CashService,
    CashShiftError,
    InsufficientCashBalanceError,
)

logger = logging.getLogger(__name__)

ALLOWED_CASH_ROLES = ['admin', 'operator', 'cajero']


class CashBaseMixin(LoginRequiredMixin, CashierRequiredMixin):
    """Mixin base de seguridad para las vistas operativas de caja y tesorería (SCRUM-116)."""

    allowed_roles = ALLOWED_CASH_ROLES
    permission_denied_message = "Requiere rol de Cajero, Operador o Administrador para operar en este módulo."


class CashDashboardView(CashBaseMixin, View):
    """
    Panel principal de gestión de caja y consulta en tiempo real.

    Si el cajero posee un turno activo, muestra sus saldos actuales por divisa,
    los últimos movimientos y accesos para registrar ingresos/egresos o cerrar la jornada.
    Si no posee turno activo, presenta las cajas registradoras disponibles para apertura.
    """

    template_name = 'cash/dashboard.html'

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        active_shift = CashShift.objects.filter(cashier=user, status=ShiftStatus.OPEN).first()

        context: Dict[str, Any] = {
            'active_shift': active_shift,
            'now': timezone.now(),
        }

        if active_shift:
            # Calcular saldos en vivo por divisa
            summary = CashService.get_shift_summary(active_shift)
            recent_movements = active_shift.movements.select_related('currency', 'cashier', 'transaction')[:25]

            context['summary'] = summary
            context['recent_movements'] = recent_movements
            context['currencies_summary'] = summary['currencies']
            context['total_inflows'] = sum(
                (Decimal(c['total_in']) for c in summary['currencies']),
                Decimal('0.00'),
            )
            context['total_outflows'] = sum(
                (Decimal(c['total_out']) for c in summary['currencies']),
                Decimal('0.00'),
            )
        else:
            # Cajas físicas de la sucursal disponibles para abrir
            registers = CashRegister.objects.filter(is_active=True).order_by('branch_name', 'register_code')
            recent_shifts = CashShift.objects.filter(cashier=user).exclude(status=ShiftStatus.OPEN)[:5]
            context['registers'] = registers
            context['recent_shifts'] = recent_shifts

        return render(request, self.template_name, context)


class CashShiftOpenView(CashBaseMixin, View):
    """
    Vista para la apertura formal de un turno de caja con fondo inicial (RF-22).
    """

    template_name = 'cash/shift_open.html'

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # Si el cajero ya tiene un turno abierto, redirigir al dashboard
        active_shift = CashShift.objects.filter(cashier=request.user, status=ShiftStatus.OPEN).first()
        if active_shift:
            messages.info(
                request,
                f"Ya cuenta con el turno {active_shift.shift_number} abierto en la caja "
                f"{active_shift.cash_register.register_code}."
            )
            return redirect('cash:dashboard')

        form = CashShiftOpenForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        active_shift = CashShift.objects.filter(cashier=request.user, status=ShiftStatus.OPEN).first()
        if active_shift:
            messages.warning(request, "Ya posee un turno abierto en el sistema.")
            return redirect('cash:dashboard')

        form = CashShiftOpenForm(request.POST)
        if form.is_valid():
            keycloak_sub = request.session.get('oidc_id_token_sub', '')
            try:
                shift = form.save(cashier=request.user, keycloak_user_id=keycloak_sub)
                messages.success(
                    request,
                    f"¡Turno {shift.shift_number} abierto exitosamente en la caja {shift.cash_register.register_code}!"
                )
                return redirect('cash:dashboard')
            except CashError as err:
                messages.error(request, str(err))
            except Exception as exc:
                logger.exception("Error al abrir turno de caja: %s", exc)
                messages.error(request, "Ocurrió un error inesperado al intentar abrir el turno.")

        return render(request, self.template_name, {'form': form})


class CashMovementCreateView(CashBaseMixin, View):
    """
    Vista para el registro de movimientos manuales de efectivo (RF-24).
    """

    template_name = 'cash/movement_create.html'

    def get_active_shift(self, request: HttpRequest) -> Optional[CashShift]:
        return CashShift.objects.filter(cashier=request.user, status=ShiftStatus.OPEN).first()

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        shift = self.get_active_shift(request)
        if not shift:
            messages.error(request, "Debe poseer un turno abierto para registrar movimientos de efectivo.")
            return redirect('cash:dashboard')

        form = CashMovementForm(shift=shift)
        summary = CashService.get_shift_summary(shift)
        return render(request, self.template_name, {
            'form': form,
            'shift': shift,
            'summary': summary,
        })

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        shift = self.get_active_shift(request)
        if not shift:
            messages.error(request, "No posee un turno abierto en curso.")
            return redirect('cash:dashboard')

        form = CashMovementForm(shift, request.POST)
        if form.is_valid():
            keycloak_sub = request.session.get('oidc_id_token_sub', '')
            try:
                mov = form.save(cashier=request.user, keycloak_user_id=keycloak_sub)
                messages.success(
                    request,
                    f"Movimiento de {mov.currency.code} {mov.amount:,.2f} ({mov.get_movement_type_display()}) "
                    f"registrado con éxito. Saldo resultante: {mov.resulting_balance:,.2f}."
                )
                return redirect('cash:dashboard')
            except InsufficientCashBalanceError as err:
                messages.error(request, str(err))
            except CashError as err:
                messages.error(request, str(err))
            except Exception as exc:
                logger.exception("Error al registrar movimiento de efectivo: %s", exc)
                messages.error(request, "Ocurrió un error al registrar el movimiento físico.")

        summary = CashService.get_shift_summary(shift)
        return render(request, self.template_name, {
            'form': form,
            'shift': shift,
            'summary': summary,
        })


class CashShiftCloseView(CashBaseMixin, View):
    """
    Vista para el Cierre de Turno con Arqueo Ciego (RF-23).

    Protocolo de Arqueo Ciego:
    Los saldos teóricos esperados son omitidos de la interfaz visual durante el conteo.
    El cajero ingresa las cifras físicas reales encontradas en la gaveta y, tras el envío,
    el sistema calcula y revela las diferencias matemáticas (sobrante o faltante).
    """

    template_name = 'cash/shift_close.html'

    def get_shift(self, request: HttpRequest, pk: Optional[int] = None) -> CashShift:
        if pk:
            shift = get_object_or_404(CashShift, pk=pk)
            # Aislamiento por usuario: solo el cajero titular o supervisores (admin/operator) pueden cerrar
            if not verify_shift_ownership(request.user, shift):
                raise PermissionDenied("No tiene autorización para cerrar un turno de caja asignado a otro usuario.")
            return shift

        shift = CashShift.objects.filter(cashier=request.user, status=ShiftStatus.OPEN).first()
        if not shift:
            raise Http404("No se encontró ningún turno abierto para cerrar.")
        return shift

    def get(self, request: HttpRequest, pk: Optional[int] = None, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            shift = self.get_shift(request, pk)
        except Http404:
            messages.warning(request, "No posee ningún turno abierto pendiente de cierre.")
            return redirect('cash:dashboard')

        if not shift.is_open:
            messages.info(request, f"El turno {shift.shift_number} ya se encuentra cerrado.")
            return redirect('cash:shift_detail', pk=shift.pk)

        form = BlindReconciliationForm(shift=shift)
        return render(request, self.template_name, {
            'form': form,
            'shift': shift,
            'reconciliation_currencies': form.reconciliation_currencies,
        })

    def post(self, request: HttpRequest, pk: Optional[int] = None, *args: Any, **kwargs: Any) -> HttpResponse:
        shift = self.get_shift(request, pk)
        if not shift.is_open:
            messages.warning(request, "Este turno ya se encuentra cerrado.")
            return redirect('cash:shift_detail', pk=shift.pk)

        form = BlindReconciliationForm(shift, request.POST)
        if form.is_valid():
            try:
                closed_shift = form.save(closed_by=request.user)

                if closed_shift.status == ShiftStatus.RECONCILED:
                    messages.success(
                        request,
                        f"¡Turno {closed_shift.shift_number} cuadrado y cerrado con éxito! Sin diferencias de arqueo."
                    )
                else:
                    messages.warning(
                        request,
                        f"El turno {closed_shift.shift_number} fue cerrado con diferencias en el arqueo físico. "
                        f"Revise el acta correspondiente."
                    )

                return redirect('cash:shift_receipt', pk=closed_shift.pk)
            except ValidationError as err:
                messages.error(request, str(err))
            except CashError as err:
                messages.error(request, str(err))
            except Exception as exc:
                logger.exception("Error al cerrar turno con arqueo ciego: %s", exc)
                messages.error(request, "Ocurrió un error al procesar el arqueo de caja.")

        return render(request, self.template_name, {
            'form': form,
            'shift': shift,
            'reconciliation_currencies': form.reconciliation_currencies,
        })


class CashShiftDetailView(CashBaseMixin, DetailView):
    """
    Ficha técnica y acta completa de arqueo y cierre del turno con aislamiento por usuario (SCRUM-116).
    """

    model = CashShift
    template_name = 'cash/shift_detail.html'
    context_object_name = 'shift'

    def get_object(self, queryset=None) -> CashShift:
        shift = super().get_object(queryset=queryset)
        if not verify_shift_ownership(self.request.user, shift):
            raise PermissionDenied("No tiene autorización para visualizar los detalles de un turno asignado a otro cajero.")
        return shift

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        shift: CashShift = self.object
        summary = CashService.get_shift_summary(shift)
        movements = shift.movements.select_related('currency', 'cashier', 'transaction').order_by('created_at')

        context['summary'] = summary
        context['currencies_summary'] = summary['currencies']
        context['movements'] = movements
        context['is_closed'] = not shift.is_open
        return context


class CashShiftReceiptView(CashShiftDetailView):
    """
    Vista imprimible del acta de arqueo y comprobante de cierre de caja.
    """

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['is_printable_receipt'] = True
        return context


class CashShiftListView(CashBaseMixin, ListView):
    """
    Historial y auditoría de turnos de caja de la plataforma.
    """

    model = CashShift
    template_name = 'cash/shift_list.html'
    context_object_name = 'shifts'
    paginate_by = 15

    def get_queryset(self):
        qs = CashShift.objects.select_related('cash_register', 'cashier', 'closed_by').order_by('-opened_at')
        status = self.request.GET.get('status')
        register_id = self.request.GET.get('register')

        if status:
            qs = qs.filter(status=status)
        if register_id:
            qs = qs.filter(cash_register_id=register_id)

        # Aislamiento por usuario: si el usuario no es admin ni operador, solo ve sus propios turnos
        user = self.request.user
        if not has_role(user, "admin,operator"):
            qs = qs.filter(cashier=user)

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['registers'] = CashRegister.objects.filter(is_active=True).order_by('register_code')
        context['status_choices'] = ShiftStatus.choices
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_register'] = self.request.GET.get('register', '')
        return context


class CashRegisterListView(CashBaseMixin, ListView):
    """
    Panel de visualización del estado físico de las cajas y ventanillas de la sucursal.
    """

    model = CashRegister
    template_name = 'cash/register_list.html'
    context_object_name = 'registers'

    def get_queryset(self):
        return CashRegister.objects.select_related('current_cashier').order_by('branch_name', 'register_code')


class CashShiftStatusApiView(CashBaseMixin, View):
    """
    Endpoint JSON que retorna el estado y saldos en vivo de un turno de caja.
    """

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> JsonResponse:
        shift = get_object_or_404(CashShift, pk=pk)
        if not verify_shift_ownership(request.user, shift):
            raise PermissionDenied("No tiene autorización para consultar saldos de un turno ajeno.")
        summary = CashService.get_shift_summary(shift)
        return JsonResponse({
            'success': True,
            'shift_number': shift.shift_number,
            'status': shift.status,
            'is_open': shift.is_open,
            'opened_at': shift.opened_at.isoformat(),
            'closed_at': shift.closed_at.isoformat() if shift.closed_at else None,
            'summary': summary,
        })

