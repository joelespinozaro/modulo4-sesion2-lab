from src.services.guardrails.layer5_pii import PIIGuardrailMiddleware, _RegexPIIDetector
from tests.guardrails.conftest import build_state


def _middleware_with_regex_fallback() -> PIIGuardrailMiddleware:
    """Fuerza el uso del detector fallback (sin depender de que Presidio/spaCy
    estén instalados en el entorno de test)."""
    middleware = PIIGuardrailMiddleware()
    middleware._detector = _RegexPIIDetector()
    middleware._engine_name = "regex_fallback"
    return middleware


def test_falls_back_to_regex_when_presidio_unavailable(monkeypatch):
    def _raise_import_error(*args, **kwargs):
        raise ImportError("presidio_analyzer no instalado")

    monkeypatch.setattr(
        "src.services.guardrails.layer5_pii._PresidioPIIDetector.__init__",
        _raise_import_error,
    )

    middleware = PIIGuardrailMiddleware()

    assert middleware._engine_name == "regex_fallback"
    assert isinstance(middleware._detector, _RegexPIIDetector)


def test_blocks_dni_pe():
    middleware = _middleware_with_regex_fallback()
    state = build_state("Mi DNI es 45678912, ¿pueden verificar mi matrícula?")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


def test_blocks_ruc_pe():
    middleware = _middleware_with_regex_fallback()
    state = build_state("La factura debe emitirse al RUC 20123456789")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None


def test_masks_phone_pe_instead_of_blocking():
    middleware = _middleware_with_regex_fallback()
    state = build_state("Mi celular es 987654321, llámenme por ahí")

    result = middleware.before_agent(state, runtime=None)

    assert result is None
    latest_message = state["messages"][-1]
    assert "987654321" not in latest_message.content
    assert "98" in latest_message.content


def test_passes_benign_message():
    middleware = _middleware_with_regex_fallback()
    state = build_state("¿Cuánto dura el programa de Inteligencia Artificial?")

    result = middleware.before_agent(state, runtime=None)

    assert result is None
