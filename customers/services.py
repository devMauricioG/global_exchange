"""
Módulo de servicios y lógica de negocio para la aplicación de clientes.

Contiene las funciones especializadas para la vinculación automática de identidades
de Keycloak (claim ``sub``) con las fichas de cliente (:class:`~customers.models.Cliente`)
y la asignación de representación mediante :class:`~customers.models.CustomerUserAssignment`
en Django.
"""

import logging
from typing import Any, Dict, Optional
from django.contrib.auth.models import AbstractBaseUser
from .models import Cliente, CustomerUserAssignment

logger = logging.getLogger(__name__)


def vincular_cliente_keycloak(
    user: AbstractBaseUser,
    keycloak_id: Optional[str] = None,
    email: Optional[str] = None,
    claims: Optional[Dict[str, Any]] = None,
) -> Optional[Cliente]:
    """
    Vincula automáticamente la identidad de Keycloak con la ficha de cliente en Django
    mediante una asignación de representación :class:`~customers.models.CustomerUserAssignment`.

    Estrategia de vinculación:

    1. Si se provee ``keycloak_id`` (claim ``sub``), busca una ficha existente con dicho identificador.
       Si existe, asegura la asignación activa como representante principal con el usuario Django.
    2. Si no se encuentra por ``keycloak_id`` y se dispone de un ``email``, busca por coincidencia exacta
       (insensible a mayúsculas/minúsculas) en el campo ``correo``. Si existe la ficha, le asigna el
       ``keycloak_id`` y crea o reactiva la asignación del usuario.
    3. Si no existe una ficha previa, no crea ninguna. La asociación de identidades
       con clientes es una atribución administrativa (RN03 del ERS).

    :param user: Instancia del usuario autenticado en Django.
    :type user: django.contrib.auth.models.AbstractBaseUser
    :param keycloak_id: Identificador único universal del usuario en Keycloak (claim ``sub``).
    :type keycloak_id: str, optional
    :param email: Correo electrónico del usuario (opcional, extraído de claims o del objeto user).
    :type email: str, optional
    :param claims: Diccionario opcional con las claims OIDC de Keycloak.
    :type claims: dict, optional
    :return: Instancia de :class:`~customers.models.Cliente` vinculada o creada, o None si no fue posible vincular.
    :rtype: customers.models.Cliente or None
    """
    if claims is None:
        claims = {}

    sub = keycloak_id or claims.get("sub")
    correo = (email or claims.get("email") or getattr(user, "email", "")).strip().lower()

    if not sub and not correo:
        logger.warning(
            "No se pudo vincular cliente para el usuario %s: falta keycloak_id (sub) y correo.",
            getattr(user, "username", str(user)),
        )
        return None

    def _asegurar_asignacion(cli: Cliente, es_principal: bool = True) -> CustomerUserAssignment:
        asignacion, created = CustomerUserAssignment.objects.get_or_create(
            customer=cli,
            user=user,
            defaults={
                'is_primary_representative': es_principal,
                'is_active': True,
            },
        )
        cambios = False
        if not asignacion.is_active:
            asignacion.is_active = True
            cambios = True
        if es_principal and not asignacion.is_primary_representative:
            # Si no hay otro representante principal, marcar este
            if not CustomerUserAssignment.objects.filter(customer=cli, is_primary_representative=True, is_active=True).exclude(pk=asignacion.pk).exists():
                asignacion.is_primary_representative = True
                cambios = True
        if cambios:
            asignacion.save()
        return asignacion

    cliente = None

    # 1. Buscar por keycloak_id (sub)
    if sub:
        cliente = Cliente.objects.filter(keycloak_id=sub).first()
        if cliente:
            logger.info(
                "Cliente #%s encontrado por keycloak_id (sub=%s).",
                cliente.id,
                sub,
            )
            actualizado = False
            if correo and cliente.correo.lower() != correo:
                # Si el correo cambió en Keycloak, actualizar si no colisiona
                if not Cliente.objects.filter(correo__iexact=correo).exclude(pk=cliente.pk).exists():
                    cliente.correo = correo
                    actualizado = True
            if actualizado:
                cliente.save()
            _asegurar_asignacion(cliente, es_principal=True)
            return cliente

    # 2. Buscar por correo electrónico (cliente preexistente creado por admin/operador)
    if correo:
        cliente = Cliente.objects.filter(correo__iexact=correo).first()
        if cliente:
            logger.info(
                "Cliente preexistente #%s (%s) encontrado por correo. Vinculando con Keycloak sub=%s.",
                cliente.id,
                cliente.correo,
                sub,
            )
            if sub:
                cliente.keycloak_id = sub
                cliente.save()
            _asegurar_asignacion(cliente, es_principal=True)
            return cliente

    logger.info(
        "El usuario %s no tiene una ficha de cliente asignada todavía.",
        getattr(user, "username", str(user)),
    )
    return None

