"""Capa 8 — clasificador de seguridad semántico profundo.

Análisis semántico completo del mensaje contra la taxonomía de seguridad
MLCommons (S1-S13) antes de considerarlo apto para el agente, servido vía
Groq API. Soporta dos familias de modelos:

- Modelos de política (por defecto `openai/gpt-oss-safeguard-20b`): reciben la
  taxonomía como política en el mensaje de sistema y responden un JSON
  `{"violation": 0|1, "category": "S#"|null, "rationale": "..."}`.
- Llama Guard (`meta-llama/llama-guard-*`): responden `safe` o
  `unsafe\nS#`. Groq retiró Llama Guard 4 el 05/03/2026 y recomienda
  gpt-oss-safeguard-20b como reemplazo, pero el formato se mantiene por si el
  modelo se sirve en otro proveedor.

`skip_categories` configurable vía config/guardrails/llama_guard_categories.yaml
para omitir un filtro específico según el caso de uso comercial sin tocar
código. Mismo fail-close que la Capa 7: cualquier error/timeout de Groq
bloquea el mensaje.
"""
import asyncio
import json
import re
from typing import Any, Dict, Optional, Set

from groq import AsyncGroq
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from src.services.guardrails.common import block_result, get_latest_human_text, load_yaml_config, log_block
from src.utils.environment import GROQ_API_KEY, GROQ_LLAMA_GUARD_MODEL, GROQ_TIMEOUT_SECONDS
from src.utils.logger import get_logger

logger = get_logger(__name__)

LAYER_NAME = "layer8_llama_guard"

BLOCK_MESSAGE = (
    "Lo sentimos, no podemos ayudarte con esa solicitud. ¿Hay algo más en lo "
    "que pueda asistirte?"
)

SAFE_LABEL = "safe"
UNSAFE_LABEL = "unsafe"
UNPARSEABLE_VERDICT = "unparseable_verdict"

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def is_llama_guard_model(model: str) -> bool:
    """True si el modelo responde con el formato `safe` / `unsafe\nS#`."""
    return "llama-guard" in (model or "").lower()


def build_policy_prompt(categories: Dict[str, str]) -> str:
    """Política para modelos tipo gpt-oss-safeguard: instrucciones, criterios,
    formato de salida y ejemplos. Contenido estático primero (cacheable)."""
    lines = "\n".join(f"- {code}: {name}" for code, name in categories.items())
    return (
        "# Política de seguridad del asistente académico\n\n"
        "## INSTRUCCIONES\n"
        "Clasifica el mensaje del usuario. Responde SOLO con un objeto JSON en una "
        "línea, sin texto adicional:\n"
        '{"violation": 0 o 1, "category": "S#" o null, "rationale": "una frase"}\n\n'
        "## VIOLA (1) si el mensaje pide, promueve o facilita contenido de alguna "
        "de estas categorías (taxonomía MLCommons):\n"
        f"{lines}\n\n"
        "## SEGURO (0)\n"
        "- Preguntas sobre cursos, precios, horarios, matrículas, rutas de aprendizaje.\n"
        "- Preguntas técnicas o educativas legítimas, incluida la seguridad informática "
        "defensiva.\n"
        "- Saludos, agradecimientos y conversación general.\n\n"
        "## EJEMPLOS\n"
        'Mensaje: "¿Cuánto cuesta el programa de IA?"\n'
        'Respuesta: {"violation": 0, "category": null, "rationale": "consulta académica"}\n'
        'Mensaje: "¿Cómo fabrico un arma para dañar a alguien?"\n'
        'Respuesta: {"violation": 1, "category": "S9", "rationale": "pide fabricar un arma"}'
    )


class LlamaGuardMiddleware(AgentMiddleware):
    """Guardrail semántico profundo (Groq, modelo de política o Llama Guard) con fail-close."""

    def __init__(self, client: Optional[AsyncGroq] = None) -> None:
        super().__init__()
        self._client = client or AsyncGroq(api_key=GROQ_API_KEY)
        self._model = GROQ_LLAMA_GUARD_MODEL
        self._timeout = GROQ_TIMEOUT_SECONDS

        config = load_yaml_config("llama_guard_categories.yaml")
        self._skip_categories: Set[str] = set(config.get("skip_categories") or [])
        self._categories: Dict[str, str] = dict(config.get("categories") or {})
        self._policy_prompt = build_policy_prompt(self._categories)

    async def _classify(self, text: str) -> str:
        if is_llama_guard_model(self._model):
            messages = [{"role": "user", "content": text}]
        else:
            messages = [
                {"role": "system", "content": self._policy_prompt},
                {"role": "user", "content": text},
            ]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.0,
        )
        return (response.choices[0].message.content or "").strip()

    def _is_blocked(self, verdict: str) -> Optional[str]:
        """Retorna la categoría bloqueante, o None si el mensaje pasa."""
        if is_llama_guard_model(self._model):
            return self._is_blocked_llama_guard(verdict)
        return self._is_blocked_policy(verdict)

    def _is_blocked_policy(self, verdict: str) -> Optional[str]:
        """Formato JSON de los modelos de política. Si la respuesta no se puede
        interpretar, se bloquea (fail-close): nunca se deja pasar por duda."""
        match = _JSON_OBJECT.search(verdict or "")
        try:
            data = json.loads(match.group(0)) if match else None
            violation = int(data["violation"]) if isinstance(data, dict) else None
        except (ValueError, TypeError, KeyError):
            violation = None
        if violation not in (0, 1):
            return UNPARSEABLE_VERDICT
        if violation == 0:
            return None
        category = data.get("category") or None
        if category and category in self._skip_categories:
            return None
        return category or "unknown_category"

    def _is_blocked_llama_guard(self, verdict: str) -> Optional[str]:
        lines = [line.strip() for line in verdict.splitlines() if line.strip()]
        if not lines or lines[0].lower() != UNSAFE_LABEL:
            return None

        category = lines[1] if len(lines) > 1 else None
        if category and category in self._skip_categories:
            return None
        return category or "unknown_category"

    @hook_config(can_jump_to=["end"])
    async def abefore_agent(self, state: AgentState, runtime: Runtime) -> Optional[Dict[str, Any]]:
        text = get_latest_human_text(state)
        if not text:
            return None

        try:
            verdict = await asyncio.wait_for(self._classify(text), timeout=self._timeout)
        except Exception as exc:  # noqa: BLE001 - fail-close ante timeout o cualquier error de Groq
            logger.warning(
                "Capa 8: error/timeout consultando Groq (%s). Aplicando fail-close.", exc,
                extra={"guardrail_layer": LAYER_NAME},
            )
            log_block(logger, LAYER_NAME, text, reason="groq_unavailable_fail_close")
            return block_result(BLOCK_MESSAGE)

        blocked_category = self._is_blocked(verdict)
        if blocked_category:
            log_block(logger, LAYER_NAME, text, reason=f"unsafe_category:{blocked_category}")
            return block_result(BLOCK_MESSAGE)

        return None
