from src.repositories import document_repository


def read_document(doc_id: str) -> str:
    if not document_repository.document_exists(doc_id):
        raise ValueError(f"Doc with id {doc_id} not found")
    return document_repository.get_document(doc_id)


def edit_document(doc_id: str, old_str: str, new_str: str) -> str:
    if not document_repository.document_exists(doc_id):
        raise ValueError(f"Doc with id {doc_id} not found")
    return document_repository.update_document(doc_id, old_str, new_str)
