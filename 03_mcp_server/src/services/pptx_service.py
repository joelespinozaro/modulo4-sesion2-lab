from io import BytesIO
from typing import Optional

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from src.dto.pptx import SlideInput
from src.services.pptx_theme import (
    ACCENT,
    BODY_SIZE,
    COLUMN_TITLE_SIZE,
    DARK_BG,
    DIVIDER,
    FONT_NAME,
    FOOTER_SIZE,
    LIGHT_BG,
    SEPARATOR_TITLE_SIZE,
    SLIDE_TITLE_SIZE,
    SUBTITLE_SIZE,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED_ON_DARK,
    TEXT_MUTED_ON_LIGHT,
    TITLE_SIZE,
)

MARGIN = Inches(0.7)
BLANK_LAYOUT_INDEX = 6


def _add_rect(slide, left: Emu, top: Emu, width: Emu, height: Emu, color) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False


def _add_text(
    slide,
    left: Emu,
    top: Emu,
    width: Emu,
    height: Emu,
    text: str,
    *,
    size: Pt,
    color,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
    autofit: bool = False,
) -> None:
    """autofit=True: si el texto no entra en el alto reservado (título largo que
    envuelve a 2+ líneas), PowerPoint/LibreOffice reduce la fuente al abrir el
    archivo en vez de desbordar y pisar las formas de abajo (accent bar, subtítulo)."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    if autofit:
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    paragraph = tf.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = size
    run.font.bold = bold
    run.font.name = FONT_NAME
    run.font.color.rgb = color


def _add_bullets(slide, left: Emu, top: Emu, width: Emu, height: Emu, items: list[str], *, color) -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        paragraph = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        paragraph.space_after = Pt(10)
        run = paragraph.add_run()
        run.text = f"›  {item}"
        run.font.size = BODY_SIZE
        run.font.name = FONT_NAME
        run.font.color.rgb = color


def _add_footer(slide, prs: Presentation, *, dark: bool, page_number: Optional[int] = None) -> None:
    _add_rect(slide, 0, prs.slide_height - Pt(3), prs.slide_width, Pt(3), ACCENT)
    if page_number is not None:
        color = TEXT_MUTED_ON_DARK if dark else TEXT_MUTED_ON_LIGHT
        _add_text(
            slide,
            prs.slide_width - Inches(1.2),
            prs.slide_height - Inches(0.5),
            Inches(0.9),
            Inches(0.35),
            str(page_number),
            size=FOOTER_SIZE,
            color=color,
            align=PP_ALIGN.RIGHT,
        )


def _content_width(prs: Presentation) -> Emu:
    return prs.slide_width - 2 * MARGIN


def _build_title_slide(prs: Presentation, title: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[BLANK_LAYOUT_INDEX])
    _add_rect(slide, 0, 0, prs.slide_width, prs.slide_height, DARK_BG)
    _add_text(
        slide, MARGIN, Inches(2.15), _content_width(prs), Inches(2.0),
        title, size=TITLE_SIZE, color=TEXT_LIGHT, bold=True, autofit=True,
    )
    _add_rect(slide, MARGIN, Inches(4.35), Inches(1.4), Pt(4), ACCENT)
    _add_text(
        slide, MARGIN, Inches(4.55), _content_width(prs), Inches(0.6),
        "Generado por el asistente", size=SUBTITLE_SIZE, color=TEXT_MUTED_ON_DARK,
    )


def _build_separador_slide(prs: Presentation, slide_input: SlideInput) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[BLANK_LAYOUT_INDEX])
    _add_rect(slide, 0, 0, prs.slide_width, prs.slide_height, DARK_BG)
    _add_text(
        slide, MARGIN, Inches(2.5), _content_width(prs), Inches(1.7),
        slide_input.title, size=SEPARATOR_TITLE_SIZE, color=TEXT_LIGHT, bold=True, autofit=True,
    )
    _add_rect(slide, MARGIN, Inches(4.35), Inches(1.0), Pt(4), ACCENT)
    _add_footer(slide, prs, dark=True)


def _build_contenido_slide(prs: Presentation, slide_input: SlideInput, page_number: int) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[BLANK_LAYOUT_INDEX])
    _add_rect(slide, 0, 0, prs.slide_width, prs.slide_height, LIGHT_BG)
    _add_text(
        slide, MARGIN, Inches(0.45), _content_width(prs), Inches(1.15),
        slide_input.title, size=SLIDE_TITLE_SIZE, color=TEXT_DARK, bold=True, autofit=True,
    )
    _add_rect(slide, MARGIN, Inches(1.75), Inches(1.0), Pt(4), ACCENT)
    _add_bullets(
        slide, MARGIN, Inches(2.05), _content_width(prs), Inches(4.65),
        slide_input.bullets, color=TEXT_DARK,
    )
    _add_footer(slide, prs, dark=False, page_number=page_number)


def _build_comparacion_slide(prs: Presentation, slide_input: SlideInput, page_number: int) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[BLANK_LAYOUT_INDEX])
    _add_rect(slide, 0, 0, prs.slide_width, prs.slide_height, LIGHT_BG)
    _add_text(
        slide, MARGIN, Inches(0.45), _content_width(prs), Inches(1.15),
        slide_input.title, size=SLIDE_TITLE_SIZE, color=TEXT_DARK, bold=True, autofit=True,
    )
    _add_rect(slide, MARGIN, Inches(1.75), Inches(1.0), Pt(4), ACCENT)

    gap = Inches(0.4)
    col_width = (_content_width(prs) - gap) // 2
    left_x = MARGIN
    right_x = left_x + col_width + gap

    _add_rect(slide, left_x + col_width + gap // 2, Inches(2.2), Pt(1.5), Inches(4.2), DIVIDER)

    if slide_input.left_title:
        _add_text(
            slide, left_x, Inches(2.1), col_width, Inches(0.5),
            slide_input.left_title, size=COLUMN_TITLE_SIZE, color=ACCENT, bold=True,
        )
    _add_bullets(slide, left_x, Inches(2.65), col_width, Inches(3.8), slide_input.left_bullets, color=TEXT_DARK)

    if slide_input.right_title:
        _add_text(
            slide, right_x, Inches(2.1), col_width, Inches(0.5),
            slide_input.right_title, size=COLUMN_TITLE_SIZE, color=ACCENT, bold=True,
        )
    _add_bullets(slide, right_x, Inches(2.65), col_width, Inches(3.8), slide_input.right_bullets, color=TEXT_DARK)

    _add_footer(slide, prs, dark=False, page_number=page_number)


def build_pptx(title: str, slides: list[SlideInput]) -> bytes:
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)

    _build_title_slide(presentation, title)

    for page_number, slide_input in enumerate(slides, start=2):
        if slide_input.layout == "separador":
            _build_separador_slide(presentation, slide_input)
        elif slide_input.layout == "comparacion":
            _build_comparacion_slide(presentation, slide_input, page_number)
        else:
            _build_contenido_slide(presentation, slide_input, page_number)

    buffer = BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()
