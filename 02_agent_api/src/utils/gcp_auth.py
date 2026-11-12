"""Autenticación service-to-service vía ID tokens de Google (Cloud Run → Cloud
Run privado, ej. hacia 03_mcp_server — ver DEPLOYMENT.md).

`GoogleIDTokenAuth` es un `httpx.Auth` (no un header estático): los ID tokens
de Google expiran (~1h), y una conexión MCP puede vivir mientras dure el
proceso — un header fijado una sola vez al arrancar se volvería inválido. Acá
se cachea el token y se refresca cuando falta poco para expirar, en vez de
pedir uno nuevo en cada request.

Fail-open: si no se puede obtener un token (ej. dev local sin credenciales de
service account), se seguiría sin el header — en producción, si de verdad
falta el token, el Cloud Run destino (privado) igual rechaza con 401/403, así
que fallar abierto acá no baja la seguridad real; en local, contra un server
sin auth, simplemente no hace falta."""
import time
from typing import Generator, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Margen de refresco: pedir un token nuevo si al actual le queda menos que esto.
_REFRESH_MARGIN_SECONDS = 60


def cloud_run_audience(url: str) -> str:
    """Devuelve la audiencia aceptada por Cloud Run para una URL HTTP.

    El cliente MCP apunta a ``https://servicio.run.app/mcp``, pero Cloud Run
    valida el ID token contra el origen del servicio, sin path, query ni
    fragment. Para URLs locales se aplica la misma normalización, aunque en
    ese entorno normalmente no haya credenciales ni validación de tokens.
    """
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"URL de servicio inválida: {url!r}")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


class GoogleIDTokenAuth(httpx.Auth):
    """Agrega `Authorization: Bearer <ID token>` para la audiencia dada,
    refrescando el token cuando está por expirar."""

    def __init__(self, audience: str) -> None:
        self._audience = audience
        self._token: Optional[str] = None
        self._expiry: float = 0.0

    def _fetch_token(self) -> Optional[str]:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token as google_id_token

            token = google_id_token.fetch_id_token(Request(), self._audience)
            self._token = token
            # Los ID tokens de Google duran ~1h; no decodificamos el JWT acá
            # (no hace falta la librería completa solo para leer `exp`) —
            # asumimos la duración estándar y refrescamos con margen.
            self._expiry = time.time() + 3600 - _REFRESH_MARGIN_SECONDS
            return token
        except Exception as exc:  # noqa: BLE001 - fail-open, ver docstring del módulo
            logger.warning(
                "No se pudo obtener ID token de Google para %s (%s). "
                "Continuando sin header de autenticación.",
                self._audience,
                exc,
            )
            return None

    def _get_valid_token(self) -> Optional[str]:
        if self._token is None or time.time() >= self._expiry:
            return self._fetch_token()
        return self._token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        token = self._get_valid_token()
        if token:
            request.headers["Authorization"] = f"Bearer {token}"
        yield request
