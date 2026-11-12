from typing import Any, Dict, List, Tuple

from src.repositories import knowledge_repository


def retrieve_documents(query: str, k: int) -> Tuple[str, List[Dict[str, Any]]]:
    results = knowledge_repository.search_similar(query, k)

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
