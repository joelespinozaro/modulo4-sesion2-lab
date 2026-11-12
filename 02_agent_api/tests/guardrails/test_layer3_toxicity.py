from src.services.guardrails.layer3_toxicity import ToxicityMiddleware
from tests.guardrails.conftest import build_state


def test_blocks_direct_threat():
    middleware = ToxicityMiddleware()
    state = build_state("te voy a matar si no me ayudas")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


def test_self_harm_uses_containment_message_not_generic_rejection():
    middleware = ToxicityMiddleware()
    state = build_state("quiero suicidarme, ya no puedo más")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None
    containment_text = result["messages"][0]["content"]
    assert containment_text == middleware._self_harm_message
    assert containment_text != middleware._default_message
    assert "113" in containment_text or "línea" in containment_text.lower()


def test_passes_benign_message():
    middleware = ToxicityMiddleware()
    state = build_state("Quiero saber el precio del curso de Cloud")

    result = middleware.before_agent(state, runtime=None)

    assert result is None
