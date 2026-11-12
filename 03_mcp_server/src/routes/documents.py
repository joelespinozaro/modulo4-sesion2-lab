from mcp.server.fastmcp import FastMCP
from pydantic import Field

from src.controllers import document_controller


def register_document_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="read_doc_contents",
        description="Lee el contenido de un documento y lo devuelve como texto.",
    )
    def read_document(
        doc_id: str = Field(description="Id del documento a leer"),
    ) -> str:
        return document_controller.handle_read_document(doc_id)

    @mcp.tool(
        name="edit_document",
        description=(
            "Edita un documento reemplazando un texto (old_str) por otro (new_str) "
            "dentro de su contenido. old_str debe coincidir exactamente con el "
            "contenido actual del documento, incluyendo espacios, así que SIEMPRE hay "
            "que llamar primero a read_doc_contents para obtener el texto exacto antes "
            "de usar esta herramienta — nunca inventar old_str. Para reemplazar todo "
            "el documento, usar el contenido completo leído como old_str. Para agregar "
            "texto, usar el contenido completo leído como old_str y ese mismo "
            "contenido más el texto nuevo como new_str."
        ),
    )
    def edit_document(
        doc_id: str = Field(description="Id del documento que se va a editar"),
        old_str: str = Field(
            description="El texto a reemplazar. Debe coincidir exactamente, incluyendo espacios."
        ),
        new_str: str = Field(description="El texto nuevo que reemplazará al texto anterior."),
    ) -> str:
        return document_controller.handle_edit_document(doc_id, old_str, new_str)
