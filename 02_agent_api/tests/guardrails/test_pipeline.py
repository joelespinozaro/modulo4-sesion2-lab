from src.services.guardrails.common import get_latest_human_text
from tests.guardrails.conftest import build_state


def test_build_input_guardrails_returns_8_layers_in_fixed_order(monkeypatch):
    """No debe existir ningún flag/modo debug que altere el orden o cantidad
    de capas (criterio de la HU: cero excepciones / sin bypass)."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    from src.services.guardrails import build_input_guardrails
    from src.services.guardrails.layer1_secrets import SecretKeysMiddleware
    from src.services.guardrails.layer2_prompt_injection import PromptInjectionMiddleware
    from src.services.guardrails.layer3_toxicity import ToxicityMiddleware
    from src.services.guardrails.layer4_custom_regex import CustomRegexMiddleware
    from src.services.guardrails.layer5_pii import PIIGuardrailMiddleware
    from src.services.guardrails.layer6_url_filter import UrlFilterMiddleware
    from src.services.guardrails.layer7_prompt_guard import PromptGuardMiddleware
    from src.services.guardrails.layer8_llama_guard import LlamaGuardMiddleware

    expected_order = [
        SecretKeysMiddleware,
        PromptInjectionMiddleware,
        ToxicityMiddleware,
        CustomRegexMiddleware,
        PIIGuardrailMiddleware,
        UrlFilterMiddleware,
        PromptGuardMiddleware,
        LlamaGuardMiddleware,
    ]

    guardrails = build_input_guardrails()

    assert len(guardrails) == 8
    assert [type(g) for g in guardrails] == expected_order


def test_get_latest_human_text_ignores_history_and_uses_current_message(sample_history):
    """El mensaje a validar en cada capa debe ser siempre el más reciente,
    nunca uno del historial antepuesto por AgentService.chat."""
    state = build_state("mensaje actual del usuario", history=sample_history)

    assert get_latest_human_text(state) == "mensaje actual del usuario"


def test_get_latest_human_text_returns_none_if_last_message_is_not_human():
    from langchain_core.messages import AIMessage, HumanMessage

    state = {"messages": [HumanMessage(content="hola"), AIMessage(content="respuesta")]}

    assert get_latest_human_text(state) is None
