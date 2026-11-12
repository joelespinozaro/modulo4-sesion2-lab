import logging

from src.utils.pii import RegexPIIDetector
from src.utils.pii_log_filter import PIIRedactionFilter


def _filter_with_regex_fallback() -> PIIRedactionFilter:
    """Fuerza el uso del detector fallback (sin depender de que Presidio/spaCy
    estén instalados en el entorno de test), igual que test_layer5_pii.py."""
    pii_filter = PIIRedactionFilter()
    pii_filter._detector = RegexPIIDetector()
    pii_filter._engine_name = "regex_fallback"
    return pii_filter


def _make_record(message: str, **extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_redacts_dni_in_message():
    pii_filter = _filter_with_regex_fallback()
    record = _make_record("Respuesta a la pregunta: mi DNI es 45678912")

    assert pii_filter.filter(record) is True
    assert "45678912" not in record.getMessage()
    assert "45" in record.getMessage()


def test_leaves_benign_message_untouched():
    pii_filter = _filter_with_regex_fallback()
    record = _make_record("Chat finalizado")

    assert pii_filter.filter(record) is True
    assert record.getMessage() == "Chat finalizado"


def test_redacts_pii_in_extra_fields():
    pii_filter = _filter_with_regex_fallback()
    record = _make_record("Respuesta generada", answer="mi RUC es 20123456789")

    assert pii_filter.filter(record) is True
    assert "20123456789" not in record.answer


def test_fails_open_when_detector_raises():
    pii_filter = _filter_with_regex_fallback()

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    pii_filter._detector.analyze = _raise
    record = _make_record("mensaje con DNI 45678912")

    assert pii_filter.filter(record) is True
    assert record.getMessage() == "mensaje con DNI 45678912"
