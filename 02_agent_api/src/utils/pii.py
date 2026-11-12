"""Motor de detección de PII compartido.

Motor principal: Microsoft Presidio (spaCy `es_core_news_sm`) con recognizers
custom para entidades de Perú (DNI_PE, RUC_PE, PHONE_PE). Fallback automático:
si Presidio no está instalado o falla al inicializar, se usa un detector
100% REGEX local equivalente, sin interrumpir el servicio. Todo el
procesamiento es local (nunca se envía el texto a un servicio externo).

Usado por `src.services.guardrails.layer5_pii` (guardrail de entrada, hoy
desconectado del pipeline activo — ver guardrails/__init__.py), por
`src.utils.pii_log_filter` (ofuscación de PII en logs) y por
`src.utils.langsmith_anonymizer` (ofuscación de PII en trazas LangSmith)."""
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

SPACY_MODEL = "es_core_news_sm"

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "guardrails" / "pii_strategies.yaml"


def _load_pii_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_pii_score_threshold() -> float:
    """Umbral de confianza compartido (config/guardrails/pii_strategies.yaml,
    clave `score_threshold`) para todo consumidor de ofuscación de PII fuera
    del InputGuardrail (que usa su propia instancia de PIIGuardrailMiddleware)."""
    return _load_pii_config().get("score_threshold", 0.6)


def get_pii_strategies() -> Dict[str, str]:
    """Estrategias por entidad (config/guardrails/pii_strategies.yaml, clave
    `strategies`) — `block`/`mask` enmascaran, `off` (o cualquier entidad no
    listada) se ignora. Igual criterio que `PIIGuardrailMiddleware._strategy_for`."""
    return _load_pii_config().get("strategies", {})

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


def mask_span(text: str, start: int, end: int, visible: int = 2) -> str:
    span = text[start:end]
    if len(span) <= visible:
        masked_span = "*" * len(span)
    else:
        masked_span = span[:visible] + "*" * (len(span) - visible)
    return text[:start] + masked_span + text[end:]


class RegexPIIDetector:
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


class PresidioPIIDetector:
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


_shared_detector_lock = threading.Lock()
_shared_detector: Optional[Tuple[object, str]] = None


def get_shared_pii_detector() -> Tuple[object, str]:
    """Construye (una sola vez por proceso) y retorna el detector de PII a usar,
    junto con el nombre del motor ("presidio" o "regex_fallback")."""
    global _shared_detector
    if _shared_detector is not None:
        return _shared_detector

    with _shared_detector_lock:
        if _shared_detector is not None:
            return _shared_detector
        try:
            _shared_detector = (PresidioPIIDetector(), "presidio")
        except Exception:
            _shared_detector = (RegexPIIDetector(), "regex_fallback")
        return _shared_detector
