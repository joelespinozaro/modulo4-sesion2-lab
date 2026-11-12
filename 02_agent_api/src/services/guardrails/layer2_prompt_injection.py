"""Capa 2 — Prompt Injection (REGEX).

Intercepta instrucciones disfrazadas que intenten sobrescribir el
comportamiento del agente. Patrones cargados desde
config/guardrails/prompt_injection_patterns.yaml (≥60 patrones ES/EN,
5 categorías), editables por negocio sin tocar código.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_text, load_yaml_config, log_block
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer2_prompt_injection"

BLOCK_MESSAGE = (
    "No puedo procesar instrucciones que intenten modificar mi comportamiento "
    "o revelar información interna del sistema. ¿En qué más puedo ayudarte?"
)

_REGEX_FLAGS = re.IGNORECASE | re.MULTILINE | re.DOTALL


def _compile_patterns(config: Dict[str, Any]) -> List[Tuple[str, re.Pattern]]:
    compiled: List[Tuple[str, re.Pattern]] = []
    for category, patterns in config.items():
        if category == "respuestas" or not isinstance(patterns, list):
            continue
        for raw_pattern in patterns:
            compiled.append((category, re.compile(raw_pattern, _REGEX_FLAGS)))
    return compiled


class PromptInjectionMiddleware(AgentMiddleware):
    """Guardrail determinista: bloquea patrones de prompt injection/jailbreak."""

    def __init__(self) -> None:
        super().__init__()
        config = load_yaml_config("prompt_injection_patterns.yaml")
        self._patterns = _compile_patterns(config)
        logger.info("Capa 2 cargada con %d patrones de prompt injection", len(self._patterns))

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        text = get_latest_human_text(state)
        if not text:
            return None

        for category, pattern in self._patterns:
            if pattern.search(text):
                log_block(logger, LAYER_NAME, text, reason=f"category:{category}")
                return block_result(BLOCK_MESSAGE)

        return None
