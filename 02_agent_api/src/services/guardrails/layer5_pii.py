"""Capa 5 — Detección de PII.

Modo principal: NLP + ML vía Microsoft Presidio (spaCy `es_core_news_sm`),
umbral `score > 0.6`, con recognizers custom para entidades de Perú
(DNI_PE, RUC_PE, PHONE_PE). Modo fallback automático: si Presidio no está
instalado o falla al inicializar, se activa un detector 100% REGEX local
equivalente, sin interrumpir el servicio. Todo el procesamiento es local
(nunca se envía el mensaje a un servicio externo para esta capa).

Estrategia configurable por entidad (block/mask/off) vía
config/guardrails/pii_strategies.yaml.
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_message, load_yaml_config, log_block
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer5_pii"

SPACY_MODEL = "es_core_news_sm"

DNI_PE_REGEX = r"\b\d{8}\b"
RUC_PE_REGEX = r"\b(10|15|17|20)\d{9}\b"
PHONE_PE_REGEX = r"(\+51\s?9\d{8}\b|\b9\d{8}\b)"
EMAIL_REGEX = r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"
CREDIT_CARD_REGEX = r"\b(?:\d[ -]?){13,19}\b"


@dataclass
class PIIMatch:
    entity_type: str
    start: int
    end: int
    score: float


def _mask(text: str, start: int, end: int, visible: int = 2) -> str:
    span = text[start:end]
    if len(span) <= visible:
        masked_span = "*" * len(span)
    else:
        masked_span = span[:visible] + "*" * (len(span) - visible)
    return text[:start] + masked_span + text[end:]


class _RegexPIIDetector:
    """Fallback 100% local usado cuando Presidio no está disponible."""

    _CUSTOM_PATTERNS = {
        "DNI_PE": DNI_PE_REGEX,
        "RUC_PE": RUC_PE_REGEX,
        "PHONE_PE": PHONE_PE_REGEX,
        "EMAIL_ADDRESS": EMAIL_REGEX,
        "CREDIT_CARD": CREDIT_CARD_REGEX,
    }

    def __init__(self) -> None:
        self._compiled = {
            entity: re.compile(pattern) for entity, pattern in self._CUSTOM_PATTERNS.items()
        }

    def analyze(self, text: str, score_threshold: float) -> List[PIIMatch]:
        matches: List[PIIMatch] = []
        for entity_type, pattern in self._compiled.items():
            for m in pattern.finditer(text):
                matches.append(PIIMatch(entity_type, m.start(), m.end(), score=1.0))
        return matches


class _PresidioPIIDetector:
    """Motor principal: Presidio AnalyzerEngine + recognizers custom PE."""

    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "es", "model_name": SPACY_MODEL}],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()

        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["es"])

        self._analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity="DNI_PE",
                supported_language="es",
                patterns=[Pattern(name="dni_pe", regex=DNI_PE_REGEX, score=0.85)],
            )
        )
        self._analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity="RUC_PE",
                supported_language="es",
                patterns=[Pattern(name="ruc_pe", regex=RUC_PE_REGEX, score=0.9)],
            )
        )
        self._analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity="PHONE_PE",
                supported_language="es",
                patterns=[Pattern(name="phone_pe", regex=PHONE_PE_REGEX, score=0.85)],
            )
        )

    def analyze(self, text: str, score_threshold: float) -> List[PIIMatch]:
        results = self._analyzer.analyze(text=text, language="es", score_threshold=score_threshold)
        return [
            PIIMatch(entity_type=r.entity_type, start=r.start, end=r.end, score=r.score)
            for r in results
        ]


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
