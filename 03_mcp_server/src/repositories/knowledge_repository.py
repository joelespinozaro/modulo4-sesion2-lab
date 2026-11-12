from typing import Any, List, Tuple

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


def search_similar(query: str, k: int) -> List[Tuple[Any, float]]:
    vector_store = _get_vector_store()
    return vector_store.similarity_search_with_score(query, k=k)
