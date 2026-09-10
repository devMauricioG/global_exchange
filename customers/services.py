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
    3. Si no existe ninguna ficha previa, crea una nueva entidad :class:`~customers.models.Cliente`
       utilizando los datos extraídos de las claims de Keycloak (``nombre``, ``correo``, ``keycloak_id``, etc.)
       y registra la asignación de representación principal para el usuario.

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

    # 3. Si no existe ficha previa, crear automáticamente un nuevo Cliente
    nombre_completo = ""
    given_name = claims.get("given_name", "")
    family_name = claims.get("family_name", "")
    if given_name or family_name:
        nombre_completo = f"{given_name} {family_name}".strip()
    elif hasattr(user, "get_full_name") and user.get_full_name():
        nombre_completo = user.get_full_name()
    elif claims.get("name"):
        nombre_completo = claims.get("name")
    elif claims.get("preferred_username"):
        nombre_completo = claims.get("preferred_username")
    else:
        nombre_completo = getattr(user, "username", "Cliente")

    # Documento/RUC generado a partir de claims o clave única
    documento_ruc = claims.get("documento_ruc") or claims.get("document_id") or claims.get("ruc")
    if not documento_ruc:
        if sub:
            documento_ruc = f"KC-{sub[:8]}".upper()
        else:
            documento_ruc = f"DOC-{user.pk}"

    # Evitar colisión de documento_ruc si ya existiera
    base_doc = documento_ruc
    counter = 1
    while Cliente.objects.filter(documento_ruc=documento_ruc).exists():
        documento_ruc = f"{base_doc}-{counter}"
        counter += 1

    cliente = Cliente.objects.create(
        nombre=nombre_completo,
        documento_ruc=documento_ruc,
        correo=correo or f"{getattr(user, 'username', 'user')}@globalexchange.local",
        keycloak_id=sub,
        segmentacion=Cliente.Segmentacion.MINORISTA,
        is_active=True,
    )
    _asegurar_asignacion(cliente, es_principal=True)
    logger.info(
        "Nueva ficha de Cliente #%s creada y asignada automáticamente con Keycloak (sub=%s) para el usuario %s.",
        cliente.id,
        sub,
        getattr(user, "username", str(user)),
    )
    return cliente

