"""
Capa de servicios de dominio para el Inventario de Billetes por Denominación (apps.cash.inventory_services).

Orquesta la lógica de negocio del módulo SCRUM-116:
- Apertura de turno con dotación de bóveda a caja por denominación.
- Registro de operaciones cambiarias con actualización de stock físico.
- Declaración de arqueo físico por el cajero.
- Revisión y aprobación/rechazo del arqueo por el Administrador.
- Consultas de estado de inventario en bóveda y caja.

Reglas de negocio garantizadas:
- Ningún saldo de denominación puede quedar negativo (PositiveIntegerField + select_for_update).
- Toda apertura y cierre es atómica (django.db.transaction.atomic).
- Los movimientos BanknoteMovement son inmutables (solo se crean, nunca se editan ni eliminan).
- Solo se asigna inventario de divisas con tasa de cambio activa.
"""

from __future__ import annotations

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import models, transaction as db_transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ==============================================================================
# Excepciones de dominio — Inventario de Billetes
# ==============================================================================


class InventoryError(Exception):
    """Excepción base para fallas en el módulo de inventario de billetes."""
    pass


class InsufficientVaultStockError(InventoryError):
    """
    Lanzada cuando la bóveda no tiene stock suficiente para cubrir la dotación solicitada
    y la configuración no permite apertura parcial.
    """
    def __init__(self, denomination: Any, requested: int, available: int) -> None:
        self.denomination = denomination
        self.requested = requested
        self.available = available
        super().__init__(
            f"Stock insuficiente en bóveda para {denomination}: "
            f"solicitado={requested}, disponible={available}."
        )


class InsufficientRegisterStockError(InventoryError):
    """
    Lanzada cuando la caja no cuenta con billetes suficientes de una denominación
    para completar la entrega a un cliente en una operación cambiaria.
    """
    def __init__(self, denomination: Any, requested: int, available: int) -> None:
        self.denomination = denomination
        self.requested = requested
        self.available = available
        super().__init__(
            f"Stock insuficiente en caja para {denomination}: "
            f"solicitado={requested}, disponible={available}."
        )


class InvalidShiftStateError(InventoryError):
    """
    Lanzada cuando se intenta una operación de inventario sobre un turno que no
    se encuentra en el estado requerido para esa operación.
    """
    def __init__(self, shift: Any, expected_state: str, actual_state: str) -> None:
        self.shift = shift
        self.expected_state = expected_state
        self.actual_state = actual_state
        super().__init__(
            f"Turno {shift.shift_number} en estado '{actual_state}'; "
            f"se esperaba '{expected_state}'."
        )


# ==============================================================================
# Servicio principal de inventario
# ==============================================================================


class InventoryService:
    """
    Servicio de dominio para la gestión del inventario físico de billetes por denominación.

    Todos los métodos de escritura son atómicos. Los métodos de consulta son de solo lectura
    y no modifican ningún estado de la base de datos.
    """

    # --------------------------------------------------------------------------
    # 1. Apertura de turno — Dotación de billetes bóveda → caja
    # --------------------------------------------------------------------------

    @classmethod
    @db_transaction.atomic
    def open_shift_inventory(
        cls,
        shift: Any,
        vault: Any,
        performed_by: Any,
        keycloak_id: str = '',
    ) -> Tuple[List[Any], List[str]]:
        """
        Transfiere la dotación inicial de billetes desde la bóveda a la caja al abrir el turno.

        Solo transfiere denominaciones de divisas que tengan al menos una tasa de cambio activa.
        Crea un registro ``ShiftDenominationCount`` por cada denominación asignada.
        Registra un ``BanknoteMovement`` de tipo ``SHIFT_OPENING`` por denominación.

        :param shift: Instancia de ``CashShift`` en estado OPEN (recién creado).
        :param vault: Instancia de ``Vault`` activa desde donde se extrae la dotación.
        :param performed_by: Instancia del usuario que ejecuta la operación (cajero o admin).
        :param keycloak_id: Identificador Keycloak del usuario responsable.
        :returns: Tupla ``(denomination_counts, warnings)`` donde ``denomination_counts`` es la
                  lista de ``ShiftDenominationCount`` creados y ``warnings`` es una lista de
                  mensajes de advertencia por dotación parcial.
        :raises InsufficientVaultStockError: Si la bóveda no tiene stock suficiente y la
                                             configuración no permite apertura parcial.
        :raises InvalidShiftStateError: Si el turno no está en estado OPEN.
        """
        from .models import CashRegister, CashShift, ShiftStatus
        from .inventory_models import (
            BanknoteInventory,
            BanknoteMovement,
            BanknoteMovementType,
            CurrencyDenomination,
            InitialFloatConfig,
            LocationType,
            ShiftDenominationCount,
        )
        from rates.models import Currency, ExchangeRate

        # Validar estado del turno
        if shift.status != ShiftStatus.OPEN:
            raise InvalidShiftStateError(shift, ShiftStatus.OPEN, shift.status)

        # Obtener divisas con tasa de cambio activa
        active_currency_codes = set(
            ExchangeRate.objects.filter(is_active=True).values_list(
                'base_currency__code', flat=True
            )
        ) | set(
            ExchangeRate.objects.filter(is_active=True).values_list(
                'target_currency__code', flat=True
            )
        )

        if not active_currency_codes:
            logger.warning(
                "Apertura de turno %s: No hay tasas de cambio activas. "
                "No se asignará inventario de denominaciones.",
                shift.shift_number,
            )
            return [], ["No hay tasas de cambio activas. No se asignó inventario de billetes."]

        # Obtener denominaciones activas para esas divisas
        active_denominations = CurrencyDenomination.objects.filter(
            currency__code__in=active_currency_codes,
            is_active=True,
        ).select_related('currency').order_by('currency__code', '-value')

        warnings: List[str] = []
        denomination_counts: List[ShiftDenominationCount] = []

        for denomination in active_denominations:
            # Buscar configuración de dotación inicial
            config = InitialFloatConfig.objects.filter(
                denomination=denomination,
                currency=denomination.currency,
                is_active=True,
            ).first()

            if not config:
                # Sin configuración: saltar denominación silenciosamente
                logger.debug(
                    "Sin InitialFloatConfig para %s — denominación omitida en apertura.",
                    denomination,
                )
                continue

            requested_qty = config.default_quantity
            if requested_qty <= 0:
                continue

            # Bloquear el registro de inventario en bóveda (select_for_update evita race conditions)
            vault_inv = (
                BanknoteInventory.objects
                .select_for_update()
                .filter(
                    location_type=LocationType.VAULT,
                    vault=vault,
                    denomination=denomination,
                    currency=denomination.currency,
                )
                .first()
            )

            available_qty = vault_inv.quantity if vault_inv else 0

            if available_qty == 0:
                # Sin stock en bóveda
                if not config.allow_partial_fill:
                    raise InsufficientVaultStockError(denomination, requested_qty, 0)
                msg = (
                    f"Sin stock en bóveda para {denomination} — denominación omitida en apertura."
                )
                warnings.append(msg)
                logger.warning(msg)
                continue

            # Determinar cantidad a transferir
            transfer_qty = min(requested_qty, available_qty)
            if transfer_qty < requested_qty:
                if not config.allow_partial_fill:
                    raise InsufficientVaultStockError(denomination, requested_qty, available_qty)
                msg = (
                    f"Dotación parcial para {denomination}: solicitado={requested_qty}, "
                    f"transferido={transfer_qty} (stock disponible en bóveda insuficiente)."
                )
                warnings.append(msg)
                logger.warning(msg)

            # 1. Descontar de bóveda
            vault_inv.quantity -= transfer_qty
            vault_inv.save(update_fields=['quantity', 'updated_at'])

            # 2. Acreditar en caja (crear o actualizar)
            register_inv, _ = BanknoteInventory.objects.select_for_update().get_or_create(
                location_type=LocationType.REGISTER,
                cash_register=shift.cash_register,
                denomination=denomination,
                currency=denomination.currency,
                defaults={'quantity': 0},
            )
            register_inv.quantity += transfer_qty
            register_inv.save(update_fields=['quantity', 'updated_at'])

            # 3. Crear BanknoteMovement inmutable
            BanknoteMovement.objects.create(
                movement_type=BanknoteMovementType.SHIFT_OPENING,
                user=performed_by,
                keycloak_user_id=keycloak_id,
                shift=shift,
                currency=denomination.currency,
                denomination=denomination,
                quantity=transfer_qty,
                source_location_type=LocationType.VAULT,
                source_vault=vault,
                target_location_type=LocationType.REGISTER,
                target_register=shift.cash_register,
                resulting_source_qty=vault_inv.quantity,
                resulting_target_qty=register_inv.quantity,
                reference=f"Apertura turno {shift.shift_number}",
            )

            # 4. Crear ShiftDenominationCount (control por turno)
            count_record = ShiftDenominationCount.objects.create(
                shift=shift,
                currency=denomination.currency,
                denomination=denomination,
                opening_quantity=transfer_qty,
                system_expected_quantity=transfer_qty,
            )
            denomination_counts.append(count_record)

        logger.info(
            "Apertura inventario turno %s: %d denominaciones asignadas, %d advertencias.",
            shift.shift_number,
            len(denomination_counts),
            len(warnings),
        )
        return denomination_counts, warnings

    # --------------------------------------------------------------------------
    # 2. Registro de operación cambiaria — Actualización de stock en caja
    # --------------------------------------------------------------------------

    @classmethod
    @db_transaction.atomic
    def register_exchange_operation(
        cls,
        shift: Any,
        currency_in: Any,
        denomination_in_amounts: Dict[int, int],
        currency_out: Any,
        denomination_out_amounts: Dict[int, int],
        performed_by: Any,
        transaction: Optional[Any] = None,
        keycloak_id: str = '',
    ) -> None:
        """
        Actualiza el inventario de la caja por una operación de cambio de divisas.

        Los billetes del cliente (``denomination_in_amounts``) entran a la caja;
        los billetes entregados al cliente (``denomination_out_amounts``) salen de la caja.
        Valida stock disponible antes de confirmar cualquier movimiento.

        :param shift: Turno activo.
        :param currency_in: Divisa recibida del cliente.
        :param denomination_in_amounts: ``{denomination_id: cantidad_billetes}`` recibidos.
        :param currency_out: Divisa entregada al cliente.
        :param denomination_out_amounts: ``{denomination_id: cantidad_billetes}`` entregados.
        :param performed_by: Usuario cajero.
        :param transaction: Instancia de ``Transaction`` opcional, para trazabilidad.
        :param keycloak_id: Identificador Keycloak del usuario.
        :raises InvalidShiftStateError: Si el turno no está OPEN.
        :raises InsufficientRegisterStockError: Si la caja no tiene stock para alguna denominación OUT.
        """
        from .models import ShiftStatus
        from .inventory_models import (
            BanknoteInventory,
            BanknoteMovement,
            BanknoteMovementType,
            CurrencyDenomination,
            LocationType,
            ShiftDenominationCount,
        )

        if shift.status != ShiftStatus.OPEN:
            raise InvalidShiftStateError(shift, ShiftStatus.OPEN, shift.status)

        # --- Validar stock ANTES de modificar nada ---
        for denom_id, qty_out in denomination_out_amounts.items():
            if qty_out <= 0:
                continue
            denomination = CurrencyDenomination.objects.get(pk=denom_id)
            inv = BanknoteInventory.objects.filter(
                location_type=LocationType.REGISTER,
                cash_register=shift.cash_register,
                denomination=denomination,
                currency=currency_out,
            ).first()
            available = inv.quantity if inv else 0
            if available < qty_out:
                raise InsufficientRegisterStockError(denomination, qty_out, available)

        # --- Procesar ENTRADAS (cliente → caja) ---
        for denom_id, qty_in in denomination_in_amounts.items():
            if qty_in <= 0:
                continue
            denomination = CurrencyDenomination.objects.get(pk=denom_id)
            inv, _ = BanknoteInventory.objects.select_for_update().get_or_create(
                location_type=LocationType.REGISTER,
                cash_register=shift.cash_register,
                denomination=denomination,
                currency=currency_in,
                defaults={'quantity': 0},
            )
            inv.quantity += qty_in
            inv.save(update_fields=['quantity', 'updated_at'])

            BanknoteMovement.objects.create(
                movement_type=BanknoteMovementType.EXCHANGE_IN,
                user=performed_by,
                keycloak_user_id=keycloak_id,
                shift=shift,
                transaction=transaction,
                currency=currency_in,
                denomination=denomination,
                quantity=qty_in,
                source_location_type=LocationType.EXTERNAL,
                target_location_type=LocationType.REGISTER,
                target_register=shift.cash_register,
                resulting_source_qty=None,
                resulting_target_qty=inv.quantity,
                reference=f"Entrada operación tx={getattr(transaction, 'id', 'N/A')}",
            )

            # Actualizar ShiftDenominationCount
            count = ShiftDenominationCount.objects.filter(
                shift=shift, denomination=denomination
            ).first()
            if count:
                count.operations_in += qty_in
                count.calculate_expected()
                count.save(update_fields=['operations_in', 'system_expected_quantity'])

        # --- Procesar SALIDAS (caja → cliente) ---
        for denom_id, qty_out in denomination_out_amounts.items():
            if qty_out <= 0:
                continue
            denomination = CurrencyDenomination.objects.get(pk=denom_id)
            inv = (
                BanknoteInventory.objects
                .select_for_update()
                .get(
                    location_type=LocationType.REGISTER,
                    cash_register=shift.cash_register,
                    denomination=denomination,
                    currency=currency_out,
                )
            )
            inv.quantity -= qty_out
            inv.save(update_fields=['quantity', 'updated_at'])

            BanknoteMovement.objects.create(
                movement_type=BanknoteMovementType.EXCHANGE_OUT,
                user=performed_by,
                keycloak_user_id=keycloak_id,
                shift=shift,
                transaction=transaction,
                currency=currency_out,
                denomination=denomination,
                quantity=qty_out,
                source_location_type=LocationType.REGISTER,
                source_register=shift.cash_register,
                target_location_type=LocationType.EXTERNAL,
                resulting_source_qty=inv.quantity,
                resulting_target_qty=None,
                reference=f"Salida operación tx={getattr(transaction, 'id', 'N/A')}",
            )

            # Actualizar ShiftDenominationCount
            count = ShiftDenominationCount.objects.filter(
                shift=shift, denomination=denomination
            ).first()
            if count:
                count.operations_out += qty_out
                count.calculate_expected()
                count.save(update_fields=['operations_out', 'system_expected_quantity'])

        logger.info(
            "Operación cambiaria registrada en turno %s: %d entradas, %d salidas.",
            shift.shift_number,
            len(denomination_in_amounts),
            len(denomination_out_amounts),
        )

    # --------------------------------------------------------------------------
    # 3. Declaración de arqueo — Cajero ingresa conteo físico
    # --------------------------------------------------------------------------

    @classmethod
    @db_transaction.atomic
    def submit_cashier_count(
        cls,
        shift: Any,
        denomination_counts: Dict[int, int],
        performed_by: Any,
    ) -> None:
        """
        El cajero declara el conteo físico de billetes por denominación para cerrar el turno.

        Actualiza cada ``ShiftDenominationCount``, calcula diferencias y pone el turno y
        la caja en estado ``PENDING_REVIEW`` / ``PENDING_CONTROL`` respectivamente.
        No transfiere inventario a bóveda (eso ocurre solo al aprobar el admin).

        :param shift: Turno activo (debe estar en estado OPEN).
        :param denomination_counts: ``{denomination_id: cantidad_contada}`` declarado por el cajero.
        :param performed_by: Usuario cajero que declara el arqueo.
        :raises InvalidShiftStateError: Si el turno no está en estado OPEN (protege anti-doble-cierre).
        """
        from .models import CashRegister, CashRegisterStatus, CashShift, ShiftStatus
        from .inventory_models import ShiftDenominationCount

        if shift.status != ShiftStatus.OPEN:
            raise InvalidShiftStateError(shift, ShiftStatus.OPEN, shift.status)

        # Actualizar cada ShiftDenominationCount con el conteo físico
        for denom_id, counted_qty in denomination_counts.items():
            count = ShiftDenominationCount.objects.filter(
                shift=shift,
                denomination_id=denom_id,
            ).first()
            if not count:
                logger.warning(
                    "ShiftDenominationCount no encontrado para denominación %s en turno %s — omitido.",
                    denom_id,
                    shift.shift_number,
                )
                continue
            count.update_reconciliation(max(0, int(counted_qty)))
            count.save(update_fields=[
                'counted_quantity',
                'system_expected_quantity',
                'difference_quantity',
                'difference_amount',
            ])

        # Cambiar estado del turno y de la caja
        shift.status = ShiftStatus.PENDING_REVIEW
        shift.save(update_fields=['status'])

        register = shift.cash_register
        register.status = CashRegisterStatus.PENDING_CONTROL
        register.save(update_fields=['status', 'updated_at'])

        logger.info(
            "Cajero %s declaró arqueo físico del turno %s — estado: PENDING_REVIEW.",
            performed_by.username,
            shift.shift_number,
        )

    # --------------------------------------------------------------------------
    # 4. Aprobación / Rechazo de arqueo — Acción del Administrador
    # --------------------------------------------------------------------------

    @classmethod
    @db_transaction.atomic
    def approve_reconciliation(
        cls,
        shift: Any,
        action: str,
        admin_user: Any,
        adjusted_counts: Optional[Dict[int, int]] = None,
        notes: str = '',
    ) -> None:
        """
        El Administrador aprueba, rechaza o ajusta el arqueo de un turno.

        - ``APPROVE``: Acepta el conteo del cajero. Transfiere inventario caja → bóveda.
          Shift → RECONCILED / DISCREPANCY según diferencias. Caja → CLOSED.
        - ``REJECT``: Devuelve el turno a OPEN para reconteo. No transfiere inventario.
          Resetea ``counted_quantity`` en todos los ``ShiftDenominationCount``.
        - ``APPROVE_WITH_ADJUSTMENT``: Usa ``adjusted_counts`` (obligatorio) y ``notes``
          (obligatorio). Transfiere las cantidades ajustadas. Shift → DISCREPANCY.

        :param shift: Turno en estado PENDING_REVIEW.
        :param action: Valor de ``ReconciliationAction`` (APPROVE, REJECT, APPROVE_WITH_ADJUSTMENT).
        :param admin_user: Usuario administrador.
        :param adjusted_counts: ``{denomination_id: cantidad_ajustada}`` solo para APPROVE_WITH_ADJUSTMENT.
        :param notes: Motivo/justificación del admin. **Obligatorio** si es APPROVE_WITH_ADJUSTMENT.
        :raises InvalidShiftStateError: Si el turno no está en PENDING_REVIEW.
        :raises ValidationError: Si APPROVE_WITH_ADJUSTMENT se usa sin ``notes``.
        """
        from .models import CashRegister, CashRegisterStatus, CashShift, ShiftStatus
        from .inventory_models import (
            BanknoteInventory,
            BanknoteMovement,
            BanknoteMovementType,
            LocationType,
            ReconciliationAction,
            ShiftDenominationCount,
            Vault,
        )

        if shift.status != ShiftStatus.PENDING_REVIEW:
            raise InvalidShiftStateError(shift, ShiftStatus.PENDING_REVIEW, shift.status)

        if action == ReconciliationAction.APPROVE_WITH_ADJUSTMENT:
            if not notes or not notes.strip():
                raise ValidationError(
                    "El campo 'notas' es obligatorio al aprobar con ajuste. "
                    "Indique el motivo del ajuste para el registro de auditoría."
                )
            if not adjusted_counts:
                raise ValidationError(
                    "Debe proporcionar 'adjusted_counts' al aprobar con ajuste."
                )

        if action == ReconciliationAction.REJECT:
            cls._reject_reconciliation(shift)
            return

        # APPROVE o APPROVE_WITH_ADJUSTMENT → transferir a bóveda
        cls._approve_and_transfer(
            shift=shift,
            action=action,
            admin_user=admin_user,
            adjusted_counts=adjusted_counts or {},
            notes=notes,
        )

    @classmethod
    def _reject_reconciliation(cls, shift: Any) -> None:
        """Restablece el turno y la caja a OPEN para un nuevo reconteo del cajero."""
        from .models import CashRegisterStatus, ShiftStatus
        from .inventory_models import ShiftDenominationCount

        # Resetear conteos del cajero
        ShiftDenominationCount.objects.filter(shift=shift).update(
            counted_quantity=None,
            difference_quantity=0,
            difference_amount=Decimal('0.00'),
        )

        # Volver turno y caja a OPEN
        shift.status = ShiftStatus.OPEN
        shift.save(update_fields=['status'])

        register = shift.cash_register
        register.status = CashRegisterStatus.OPEN
        register.save(update_fields=['status', 'updated_at'])

        logger.info(
            "Arqueo del turno %s RECHAZADO por admin. Turno y caja vuelven a OPEN.",
            shift.shift_number,
        )

    @classmethod
    def _approve_and_transfer(
        cls,
        shift: Any,
        action: str,
        admin_user: Any,
        adjusted_counts: Dict[int, int],
        notes: str,
    ) -> None:
        """
        Transfiere el inventario de la caja a la bóveda y cierra el turno.
        Se invoca para APPROVE y APPROVE_WITH_ADJUSTMENT.
        """
        from .models import CashRegisterStatus, ShiftStatus
        from .inventory_models import (
            BanknoteInventory,
            BanknoteMovement,
            BanknoteMovementType,
            LocationType,
            ReconciliationAction,
            ShiftDenominationCount,
            Vault,
        )

        # Obtener bóveda activa (primera activa — en producción usar la bóveda de la sucursal)
        vault = Vault.objects.filter(is_active=True).first()
        if not vault:
            raise ValidationError("No hay bóveda activa para recibir el inventario de cierre.")

        has_discrepancy = False
        counts = ShiftDenominationCount.objects.filter(shift=shift).select_related(
            'denomination', 'currency'
        )

        for count in counts:
            # Determinar cantidad a transferir
            if action == ReconciliationAction.APPROVE_WITH_ADJUSTMENT:
                transfer_qty = adjusted_counts.get(count.denomination_id, count.counted_quantity or 0)
                count.admin_adjusted_quantity = transfer_qty
                count.admin_notes = notes
                count.save(update_fields=['admin_adjusted_quantity', 'admin_notes'])
            else:
                transfer_qty = count.counted_quantity or 0

            # Si hay diferencia, marcar discrepancia
            if count.difference_quantity != 0:
                has_discrepancy = True

            if transfer_qty <= 0:
                continue

            # Descontar de caja
            register_inv = (
                BanknoteInventory.objects
                .select_for_update()
                .filter(
                    location_type=LocationType.REGISTER,
                    cash_register=shift.cash_register,
                    denomination=count.denomination,
                    currency=count.currency,
                )
                .first()
            )
            if register_inv:
                # Transferir la cantidad aprobada (no más de lo disponible en la caja)
                actual_transfer = min(transfer_qty, register_inv.quantity)
                register_inv.quantity -= actual_transfer
                register_inv.save(update_fields=['quantity', 'updated_at'])
            else:
                actual_transfer = 0

            # Acreditar en bóveda
            vault_inv, _ = BanknoteInventory.objects.select_for_update().get_or_create(
                location_type=LocationType.VAULT,
                vault=vault,
                denomination=count.denomination,
                currency=count.currency,
                defaults={'quantity': 0},
            )
            vault_inv.quantity += actual_transfer
            vault_inv.save(update_fields=['quantity', 'updated_at'])

            # Registrar movimiento inmutable
            BanknoteMovement.objects.create(
                movement_type=BanknoteMovementType.SHIFT_CLOSING,
                user=admin_user,
                shift=shift,
                currency=count.currency,
                denomination=count.denomination,
                quantity=actual_transfer,
                source_location_type=LocationType.REGISTER,
                source_register=shift.cash_register,
                target_location_type=LocationType.VAULT,
                target_vault=vault,
                resulting_source_qty=register_inv.quantity if register_inv else 0,
                resulting_target_qty=vault_inv.quantity,
                reference=f"Cierre turno {shift.shift_number} — {action}",
            )

        # Actualizar estado del turno
        from .models import ShiftStatus
        if has_discrepancy or action == ReconciliationAction.APPROVE_WITH_ADJUSTMENT:
            shift.status = ShiftStatus.DISCREPANCY
        else:
            shift.status = ShiftStatus.RECONCILED
        shift.closed_at = timezone.now()
        shift.save(update_fields=['status', 'closed_at'])

        # Cerrar caja física
        register = shift.cash_register
        register.status = CashRegisterStatus.CLOSED
        register.save(update_fields=['status', 'updated_at'])

        logger.info(
            "Arqueo del turno %s APROBADO por %s — acción: %s, resultado: %s.",
            shift.shift_number,
            admin_user.username,
            action,
            shift.status,
        )

    # --------------------------------------------------------------------------
    # 5. Consultas de inventario
    # --------------------------------------------------------------------------

    @classmethod
    def get_register_stock_summary(cls, cash_register: Any) -> List[Dict[str, Any]]:
        """
        Retorna el resumen de stock actual por denominación en la caja indicada.

        :returns: Lista de dicts ``{denomination, currency_code, value, quantity, total_amount}``.
        """
        from .inventory_models import BanknoteInventory, LocationType

        entries = BanknoteInventory.objects.filter(
            location_type=LocationType.REGISTER,
            cash_register=cash_register,
            quantity__gt=0,
        ).select_related('denomination', 'currency').order_by('currency__code', '-denomination__value')

        return [
            {
                'denomination_id': inv.denomination_id,
                'denomination': str(inv.denomination),
                'currency_code': inv.currency.code,
                'value': inv.denomination.value,
                'quantity': inv.quantity,
                'total_amount': inv.total_amount,
            }
            for inv in entries
        ]

    @classmethod
    def get_vault_stock_summary(cls, vault: Any) -> List[Dict[str, Any]]:
        """
        Retorna el resumen de stock actual por denominación en la bóveda indicada.

        :returns: Lista de dicts ``{denomination, currency_code, value, quantity, total_amount}``.
        """
        from .inventory_models import BanknoteInventory, LocationType

        entries = BanknoteInventory.objects.filter(
            location_type=LocationType.VAULT,
            vault=vault,
        ).select_related('denomination', 'currency').order_by('currency__code', '-denomination__value')

        return [
            {
                'denomination_id': inv.denomination_id,
                'denomination': str(inv.denomination),
                'currency_code': inv.currency.code,
                'value': inv.denomination.value,
                'quantity': inv.quantity,
                'total_amount': inv.total_amount,
            }
            for inv in entries
        ]

    @classmethod
    @db_transaction.atomic
    def vault_deposit(
        cls,
        vault: Any,
        currency: Any,
        denomination: Any,
        quantity: int,
        performed_by: Any,
        notes: str = '',
    ) -> None:
        """
        Registra un ingreso externo de billetes a la bóveda (ej. reposición desde banco).

        :param vault: Bóveda destino.
        :param currency: Divisa de los billetes.
        :param denomination: Denominación específica del billete.
        :param quantity: Cantidad de billetes a ingresar (debe ser > 0).
        :param performed_by: Administrador que autoriza el ingreso.
        :param notes: Referencia o justificación del movimiento.
        :raises ValidationError: Si ``quantity <= 0``.
        """
        from .inventory_models import (
            BanknoteInventory,
            BanknoteMovement,
            BanknoteMovementType,
            LocationType,
        )

        if quantity <= 0:
            raise ValidationError("La cantidad a depositar debe ser mayor a cero.")

        inv, _ = BanknoteInventory.objects.select_for_update().get_or_create(
            location_type=LocationType.VAULT,
            vault=vault,
            denomination=denomination,
            currency=currency,
            defaults={'quantity': 0},
        )
        inv.quantity += quantity
        inv.save(update_fields=['quantity', 'updated_at'])

        BanknoteMovement.objects.create(
            movement_type=BanknoteMovementType.VAULT_DEPOSIT,
            user=performed_by,
            currency=currency,
            denomination=denomination,
            quantity=quantity,
            source_location_type=LocationType.EXTERNAL,
            target_location_type=LocationType.VAULT,
            target_vault=vault,
            resulting_source_qty=None,
            resulting_target_qty=inv.quantity,
            reference=notes or f"Depósito externo en {vault.code}",
        )

        logger.info(
            "Depósito en bóveda %s: %d x %s por %s.",
            vault.code,
            quantity,
            denomination,
            performed_by.username,
        )

