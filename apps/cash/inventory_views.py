"""
Vistas basadas en clases para el módulo de Inventario de Billetes por Denominación (SCRUM-116).

Gestiona la interfaz web para:
- Panel de bóvedas activas (admin).
- Ingreso manual de billetes a bóveda (admin).
- Consulta de inventario de caja por turno (cajero/operador).
- Declaración de arqueo físico por denominación — arqueo ciego (cajero).
- Listado y revisión de arqueos pendientes de conciliación (admin).
"""

import logging
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View

from authentication.permissions import (
    CashierRequiredMixin,
    has_role,
    verify_shift_ownership,
)
from rates.models import Currency
from .inventory_models import (
    CurrencyDenomination,
    ReconciliationAction,
    ShiftDenominationCount,
    Vault,
)
from .inventory_services import InventoryError, InventoryService
from .models import CashShift, ShiftStatus
from .views import CashBaseMixin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _require_admin(request: HttpRequest) -> None:
    """Lanza PermissionDenied si el usuario no tiene rol admin."""
    if not has_role(request.user, 'admin'):
        raise PermissionDenied("Se requiere rol de Administrador para acceder a esta sección.")


# ===========================================================================
# 1. VaultDashboardView — Panel de bóvedas (solo admin)
# ===========================================================================

class VaultDashboardView(LoginRequiredMixin, CashierRequiredMixin, View):
    """
    Muestra el inventario actual de todas las bóvedas activas agrupado
    por denominación y divisa. Acceso exclusivo para administradores.
    """

    template_name = 'cash/vault_dashboard.html'
    allowed_roles = ['admin']
    permission_denied_message = "Se requiere rol de Administrador para acceder al Panel de Bóveda."

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        _require_admin(request)
        vaults = Vault.objects.filter(is_active=True)

        vault_data = []
        for vault in vaults:
            stock = InventoryService.get_vault_stock_summary(vault)
            vault_data.append({
                'vault': vault,
                'stock': stock,
                'total_items': len(stock),
            })

        context: Dict[str, Any] = {
            'vault_data': vault_data,
            'page_title': '🏦 Panel de Bóveda Central',
        }
        return render(request, self.template_name, context)


# ===========================================================================
# 2. VaultDepositView — Ingreso de billetes a bóveda (solo admin)
# ===========================================================================

class VaultDepositView(LoginRequiredMixin, CashierRequiredMixin, View):
    """
    Permite al administrador registrar un ingreso externo de billetes a la bóveda.
    GET: Muestra formulario de selección de bóveda, divisa, denominación y cantidad.
    POST: Llama a InventoryService.vault_deposit() y redirige con mensaje de éxito.
    """

    template_name = 'cash/vault_deposit.html'
    allowed_roles = ['admin']
    permission_denied_message = "Se requiere rol de Administrador para registrar depósitos en bóveda."

    def _build_context(self) -> Dict[str, Any]:
        return {
            'vaults': Vault.objects.filter(is_active=True),
            'currencies': Currency.objects.filter(is_active=True).order_by('code'),
            'denominations': CurrencyDenomination.objects.filter(
                is_active=True
            ).select_related('currency').order_by('currency__code', '-value'),
            'page_title': '💰 Ingreso de Billetes a Bóveda',
        }

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        _require_admin(request)
        return render(request, self.template_name, self._build_context())

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        _require_admin(request)

        vault_id = request.POST.get('vault')
        denomination_id = request.POST.get('denomination')
        quantity_raw = request.POST.get('quantity', '').strip()
        notes = request.POST.get('notes', '').strip()

        # Validaciones básicas
        if not vault_id or not denomination_id or not quantity_raw:
            messages.error(request, "Por favor complete todos los campos obligatorios.")
            return render(request, self.template_name, self._build_context())

        try:
            quantity = int(quantity_raw)
            if quantity <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, "La cantidad debe ser un número entero positivo.")
            return render(request, self.template_name, self._build_context())

        vault = get_object_or_404(Vault, pk=vault_id, is_active=True)
        denomination = get_object_or_404(CurrencyDenomination, pk=denomination_id, is_active=True)
        currency = denomination.currency

        try:
            InventoryService.vault_deposit(
                vault=vault,
                currency=currency,
                denomination=denomination,
                quantity=quantity,
                performed_by=request.user,
                notes=notes,
            )
            messages.success(
                request,
                f"✅ Depósito registrado: {quantity} billete(s) de {denomination} "
                f"({currency.code}) ingresado(s) correctamente a {vault.name}.",
            )
            return redirect('cash:vault_dashboard')
        except (ValidationError, InventoryError) as exc:
            messages.error(request, f"Error al registrar depósito: {exc}")
            return render(request, self.template_name, self._build_context())


# ===========================================================================
# 3. ShiftInventoryView — Stock actual de la caja del turno (cajero/operador)
# ===========================================================================

class ShiftInventoryView(CashBaseMixin, View):
    """
    Muestra el inventario físico actual de billetes en la caja asignada al turno.
    Verifica que el usuario sea el titular del turno (o admin/operador).
    """

    template_name = 'cash/shift_inventory.html'

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        shift = get_object_or_404(CashShift, pk=pk)

        if not verify_shift_ownership(request.user, shift):
            raise PermissionDenied("No tiene autorización para consultar este turno.")

        stock = InventoryService.get_register_stock_summary(shift.cash_register)

        context: Dict[str, Any] = {
            'shift': shift,
            'stock': stock,
            'is_open': shift.status == ShiftStatus.OPEN,
            'page_title': f'📦 Inventario de Caja — Turno {shift.shift_number}',
        }
        return render(request, self.template_name, context)


# ===========================================================================
# 4. CashierDenominationCountView — Arqueo físico por denominación (cajero)
# ===========================================================================

class CashierDenominationCountView(CashBaseMixin, View):
    """
    Permite al cajero titular declarar el conteo físico de billetes por denominación
    al cierre del turno (arqueo ciego — sin mostrar los saldos teóricos).

    GET: Tabla de ShiftDenominationCount sin columna de saldo teórico.
    POST: Recolecta denom_{id} para cada denominación y llama submit_cashier_count().
    """

    template_name = 'cash/cashier_denomination_count.html'

    def _get_shift_and_check(self, request: HttpRequest, pk: int) -> CashShift:
        shift = get_object_or_404(CashShift, pk=pk)

        # Solo el cajero titular puede acceder (no admin ni operador)
        if shift.cashier != request.user:
            raise PermissionDenied("Solo el cajero titular del turno puede realizar el arqueo físico.")

        if shift.status != ShiftStatus.OPEN:
            messages.warning(
                request,
                "Este turno no está abierto. No se puede realizar el arqueo físico.",
            )
        return shift

    def _get_denomination_counts(self, shift: CashShift):
        """Retorna los ShiftDenominationCount agrupados por divisa."""
        counts = (
            ShiftDenominationCount.objects
            .filter(shift=shift)
            .select_related('currency', 'denomination')
            .order_by('currency__code', '-denomination__value')
        )
        # Agrupar por divisa
        grouped: Dict[str, Any] = {}
        for count in counts:
            code = count.currency.code
            if code not in grouped:
                grouped[code] = {
                    'currency': count.currency,
                    'counts': [],
                }
            grouped[code]['counts'].append(count)
        return list(grouped.values())

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        shift = self._get_shift_and_check(request, pk)
        grouped_counts = self._get_denomination_counts(shift)

        context: Dict[str, Any] = {
            'shift': shift,
            'grouped_counts': grouped_counts,
            'page_title': f'🔢 Arqueo Físico por Denominación — Arqueo Ciego',
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        shift = self._get_shift_and_check(request, pk)

        if shift.status != ShiftStatus.OPEN:
            messages.error(request, "El turno no está abierto. No se puede procesar el arqueo.")
            return redirect('cash:shift_detail', pk=shift.pk)

        # Recolectar conteo por denominación desde el POST
        denomination_counts: Dict[int, int] = {}
        counts_qs = ShiftDenominationCount.objects.filter(shift=shift)
        for count in counts_qs:
            field_name = f'denom_{count.denomination_id}'
            raw_value = request.POST.get(field_name, '0').strip()
            try:
                qty = max(0, int(raw_value))
            except (ValueError, TypeError):
                qty = 0
            denomination_counts[count.denomination_id] = qty

        try:
            InventoryService.submit_cashier_count(
                shift=shift,
                denomination_counts=denomination_counts,
                performed_by=request.user,
            )
            messages.success(
                request,
                "✅ Arqueo físico declarado correctamente. El turno queda pendiente de revisión por el Administrador.",
            )
        except Exception as exc:
            messages.error(request, f"Error al registrar el arqueo: {exc}")
            return redirect('cash:cashier_denomination_count', pk=shift.pk)

        return redirect('cash:shift_detail', pk=shift.pk)


# ===========================================================================
# 5. AdminReconciliationListView — Arqueos pendientes de revisión (solo admin)
# ===========================================================================

class AdminReconciliationListView(LoginRequiredMixin, CashierRequiredMixin, View):
    """
    Lista todos los turnos con status PENDING_REVIEW para que el administrador
    los revise y tome acción (aprobar, rechazar o aprobar con ajuste).
    """

    template_name = 'cash/admin_reconciliation_list.html'
    allowed_roles = ['admin']
    permission_denied_message = "Se requiere rol de Administrador para revisar arqueos."

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        _require_admin(request)
        pending_shifts = (
            CashShift.objects
            .filter(status=ShiftStatus.PENDING_REVIEW)
            .select_related('cashier', 'cash_register')
            .order_by('opened_at')
        )

        context: Dict[str, Any] = {
            'pending_shifts': pending_shifts,
            'page_title': '⚖️ Arqueos Pendientes de Revisión',
        }
        return render(request, self.template_name, context)


# ===========================================================================
# 6. AdminReconciliationActionView — Revisión y acción de arqueo (solo admin)
# ===========================================================================

class AdminReconciliationActionView(LoginRequiredMixin, CashierRequiredMixin, View):
    """
    Auditoría y resolución de arqueos por el administrador.

    Muestra detalle del arqueo y procesa la acción del admin.
    """

    template_name = 'cash/admin_reconciliation_detail.html'
    allowed_roles = ['admin']
    permission_denied_message = "Se requiere rol de Administrador para gestionar arqueos."

    def _get_shift(self, pk: int) -> CashShift:
        return get_object_or_404(
            CashShift.objects.select_related('cashier', 'cash_register'),
            pk=pk,
            status=ShiftStatus.PENDING_REVIEW,
        )

    def _get_counts_detail(self, shift: CashShift):
        """Retorna los ShiftDenominationCount con cálculo de diferencia para la vista."""
        counts = (
            ShiftDenominationCount.objects
            .filter(shift=shift)
            .select_related('currency', 'denomination')
            .order_by('currency__code', '-denomination__value')
        )
        return counts

    def get(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        _require_admin(request)
        shift = self._get_shift(pk)
        counts = self._get_counts_detail(shift)
        actions = ReconciliationAction.choices

        context: Dict[str, Any] = {
            'shift': shift,
            'counts': counts,
            'actions': actions,
            'APPROVE': ReconciliationAction.APPROVE,
            'REJECT': ReconciliationAction.REJECT,
            'APPROVE_WITH_ADJUSTMENT': ReconciliationAction.APPROVE_WITH_ADJUSTMENT,
            'page_title': f'🔍 Revisión de Arqueo — Turno {shift.shift_number}',
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        _require_admin(request)
        shift = self._get_shift(pk)

        action = request.POST.get('action', '').strip()
        notes = request.POST.get('notes', '').strip()

        # Validar acción
        valid_actions = [a[0] for a in ReconciliationAction.choices]
        if action not in valid_actions:
            messages.error(request, "Acción no válida. Seleccione APPROVE, REJECT o APPROVE_WITH_ADJUSTMENT.")
            return redirect('cash:admin_reconciliation_action', pk=pk)

        # Recolectar cantidades ajustadas si aplica
        adjusted_counts: Dict[int, int] = {}
        if action == ReconciliationAction.APPROVE_WITH_ADJUSTMENT:
            counts_qs = ShiftDenominationCount.objects.filter(shift=shift)
            for count in counts_qs:
                field_name = f'adjusted_{count.denomination_id}'
                raw_value = request.POST.get(field_name, '').strip()
                try:
                    qty = max(0, int(raw_value))
                except (ValueError, TypeError):
                    qty = count.counted_quantity or 0
                adjusted_counts[count.denomination_id] = qty

        try:
            InventoryService.approve_reconciliation(
                shift=shift,
                action=action,
                admin_user=request.user,
                adjusted_counts=adjusted_counts if adjusted_counts else None,
                notes=notes,
            )
            action_labels = {
                ReconciliationAction.APPROVE: "aprobado",
                ReconciliationAction.REJECT: "rechazado (devuelto para reconteo)",
                ReconciliationAction.APPROVE_WITH_ADJUSTMENT: "aprobado con ajuste",
            }
            label = action_labels.get(action, action)
            messages.success(
                request,
                f"✅ Arqueo del turno {shift.shift_number} {label} correctamente.",
            )
        except (ValidationError, InventoryError) as exc:
            messages.error(request, f"Error al procesar el arqueo: {exc}")
            return redirect('cash:admin_reconciliation_action', pk=pk)

        return redirect('cash:admin_reconciliation_list')
