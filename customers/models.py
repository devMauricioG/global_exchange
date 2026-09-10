"""
Módulo de modelos para la aplicación de gestión de clientes (customers).

Este módulo define la entidad principal :class:`Cliente` y sus enumeraciones
asociadas para la clasificación y segmentación de clientes en la plataforma
Global Exchange.
"""

from django.conf import settings
from django.db import models


class Cliente(models.Model):
    """
    Modelo representativo de un Cliente dentro del sistema Global Exchange.

    Almacena los datos personales, fiscales, de contacto y clasificación por segmento
    financiero/operativo del cliente, así como su vinculación con la identidad de Keycloak
    y sus múltiples representantes autorizados a través de :class:`CustomerUserAssignment`.

    :ivar id: Identificador numérico único auto-incremental (clave primaria).
    :vartype id: int
    :ivar keycloak_id: Identificador único universal (claim ``sub``) en Keycloak.
    :vartype keycloak_id: str or None
    :ivar usuarios: Relación muchos a muchos con usuarios Django mediante :class:`CustomerUserAssignment`.
    :vartype usuarios: django.db.models.fields.related.ManyToManyField
    :ivar nombre: Nombre completo o razón social del cliente.
    :vartype nombre: str
    :ivar documento_ruc: Documento de identidad civil o RUC (único en el sistema).
    :vartype documento_ruc: str
    :ivar correo: Dirección de correo electrónico de contacto (único en el sistema).
    :vartype correo: str
    :ivar telefono: Número telefónico de contacto del cliente (opcional).
    :vartype telefono: str
    :ivar segmentacion: Categoría de segmentación del cliente ('MIN', 'MAY', 'COR', 'VIP').
    :vartype segmentacion: str
    :ivar is_active: Bandera lógica que indica si el cliente está activo o dado de baja.
    :vartype is_active: bool
    :ivar created_at: Fecha y hora de registro del cliente en el sistema.
    :vartype created_at: datetime.datetime
    :ivar updated_at: Fecha y hora de la última actualización de los datos del cliente.
    :vartype updated_at: datetime.datetime
    """

    class Segmentacion(models.TextChoices):
        """
        Opciones de segmentación disponibles para clasificar a los clientes.

        * ``MINORISTA`` ('MIN'): Cliente persona física o minorista estándar.
        * ``MAYORISTA`` ('MAY'): Cliente con perfil mayorista comercial.
        * ``CORPORATIVO`` ('COR'): Empresas e instituciones corporativas.
        * ``VIP`` ('VIP'): Clientes preferenciales o de alto volumen.
        """
        MINORISTA = 'MIN', 'Minorista'
        MAYORISTA = 'MAY', 'Mayorista'
        CORPORATIVO = 'COR', 'Corporativo'
        VIP = 'VIP', 'VIP'

    keycloak_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='ID de Keycloak (sub)',
        help_text='Identificador único inmutable del usuario en Keycloak (claim sub).',
    )
    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='CustomerUserAssignment',
        related_name='clientes_representados',
        blank=True,
        verbose_name='Usuarios representantes',
        help_text='Usuarios autorizados para operar y representar a este cliente.',
    )
    nombre = models.CharField(
        max_length=150,
        verbose_name='Nombre o Razón Social',
        help_text='Nombre y apellido o razón social de la entidad cliente.',
    )
    documento_ruc = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Documento / RUC',
        help_text='Número de documento de identidad fiscal o civil único.',
    )
    correo = models.EmailField(
        unique=True,
        verbose_name='Correo Electrónico',
        help_text='Dirección de correo electrónico única para notificaciones.',
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono',
        help_text='Número de teléfono de contacto (opcional).',
    )
    segmentacion = models.CharField(
        max_length=3,
        choices=Segmentacion.choices,
        default=Segmentacion.MINORISTA,
        verbose_name='Segmentación',
        help_text='Categoría o segmento comercial asignado al cliente.',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Indica si el cliente se encuentra actualmente activo en el sistema.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro',
        help_text='Timestamp automático de creación.',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización',
        help_text='Timestamp automático de la última modificación.',
    )

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        Representación en cadena de texto del cliente.

        :return: Nombre del cliente junto con la etiqueta legible de su segmentación.
        :rtype: str
        """
        return f'{self.nombre} ({self.get_segmentacion_display()})'

    @property
    def representante_principal(self):
        """
        Retorna la asignación del representante principal activo del cliente, si existe.

        :return: Asignación principal activa o None.
        :rtype: CustomerUserAssignment or None
        """
        return self.assignments.filter(is_primary_representative=True, is_active=True).select_related('user').first()


class CustomerUserAssignment(models.Model):
    """
    Modelo de asociación intermedia para la relación de multi-representación Usuario ↔ Cliente.

    Permite que un usuario de Django represente a múltiples clientes (por ejemplo, a sí mismo
    y a diversas personas jurídicas) y que un cliente cuente con múltiples usuarios representantes,
    distinguiendo al representante principal.

    :ivar id: Identificador numérico único auto-incremental (clave primaria).
    :vartype id: int
    :ivar customer: Cliente representado (:class:`Cliente`).
    :vartype customer: Cliente
    :ivar user: Usuario autenticado que ejerce la representación (:class:`django.contrib.auth.models.User`).
    :vartype user: django.contrib.auth.models.User
    :ivar is_primary_representative: Indica si el usuario es el representante legal o titular principal.
    :vartype is_primary_representative: bool
    :ivar assigned_at: Fecha y hora en la que se efectuó la asignación.
    :vartype assigned_at: datetime.datetime
    :ivar is_active: Estado lógico de la asignación/representación.
    :vartype is_active: bool
    """

    customer = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Cliente',
        help_text='Ficha de cliente vinculada a esta asignación.',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_assignments',
        verbose_name='Usuario',
        help_text='Cuenta de usuario asociada como representante del cliente.',
    )
    is_primary_representative = models.BooleanField(
        default=False,
        verbose_name='Representante Principal',
        help_text='Indica si el usuario es el representante legal o titular principal del cliente.',
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Asignación',
        help_text='Marca temporal de la vinculación entre el usuario y el cliente.',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Asignación Activa',
        help_text='Indica si la representación se encuentra actualmente activa y autorizada.',
    )

    class Meta:
        verbose_name = 'Asignación de Usuario a Cliente'
        verbose_name_plural = 'Asignaciones de Usuarios a Clientes'
        ordering = ['-is_primary_representative', '-assigned_at']
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'user'],
                name='unique_customer_user_assignment',
            )
        ]

    def __str__(self) -> str:
        """
        Representación en cadena de texto de la asignación.

        :return: Descripción textual del usuario, cliente y rol de representación.
        :rtype: str
        """
        rol = 'Principal' if self.is_primary_representative else 'Secundario'
        estado = 'Activo' if self.is_active else 'Inactivo'
        return f'{self.user} → {self.customer.nombre} ({rol}, {estado})'


