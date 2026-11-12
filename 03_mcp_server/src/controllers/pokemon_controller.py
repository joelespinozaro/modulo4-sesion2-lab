from mcp.types import CallToolResult, TextContent

from src.dto.pokemon import Pokemon
from src.services import pokemon_service


def _format_pokemon_text(pokemon: Pokemon) -> str:
    types = ", ".join(pokemon.types)
    abilities = ", ".join(pokemon.abilities)
    stats = ", ".join(f"{name}: {value}" for name, value in pokemon.stats.items())
    return (
        f"#{pokemon.id} {pokemon.name} — tipo(s): {types} — habilidades: {abilities} — "
        f"altura: {pokemon.height} — peso: {pokemon.weight} — "
        f"experiencia base: {pokemon.base_experience} — stats: {stats}"
    )


def _pokemon_structured_data(pokemon: Pokemon) -> dict:
    stats = ", ".join(f"{name}: {value}" for name, value in pokemon.stats.items())
    return {
        "title": f"#{pokemon.id} {pokemon.name}",
        "image_url": pokemon.image_url,
        "fields": [
            {"label": "Tipo(s)", "value": ", ".join(pokemon.types) or "-"},
            {"label": "Habilidades", "value": ", ".join(pokemon.abilities) or "-"},
            {"label": "Altura", "value": str(pokemon.height)},
            {"label": "Peso", "value": str(pokemon.weight)},
            {"label": "Experiencia base", "value": str(pokemon.base_experience)},
            {"label": "Stats", "value": stats or "-"},
        ],
    }


async def handle_get_pokemon(name_or_id: str) -> CallToolResult:
    pokemon = await pokemon_service.get_pokemon(name_or_id)
    return CallToolResult(
        content=[TextContent(type="text", text=_format_pokemon_text(pokemon))],
        structuredContent=_pokemon_structured_data(pokemon),
    )


async def handle_list_pokemons(limit: int, offset: int) -> str:
    names = await pokemon_service.list_pokemons(limit, offset)
    return "\n".join(names)
