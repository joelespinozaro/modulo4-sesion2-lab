import pytest
from google.cloud import modelarmor_v1
from langchain_core.messages import AIMessage

from src.services.guardrails.layer_model_armor import ModelArmorMiddleware
from tests.guardrails.conftest import build_state


def _no_match_response() -> modelarmor_v1.SanitizeUserPromptResponse:
    return modelarmor_v1.SanitizeUserPromptResponse(
        sanitization_result=modelarmor_v1.SanitizationResult(
            invocation_result=modelarmor_v1.InvocationResult.SUCCESS,
            filter_match_state=modelarmor_v1.FilterMatchState.NO_MATCH_FOUND,
        )
    )


def _rai_match_response() -> modelarmor_v1.SanitizeUserPromptResponse:
    filter_result = modelarmor_v1.FilterResult(
        rai_filter_result=modelarmor_v1.RaiFilterResult(
            match_state=modelarmor_v1.FilterMatchState.MATCH_FOUND,
        )
    )
    return modelarmor_v1.SanitizeUserPromptResponse(
        sanitization_result=modelarmor_v1.SanitizationResult(
            invocation_result=modelarmor_v1.InvocationResult.SUCCESS,
            filter_match_state=modelarmor_v1.FilterMatchState.MATCH_FOUND,
            filter_results={"rai": filter_result},
        )
    )


def _sdp_deidentify_response(masked_text: str) -> modelarmor_v1.SanitizeUserPromptResponse:
    sdp_result = modelarmor_v1.SdpFilterResult(
        deidentify_result=modelarmor_v1.SdpDeidentifyResult(
            match_state=modelarmor_v1.FilterMatchState.MATCH_FOUND,
            data=modelarmor_v1.DataItem(text=masked_text),
        )
    )
    filter_result = modelarmor_v1.FilterResult(sdp_filter_result=sdp_result)
    return modelarmor_v1.SanitizeUserPromptResponse(
        sanitization_result=modelarmor_v1.SanitizationResult(
            invocation_result=modelarmor_v1.InvocationResult.SUCCESS,
            filter_match_state=modelarmor_v1.FilterMatchState.MATCH_FOUND,
            filter_results={"sdp": filter_result},
        )
    )


class _FakeModelArmorClient:
    """Cliente de Model Armor falso para no depender de red/credenciales GCP."""

    def __init__(self, user_prompt_response=None, model_response_response=None, raise_error=False):
        self._user_prompt_response = user_prompt_response
        self._model_response_response = model_response_response
        self._raise_error = raise_error

    def sanitize_user_prompt(self, request):
        if self._raise_error:
            raise ConnectionError("Model Armor no disponible")
        return self._user_prompt_response

    def sanitize_model_response(self, request):
        if self._raise_error:
            raise ConnectionError("Model Armor no disponible")
        return self._model_response_response


class _FakeAgentMiddleware:
    """Middleware local falso para probar la orquestación del fallback sin
    depender de las capas reales (regex/Groq)."""

    def __init__(self, block: bool = False) -> None:
        self._block = block
        self.called = False

    def before_agent(self, state, runtime):
        self.called = True
        if self._block:
            return {"messages": [{"role": "assistant", "content": "bloqueado"}], "jump_to": "end"}
        return None


def _middleware(**kwargs) -> ModelArmorMiddleware:
    return ModelArmorMiddleware(client=_FakeModelArmorClient(**kwargs))


# ----------------------------------------------------------------------
# Input: sanitize_user_prompt
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_input_passes_benign_message():
    middleware = _middleware(user_prompt_response=_no_match_response())
    state = build_state("¿Cuánto dura el programa de Inteligencia Artificial?")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is None


@pytest.mark.asyncio
async def test_input_blocks_on_rai_match():
    middleware = _middleware(user_prompt_response=_rai_match_response())
    state = build_state("mensaje con contenido dañino")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


@pytest.mark.asyncio
async def test_input_masks_on_sdp_deidentify():
    middleware = _middleware(user_prompt_response=_sdp_deidentify_response("mi DNI es 45******"))
    state = build_state("mi DNI es 45678912")

    result = await middleware.abefore_agent(state, runtime=None)

    assert result is None
    assert state["messages"][-1].content == "mi DNI es 45******"


@pytest.mark.asyncio
async def test_input_falls_back_to_local_when_client_fails_and_local_blocks():
    middleware = _middleware(raise_error=True)
    blocking_layer = _FakeAgentMiddleware(block=True)
    passthrough_layer = _FakeAgentMiddleware(block=False)
    middleware._local_fallback = [passthrough_layer, blocking_layer]
    state = build_state("cualquier mensaje")

    result = await middleware.abefore_agent(state, runtime=None)

    assert passthrough_layer.called is True
    assert blocking_layer.called is True
    assert result is not None
    assert result["jump_to"] == "end"


@pytest.mark.asyncio
async def test_input_falls_back_to_local_and_passes_when_all_local_layers_pass():
    middleware = _middleware(raise_error=True)
    layer_a = _FakeAgentMiddleware(block=False)
    layer_b = _FakeAgentMiddleware(block=False)
    middleware._local_fallback = [layer_a, layer_b]
    state = build_state("cualquier mensaje")

    result = await middleware.abefore_agent(state, runtime=None)

    assert layer_a.called is True
    assert layer_b.called is True
    assert result is None


# ----------------------------------------------------------------------
# Output: sanitize_model_response
# ----------------------------------------------------------------------

def _output_state(answer: str) -> dict:
    state = build_state("una pregunta cualquiera")
    state["messages"].append(AIMessage(content=answer))
    return state


@pytest.mark.asyncio
async def test_output_passes_benign_response():
    middleware = _middleware(
        model_response_response=modelarmor_v1.SanitizeModelResponseResponse(
            sanitization_result=modelarmor_v1.SanitizationResult(
                invocation_result=modelarmor_v1.InvocationResult.SUCCESS,
                filter_match_state=modelarmor_v1.FilterMatchState.NO_MATCH_FOUND,
            )
        )
    )
    state = _output_state("La respuesta es 42.")
    original = state["messages"][-1].content

    result = await middleware.aafter_agent(state, runtime=None)

    assert result is None
    assert state["messages"][-1].content == original


@pytest.mark.asyncio
async def test_output_masks_sdp_in_response():
    sdp_result = modelarmor_v1.SdpFilterResult(
        deidentify_result=modelarmor_v1.SdpDeidentifyResult(
            match_state=modelarmor_v1.FilterMatchState.MATCH_FOUND,
            data=modelarmor_v1.DataItem(text="tu RUC es 20**********"),
        )
    )
    filter_result = modelarmor_v1.FilterResult(sdp_filter_result=sdp_result)
    middleware = _middleware(
        model_response_response=modelarmor_v1.SanitizeModelResponseResponse(
            sanitization_result=modelarmor_v1.SanitizationResult(
                invocation_result=modelarmor_v1.InvocationResult.SUCCESS,
                filter_match_state=modelarmor_v1.FilterMatchState.MATCH_FOUND,
                filter_results={"sdp": filter_result},
            )
        )
    )
    state = _output_state("tu RUC es 20123456789")

    result = await middleware.aafter_agent(state, runtime=None)

    assert result is None
    assert state["messages"][-1].content == "tu RUC es 20**********"


@pytest.mark.asyncio
async def test_output_blocks_on_binary_filter_match():
    filter_result = modelarmor_v1.FilterResult(
        malicious_uri_filter_result=modelarmor_v1.MaliciousUriFilterResult(
            match_state=modelarmor_v1.FilterMatchState.MATCH_FOUND,
        )
    )
    middleware = _middleware(
        model_response_response=modelarmor_v1.SanitizeModelResponseResponse(
            sanitization_result=modelarmor_v1.SanitizationResult(
                invocation_result=modelarmor_v1.InvocationResult.SUCCESS,
                filter_match_state=modelarmor_v1.FilterMatchState.MATCH_FOUND,
                filter_results={"malicious_uris": filter_result},
            )
        )
    )
    state = _output_state("visita este link sospechoso.example")

    result = await middleware.aafter_agent(state, runtime=None)

    assert result is None
    assert state["messages"][-1].content != "visita este link sospechoso.example"


@pytest.mark.asyncio
async def test_output_fails_open_when_client_fails():
    """Sin backup local para la salida (capacidad nueva): si Model Armor
    falla, la respuesta se entrega sin escanear (fail-open documentado)."""
    middleware = _middleware(raise_error=True)
    state = _output_state("respuesta original sin tocar")

    result = await middleware.aafter_agent(state, runtime=None)

    assert result is None
    assert state["messages"][-1].content == "respuesta original sin tocar"
