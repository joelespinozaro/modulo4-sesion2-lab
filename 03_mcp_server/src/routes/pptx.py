from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult
from pydantic import Field

from src.controllers import pptx_controller
from src.dto.pptx import SlideInput


def register_pptx_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="generate_pptx",
        description=(
            "Genera un archivo .pptx (PowerPoint) descargable a partir de un título y "
            "una lista de slides ya decididas (cada una con su propio título y "
            "viñetas/bullets), y lo entrega como adjunto en la interfaz del chat. "
            "Antes de llamarla, cargá la skill 'generar_presentaciones' (vía "
            "load_skill) para saber de dónde sacar el contenido y cómo estructurar "
            "las slides."
        ),
    )
    async def generate_pptx(
        title: str = Field(description="Título de la presentación"),
        slides: list[SlideInput] = Field(
            description=(
                "Lista de slides. Cada una: 'layout' ('contenido' | 'separador' | "
                "'comparacion', default 'contenido'), 'title'. Para 'contenido': "
                "'bullets' (lista de strings). Para 'comparacion': 'left_title', "
                "'left_bullets', 'right_title', 'right_bullets'. 'separador' solo usa "
                "'title'. Ver skill 'generar_presentaciones' para cuándo usar cada uno."
            )
        ),
    ) -> CallToolResult:
        return await pptx_controller.handle_generate_pptx(title, slides)
