"""
Cliente HTTP FacturaSeguraClient y Protocolo de Cuota con Reserva Blindada (SCRUM-120).

Implementa la conexión HTTP formal conforme al documento técnico:
'API de Factura Segura para ESI (External Systems Interoperation) v01'.

Características principales:

* Cliente HTTP nativo conectando al endpoint PAC:
  https://apitest.facturasegura.com.py/ (Test/Sandbox) o portal oficial (Prod).
* Operaciones oficiales del estándar ESI:
  login, calcular_de, generar_de, get_estado_sifen, dwn_kude, dwn_xml,
  sol_cancelacion y sol_inutilizacion.
* Bloqueo de seguridad estricto condicionado a FACTURA_SEGURA_LIVE_ENABLED=True.
* Protocolo de cuota inviolable con reserva blindada de 10 llamadas exclusivas
  para la presentación en vivo y suites de QA:

  - Si la cuota comercial ordinaria alcanza el umbral presupuestario,
    se bloquean peticiones con QuotaShieldExhaustedError.
  - Se preservan estrictamente 10 unidades de cuota para la presentación final.
"""

from datetime import datetime
import json
import logging
import threading
from typing import Any, Dict, Optional, Tuple, Union
import urllib.error
import urllib.request
import uuid

from django.conf import settings
from django.utils import timezone

from .exceptions import (
    InvoiceNotFoundError,
    InvoiceProviderError,
    InvoiceValidationError,
    LiveModeDisabledError,
    QuotaExhaustedError,
    QuotaShieldExhaustedError,
    TestQuotaExhaustedError,
)

logger = logging.getLogger(__name__)


class FacturaSeguraClient:
    """
    Cliente HTTP formal y gestor de cuotas para la API de Factura Segura PAC / ESI v01.

    Gestiona la conexión REST, autenticación vía Authentication-Token y la aplicación
    estricta del protocolo de cuotas con reserva blindada de 10 llamadas para presentación.
    """

    DEFAULT_TEST_URL = 'https://apitest.facturasegura.com.py'
    DEFAULT_PROD_URL = 'https://portal.facturasegura.com.py'
    RESERVA_BLINDADA_PRESENTACION_DEFAULT = 10
    DEFAULT_TOTAL_QUOTA = 100

    # Contadores compartidos en memoria (thread-safe)
    _lock = threading.Lock()
    _in_memory_total_quota: int = DEFAULT_TOTAL_QUOTA
    _in_memory_used_quota: int = 0
    _in_memory_test_reserved: int = RESERVA_BLINDADA_PRESENTACION_DEFAULT
    _in_memory_test_used: int = 0

    def __init__(
        self,
        api_url: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        auth_token: Optional[str] = None,
        emisor_ruc: Optional[str] = None,
        timeout: int = 15,
        config: Optional[Any] = None,
    ):
        self.api_url = (api_url or getattr(settings, 'FACTURA_SEGURA_API_URL', self.DEFAULT_TEST_URL)).rstrip('/')
        self.email = email or getattr(settings, 'FACTURA_SEGURA_EMAIL', '')
        self.password = password or getattr(settings, 'FACTURA_SEGURA_PASSWORD', '')
        self._auth_token = auth_token or getattr(settings, 'FACTURA_SEGURA_TOKEN', '')
        self.emisor_ruc = emisor_ruc or getattr(settings, 'FACTURA_SEGURA_EMISOR_RUC', '80012345')
        self.timeout = timeout
        self._config = config

    # -------------------------------------------------------------------------
    # Seguridad y Modo Live
    # -------------------------------------------------------------------------

    @property
    def is_live_enabled(self) -> bool:
        """Indica si el entorno permite la ejecución de peticiones reales en vivo."""
        return bool(getattr(settings, 'FACTURA_SEGURA_LIVE_ENABLED', False))

    def _ensure_live_allowed(self) -> None:
        """
        Valida que no se realicen llamadas externas si el modo live está desactivado.
        Previene consumo inadvertido de créditos o cuota real durante desarrollo y tests.
        """
        if not self.is_live_enabled:
            raise LiveModeDisabledError(
                "La integración en vivo con la API de Factura Segura se encuentra desactivada "
                "(FACTURA_SEGURA_LIVE_ENABLED=False). Use MockInvoiceProvider para desarrollo y tests."
            )

    # -------------------------------------------------------------------------
    # Protocolo de Cuota y Reserva Blindada (Contador Estricto)
    # -------------------------------------------------------------------------

    def get_db_config(self) -> Optional[Any]:
        """Obtiene el modelo persistente FacturaSeguraConfig si la app transactions está disponible."""
        if self._config:
            return self._config
        try:
            from transactions.models import FacturaSeguraConfig
            self._config = FacturaSeguraConfig.get_config()
            return self._config
        except Exception:
            return None

    @property
    def total_quota(self) -> int:
        """Retorna la cuota total presupuestada."""
        cfg = self.get_db_config()
        if cfg:
            return cfg.total_quota
        return self._in_memory_total_quota

    @property
    def used_quota(self) -> int:
        """Retorna la cantidad de peticiones ordinarias/comerciales consumidas."""
        cfg = self.get_db_config()
        if cfg:
            return cfg.used_quota
        return self._in_memory_used_quota

    @property
    def test_quota_reserved(self) -> int:
        """Retorna la cantidad de llamadas blindadas exclusivamente para la presentación/QA (10)."""
        cfg = self.get_db_config()
        if cfg:
            return cfg.test_quota_reserved
        return self._in_memory_test_reserved

    @property
    def test_quota_used(self) -> int:
        """Retorna la cantidad de llamadas de presentación/QA consumidas de la reserva blindada."""
        cfg = self.get_db_config()
        if cfg:
            return cfg.test_quota_used
        return self._in_memory_test_used

    @property
    def operational_quota_available(self) -> int:
        """
        Retorna la cuota comercial disponible antes de alcanzar el umbral de la reserva blindada.
        Garantiza que nunca se toquen las 10 llamadas protegidas para la presentación.
        """
        disponible = self.total_quota - self.used_quota - self.test_quota_reserved
        return max(0, disponible)

    @property
    def test_quota_available(self) -> int:
        """Retorna la cuota restante de la reserva blindada de 10 pruebas/presentación."""
        return max(0, self.test_quota_reserved - self.test_quota_used)

    @property
    def is_operational_quota_exhausted(self) -> bool:
        """Indica si la cuota comercial ordinaria se ha agotado (alcanzando el umbral blindado)."""
        return self.operational_quota_available == 0

    @property
    def is_test_quota_exhausted(self) -> bool:
        """Indica si la reserva blindada de 10 pruebas/presentación se ha consumido por completo."""
        return self.test_quota_available == 0

    def consume_quota(self, is_test: bool = False, is_presentation: bool = False) -> int:
        """
        Ejecuta el protocolo de consumo de cuota estricto.

        - Si no es prueba ni presentación (operación comercial ordinaria):
          Consume del saldo comercial. Si el saldo alcanza el umbral de las 10 llamadas blindadas,
          bloquea la petición disparando QuotaShieldExhaustedError.
        - Si es prueba o presentación:
          Consume de la reserva blindada de 10 unidades. Si se agotan, dispara TestQuotaExhaustedError.

        :param is_test: Flag booleano que identifica llamadas de prueba/QA.
        :param is_presentation: Flag booleano que identifica llamadas de la presentación en vivo.
        :raises QuotaShieldExhaustedError: Si se agota la cuota comercial ordinaria.
        :raises TestQuotaExhaustedError: Si se agotan las 10 llamadas de la reserva blindada.
        :return: Cuota restante disponible para la categoría invocada.
        """
        is_shield_call = bool(is_test or is_presentation)

        with self._lock:
            cfg = self.get_db_config()

            if not is_shield_call:
                if self.operational_quota_available <= 0:
                    raise QuotaShieldExhaustedError(
                        f"Cuota comercial ordinaria agotada (Total: {self.total_quota}, Usadas: {self.used_quota}). "
                        f"Las {self.test_quota_reserved} llamadas restantes se encuentran blindadas exclusivamente "
                        f"para la presentación en vivo y QA."
                    )
                if cfg:
                    cfg.used_quota += 1
                    cfg.save(update_fields=['used_quota', 'updated_at'])
                else:
                    FacturaSeguraClient._in_memory_used_quota += 1
                return self.operational_quota_available
            else:
                if self.test_quota_available <= 0:
                    raise TestQuotaExhaustedError(
                        f"Reserva blindada de {self.test_quota_reserved} llamadas para presentación/QA agotada "
                        f"({self.test_quota_used}/{self.test_quota_reserved} consumidas)."
                    )
                if cfg:
                    cfg.test_quota_used += 1
                    cfg.save(update_fields=['test_quota_used', 'updated_at'])
                else:
                    FacturaSeguraClient._in_memory_test_used += 1
                return self.test_quota_available

    def consultar_cuota(self) -> Dict[str, Any]:
        """
        Consulta y audita el estado del balance de cuotas en tiempo real.

        :return: Diccionario estructurado con métricas de cuota y estado del blindaje.
        """
        cfg = self.get_db_config()
        if cfg:
            try:
                cfg.refresh_from_db()
            except Exception:
                pass

        env = 'SANDBOX' if 'test' in self.api_url.lower() else 'PRODUCTION'
        return {
            'total_quota': self.total_quota,
            'used_quota': self.used_quota,
            'operational_quota_available': self.operational_quota_available,
            'test_quota_reserved': self.test_quota_reserved,
            'test_quota_used': self.test_quota_used,
            'test_quota_available': self.test_quota_available,
            'is_operational_quota_exhausted': self.is_operational_quota_exhausted,
            'is_test_quota_exhausted': self.is_test_quota_exhausted,
            'is_live_enabled': self.is_live_enabled,
            'shield_active': True,
            'api_url': self.api_url,
            'environment': env,
        }

    def reset_quotas(self, total: int = 100) -> None:
        """Reinicia los contadores de cuota (utilidad para tests unitarios y administración)."""
        with self._lock:
            FacturaSeguraClient._in_memory_total_quota = total
            FacturaSeguraClient._in_memory_used_quota = 0
            FacturaSeguraClient._in_memory_test_reserved = self.RESERVA_BLINDADA_PRESENTACION_DEFAULT
            FacturaSeguraClient._in_memory_test_used = 0

            cfg = self.get_db_config()
            if cfg:
                try:
                    cfg.total_quota = total
                    cfg.used_quota = 0
                    cfg.test_quota_reserved = self.RESERVA_BLINDADA_PRESENTACION_DEFAULT
                    cfg.test_quota_used = 0
                    cfg.save()
                except Exception:
                    pass

    def replenish_quota(self, amount: int = 100) -> None:
        """Incrementa la cuota comercial total asignada."""
        with self._lock:
            FacturaSeguraClient._in_memory_total_quota += amount
            cfg = self.get_db_config()
            if cfg:
                try:
                    cfg.total_quota += amount
                    cfg.save(update_fields=['total_quota', 'updated_at'])
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # Operaciones HTTP Formales (ESI v01)
    # -------------------------------------------------------------------------

    def login(self, email: Optional[str] = None, password: Optional[str] = None) -> str:
        """
        Ejecuta la autenticación de credenciales ESI contra POST /login?include_auth_token.

        Retorna y almacena en caché interna el token de sesión Authentication-Token.
        """
        self._ensure_live_allowed()

        user_email = email or self.email
        user_password = password or self.password

        if not user_email or not user_password:
            raise InvoiceProviderError(
                "Credenciales no configuradas para Factura Segura (email o password faltantes).",
                status_code=401,
            )

        login_url = f"{self.api_url}/login?include_auth_token"
        payload = json.dumps({'email': user_email, 'password': user_password}).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        req = urllib.request.Request(login_url, data=payload, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                token = (
                    data.get('response', {})
                    .get('user', {})
                    .get('authentication_token')
                )
                if not token:
                    raise InvoiceProviderError(
                        "Respuesta de login no contiene authentication_token válido.",
                        status_code=401,
                        error_details=data,
                    )
                self._auth_token = token
                return token
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            raise InvoiceProviderError(
                f"Error en login contra Factura Segura: {e.reason}",
                status_code=e.code,
                error_details={'response': err_body},
            )
        except Exception as e:
            if isinstance(e, InvoiceProviderError):
                raise
            raise InvoiceProviderError(f"Falla de red en autenticación Factura Segura: {e}")

    def get_auth_token(self) -> str:
        """Retorna el token en caché o ejecuta login si aún no fue adquirido."""
        if self._auth_token:
            return self._auth_token
        return self.login()

    def _post_esi(
        self,
        operation: str,
        params: Dict[str, Any],
        is_test: bool = False,
        is_presentation: bool = False,
    ) -> Dict[str, Any]:
        """
        Ejecuta una petición estándar al webservice ESI /misife00/v1/esi aplicando
        el envelope formal, validación live y control estricto de cuota.
        """
        self._ensure_live_allowed()
        self.consume_quota(is_test=is_test, is_presentation=is_presentation)

        token = self.get_auth_token()
        url = f"{self.api_url}/misife00/v1/esi"

        body = json.dumps({'operation': operation, 'params': params}).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authentication-Token': token,
        }

        req = urllib.request.Request(url, data=body, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            err_text = e.read().decode('utf-8', errors='replace')
            raise InvoiceProviderError(
                f"Error HTTP {e.code} en operación '{operation}': {e.reason}",
                status_code=e.code,
                error_details={'raw': err_text},
            )
        except Exception as e:
            if isinstance(e, InvoiceProviderError):
                raise
            raise InvoiceProviderError(f"Error de comunicación en '{operation}': {e}")

        code = result.get('code', 0)
        if code < 0:
            description = result.get('description', 'Error en webservice Factura Segura')
            if 'cuota' in description.lower() or 'saldo' in description.lower() or code == -10099:
                raise QuotaExhaustedError(description, status_code=code, error_details=result)
            raise InvoiceProviderError(description, status_code=code, error_details=result)

        return result

    def calcular_de(
        self,
        de_data: Dict[str, Any],
        is_test: bool = False,
        is_presentation: bool = False,
    ) -> Dict[str, Any]:
        """
        Invoca la operación calcular_de en Factura Segura PAC.

        Retorna el documento electrónico enriquecido con cálculos de subtotales, IVA y totales.
        """
        resp = self._post_esi(
            'calcular_de',
            {'DE': de_data},
            is_test=is_test,
            is_presentation=is_presentation,
        )
        results = resp.get('results', [])
        if results and isinstance(results[0], dict) and 'DE' in results[0]:
            return results[0]['DE']
        return de_data

    def generar_de(
        self,
        de_data: Dict[str, Any],
        is_test: bool = False,
        is_presentation: bool = False,
    ) -> Dict[str, Any]:
        """
        Invoca la operación generar_de en Factura Segura PAC.

        Construye el lote, firma criptográficamente el DTE y despacha a SIFEN.
        Retorna el resultado estructurado conteniendo el CDC de 44 dígitos generado.
        """
        resp = self._post_esi(
            'generar_de',
            {'DE': de_data},
            is_test=is_test,
            is_presentation=is_presentation,
        )
        results = resp.get('results', [])
        if not results or not isinstance(results[0], dict) or 'CDC' not in results[0]:
            raise InvoiceProviderError(
                "La respuesta de generar_de no retornó un CDC válido.",
                error_details=resp,
            )
        return resp

    def get_estado_sifen(
        self,
        cdc: str,
        ruc_emisor: Optional[str] = None,
        is_test: bool = False,
        is_presentation: bool = False,
    ) -> Dict[str, Any]:
        """
        Invoca la operación get_estado_sifen con parámetros CDC y dRucEm.

        Consulta en el webservice de Factura Segura el estado tributario del DTE.
        """
        ruc = (ruc_emisor or self.emisor_ruc).split('-')[0].strip()
        return self._post_esi(
            'get_estado_sifen',
            {'CDC': cdc, 'dRucEm': ruc},
            is_test=is_test,
            is_presentation=is_presentation,
        )

    def sol_cancelacion(
        self,
        cdc: str,
        motivo: str = '',
        ruc_emisor: Optional[str] = None,
        is_test: bool = False,
        is_presentation: bool = False,
    ) -> Dict[str, Any]:
        """
        Invoca la operación sol_cancelacion en Factura Segura PAC.
        """
        ruc = (ruc_emisor or self.emisor_ruc).split('-')[0].strip()
        params = {'CDC': cdc, 'dRucEm': ruc}
        if motivo:
            params['dMotivo'] = motivo
        return self._post_esi(
            'sol_cancelacion',
            params,
            is_test=is_test,
            is_presentation=is_presentation,
        )

    def sol_inutilizacion(
        self,
        ruc_emisor: str,
        timbrado: str,
        est: str,
        pun_exp: str,
        num_doc: str,
        tipo_de: str = '1',
        is_test: bool = False,
        is_presentation: bool = False,
    ) -> Dict[str, Any]:
        """
        Invoca la operación sol_inutilizacion en Factura Segura PAC.
        """
        ruc = ruc_emisor.split('-')[0].strip()
        params = {
            'dRucEm': ruc,
            'iTiDE': str(tipo_de),
            'dNumTim': str(timbrado),
            'dEst': str(est).zfill(3),
            'dPunExp': str(pun_exp).zfill(3),
            'dNumDoc': str(num_doc).zfill(7),
        }
        return self._post_esi(
            'sol_inutilizacion',
            params,
            is_test=is_test,
            is_presentation=is_presentation,
        )

    def dwn_kude(
        self,
        cdc: str,
        ruc_emisor: Optional[str] = None,
        is_test: bool = False,
        is_presentation: bool = False,
    ) -> bytes:
        """
        Descarga el KuDE en formato PDF mediante HTTP GET.
        URI: /misife00/v1/esi/dwn_kude/{dRucEm}/{CDC}
        """
        self._ensure_live_allowed()
        self.consume_quota(is_test=is_test, is_presentation=is_presentation)

        token = self.get_auth_token()
        ruc = (ruc_emisor or self.emisor_ruc).split('-')[0].strip()
        url = f"{self.api_url}/misife00/v1/esi/dwn_kude/{ruc}/{cdc}"

        headers = {'Authentication-Token': token}
        req = urllib.request.Request(url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            err_text = e.read().decode('utf-8', errors='replace')
            raise InvoiceProviderError(
                f"Error descargando KuDE para CDC {cdc} (HTTP {e.code}): {e.reason}",
                status_code=e.code,
                error_details={'raw': err_text},
            )
        except Exception as e:
            if isinstance(e, InvoiceProviderError):
                raise
            raise InvoiceProviderError(f"Error descargando KuDE para CDC {cdc}: {e}")

    def dwn_xml(
        self,
        cdc: str,
        ruc_emisor: Optional[str] = None,
        is_test: bool = False,
        is_presentation: bool = False,
    ) -> str:
        """
        Descarga el XML firmado mediante HTTP GET.
        URI: /misife00/v1/esi/dwn_xml/{dRucEm}/{CDC}
        """
        self._ensure_live_allowed()
        self.consume_quota(is_test=is_test, is_presentation=is_presentation)

        token = self.get_auth_token()
        ruc = (ruc_emisor or self.emisor_ruc).split('-')[0].strip()
        url = f"{self.api_url}/misife00/v1/esi/dwn_xml/{ruc}/{cdc}"

        headers = {'Authentication-Token': token}
        req = urllib.request.Request(url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            err_text = e.read().decode('utf-8', errors='replace')
            raise InvoiceProviderError(
                f"Error descargando XML firmado para CDC {cdc} (HTTP {e.code}): {e.reason}",
                status_code=e.code,
                error_details={'raw': err_text},
            )
        except Exception as e:
            if isinstance(e, InvoiceProviderError):
                raise
            raise InvoiceProviderError(f"Error descargando XML firmado para CDC {cdc}: {e}")

