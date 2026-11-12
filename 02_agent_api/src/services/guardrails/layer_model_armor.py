"""Motor de content-safety vía GCP Model Armor, con fallback automático al
pipeline local si la API falla.

Reemplaza 5 de las capas locales (prompt injection, toxicidad, URLs
maliciosas, y las 2 capas semánticas vía Groq) cuando
`GUARDRAIL_ENGINE=model_armor` (ver `guardrails/__init__.py`). Las capas 1
(secrets) y 4 (regex custom) NO se reemplazan — son reglas de negocio propias
que Model Armor no conoce y siguen siempre activas.

Escanea tanto la entrada (`sanitize_user_prompt`, hook `abefore_agent`) como
la respuesta del agente (`sanitize_model_response`, hook `aafter_agent`) —
esto último es una capacidad NUEVA: ninguna capa local escanea hoy la salida,
así que no hay pipeline local que replicar como backup ahí (ver comentario
en `aafter_agent`).

Filtro `sdp` (datos sensibles): si Model Armor trae `deidentify_result`, se
usa ese texto ya enmascarado en vez de bloquear — igual criterio que
`layer5_pii.py`. El resto de los filtros (`rai`, `pi_and_jailbreak`,
`malicious_uris`, `csam`) son binarios: solo bloquean.
"""
import asyncio
from typing import Any, Dict, List, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_message, log_block
from src.services.guardrails.layer2_prompt_injection import PromptInjectionMiddleware
from src.services.guardrails.layer3_toxicity import ToxicityMiddleware
from src.services.guardrails.layer6_url_filter import UrlFilterMiddleware
from src.services.guardrails.layer7_prompt_guard import PromptGuardMiddleware
from src.services.guardrails.layer8_llama_guard import LlamaGuardMiddleware
from src.utils.environment import (
    MODEL_ARMOR_LOCATION,
    MODEL_ARMOR_PROJECT_ID,
    MODEL_ARMOR_TEMPLATE_ID,
    MODEL_ARMOR_TIMEOUT_SECONDS,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer_model_armor"

INPUT_BLOCK_MESSAGE = (
    "No puedo procesar este mensaje por motivos de seguridad. Por favor, "
    "reformula tu consulta de manera directa."
)
OUTPUT_BLOCK_MESSAGE = (
    "Lo sentimos, no podemos mostrar esa respuesta. ¿Hay algo más en lo que "
    "pueda ayudarte?"
)

# Subcampos de `FilterResult` (ver _extract_deidentified_text) para los
# filtros binarios de Model Armor: si hacen match, siempre bloquean (no
# tienen una versión "de-identificada" para dejar pasar enmascarado).
_BLOCKING_SUBFIELDS = (
    "rai_filter_result",
    "pi_and_jailbreak_filter_result",
    "malicious_uri_filter_result",
    "csam_filter_filter_result",
)


def _build_local_fallback() -> List[AgentMiddleware]:
    """Las 5 capas que Model Armor reemplaza, en el mismo orden de siempre —
    se usan solo si la llamada a la API de Model Armor falla."""
    return [
        PromptInjectionMiddleware(),
        ToxicityMiddleware(),
        UrlFilterMiddleware(),
        PromptGuardMiddleware(),
        LlamaGuardMiddleware(),
    ]


async def _run_layer_before_agent(
    layer: AgentMiddleware, state: AgentState, runtime: Runtime
) -> Optional[Dict[str, Any]]:
    """Invoca el hook antes-del-agente de una capa local, sync o async según
    cuál tenga definida (mismo patrón que usaría create_agent internamente)."""
    abefore = getattr(layer, "abefore_agent", None)
    if abefore is not None and type(layer).abefore_agent is not AgentMiddleware.abefore_agent:
        return await abefore(state, runtime)
    return layer.before_agent(state, runtime)


class ModelArmorMiddleware(AgentMiddleware):
    """Guardrail de content-safety vía GCP Model Armor, con fallback local."""

    def __init__(self, client: Optional[Any] = None) -> None:
        super().__init__()
        from google.cloud import modelarmor_v1

        self._modelarmor_v1 = modelarmor_v1
        self._timeout = MODEL_ARMOR_TIMEOUT_SECONDS
        self._client = client or self._build_client_with_timeout(modelarmor_v1, self._timeout)
        self._template_path = (
            f"projects/{MODEL_ARMOR_PROJECT_ID}/locations/{MODEL_ARMOR_LOCATION}"
            f"/templates/{MODEL_ARMOR_TEMPLATE_ID}"
        )
        self._local_fallback = _build_local_fallback()

    @staticmethod
    def _build_client(modelarmor_v1):
        from google.api_core.client_options import ClientOptions

        return modelarmor_v1.ModelArmorClient(
            transport="rest",
            client_options=ClientOptions(
                api_endpoint=f"modelarmor.{MODEL_ARMOR_LOCATION}.rep.googleapis.com"
            ),
        )

    @staticmethod
    def _build_client_with_timeout(modelarmor_v1, timeout: float):
        """Construye el cliente con un timeout duro.

        `ModelArmorClient(...)` es una llamada síncrona que puede resolver
        credenciales ADC por red (refresco de token, o sondeo del metadata
        server de GCE) — sin timeout propio, así que un problema de red ahí
        cuelga indefinidamente a quien la llame (el arranque de la API real,
        o un kernel de Jupyter). Se corre en un hilo daemon con timeout: si
        no vuelve a tiempo, se abandona el hilo (nunca bloquea el proceso) y
        se levanta una excepción para que el caller (`build_input_guardrails`)
        dispare su fallback normal a local — mismo criterio fail-open que el
        resto de esta capa."""
        import threading

        result: Dict[str, Any] = {}

        def _worker() -> None:
            try:
                result["client"] = ModelArmorMiddleware._build_client(modelarmor_v1)
            except Exception as exc:  # noqa: BLE001 - se re-lanza en el hilo llamador
                result["error"] = exc

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            raise TimeoutError(
                f"Construir el cliente de Model Armor tardó más de {timeout}s "
                "(credenciales ADC lentas/inalcanzables u otro problema de red)."
            )
        if "error" in result:
            raise result["error"]
        return result["client"]

    # ------------------------------------------------------------------
    # Input: sanitize_user_prompt
    # ------------------------------------------------------------------

    async def _sanitize_user_prompt(self, text: str):
        request = self._modelarmor_v1.SanitizeUserPromptRequest(
            name=self._template_path,
            user_prompt_data=self._modelarmor_v1.DataItem(text=text),
        )
        return await asyncio.wait_for(
            asyncio.to_thread(self._client.sanitize_user_prompt, request=request),
            timeout=self._timeout,
        )

    @hook_config(can_jump_to=["end"])
    async def abefore_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        latest_message = get_latest_human_message(state)
        if latest_message is None:
            return None
        text = getattr(latest_message, "content", None)
        if not isinstance(text, str) or not text:
            return None

        try:
            response = await self._sanitize_user_prompt(text)
            result = response.sanitization_result
            if result.invocation_result != self._modelarmor_v1.InvocationResult.SUCCESS:
                raise RuntimeError(f"Model Armor invocation_result={result.invocation_result}")
        except Exception as exc:  # noqa: BLE001 - dispara el fallback local
            logger.warning(
                "Model Armor no disponible para sanitize_user_prompt (%s). "
                "Usando fallback local (5 capas).",
                exc,
                extra={"guardrail_layer": LAYER_NAME, "model_armor_fallback": "input"},
            )
            return await self._run_local_fallback(state, runtime)

        if result.filter_match_state == self._modelarmor_v1.FilterMatchState.NO_MATCH_FOUND:
            return None

        masked = self._extract_deidentified_text(result)
        if masked is not None:
            latest_message.content = masked
            logger.info(
                "Model Armor: PII enmascarada en el mensaje entrante",
                extra={"guardrail_layer": LAYER_NAME},
            )
            return None

        log_block(logger, LAYER_NAME, text, reason="model_armor_match", extra={"engine": "model_armor"})
        return block_result(INPUT_BLOCK_MESSAGE)

    async def _run_local_fallback(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        for layer in self._local_fallback:
            result = await _run_layer_before_agent(layer, state, runtime)
            if result is not None:
                return result
        return None

    # ------------------------------------------------------------------
    # Output: sanitize_model_response
    # ------------------------------------------------------------------

    async def _sanitize_model_response(self, text: str):
        request = self._modelarmor_v1.SanitizeModelResponseRequest(
            name=self._template_path,
            model_response_data=self._modelarmor_v1.DataItem(text=text),
        )
        return await asyncio.wait_for(
            asyncio.to_thread(self._client.sanitize_model_response, request=request),
            timeout=self._timeout,
        )

    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        messages = state.get("messages") or []
        if not messages:
            return None
        last_message = messages[-1]
        if not isinstance(last_message, AIMessage):
            return None
        text = last_message.content
        if not isinstance(text, str) or not text:
            return None

        try:
            response = await self._sanitize_model_response(text)
            result = response.sanitization_result
            if result.invocation_result != self._modelarmor_v1.InvocationResult.SUCCESS:
                raise RuntimeError(f"Model Armor invocation_result={result.invocation_result}")
        except Exception as exc:  # noqa: BLE001
            # No existe pipeline local de salida que replicar como backup acá:
            # ninguna de las 8 capas escanea hoy la respuesta, es capacidad
            # nueva de Model Armor. Decisión explícita: fail-open (se deja
            # pasar la respuesta sin escanear) en vez de bloquear cada vez
            # que la API tenga un blip. Para fail-closed, cambiar el
            # `return None` de abajo por `last_message.content = OUTPUT_BLOCK_MESSAGE`.
            logger.warning(
                "Model Armor no disponible para sanitize_model_response (%s). "
                "Respuesta entregada sin escanear (fail-open, sin backup local).",
                exc,
                extra={"guardrail_layer": LAYER_NAME, "model_armor_output_scan": "failed_open"},
            )
            return None

        if result.filter_match_state == self._modelarmor_v1.FilterMatchState.NO_MATCH_FOUND:
            return None

        masked = self._extract_deidentified_text(result)
        if masked is not None:
            last_message.content = masked
            logger.info(
                "Model Armor: PII enmascarada en la respuesta del agente",
                extra={"guardrail_layer": LAYER_NAME},
            )
            return None

        log_block(logger, LAYER_NAME, text, reason="model_armor_match_response", extra={"engine": "model_armor"})
        last_message.content = OUTPUT_BLOCK_MESSAGE
        return None

    def _extract_deidentified_text(self, result) -> Optional[str]:
        """Si el único filtro que hizo match es SDP (datos sensibles) y trae
        texto de-identificado, lo retorna para enmascarar en vez de bloquear.
        Si además hace match cualquier filtro binario (RAI, prompt
        injection/jailbreak, URLs maliciosas, CSAM), se prioriza el bloqueo.

        Nota de estructura: `SanitizationResult.filter_results` es un map
        cuyos VALORES son `FilterResult` — un wrapper con un subcampo por
        tipo de filtro (`rai_filter_result`, `sdp_filter_result`,
        `pi_and_jailbreak_filter_result`, `malicious_uri_filter_result`,
        `csam_filter_filter_result`); el match_state vive en ese subcampo, no
        en el wrapper. Se recorre por subcampo (no por clave del map) para no
        depender de adivinar el string exacto de cada clave — confirmado
        inspeccionando `google.cloud.modelarmor_v1` instalado (protobuf)."""
        filter_results = getattr(result, "filter_results", None) or {}

        blocked = False
        deidentified_text: Optional[str] = None

        for wrapper in filter_results.values():
            for field_name in _BLOCKING_SUBFIELDS:
                sub = getattr(wrapper, field_name, None)
                if sub is not None and self._matched(sub):
                    blocked = True

            sdp = getattr(wrapper, "sdp_filter_result", None)
            deidentify_result = getattr(sdp, "deidentify_result", None) if sdp is not None else None
            if deidentify_result is not None and self._matched(deidentify_result):
                data = getattr(deidentify_result, "data", None)
                text = getattr(data, "text", None) if data is not None else None
                if isinstance(text, str) and text:
                    deidentified_text = text

        if blocked:
            return None
        return deidentified_text

    def _matched(self, sub_result) -> bool:
        return getattr(sub_result, "match_state", None) == self._modelarmor_v1.FilterMatchState.MATCH_FOUND
