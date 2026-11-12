from decouple import config

OPENAI_API_KEY: str = config("OPENAI_API_KEY")
OPENAI_MODEL: str = config("OPENAI_MODEL")

DATABASE_URL: str = config("DATABASE_URL")
HISTORY_LIMIT: int = config("HISTORY_LIMIT", default=10, cast=int)

QDRANT_URL: str | None = config("QDRANT_URL", default=None)
QDRANT_API_KEY: str | None = config("QDRANT_API_KEY", default=None)
QDRANT_COLLECTION_NAME: str = config("QDRANT_COLLECTION_NAME", default="documents")

NEON_API_KEY: str | None = config("NEON_API_KEY", default=None)

LANGSMITH_API_KEY: str | None = config("LANGSMITH_API_KEY", default=None)
LANGSMITH_PROJECT: str = config("LANGSMITH_PROJECT", default="agente-mcp")
LANGSMITH_ENDPOINT: str = config("LANGSMITH_ENDPOINT", default="https://api.smith.langchain.com")