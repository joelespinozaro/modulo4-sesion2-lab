"""InputGuardrail — Pipeline de validación de entrada de 8 capas (HU SEC-001).

Las capas se ejecutan en orden estricto 1→8 (nunca en paralelo ni en orden
distinto) gracias al orden de la lista `middleware=[...]` que recibe
`create_agent`. Cualquier capa puede cortocircuitar el pipeline retornando
`jump_to: "end"`, evitando que se ejecuten las capas restantes. No existe
ningún flag de bypass/debug: `build_input_guardrails()` siempre construye
las 8 capas completas.
"""
from typing import List

from langchain.agents.middleware import AgentMiddleware

from src.services.guardrails.layer1_secrets import SecretKeysMiddleware
from src.services.guardrails.layer2_prompt_injection import PromptInjectionMiddleware
from src.services.guardrails.layer3_toxicity import ToxicityMiddleware
from src.services.guardrails.layer4_custom_regex import CustomRegexMiddleware
from src.services.guardrails.layer5_pii import PIIGuardrailMiddleware
from src.services.guardrails.layer6_url_filter import UrlFilterMiddleware
from src.services.guardrails.layer7_prompt_guard import PromptGuardMiddleware
from src.services.guardrails.layer8_llama_guard import LlamaGuardMiddleware

__all__ = ["build_input_guardrails"]


def build_input_guardrails() -> List[AgentMiddleware]:
    """Construye el pipeline completo de 8 capas, en el orden fijo requerido.

    Las capas 1-4 y 6 son deterministas (REGEX, sin dependencia externa).
    La capa 5 usa Presidio con fallback local a REGEX. Las capas 7-8 usan la
    API de Groq (Llama Prompt Guard 2 / Llama Guard 4) con fail-close.
    """
    return [
        SecretKeysMiddleware(),
        PromptInjectionMiddleware(),
        ToxicityMiddleware(),
        CustomRegexMiddleware(),
        PIIGuardrailMiddleware(),
        UrlFilterMiddleware(),
        PromptGuardMiddleware(),
        LlamaGuardMiddleware(),
    ]
