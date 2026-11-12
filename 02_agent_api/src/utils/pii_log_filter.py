"""Ofuscación automática de PII en logs (DLP de logs).

El PII ya no se bloquea en la entrada del agente (ver
`src.services.guardrails.__init__`) — se deja pasar tal cual para no romper
flujos que lo necesitan. En cambio, este filtro se adjunta a todo logger
creado vía `src.utils.logger.get_logger()` y enmascara cualquier PII
detectado (DNI, RUC, teléfono, email, tarjeta) antes de que el log se emita,
tanto en el mensaje formateado como en campos sueltos pasados por `extra=`.

Reutiliza el mismo motor de detección que la Capa 5 del InputGuardrail
(`src.utils.pii`), vía un detector singleton (no recarga Presidio/spaCy por
cada logger). A diferencia de esa capa, acá no se respetan las estrategias
`block`/`off` de `config/guardrails/pii_strategies.yaml` — el propósito es
puramente DLP de logs, así que toda entidad detectada sobre el umbral se
enmascara. Fail-open: si el detector falla, el log se emite sin modificar.

Nota de diseño: este módulo NO importa nada de `src.services.guardrails`
(aunque lee el mismo archivo de config) para no crear un import circular —
`get_logger()` se llama a nivel de módulo desde varias capas del guardrail,
y `guardrails/__init__.py` importa esas capas (con dependencia de langchain)
al cargarse; que `src.utils` (nivel más bajo) dependiera de ese paquete
crearía un ciclo frágil dependiente del orden de imports.
"""
import logging

from src.utils.pii import get_pii_score_threshold, get_shared_pii_detector, mask_span

_RESERVED_LOG_RECORD_ATTRS = set(vars(logging.makeLogRecord({})).keys())


class PIIRedactionFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self._detector, self._engine_name = get_shared_pii_detector()
        self._score_threshold: float = get_pii_score_threshold()

    def _redact_text(self, text: str) -> str:
        matches = self._detector.analyze(text, self._score_threshold)
        if not matches:
            return text
        masked = text
        for match in sorted(matches, key=lambda m: m.start, reverse=True):
            masked = mask_span(masked, match.start, match.end)
        return masked

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            redacted_message = self._redact_text(message)
            if redacted_message != message:
                record.msg = redacted_message
                record.args = ()

            for key, value in list(record.__dict__.items()):
                if key in _RESERVED_LOG_RECORD_ATTRS or not isinstance(value, str):
                    continue
                redacted_value = self._redact_text(value)
                if redacted_value != value:
                    setattr(record, key, redacted_value)
        except Exception:
            pass  # fail-open: nunca se cae el logging por esta capa

        return True
