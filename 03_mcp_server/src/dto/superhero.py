from pydantic import BaseModel


class Superhero(BaseModel):
    id: int
    name: str
    full_name: str
    publisher: str
    alignment: str
    powerstats: dict[str, str]
    image_url: str

    @classmethod
    def from_api(cls, data: dict) -> "Superhero":
        biography = data.get("biography", {})
        image = data.get("image", {})
        return cls(
            id=int(data["id"]),
            name=data["name"],
            full_name=biography.get("full-name") or "-",
            publisher=biography.get("publisher") or "-",
            alignment=biography.get("alignment") or "-",
            powerstats=data.get("powerstats", {}),
            image_url=image.get("url", ""),
        )
