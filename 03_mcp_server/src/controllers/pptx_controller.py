import base64
import re

from mcp.types import CallToolResult, TextContent

from src.dto.pptx import SlideInput
from src.services import pptx_service

PPTX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "presentacion"


async def handle_generate_pptx(title: str, slides: list[SlideInput]) -> CallToolResult:
    data = pptx_service.build_pptx(title, slides)
    filename = f"{_slugify(title)}.pptx"

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=f"Presentación '{title}' generada con {len(slides)} slide(s): {filename}",
            )
        ],
        structuredContent={
            "filename": filename,
            "mime_type": PPTX_MIME_TYPE,
            "data_base64": base64.b64encode(data).decode("ascii"),
            "slide_count": len(slides),
        },
    )
