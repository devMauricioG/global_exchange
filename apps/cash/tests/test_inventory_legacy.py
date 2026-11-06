"""
Tests para el módulo de Inventario de Billetes por Denominación (SCRUM-116).

Cubre:
- InventoryModelTests: Validaciones de modelos (inmutabilidad, no negativos, unique_together).
- InventoryServiceOpenTests: Apertura de turno con dotación bóveda → caja.
- InventoryServiceOperationTests: Registro de operaciones cambiarias.
- InventoryServiceReconciliationTests: Declaración y aprobación/rechazo de arqueo.
- InventoryServiceStockSummaryTests: Consultas de stock en caja y bóveda.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.cash.inventory_models import (
    BanknoteInventory,
    BanknoteMovement,
    BanknoteMovementType,
    CurrencyDenomination,
    InitialFloatConfig,
    LocationType,
    ReconciliationAction,
    ShiftDenominationCount,
    Vault,
)
from apps.cash.inventory_services import (
    InventoryService,
    InsufficientRegisterStockError,
    InsufficientVaultStockError,
    InvalidShiftStateError,
)
from apps.cash.models import (
    CashRegister,
    CashRegisterStatus,
    CashShift,
    ShiftStatus,
)
from rates.models import Currency, ExchangeRate


# ==============================================================================
# Helpers
# ==============================================================================

def _make_currency(code: str) -> Currency:
    """Crea o devuelve una Currency con los campos mínimos requeridos."""
    return Currency.objects.get_or_create(
        code=code,
        defaults={
            'name': f'Moneda {code}',
            'symbol': code[0],
            'decimals': 2,
            'is_active': True,
        },
    )[0]


def _make_exchange_rate(base: Currency, target: Currency) -> ExchangeRate:
    """Crea una ExchangeRate activa entre dos divisas."""
    return ExchangeRate.objects.create(
        base_currency=base,
        target_currency=target,
        buy_rate=Decimal('1.000000'),
        sell_rate=Decimal('1.050000'),
        is_active=True,
    )


# ==============================================================================
# Clase 1 — Validaciones de modelos
# ==============================================================================


class InventoryModelTests(TestCase):
    """Tests de validación directa de los modelos del módulo de inventario."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username='cajero_test', password='pass')
        self.usd = _make_currency('USD')
        self.brl = _make_currency('BRL')

        self.usd100 = CurrencyDenomination.objects.create(
            currency=self.usd, value=Decimal('100'), is_active=True
        )
        self.usd50 = CurrencyDenomination.objects.create(
            currency=self.usd, value=Decimal('50'), is_active=True
        )
        self.brl50 = CurrencyDenomination.objects.create(
            currency=self.brl, value=Decimal('50'), is_active=True
        )

        self.vault = Vault.objects.create(
            code='BOVEDA-01',
            name='Bóveda Central',
            is_active=True,
        )

    # ------------------------------------------------------------------
    # 1. unique_together en CurrencyDenomination
    # ------------------------------------------------------------------

    def test_currency_denomination_unique_together(self) -> None:
        """Crear dos denominaciones USD-100 debe lanzar IntegrityError."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CurrencyDenomination.objects.create(
                    currency=self.usd, value=Decimal('100'), is_active=True
                )

    # ------------------------------------------------------------------
    # 2. BanknoteInventory no admite quantity negativa
    # ------------------------------------------------------------------

    def test_banknote_inventory_no_negative(self) -> None:
        """clean() debe lanzar ValidationError si quantity < 0."""
        inv = BanknoteInventory(
            location_type=LocationType.VAULT,
            vault=self.vault,
            currency=self.usd,
            denomination=self.usd100,
            quantity=-1,
        )
        with self.assertRaises(ValidationError):
            inv.clean()

    # ------------------------------------------------------------------
    # 3 & 4. BanknoteMovement es inmutable (save y delete protegidos)
    # ------------------------------------------------------------------

    def _create_register(self) -> CashRegister:
        return CashRegister.objects.create(
            register_code='CAJA-IMM-01',
            name='Caja Inmutabilidad',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )

    def _create_shift(self, register: CashRegister) -> CashShift:
        return CashShift.objects.create(
            cash_register=register,
            cashier=self.user,
            shift_number='SHIFT-IMM-001',
            status=ShiftStatus.OPEN,
        )

    def test_banknote_movement_immutable_save(self) -> None:
        """Intentar save() en un BanknoteMovement ya persistido debe lanzar ValidationError."""
        register = self._create_register()
        shift = self._create_shift(register)

        # Crear movimiento válido
        mov = BanknoteMovement.objects.create(
            movement_type=BanknoteMovementType.SHIFT_OPENING,
            user=self.user,
            shift=shift,
            currency=self.usd,
            denomination=self.usd100,
            quantity=5,
            source_location_type=LocationType.VAULT,
            source_vault=self.vault,
            target_location_type=LocationType.REGISTER,
            target_register=register,
        )

        # Intentar re-guardar (mutación) debe fallar
        with self.assertRaises(ValidationError):
            mov.save()

    def test_banknote_movement_immutable_delete(self) -> None:
        """Intentar delete() en un BanknoteMovement debe lanzar ValidationError."""
        register = self._create_register()
        shift = self._create_shift(register)

        mov = BanknoteMovement.objects.create(
            movement_type=BanknoteMovementType.SHIFT_OPENING,
            user=self.user,
            shift=shift,
            currency=self.usd,
            denomination=self.usd100,
            quantity=5,
            source_location_type=LocationType.VAULT,
            source_vault=self.vault,
            target_location_type=LocationType.REGISTER,
            target_register=register,
        )

        with self.assertRaises(ValidationError):
            mov.delete()

    # ------------------------------------------------------------------
    # 5. ShiftDenominationCount.calculate_expected
    # ------------------------------------------------------------------

    def test_shift_denomination_count_calculate_expected(self) -> None:
        """calculate_expected con opening=10, ops_in=5, ops_out=3 debe retornar 12."""
        register = CashRegister.objects.create(
            register_code='CAJA-CALC-01',
            name='Caja Cálculo',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )
        shift = CashShift.objects.create(
            cash_register=register,
            cashier=self.user,
            shift_number='SHIFT-CALC-001',
            status=ShiftStatus.OPEN,
        )
        count = ShiftDenominationCount(
            shift=shift,
            currency=self.usd,
            denomination=self.usd100,
            opening_quantity=10,
            operations_in=5,
            operations_out=3,
        )
        result = count.calculate_expected()
        self.assertEqual(result, 12)

    # ------------------------------------------------------------------
    # 6. ShiftDenominationCount.update_reconciliation
    # ------------------------------------------------------------------

    def test_shift_denomination_count_update_reconciliation(self) -> None:
        """update_reconciliation(10) con expected=12 (USD-100) → diff_qty=-2, diff_amount=-200."""
        register = CashRegister.objects.create(
            register_code='CAJA-REC-01',
            name='Caja Reconciliación',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )
        shift = CashShift.objects.create(
            cash_register=register,
            cashier=self.user,
            shift_number='SHIFT-REC-001',
            status=ShiftStatus.OPEN,
        )
        count = ShiftDenominationCount(
            shift=shift,
            currency=self.usd,
            denomination=self.usd100,
            opening_quantity=10,
            operations_in=5,
            operations_out=3,  # expected = 12
        )
        count.update_reconciliation(10)
        self.assertEqual(count.difference_quantity, -2)
        self.assertEqual(count.difference_amount, Decimal('-200'))


# ==============================================================================
# Clase 2 — Apertura de turno (InventoryService.open_shift_inventory)
# ==============================================================================


class InventoryServiceOpenTests(TestCase):
    """Tests del servicio de apertura de turno con dotación bóveda → caja."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username='cajero_test', password='pass')
        self.usd = _make_currency('USD')
        self.brl = _make_currency('BRL')

        self.usd100 = CurrencyDenomination.objects.create(
            currency=self.usd, value=Decimal('100'), is_active=True
        )

        self.vault = Vault.objects.create(
            code='BOVEDA-01',
            name='Bóveda Central',
            is_active=True,
        )

        self.register = CashRegister.objects.create(
            register_code='CAJA-TEST-01',
            name='Caja Test',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )
        self.shift = CashShift.objects.create(
            cash_register=self.register,
            cashier=self.user,
            shift_number='SHIFT-TEST-001',
            status=ShiftStatus.OPEN,
        )

        # ExchangeRate activo con USD como base
        self.pyg = _make_currency('PYG')
        _make_exchange_rate(self.usd, self.pyg)

        # Configuración de dotación inicial
        self.float_config = InitialFloatConfig.objects.create(
            currency=self.usd,
            denomination=self.usd100,
            default_quantity=5,
            allow_partial_fill=True,
            is_active=True,
        )

        # Stock inicial en bóveda
        self.vault_inv = BanknoteInventory.objects.create(
            location_type=LocationType.VAULT,
            vault=self.vault,
            currency=self.usd,
            denomination=self.usd100,
            quantity=10,
        )

    # ------------------------------------------------------------------
    # 1. Verifica que la dotación se transfiere correctamente
    # ------------------------------------------------------------------

    def test_open_shift_inventory_transfers_to_register(self) -> None:
        """open_shift_inventory debe dejar 5 en REGISTER y 5 en VAULT."""
        InventoryService.open_shift_inventory(self.shift, self.vault, self.user)

        self.vault_inv.refresh_from_db()
        self.assertEqual(self.vault_inv.quantity, 5)

        register_inv = BanknoteInventory.objects.get(
            location_type=LocationType.REGISTER,
            cash_register=self.register,
            denomination=self.usd100,
        )
        self.assertEqual(register_inv.quantity, 5)

    # ------------------------------------------------------------------
    # 2. Verifica creación de BanknoteMovement de tipo SHIFT_OPENING
    # ------------------------------------------------------------------

    def test_open_shift_inventory_creates_banknote_movements(self) -> None:
        """Después de open_shift_inventory debe existir un BanknoteMovement SHIFT_OPENING."""
        InventoryService.open_shift_inventory(self.shift, self.vault, self.user)

        exists = BanknoteMovement.objects.filter(
            shift=self.shift,
            movement_type=BanknoteMovementType.SHIFT_OPENING,
        ).exists()
        self.assertTrue(exists)

    # ------------------------------------------------------------------
    # 3. Verifica creación de ShiftDenominationCount
    # ------------------------------------------------------------------

    def test_open_shift_inventory_creates_denomination_counts(self) -> None:
        """Después de open_shift_inventory debe existir ShiftDenominationCount con opening_quantity=5."""
        InventoryService.open_shift_inventory(self.shift, self.vault, self.user)

        count = ShiftDenominationCount.objects.filter(
            shift=self.shift,
            denomination=self.usd100,
        ).first()
        self.assertIsNotNone(count)
        self.assertEqual(count.opening_quantity, 5)

    # ------------------------------------------------------------------
    # 4. Dotación parcial: vault tiene menos que default_quantity
    # ------------------------------------------------------------------

    def test_open_shift_partial_fill_with_warning(self) -> None:
        """Vault con quantity=3 y allow_partial_fill=True debe transferir 3 y retornar warning."""
        self.vault_inv.quantity = 3
        self.vault_inv.save(update_fields=['quantity', 'updated_at'])

        counts, warnings = InventoryService.open_shift_inventory(
            self.shift, self.vault, self.user
        )

        self.vault_inv.refresh_from_db()
        self.assertEqual(self.vault_inv.quantity, 0)

        register_inv = BanknoteInventory.objects.get(
            location_type=LocationType.REGISTER,
            cash_register=self.register,
            denomination=self.usd100,
        )
        self.assertEqual(register_inv.quantity, 3)
        self.assertTrue(len(warnings) > 0)

    # ------------------------------------------------------------------
    # 5. Sin dotación parcial y vault insuficiente → InsufficientVaultStockError
    # ------------------------------------------------------------------

    def test_open_shift_raises_if_insufficient_and_no_partial(self) -> None:
        """allow_partial_fill=False y vault con quantity=2 debe lanzar InsufficientVaultStockError."""
        self.float_config.allow_partial_fill = False
        self.float_config.save(update_fields=['allow_partial_fill'])

        self.vault_inv.quantity = 2
        self.vault_inv.save(update_fields=['quantity', 'updated_at'])

        with self.assertRaises(InsufficientVaultStockError):
            InventoryService.open_shift_inventory(self.shift, self.vault, self.user)

    # ------------------------------------------------------------------
    # 6. Turno en estado CLOSED → InvalidShiftStateError
    # ------------------------------------------------------------------

    def test_open_shift_invalid_state_raises(self) -> None:
        """Turno en estado CLOSED debe lanzar InvalidShiftStateError."""
        self.shift.status = ShiftStatus.CLOSED
        self.shift.save(update_fields=['status'])

        with self.assertRaises(InvalidShiftStateError):
            InventoryService.open_shift_inventory(self.shift, self.vault, self.user)


# ==============================================================================
# Clase 3 — Operaciones cambiarias (InventoryService.register_exchange_operation)
# ==============================================================================


class InventoryServiceOperationTests(TestCase):
    """Tests de registro de operaciones cambiarias con actualización de stock."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username='cajero_test', password='pass')
        self.usd = _make_currency('USD')
        self.brl = _make_currency('BRL')

        self.usd100 = CurrencyDenomination.objects.create(
            currency=self.usd, value=Decimal('100'), is_active=True
        )
        self.brl50 = CurrencyDenomination.objects.create(
            currency=self.brl, value=Decimal('50'), is_active=True
        )

        self.vault = Vault.objects.create(
            code='BOVEDA-01',
            name='Bóveda Central',
            is_active=True,
        )

        self.register = CashRegister.objects.create(
            register_code='CAJA-TEST-01',
            name='Caja Test',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )
        self.shift = CashShift.objects.create(
            cash_register=self.register,
            cashier=self.user,
            shift_number='SHIFT-TEST-001',
            status=ShiftStatus.OPEN,
        )

        # ExchangeRate activo para USD y BRL
        self.pyg = _make_currency('PYG')
        _make_exchange_rate(self.usd, self.pyg)
        _make_exchange_rate(self.brl, self.pyg)

        # Configuración de dotación para USD-100
        InitialFloatConfig.objects.create(
            currency=self.usd,
            denomination=self.usd100,
            default_quantity=5,
            allow_partial_fill=True,
            is_active=True,
        )

        # Stock inicial en bóveda
        BanknoteInventory.objects.create(
            location_type=LocationType.VAULT,
            vault=self.vault,
            currency=self.usd,
            denomination=self.usd100,
            quantity=10,
        )

        # Abrir inventario del turno (dotación bóveda → caja)
        InventoryService.open_shift_inventory(self.shift, self.vault, self.user)

    def _get_register_inv(self, denomination: CurrencyDenomination) -> BanknoteInventory:
        return BanknoteInventory.objects.get(
            location_type=LocationType.REGISTER,
            cash_register=self.register,
            denomination=denomination,
        )

    # ------------------------------------------------------------------
    # 1. Entrada de billetes aumenta el stock
    # ------------------------------------------------------------------

    def test_register_exchange_in_increases_stock(self) -> None:
        """denomination_in_amounts={usd100: 3} debe aumentar el stock del REGISTER en 3."""
        inv_before = self._get_register_inv(self.usd100)
        qty_before = inv_before.quantity

        InventoryService.register_exchange_operation(
            shift=self.shift,
            currency_in=self.usd,
            denomination_in_amounts={self.usd100.id: 3},
            currency_out=self.brl,
            denomination_out_amounts={},
            performed_by=self.user,
        )

        inv_after = self._get_register_inv(self.usd100)
        self.assertEqual(inv_after.quantity, qty_before + 3)

    # ------------------------------------------------------------------
    # 2. Salida de billetes disminuye el stock
    # ------------------------------------------------------------------

    def test_register_exchange_out_decreases_stock(self) -> None:
        """denomination_out_amounts={usd100: 2} debe disminuir el stock del REGISTER en 2."""
        inv_before = self._get_register_inv(self.usd100)
        qty_before = inv_before.quantity

        InventoryService.register_exchange_operation(
            shift=self.shift,
            currency_in=self.brl,
            denomination_in_amounts={},
            currency_out=self.usd,
            denomination_out_amounts={self.usd100.id: 2},
            performed_by=self.user,
        )

        inv_after = self._get_register_inv(self.usd100)
        self.assertEqual(inv_after.quantity, qty_before - 2)

    # ------------------------------------------------------------------
    # 3. Salida mayor al stock disponible → InsufficientRegisterStockError
    # ------------------------------------------------------------------

    def test_register_exchange_raises_if_insufficient(self) -> None:
        """out_amount > available debe lanzar InsufficientRegisterStockError."""
        with self.assertRaises(InsufficientRegisterStockError):
            InventoryService.register_exchange_operation(
                shift=self.shift,
                currency_in=self.brl,
                denomination_in_amounts={},
                currency_out=self.usd,
                denomination_out_amounts={self.usd100.id: 999},
                performed_by=self.user,
            )

    # ------------------------------------------------------------------
    # 4. Operaciones actualizan ShiftDenominationCount
    # ------------------------------------------------------------------

    def test_register_exchange_updates_denomination_count(self) -> None:
        """register_exchange_operation debe actualizar operations_in y operations_out."""
        InventoryService.register_exchange_operation(
            shift=self.shift,
            currency_in=self.usd,
            denomination_in_amounts={self.usd100.id: 3},
            currency_out=self.usd,
            denomination_out_amounts={self.usd100.id: 1},
            performed_by=self.user,
        )

        count = ShiftDenominationCount.objects.get(
            shift=self.shift,
            denomination=self.usd100,
        )
        self.assertEqual(count.operations_in, 3)
        self.assertEqual(count.operations_out, 1)


# ==============================================================================
# Clase 4 — Reconciliación (submit_cashier_count + approve_reconciliation)
# ==============================================================================


class InventoryServiceReconciliationTests(TestCase):
    """Tests del flujo completo de arqueo: declaración del cajero y aprobación del admin."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username='cajero_test', password='pass')
        self.admin = User.objects.create_user(username='admin_test', password='pass')

        self.usd = _make_currency('USD')
        self.usd100 = CurrencyDenomination.objects.create(
            currency=self.usd, value=Decimal('100'), is_active=True
        )

        self.vault = Vault.objects.create(
            code='BOVEDA-01',
            name='Bóveda Central',
            is_active=True,
        )

        self.register = CashRegister.objects.create(
            register_code='CAJA-TEST-01',
            name='Caja Test',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )
        self.shift = CashShift.objects.create(
            cash_register=self.register,
            cashier=self.user,
            shift_number='SHIFT-TEST-001',
            status=ShiftStatus.OPEN,
        )

        self.pyg = _make_currency('PYG')
        _make_exchange_rate(self.usd, self.pyg)

        InitialFloatConfig.objects.create(
            currency=self.usd,
            denomination=self.usd100,
            default_quantity=5,
            allow_partial_fill=True,
            is_active=True,
        )

        BanknoteInventory.objects.create(
            location_type=LocationType.VAULT,
            vault=self.vault,
            currency=self.usd,
            denomination=self.usd100,
            quantity=10,
        )

        InventoryService.open_shift_inventory(self.shift, self.vault, self.user)

    def _submit_count(self, qty: int = 5) -> None:
        """Helper: cajero declara arqueo con la cantidad indicada."""
        InventoryService.submit_cashier_count(
            shift=self.shift,
            denomination_counts={self.usd100.id: qty},
            performed_by=self.user,
        )

    # ------------------------------------------------------------------
    # 1. submit_cashier_count → shift.status == PENDING_REVIEW
    # ------------------------------------------------------------------

    def test_submit_cashier_count_sets_pending_review(self) -> None:
        """submit_cashier_count debe cambiar el turno a PENDING_REVIEW."""
        self._submit_count()
        self.shift.refresh_from_db()
        self.assertEqual(self.shift.status, ShiftStatus.PENDING_REVIEW)

    # ------------------------------------------------------------------
    # 2. submit_cashier_count → register.status == PENDING_CONTROL
    # ------------------------------------------------------------------

    def test_submit_cashier_count_sets_pending_control_on_register(self) -> None:
        """submit_cashier_count debe cambiar la caja a PENDING_CONTROL."""
        self._submit_count()
        self.register.refresh_from_db()
        self.assertEqual(self.register.status, CashRegisterStatus.PENDING_CONTROL)

    # ------------------------------------------------------------------
    # 3. submit_cashier_count sobre turno no OPEN → InvalidShiftStateError
    # ------------------------------------------------------------------

    def test_submit_cashier_count_raises_if_not_open(self) -> None:
        """submit_cashier_count sobre turno en PENDING_REVIEW debe lanzar InvalidShiftStateError."""
        self._submit_count()  # deja el turno en PENDING_REVIEW

        with self.assertRaises(InvalidShiftStateError):
            InventoryService.submit_cashier_count(
                shift=self.shift,
                denomination_counts={self.usd100.id: 5},
                performed_by=self.user,
            )

    # ------------------------------------------------------------------
    # 4. approve_reconciliation(APPROVE) → VAULT incrementa
    # ------------------------------------------------------------------

    def test_approve_reconciliation_transfers_to_vault(self) -> None:
        """APPROVE debe transferir el inventario de la caja a la bóveda."""
        self._submit_count(qty=5)

        vault_inv = BanknoteInventory.objects.get(
            location_type=LocationType.VAULT,
            vault=self.vault,
            denomination=self.usd100,
        )
        qty_before = vault_inv.quantity

        InventoryService.approve_reconciliation(
            shift=self.shift,
            action=ReconciliationAction.APPROVE,
            admin_user=self.admin,
        )

        vault_inv.refresh_from_db()
        self.assertGreater(vault_inv.quantity, qty_before)

    # ------------------------------------------------------------------
    # 5. approve_reconciliation(APPROVE) → shift cierra correctamente
    # ------------------------------------------------------------------

    def test_approve_reconciliation_sets_shift_closed(self) -> None:
        """APPROVE debe dejar el turno en RECONCILED o DISCREPANCY."""
        self._submit_count(qty=5)

        InventoryService.approve_reconciliation(
            shift=self.shift,
            action=ReconciliationAction.APPROVE,
            admin_user=self.admin,
        )

        self.shift.refresh_from_db()
        self.assertIn(
            self.shift.status,
            [ShiftStatus.RECONCILED, ShiftStatus.DISCREPANCY],
        )

    # ------------------------------------------------------------------
    # 6. approve_reconciliation(REJECT) → turno vuelve a OPEN
    # ------------------------------------------------------------------

    def test_reject_reconciliation_resets_to_open(self) -> None:
        """REJECT debe devolver el turno a OPEN y resetear counted_quantity."""
        self._submit_count(qty=4)

        InventoryService.approve_reconciliation(
            shift=self.shift,
            action=ReconciliationAction.REJECT,
            admin_user=self.admin,
        )

        self.shift.refresh_from_db()
        self.assertEqual(self.shift.status, ShiftStatus.OPEN)

        count = ShiftDenominationCount.objects.get(
            shift=self.shift,
            denomination=self.usd100,
        )
        self.assertIsNone(count.counted_quantity)

    # ------------------------------------------------------------------
    # 7. APPROVE_WITH_ADJUSTMENT sin notes → ValidationError
    # ------------------------------------------------------------------

    def test_approve_with_adjustment_requires_notes(self) -> None:
        """APPROVE_WITH_ADJUSTMENT con notes='' debe lanzar ValidationError."""
        self._submit_count(qty=5)

        with self.assertRaises(ValidationError):
            InventoryService.approve_reconciliation(
                shift=self.shift,
                action=ReconciliationAction.APPROVE_WITH_ADJUSTMENT,
                admin_user=self.admin,
                adjusted_counts={self.usd100.id: 5},
                notes='',
            )

    # ------------------------------------------------------------------
    # 8. APPROVE_WITH_ADJUSTMENT usa adjusted_counts
    # ------------------------------------------------------------------

    def test_approve_with_adjustment_uses_adjusted_counts(self) -> None:
        """APPROVE_WITH_ADJUSTMENT debe guardar admin_adjusted_quantity=3 en el count."""
        self._submit_count(qty=5)

        InventoryService.approve_reconciliation(
            shift=self.shift,
            action=ReconciliationAction.APPROVE_WITH_ADJUSTMENT,
            admin_user=self.admin,
            adjusted_counts={self.usd100.id: 3},
            notes='Ajuste manual aprobado por supervisor.',
        )

        count = ShiftDenominationCount.objects.get(
            shift=self.shift,
            denomination=self.usd100,
        )
        self.assertEqual(count.admin_adjusted_quantity, 3)


# ==============================================================================
# Clase 5 — Consultas de stock y depósito en bóveda
# ==============================================================================


class InventoryServiceStockSummaryTests(TestCase):
    """Tests de consultas de inventario en caja y bóveda, y depósito externo."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username='cajero_test', password='pass')
        self.admin = User.objects.create_user(username='admin_test', password='pass')

        self.usd = _make_currency('USD')
        self.usd100 = CurrencyDenomination.objects.create(
            currency=self.usd, value=Decimal('100'), is_active=True
        )

        self.vault = Vault.objects.create(
            code='BOVEDA-01',
            name='Bóveda Central',
            is_active=True,
        )

        self.register = CashRegister.objects.create(
            register_code='CAJA-TEST-01',
            name='Caja Test',
            status=CashRegisterStatus.CLOSED,
            is_active=True,
        )
        self.shift = CashShift.objects.create(
            cash_register=self.register,
            cashier=self.user,
            shift_number='SHIFT-TEST-001',
            status=ShiftStatus.OPEN,
        )

        self.pyg = _make_currency('PYG')
        _make_exchange_rate(self.usd, self.pyg)

        InitialFloatConfig.objects.create(
            currency=self.usd,
            denomination=self.usd100,
            default_quantity=5,
            allow_partial_fill=True,
            is_active=True,
        )

        BanknoteInventory.objects.create(
            location_type=LocationType.VAULT,
            vault=self.vault,
            currency=self.usd,
            denomination=self.usd100,
            quantity=10,
        )

        InventoryService.open_shift_inventory(self.shift, self.vault, self.user)

    # ------------------------------------------------------------------
    # 1. get_register_stock_summary retorna lista no vacía
    # ------------------------------------------------------------------

    def test_get_register_stock_summary_returns_list(self) -> None:
        """get_register_stock_summary debe retornar al menos una entrada."""
        result = InventoryService.get_register_stock_summary(self.register)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        entry = result[0]
        self.assertIn('denomination', entry)
        self.assertIn('quantity', entry)

    # ------------------------------------------------------------------
    # 2. get_vault_stock_summary retorna lista
    # ------------------------------------------------------------------

    def test_get_vault_stock_summary_returns_list(self) -> None:
        """get_vault_stock_summary debe retornar entradas de bóveda."""
        result = InventoryService.get_vault_stock_summary(self.vault)
        self.assertIsInstance(result, list)
        # La bóveda debe tener al menos el remanente tras la apertura
        # (10 iniciales - 5 transferidos = 5 en bóveda)
        self.assertGreater(len(result), 0)

    # ------------------------------------------------------------------
    # 3. vault_deposit incrementa stock en bóveda
    # ------------------------------------------------------------------

    def test_vault_deposit_increases_stock(self) -> None:
        """vault_deposit(vault, USD, usd100, 20, admin) debe incrementar el stock VAULT en 20."""
        vault_inv = BanknoteInventory.objects.get(
            location_type=LocationType.VAULT,
            vault=self.vault,
            denomination=self.usd100,
        )
        qty_before = vault_inv.quantity

        InventoryService.vault_deposit(
            vault=self.vault,
            currency=self.usd,
            denomination=self.usd100,
            quantity=20,
            performed_by=self.admin,
            notes='Reposición desde banco central',
        )

        vault_inv.refresh_from_db()
        self.assertEqual(vault_inv.quantity, qty_before + 20)
