"""
Módulo de modelos de datos para el Inventario Físico de Billetes por Denominación (apps.cash).

Controla la trazabilidad y stock de billetes y monedas tanto en el inventario central (Bóveda)
como en cada caja registradora de sucursal durante la apertura, operación presencial y cierre con arqueo:
- :class:`Vault`: Bóveda central de almacenamiento y tesorería general.
- :class:`CurrencyDenomination`: Denominaciones oficiales reconocidas por cada divisa.
- :class:`BanknoteInventory`: Existencias físicas (stock no negativo) en Bóveda o Caja.
- :class:`InitialFloatConfig`: Reglas configurables de dotación inicial para apertura de ventanilla.
- :class:`BanknoteMovement`: Auditoría forense inmutable de traslados de billetes entre ubicaciones.
- :class:`ShiftDenominationCount`: Arqueo físico detallado por denominación en el turno.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class LocationType(models.TextChoices):
    """Tipos de ubicación física donde residen los billetes."""
    VAULT = 'VAULT', 'Bóveda Central'
    REGISTER = 'REGISTER', 'Caja Registradora / Ventanilla'
    EXTERNAL = 'EXTERNAL', 'Externo (Cliente / Banco Central)'


class BanknoteMovementType(models.TextChoices):
    """Tipos formales de transferencias y movimientos de billetes."""
    VAULT_DEPOSIT = 'VAULT_DEPOSIT', 'Ingreso Externo a Bóveda'
    VAULT_WITHDRAWAL = 'VAULT_WITHDRAWAL', 'Extracción Externa de Bóveda'
    SHIFT_OPENING = 'SHIFT_OPENING', 'Dotación de Apertura (Bóveda -> Caja)'
    EXCHANGE_IN = 'EXCHANGE_IN', 'Ingreso por Operación (Cliente -> Caja)'
    EXCHANGE_OUT = 'EXCHANGE_OUT', 'Egreso por Operación (Caja -> Cliente)'
    SHIFT_CLOSING = 'SHIFT_CLOSING', 'Devolución de Cierre (Caja -> Bóveda)'
    SURPLUS_ADJUSTMENT = 'SURPLUS_ADJUSTMENT', 'Ajuste por Sobrante de Caja'
    SHORTAGE_ADJUSTMENT = 'SHORTAGE_ADJUSTMENT', 'Ajuste por Faltante de Caja'
    MANUAL_TRANSFER = 'MANUAL_TRANSFER', 'Transferencia Manual de Billetes'


class ReconciliationAction(models.TextChoices):
    """Acciones del Administrador en la revisión de un arqueo de caja."""
    APPROVE = 'APPROVE', 'Aprobar Arqueo'
    REJECT = 'REJECT', 'Rechazar (Pedir Reconteo)'
    APPROVE_WITH_ADJUSTMENT = 'APPROVE_WITH_ADJUSTMENT', 'Aprobar con Ajuste'


class Vault(models.Model):
    """
    Bóveda central de resguardo de efectivo de una sucursal o casa central.
    """
    branch_name = models.CharField(
        max_length=128,
        default='Casa Central',
        verbose_name='Sucursal',
        help_text='Sucursal a la que pertenece la bóveda central.',
    )
    code = models.CharField(
        max_length=32,
        unique=True,
        verbose_name='Código de Bóveda',
        help_text='Identificador único de la bóveda (ej. BOVEDA-CENTRAL).',
    )
    name = models.CharField(
        max_length=128,
        verbose_name='Nombre de la Bóveda',
        help_text='Descripción formal de la bóveda o tesorería.',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa',
        help_text='Habilita transferencias hacia o desde esta bóveda.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Alta')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Modificación')

    class Meta:
        verbose_name = 'Bóveda Central'
        verbose_name_plural = 'Bóvedas Centrales'
        ordering = ['branch_name', 'code']

    def __str__(self) -> str:
        return f"{self.name} ({self.code}) - {self.branch_name}"

    def get_stock(self, denomination: 'CurrencyDenomination') -> int:
        """Devuelve la cantidad disponible de billetes de una denominación."""
        inv = self.banknote_stocks.filter(denomination=denomination).first()
        return inv.quantity if inv else 0


class CurrencyDenomination(models.Model):
    """
    Denominación oficial de billete o moneda para una divisa específica.
    """
    currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.CASCADE,
        related_name='denominations',
        verbose_name='Divisa',
    )
    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Valor Facial',
        help_text='Valor facial del billete o moneda (ej. 100, 50, 20, 100000).',
    )
    is_coin = models.BooleanField(
        default=False,
        verbose_name='Es Moneda Metálica',
        help_text='Indica si el valor corresponde a moneda metálica en vez de billete.',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa para Operaciones',
        help_text='Habilita el conteo y asignación de esta denominación.',
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Orden Visual',
        help_text='Secuencia de presentación visual en formularios y actas.',
    )

    class Meta:
        verbose_name = 'Denominación de Moneda'
        verbose_name_plural = 'Denominaciones de Moneda'
        unique_together = ('currency', 'value')
        ordering = ['currency', '-value']

    def __str__(self) -> str:
        formatted_val = f"{self.value:,.0f}" if self.value % 1 == 0 else f"{self.value:,.2f}"
        tipo = "Moneda" if self.is_coin else "Billete"
        return f"{self.currency.code} {formatted_val} ({tipo})"


class BanknoteInventory(models.Model):
    """
    Inventario físico de billetes por denominación y ubicación (Bóveda o Caja).
    Regla estricta: La cantidad nunca puede ser negativa.
    """
    location_type = models.CharField(
        max_length=16,
        choices=LocationType.choices,
        verbose_name='Tipo de Ubicación',
    )
    vault = models.ForeignKey(
        Vault,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='banknote_stocks',
        verbose_name='Bóveda Asignada',
    )
    cash_register = models.ForeignKey(
        'cash.CashRegister',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='banknote_stocks',
        verbose_name='Caja Registradora Asignada',
    )
    currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.PROTECT,
        related_name='banknote_inventories',
        verbose_name='Divisa',
    )
    denomination = models.ForeignKey(
        CurrencyDenomination,
        on_delete=models.PROTECT,
        related_name='inventory_entries',
        verbose_name='Denominación',
    )
    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Cantidad de Billetes',
        help_text='Cantidad física en existencia. No puede ser negativa.',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')

    class Meta:
        verbose_name = 'Inventario de Billetes'
        verbose_name_plural = 'Inventarios de Billetes'
        unique_together = ('location_type', 'vault', 'cash_register', 'denomination')
        ordering = ['currency', '-denomination__value']

    def __str__(self) -> str:
        loc = self.vault.name if self.location_type == LocationType.VAULT and self.vault else (
            self.cash_register.register_code if self.cash_register else 'Sin Ubicación'
        )
        return f"{self.denomination}: {self.quantity} u. en {loc}"

    @property
    def total_amount(self) -> Decimal:
        """Valor monetario total de los billetes en existencia."""
        return Decimal(str(self.quantity)) * self.denomination.value

    def clean(self) -> None:
        super().clean()
        if self.location_type == LocationType.VAULT and not self.vault:
            raise ValidationError("Debe indicar la bóveda correspondiente para una ubicación de tipo BÓVEDA.")
        if self.location_type == LocationType.REGISTER and not self.cash_register:
            raise ValidationError("Debe indicar la caja registradora correspondiente para una ubicación de tipo CAJA.")
        if self.quantity < 0:
            raise ValidationError("La cantidad física de billetes no puede ser negativa.")


class InitialFloatConfig(models.Model):
    """
    Configuración de dotación inicial por divisa y denominación.
    Permite al Administrador definir cuántos billetes de cada denominación
    se transfieren automáticamente de la Bóveda a la Caja durante la apertura.
    """
    currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.CASCADE,
        related_name='initial_float_configs',
        verbose_name='Divisa',
    )
    denomination = models.ForeignKey(
        CurrencyDenomination,
        on_delete=models.CASCADE,
        related_name='initial_float_configs',
        verbose_name='Denominación',
    )
    default_quantity = models.PositiveIntegerField(
        default=10,
        verbose_name='Cantidad Base de Apertura',
        help_text='Cantidad de billetes a asignar desde la bóveda al abrir turno.',
    )
    allow_partial_fill = models.BooleanField(
        default=True,
        verbose_name='Permitir Dotación Parcial si falta stock en Bóveda',
        help_text='Si está marcado y la bóveda no tiene la cantidad completa, asigna lo disponible con advertencia.',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Regla Activa',
    )

    class Meta:
        verbose_name = 'Configuración de Dotación Inicial'
        verbose_name_plural = 'Configuraciones de Dotación Inicial'
        unique_together = ('currency', 'denomination')
        ordering = ['currency', '-denomination__value']

    def __str__(self) -> str:
        return f"Dotación Inicial {self.denomination}: {self.default_quantity} u."


class BanknoteMovement(models.Model):
    """
    Auditoría inmutable de movimientos de billetes.
    Registra cada entrada o salida física por denominación garantizando que el
    saldo de billetes pueda reconstruirse enteramente a partir del historial.
    """
    movement_type = models.CharField(
        max_length=32,
        choices=BanknoteMovementType.choices,
        verbose_name='Tipo de Movimiento',
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name='Fecha y Hora',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='banknote_movements',
        verbose_name='Usuario Responsable',
    )
    keycloak_user_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Keycloak User ID',
    )
    shift = models.ForeignKey(
        'cash.CashShift',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='banknote_movements',
        verbose_name='Turno de Caja Relacionado',
    )
    transaction = models.ForeignKey(
        'transactions.Transaction',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='banknote_movements',
        verbose_name='Transacción Cambiaria',
    )
    currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.PROTECT,
        verbose_name='Divisa',
    )
    denomination = models.ForeignKey(
        CurrencyDenomination,
        on_delete=models.PROTECT,
        verbose_name='Denominación',
    )
    quantity = models.PositiveIntegerField(
        verbose_name='Cantidad de Billetes Transferidos',
    )
    source_location_type = models.CharField(
        max_length=16,
        choices=LocationType.choices,
        blank=True,
        verbose_name='Tipo Ubicación Origen',
    )
    source_vault = models.ForeignKey(
        Vault,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements_from_vault',
        verbose_name='Bóveda Origen',
    )
    source_register = models.ForeignKey(
        'cash.CashRegister',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements_from_register',
        verbose_name='Caja Origen',
    )
    target_location_type = models.CharField(
        max_length=16,
        choices=LocationType.choices,
        blank=True,
        verbose_name='Tipo Ubicación Destino',
    )
    target_vault = models.ForeignKey(
        Vault,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements_to_vault',
        verbose_name='Bóveda Destino',
    )
    target_register = models.ForeignKey(
        'cash.CashRegister',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements_to_register',
        verbose_name='Caja Destino',
    )
    resulting_source_qty = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Saldo Resultante en Origen',
    )
    resulting_target_qty = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Saldo Resultante en Destino',
    )
    reference = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Referencia / Concepto',
    )

    class Meta:
        verbose_name = 'Movimiento de Billetes'
        verbose_name_plural = 'Movimientos de Billetes'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.get_movement_type_display()} - {self.denomination}: {self.quantity} u."

    @property
    def total_amount(self) -> Decimal:
        return Decimal(str(self.quantity)) * self.denomination.value

    def clean(self) -> None:
        super().clean()
        if self.pk:
            orig = BanknoteMovement.objects.get(pk=self.pk)
            if orig:
                raise ValidationError("Los movimientos de billetes son inmutables y no admiten modificación.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            raise ValidationError("Los movimientos de billetes son inmutables y no admiten actualización.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:
        raise ValidationError("Los registros de auditoría de billetes no pueden ser eliminados.")


class ShiftDenominationCount(models.Model):
    """
    Control y arqueo físico de billetes por denominación para una sesión o turno de caja.
    Contrasta el inventario teórico contra el recuento físico del cajero y las aprobaciones del admin.
    """
    shift = models.ForeignKey(
        'cash.CashShift',
        on_delete=models.CASCADE,
        related_name='denomination_counts',
        verbose_name='Turno de Caja',
    )
    currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.PROTECT,
        verbose_name='Divisa',
    )
    denomination = models.ForeignKey(
        CurrencyDenomination,
        on_delete=models.PROTECT,
        verbose_name='Denominación',
    )
    opening_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Dotación Inicial',
        help_text='Cantidad de billetes recibidos de la bóveda al abrir turno.',
    )
    operations_in = models.PositiveIntegerField(
        default=0,
        verbose_name='Ingresos por Operaciones (+)',
        help_text='Billetes recibidos de clientes en operaciones.',
    )
    operations_out = models.PositiveIntegerField(
        default=0,
        verbose_name='Egresos por Operaciones (-)',
        help_text='Billetes entregados a clientes en operaciones.',
    )
    system_expected_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Stock Teórico del Sistema',
        help_text='Calculado: Inicial + Entradas - Salidas.',
    )
    counted_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Conteo Físico Declarado',
        help_text='Cantidad física contada e ingresada por el cajero en el arqueo.',
    )
    difference_quantity = models.IntegerField(
        default=0,
        verbose_name='Diferencia en Billetes',
        help_text='Declarado - Teórico. Negativo = Faltante, Positivo = Sobrante.',
    )
    difference_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Diferencia Monetaria',
    )
    admin_adjusted_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Cantidad Ajustada por Admin',
        help_text='Cantidad final verificada y aprobada por el administrador con ajuste.',
    )
    admin_notes = models.TextField(
        blank=True,
        verbose_name='Notas de Revisión del Admin',
        help_text='Motivo obligatorio si se aprueba con ajuste o justificación de rechazo.',
    )

    class Meta:
        verbose_name = 'Arqueo de Denominación por Turno'
        verbose_name_plural = 'Arqueos de Denominación por Turno'
        unique_together = ('shift', 'denomination')
        ordering = ['currency', '-denomination__value']

    def __str__(self) -> str:
        return f"{self.shift.shift_number} - {self.denomination}: Contado {self.counted_quantity or 0} / Teórico {self.system_expected_quantity}"

    def calculate_expected(self) -> int:
        """Calcula y actualiza el saldo teórico del sistema."""
        self.system_expected_quantity = max(0, self.opening_quantity + self.operations_in - self.operations_out)
        return self.system_expected_quantity

    def update_reconciliation(self, counted_qty: int) -> None:
        """Computa la diferencia física y monetaria respecto al conteo del cajero."""
        self.counted_quantity = max(0, counted_qty)
        self.calculate_expected()
        self.difference_quantity = self.counted_quantity - self.system_expected_quantity
        self.difference_amount = Decimal(str(self.difference_quantity)) * self.denomination.value

