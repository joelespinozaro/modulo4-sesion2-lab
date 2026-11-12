from mcp.server.fastmcp import FastMCP

from src.routes.documents import register_document_tools
from src.routes.knowledge import register_knowledge_tools
from src.routes.pokemon import register_pokemon_tools
from src.routes.pptx import register_pptx_tools
from src.routes.skills import register_skill_resources
from src.routes.superhero import register_superhero_tools
from src.utils.logger import get_logger

logger = get_logger(__name__)

mcp = FastMCP(
    "DemoMCPServer",
    log_level="ERROR",
    dependencies=[
        "httpx",
        "python-decouple",
        "python-json-logger",
        "langchain-openai",
        "langchain-qdrant",
        "qdrant-client",
        "python-pptx",
        "pyyaml",
    ],
)
register_document_tools(mcp)
register_pokemon_tools(mcp)
register_knowledge_tools(mcp)
register_superhero_tools(mcp)
register_pptx_tools(mcp)
register_skill_resources(mcp)

if __name__ == "__main__":
    logger.info("Iniciando DemoMCPServer (stdio)")
    mcp.run(transport="stdio")
