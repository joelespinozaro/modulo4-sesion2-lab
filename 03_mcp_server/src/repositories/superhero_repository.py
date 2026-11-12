import httpx

from src.utils.environment import (
    HTTP_TIMEOUT_SECONDS,
    SUPERHERO_API_BASE_URL,
    SUPERHERO_API_TOKEN,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=f"{SUPERHERO_API_BASE_URL}/{SUPERHERO_API_TOKEN}",
        timeout=HTTP_TIMEOUT_SECONDS,
    )


async def fetch_superhero(id_: str) -> dict | None:
    async with _client() as client:
        try:
            response = await client.get(f"/{id_}")
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Error consultando SuperheroAPI /%s: %s", id_, exc)
            raise RuntimeError(f"No se pudo obtener el personaje {id_}") from exc

    if data.get("response") == "error":
        return None
    return data


async def search_superheroes(name: str) -> list[dict]:
    async with _client() as client:
        try:
            response = await client.get(f"/search/{name}")
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Error consultando SuperheroAPI /search/%s: %s", name, exc)
            raise RuntimeError(f"No se pudo buscar el personaje {name}") from exc

    if data.get("response") == "error":
        return []
    return data.get("results", [])
