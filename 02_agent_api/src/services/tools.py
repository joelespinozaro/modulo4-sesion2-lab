from typing import Any, Dict, List, Tuple

from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore

from src.utils.environment import (
    OPENAI_API_KEY,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


@tool
def get_weather(location: str) -> str:
    """Devuelve el pronóstico del clima actual para la ubicación indicada."""
    return f"El clima en {location} es soleado con una temperatura de 22°C."


_vector_store: QdrantVectorStore | None = None


def _get_vector_store() -> QdrantVectorStore:
    global _vector_store
    if _vector_store is None:
        logger.info(
            "Inicializando QdrantVectorStore",
            extra={"collection": QDRANT_COLLECTION_NAME},
        )
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", api_key=OPENAI_API_KEY
        )
        _vector_store = QdrantVectorStore.from_existing_collection(
            embedding=embeddings,
            collection_name=QDRANT_COLLECTION_NAME,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )
    return _vector_store


@tool(response_format="content_and_artifact")
def retrieve_documents(query: str, k: int = 4) -> Tuple[str, List[Dict[str, Any]]]:
    """Busca en la base de conocimiento (Qdrant) documentos relevantes sobre la
    academia: programas, cursos, temarios, precios, duración, requisitos,
    certificaciones e información institucional en general. Usa siempre esta
    herramienta para responder preguntas sobre estos temas, en lugar de
    responder de memoria."""
    vector_store = _get_vector_store()
    results = vector_store.similarity_search_with_score(query, k=k)

    if not results:
        return "No se encontraron documentos relevantes.", []

    contexts: List[Dict[str, Any]] = []
    content_parts: List[str] = []
    for doc, score in results:
        contexts.append(
            {
                "page_content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score),
            }
        )
        content_parts.append(doc.page_content)

    content = "\n\n---\n\n".join(content_parts)
    return content, contexts