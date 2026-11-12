import os

from decouple import config

OPENAI_API_KEY: str = config("OPENAI_API_KEY")
OPENAI_MODEL: str = config("OPENAI_MODEL")

DATABASE_URL: str = config("DATABASE_URL")
HISTORY_LIMIT: int = config("HISTORY_LIMIT", default=10, cast=int)

NEON_API_KEY: str | None = config("NEON_API_KEY", default=None)
NEON_PROJECT_ID: str | None = config("NEON_PROJECT_ID", default=None)

# 03_mcp_server es su propio servicio (Cloud Run aparte), conectado por HTTP
# streamable — no un subproceso local. En dev local, apunta al server corriendo
# aparte (ej. http://localhost:8000/mcp); en producción, al Cloud Run privado
# (autenticado con ID token vía src.utils.gcp_auth.GoogleIDTokenAuth).
DEMO_MCP_SERVER_URL: str | None = config("DEMO_MCP_SERVER_URL", default=None)

LANGSMITH_TRACING: bool = config("LANGSMITH_TRACING", default=False, cast=bool)
LANGSMITH_API_KEY: str | None = config("LANGSMITH_API_KEY", default=None)
LANGSMITH_PROJECT: str = config("LANGSMITH_PROJECT", default="agente-mcp")
LANGSMITH_ENDPOINT: str = config("LANGSMITH_ENDPOINT", default="https://api.smith.langchain.com")

# El SDK de LangSmith (usado internamente por langchain) lee estas variables
# directamente de las variables de entorno del proceso, no del config() de
# decouple, así que hay que propagarlas explícitamente a os.environ.
if LANGSMITH_TRACING and LANGSMITH_API_KEY:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_ENDPOINT", LANGSMITH_ENDPOINT)
    os.environ.setdefault("LANGSMITH_API_KEY", LANGSMITH_API_KEY)
    os.environ.setdefault("LANGSMITH_PROJECT", LANGSMITH_PROJECT)

    # El tracing automático de LangChain (activado por las env vars de arriba)
    # construye su propio Client() bajo el capó vía este singleton cacheado.
    # Sembrándolo acá, ANTES de que corra cualquier trace, todas las trazas
    # quedan ofuscadas (secretos + PII) del mismo modo que los logs — ver
    # src.utils.langsmith_anonymizer. Si ya hay un cliente cacheado (import
    # tardío de otro módulo), esto no lo pisa: get_cached_client() ignora los
    # kwargs cuando el singleton ya existe.
    from langsmith.run_trees import get_cached_client

    from src.utils.langsmith_anonymizer import build_langsmith_anonymizer

    get_cached_client(anonymizer=build_langsmith_anonymizer())

# InputGuardrail (HU SEC-001) — Capas 7 y 8, servidas vía Groq API
GROQ_API_KEY: str = config("GROQ_API_KEY")
GROQ_PROMPT_GUARD_MODEL: str = config(
    "GROQ_PROMPT_GUARD_MODEL", default="meta-llama/Llama-Prompt-Guard-2-86M"
)
GROQ_LLAMA_GUARD_MODEL: str = config(
    "GROQ_LLAMA_GUARD_MODEL", default="openai/gpt-oss-safeguard-20b"
)
GROQ_TIMEOUT_SECONDS: float = config("GROQ_TIMEOUT_SECONDS", default=3, cast=float)

# InputGuardrail — Capa 4 (anti-ReDoS)
CUSTOM_REGEX_TIMEOUT_SECONDS: float = config("CUSTOM_REGEX_TIMEOUT_SECONDS", default=1, cast=float)

# InputGuardrail — motor de content-safety: "model_armor" (GCP, con fallback
# automático al pipeline local si la API falla) o "local" (siempre el pipeline
# propio). Las capas 1 (secrets) y 4 (regex custom) están siempre activas sin
# importar el motor — no son reemplazables por Model Armor.
GUARDRAIL_ENGINE: str = config("GUARDRAIL_ENGINE", default="model_armor")
MODEL_ARMOR_PROJECT_ID: str | None = config("MODEL_ARMOR_PROJECT_ID", default=None)
MODEL_ARMOR_LOCATION: str = config("MODEL_ARMOR_LOCATION", default="us-central1")
MODEL_ARMOR_TEMPLATE_ID: str | None = config("MODEL_ARMOR_TEMPLATE_ID", default=None)
MODEL_ARMOR_TIMEOUT_SECONDS: float = config("MODEL_ARMOR_TIMEOUT_SECONDS", default=3, cast=float)

# El cliente de Model Armor (google-cloud-modelarmor) resuelve credenciales
# vía Application Default Credentials, leyendo esta variable directamente de
# os.environ — decouple no la propaga solo por estar en .env, así que hay que
# reenviarla explícitamente (mismo patrón que LANGSMITH_* más abajo).
# Alternativa sin esta variable: `gcloud auth application-default login`.
GOOGLE_APPLICATION_CREDENTIALS: str | None = config("GOOGLE_APPLICATION_CREDENTIALS", default=None)
if GOOGLE_APPLICATION_CREDENTIALS:
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", GOOGLE_APPLICATION_CREDENTIALS)

# Hooks (parte 3): presupuesto de tokens por conversación
TOKEN_BUDGET: int = config("TOKEN_BUDGET", default=8000, cast=int)
