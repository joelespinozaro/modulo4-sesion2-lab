import time

from src.services.guardrails.layer4_custom_regex import CustomRegexMiddleware, CustomRegexRule
from tests.guardrails.conftest import build_state


def test_blocks_configured_business_rule():
    rules = [
        CustomRegexRule(
            name="test_rule",
            pattern=r"(?i)acme\s*academy",
            reason="mención de competidor",
            message="No podemos hablar de otras instituciones.",
        )
    ]
    middleware = CustomRegexMiddleware(timeout_seconds=1.0, rules=rules)
    state = build_state("¿Qué opinas de Acme Academy?")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


def test_passes_benign_message_with_business_rules():
    rules = [
        CustomRegexRule(
            name="test_rule",
            pattern=r"(?i)acme\s*academy",
            reason="mención de competidor",
            message="No podemos hablar de otras instituciones.",
        )
    ]
    middleware = CustomRegexMiddleware(timeout_seconds=1.0, rules=rules)
    state = build_state("¿Cuánto dura el curso de IA?")

    result = middleware.before_agent(state, runtime=None)

    assert result is None


def test_catastrophic_regex_times_out_without_hanging_the_service():
    """Patrón de regex catastrófico conocido: (a+)+$ con una entrada diseñada
    para causar backtracking exponencial. El timeout de 1s debe abortar SOLO
    esa evaluación puntual, sin colgar el proceso ni caer el servicio."""
    catastrophic_rule = CustomRegexRule(
        name="catastrophic_rule",
        pattern=r"(a+)+$",
        reason="regla catastrófica de prueba",
        message="bloqueado",
    )
    middleware = CustomRegexMiddleware(timeout_seconds=0.5, rules=[catastrophic_rule])

    malicious_input = "a" * 40 + "!"
    state = build_state(malicious_input)

    start = time.perf_counter()
    result = middleware.before_agent(state, runtime=None)
    elapsed = time.perf_counter() - start

    # El timeout debe respetarse (con margen razonable) y el pipeline debe
    # continuar en lugar de bloquear el hilo indefinidamente.
    assert elapsed < 3.0
    # La entrada no calza (termina en "!"), y como la regla catastrófica
    # expira por timeout, el sistema continúa sin bloquear por esta regla.
    assert result is None
