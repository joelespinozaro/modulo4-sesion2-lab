"""Capa 4 — Custom Regex & Anti-ReDoS.

Reglas de negocio personalizables (ej. bloquear menciones de competidores),
cargadas desde config/guardrails/custom_patterns.yaml (no hardcodeadas), sin
exponer el servicio a ataques de denegación de servicio vía regex catastrófico.

Usa la librería `regex` (no la `re` estándar) porque soporta un parámetro
`timeout` nativo por evaluación: si una regla individual excede el timeout,
se aborta solo esa verificación (regex.TimeoutError / TimeoutError) y el
pipeline continúa evaluando el resto de reglas y capas sin caerse.
"""
from typing import Any, Dict, List, Optional

import regex
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import (
    DEFAULT_BLOCK_MESSAGE,
    block_result,
    get_latest_human_text,
    load_yaml_config,
    log_block,
)
from src.utils.environment import CUSTOM_REGEX_TIMEOUT_SECONDS
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer4_custom_regex"


class CustomRegexRule:
    def __init__(self, name: str, pattern: str, reason: str, message: str) -> None:
        self.name = name
        self.pattern = regex.compile(pattern)
        self.reason = reason
        self.message = message


def _load_rules() -> List[CustomRegexRule]:
    config = load_yaml_config("custom_patterns.yaml")
    rules_config = config.get("rules") or []
    rules: List[CustomRegexRule] = []
    for rule_cfg in rules_config:
        rules.append(
            CustomRegexRule(
                name=rule_cfg["name"],
                pattern=rule_cfg["pattern"],
                reason=rule_cfg.get("reason", "custom_rule_match"),
                message=rule_cfg.get("message", DEFAULT_BLOCK_MESSAGE),
            )
        )
    return rules


class CustomRegexMiddleware(AgentMiddleware):
    """Guardrail determinista con reglas configurables y protección anti-ReDoS."""

    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
        rules: Optional[List[CustomRegexRule]] = None,
    ) -> None:
        super().__init__()
        self._rules = rules if rules is not None else _load_rules()
        self._timeout_seconds = timeout_seconds or CUSTOM_REGEX_TIMEOUT_SECONDS
        logger.info("Capa 4 cargada con %d regla(s) de negocio", len(self._rules))

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        text = get_latest_human_text(state)
        if not text:
            return None

        for rule in self._rules:
            try:
                match = rule.pattern.search(text, timeout=self._timeout_seconds)
            except TimeoutError:
                logger.warning(
                    "Capa 4: timeout evaluando regla '%s' (posible ReDoS); "
                    "se omite esta regla y continúa el pipeline",
                    rule.name,
                    extra={"guardrail_layer": LAYER_NAME, "rule_name": rule.name},
                )
                continue

            if match:
                log_block(logger, LAYER_NAME, text, reason=f"rule:{rule.name}")
                return block_result(rule.message)

        return None
