import asyncio

import pytest

from src.services.guardrails.layer8_llama_guard import LlamaGuardMiddleware
from tests.guardrails.conftest import build_state


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeGroqClient:
    def __init__(self, verdict: str = "safe", delay: float = 0.0, raise_error: bool = False) -> None:
        self._verdict = verdict
        self._delay = delay
        self._raise_error = raise_error
        self.chat = self
        self.completions = self

    async def create(self, **kwargs):
        if self._raise_error:
            raise ConnectionError("Groq no disponible")
        if self._delay:
            await asyncio.sleep(self._delay)
        return _FakeCompletion(self._verdict)


LLAMA_GUARD_MODEL = "meta-llama/llama-guard-4-12b"


def _llama_guard_middleware(**kwargs) -> LlamaGuardMiddleware:
    middleware = LlamaGuardMiddleware(client=_FakeGroqClient(**kwargs))
    middleware._model = LLAMA_GUARD_MODEL
    return middleware


@pytest.mark.asyncio
async def test_passes_safe_message():
    middleware = _llama_guard_middleware(verdict="safe")
    state = build_state("¿Qué certificaciones ofrece la academia?")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is None


@pytest.mark.asyncio
async def test_blocks_unsafe_message():
    middleware = _llama_guard_middleware(verdict="unsafe\nS1")
    state = build_state("Cómo cometo un crimen violento contra alguien")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


@pytest.mark.asyncio
async def test_skip_categories_lets_message_pass():
    middleware = _llama_guard_middleware(verdict="unsafe\nS6")
    middleware._skip_categories = {"S6"}
    state = build_state("Dame un consejo financiero general")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is None


@pytest.mark.asyncio
async def test_fail_closes_on_groq_error():
    middleware = LlamaGuardMiddleware(client=_FakeGroqClient(raise_error=True))
    state = build_state("Mensaje normal cualquiera")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


@pytest.mark.asyncio
async def test_fail_closes_on_timeout():
    middleware = LlamaGuardMiddleware(client=_FakeGroqClient(verdict="safe", delay=5.0))
    middleware._timeout = 0.1
    state = build_state("Mensaje normal cualquiera")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


# ---------------------------------------------------------------------------
# Modelos de política (gpt-oss-safeguard-20b, el reemplazo de Llama Guard 4
# en Groq): responden JSON en lugar de safe/unsafe.
# ---------------------------------------------------------------------------

POLICY_MODEL = "openai/gpt-oss-safeguard-20b"


class _RecordingGroqClient(_FakeGroqClient):
    def __init__(self, verdict: str) -> None:
        super().__init__(verdict=verdict)
        self.last_messages = None

    async def create(self, **kwargs):
        self.last_messages = kwargs["messages"]
        return await super().create(**kwargs)


def _policy_middleware(verdict: str) -> LlamaGuardMiddleware:
    middleware = LlamaGuardMiddleware(client=_RecordingGroqClient(verdict=verdict))
    middleware._model = POLICY_MODEL
    return middleware


@pytest.mark.asyncio
async def test_policy_model_sends_policy_as_system_message():
    middleware = _policy_middleware('{"violation": 0, "category": null, "rationale": "ok"}')

    await middleware.abefore_agent(build_state("¿Qué cursos tienen?"), runtime=None)

    messages = middleware._client.last_messages
    assert messages[0]["role"] == "system"
    assert "S9" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "¿Qué cursos tienen?"}


@pytest.mark.asyncio
async def test_policy_model_passes_safe_json():
    middleware = _policy_middleware('{"violation": 0, "category": null, "rationale": "consulta académica"}')

    result = await middleware.abefore_agent(build_state("¿Cuánto cuesta el programa?"), runtime=None)

    assert result is None


@pytest.mark.asyncio
async def test_policy_model_blocks_violation_json():
    middleware = _policy_middleware('{"violation": 1, "category": "S9", "rationale": "arma"}')

    result = await middleware.abefore_agent(build_state("Cómo fabrico un arma"), runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


@pytest.mark.asyncio
async def test_policy_model_respects_skip_categories():
    middleware = _policy_middleware('{"violation": 1, "category": "S6", "rationale": "consejo"}')
    middleware._skip_categories = {"S6"}

    result = await middleware.abefore_agent(build_state("Dame un consejo financiero general"), runtime=None)

    assert result is None


@pytest.mark.asyncio
async def test_policy_model_fail_closes_on_unparseable_verdict():
    # Antes del cambio, una respuesta que no empezaba con "unsafe" pasaba:
    # con un modelo de política eso dejaba la capa abierta.
    middleware = _policy_middleware("safe")

    result = await middleware.abefore_agent(build_state("Mensaje normal cualquiera"), runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"
