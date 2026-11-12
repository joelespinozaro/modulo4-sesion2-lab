from src.dto.superhero import Superhero
from src.repositories import superhero_repository


async def get_superhero(id_: str) -> Superhero:
    raw = await superhero_repository.fetch_superhero(id_)
    if raw is None:
        raise ValueError(f"Personaje con id '{id_}' no encontrado")
    return Superhero.from_api(raw)


async def search_superheroes(name: str) -> list[Superhero]:
    results = await superhero_repository.search_superheroes(name)
    return [Superhero.from_api(item) for item in results]
