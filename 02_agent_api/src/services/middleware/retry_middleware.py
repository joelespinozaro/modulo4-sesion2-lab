"""RetryMiddleware — reintentos con backoff exponencial ante errores transitorios.

Hooks utilizados (wrap-style):
  - wrap_model_call  → versión sync, permite llamar al handler N veces
  - awrap_model_call → versión async, equivalente para ainvoke

A diferencia de los hooks node-style, wrap_model_call controla CUÁNTAS VECES
se llama al modelo (0 = short-circuit, 1 = normal, N = retry). Esto lo hace
el único mecanismo adecuado para implementar lógica de reintentos.
"""
import asyncio
import time
from typing import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse

from src.utils.logger import get_logger

logger = get_logger(__name__)


class RetryMiddleware(AgentMiddleware):
    """Reintentos con backoff exponencial ante errores transitorios del modelo.

    Reintenta la llamada al LLM hasta `max_retries` veces. Entre cada intento
    espera `base_delay * 2^intento` segundos (backoff exponencial).

    Casos de uso típicos: rate limit errors, timeouts, errores 5xx transitorios.

    Args:
        max_retries: número máximo de intentos (default: 3).
        base_delay:  tiempo base en segundos para el backoff (default: 1.0).
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0) -> None:
        super().__init__()
        self.max_retries = max_retries
        self.base_delay = base_delay

    # ── Versión SYNC ────────────────────────────────────────────────────────

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = handler(request)
                if attempt > 0:
                    logger.info(
                        "Retry exitoso",
                        extra={"middleware": "RetryMiddleware", "attempt": attempt + 1},
                    )
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        "Error en llamada al modelo, reintentando",
                        extra={
                            "middleware": "RetryMiddleware",
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "delay_s": delay,
                            "error": str(exc),
                        },
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Agotados todos los reintentos",
                        extra={
                            "middleware": "RetryMiddleware",
                            "max_retries": self.max_retries,
                            "error": str(exc),
                        },
                    )

        raise RuntimeError(
            f"RetryMiddleware: fallaron {self.max_retries} intentos. "
            f"Último error: {last_error}"
        ) from last_error

    # ── Versión ASYNC ───────────────────────────────────────────────────────

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await handler(request)
                if attempt > 0:
                    logger.info(
                        "Retry async exitoso",
                        extra={"middleware": "RetryMiddleware", "attempt": attempt + 1},
                    )
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        "Error en llamada async al modelo, reintentando",
                        extra={
                            "middleware": "RetryMiddleware",
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "delay_s": delay,
                            "error": str(exc),
                        },
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Agotados todos los reintentos async",
                        extra={
                            "middleware": "RetryMiddleware",
                            "max_retries": self.max_retries,
                            "error": str(exc),
                        },
                    )

        raise RuntimeError(
            f"RetryMiddleware: fallaron {self.max_retries} intentos async. "
            f"Último error: {last_error}"
        ) from last_error
