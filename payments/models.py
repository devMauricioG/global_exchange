"""
Módulo de modelos de datos para la aplicación de medios de pago (payments).

Define la entidad principal :class:`PaymentMethod` y sus enumeraciones asociadas
para la administración y registro seguro de cuentas bancarias, billeteras digitales
y otros instrumentos financieros asociados a los clientes en Global Exchange.
"""
import re
from django.core.exceptions import ValidationError
from django.db import models, transaction
from datetime import date

class EntidadFinanciera(models.Model):
    """
    Catálogo parametrizado de entidades bancarias y proveedoras de billeteras
    electrónicas disponibles para los medios de pago.

    Permite gestionar bancos y billeteras digitales sin requerir cambios en
    el código fuente ni migraciones, habilitando su administración dinámica
    desde el panel de administración de Django.

    :ivar nombre: Nombre comercial de la entidad (ej. 'Banco Itaú', 'Tigo Money').
    :vartype nombre: str
    :ivar tipo: Clasificación de la entidad ('BANCO' o 'BILLETERA').
    :vartype tipo: str
    :ivar activo: Indica si la entidad está disponible para selección.
    :vartype activo: bool
    :ivar orden: Prioridad de aparición en los dropdowns (menor = primero).
    :vartype orden: int
    """

    class TipoEntidad(models.TextChoices):
        BANCO = 'BANCO', 'Banco'
        BILLETERA = 'BILLETERA', 'Billetera Digital'

    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nombre de la Entidad',
        help_text='Nombre comercial del banco o proveedor de billetera.',
    )
    tipo = models.CharField(
        max_length=20,
        choices=TipoEntidad.choices,
        verbose_name='Tipo de Entidad',
        help_text='Clasifica si es un banco o una billetera digital.',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Indica si la entidad está disponible para selección en los formularios.',
    )
    orden = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Orden de Aparición',
        help_text='Define la prioridad de aparición en los dropdowns (menor valor aparece primero).',
    )

    class Meta:
        verbose_name = 'Entidad Financiera'
        verbose_name_plural = 'Entidades Financieras'
        ordering = ['tipo', 'orden', 'nombre']

    def __str__(self) -> str:
        return f'{self.nombre} ({self.get_tipo_display()})'
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
    entidad_bancaria = models.ForeignKey(
        'EntidadFinanciera',
        on_delete=models.PROTECT,
        related_name='medios_pago',
        null=True,
        blank=True,
        verbose_name='Entidad Bancaria / Billetera',
        help_text='Entidad seleccionada del catálogo parametrizado.',
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
    # --- Campos específicos: Tarjeta de Débito/Crédito ---
    tarjeta_ultimos_digitos = models.CharField(
        max_length=4,
        blank=True,
        verbose_name='Últimos 4 Dígitos',
        help_text='Últimos 4 dígitos visibles de la tarjeta. El resto del número nunca se almacena.',
    )
    tarjeta_mes_vencimiento = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Mes de Vencimiento',
        help_text='Mes de vencimiento de la tarjeta (1-12).',
    )
    tarjeta_anio_vencimiento = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Año de Vencimiento',
        help_text='Año de vencimiento de la tarjeta (formato AAAA, 4 dígitos).',
    )


    # --- Campo específico: Transferencia Bancaria ---
    class TipoCuentaBancaria(models.TextChoices):
        AHORRO = 'AHORRO', 'Caja de Ahorro'
        CORRIENTE = 'CORRIENTE', 'Cuenta Corriente'

    tipo_cuenta_bancaria = models.CharField(
        max_length=20,
        choices=TipoCuentaBancaria.choices,
        blank=True,
        verbose_name='Tipo de Cuenta Bancaria',
        help_text='Clasificación de la cuenta para transferencias bancarias.',
    )

    # --- Campo específico: Billetera Digital ---
    telefono_billetera = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono de Billetera',
        help_text='Número de teléfono asociado a la billetera móvil (formato validado en clean()).',
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

        Además de las validaciones generales existentes, exige la presencia
        de los campos específicos correspondientes según ``tipo_medio``:
        Tarjeta requiere últimos dígitos y vencimiento; Transferencia requiere
        tipo de cuenta; Billetera requiere teléfono validado.
        """
        super().clean()
       
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


        if self.tipo_medio == self.TipoMedio.TARJETA:
            if not self.tarjeta_ultimos_digitos or not self.tarjeta_ultimos_digitos.isdigit() or len(self.tarjeta_ultimos_digitos) != 4:
                raise ValidationError({'tarjeta_ultimos_digitos': 'Debe indicar los últimos 4 dígitos de la tarjeta.'})
            if not self.tarjeta_mes_vencimiento or not (1 <= self.tarjeta_mes_vencimiento <= 12):
                raise ValidationError({'tarjeta_mes_vencimiento': 'Mes de vencimiento inválido (1-12).'})
            if not self.tarjeta_anio_vencimiento or self.tarjeta_anio_vencimiento < date.today().year:
                raise ValidationError({'tarjeta_anio_vencimiento': 'Año de vencimiento inválido o vencido.'})

        elif self.tipo_medio == self.TipoMedio.TRANSFERENCIA:
            if not self.tipo_cuenta_bancaria:
                raise ValidationError({'tipo_cuenta_bancaria': 'Debe indicar el tipo de cuenta bancaria.'})

        elif self.tipo_medio == self.TipoMedio.BILLETERA:
            telefono = (self.telefono_billetera or '').strip()
            if not telefono:
                raise ValidationError({'telefono_billetera': 'Debe indicar el teléfono de la billetera.'})
            if not re.match(r'^0?9\d{8}$', telefono.replace(' ', '').replace('-', '')):
                raise ValidationError({'telefono_billetera': 'Formato de teléfono inválido (ej. 0981123456).'})

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

class ReceivingMethod(models.Model):
    """
    Modelo que representa una Cuenta de Acreditación de Fondos de un Cliente.

    A diferencia de :class:`PaymentMethod` (medios utilizados para pagar),
    este modelo registra las cuentas destino donde el cliente recibe fondos
    producto de sus operaciones de compra/venta de divisas.

    :ivar cliente: Cliente titular de la cuenta de acreditación.
    :vartype cliente: customers.models.Cliente
    :ivar entidad_bancaria: Entidad del catálogo parametrizado seleccionada.
    :vartype entidad_bancaria: EntidadFinanciera
    :ivar tipo_cuenta: Tipo de cuenta bancaria o billetera para acreditación.
    :vartype tipo_cuenta: str
    :ivar numero_cuenta: Número de cuenta o teléfono de billetera destino.
    :vartype numero_cuenta: str
    :ivar titular: Nombre del titular de la cuenta receptora.
    :vartype titular: str
    :ivar documento_titular: Documento del titular (opcional).
    :vartype documento_titular: str
    :ivar es_predeterminado: Indica si es la cuenta preferida para acreditaciones.
    :vartype es_predeterminado: bool
    :ivar activo: Bandera lógica de borrado (soft-delete).
    :vartype activo: bool
    """

    class TipoCuenta(models.TextChoices):
        AHORRO = 'AHORRO', 'Caja de Ahorro'
        CORRIENTE = 'CORRIENTE', 'Cuenta Corriente'
        BILLETERA = 'BILLETERA', 'Billetera Digital / Móvil'

    cliente = models.ForeignKey(
        'customers.Cliente',
        on_delete=models.CASCADE,
        related_name='medios_acreditacion',
        verbose_name='Cliente',
        help_text='Cliente titular de esta cuenta de acreditación de fondos.',
    )
    entidad_bancaria = models.ForeignKey(
        'EntidadFinanciera',
        on_delete=models.PROTECT,
        related_name='medios_acreditacion',
        verbose_name='Entidad Bancaria / Billetera',
        help_text='Entidad seleccionada del catálogo parametrizado.',
    )
    tipo_cuenta = models.CharField(
        max_length=20,
        choices=TipoCuenta.choices,
        verbose_name='Tipo de Cuenta',
        help_text='Clasificación de la cuenta destino para acreditación.',
    )
    numero_cuenta = models.CharField(
        max_length=50,
        verbose_name='Número de Cuenta / Teléfono',
        help_text='Número de cuenta bancaria o teléfono de billetera destino.',
    )
    titular = models.CharField(
        max_length=150,
        verbose_name='Titular de la Cuenta',
        help_text='Nombre completo o razón social del titular de la cuenta receptora.',
    )
    documento_titular = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Documento / RUC del Titular',
        help_text='Cédula de identidad o RUC del titular (opcional).',
    )
    es_predeterminado = models.BooleanField(
        default=False,
        verbose_name='Predeterminado',
        help_text='Indica si esta es la cuenta preferida para recibir acreditaciones.',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Indica si la cuenta está habilitada (borrado lógico).',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')

    class Meta:
        verbose_name = 'Medio de Acreditación'
        verbose_name_plural = 'Medios de Acreditación'
        ordering = ['-es_predeterminado', '-created_at']
        indexes = [
            models.Index(fields=['cliente', 'activo']),
            models.Index(fields=['cliente', 'es_predeterminado']),
        ]

    def __str__(self) -> str:
        pred = ' (Predeterminado)' if self.es_predeterminado else ''
        return f'{self.entidad_bancaria} - {self.numero_cuenta}{pred}'

    def clean(self) -> None:
        super().clean()
        if self.numero_cuenta:
            self.numero_cuenta = self.numero_cuenta.strip()
            if not self.numero_cuenta:
                raise ValidationError({'numero_cuenta': 'El número de cuenta no puede estar vacío.'})
        if self.titular:
            self.titular = self.titular.strip()
            if not self.titular:
                raise ValidationError({'titular': 'El titular no puede estar vacío.'})
        if self.es_predeterminado and not self.activo:
            raise ValidationError({'es_predeterminado': 'Una cuenta inactiva no puede ser predeterminada.'})
        if self.entidad_bancaria_id and self.tipo_cuenta:
            if self.entidad_bancaria.tipo == 'BILLETERA' and self.tipo_cuenta != self.TipoCuenta.BILLETERA:
                raise ValidationError({'tipo_cuenta': 'Para una billetera digital, el tipo de cuenta debe ser "Billetera Digital / Móvil".'})
            if self.entidad_bancaria.tipo == 'BANCO' and self.tipo_cuenta == self.TipoCuenta.BILLETERA:
                raise ValidationError({'tipo_cuenta': 'Para un banco, el tipo de cuenta debe ser Caja de Ahorro o Cuenta Corriente.'})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        with transaction.atomic():
            if self.es_predeterminado and self.cliente_id:
                ReceivingMethod.objects.filter(
                    cliente_id=self.cliente_id,
                    es_predeterminado=True,
                ).exclude(pk=self.pk).update(es_predeterminado=False)
            super().save(*args, **kwargs)


class PaymentGatewayRecord(models.Model):
    """
    Modelo que registra transacciones y sesiones procesadas a través de pasarelas de pago externas.

    Almacena las referencias de sesiones de Stripe Checkout, PaymentIntents o transferencias
    SIPAP vinculadas a una orden cambiaria (:class:`transactions.models.Transaction`), permitiendo
    auditoría, trazabilidad y conciliación financiera en tiempo real.

    :ivar cliente: Cliente titular asociado a la operación de pago.
    :vartype cliente: customers.models.Cliente
    :ivar transaction: Transacción cambiaria asociada a la liquidación.
    :vartype transaction: transactions.models.Transaction
    :ivar gateway: Identificador de la pasarela de pago ('STRIPE' o 'SIPAP').
    :vartype gateway: str
    :ivar session_id: Identificador de sesión de Stripe Checkout (ej. cs_test_...).
    :vartype session_id: str
    :ivar payment_intent_id: Identificador del PaymentIntent en Stripe (ej. pi_...).
    :vartype payment_intent_id: str
    :ivar monto: Monto monetario involucrado en la operación.
    :vartype monto: decimal.Decimal
    :ivar moneda: Código ISO de la moneda en la que se efectúa el cobro.
    :vartype moneda: str
    :ivar estado: Estado del cobro ('PENDIENTE', 'COMPLETADO', 'FALLIDO', 'CANCELADO', 'REEMBOLSADO').
    :vartype estado: str
    :ivar checkout_url: Enlace directo generado por Stripe Checkout para redirección del cliente.
    :vartype checkout_url: str
    :ivar referencia_externa: Referencia devuelta por la pasarela o comprobante de pago.
    :vartype referencia_externa: str
    :ivar datos_evento: Metadatos o carga útil JSON retornada por el servicio.
    :vartype datos_evento: dict
    :ivar error_mensaje: Detalle del error en caso de fallo de procesamiento.
    :vartype error_mensaje: str
    :ivar created_at: Marca temporal de creación del registro.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de última modificación.
    :vartype updated_at: datetime.datetime
    """

    class Gateway(models.TextChoices):
        STRIPE = 'STRIPE', 'Stripe Checkout / Cards'
        SIPAP = 'SIPAP', 'Transferencia Bancaria SIPAP'

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de Pago'
        COMPLETADO = 'COMPLETADO', 'Completado / Pagado'
        FALLIDO = 'FALLIDO', 'Fallido / Rechazado'
        CANCELADO = 'CANCELADO', 'Cancelado / Expirado'
        REEMBOLSADO = 'REEMBOLSADO', 'Reembolsado'

    cliente = models.ForeignKey(
        'customers.Cliente',
        on_delete=models.CASCADE,
        related_name='gateway_records',
        null=True,
        blank=True,
        verbose_name='Cliente',
        help_text='Cliente titular al cual pertenece esta operación de pasarela.',
    )
    transaction = models.ForeignKey(
        'transactions.Transaction',
        on_delete=models.SET_NULL,
        related_name='gateway_records',
        null=True,
        blank=True,
        verbose_name='Transacción Cambiaria',
        help_text='Transacción de cambio asociada a este intento de pago.',
    )
    gateway = models.CharField(
        max_length=20,
        choices=Gateway.choices,
        default=Gateway.STRIPE,
        verbose_name='Pasarela de Pago',
        help_text='Proveedor o pasarela tecnológica utilizada para el cobro.',
    )
    session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        verbose_name='ID de Sesión (Checkout)',
        help_text='Identificador único de la sesión de Stripe Checkout (cs_test_...).',
    )
    payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        verbose_name='ID de PaymentIntent',
        help_text='Identificador del PaymentIntent asociado en Stripe (pi_...).',
    )
    monto = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='Monto de Operación',
        help_text='Monto cobrado o a procesar a través de la pasarela.',
    )
    moneda = models.CharField(
        max_length=10,
        default='USD',
        verbose_name='Moneda',
        help_text='Código de moneda de la operación en la pasarela (ej. USD, PYG).',
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
        verbose_name='Estado del Pago',
        help_text='Estado actual del cobro en la pasarela externa.',
    )
    checkout_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='URL de Stripe Checkout',
        help_text='URL de redirección al formulario seguro hospedado por Stripe.',
    )
    referencia_externa = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Referencia Externa',
        help_text='Código de referencia o ID devuelto por el proveedor de pago.',
    )
    datos_evento = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Datos de Evento / Metadatos',
        help_text='Carga útil o metadatos JSON suministrados por la pasarela.',
    )
    error_mensaje = models.TextField(
        blank=True,
        verbose_name='Mensaje de Error',
        help_text='Detalle o causa del fallo si la transacción no pudo completarse.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
    )

    class Meta:
        verbose_name = 'Registro de Pasarela de Pago'
        verbose_name_plural = 'Registros de Pasarela de Pago'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['payment_intent_id']),
            models.Index(fields=['gateway', 'estado']),
        ]

    def __str__(self) -> str:
        ref = self.session_id or self.payment_intent_id or f'ID-{self.id}'
        return f'{self.get_gateway_display()} — {self.moneda} {self.monto} [{self.get_estado_display()}] ({ref})'

    @property
    def is_paid(self) -> bool:
        """Indica si el pago fue acreditado y liquidado con éxito."""
        return self.estado == self.Estado.COMPLETADO


class PaymentWebhookEvent(models.Model):
    """
    Registro inmutable de eventos recibidos vía Webhook para garantizar idempotencia.

    Almacena los identificadores únicos emitidos por Stripe o SIPAP para evitar
    el doble procesamiento de eventos duplicados o reintentos de red.

    :ivar event_id: Identificador único del evento emitido por la pasarela (ej. evt_1Nz...).
    :vartype event_id: str
    :ivar gateway: Pasarela emisora del evento ('STRIPE' o 'SIPAP').
    :vartype gateway: str
    :ivar tipo_evento: Tipo o nombre del evento recibido (ej. 'checkout.session.completed').
    :vartype tipo_evento: str
    :ivar payload: Carga útil completa en formato JSON del webhook.
    :vartype payload: dict
    :ivar procesado: Bandera que indica si el evento ya fue ejecutado exitosamente.
    :vartype procesado: bool
    :ivar error_mensaje: Registro de errores si el procesamiento falló.
    :vartype error_mensaje: str
    :ivar created_at: Marca temporal de recepción del evento.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de procesamiento.
    :vartype updated_at: datetime.datetime
    """

    event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name='ID de Evento',
        help_text='Identificador único emitido por la pasarela (ej. evt_...).',
    )
    gateway = models.CharField(
        max_length=20,
        default='STRIPE',
        verbose_name='Pasarela',
        help_text='Pasarela de origen del webhook.',
    )
    tipo_evento = models.CharField(
        max_length=100,
        verbose_name='Tipo de Evento',
        help_text='Clasificación del evento notificado (ej. payment_intent.succeeded).',
    )
    payload = models.JSONField(
        default=dict,
        verbose_name='Carga Útil JSON',
        help_text='Cuerpo completo recibido en la petición del webhook.',
    )
    procesado = models.BooleanField(
        default=False,
        verbose_name='Procesado',
        help_text='Indica si la lógica de negocio correspondiente ya fue ejecutada.',
    )
    error_mensaje = models.TextField(
        blank=True,
        verbose_name='Mensaje de Error',
        help_text='Detalle de error si ocurrió una excepción durante el procesamiento.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Recepción',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Procesamiento',
    )

    class Meta:
        verbose_name = 'Evento de Webhook de Pago'
        verbose_name_plural = 'Eventos de Webhooks de Pago'
        ordering = ['-created_at']

    def __str__(self) -> str:
        proc = 'Procesado' if self.procesado else 'Pendiente'
        return f'{self.gateway} — {self.tipo_evento} ({self.event_id}) [{proc}]'