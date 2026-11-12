from src.services import document_service


def handle_read_document(doc_id: str) -> str:
    return document_service.read_document(doc_id)


def handle_edit_document(doc_id: str, old_str: str, new_str: str) -> str:
    return document_service.edit_document(doc_id, old_str, new_str)
