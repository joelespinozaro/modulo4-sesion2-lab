from pydantic import BaseModel


class Pokemon(BaseModel):
    id: int
    name: str
    height: int
    weight: int
    base_experience: int | None
    types: list[str]
    abilities: list[str]
    stats: dict[str, int]
    image_url: str | None

    @classmethod
    def from_api(cls, data: dict) -> "Pokemon":
        sprites = data.get("sprites", {})
        official_artwork = (
            sprites.get("other", {}).get("official-artwork", {}).get("front_default")
        )
        return cls(
            id=data["id"],
            name=data["name"],
            height=data["height"],
            weight=data["weight"],
            base_experience=data.get("base_experience"),
            types=[t["type"]["name"] for t in data.get("types", [])],
            abilities=[a["ability"]["name"] for a in data.get("abilities", [])],
            stats={s["stat"]["name"]: s["base_stat"] for s in data.get("stats", [])},
            image_url=official_artwork or sprites.get("front_default"),
        )
