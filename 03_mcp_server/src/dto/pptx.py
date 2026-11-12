from typing import Literal, Optional

from pydantic import BaseModel, Field


class SlideInput(BaseModel):
    layout: Literal["contenido", "separador", "comparacion"] = "contenido"
    title: str
    # "contenido": lista de viñetas normal.
    bullets: list[str] = Field(default_factory=list)
    # "comparacion": dos columnas lado a lado, cada una con su propio subtítulo y viñetas.
    left_title: Optional[str] = None
    left_bullets: list[str] = Field(default_factory=list)
    right_title: Optional[str] = None
    right_bullets: list[str] = Field(default_factory=list)
