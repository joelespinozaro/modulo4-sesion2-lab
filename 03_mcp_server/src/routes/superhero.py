from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult
from pydantic import Field

from src.controllers import superhero_controller


def register_superhero_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_superhero",
        description=(
            "Obtiene información detallada de un héroe o villano por su id numérico en "
            "SuperheroAPI: nombre real, editorial, alineación (bueno/malo/neutral), "
            "estadísticas de poder e imagen. Si no conoces el id, usa primero "
            "search_superheroes."
        ),
    )
    async def get_superhero(
        id: str = Field(description="Id numérico del personaje en SuperheroAPI"),
    ) -> CallToolResult:
        return await superhero_controller.handle_get_superhero(id)

    @mcp.tool(
        name="search_superheroes",
        description=(
            "Busca héroes y villanos por nombre (o parte del nombre) en SuperheroAPI. "
            "Devuelve todos los personajes que coinciden, con su id, nombre real, "
            "editorial, alineación y estadísticas de poder."
        ),
    )
    async def search_superheroes(
        name: str = Field(description="Nombre o parte del nombre del personaje a buscar"),
    ) -> CallToolResult:
        return await superhero_controller.handle_search_superheroes(name)
