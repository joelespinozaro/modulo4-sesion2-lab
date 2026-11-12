from src.services.guardrails.common import get_latest_human_text
from tests.guardrails.conftest import build_state


def test_build_input_guardrails_returns_7_layers_in_fixed_order(monkeypatch):
    """No debe existir ningún flag/modo debug que altere el orden o cantidad
    de capas activas (criterio de la HU: cero excepciones / sin bypass).

    La Capa 5 (PII) está desactivada a propósito: el PII ya no se bloquea en
    la entrada, se deja pasar y se ofusca automáticamente en logs vía
    PIIRedactionFilter (src.utils.pii_log_filter) — ver docstring de
    src.services.guardrails.__init__."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    import src.services.guardrails as guardrails_module

    # Aislar de MODEL_ARMOR_PROJECT_ID/TEMPLATE_ID reales en .env — si están
    # configurados (y hay ADC válidas en la máquina), build_input_guardrails()
    # usaría Model Armor de verdad en vez del pipeline local de 7 capas.
    monkeypatch.setattr(guardrails_module, "MODEL_ARMOR_PROJECT_ID", None)
    monkeypatch.setattr(guardrails_module, "MODEL_ARMOR_TEMPLATE_ID", None)

    from src.services.guardrails import build_input_guardrails
    from src.services.guardrails.layer1_secrets import SecretKeysMiddleware
    from src.services.guardrails.layer2_prompt_injection import PromptInjectionMiddleware
    from src.services.guardrails.layer3_toxicity import ToxicityMiddleware
    from src.services.guardrails.layer4_custom_regex import CustomRegexMiddleware
    from src.services.guardrails.layer6_url_filter import UrlFilterMiddleware
    from src.services.guardrails.layer7_prompt_guard import PromptGuardMiddleware
    from src.services.guardrails.layer8_llama_guard import LlamaGuardMiddleware

    expected_order = [
        SecretKeysMiddleware,
        PromptInjectionMiddleware,
        ToxicityMiddleware,
        CustomRegexMiddleware,
        UrlFilterMiddleware,
        PromptGuardMiddleware,
        LlamaGuardMiddleware,
    ]

    guardrails = build_input_guardrails()

    assert len(guardrails) == 7
    assert [type(g) for g in guardrails] == expected_order


def test_build_input_guardrails_uses_model_armor_when_configured(monkeypatch):
    """Cuando GUARDRAIL_ENGINE=model_armor y hay config completa (y el
    cliente se puede construir), el pipeline usa ModelArmorMiddleware en vez
    de las 5 capas locales que reemplaza — las capas 1 (secrets) y 4 (regex
    custom) siguen siempre activas."""
    import src.services.guardrails as guardrails_module
    import src.services.guardrails.layer_model_armor as model_armor_module
    from src.services.guardrails.layer1_secrets import SecretKeysMiddleware
    from src.services.guardrails.layer4_custom_regex import CustomRegexMiddleware

    class _FakeModelArmorMiddleware:
        """Evita construir un cliente GCP real (requeriría ADC) — acá solo
        se prueba el wiring de build_input_guardrails(), no el middleware
        en sí (eso lo cubre test_layer_model_armor.py)."""

    monkeypatch.setattr(guardrails_module, "GUARDRAIL_ENGINE", "model_armor")
    monkeypatch.setattr(guardrails_module, "MODEL_ARMOR_PROJECT_ID", "test-project")
    monkeypatch.setattr(guardrails_module, "MODEL_ARMOR_TEMPLATE_ID", "test-template")
    monkeypatch.setattr(model_armor_module, "ModelArmorMiddleware", _FakeModelArmorMiddleware)

    guardrails = guardrails_module.build_input_guardrails()

    assert [type(g) for g in guardrails] == [
        SecretKeysMiddleware,
        CustomRegexMiddleware,
        _FakeModelArmorMiddleware,
    ]


def test_build_input_guardrails_falls_back_to_local_when_client_init_fails(monkeypatch, caplog):
    """Si GUARDRAIL_ENGINE=model_armor y la config está completa pero el
    cliente no puede inicializarse (ej. sin Application Default Credentials,
    o cualquier otro error de construcción), el pipeline cae al local
    completo en vez de romper el arranque del servicio.

    Se fuerza el fallo con un stand-in que siempre lanza en __init__, en vez
    de depender de que la máquina de test carezca de ADC real — si el
    entorno SÍ tiene `gcloud auth application-default login` corrido (como
    puede pasar en dev), ModelArmorMiddleware() construiría el cliente sin
    error y este test dejaría de probar la rama de fallback."""
    import logging

    import src.services.guardrails as guardrails_module
    import src.services.guardrails.layer_model_armor as model_armor_module
    from src.services.guardrails.layer1_secrets import SecretKeysMiddleware

    class _FailingModelArmorMiddleware:
        def __init__(self) -> None:
            raise RuntimeError("simulated: no ADC / client init failure")

    monkeypatch.setattr(guardrails_module, "GUARDRAIL_ENGINE", "model_armor")
    monkeypatch.setattr(guardrails_module, "MODEL_ARMOR_PROJECT_ID", "test-project")
    monkeypatch.setattr(guardrails_module, "MODEL_ARMOR_TEMPLATE_ID", "test-template")
    monkeypatch.setattr(model_armor_module, "ModelArmorMiddleware", _FailingModelArmorMiddleware)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    with caplog.at_level(logging.WARNING):
        guardrails = guardrails_module.build_input_guardrails()

    assert len(guardrails) == 7
    assert isinstance(guardrails[0], SecretKeysMiddleware)
    assert any("ModelArmorMiddleware" in record.message for record in caplog.records)


def test_build_input_guardrails_falls_back_to_local_when_model_armor_misconfigured(monkeypatch, caplog):
    """Si GUARDRAIL_ENGINE=model_armor pero falta el project_id/template_id,
    se arma el pipeline local completo (nunca falla el arranque) y se
    registra un warning para que sea visible en observabilidad."""
    import logging

    import src.services.guardrails as guardrails_module
    from src.services.guardrails.layer1_secrets import SecretKeysMiddleware

    monkeypatch.setattr(guardrails_module, "GUARDRAIL_ENGINE", "model_armor")
    monkeypatch.setattr(guardrails_module, "MODEL_ARMOR_PROJECT_ID", None)
    monkeypatch.setattr(guardrails_module, "MODEL_ARMOR_TEMPLATE_ID", None)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    with caplog.at_level(logging.WARNING):
        guardrails = guardrails_module.build_input_guardrails()

    assert len(guardrails) == 7
    assert isinstance(guardrails[0], SecretKeysMiddleware)
    assert any("MODEL_ARMOR_PROJECT_ID" in record.message for record in caplog.records)


def test_get_latest_human_text_ignores_history_and_uses_current_message(sample_history):
    """El mensaje a validar en cada capa debe ser siempre el más reciente,
    nunca uno del historial antepuesto por AgentService.chat."""
    state = build_state("mensaje actual del usuario", history=sample_history)

    assert get_latest_human_text(state) == "mensaje actual del usuario"


def test_get_latest_human_text_returns_none_if_last_message_is_not_human():
    from langchain_core.messages import AIMessage, HumanMessage

    state = {"messages": [HumanMessage(content="hola"), AIMessage(content="respuesta")]}

    assert get_latest_human_text(state) is None
