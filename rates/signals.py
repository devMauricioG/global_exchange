"""
Receptores de señales de Django para la aplicación de tasas (rates).

Conecta el guardado de cotizaciones (:class:`~rates.models.ExchangeRate`) con
la evaluación de las suscripciones de alerta (:class:`~rates.models.RateAlertSubscription`)
y el despacho de notificaciones internas y correos electrónicos.
"""

import logging
from decimal import Decimal
from typing import List

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from customers.models import CustomerUserAssignment
from .models import ExchangeRate, RateAlertSubscription, UserNotification

logger = logging.getLogger(__name__)


def _formatear_tasa(valor: Decimal) -> str:
    """
    Formatea una tasa sin ceros decimales sobrantes.

    :param valor: Tasa a formatear.
    :type valor: decimal.Decimal
    :return: Representación legible (ej. ``7500`` o ``7432.55``).
    :rtype: str
    """
    return f'{valor.normalize():f}'


def _umbral_cruzado(suscripcion: RateAlertSubscription, tasa: Decimal) -> bool:
    """
    Evalúa si una tasa cumple la condición de una suscripción.

    :param suscripcion: Suscripción a evaluar.
    :type suscripcion: rates.models.RateAlertSubscription
    :param tasa: Tasa aplicable a la operación de la suscripción.
    :type tasa: decimal.Decimal
    :return: True si la tasa es mayor o igual (GTE) o menor o igual (LTE) al umbral.
    :rtype: bool
    """
    if suscripcion.condicion == RateAlertSubscription.Condicion.MAYOR_IGUAL:
        return tasa >= suscripcion.tasa_umbral
    return tasa <= suscripcion.tasa_umbral


def _enviar_correo(asunto: str, cuerpo: str, destinatarios: List[str], suscripcion_id: int) -> None:
    """
    Envía el correo de una alerta y registra el resultado en el log.

    Cualquier error de envío se captura y se registra para que nunca
    interrumpa el guardado de la cotización.

    :param asunto: Asunto del correo.
    :param cuerpo: Cuerpo del correo en texto plano.
    :param destinatarios: Direcciones de destino.
    :param suscripcion_id: Identificador de la suscripción que originó el aviso.
    """
    try:
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, destinatarios, fail_silently=False)
        logger.info(
            'Correo de alerta enviado (suscripción %s) a: %s',
            suscripcion_id, ', '.join(destinatarios),
        )
    except Exception:
        logger.exception('Falló el envío del correo de alerta (suscripción %s).', suscripcion_id)


def _despachar_alerta(suscripcion: RateAlertSubscription, tasa: Decimal) -> None:
    """
    Crea las notificaciones internas, programa el correo y desactiva la suscripción.

    Las notificaciones se dirigen a todos los usuarios con una asignación activa
    sobre el cliente de la suscripción. La suscripción es de un solo disparo:
    queda inactiva una vez notificada.

    :param suscripcion: Suscripción cuya condición se cumplió.
    :param tasa: Tasa que cruzó el umbral.
    """
    usuarios = [
        asignacion.user
        for asignacion in CustomerUserAssignment.objects.filter(
            customer=suscripcion.cliente, is_active=True,
        ).select_related('user')
    ]
    if not usuarios:
        logger.warning(
            'La alerta %s se cumplió pero el cliente %s no tiene usuarios asignados.',
            suscripcion.pk, suscripcion.cliente_id,
        )
        return

    par = f'{suscripcion.base_currency.code}/{suscripcion.target_currency.code}'
    simbolo = '≥' if suscripcion.condicion == RateAlertSubscription.Condicion.MAYOR_IGUAL else '≤'
    titulo = f'Alerta de cotización {par}'
    mensaje = (
        f'La tasa de {suscripcion.get_tipo_operacion_display().lower()} {par} '
        f'llegó a {_formatear_tasa(tasa)} (umbral configurado: {simbolo} '
        f'{_formatear_tasa(suscripcion.tasa_umbral)}).'
    )

    UserNotification.objects.bulk_create([
        UserNotification(usuario=usuario, titulo=titulo, mensaje=mensaje)
        for usuario in usuarios
    ])

    destinatarios = [usuario.email for usuario in usuarios if usuario.email]
    if destinatarios:
        transaction.on_commit(
            lambda: _enviar_correo(titulo, mensaje, destinatarios, suscripcion.pk)
        )

    suscripcion.activo = False
    suscripcion.save(update_fields=['activo', 'updated_at'])


@receiver(post_save, sender=ExchangeRate, dispatch_uid='rates_evaluar_alertas_cotizacion')
def evaluar_alertas_cotizacion(sender, instance: ExchangeRate, raw: bool = False, **kwargs) -> None:
    """
    Evalúa las suscripciones activas cada vez que se guarda una cotización.

    Solo considera cotizaciones vigentes (:attr:`ExchangeRate.is_current`) y
    suscripciones activas del mismo par de monedas. La tasa comparada se obtiene
    con :meth:`ExchangeRate.get_rate_for_operation`, según el tipo de operación
    de cada suscripción.

    :param sender: Modelo emisor de la señal (:class:`ExchangeRate`).
    :param instance: Cotización recién guardada.
    :param raw: True cuando se guarda desde una fixture; en ese caso no se evalúa.
    """
    if raw or not instance.is_current:
        return

    suscripciones = RateAlertSubscription.objects.filter(
        activo=True,
        base_currency_id=instance.base_currency_id,
        target_currency_id=instance.target_currency_id,
    ).select_related('cliente', 'base_currency', 'target_currency')

    for suscripcion in suscripciones:
        tasa = instance.get_rate_for_operation(suscripcion.tipo_operacion)
        if _umbral_cruzado(suscripcion, tasa):
            _despachar_alerta(suscripcion, tasa)