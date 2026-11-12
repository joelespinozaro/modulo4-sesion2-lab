from decouple import config

POKEAPI_BASE_URL: str = config(
    "POKEAPI_BASE_URL", default="https://pokeapi.co/api/v2"
)
HTTP_TIMEOUT_SECONDS: float = config("HTTP_TIMEOUT_SECONDS", default=10, cast=float)

# Qdrant (base de conocimiento para retrieve_documents)
OPENAI_API_KEY: str = config("OPENAI_API_KEY")
QDRANT_URL: str | None = config("QDRANT_URL", default=None)
QDRANT_API_KEY: str | None = config("QDRANT_API_KEY", default=None)
QDRANT_COLLECTION_NAME: str = config("QDRANT_COLLECTION_NAME", default="documents")

# SuperheroAPI (https://superheroapi.com/)
SUPERHERO_API_BASE_URL: str = config(
    "SUPERHERO_API_BASE_URL", default="https://www.superheroapi.com/api.php"
)
SUPERHERO_API_TOKEN: str = config("SUPERHERO_API_TOKEN")
