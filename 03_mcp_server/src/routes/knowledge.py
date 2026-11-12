from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult
from pydantic import Field

from src.controllers import knowledge_controller


def register_knowledge_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="retrieve_documents",
        description=(
            "Busca en la base de conocimiento (Qdrant) documentos relevantes sobre la "
            "academia: programas, cursos, temarios, precios, duración, requisitos, "
            "certificaciones e información institucional en general. Usa siempre esta "
            "herramienta para responder preguntas sobre estos temas, en lugar de "
            "responder de memoria."
        ),
    )
    def retrieve_documents(
        query: str = Field(description="Consulta de búsqueda en lenguaje natural"),
        k: int = Field(default=4, description="Cantidad máxima de documentos a devolver"),
    ) -> CallToolResult:
        return knowledge_controller.handle_retrieve_documents(query, k)
