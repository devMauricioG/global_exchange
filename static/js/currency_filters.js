/**
 * Módulo de utilidades JavaScript para formateo de cifras monetarias en Global Exchange.
 *
 * Convenciones (estándar paraguayo / latinoamericano):
 * - Separador de miles: punto (.)
 * - Separador decimal: coma (,)
 * - PYG (0 decimales): 7.500.000
 * - USD (2 decimales): 1.250,50
 *
 * Uso:
 *   formatMoney(7500000, 0)      → "7.500.000"
 *   formatMoney(1250.5, 2)       → "1.250,50"
 *   formatCurrency(1250.5, {symbol: '$', decimals: 2}) → "$ 1.250,50"
 */

window.GXCurrency = (function () {
    'use strict';

    /**
     * Formatea un valor numérico con separadores de miles (.) y decimales (,).
     *
     * @param {number|string} value - Valor numérico a formatear.
     * @param {number} [decimalPlaces=2] - Cantidad de dígitos decimales.
     * @returns {string} Cadena formateada.
     */
    function formatMoney(value, decimalPlaces) {
        if (value === null || value === undefined || value === '') return '';

        if (typeof decimalPlaces === 'undefined' || decimalPlaces === null) {
            decimalPlaces = 2;
        }
        decimalPlaces = Math.max(0, parseInt(decimalPlaces, 10) || 0);

        var num = parseFloat(String(value).replace(/\./g, '').replace(',', '.'));
        if (isNaN(num)) return String(value);

        var sign = num < 0 ? '-' : '';
        num = Math.abs(num);

        var fixed = num.toFixed(decimalPlaces);
        var parts = fixed.split('.');
        var intPart = parts[0];
        var decPart = parts.length > 1 ? parts[1] : '';

        // Agregar separadores de miles con puntos
        var formatted = '';
        for (var i = intPart.length - 1, count = 0; i >= 0; i--, count++) {
            if (count > 0 && count % 3 === 0) {
                formatted = '.' + formatted;
            }
            formatted = intPart[i] + formatted;
        }

        if (decimalPlaces > 0 && decPart) {
            return sign + formatted + ',' + decPart;
        }
        return sign + formatted;
    }

    /**
     * Formatea un monto con símbolo de divisa.
     *
     * @param {number|string} value - Valor numérico.
     * @param {Object} currency - Objeto con propiedades {symbol, decimals}.
     * @returns {string} Cadena con símbolo y monto formateado.
     */
    function formatCurrency(value, currency) {
        if (!currency) return formatMoney(value, 2);
        var decimals = currency.decimals !== undefined ? currency.decimals : 2;
        var symbol = currency.symbol || '';
        var formatted = formatMoney(value, decimals);
        if (symbol) {
            return symbol + ' ' + formatted;
        }
        return formatted;
    }

    /**
     * Formatea una tasa de cambio con precisión adecuada.
     *
     * @param {number|string} value - Valor de la tasa.
     * @param {number} [decimalPlaces] - Decimales explícitos (auto-detecta si no se provee).
     * @returns {string} Tasa formateada.
     */
    function formatRate(value, decimalPlaces) {
        if (value === null || value === undefined || value === '') return '';

        if (typeof decimalPlaces === 'undefined' || decimalPlaces === null) {
            var str = String(value);
            if (str.indexOf('.') !== -1) {
                var dec = str.split('.')[1].replace(/0+$/, '');
                decimalPlaces = Math.max(2, Math.min(dec.length, 6));
            } else {
                decimalPlaces = 2;
            }
        }
        return formatMoney(value, decimalPlaces);
    }

    /**
     * Aplica formateo en tiempo real a un campo de input numérico.
     * El valor real (sin formato) se mantiene en un input hidden asociado.
     *
     * @param {HTMLInputElement} input - Campo de texto visible.
     * @param {number} [decimals=2] - Cantidad de decimales para la moneda.
     */
    function bindInputFormatter(input, decimals) {
        if (!input) return;
        if (typeof decimals === 'undefined') decimals = 2;

        // Formatear el valor inicial si existe
        var initial = input.value;
        if (initial && !isNaN(parseFloat(initial))) {
            input.value = formatMoney(initial, decimals);
        }

        input.addEventListener('focus', function () {
            // Al enfocar, mostrar el valor sin formato para edición
            var raw = this.value.replace(/\./g, '').replace(',', '.');
            if (!isNaN(parseFloat(raw))) {
                this.value = raw;
            }
        });

        input.addEventListener('blur', function () {
            // Al perder foco, formatear el valor
            var raw = this.value.replace(/\./g, '').replace(',', '.');
            if (raw !== '' && !isNaN(parseFloat(raw))) {
                this.value = formatMoney(parseFloat(raw), decimals);
            }
        });
    }

    /**
     * Auto-formatea todos los elementos con data-format-money en la página.
     * Atributos soportados:
     *   data-format-money="2"   → formatea el textContent con 2 decimales
     *   data-format-money="0"   → formatea sin decimales
     *   data-currency-symbol    → antepone el símbolo
     */
    function autoFormatElements() {
        var elements = document.querySelectorAll('[data-format-money]');
        elements.forEach(function (el) {
            var decimals = parseInt(el.getAttribute('data-format-money'), 10);
            if (isNaN(decimals)) decimals = 2;
            var symbol = el.getAttribute('data-currency-symbol') || '';
            var rawValue = el.textContent.trim();

            if (rawValue && !isNaN(parseFloat(rawValue))) {
                var formatted = formatMoney(parseFloat(rawValue), decimals);
                el.textContent = symbol ? (symbol + ' ' + formatted) : formatted;
            }
        });
    }

    // Auto-ejecutar al cargar el DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoFormatElements);
    } else {
        autoFormatElements();
    }

    // API pública
    return {
        formatMoney: formatMoney,
        formatCurrency: formatCurrency,
        formatRate: formatRate,
        bindInputFormatter: bindInputFormatter,
        autoFormatElements: autoFormatElements
    };

})();
