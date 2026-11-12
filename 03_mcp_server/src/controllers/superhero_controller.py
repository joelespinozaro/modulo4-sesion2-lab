from mcp.types import CallToolResult, TextContent

from src.dto.superhero import Superhero
from src.services import superhero_service


def _format_superhero_text(hero: Superhero) -> str:
    stats = ", ".join(f"{name}: {value}" for name, value in hero.powerstats.items())
    return (
        f"#{hero.id} {hero.name} (nombre real: {hero.full_name}) — editorial: {hero.publisher} — "
        f"alineación: {hero.alignment} — stats: {stats} — imagen: {hero.image_url}"
    )


def _superhero_structured_data(hero: Superhero) -> dict:
    stats = ", ".join(f"{name}: {value}" for name, value in hero.powerstats.items())
    return {
        "title": f"#{hero.id} {hero.name}",
        "image_url": hero.image_url,
        # superherodb.com (el host de las imágenes de SuperheroAPI) responde 403 con
        # un challenge de Cloudflare cuando se pide la imagen directo como <img> desde
        # otro origen, así que el frontend la muestra como enlace en vez de embebida.
        "image_link_only": True,
        "fields": [
            {"label": "Nombre real", "value": hero.full_name},
            {"label": "Editorial", "value": hero.publisher},
            {"label": "Alineación", "value": hero.alignment},
            {"label": "Stats", "value": stats or "-"},
        ],
    }


async def handle_get_superhero(id_: str) -> CallToolResult:
    hero = await superhero_service.get_superhero(id_)
    return CallToolResult(
        content=[TextContent(type="text", text=_format_superhero_text(hero))],
        structuredContent=_superhero_structured_data(hero),
    )


async def handle_search_superheroes(name: str) -> CallToolResult:
    heroes = await superhero_service.search_superheroes(name)
    if not heroes:
        text = f"No se encontraron personajes que coincidan con '{name}'."
        return CallToolResult(content=[TextContent(type="text", text=text)])

    text = "\n".join(_format_superhero_text(hero) for hero in heroes)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent={"items": [_superhero_structured_data(hero) for hero in heroes]},
    )
