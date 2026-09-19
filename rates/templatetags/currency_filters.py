"""
Módulo de etiquetas y filtros de plantilla para formateo de cifras monetarias.

Provee filtros reutilizables para visualizar montos con separadores de miles (punto),
separadores decimales (coma) y precisión decimal dinámica según la divisa configurada
en el modelo :class:`~rates.models.Currency`.

Convenciones de formato (estándar paraguayo / latinoamericano):
- Separador de miles: punto (.)
- Separador decimal: coma (,)
- Ejemplo PYG (0 decimales): 7.500.000
- Ejemplo USD (2 decimales): 1.250,50

Uso en plantillas:
    .. code-block:: django

        {% load currency_filters %}

        {{ monto|format_currency:currency_obj }}
        {{ monto|format_number:2 }}
        {{ valor|format_rate }}
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django import template

register = template.Library()


def _format_number(value, decimal_places=2):
    """
    Formatea un valor numérico con separadores de miles (.) y decimales (,).

    :param value: Valor numérico a formatear.
    :type value: int, float, Decimal, str
    :param decimal_places: Cantidad de dígitos decimales a mostrar.
    :type decimal_places: int
    :return: Cadena formateada (ej. '7.500.000' o '1.250,50').
    :rtype: str
    """
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)

    decimal_places = max(0, int(decimal_places))

    if decimal_places > 0:
        quantize_str = '0.' + '0' * decimal_places
        d = d.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
    else:
        d = d.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    sign = '-' if d < 0 else ''
    d = abs(d)
    str_value = str(d)

    if '.' in str_value:
        int_part, dec_part = str_value.split('.', 1)
    else:
        int_part = str_value
        dec_part = ''

    # Agregar separadores de miles con puntos
    formatted_int = ''
    for i, digit in enumerate(reversed(int_part)):
        if i > 0 and i % 3 == 0:
            formatted_int = '.' + formatted_int
        formatted_int = digit + formatted_int

    if decimal_places > 0 and dec_part:
        # Asegurar que la parte decimal tenga la longitud correcta
        dec_part = dec_part.ljust(decimal_places, '0')[:decimal_places]
        return f'{sign}{formatted_int},{dec_part}'
    else:
        return f'{sign}{formatted_int}'


@register.filter(name='format_currency')
def format_currency(value, currency=None):
    """
    Filtro de plantilla que formatea un monto según la configuración de la divisa.

    Si se pasa un objeto Currency, utiliza sus decimales configurados y antepone
    el símbolo. Si no se provee, usa 2 decimales por defecto.

    Uso en plantilla:
        .. code-block:: django

            {{ monto|format_currency:currency_obj }}
            {# Resultado: $ 1.250,50 o ₲ 7.500.000 #}

    :param value: Monto numérico a formatear.
    :type value: int, float, Decimal, str
    :param currency: Instancia del modelo Currency (opcional).
    :type currency: rates.models.Currency or None
    :return: Cadena con el monto formateado, opcionalmente precedido por el símbolo.
    :rtype: str
    """
    if value is None or value == '':
        return ''

    if currency is not None:
        decimals = getattr(currency, 'decimals', getattr(currency, 'decimal_places', 2))
        symbol = getattr(currency, 'symbol', '')
        formatted = _format_number(value, decimals)
        if symbol:
            return f'{symbol} {formatted}'
        return formatted

    return _format_number(value, 2)


@register.filter(name='format_number')
def format_number(value, decimal_places=2):
    """
    Filtro de plantilla que formatea un valor numérico con una cantidad fija de decimales.

    Uso en plantilla:
        .. code-block:: django

            {{ monto|format_number:0 }}    {# 7.500.000 #}
            {{ monto|format_number:2 }}    {# 1.250,50 #}
            {{ monto|format_number }}      {# 1.250,50 (default 2 decimales) #}

    :param value: Monto numérico a formatear.
    :type value: int, float, Decimal, str
    :param decimal_places: Número de decimales a mostrar (default: 2).
    :type decimal_places: int
    :return: Cadena formateada con separadores de miles y decimales.
    :rtype: str
    """
    if value is None or value == '':
        return ''
    try:
        decimal_places = int(decimal_places)
    except (TypeError, ValueError):
        decimal_places = 2
    return _format_number(value, decimal_places)


@register.filter(name='format_rate')
def format_rate(value, decimal_places=None):
    """
    Filtro de plantilla para formatear tasas de cambio con precisión cambiaria.

    Si no se especifican decimales, utiliza 2 si el valor tiene hasta 2 decimales
    significativos, o hasta 6 decimales si tiene mayor precisión.

    Uso en plantilla:
        .. code-block:: django

            {{ rate.buy_rate|format_rate }}     {# 7.450,00 o 0,000134 #}
            {{ rate.spread|format_rate:4 }}     {# 150,0000 #}

    :param value: Tasa numérica a formatear.
    :type value: int, float, Decimal, str
    :param decimal_places: Decimales forzados (opcional).
    :type decimal_places: int or None
    :return: Cadena formateada.
    :rtype: str
    """
    if value is None or value == '':
        return ''

    if decimal_places is not None:
        try:
            decimal_places = int(decimal_places)
        except (TypeError, ValueError):
            decimal_places = None

    if decimal_places is None:
        try:
            d = Decimal(str(value))
            # Determinar decimales significativos reales
            sign, digits, exponent = d.as_tuple()
            if exponent >= 0:
                decimal_places = 2
            else:
                actual_decimals = abs(exponent)
                # Verificar si los decimales finales son ceros
                str_val = str(d)
                if '.' in str_val:
                    dec_str = str_val.split('.')[1].rstrip('0')
                    significant = len(dec_str) if dec_str else 0
                else:
                    significant = 0
                decimal_places = max(2, min(significant, 6))
        except (InvalidOperation, TypeError, ValueError):
            decimal_places = 2

    return _format_number(value, decimal_places)
