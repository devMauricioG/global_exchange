"""
Módulo de modelos de datos para la aplicación de tasas de cambio y comisiones (rates).

Define las entidades principales para la parametrización financiera en Global Exchange:
- :class:`Currency`: Catálogo de divisas internacionales admitidas.
- :class:`ExchangeRate`: Cotizaciones de compra y venta entre pares de divisas con cálculo automático de spread.
- :class:`SegmentCommission`: Reglas de comisiones porcentuales, cargos fijos y descuentos por segmento de cliente.
- :class:`OperationLimit`: Parámetros y reglas de límites operativos (mínimo, máximo, diario, mensual) por divisa y segmento.
"""

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from customers.models import Cliente


class Currency(models.Model):
    """
    Modelo representativo de una divisa o moneda en el sistema Global Exchange.

    Almacena las especificaciones monetarias estándar internacionales (código ISO 4217,
    símbolo, precisión decimal y estado operativo).

    :ivar id: Identificador numérico auto-incremental (PK).
    :vartype id: int
    :ivar code: Código alfabético ISO 4217 de 3 caracteres (ej: 'USD', 'EUR', 'PYG', 'BRL', 'ARS', 'GBP').
    :vartype code: str
    :ivar name: Nombre oficial o descriptivo de la divisa (ej: 'Dólar Estadounidense').
    :vartype name: str
    :ivar symbol: Símbolo gráfico o representativo de la moneda (ej: '$', '₲', '€', 'R$', '£').
    :vartype symbol: str
    :ivar decimals: Cantidad de dígitos decimales admitidos para transacciones (ej: 0 para PYG, 2 para USD).
    :vartype decimals: int
    :ivar is_active: Estado operativo de la moneda (True si está habilitada para operaciones).
    :vartype is_active: bool
    :ivar created_at: Marca temporal de creación del registro.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de la última modificación.
    :vartype updated_at: datetime.datetime
    """

    code = models.CharField(
        max_length=3,
        unique=True,
        db_index=True,
        verbose_name='Código ISO 4217',
        help_text='Código alfabético de 3 letras mayúsculas de la moneda (ej. USD, PYG, EUR).',
    )
    name = models.CharField(
        max_length=50,
        verbose_name='Nombre de la Moneda',
        help_text='Nombre completo descriptivo de la moneda (ej. Dólar Estadounidense, Guaraní Paraguayo).',
    )
    symbol = models.CharField(
        max_length=10,
        verbose_name='Símbolo',
        help_text='Símbolo representativo de la divisa (ej. $, ₲, €, R$, £).',
    )
    decimals = models.PositiveSmallIntegerField(
        default=2,
        verbose_name='Decimales',
        help_text='Cantidad de cifras decimales admitidas para la moneda (0 para PYG, 2 para USD/EUR).',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa',
        help_text='Indica si la moneda está disponible para operaciones de cambio y cotizaciones.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación',
        help_text='Timestamp automático de registro de la moneda.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
        help_text='Timestamp automático de la última modificación de los datos de la moneda.',
    )

    class Meta:
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'
        ordering = ['code']

    def clean(self) -> None:
        """
        Normaliza y valida los atributos de la moneda.

        - Convierte el código ISO a mayúsculas y verifica que contenga exactamente 3 letras.
        """
        if self.code:
            self.code = self.code.strip().upper()
            if len(self.code) != 3 or not self.code.isalpha():
                raise ValidationError({
                    'code': 'El código ISO debe constar exactamente de 3 caracteres alfabéticos (ej. USD, PYG).'
                })
        if self.name:
            self.name = self.name.strip()
        if self.decimals is not None:
            if self.decimals < 0 or self.decimals > 10:
                raise ValidationError({
                    'decimals': 'La cantidad de decimales debe ser un número entero entre 0 y 10.'
                })

    @property
    def decimal_places(self) -> int:
        """Alias de compatibilidad para la cantidad de dígitos decimales."""
        return self.decimals

    def save(self, *args, **kwargs) -> None:
        """Normaliza los campos y ejecuta la validación de limpieza antes de persistir."""
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()
        if self.symbol:
            self.symbol = self.symbol.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """
        Representación en cadena de texto de la moneda.

        :return: Código ISO, nombre y símbolo.
        :rtype: str
        """
        return f'{self.code} - {self.name} ({self.symbol})'


class ExchangeRate(models.Model):
    """
    Modelo de Tasa de Cambio y Cotización entre un par de divisas (base ↔ cotizada).

    Almacena los valores oficiales de compra y venta para una fecha y vigencia determinada,
    calculando de forma automática el spread cambiario.

    :ivar id: Identificador numérico auto-incremental (PK).
    :vartype id: int
    :ivar base_currency: Moneda origen o base (:class:`Currency`).
    :vartype base_currency: Currency
    :ivar target_currency: Moneda cotizada o destino (:class:`Currency`).
    :vartype target_currency: Currency
    :ivar buy_rate: Tasa de cambio para compra (valor que la casa paga por unidad de base).
    :vartype buy_rate: decimal.Decimal
    :ivar sell_rate: Tasa de cambio para venta (valor al que la casa vende la unidad de base).
    :vartype sell_rate: decimal.Decimal
    :ivar spread: Diferencia entre la tasa de venta y la de compra (``sell_rate - buy_rate``).
    :vartype spread: decimal.Decimal
    :ivar valid_from: Fecha y hora a partir de la cual entra en vigencia la cotización.
    :vartype valid_from: datetime.datetime
    :ivar valid_to: Fecha y hora límite de vigencia de la cotización (opcional).
    :vartype valid_to: datetime.datetime or None
    :ivar is_active: Indica si la cotización se encuentra activa y operable.
    :vartype is_active: bool
    :ivar updated_by: Usuario que registró o modificó la tasa (:class:`django.contrib.auth.models.User`).
    :vartype updated_by: django.contrib.auth.models.User or None
    :ivar created_at: Marca temporal de creación del registro.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de última modificación.
    :vartype updated_at: datetime.datetime
    """

    base_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='base_exchange_rates',
        verbose_name='Moneda Base (Origen)',
        help_text='Moneda que se toma como unidad de referencia para la cotización (ej. USD en USD/PYG).',
    )
    target_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='target_exchange_rates',
        verbose_name='Moneda Destino (Cotizada)',
        help_text='Moneda en la que se expresa el precio de la unidad base (ej. PYG en USD/PYG).',
    )
    buy_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name='Tasa de Compra',
        help_text='Precio de compra de la divisa base expresado en unidades de la moneda destino.',
    )
    sell_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name='Tasa de Venta',
        help_text='Precio de venta de la divisa base expresado en unidades de la moneda destino.',
    )
    spread = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('0.000000'),
        editable=False,
        verbose_name='Spread Cambiario',
        help_text='Diferencial calculado automáticamente como margen entre venta y compra (sell_rate - buy_rate).',
    )
    valid_from = models.DateTimeField(
        default=timezone.now,
        verbose_name='Vigente Desde',
        help_text='Momento exacto a partir del cual rige esta cotización.',
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Vigente Hasta',
        help_text='Momento en el que expira la cotización (opcional, null si permanece vigente hasta nuevo aviso).',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa',
        help_text='Indica si la tasa está habilitada actualmente para cotizaciones y transacciones.',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_exchange_rates',
        verbose_name='Usuario de Actualización',
        help_text='Operador o administrador responsable de la fijación de la cotización.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro',
        help_text='Timestamp automático de inserción en el sistema.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
        help_text='Timestamp automático de la última modificación.',
    )

    class Meta:
        verbose_name = 'Tasa de Cambio'
        verbose_name_plural = 'Tasas de Cambio'
        ordering = ['-valid_from', '-created_at']
        indexes = [
            models.Index(fields=['base_currency', 'target_currency', 'is_active', '-valid_from']),
        ]

    def clean(self) -> None:
        """
        Valida las reglas de consistencia de la tasa de cambio:

        1. La moneda base y destino deben ser distintas.
        2. La tasa de compra debe ser estrictamente positiva (> 0).
        3. La tasa de venta debe ser estrictamente positiva (> 0).
        4. La tasa de venta debe ser mayor o igual a la tasa de compra (sell_rate >= buy_rate).
        5. Si se especifica `valid_to`, debe ser posterior a `valid_from`.
        """
        errors = {}

        if self.base_currency_id and self.target_currency_id:
            if self.base_currency_id == self.target_currency_id:
                errors['target_currency'] = 'La moneda destino debe ser diferente a la moneda base.'

        if self.buy_rate is not None and self.buy_rate <= Decimal('0'):
            errors['buy_rate'] = 'La tasa de compra debe ser un valor numérico estrictamente positivo (> 0).'

        if self.sell_rate is not None and self.sell_rate <= Decimal('0'):
            errors['sell_rate'] = 'La tasa de venta debe ser un valor numérico estrictamente positivo (> 0).'

        if self.buy_rate is not None and self.sell_rate is not None:
            if self.sell_rate < self.buy_rate:
                errors['sell_rate'] = 'La tasa de venta no puede ser inferior a la tasa de compra.'

        if self.valid_from and self.valid_to:
            if self.valid_to <= self.valid_from:
                errors['valid_to'] = 'La fecha de fin de vigencia (valid_to) debe ser posterior a la fecha de inicio (valid_from).'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        """
        Calcula automáticamente el spread (sell_rate - buy_rate) y valida la entidad antes de persistir.
        """
        if self.buy_rate is not None and self.sell_rate is not None:
            self.spread = self.sell_rate - self.buy_rate
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_current(self) -> bool:
        """
        Evalúa si la cotización se encuentra vigente en el instante actual.

        :return: True si está activa y el instante actual se encuentra dentro del rango de vigencia.
        :rtype: bool
        """
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from > now:
            return False
        if self.valid_to and self.valid_to < now:
            return False
        return True

    def is_currently_valid(self) -> bool:
        """Alias funcional para evaluar la vigencia temporal actual."""
        return self.is_current

    def get_rate_for_operation(self, operation_type: str) -> Decimal:
        """
        Retorna la tasa oficial correspondiente a una operación de compra o venta.

        :param operation_type: 'BUY' (retorna sell_rate) o 'SELL' (retorna buy_rate).
        :type operation_type: str
        :return: Tasa de cambio oficial aplicable.
        :rtype: decimal.Decimal
        :raises ValueError: Si el tipo de operación no es válido.
        """
        op = str(operation_type).upper().strip()
        if op == 'BUY':
            return self.sell_rate
        elif op == 'SELL':
            return self.buy_rate
        raise ValueError(f"Tipo de operación inválido: '{operation_type}'. Debe ser 'BUY' o 'SELL'.")

    def __str__(self) -> str:
        """
        Representación textual de la tasa de cambio.

        :return: Par de monedas, tasa de compra, venta y spread.
        :rtype: str
        """
        base = getattr(self.base_currency, 'code', '???')
        target = getattr(self.target_currency, 'code', '???')
        return f'{base}/{target} — Compra: {self.buy_rate} | Venta: {self.sell_rate} (Spread: {self.spread})'


class SegmentCommission(models.Model):
    """
    Modelo de Reglas de Comisiones y Políticas Cambiarias por Segmento de Cliente.

    Define las tarifas, recargos fijos y bonificaciones sobre el spread que se aplican
    automáticamente a las transacciones de compra/venta según la clasificación del cliente
    (:class:`~customers.models.Cliente.Segmentacion`).

    :ivar id: Identificador numérico auto-incremental (PK).
    :vartype id: int
    :ivar segment: Segmento de cliente al que aplica la regla ('MIN', 'MAY', 'COR', 'VIP').
    :vartype segment: str
    :ivar commission_percentage: Porcentaje de comisión aplicado sobre el monto de la operación (ej: 1.50 para 1.5%).
    :vartype commission_percentage: decimal.Decimal
    :ivar fixed_fee: Cargo fijo o costo administrativo por transacción en moneda local.
    :vartype fixed_fee: decimal.Decimal
    :ivar spread_discount_percentage: Porcentaje de bonificación o descuento otorgado sobre el spread comercial.
    :vartype spread_discount_percentage: decimal.Decimal
    :ivar is_active: Estado operativo de la regla de comisión.
    :vartype is_active: bool
    :ivar created_at: Marca temporal de creación de la regla.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de la última actualización.
    :vartype updated_at: datetime.datetime
    """

    segment = models.CharField(
        max_length=3,
        choices=Cliente.Segmentacion.choices,
        unique=True,
        db_index=True,
        verbose_name='Segmento de Cliente',
        help_text='Categoría o segmento de clientes al cual se le aplican estas condiciones tarifarias.',
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Porcentaje de Comisión (%)',
        help_text='Porcentaje de comisión sobre el monto total de la operación (0.00% a 100.00%).',
    )
    fixed_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Cargo Fijo por Operación',
        help_text='Comisión fija aplicable por transacción independiente del volumen operado.',
    )
    spread_discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Descuento sobre Spread (%)',
        help_text='Porcentaje de bonificación o reducción del margen de spread para este segmento (0.00% a 100.00%).',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Regla Activa',
        help_text='Indica si esta política de comisión se encuentra actualmente en vigencia.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación',
        help_text='Timestamp automático de inserción de la regla.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
        help_text='Timestamp de la última modificación de los parámetros de comisión.',
    )

    class Meta:
        verbose_name = 'Comisión por Segmento'
        verbose_name_plural = 'Comisiones por Segmento'
        ordering = ['segment']

    def clean(self) -> None:
        """
        Valida que los valores de comisión y descuentos se encuentren en rangos válidos.

        - ``commission_percentage`` debe estar entre 0.00% y 100.00%.
        - ``fixed_fee`` debe ser mayor o igual a 0.00.
        - ``spread_discount_percentage`` debe estar entre 0.00% y 100.00%.
        """
        errors = {}

        if self.commission_percentage is not None:
            if self.commission_percentage < Decimal('0.00') or self.commission_percentage > Decimal('100.00'):
                errors['commission_percentage'] = 'El porcentaje de comisión debe situarse entre 0.00% y 100.00%.'

        if self.fixed_fee is not None and self.fixed_fee < Decimal('0.00'):
            errors['fixed_fee'] = 'El cargo fijo no puede ser negativo.'

        if self.spread_discount_percentage is not None:
            if self.spread_discount_percentage < Decimal('0.00') or self.spread_discount_percentage > Decimal('100.00'):
                errors['spread_discount_percentage'] = 'El descuento sobre el spread debe situarse entre 0.00% y 100.00%.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        """Ejecuta la validación de limpieza antes de persistir en base de datos."""
        self.full_clean()
        super().save(*args, **kwargs)

    def calculate_commission(self, amount: Decimal) -> Decimal:
        """
        Calcula el importe total de la comisión para un monto dado.

        :param amount: Monto de la transacción sobre el cual calcular la comisión.
        :type amount: decimal.Decimal
        :return: Monto resultante de sumar el cargo porcentual más el cargo fijo.
        :rtype: decimal.Decimal
        """
        if not self.is_active or amount <= Decimal('0'):
            return Decimal('0.00')
        percentage_part = (amount * self.commission_percentage) / Decimal('100.00')
        return percentage_part + self.fixed_fee

    def apply_spread_discount(self, original_spread: Decimal) -> Decimal:
        """
        Calcula el spread efectivo aplicando el porcentaje de descuento del segmento.

        :param original_spread: Margen de spread base de la cotización.
        :type original_spread: decimal.Decimal
        :return: Spread ajustado tras aplicar la bonificación.
        :rtype: decimal.Decimal
        """
        if not self.is_active or self.spread_discount_percentage <= Decimal('0'):
            return original_spread
        discount = (original_spread * self.spread_discount_percentage) / Decimal('100.00')
        return max(Decimal('0.000000'), original_spread - discount)

    def __str__(self) -> str:
        """
        Representación en cadena de texto de la regla de comisión.

        :return: Nombre del segmento junto con los porcentajes y cargos parametrizados.
        :rtype: str
        """
        segment_display = self.get_segment_display()
        return (
            f'Comisión {segment_display} — {self.commission_percentage}% '
            f'+ {self.fixed_fee} fijo (Dto. Spread: {self.spread_discount_percentage}%)'
        )


class OperationLimit(models.Model):
    """
    Modelo de Límites Operativos por Moneda y Segmento de Cliente (SCRUM-77 / SCRUM-64).

    Define los topes mínimos y máximos por transacción individual, así como los
    umbrales acumulados diarios y mensuales para el control de riesgos operativos
    y aseguramiento de cumplimiento normativo antilavado (PLA/FT) según la divisa
    y la clasificación del cliente (:class:`~customers.models.Cliente.Segmentacion`).

    :ivar id: Identificador numérico auto-incremental (PK).
    :vartype id: int
    :ivar segment: Segmento de cliente al que aplica la regla ('MIN', 'MAY', 'COR', 'VIP').
    :vartype segment: str
    :ivar currency: Divisa sobre la cual rigen los límites monetarios (:class:`Currency`).
    :vartype currency: rates.models.Currency
    :ivar monto_minimo: Monto mínimo permitido por transacción individual.
    :vartype monto_minimo: decimal.Decimal
    :ivar monto_maximo: Monto tope permitido por transacción individual (0.00 = ilimitado).
    :vartype monto_maximo: decimal.Decimal
    :ivar limite_diario: Monto máximo acumulado en un día calendario (0.00 = ilimitado).
    :vartype limite_diario: decimal.Decimal
    :ivar limite_mensual: Monto máximo acumulado en un mes calendario (0.00 = ilimitado).
    :vartype limite_mensual: decimal.Decimal
    :ivar is_active: Estado operativo de la regla de límites.
    :vartype is_active: bool
    :ivar created_at: Marca temporal de creación del registro.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de última modificación.
    :vartype updated_at: datetime.datetime
    """

    segment = models.CharField(
        max_length=3,
        choices=Cliente.Segmentacion.choices,
        db_index=True,
        verbose_name='Segmento de Cliente',
        help_text='Categoría o segmento comercial de clientes al cual se aplican estos límites.',
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='operation_limits',
        verbose_name='Moneda',
        help_text='Divisa sobre la cual rigen los límites monetarios parametrizados.',
    )
    monto_minimo = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Monto Mínimo por Operación',
        help_text='Monto mínimo requerido por transacción individual en esta divisa.',
    )
    monto_maximo = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Monto Máximo por Operación',
        help_text='Monto tope permitido por transacción individual (0.00 = sin límite individual).',
    )
    limite_diario = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Límite Acumulado Diario',
        help_text='Monto máximo acumulado habilitado en un día calendario (0.00 = sin límite diario).',
    )
    limite_mensual = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Límite Acumulado Mensual',
        help_text='Monto máximo acumulado habilitado en un mes calendario (0.00 = sin límite mensual).',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Regla Activa',
        help_text='Indica si esta política de límites se encuentra actualmente en vigencia.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación',
        help_text='Timestamp automático de inserción de la regla.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
        help_text='Timestamp de la última modificación de los parámetros de límites.',
    )

    class Meta:
        verbose_name = 'Límite Operativo'
        verbose_name_plural = 'Límites Operativos'
        ordering = ['segment', 'currency__code']
        constraints = [
            models.UniqueConstraint(
                fields=['segment', 'currency'],
                name='unique_segment_currency_operation_limit',
            )
        ]

    def clean(self) -> None:
        """
        Valida que los montos y topes acumulados mantengan consistencia lógica:

        - Todos los montos deben ser mayores o iguales a 0.00.
        - Si ``monto_maximo > 0``, debe ser mayor o igual a ``monto_minimo``.
        - Si ``limite_diario > 0`` y ``monto_maximo > 0``, ``monto_maximo`` no puede superar ``limite_diario``.
        - Si ``limite_mensual > 0`` y ``limite_diario > 0``, ``limite_diario`` no puede superar ``limite_mensual``.
        - Si ``limite_mensual > 0`` y ``monto_maximo > 0``, ``monto_maximo`` no puede superar ``limite_mensual``.
        """
        errors = {}

        if self.monto_minimo is not None and self.monto_minimo < Decimal('0.00'):
            errors['monto_minimo'] = 'El monto mínimo no puede ser un valor negativo.'

        if self.monto_maximo is not None and self.monto_maximo < Decimal('0.00'):
            errors['monto_maximo'] = 'El monto máximo no puede ser un valor negativo.'

        if self.limite_diario is not None and self.limite_diario < Decimal('0.00'):
            errors['limite_diario'] = 'El límite diario acumulado no puede ser un valor negativo.'

        if self.limite_mensual is not None and self.limite_mensual < Decimal('0.00'):
            errors['limite_mensual'] = 'El límite mensual acumulado no puede ser un valor negativo.'

        # Relaciones de jerarquía entre montos
        if (
            self.monto_minimo is not None
            and self.monto_maximo is not None
            and self.monto_maximo > Decimal('0.00')
            and self.monto_minimo > self.monto_maximo
        ):
            errors['monto_minimo'] = 'El monto mínimo no puede ser superior al monto máximo por operación.'

        if (
            self.monto_maximo is not None
            and self.limite_diario is not None
            and self.monto_maximo > Decimal('0.00')
            and self.limite_diario > Decimal('0.00')
            and self.monto_maximo > self.limite_diario
        ):
            errors['monto_maximo'] = 'El monto máximo por operación no puede superar el límite diario acumulado.'

        if (
            self.limite_diario is not None
            and self.limite_mensual is not None
            and self.limite_diario > Decimal('0.00')
            and self.limite_mensual > Decimal('0.00')
            and self.limite_diario > self.limite_mensual
        ):
            errors['limite_diario'] = 'El límite diario acumulado no puede superar el límite mensual acumulado.'

        if (
            self.monto_maximo is not None
            and self.limite_mensual is not None
            and self.monto_maximo > Decimal('0.00')
            and self.limite_mensual > Decimal('0.00')
            and self.monto_maximo > self.limite_mensual
        ):
            errors['monto_maximo'] = 'El monto máximo por operación no puede superar el límite mensual acumulado.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        """Ejecuta la validación de limpieza antes de persistir en base de datos."""
        self.full_clean()
        super().save(*args, **kwargs)

    def validate_amount(
        self,
        amount: Decimal,
        accumulated_daily: Decimal = Decimal('0.00'),
        accumulated_monthly: Decimal = Decimal('0.00'),
    ) -> dict:
        """
        Evalúa si un monto dado cumple con todas las restricciones de esta regla.

        :param amount: Monto de la operación individual a validar.
        :type amount: decimal.Decimal
        :param accumulated_daily: Volumen ya acumulado hoy por el cliente en esta divisa.
        :type accumulated_daily: decimal.Decimal
        :param accumulated_monthly: Volumen ya acumulado en el mes por el cliente en esta divisa.
        :type accumulated_monthly: decimal.Decimal
        :return: Diccionario con bandera `is_valid`, lista de `errors` y saldos restantes.
        :rtype: dict
        """
        errors = []
        curr_code = getattr(self.currency, 'code', 'DIVISA')

        if amount < self.monto_minimo:
            errors.append(
                f'El monto ({amount} {curr_code}) es inferior al mínimo permitido '
                f'por operación ({self.monto_minimo} {curr_code}).'
            )

        if self.monto_maximo > Decimal('0.00') and amount > self.monto_maximo:
            errors.append(
                f'El monto ({amount} {curr_code}) supera el máximo permitido '
                f'por operación ({self.monto_maximo} {curr_code}).'
            )

        if self.limite_diario > Decimal('0.00'):
            new_daily_total = accumulated_daily + amount
            if new_daily_total > self.limite_diario:
                available_daily = max(Decimal('0.00'), self.limite_diario - accumulated_daily)
                errors.append(
                    f'Supera el límite diario acumulado ({self.limite_diario} {curr_code}). '
                    f'Acumulado hoy: {accumulated_daily} {curr_code}. Disponible: {available_daily} {curr_code}.'
                )

        if self.limite_mensual > Decimal('0.00'):
            new_monthly_total = accumulated_monthly + amount
            if new_monthly_total > self.limite_mensual:
                available_monthly = max(Decimal('0.00'), self.limite_mensual - accumulated_monthly)
                errors.append(
                    f'Supera el límite mensual acumulado ({self.limite_mensual} {curr_code}). '
                    f'Acumulado en el mes: {accumulated_monthly} {curr_code}. Disponible: {available_monthly} {curr_code}.'
                )

        remaining_daily = (
            max(Decimal('0.00'), self.limite_diario - (accumulated_daily + amount))
            if self.limite_diario > Decimal('0.00')
            else None
        )
        remaining_monthly = (
            max(Decimal('0.00'), self.limite_mensual - (accumulated_monthly + amount))
            if self.limite_mensual > Decimal('0.00')
            else None
        )

        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'remaining_daily': remaining_daily,
            'remaining_monthly': remaining_monthly,
            'monto_minimo': self.monto_minimo,
            'monto_maximo': self.monto_maximo,
            'limite_diario': self.limite_diario,
            'limite_mensual': self.limite_mensual,
            'currency_code': curr_code,
            'segment': self.segment,
        }

    def __str__(self) -> str:
        """
        Representación en cadena de texto de la regla de límites operativos.

        :return: Segmento, divisa, mínimo, máximo y límites diarios/mensuales.
        :rtype: str
        """
        segment_display = self.get_segment_display()
        curr_code = getattr(self.currency, 'code', '???')
        max_str = f'{self.monto_maximo}' if self.monto_maximo > Decimal('0.00') else 'Sin Máx'
        daily_str = f'{self.limite_diario}' if self.limite_diario > Decimal('0.00') else 'Sin Límite'
        monthly_str = f'{self.limite_mensual}' if self.limite_mensual > Decimal('0.00') else 'Sin Límite'
        return (
            f'Límites {segment_display} ({curr_code}) — Mín: {self.monto_minimo}, '
            f'Máx: {max_str}, Diario: {daily_str}, Mensual: {monthly_str}'
        )
