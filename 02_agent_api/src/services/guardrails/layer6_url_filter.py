"""Capa 6 — Filtro de URLs / Anti-Phishing.

Bloquea enlaces sospechosos para prevenir phishing y prompt injection
indirecto vía contenido web enlazado. Detecta URLs con y sin protocolo
(http/https/ftp, dominios "pelados") y bloquea siempre los acortadores
conocidos. TLDs y acortadores cargados desde
config/guardrails/url_blocklist.yaml (≥60 TLDs, ≥20 acortadores).
"""
import re
from typing import Any, Dict, List, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_text, load_yaml_config, log_block
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer6_url_filter"

BLOCK_MESSAGE = (
    "Tu mensaje contiene un enlace que no podemos verificar como seguro. Por "
    "tu protección, evita compartir enlaces en este chat."
)

_PROTOCOL_URL_PATTERN = re.compile(r"\b(?:https?|ftp)://[^\s<>\"']+", re.IGNORECASE)


def _build_bare_domain_pattern(tlds: List[str]) -> re.Pattern:
    """Construye un patrón para dominios "pelados" (sub.dominio.TLD)."""
    escaped_tlds = sorted((re.escape(tld) for tld in tlds), key=len, reverse=True)
    tld_group = "|".join(escaped_tlds)
    return re.compile(
        rf"\b[a-zA-Z0-9](?:[a-zA-Z0-9-]{{0,61}}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9-]{{1,63}})*\.(?:{tld_group})\b",
        re.IGNORECASE,
    )


def _build_exact_domain_pattern(domains: List[str]) -> re.Pattern:
    """Construye un patrón que matchea exactamente los dominios dados (ej. acortadores)."""
    escaped = sorted((re.escape(d) for d in domains), key=len, reverse=True)
    group = "|".join(escaped)
    return re.compile(rf"\b(?:{group})\b", re.IGNORECASE)


class UrlFilterMiddleware(AgentMiddleware):
    """Guardrail determinista: bloquea URLs (con/sin protocolo) y acortadores."""

    def __init__(self) -> None:
        super().__init__()
        config = load_yaml_config("url_blocklist.yaml")
        self._tlds = config.get("tlds", [])
        self._shorteners = [s.lower() for s in config.get("shorteners", [])]
        # Los acortadores se detectan como dominios exactos, independientemente
        # de si su TLD (ej. ".ly", ".gd") está en la lista general de TLDs.
        self._shortener_pattern = _build_exact_domain_pattern(self._shorteners)
        self._bare_domain_pattern = _build_bare_domain_pattern(self._tlds)
        logger.info(
            "Capa 6 cargada con %d TLD(s) y %d acortador(es)",
            len(self._tlds),
            len(self._shorteners),
        )

    def _find_urls(self, text: str) -> List[str]:
        urls = _PROTOCOL_URL_PATTERN.findall(text)
        urls.extend(self._bare_domain_pattern.findall(text))
        return urls

    def _find_shorteners(self, text: str) -> List[str]:
        return self._shortener_pattern.findall(text)

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        text = get_latest_human_text(state)
        if not text:
            return None

        shortener_hits = self._find_shorteners(text)
        urls = self._find_urls(text)
        if not urls and not shortener_hits:
            return None

        reason = "shortener_detected" if shortener_hits else "url_detected"
        total_hits = len(urls) + len(shortener_hits)

        log_block(logger, LAYER_NAME, text, reason=reason, extra={"url_count": total_hits})
        return block_result(BLOCK_MESSAGE)
