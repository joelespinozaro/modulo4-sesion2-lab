import httpx

from src.utils.environment import HTTP_TIMEOUT_SECONDS, POKEAPI_BASE_URL
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def fetch_pokemon(name_or_id: str) -> dict | None:
    async with httpx.AsyncClient(
        base_url=POKEAPI_BASE_URL, timeout=HTTP_TIMEOUT_SECONDS
    ) as client:
        try:
            response = await client.get(f"/pokemon/{name_or_id.lower()}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.warning("Error consultando PokeAPI /pokemon/%s: %s", name_or_id, exc)
            raise RuntimeError(f"No se pudo obtener el pokemon {name_or_id}") from exc


async def fetch_pokemon_list(limit: int, offset: int) -> list[dict]:
    async with httpx.AsyncClient(
        base_url=POKEAPI_BASE_URL, timeout=HTTP_TIMEOUT_SECONDS
    ) as client:
        try:
            response = await client.get("/pokemon", params={"limit": limit, "offset": offset})
            response.raise_for_status()
            return response.json()["results"]
        except httpx.HTTPError as exc:
            logger.warning("Error consultando PokeAPI /pokemon: %s", exc)
            raise RuntimeError("No se pudo obtener la lista de pokemons") from exc
