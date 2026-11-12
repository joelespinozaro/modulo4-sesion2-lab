"""Anonymizador para las trazas de LangSmith.

LangSmith es una vía de observabilidad separada del logging de Python: el
SDK de LangChain serializa inputs/outputs/metadata/error de cada run y los
sube directo a la API de LangSmith (`LangChainTracer`), sin pasar por
`logging` — por eso `PIIRedactionFilter` (src.utils.pii_log_filter), que
está enganchado como logging.Filter, nunca ve ese tráfico.

`langsmith.Client(anonymizer=...)` es el hook correcto: recorre recursivamente
cada string dentro del payload (hasta `max_depth`) y lo reemplaza antes de
que el run se envíe. Acá se compone en dos pasadas sobre el mismo mecanismo:

1. Secretos: `create_secret_anonymizer()` (reglas propias del SDK: API keys de
   proveedores conocidos, JWT, PEM, headers Authorization, etc.) + reglas
   extra para las claves de este proyecto que el default no cubre (Groq
   `gsk_...`, Neon `napi_...`).
2. PII: el mismo motor de detección que ya usan los logs (`src.utils.pii`),
   aplicado string por string — mismo umbral y mismo enmascarado
   (`mask_span`). A diferencia de `PIIRedactionFilter` (logs), acá SÍ se
   respetan las estrategias de `pii_strategies.yaml` (solo entidades
   `block`/`mask`, nunca `off`): un payload de traza es un árbol de campos
   estructurales (`role`, nombre del modelo, nombre de la tool...), y la NER
   en español de Presidio dispara falsos positivos frecuentes sobre esos
   strings cortos en inglés (p.ej. "system" -> ORGANIZATION, "assistant" ->
   PERSON, "gpt-4o-mini" -> PERSON) — como PERSON/LOCATION/ORGANIZATION están
   en `off` (o ni siquiera listadas), filtrar por estrategia los excluye sin
   tocar la detección real de DNI/RUC/teléfono/email/tarjeta/IBAN.

Se activa una sola vez al arrancar el proceso, sembrando el cliente LangSmith
singleton (`langsmith.run_trees.get_cached_client`) — ver `src.utils.environment`.
"""
import re
from typing import Any

from langsmith.anonymizer import StringNodeRule, create_anonymizer, create_secret_anonymizer

from src.utils.pii import get_pii_score_threshold, get_pii_strategies, get_shared_pii_detector, mask_span

SECRET_PLACEHOLDER = "[SECRET_DETECTED]"

# Claves de proveedores usados en este proyecto que DEFAULT_SECRET_RULES no
# reconoce (ver layer1_secrets.py / .env): Groq y Neon.
_EXTRA_SECRET_RULES: list[StringNodeRule] = [
    {"pattern": re.compile(r"gsk_[A-Za-z0-9]{20,}"), "replace": SECRET_PLACEHOLDER},
    {"pattern": re.compile(r"napi_[A-Za-z0-9]{20,}"), "replace": SECRET_PLACEHOLDER},
]

# Leídos una sola vez al importar el módulo (no en cada string del payload).
_SCORE_THRESHOLD = get_pii_score_threshold()
_ENTITY_STRATEGIES = get_pii_strategies()


def _redact_pii_string(value: str) -> str:
    if not value:
        return value
    detector, _ = get_shared_pii_detector()
    try:
        matches = detector.analyze(value, _SCORE_THRESHOLD)
    except Exception:  # noqa: BLE001 - fail-open: nunca se cae la traza por esto
        return value
    relevant = [m for m in matches if _ENTITY_STRATEGIES.get(m.entity_type, "off") != "off"]
    masked = value
    for match in sorted(relevant, key=lambda m: m.start, reverse=True):
        masked = mask_span(masked, match.start, match.end)
    return masked


def build_langsmith_anonymizer() -> Any:
    """Anonymizer combinado (secretos + PII) para `langsmith.Client(anonymizer=...)`."""
    secret_anonymizer = create_secret_anonymizer(extra_rules=_EXTRA_SECRET_RULES)
    pii_anonymizer = create_anonymizer(_redact_pii_string, max_depth=24)

    def anonymizer(data: Any) -> Any:
        return pii_anonymizer(secret_anonymizer(data))

    return anonymizer
