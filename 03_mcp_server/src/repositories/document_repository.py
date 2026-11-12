_docs: dict[str, str] = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
}


def document_exists(doc_id: str) -> bool:
    return doc_id in _docs


def get_document(doc_id: str) -> str | None:
    return _docs.get(doc_id)


def update_document(doc_id: str, old_str: str, new_str: str) -> str:
    _docs[doc_id] = _docs[doc_id].replace(old_str, new_str)
    return _docs[doc_id]
