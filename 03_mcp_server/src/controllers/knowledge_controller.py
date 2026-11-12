from mcp.types import CallToolResult, TextContent

from src.services import knowledge_service


def handle_retrieve_documents(query: str, k: int) -> CallToolResult:
    """Devuelve un CallToolResult explícito (en vez de solo texto) para que los
    contextos recuperados viajen como structuredContent — así el cliente MCP
    (langchain-mcp-adapters) los expone como artifact del ToolMessage, igual
    que hacía la tool local original con response_format="content_and_artifact"."""
    content, contexts = knowledge_service.retrieve_documents(query, k)
    return CallToolResult(
        content=[TextContent(type="text", text=content)],
        structuredContent={"contexts": contexts},
    )
