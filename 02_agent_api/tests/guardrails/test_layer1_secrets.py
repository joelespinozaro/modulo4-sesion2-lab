from src.services.guardrails.layer1_secrets import SecretKeysMiddleware
from tests.guardrails.conftest import build_state


def test_blocks_openai_style_key():
    middleware = SecretKeysMiddleware()
    state = build_state("Mi clave es sk-proj-abcdefghijklmnopqrstuvwxyz123456")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


def test_blocks_github_token():
    middleware = SecretKeysMiddleware()
    state = build_state("aquí está ghp_1234567890abcdef1234567890abcdef1234")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


def test_blocks_bearer_token():
    middleware = SecretKeysMiddleware()
    state = build_state("Authorization: Bearer abcdEFGH12345678901234567890")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None


def test_passes_benign_message():
    middleware = SecretKeysMiddleware()
    state = build_state("¿Cuánto dura el curso de IA?")

    result = middleware.before_agent(state, runtime=None)

    assert result is None


def test_validates_last_message_not_first(sample_history):
    """El pipeline debe validar el mensaje humano MÁS RECIENTE, no el primero
    de la lista (el historial se antepone en cada invocación)."""
    middleware = SecretKeysMiddleware()
    state = build_state("sk-proj-abcdefghijklmnopqrstuvwxyz123456", history=sample_history)

    result = middleware.before_agent(state, runtime=None)

    assert result is not None
