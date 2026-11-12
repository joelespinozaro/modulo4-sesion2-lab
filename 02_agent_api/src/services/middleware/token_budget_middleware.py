"""TokenBudgetMiddleware — control de presupuesto de tokens con estado personalizado.

Hooks utilizados (node-style):
  - before_model con @hook_config(can_jump_to=["end"]) → verifica si el budget está agotado
  - after_model → acumula tokens de la respuesta en el estado

Demuestra el uso de `state_schema` para extender AgentState con campos personalizados
que persisten a lo largo de toda la invocación del agente.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.messages import AIMessage
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

from src.utils.logger import get_logger

logger = get_logger(__name__)

BUDGET_EXCEEDED_RESPONSE = (
    "He alcanzado el límite de procesamiento configurado para esta sesión. "
    "Por favor, inicia una nueva conversación."
)


class TokenBudgetState(AgentState):
    """AgentState extendido con contador acumulado de tokens.

    El campo `token_count` persiste entre iteraciones del loop del agente
    y se puede inicializar al llamar a invoke/ainvoke.
    """

    token_count: NotRequired[int]


class TokenBudgetMiddleware(AgentMiddleware):
    """Controla el presupuesto de tokens por invocación.

    Acumula los tokens consumidos en el estado del agente y detiene la
    ejecución si se supera el presupuesto configurado.

    Args:
        budget: número máximo de tokens permitidos por invocación (default: 4000).

    Atributos de clase:
        state_schema: registra TokenBudgetState en el agente para que el campo
                      `token_count` esté disponible en todos los hooks.
    """

    state_schema = TokenBudgetState  # ← el agente usa este schema extendido

    def __init__(self, budget: int = 4000) -> None:
        super().__init__()
        self.budget = budget

    # ── VERIFICA antes de llamar al modelo ──────────────────────────────────

    @hook_config(can_jump_to=["end"])
    def before_model(
        self, state: TokenBudgetState, runtime: Runtime
    ) -> dict[str, Any] | None:
        current = state.get("token_count", 0)
        logger.info(
            "before_model: verificando presupuesto",
            extra={
                "middleware": "TokenBudgetMiddleware",
                "token_count": current,
                "budget": self.budget,
            },
        )
        if current >= self.budget:
            logger.warning(
                "Presupuesto de tokens agotado",
                extra={"middleware": "TokenBudgetMiddleware", "token_count": current},
            )
            return {
                "messages": [AIMessage(content=BUDGET_EXCEEDED_RESPONSE)],
                "jump_to": "end",
            }
        return None

    # ── ACUMULA tokens después de la respuesta ──────────────────────────────

    def after_model(
        self, state: TokenBudgetState, runtime: Runtime
    ) -> dict[str, Any] | None:
        last_msg = state["messages"][-1]
        usage = getattr(last_msg, "usage_metadata", None) or {}
        new_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        accumulated = state.get("token_count", 0) + new_tokens
        logger.info(
            "after_model: acumulando tokens",
            extra={
                "middleware": "TokenBudgetMiddleware",
                "new_tokens": new_tokens,
                "accumulated": accumulated,
            },
        )
        return {"token_count": accumulated}

    # ── Versiones ASYNC ─────────────────────────────────────────────────────

    @hook_config(can_jump_to=["end"])
    async def abefore_model(
        self, state: TokenBudgetState, runtime: Runtime
    ) -> dict[str, Any] | None:
        return self.before_model(state, runtime)

    async def aafter_model(
        self, state: TokenBudgetState, runtime: Runtime
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)
