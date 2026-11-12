---
name: generar_presentaciones
description: Cómo estructurar y generar una presentación PowerPoint (.pptx) a partir de una conversación o un tema. Usar cuando el usuario pida explícitamente una presentación, PPT, PowerPoint o slides.
---

# Generar presentaciones PowerPoint

## Cuándo usar esta skill

Solo cuando el usuario pida explícitamente una presentación, PPT, PowerPoint o
"slides". No la uses para resumir texto dentro del chat — para eso alcanza con
una respuesta normal.

## De dónde sale el contenido

- Si el usuario pide resumir o presentar algo que ya se conversó, arma las
  slides en base a esa conversación.
- Si el tema es institucional (programas, cursos, temarios, precios, duración,
  requisitos, certificaciones), consulta primero `retrieve_documents` y basa
  las slides en esa información real — no inventes datos de la academia.
- Si el tema es genérico y no relacionado con la academia, improvisa el
  contenido con tu propio conocimiento.

## Cómo estructurar las slides

- Entre 3 y 8 slides de contenido según la complejidad del tema: ni una sola
  slide con todo, ni veinte triviales.
- Cada slide: un título corto y claro, más 3 a 5 viñetas concisas (frases
  cortas, no párrafos).
- No repitas el título general como título de la primera slide de contenido:
  la portada se genera sola con ese título (con diseño oscuro + acento).

### Layouts disponibles (elegí el que mejor calce, no uses siempre el mismo)

Cada slide tiene un campo `layout`, uno de:

- **`contenido`** (default): título + lista de viñetas. Úsalo para la mayoría
  de las slides.
- **`separador`**: solo un título grande centrado sobre fondo oscuro, sin
  viñetas. Úsalo para dividir la presentación en secciones cuando el tema
  tiene 2 o más bloques temáticos claros (ej. antes de pasar de "Programas"
  a "Precios y becas").
- **`comparacion`**: dos columnas lado a lado, cada una con su propio
  `left_title`/`left_bullets` y `right_title`/`right_bullets`. Úsalo cuando
  el contenido sea naturalmente comparativo (dos programas, antes/después,
  pros/contras) — no fuerces una comparación si el tema no la tiene.

No uses `separador` para todas las slides ni abuses de `comparacion`: la
mayoría de una presentación normal es `contenido`.

## Cómo generarla

Una vez decidido el título general y la lista de slides (cada una con su
`layout`, `title` y — según el layout — `bullets` o
`left_title`/`left_bullets`/`right_title`/`right_bullets`), llama a la tool
`generate_pptx(title, slides)`. La tool arma el archivo .pptx real (con un
diseño ya prolijo: portada oscura, acento de color, footer con numeración) y
lo entrega directamente en la interfaz del chat como adjunto descargable —
vos no generás el archivo ni elegís colores/fuentes, solo decidís el
contenido y el layout de cada slide.

## Qué NO hacer

- No inventes un enlace de descarga, ruta `sandbox:` ni markdown tipo
  `[Descargar](...)` en tu respuesta de texto: el archivo llega aparte, como
  adjunto en la interfaz, no como link en el mensaje.
- Después de llamar a `generate_pptx`, en tu respuesta de texto solo confirma
  el título y la cantidad de slides generadas — no repitas el contenido
  completo de cada slide.
