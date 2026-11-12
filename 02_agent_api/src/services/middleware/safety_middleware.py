"""SafetyGuardMiddleware — guardia de contenido con jump_to.

Hook utilizado (node-style):
  - after_model con @hook_config(can_jump_to=["end"])

Detecta términos prohibidos en la respuesta del modelo y corta la ejecución
del agente (jump_to="end") reemplazando el mensaje por una respuesta estándar.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.messages import AIMessage
from langgraph.runtime import Runtime

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Términos por defecto que activan el guard (case-insensitive)
DEFAULT_BLOCKED_TERMS: list[str] = [
    "BLOQUEADO",
    "CONTENIDO PROHIBIDO",
    "ACTIVIDAD ILEGAL",
]

BLOCKED_RESPONSE = (
    "Lo siento, no puedo ayudarte con esa consulta. "
    "Si tienes otra pregunta, estaré encantado de ayudarte."
)


class SafetyGuardMiddleware(AgentMiddleware):
    """Guardia de contenido que intercepta respuestas con términos prohibidos.

    Si la respuesta del modelo contiene algún término bloqueado, reemplaza
    el mensaje y detiene la ejecución del agente inmediatamente (jump_to='end').

    Args:
        blocked_terms: lista de términos prohibidos (case-insensitive).
                       Si no se pasa, usa DEFAULT_BLOCKED_TERMS.
    """

    def __init__(self, blocked_terms: list[str] | None = None) -> None:
        super().__init__()
        self.blocked_terms = [
            t.upper() for t in (blocked_terms or DEFAULT_BLOCKED_TERMS)
        ]

    @hook_config(can_jump_to=["end"])
    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        last_message = state["messages"][-1]
        content = str(getattr(last_message, "content", "")).upper()

        for term in self.blocked_terms:
            if term in content:
                logger.warning(
                    "Contenido bloqueado detectado",
                    extra={"middleware": "SafetyGuardMiddleware", "blocked_term": term},
                )
                return {
                    "messages": [AIMessage(content=BLOCKED_RESPONSE)],
                    "jump_to": "end",
                }

        return None  # flujo normal

    # ── Versión ASYNC ───────────────────────────────────────────────────────

    @hook_config(can_jump_to=["end"])
    async def aafter_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        last_message = state["messages"][-1]
        content = str(getattr(last_message, "content", "")).upper()

        for term in self.blocked_terms:
            if term in content:
                logger.warning(
                    "Contenido bloqueado detectado (async)",
                    extra={"middleware": "SafetyGuardMiddleware", "blocked_term": term},
                )
                return {
                    "messages": [AIMessage(content=BLOCKED_RESPONSE)],
                    "jump_to": "end",
                }

        return None
