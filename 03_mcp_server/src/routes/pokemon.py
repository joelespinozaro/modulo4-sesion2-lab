from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult
from pydantic import Field

from src.controllers import pokemon_controller


def register_pokemon_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_pokemon",
        description=(
            "Obtiene información detallada de un Pokémon desde PokeAPI: tipos, "
            "habilidades, altura, peso, experiencia base, estadísticas base e imagen."
        ),
    )
    async def get_pokemon(
        name_or_id: str = Field(
            description="Nombre del Pokémon (ej. 'pikachu') o su número de Pokédex (ej. '25')"
        ),
    ) -> CallToolResult:
        return await pokemon_controller.handle_get_pokemon(name_or_id)

    @mcp.tool(
        name="list_pokemons",
        description="Lista nombres de Pokémon desde PokeAPI, con paginación.",
    )
    async def list_pokemons(
        limit: int = Field(default=20, description="Cantidad máxima de Pokémon a devolver"),
        offset: int = Field(default=0, description="Cantidad de Pokémon a saltar (para paginación)"),
    ) -> str:
        return await pokemon_controller.handle_list_pokemons(limit, offset)
