"""
Módulo de modelos de datos para la aplicación de medios de pago (payments).

Define la entidad principal :class:`PaymentMethod` y sus enumeraciones asociadas
para la administración y registro seguro de cuentas bancarias, billeteras digitales
y otros instrumentos financieros asociados a los clientes en Global Exchange.
"""

from django.core.exceptions import ValidationError
from django.db import models, transaction


class PaymentMethod(models.Model):
    """
    Modelo que representa un Medio de Pago perteneciente a un Cliente.

    Permite a los clientes registrar y gestionar de forma segura sus cuentas
    bancarias, billeteras móviles o instrumentos de pago utilizados para
    operaciones de cambio de divisas y liquidaciones financieras.

    :ivar id: Identificador numérico único auto-incremental (PK).
    :vartype id: int
    :ivar cliente: Relación con la ficha del cliente (:class:`customers.models.Cliente`).
    :vartype cliente: customers.models.Cliente
    :ivar tipo_medio: Tipo o categoría del instrumento financiero.
    :vartype tipo_medio: str
    :ivar entidad_bancaria: Nombre del banco, cooperativa o proveedor de billetera.
    :vartype entidad_bancaria: str
    :ivar numero_cuenta: Número de cuenta bancaria o número de teléfono (billetera).
    :vartype numero_cuenta: str
    :ivar titular: Nombre completo o razón social del titular registrado.
    :vartype titular: str
    :ivar documento_titular: Documento de identidad (CI / RUC) del titular de la cuenta.
    :vartype documento_titular: str
    :ivar es_predeterminado: Indica si es el medio de pago preferido para operaciones.
    :vartype es_predeterminado: bool
    :ivar activo: Bandera lógica que habilita o inhabilita el medio de pago.
    :vartype activo: bool
    :ivar created_at: Marca temporal de creación del registro.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de última modificación.
    :vartype updated_at: datetime.datetime
    """

    class TipoMedio(models.TextChoices):
        """
        Opciones disponibles para clasificar el tipo de medio de pago.

        * ``TRANSFERENCIA``: Cuenta corriente, caja de ahorro o transferencia SIPAP.
        * ``BILLETERA``: Billetera electrónica o giros móviles (Tigo Money, Personal, Wally, Zimple).
        * ``TARJETA``: Tarjeta de débito o crédito bancaria.
        * ``EFECTIVO``: Cobro o pago por ventanilla en efectivo.
        * ``OTRO``: Otros instrumentos financieros autorizados.
        """
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia Bancaria'
        BILLETERA = 'BILLETERA', 'Billetera Digital / Móvil'
        TARJETA = 'TARJETA', 'Tarjeta Débito / Crédito'
        EFECTIVO = 'EFECTIVO', 'Efectivo / Caja'
        OTRO = 'OTRO', 'Otro'

    cliente = models.ForeignKey(
        'customers.Cliente',
        on_delete=models.CASCADE,
        related_name='medios_pago',
        verbose_name='Cliente',
        help_text='Cliente titular al cual pertenece este medio de pago.',
    )
    tipo_medio = models.CharField(
        max_length=20,
        choices=TipoMedio.choices,
        default=TipoMedio.TRANSFERENCIA,
        verbose_name='Tipo de Medio',
        help_text='Clasificación del instrumento de pago.',
    )
    entidad_bancaria = models.CharField(
        max_length=100,
        verbose_name='Entidad Bancaria / Billetera',
        help_text='Nombre de la entidad bancaria o proveedora (ej. Banco Itaú, Continental, Tigo Money, etc.).',
    )
    numero_cuenta = models.CharField(
        max_length=50,
        verbose_name='Número de Cuenta / Teléfono',
        help_text='Número de cuenta bancaria o número telefónico asignado a la billetera digital.',
    )
    titular = models.CharField(
        max_length=150,
        verbose_name='Titular de la Cuenta / Billetera',
        help_text='Nombre completo o razón social del titular del medio de pago.',
    )
    documento_titular = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Documento / RUC del Titular',
        help_text='Cédula de identidad civil o RUC del titular del medio de pago (opcional).',
    )
    es_predeterminado = models.BooleanField(
        default=False,
        verbose_name='Predeterminado',
        help_text='Indica si este es el medio de pago seleccionado por defecto para liquidaciones.',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Indica si el medio de pago se encuentra habilitado para operar.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro',
        help_text='Timestamp automático de registro.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
        help_text='Timestamp automático de la última actualización.',
    )

    class Meta:
        verbose_name = 'Medio de Pago'
        verbose_name_plural = 'Medios de Pago'
        ordering = ['-es_predeterminado', '-created_at']
        indexes = [
            models.Index(fields=['cliente', 'activo']),
            models.Index(fields=['cliente', 'es_predeterminado']),
        ]

    def __str__(self) -> str:
        """
        Representación en cadena de texto del medio de pago.

        :return: Resumen legible con tipo, entidad y número de cuenta o teléfono.
        :rtype: str
        """
        pred = ' (Predeterminado)' if self.es_predeterminado else ''
        return f'{self.get_tipo_medio_display()} - {self.entidad_bancaria} ({self.numero_cuenta}){pred}'

    def clean(self) -> None:
        """
        Validaciones personalizadas del modelo PaymentMethod.

        Asegura que los campos de entidad, número de cuenta y titular no contengan sólo espacios
        y que si un medio se marca como predeterminado esté activo.
        """
        super().clean()
        if self.entidad_bancaria:
            self.entidad_bancaria = self.entidad_bancaria.strip()
            if not self.entidad_bancaria:
                raise ValidationError({'entidad_bancaria': 'La entidad bancaria o proveedora no puede estar vacía.'})

        if self.numero_cuenta:
            self.numero_cuenta = self.numero_cuenta.strip()
            if not self.numero_cuenta:
                raise ValidationError({'numero_cuenta': 'El número de cuenta o teléfono no puede estar vacío.'})

        if self.titular:
            self.titular = self.titular.strip()
            if not self.titular:
                raise ValidationError({'titular': 'El titular de la cuenta no puede estar vacío.'})

        if self.es_predeterminado and not self.activo:
            raise ValidationError({'es_predeterminado': 'Un medio de pago inactivo no puede ser marcado como predeterminado.'})

    def save(self, *args, **kwargs) -> None:
        """
        Guarda la instancia del medio de pago asegurando la integridad de la exclusividad predeterminada.

        Si se marca como predeterminado, desmarca atómicamente cualquier otro medio de pago
        predeterminado perteneciente al mismo cliente.
        """
        self.full_clean()
        with transaction.atomic():
            if self.es_predeterminado and self.cliente_id:
                PaymentMethod.objects.filter(
                    cliente_id=self.cliente_id,
                    es_predeterminado=True,
                ).exclude(pk=self.pk).update(es_predeterminado=False)

            super().save(*args, **kwargs)
