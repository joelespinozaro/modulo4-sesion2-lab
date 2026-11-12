import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

class ChatRequest(BaseModel):
    question: str
    user: str
    session_id: Optional[str] = None

class RetrievedContext(BaseModel):
    page_content: str
    metadata: Dict[str, Any]
    score: float

class SourceField(BaseModel):
    label: str
    value: str

class SourceItem(BaseModel):
    """Una ficha estructurada dentro de una tool que devuelve varios resultados en
    una sola llamada (ej. search_superheroes)."""
    title: Optional[str] = None
    image_url: Optional[str] = None
    # Algunos hosts de imágenes (ej. superherodb.com) bloquean el embed cross-origin;
    # cuando la tool lo marca así, el frontend muestra un enlace en vez de un <img>.
    image_link_only: bool = False
    fields: List[SourceField] = []

class ToolSource(BaseModel):
    """Una cita de una tool que el agente usó para responder (Qdrant, PokeAPI,
    SuperheroAPI, Neon, etc.).

    - `contexts` solo se llena para retrieve_documents (RAG).
    - `title`/`image_url`/`fields` se llenan para tools que devuelven una única ficha
      estructurada (ej. get_pokemon, get_superhero).
    - `items` se llena para tools que devuelven varias fichas en una sola llamada
      (ej. search_superheroes) — cada item trae su propio title/image_url/fields.
    - `content` es el fallback de texto plano para el resto de las tools."""
    tool: str
    label: str
    input: Optional[Dict[str, Any]] = None
    content: Optional[str] = None
    title: Optional[str] = None
    image_url: Optional[str] = None
    image_link_only: bool = False
    fields: List[SourceField] = []
    items: List[SourceItem] = []
    contexts: List[RetrievedContext] = []

class GeneratedFile(BaseModel):
    """Un archivo que una tool generó como entregable (ej. generate_pptx), no como
    cita — el frontend lo ofrece para descargar. No se persiste en el historial:
    solo viaja en la respuesta del turno en que se generó."""
    tool: str
    filename: str
    mime_type: str
    data_base64: str

class ChatResponse(BaseModel):
    user: str
    answer: str
    session_id: UUID
    trace_id: UUID
    sources: List[ToolSource] = []
    files: List[GeneratedFile] = []

class HistoryItem(BaseModel):
    question: str
    answer: str
    trace_id: UUID
    session_id: UUID
    user: Optional[str] = None
    sources: Optional[List[ToolSource]] = None
    created_at: datetime

    @field_validator("sources", mode="before")
    @classmethod
    def parse_sources(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value) if value else None
        return value

    class Config:
        from_attributes = True

class UserSessionsResponse(BaseModel):
    user: str
    sessions: List[str]