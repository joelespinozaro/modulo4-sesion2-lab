"""Capa 3 — Toxicidad (REGEX).

Bloquea contenido de odio, amenazas, acoso o autolesión. Patrones cargados
desde config/guardrails/toxicity_patterns.yaml (5 categorías). La categoría
"autolesion" recibe un mensaje de contención en lugar de un rechazo seco
(placeholder acordado; el canal de derivación real queda a definir con
Producto — ver HU_InputGuardrail.md, Capa 3).
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import (
    DEFAULT_BLOCK_MESSAGE,
    block_result,
    get_latest_human_text,
    load_yaml_config,
    log_block,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer3_toxicity"

_REGEX_FLAGS = re.IGNORECASE | re.MULTILINE

SELF_HARM_CATEGORY = "autolesion"


def _compile_patterns(config: Dict[str, Any]) -> List[Tuple[str, re.Pattern]]:
    compiled: List[Tuple[str, re.Pattern]] = []
    for category, patterns in config.items():
        if category == "respuestas" or not isinstance(patterns, list):
            continue
        for raw_pattern in patterns:
            compiled.append((category, re.compile(raw_pattern, _REGEX_FLAGS)))
    return compiled


class ToxicityMiddleware(AgentMiddleware):
    """Guardrail determinista: bloquea contenido tóxico, con contención para autolesión."""

    def __init__(self) -> None:
        super().__init__()
        config = load_yaml_config("toxicity_patterns.yaml")
        self._patterns = _compile_patterns(config)
        responses = config.get("respuestas") or {}
        self._default_message = responses.get("default", DEFAULT_BLOCK_MESSAGE)
        self._self_harm_message = responses.get("autolesion", DEFAULT_BLOCK_MESSAGE)
        logger.info("Capa 3 cargada con %d patrones de toxicidad", len(self._patterns))

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        text = get_latest_human_text(state)
        if not text:
            return None

        for category, pattern in self._patterns:
            if pattern.search(text):
                log_block(logger, LAYER_NAME, text, reason=f"category:{category}")
                message = (
                    self._self_harm_message
                    if category == SELF_HARM_CATEGORY
                    else self._default_message
                )
                return block_result(message)

        return None
