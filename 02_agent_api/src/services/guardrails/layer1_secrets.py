"""Capa 1 — Secret Keys (REGEX).

Detecta credenciales filtradas en el mensaje del usuario (API keys, tokens,
JWTs) antes de que lleguen al agente o queden registradas en logs/BD.
Sin dependencia de API externa: velocidad instantánea.
"""
import re
from typing import Any, Dict, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_text, log_block
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer1_secret_keys"

BLOCK_MESSAGE = (
    "Tu mensaje parece contener una clave de API o token secreto. Por "
    "seguridad, nunca compartas credenciales en el chat."
)

SECRET_PATTERNS = [
    re.compile(r"sk-proj-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"gho_[a-zA-Z0-9]{36}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{22,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
    re.compile(r"Bearer\s+[a-zA-Z0-9._-]{20,}", re.IGNORECASE),
]


class SecretKeysMiddleware(AgentMiddleware):
    """Guardrail determinista: bloquea mensajes que contienen secretos/credenciales."""

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        text = get_latest_human_text(state)
        if not text:
            return None

        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                log_block(logger, LAYER_NAME, text, reason=f"pattern_match:{pattern.pattern[:30]}")
                return block_result(BLOCK_MESSAGE)

        return None
