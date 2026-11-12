from pptx.dml.color import RGBColor
from pptx.util import Pt

# Paleta neutra (sin depender de assets de marca — ver skill generar_presentaciones):
# portada/separadores en fondo oscuro, contenido en fondo claro, un único acento.
FONT_NAME = "Calibri"

DARK_BG = RGBColor(0x1B, 0x1F, 0x27)
LIGHT_BG = RGBColor(0xFA, 0xFA, 0xF9)
ACCENT = RGBColor(0x3B, 0x5B, 0xDB)
TEXT_DARK = RGBColor(0x1B, 0x1F, 0x27)
TEXT_LIGHT = RGBColor(0xF5, 0xF5, 0xF4)
TEXT_MUTED_ON_LIGHT = RGBColor(0x70, 0x76, 0x82)
TEXT_MUTED_ON_DARK = RGBColor(0x9A, 0x9F, 0xA8)
DIVIDER = RGBColor(0xE1, 0xE3, 0xE8)

TITLE_SIZE = Pt(40)
SEPARATOR_TITLE_SIZE = Pt(34)
SLIDE_TITLE_SIZE = Pt(30)
COLUMN_TITLE_SIZE = Pt(20)
BODY_SIZE = Pt(18)
SUBTITLE_SIZE = Pt(18)
FOOTER_SIZE = Pt(11)
