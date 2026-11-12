"""Capa 5 — Detección de PII.

NOTA: esta capa está desconectada del pipeline activo (ver
`guardrails/__init__.py`) — la clase se mantiene funcional y testeada, pero
`build_input_guardrails()` ya no la incluye. El PII ahora se deja pasar hacia
el agente sin bloquearse; la protección se movió a la ofuscación automática
de logs (`src.utils.pii_log_filter.PIIRedactionFilter`), que reutiliza el
mismo motor de detección (`src.utils.pii`).

Modo principal: NLP + ML vía Microsoft Presidio (spaCy `es_core_news_sm`),
umbral `score > 0.6`, con recognizers custom para entidades de Perú
(DNI_PE, RUC_PE, PHONE_PE). Modo fallback automático: si Presidio no está
instalado o falla al inicializar, se activa un detector 100% REGEX local
equivalente, sin interrumpir el servicio. Todo el procesamiento es local
(nunca se envía el mensaje a un servicio externo para esta capa).

Estrategia configurable por entidad (block/mask/off) vía
config/guardrails/pii_strategies.yaml.
"""
from typing import Any, Dict, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_message, load_yaml_config, log_block
from src.utils.logger import get_logger
from src.utils.pii import SPACY_MODEL, PIIMatch, PresidioPIIDetector, RegexPIIDetector, mask_span

logger = get_logger(__name__)

LAYER_NAME = "layer5_pii"

# Alias retrocompatibles: tests y código externo a este módulo referencian
# estos nombres directamente (la lógica real vive en src.utils.pii, compartida
# con el filtro de logs).
_RegexPIIDetector = RegexPIIDetector
_PresidioPIIDetector = PresidioPIIDetector
_mask = mask_span


class PIIGuardrailMiddleware(AgentMiddleware):
    """Guardrail de PII con motor Presidio principal y fallback regex local."""

    def __init__(self) -> None:
        super().__init__()
        config = load_yaml_config("pii_strategies.yaml")
        self._score_threshold: float = config.get("score_threshold", 0.6)
        self._strategies: Dict[str, str] = config.get("strategies", {})
        messages = config.get("messages", {})
        self._block_message = messages.get(
            "block", "Tu mensaje contiene datos personales sensibles. Por seguridad, evítalos."
        )

        try:
            self._detector = _PresidioPIIDetector()
            self._engine_name = "presidio"
            logger.info("Capa 5: motor Presidio inicializado con spaCy %s", SPACY_MODEL)
        except Exception as exc:  # noqa: BLE001 - fallback intencional ante cualquier fallo
            logger.warning(
                "Capa 5: Presidio no disponible (%s). Activando fallback REGEX local.", exc
            )
            self._detector = _RegexPIIDetector()
            self._engine_name = "regex_fallback"

    def _strategy_for(self, entity_type: str) -> str:
        return self._strategies.get(entity_type, "off")

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        latest_message = get_latest_human_message(state)
        if latest_message is None:
            return None

        text = getattr(latest_message, "content", None)
        if not isinstance(text, str) or not text:
            return None

        try:
            matches = self._detector.analyze(text, self._score_threshold)
        except Exception as exc:  # noqa: BLE001 - nunca debe caer el servicio por esta capa
            logger.warning(
                "Capa 5: error analizando PII (%s); se omite esta capa para este mensaje.", exc
            )
            return None

        relevant_matches = [m for m in matches if self._strategy_for(m.entity_type) != "off"]
        if not relevant_matches:
            return None

        block_matches = [m for m in relevant_matches if self._strategy_for(m.entity_type) == "block"]
        if block_matches:
            log_block(
                logger,
                LAYER_NAME,
                text,
                reason=f"entities:{sorted({m.entity_type for m in block_matches})}",
                extra={"pii_engine": self._engine_name},
            )
            return block_result(self._block_message)

        mask_matches = sorted(
            (m for m in relevant_matches if self._strategy_for(m.entity_type) == "mask"),
            key=lambda m: m.start,
            reverse=True,
        )
        masked_text = text
        for match in mask_matches:
            masked_text = _mask(masked_text, match.start, match.end)

        if masked_text != text:
            latest_message.content = masked_text
            logger.info(
                "Capa 5: PII enmascarada antes de llegar al agente",
                extra={
                    "guardrail_layer": LAYER_NAME,
                    "pii_engine": self._engine_name,
                    "entities": sorted({m.entity_type for m in mask_matches}),
                },
            )

        return None
