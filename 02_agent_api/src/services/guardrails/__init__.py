"""InputGuardrail — Pipeline de content-safety (HU SEC-001).

Las capas se ejecutan en orden estricto (nunca en paralelo ni en orden
distinto) gracias al orden de la lista `middleware=[...]` que recibe
`create_agent`. Cualquier capa puede cortocircuitar el pipeline retornando
`jump_to: "end"`.

Dos motores posibles, elegidos vía `GUARDRAIL_ENGINE` (env var, ver
`src.utils.environment`):
- `"model_armor"` (default): GCP Model Armor (`layer_model_armor.py`)
  reemplaza las 5 capas de content-safety genérico (prompt injection,
  toxicidad, URLs maliciosas, y las 2 semánticas vía Groq) y además escanea
  la respuesta del agente (capacidad nueva, sin equivalente local). Si la
  API de Model Armor falla en tiempo de request, cae automáticamente al
  pipeline local como backup (ver `ModelArmorMiddleware._run_local_fallback`).
  Si falta configuración (`MODEL_ARMOR_PROJECT_ID`/`MODEL_ARMOR_TEMPLATE_ID`)
  o el cliente no puede inicializarse (ej. sin Application Default
  Credentials configuradas), cae a `local` ya en la construcción del
  pipeline — nunca por esto se cae el arranque del servicio.
- `"local"`: siempre el pipeline propio (regex + Groq), sin dependencia de GCP.

En AMBOS motores, las capas 1 (secrets) y 4 (regex custom) están siempre
activas — son reglas de negocio propias que ningún motor externo conoce.

La Capa 5 (PII) está desconectada a propósito en ambos motores: el PII ya no
se bloquea ni se enmascara en la entrada (debe llegar íntegro al agente para
no romper flujos que lo necesitan) — la protección se movió a la ofuscación
automática de logs, ver `src.utils.pii_log_filter.PIIRedactionFilter`. La
clase `PIIGuardrailMiddleware` (`layer5_pii.py`) se mantiene funcional y
testeada por si se necesita reactivar el bloqueo en la entrada más adelante.
"""
from typing import List

from langchain.agents.middleware import AgentMiddleware

from src.services.guardrails.layer1_secrets import SecretKeysMiddleware
from src.services.guardrails.layer2_prompt_injection import PromptInjectionMiddleware
from src.services.guardrails.layer3_toxicity import ToxicityMiddleware
from src.services.guardrails.layer4_custom_regex import CustomRegexMiddleware
# from src.services.guardrails.layer5_pii import PIIGuardrailMiddleware  # desactivada: ver docstring del módulo
from src.services.guardrails.layer6_url_filter import UrlFilterMiddleware
from src.services.guardrails.layer7_prompt_guard import PromptGuardMiddleware
from src.services.guardrails.layer8_llama_guard import LlamaGuardMiddleware
from src.utils.environment import GUARDRAIL_ENGINE, MODEL_ARMOR_PROJECT_ID, MODEL_ARMOR_TEMPLATE_ID
from src.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = ["build_input_guardrails"]


def _local_content_safety_layers() -> List[AgentMiddleware]:
    """Las 7 capas propias (sin Model Armor), sin importar el motor elegido."""
    return [
        SecretKeysMiddleware(),
        PromptInjectionMiddleware(),
        ToxicityMiddleware(),
        CustomRegexMiddleware(),
        UrlFilterMiddleware(),
        PromptGuardMiddleware(),
        LlamaGuardMiddleware(),
    ]


def build_input_guardrails() -> List[AgentMiddleware]:
    """Construye el pipeline activo según `GUARDRAIL_ENGINE` — ver docstring
    del módulo para el detalle de cada motor y el fallback automático."""
    use_model_armor = (
        GUARDRAIL_ENGINE == "model_armor"
        and bool(MODEL_ARMOR_PROJECT_ID)
        and bool(MODEL_ARMOR_TEMPLATE_ID)
    )
    if GUARDRAIL_ENGINE == "model_armor" and not use_model_armor:
        logger.warning(
            "GUARDRAIL_ENGINE=model_armor pero falta MODEL_ARMOR_PROJECT_ID/"
            "MODEL_ARMOR_TEMPLATE_ID. Usando pipeline local."
        )

    if not use_model_armor:
        return _local_content_safety_layers()

    from src.services.guardrails.layer_model_armor import ModelArmorMiddleware

    try:
        model_armor_layer = ModelArmorMiddleware()
    except Exception as exc:  # noqa: BLE001 - ej. ADC no configuradas, template inválido
        logger.warning(
            "No se pudo inicializar ModelArmorMiddleware (%s). Usando pipeline local.",
            exc,
        )
        return _local_content_safety_layers()

    return [
        SecretKeysMiddleware(),
        CustomRegexMiddleware(),
        model_armor_layer,
    ]
