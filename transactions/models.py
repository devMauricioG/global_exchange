"""
Módulo de modelos de datos para la aplicación de transacciones cambiarias (transactions).

Define la entidad principal :class:`Transaction` y sus enumeraciones asociadas
para el registro, formalización, control financiero y trazabilidad del ciclo de vida
de las operaciones de compra y venta de divisas en Global Exchange.
"""

from decimal import Decimal
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Transaction(models.Model):
    """
    Modelo representativo de una Operación / Transacción Cambiaria (SCRUM-78 / SCRUM-65).

    Registra el intercambio financiero entre dos monedas efectuado por un cliente,
    asociando las tasas de cambio de referencia, los cargos por comisión según su
    segmento comercial, los instrumentos financieros de pago y acreditación,
    y el estado operativo a lo largo del tiempo.

    :ivar id: Identificador numérico auto-incremental (PK).
    :vartype id: int
    :ivar codigo_referencia: Código alfanumérico único para identificación y recibos (ej. TX-20260923-00001).
    :vartype codigo_referencia: str
    :ivar cliente: Ficha del cliente titular que efectúa la operación (:class:`customers.models.Cliente`).
    :vartype cliente: customers.models.Cliente
    :ivar tipo_operacion: Clasificación de la operación ('COMPRA' o 'VENTA').
    :vartype tipo_operacion: str
    :ivar base_currency: Moneda base o de referencia del par (:class:`rates.models.Currency`).
    :vartype base_currency: rates.models.Currency
    :ivar target_currency: Moneda destino o cotizada del par (:class:`rates.models.Currency`).
    :vartype target_currency: rates.models.Currency
    :ivar exchange_rate: Cotización oficial aplicada (:class:`rates.models.ExchangeRate`).
    :vartype exchange_rate: rates.models.ExchangeRate or None
    :ivar tasa_base: Tasa oficial de mercado al momento del cálculo.
    :vartype tasa_base: decimal.Decimal
    :ivar comision_segmento: Monto de comisión aplicado en moneda local según el segmento del cliente.
    :vartype comision_segmento: decimal.Decimal
    :ivar tasa_neta: Tasa efectiva final tras aplicar spread bonificado y cargos.
    :vartype tasa_neta: decimal.Decimal
    :ivar monto_origen: Importe entregado en la moneda origen.
    :vartype monto_origen: decimal.Decimal
    :ivar monto_destino: Importe liquidado recibido en la moneda destino.
    :vartype monto_destino: decimal.Decimal
    :ivar medio_pago_origen: Instrumento de pago seleccionado por el cliente (:class:`payments.models.PaymentMethod`).
    :vartype medio_pago_origen: payments.models.PaymentMethod
    :ivar medio_acreditacion_destino: Cuenta receptora de fondos (:class:`payments.models.ReceivingMethod`).
    :vartype medio_acreditacion_destino: payments.models.ReceivingMethod
    :ivar estado: Estado operativo actual ('PENDIENTE', 'COMPLETADA', 'CANCELADA').
    :vartype estado: str
    :ivar token_congelamiento: Token único de cotización congelada activa si fue reservada.
    :vartype token_congelamiento: str or None
    :ivar usuario: Operador o cajero que formalizó o asistió en la transacción.
    :vartype usuario: django.contrib.auth.models.User or None
    :ivar observaciones: Notas internas u observaciones sobre la liquidación.
    :vartype observaciones: str
    :ivar created_at: Marca temporal de registro de la transacción.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de la última actualización.
    :vartype updated_at: datetime.datetime
    """

    class TipoOperacion(models.TextChoices):
        """
        Tipos de operaciones cambiarias permitidas.

        * ``COMPRA``: Cliente entrega moneda nacional/contraparte para adquirir divisa extranjera (base).
        * ``VENTA``: Cliente entrega divisa extranjera (base) para recibir moneda nacional/contraparte.
        """
        COMPRA = 'COMPRA', 'Compra de Divisas'
        VENTA = 'VENTA', 'Venta de Divisas'

    class Estado(models.TextChoices):
        """
        Estados del ciclo de vida de una transacción.

        * ``PENDIENTE``: Transacción registrada en espera de confirmación de pago o liquidación.
        * ``COMPLETADA``: Transacción formalizada, fondos recibidos y acreditados exitosamente.
        * ``CANCELADA``: Transacción anulada manualmente o por expiración de cotización congelada.
        """
        PENDIENTE = 'PENDIENTE', 'Pendiente de Pago'
        COMPLETADA = 'COMPLETADA', 'Completada / Liquidada'
        CANCELADA = 'CANCELADA', 'Cancelada / Expirada'

    codigo_referencia = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        blank=True,
        verbose_name='Código de Referencia',
        help_text='Identificador único correlativo de la transacción (ej. TX-20260923-00001).',
    )
    cliente = models.ForeignKey(
        'customers.Cliente',
        on_delete=models.PROTECT,
        related_name='transacciones',
        verbose_name='Cliente',
        help_text='Cliente titular de la transacción cambiaria.',
    )
    tipo_operacion = models.CharField(
        max_length=10,
        choices=TipoOperacion.choices,
        default=TipoOperacion.COMPRA,
        verbose_name='Tipo de Operación',
        help_text='Indica si se trata de una compra o venta de divisas.',
    )
    base_currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.PROTECT,
        related_name='transacciones_base',
        verbose_name='Moneda Base',
        help_text='Moneda base o divisa extranjera de referencia del par (ej. USD).',
    )
    target_currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.PROTECT,
        related_name='transacciones_target',
        verbose_name='Moneda Destino (Cotizada)',
        help_text='Moneda en la que se cotiza la unidad base (ej. PYG).',
    )
    exchange_rate = models.ForeignKey(
        'rates.ExchangeRate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transacciones',
        verbose_name='Cotización Aplicada',
        help_text='Registro de tasa de cambio oficial de referencia al momento de la orden.',
    )
    tasa_base = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name='Tasa Base Oficial',
        help_text='Tasa oficial de mercado (compra o venta) fijada al momento de la transacción.',
    )
    comision_segmento = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Comisión de Segmento',
        help_text='Monto total de comisión deducido o cobrado según el segmento comercial.',
    )
    tasa_neta = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name='Tasa Neta Aplicada',
        help_text='Tasa efectiva final aplicada tras aplicar bonificaciones de spread y comisiones.',
    )
    monto_origen = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='Monto de Origen',
        help_text='Monto bruto entregado por el cliente en moneda de origen.',
    )
    monto_destino = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='Monto de Destino',
        help_text='Monto neto recibido o a liquidar en moneda de destino.',
    )
    medio_pago_origen = models.ForeignKey(
        'payments.PaymentMethod',
        on_delete=models.PROTECT,
        related_name='transacciones_pago',
        verbose_name='Medio de Pago de Origen',
        help_text='Instrumento con el cual el cliente paga los fondos.',
    )
    medio_acreditacion_destino = models.ForeignKey(
        'payments.ReceivingMethod',
        on_delete=models.PROTECT,
        related_name='transacciones_acreditacion',
        verbose_name='Medio de Acreditación de Destino',
        help_text='Cuenta receptora seleccionada para recibir los fondos liquidados.',
    )
    estado = models.CharField(
        max_length=15,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
        verbose_name='Estado de la Transacción',
        help_text='Estado del ciclo de vida de la orden cambiaria.',
    )
    token_congelamiento = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Token de Congelamiento',
        help_text='Token único de la cotización congelada en sesión si aplica (ej. QTZ-XXXXXXXX).',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transacciones_registradas',
        verbose_name='Usuario Operador',
        help_text='Usuario del sistema o cajero que registró o gestionó la operación.',
    )
    fecha_pago = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Fecha de Pago',
        help_text='Timestamp exacto en que se confirmó y acreditó el pago de la orden (SCRUM-94).',
    )
    referencia_externa_pago = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name='Referencia Externa de Pago',
        help_text='Código de referencia o ID de cobro devuelto por la pasarela (Stripe, SIPAP, etc.).',
    )
    pasarela_pago = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Pasarela de Pago',
        help_text='Pasarela tecnológica utilizada para el pago (STRIPE, SIPAP, EFECTIVO).',
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones',
        help_text='Notas o comentarios adicionales relativos a la transacción.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Fecha de Creación',
        help_text='Timestamp automático de registro de la transacción.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
        help_text='Timestamp automático de la última modificación.',
    )

    class Meta:
        verbose_name = 'Transacción Cambiaria'
        verbose_name_plural = 'Transacciones Cambiarias'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cliente', 'estado', '-created_at']),
            models.Index(fields=['tipo_operacion', 'estado']),
            models.Index(fields=['codigo_referencia']),
        ]

    def __str__(self) -> str:
        """
        Representación en cadena de texto de la transacción.

        :return: Código de referencia, tipo de operación, cliente y estado.
        :rtype: str
        """
        cliente_nombre = getattr(self.cliente, 'nombre', 'Cliente')
        return f'{self.codigo_referencia or "TX-NUEVA"} — {self.get_tipo_operacion_display()} ({cliente_nombre}) [{self.get_estado_display()}]'

    @property
    def moneda_origen(self):
        """Alias para la moneda de origen de la transacción."""
        return self.base_currency if self.tipo_operacion == self.TipoOperacion.VENTA else self.target_currency

    @property
    def moneda_destino(self):
        """Alias para la moneda destino de la transacción."""
        return self.target_currency if self.tipo_operacion == self.TipoOperacion.VENTA else self.base_currency

    @property
    def is_pending(self) -> bool:
        """Indica si la transacción se encuentra en estado pendiente."""
        return self.estado == self.Estado.PENDIENTE

    @property
    def is_completed(self) -> bool:
        """Indica si la transacción fue completada satisfactoriamente."""
        return self.estado == self.Estado.COMPLETADA

    @property
    def is_cancelled(self) -> bool:
        """Indica si la transacción fue cancelada o expiró."""
        return self.estado == self.Estado.CANCELADA

    @classmethod
    def generate_unique_reference_code(cls) -> str:
        """
        Genera un código correlativo único para la transacción con formato TX-YYYYMMDD-XXXXX.
        """
        now = timezone.now()
        date_str = now.strftime('%Y%m%d')
        # Secuencia basada en conteo diario o sufijo único aleatorio/hex
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f'TX-{date_str}-{random_suffix}'

    def clean(self) -> None:
        """
        Valida la integridad de los datos de la transacción:

        1. Las monedas base y destino deben ser distintas.
        2. Los montos (origen, destino) y tasas (base, neta) deben ser estrictamente positivos (> 0).
        3. La comisión no puede ser un valor negativo.
        4. El medio de pago de origen debe pertenecer al cliente de la transacción.
        5. El medio de acreditación destino debe pertenecer al cliente de la transacción.
        """
        super().clean()
        errors = {}

        if self.base_currency_id and self.target_currency_id:
            if self.base_currency_id == self.target_currency_id:
                errors['target_currency'] = 'La moneda destino debe ser diferente a la moneda base.'

        if self.monto_origen is not None and self.monto_origen <= Decimal('0.00'):
            errors['monto_origen'] = 'El monto de origen debe ser estrictamente positivo (> 0).'

        if self.monto_destino is not None and self.monto_destino <= Decimal('0.00'):
            errors['monto_destino'] = 'El monto de destino debe ser estrictamente positivo (> 0).'

        if self.tasa_base is not None and self.tasa_base <= Decimal('0.00'):
            errors['tasa_base'] = 'La tasa base debe ser estrictamente positiva (> 0).'

        if self.tasa_neta is not None and self.tasa_neta <= Decimal('0.00'):
            errors['tasa_neta'] = 'La tasa neta debe ser estrictamente positiva (> 0).'

        if self.comision_segmento is not None and self.comision_segmento < Decimal('0.00'):
            errors['comision_segmento'] = 'La comisión de segmento no puede ser negativa.'

        if self.cliente_id:
            if self.medio_pago_origen_id and self.medio_pago_origen.cliente_id != self.cliente_id:
                errors['medio_pago_origen'] = 'El medio de pago seleccionado no pertenece al cliente titular de la transacción.'

            if self.medio_acreditacion_destino_id and self.medio_acreditacion_destino.cliente_id != self.cliente_id:
                errors['medio_acreditacion_destino'] = 'El medio de acreditación seleccionado no pertenece al cliente titular de la transacción.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        """
        Asigna automáticamente el código de referencia si no existe, ejecuta validaciones y persiste.
        """
        if not self.codigo_referencia:
            self.codigo_referencia = self.generate_unique_reference_code()

        self.full_clean()
        super().save(*args, **kwargs)

    def mark_as_completed(
        self,
        user=None,
        fecha_pago=None,
        referencia_externa: str = '',
        pasarela: str = '',
        save: bool = True,
    ) -> None:
        """
        Realiza la transición de estado a COMPLETADA registrando fecha, pasarela y referencia de pago (SCRUM-94).
        """
        self.estado = self.Estado.COMPLETADA
        self.fecha_pago = fecha_pago or timezone.now()
        if referencia_externa:
            self.referencia_externa_pago = referencia_externa
        if pasarela:
            self.pasarela_pago = pasarela
        if user:
            self.usuario = user
        if save:
            self.save(update_fields=[
                'estado',
                'usuario',
                'fecha_pago',
                'referencia_externa_pago',
                'pasarela_pago',
                'observaciones',
                'updated_at',
            ])

    def mark_as_cancelled(self, motivo: str = '', save: bool = True) -> None:
        """
        Realiza la transición de estado a CANCELADA agregando el motivo en las observaciones.
        """
        self.estado = self.Estado.CANCELADA
        if motivo:
            obs = self.observaciones or ''
            self.observaciones = f"{obs}\n[Cancelación] {motivo}".strip()
        if save:
            self.save(update_fields=['estado', 'observaciones', 'updated_at'])

    @property
    def kude(self):
        """
        Retorna la factura electrónica (KuDE) asociada a la transacción, si existe.
        """
        return getattr(self, 'factura_electronica', None)

    @property
    def has_kude(self) -> bool:
        """
        Indica si la transacción cuenta con un documento tributario electrónico (KuDE) emitido.
        """
        return hasattr(self, 'factura_electronica') and self.factura_electronica is not None


class ElectronicInvoice(models.Model):
    """
    Modelo representativo del Documento Tributario Electrónico (DTE) y su representación gráfica KuDE.

    Satisface los requerimientos técnicos y fiscales del Sistema Integrado de Facturación
    Electrónica Nacional (SIFEN / e-Kuatia) de la Dirección Nacional de Ingresos Tributarios (DNIT)
    de Paraguay (SCRUM-121).

    :ivar id: Identificador numérico auto-incremental (PK).
    :vartype id: int
    :ivar transaction: Transacción cambiaria liquidada asociada a esta factura electrónica.
    :vartype transaction: transactions.models.Transaction
    :ivar cdc: Código de Control / Clave de Acceso de 44 dígitos numéricos según estándar SIFEN.
    :vartype cdc: str
    :ivar timbrado: Número de timbrado fiscal otorgado por la DNIT (8 dígitos).
    :vartype timbrado: str
    :ivar numero_factura: Número legal de factura con formato Establecimiento-Punto-Secuencia (ej. 001-001-0000001).
    :vartype numero_factura: str
    :ivar fecha_emision: Fecha y hora exacta de emisión y firma del documento.
    :vartype fecha_emision: datetime.datetime
    :ivar estado: Estado de autorización en SIFEN ('EMITIDO', 'APROBADO', 'RECHAZADO').
    :vartype estado: str
    :ivar xml_firmado: Contenido íntegro del XML firmado digitalmente (formato e-Kuatia).
    :vartype xml_firmado: str
    :ivar qr_data: Parámetros y URL para validación mediante código QR oficial de la DNIT.
    :vartype qr_data: str
    :ivar protocolo_autorizacion: Número de protocolo asignado tras la aprobación en el receptor SIFEN.
    :vartype protocolo_autorizacion: str
    :ivar created_at: Marca temporal de creación del registro.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Marca temporal de la última actualización.
    :vartype updated_at: datetime.datetime
    """

    class EstadoSifen(models.TextChoices):
        """
        Estados de la factura electrónica en el flujo de autorización SIFEN.
        """
        EMITIDO = 'EMITIDO', 'Emitido'
        APROBADO = 'APROBADO', 'Aprobado / Autorizado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'
        CANCELADO = 'CANCELADO', 'Cancelado / Anulado'

    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.CASCADE,
        related_name='factura_electronica',
        verbose_name='Transacción Asociada',
        help_text='Transacción cambiaria vinculada a este documento tributario electrónico.',
    )
    cdc = models.CharField(
        max_length=44,
        unique=True,
        db_index=True,
        verbose_name='Código de Control (CDC)',
        help_text='Clave de Acceso única de 44 dígitos numéricos para consulta oficial en SIFEN.',
    )
    timbrado = models.CharField(
        max_length=8,
        default='12548963',
        verbose_name='Número de Timbrado',
        help_text='Número de timbrado fiscal vigente otorgado por la DNIT.',
    )
    numero_factura = models.CharField(
        max_length=20,
        db_index=True,
        verbose_name='Número de Factura Electrónica',
        help_text='Formato legal oficial: 001-001-0000001 (Establecimiento-PuntoExpedición-Secuencia).',
    )
    fecha_emision = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='Fecha y Hora de Emisión',
        help_text='Fecha y hora formal de emisión tributaria.',
    )
    estado = models.CharField(
        max_length=15,
        choices=EstadoSifen.choices,
        default=EstadoSifen.APROBADO,
        db_index=True,
        verbose_name='Estado en SIFEN',
        help_text='Estado de recepción y autorización en el Sistema Integrado de Facturación Electrónica.',
    )
    xml_firmado = models.TextField(
        blank=True,
        verbose_name='XML Firmado (e-Kuatia)',
        help_text='Estructura canónica del Documento Electrónico con firma digital XML-DSig.',
    )
    qr_data = models.TextField(
        blank=True,
        verbose_name='Cadena de Verificación QR',
        help_text='URL y parámetros oficiales para consulta pública y lectura QR en portal SET/DNIT.',
    )
    protocolo_autorizacion = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Protocolo de Autorización SIFEN',
        help_text='Identificador de transacción y protocolo emitido por el webservice de la DNIT.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
    )

    class Meta:
        verbose_name = 'Factura Electrónica (KuDE)'
        verbose_name_plural = 'Facturas Electrónicas (KuDE)'
        ordering = ['-fecha_emision']
        indexes = [
            models.Index(fields=['cdc']),
            models.Index(fields=['numero_factura']),
            models.Index(fields=['estado', '-fecha_emision']),
        ]

    def __str__(self) -> str:
        return f'KuDE {self.numero_factura} (CDC: {self.cdc[:8]}...) [{self.get_estado_display()}]'

    @property
    def cdc_formatted(self) -> str:
        """
        Formatea el CDC de 44 dígitos en 11 bloques de 4 dígitos separados por guiones.
        """
        if not self.cdc or len(self.cdc) != 44:
            return self.cdc or ''
        return '-'.join(self.cdc[i:i + 4] for i in range(0, 44, 4))

    @property
    def is_aprobado(self) -> bool:
        """
        Indica si el documento electrónico se encuentra aprobado y autorizado ante SIFEN.
        """
        return self.estado == self.EstadoSifen.APROBADO


class FacturaSeguraConfig(models.Model):
    """
    Configuración del cliente PAC FacturaSegura y Protocolo de Cuota con Reserva Blindada (SCRUM-122).

    Administra las credenciales de conexión con el proveedor autorizado de facturación electrónica
    (SIFEN / e-Kuatia) y garantiza que 10 consultas / emisiones queden estrictamente reservadas y blindadas
    para pruebas automatizadas y QA, bloqueando operaciones comerciales ordinarias ante agotamiento.
    """

    class Environment(models.TextChoices):
        SANDBOX = 'SANDBOX', 'Ambiente Sandbox / Pruebas'
        PRODUCTION = 'PRODUCTION', 'Ambiente Producción'

    api_key = models.CharField(
        max_length=150,
        default='fs_live_sec_key_demo',
        verbose_name='Clave API FacturaSegura',
        help_text='Token o API Key provisto por FacturaSegura PAC.',
    )
    api_url = models.CharField(
        max_length=255,
        default='https://api.facturasegura.com.py/v1',
        verbose_name='URL del PAC',
        help_text='Endpoint base del servicio de facturación electrónica.',
    )
    client_id = models.CharField(
        max_length=100,
        default='global-exchange-pac',
        verbose_name='ID de Cliente PAC',
    )
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.SANDBOX,
        verbose_name='Ambiente Operativo',
    )
    total_quota = models.PositiveIntegerField(
        default=1000,
        verbose_name='Cuota Total Asignada',
        help_text='Cantidad total de llamadas/facturas contratadas para el período.',
    )
    used_quota = models.PositiveIntegerField(
        default=0,
        verbose_name='Cuota Operativa Consumida',
        help_text='Cantidad de documentos emitidos en operación ordinaria.',
    )
    test_quota_reserved = models.PositiveIntegerField(
        default=10,
        verbose_name='Reserva Blindada de Pruebas',
        help_text='Cantidad de consultas/emisiones protegidas e inalterables para pruebas y QA.',
    )
    test_quota_used = models.PositiveIntegerField(
        default=0,
        verbose_name='Cuota de Pruebas Consumida',
        help_text='Llamadas de prueba realizadas sobre la reserva blindada.',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
    )

    class Meta:
        verbose_name = 'Configuración FacturaSegura'
        verbose_name_plural = 'Configuraciones FacturaSegura'

    def __str__(self) -> str:
        return f'FacturaSegura [{self.environment}] (Cuota Disp: {self.operational_quota_available}, Blindada Test: {self.test_quota_available})'

    @property
    def operational_quota_available(self) -> int:
        """
        Retorna la cuota restante disponible para operaciones comerciales ordinarias.
        Protege estrictamente la reserva blindada de pruebas (test_quota_reserved).
        """
        disponible = self.total_quota - self.used_quota - self.test_quota_reserved
        return max(0, disponible)

    @property
    def test_quota_available(self) -> int:
        """
        Retorna la cuota restante de la reserva blindada de 10 pruebas.
        """
        return max(0, self.test_quota_reserved - self.test_quota_used)

    @property
    def is_operational_quota_exhausted(self) -> bool:
        """
        Indica si la cuota operativa se ha agotado (alcanzando el límite de la reserva blindada).
        """
        return self.operational_quota_available == 0

    @property
    def is_test_quota_exhausted(self) -> bool:
        """
        Indica si las 10 pruebas blindadas fueron completamente consumidas.
        """
        return self.test_quota_available == 0

    def consume_quota(self, is_test: bool = False) -> int:
        """
        Ejecuta el protocolo de consumo de cuota asegurando la reserva blindada de 10 pruebas.

        :param is_test: Indica si la llamada proviene de la suite de pruebas/QA.
        :raises QuotaShieldExhaustedError: Si se intenta operar habiendo consumido el saldo operativo.
        :raises TestQuotaExhaustedError: Si se agotan las 10 pruebas blindadas.
        :return: Cuota restante disponible para la categoría invocada.
        """
        from .facturasegura_client import QuotaShieldExhaustedError, TestQuotaExhaustedError

        if not is_test:
            if self.operational_quota_available <= 0:
                raise QuotaShieldExhaustedError(
                    f"Cuota operativa agotada (Total: {self.total_quota}, Usadas: {self.used_quota}). "
                    f"Las {self.test_quota_reserved} consultas restantes están blindadas exclusivamente para pruebas de integración y QA."
                )
            self.used_quota += 1
            self.save(update_fields=['used_quota', 'updated_at'])
            return self.operational_quota_available
        else:
            if self.test_quota_available <= 0:
                raise TestQuotaExhaustedError(
                    f"Reserva blindada de {self.test_quota_reserved} pruebas agotada ({self.test_quota_used}/{self.test_quota_reserved} consumidas)."
                )
            self.test_quota_used += 1
            self.save(update_fields=['test_quota_used', 'updated_at'])
            return self.test_quota_available

    def replenish_quota(self, amount: int = 100) -> None:
        """Incrementa la cuota total disponible."""
        self.total_quota += amount
        self.save(update_fields=['total_quota', 'updated_at'])

    def reset_test_quota(self) -> None:
        """Restablece el contador de la reserva blindada de 10 pruebas."""
        self.test_quota_used = 0
        self.save(update_fields=['test_quota_used', 'updated_at'])

    @classmethod
    def get_config(cls) -> 'FacturaSeguraConfig':
        """Obtiene o inicializa la configuración activa del PAC."""
        config, _ = cls.objects.get_or_create(
            id=1,
            defaults={
                'total_quota': 1000,
                'used_quota': 0,
                'test_quota_reserved': 10,
                'test_quota_used': 0,
            }
        )
        return config


class KioskTotem(models.Model):
    """
    Terminal de autoservicio físico (Tótem / Kiosco) para operaciones cambiarias en efectivo (SCRUM-122).
    """

    class Estado(models.TextChoices):
        ONLINE = 'ONLINE', 'En Línea'
        OFFLINE = 'OFFLINE', 'Fuera de Servicio'
        MAINTENANCE = 'MAINTENANCE', 'En Mantenimiento'
        LOW_CASH = 'LOW_CASH', 'Bajo Saldo en Efectivo'

    codigo = models.CharField(
        max_length=50,
        unique=True,
        default='TOTEM-01',
        verbose_name='Código de Terminal',
        help_text='Identificador único del hardware del kiosco (ej. TOTEM-01).',
    )
    nombre = models.CharField(
        max_length=100,
        default='Tótem Sucursal Central',
        verbose_name='Nombre Descriptivo',
    )
    ubicacion = models.CharField(
        max_length=200,
        default='Casa Central - Hall de Atención',
        verbose_name='Ubicación Física',
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ONLINE,
        verbose_name='Estado Operativo',
    )
    ip_address = models.GenericIPAddressField(
        default='192.168.1.100',
        verbose_name='Dirección IP de la Terminal',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Habilitado',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Alta',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
    )

    class Meta:
        verbose_name = 'Tótem / Terminal Kiosco'
        verbose_name_plural = 'Tótems / Terminales Kiosco'
        ordering = ['codigo']

    def __str__(self) -> str:
        return f'{self.codigo} - {self.nombre} ({self.get_estado_display()})'

    def get_total_balance(self, currency_code: str) -> Decimal:
        """Calcula el saldo total en efectivo disponible en los casetes para la moneda indicada."""
        return sum(
            vault.saldo for vault in self.vaults.filter(currency__code=currency_code)
        )


class KioskCashVault(models.Model):
    """
    Casete / Depósito de Billetes por denominación individual en la terminal Kiosco (SCRUM-122).
    """

    totem = models.ForeignKey(
        KioskTotem,
        on_delete=models.CASCADE,
        related_name='vaults',
        verbose_name='Tótem Asignado',
    )
    currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.PROTECT,
        related_name='kiosk_vaults',
        verbose_name='Moneda',
    )
    denominacion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Denominación de Billete',
        help_text='Valor facial del billete (ej. 100000 para PYG o 100 para USD).',
    )
    cantidad = models.PositiveIntegerField(
        default=100,
        verbose_name='Cantidad de Billetes Físicos',
        help_text='Stock físico actual de piezas de esta denominación en el casete.',
    )
    capacidad_maxima = models.PositiveIntegerField(
        default=2000,
        verbose_name='Capacidad Máxima del Casete',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Casete de Billetes (Tótem)'
        verbose_name_plural = 'Casetes de Billetes (Tótem)'
        unique_together = ('totem', 'currency', 'denominacion')
        ordering = ['totem', 'currency', '-denominacion']

    def __str__(self) -> str:
        return f'{self.totem.codigo} | {self.currency.code} {self.denominacion:,.0f} (Stock: {self.cantidad} un.)'

    @property
    def saldo(self) -> Decimal:
        """Saldo monetario total almacenado en este casete."""
        return self.denominacion * Decimal(self.cantidad)


class KioskCashOperation(models.Model):
    """
    Registro y comprobante de movimiento físico de efectivo (aceptación / dispensación) en Kiosco (SCRUM-122).
    """

    class TipoOperacion(models.TextChoices):
        ACEPTACION = 'ACEPTACION', 'Aceptación Física de Billetes'
        DISPENSACION = 'DISPENSACION', 'Dispensación Física de Divisas'
        RECARGA = 'RECARGA', 'Recarga / Mantenimiento de Casetes'

    totem = models.ForeignKey(
        KioskTotem,
        on_delete=models.PROTECT,
        related_name='cash_operations',
        verbose_name='Tótem',
    )
    transaction = models.ForeignKey(
        'Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_operations',
        verbose_name='Transacción Cambiaria',
    )
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='Identificador de Comprobante',
    )
    tipo_operacion = models.CharField(
        max_length=20,
        choices=TipoOperacion.choices,
        verbose_name='Tipo de Movimiento',
    )
    currency = models.ForeignKey(
        'rates.Currency',
        on_delete=models.PROTECT,
        related_name='cash_operations',
        verbose_name='Moneda',
    )
    monto_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Monto Total en Efectivo',
    )
    desglose_billetes = models.JSONField(
        default=dict,
        verbose_name='Desglose por Denominación',
        help_text='Diccionario con la cantidad física por denominación, ej. {"100000": 3, "50000": 2}.',
    )
    total_billetes = models.PositiveIntegerField(
        default=0,
        verbose_name='Total de Billetes Físicos',
    )
    codigo_qr = models.TextField(
        blank=True,
        verbose_name='Cadena de Verificación QR',
    )
    hash_verificacion = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Hash Criptográfico SHA-256',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora',
    )

    class Meta:
        verbose_name = 'Comprobante de Movimiento en Efectivo'
        verbose_name_plural = 'Comprobantes de Movimientos en Efectivo'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.get_tipo_operacion_display()} {self.currency.code} {self.monto_total:,.2f} ({self.totem.codigo})'

    @property
    def fecha_formateada(self) -> str:
        """Marca temporal formateada legible."""
        return self.created_at.strftime("%d/%m/%Y %H:%M:%S")
