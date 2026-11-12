"""LoggingMiddleware — logging estructurado de cada llamada al modelo.

Hooks utilizados (node-style):
  - before_model / abefore_model  → registra inicio de llamada y mensajes en contexto
  - after_model  / aafter_model   → registra tokens consumidos y tiempo de respuesta
"""
import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(AgentMiddleware):
    """Logging estructurado de cada llamada al modelo.

    Registra antes de cada llamada: número de mensajes en contexto.
    Registra después de cada llamada: tiempo transcurrido y tokens consumidos.
    Implementa versiones sync y async para compatibilidad con invoke/ainvoke.
    """

    # Variable de instancia para medir tiempo entre before y after
    _start_time: float = 0.0

    # ── Hooks SYNC ──────────────────────────────────────────────────────────

    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        self._start_time = time.perf_counter()
        msg_count = len(state["messages"])
        logger.info(
            "before_model",
            extra={"middleware": "LoggingMiddleware", "messages_in_context": msg_count},
        )
        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        elapsed_ms = round((time.perf_counter() - self._start_time) * 1000, 2)
        last_msg = state["messages"][-1]
        usage = getattr(last_msg, "usage_metadata", None) or {}
        logger.info(
            "after_model",
            extra={
                "middleware": "LoggingMiddleware",
                "elapsed_ms": elapsed_ms,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            },
        )
        return None

    # ── Hooks ASYNC (para ainvoke) ──────────────────────────────────────────

    async def abefore_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        self._start_time = time.perf_counter()
        msg_count = len(state["messages"])
        logger.info(
            "abefore_model",
            extra={"middleware": "LoggingMiddleware", "messages_in_context": msg_count},
        )
        return None

    async def aafter_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        elapsed_ms = round((time.perf_counter() - self._start_time) * 1000, 2)
        last_msg = state["messages"][-1]
        usage = getattr(last_msg, "usage_metadata", None) or {}
        logger.info(
            "aafter_model",
            extra={
                "middleware": "LoggingMiddleware",
                "elapsed_ms": elapsed_ms,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            },
        )
        return None
