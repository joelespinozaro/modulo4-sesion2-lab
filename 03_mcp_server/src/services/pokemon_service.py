from src.dto.pokemon import Pokemon
from src.repositories import pokemon_repository


async def get_pokemon(name_or_id: str) -> Pokemon:
    raw = await pokemon_repository.fetch_pokemon(name_or_id)
    if raw is None:
        raise ValueError(f"Pokemon '{name_or_id}' no encontrado")
    return Pokemon.from_api(raw)


async def list_pokemons(limit: int, offset: int) -> list[str]:
    results = await pokemon_repository.fetch_pokemon_list(limit, offset)
    return [item["name"] for item in results]
