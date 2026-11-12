"""Capa 7 — Llama Prompt Guard 2 (clasificador semántico ligero).

Segundo filtro semántico para detectar ataques que evaden el REGEX (faltas de
ortografía intencionales, redacción creativa, otros idiomas). Modelo
`meta-llama/Llama-Prompt-Guard-2-86M` servido vía Groq API, `temperature=0.0`.

Fail-close: si la API de Groq no responde dentro del timeout definido (o
lanza cualquier excepción), el mensaje se bloquea (nunca se deja pasar por
error de conexión).
"""
import asyncio
from typing import Any, Dict, List, Optional

from groq import AsyncGroq
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_text, log_block
from src.utils.environment import GROQ_API_KEY, GROQ_PROMPT_GUARD_MODEL, GROQ_TIMEOUT_SECONDS
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer7_prompt_guard"

BLOCK_MESSAGE = (
    "No puedo procesar este mensaje por motivos de seguridad. Por favor, "
    "reformula tu consulta de manera directa."
)

MAX_TOKENS_PER_SEGMENT = 512
# Aproximación conservadora sin dependencia de tokenizer: ~4 caracteres/token.
_APPROX_CHARS_PER_TOKEN = 4
MAX_CHARS_PER_SEGMENT = MAX_TOKENS_PER_SEGMENT * _APPROX_CHARS_PER_TOKEN

MALICIOUS_LABEL = "MALICIOUS"
BENIGN_LABEL = "BENIGN"


def _segment_text(text: str, max_chars: int = MAX_CHARS_PER_SEGMENT) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


class PromptGuardMiddleware(AgentMiddleware):
    """Guardrail semántico (Groq Llama Prompt Guard 2) con fail-close."""

    def __init__(self, client: Optional[AsyncGroq] = None) -> None:
        super().__init__()
        self._client = client or AsyncGroq(api_key=GROQ_API_KEY)
        self._model = GROQ_PROMPT_GUARD_MODEL
        self._timeout = GROQ_TIMEOUT_SECONDS

    async def _classify_segment(self, segment: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": segment}],
            temperature=0.0,
        )
        content = (response.choices[0].message.content or "").strip().upper()
        return MALICIOUS_LABEL if MALICIOUS_LABEL in content else BENIGN_LABEL

    @hook_config(can_jump_to=["end"])
    async def abefore_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        text = get_latest_human_text(state)
        if not text:
            return None

        segments = _segment_text(text)

        try:
            labels = await asyncio.wait_for(
                asyncio.gather(*(self._classify_segment(segment) for segment in segments)),
                timeout=self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 - fail-close ante timeout o cualquier error de Groq
            logger.warning(
                "Capa 7: error/timeout consultando Groq (%s). Aplicando fail-close.", exc,
                extra={"guardrail_layer": LAYER_NAME},
            )
            log_block(logger, LAYER_NAME, text, reason="groq_unavailable_fail_close")
            return block_result(BLOCK_MESSAGE)

        if any(label == MALICIOUS_LABEL for label in labels):
            log_block(logger, LAYER_NAME, text, reason="classified_malicious")
            return block_result(BLOCK_MESSAGE)

        return None
