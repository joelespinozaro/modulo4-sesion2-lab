import json
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional
import uuid

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import SystemMessage
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.services.guardrails import build_input_guardrails
from src.services.middleware import (
    LoggingMiddleware,
    RetryMiddleware,
    SafetyGuardMiddleware,
    TokenBudgetMiddleware,
)
from src.services.guardrails.common import hash_message
from src.services.tools import DEMO_MCP_SERVER_NAME, LOCAL_TOOLS
from src.repositories.history_repository import HistoryRepository
from src.repositories.models.history import History
from src.utils.environment import (
    TOKEN_BUDGET,
    HISTORY_LIMIT,
    NEON_PROJECT_ID,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Pipeline InputGuardrail (HU SEC-001): se construye una sola vez y se reutiliza
# en ambas inicializaciones del agente (inicial y tras cargar tools MCP).
_INPUT_GUARDRAILS = build_input_guardrails()


def _build_hooks() -> list:
    """Middlewares de la parte 3. Corren dentro del loop del agente, después de
    que los guardrails (before_agent) dejaron pasar el mensaje."""
    return [
        LoggingMiddleware(),                         # 1° logging de cada llamada al LLM
        TokenBudgetMiddleware(budget=TOKEN_BUDGET),  # 2° presupuesto de tokens
        SafetyGuardMiddleware(),                     # 3° guardia de contenido en la salida
        RetryMiddleware(max_retries=3),              # 4° reintentos ante errores transitorios
    ]

_neon_context = (
    f"Tienes acceso a una base de datos Neon Postgres. "
    f"El project_id que debes usar SIEMPRE en las herramientas MCP es: {NEON_PROJECT_ID}. "
    f"Nunca le preguntes al usuario el project_id, ya lo tienes. "
    f"La base de datos tiene las siguientes tablas: "
    f"- ventas (id, fecha_venta, id_cliente, total_venta, estado (esto puede ser completada o pendiente), id_vendedor)"
    f"- detalle_ventas (id, id_venta, id_producto, cantidad, precio_unitario, subtotal)"
    f"- clientes (id, dni, nombres, sexo, fecha_nacimiento)"
    f"- vendedores (id, dni, nombres, fecha_ingreso, fecha_nacimiento)"
    f"- productos (id, descripcion, precio, stock)"
    f"Cuando el usuario pregunte sobre ventas, clientes, vendedores o productos, usa run_sql con ese project_id para consultar. "
    f"Para preguntas sobre programas, cursos, temarios, precios, duración, requisitos, certificaciones o cualquier "
    f"información institucional, usa retrieve_documents en lugar de run_sql. "
) if NEON_PROJECT_ID else ""

SYSTEM_PROMPT = (
    "Eres un asistente útil y amigable. Responde siempre en español. "
    "Sé conciso en tus respuestas. "
    "SIEMPRE que la pregunta trate sobre la academia, sus programas, cursos, "
    "temarios, precios, duración, requisitos, certificaciones o cualquier "
    "información institucional, DEBES usar la herramienta retrieve_documents "
    "para consultar la base de conocimiento antes de responder; no respondas "
    "esos temas de memoria. Si la herramienta no encuentra información "
    "relevante, dilo explícitamente en tu respuesta. "
    "SIEMPRE que la solicitud del usuario coincida con la descripción de alguna "
    "skill de la sección 'Skills disponibles' de este prompt (si existe) — por "
    "ejemplo, pedir una presentación/PPT, o una ruta de aprendizaje/prerrequisitos "
    "de un área académica — usa la herramienta load_skill para cargar su guía "
    "detallada ANTES de actuar; esa guía indica qué tools usar y cómo. "
    "Cuando una herramienta genere un archivo (ej. generate_pptx), en tu respuesta "
    "de texto NUNCA inventes un enlace, ruta sandbox: ni markdown de descarga "
    "([texto](url)): el archivo se entrega aparte, como adjunto en la interfaz, no "
    "como link en el mensaje; solo confirma en texto plano qué generaste. "
    + _neon_context
)

RETRIEVER_TOOL_NAME = "retrieve_documents"

# Nombre de tool -> etiqueta legible para mostrar como fuente en el frontend.
# Una tool sin entrada acá se muestra igual, humanizando su nombre (ver _tool_source_label).
_SOURCE_LABELS: Dict[str, str] = {
    RETRIEVER_TOOL_NAME: "Base de conocimiento (Qdrant)",
    "get_pokemon": "PokeAPI",
    "list_pokemons": "PokeAPI",
    "get_superhero": "SuperheroAPI",
    "search_superheroes": "SuperheroAPI",
    "run_sql": "Base de datos (Neon)",
    "get_weather": "Pronóstico (simulado)",
    "load_skill": "Guía curricular",
}

MAX_SOURCE_CONTENT_CHARS = 800


def _tool_source_label(tool_name: str) -> str:
    return _SOURCE_LABELS.get(tool_name, tool_name.replace("_", " ").capitalize())


def _stringify_tool_content(content: Any) -> str:
    """Normaliza el content de un ToolMessage a texto plano.

    Las tools locales (@tool) devuelven content como str; las tools MCP
    (langchain-mcp-adapters) devuelven una lista de content blocks
    ({"type": "text", "text": ...}) incluso para salidas simples de texto."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(parts)
    return str(content)

class LoadSkillInput(BaseModel):
    skill_name: str = Field(description="Nombre de la skill a cargar (ver lista de skills disponibles)")


def _build_load_skill_tool(client: MultiServerMCPClient, skills: List[Dict[str, str]]) -> BaseTool:
    """Tool genérica de progressive disclosure: carga el contenido completo de una
    skill leyéndolo como recurso MCP (skill://.../SKILL.md, ver src/routes/skills.py
    en 03_mcp_server) recién cuando el LLM decide que la necesita — antes de eso,
    solo su name/description ocupan lugar en el system prompt (ver SkillMiddleware)."""
    skills_by_name = {s["name"]: s["uri"] for s in skills}

    async def _load_skill(skill_name: str) -> str:
        uri = skills_by_name.get(skill_name)
        if uri is None:
            available = ", ".join(skills_by_name) or "ninguna"
            return f"Skill '{skill_name}' no encontrada. Skills disponibles: {available}"

        blobs = await client.get_resources(server_name=DEMO_MCP_SERVER_NAME, uris=[uri])
        if not blobs:
            return f"No se pudo cargar el contenido de la skill '{skill_name}'."
        return f"Skill cargada: {skill_name}\n\n{blobs[0].as_string()}"

    return StructuredTool.from_function(
        name="load_skill",
        description=(
            "Carga el contenido completo de una skill de orientación curricular "
            "(leída como recurso MCP desde 03_mcp_server) en el contexto del agente. "
            "Úsala cuando el usuario pida una ruta de aprendizaje, prerrequisitos o "
            "progresión de nivel dentro de un área académica específica."
        ),
        coroutine=_load_skill,
        args_schema=LoadSkillInput,
    )


class SkillMiddleware(AgentMiddleware):
    """Inyecta en el system prompt las descripciones de las skills descubiertas vía
    MCP resources (progressive disclosure: solo name/description acá, ~gratis en
    tokens) y expone la tool load_skill para cargar el contenido completo on-demand.

    A diferencia de un enfoque anterior con una lista de skills hardcodeada en
    Python, el contenido vive en 03_mcp_server como archivos SKILL.md reales
    (formato estándar de Agent Skills), reusables fuera de este agente puntual."""

    def __init__(self, client: MultiServerMCPClient, skills: List[Dict[str, str]]) -> None:
        self.tools = [_build_load_skill_tool(client, skills)] if skills else []
        skills_list = [f"- **{skill['name']}**: {skill['description']}" for skill in skills]
        self._skills_addendum = (
            f"\n\n## Skills disponibles\n\n{chr(10).join(skills_list)}\n\n"
            "Usa la herramienta load_skill cuando necesites la guía detallada "
            "de una de estas áreas académicas."
        ) if skills else ""

    def _inject_skills(self, request: ModelRequest) -> ModelRequest:
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": self._skills_addendum}
        ]
        return request.override(system_message=SystemMessage(content=new_content))

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        if not self._skills_addendum:
            return handler(request)
        return handler(self._inject_skills(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        if not self._skills_addendum:
            return await handler(request)
        return await handler(self._inject_skills(request))


_llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY)
_agent = create_agent(
    model=_llm,
    tools=LOCAL_TOOLS,
    system_prompt=SYSTEM_PROMPT,
    middleware=_INPUT_GUARDRAILS + _build_hooks(),
)


def init_agent(
    tools: list,
    skill_client: MultiServerMCPClient | None = None,
    skills: List[Dict[str, str]] | None = None,
) -> None:
    """Reinicializa el agente global con el conjunto de tools provisto (locales + MCP)
    y, si hay skills descubiertas en el demo MCP server, agrega SkillMiddleware
    (inyecta sus descripciones en el prompt + la tool load_skill)."""
    global _agent
    skill_middleware = [SkillMiddleware(skill_client, skills)] if skill_client and skills else []
    # guardrails → hooks de la parte 3 → skills (SkillMiddleware envuelve la llamada más interna)
    middleware = _INPUT_GUARDRAILS + _build_hooks() + skill_middleware
    _agent = create_agent(
        model=_llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
    )
    logger.info(
        "Agente reinicializado con %d tool(s) (%d skill(s)): %s",
        len(tools),
        len(skills or []),
        [t.name for t in tools],
    )


class AgentService:
    def __init__(self, db: Session) -> None:
        self._repo = HistoryRepository(db)

    async def chat(self, question: str, user: str, session_id: Optional[str]) -> dict:
        # No se loguea la pregunta en texto plano: el InputGuardrail (capas 1-8)
        # corre dentro de _agent.ainvoke y puede bloquear mensajes con secretos
        # o PII antes de procesarlos; solo se hashea aquí (criterio de privacidad
        # de HU_InputGuardrail.md).
        logger.info(
            "Pregunta entrante",
            extra={"user": user, "question_hash": hash_message(question)},
        )

        is_new_session = not session_id
        if is_new_session:
            logger.info("Creando nueva sesión")
            session_id = str(uuid.uuid4())

        trace_id = str(uuid.uuid4())

        logger.info(
            "Iniciando chat",
            extra={"session_id": session_id, "trace_id": trace_id, "user": user},
        )

        t0 = time.perf_counter()
        history_records = [] if is_new_session else self._repo.get_by_session_id(session_id, limit=HISTORY_LIMIT)
        t_history = time.perf_counter() - t0

        history_messages: List[BaseMessage] = []
        for record in history_records:
            history_messages.append(HumanMessage(content=record.question))
            history_messages.append(AIMessage(content=record.answer))

        t0 = time.perf_counter()
        agent_response = await _agent.ainvoke(
            {"messages": [*history_messages, HumanMessage(content=question)]}
        )
        result = self._parse_agent_response(agent_response)
        sources, files = self._extract_sources_and_files(agent_response)
        t_agent = time.perf_counter() - t0

        t0 = time.perf_counter()
        self._repo.save(
            History(
                trace_id=trace_id,
                session_id=session_id,
                question=question,
                answer=result["answer"],
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                user=user,
                sources=(
                    json.dumps(sources, ensure_ascii=False)
                    if sources
                    else None
                ),
            )
        )
        t_save = time.perf_counter() - t0

        logger.info(
            "Chat finalizado",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "t_history_ms": round(t_history * 1000, 2),
                "t_agent_ms": round(t_agent * 1000, 2),
                "t_save_ms": round(t_save * 1000, 2),
                "sources_count": len(sources or []),
            },
        )

        logger.info(f"Respuesta a la pregunta: {result['answer']}")

        return {
            "user": user,
            "answer": result["answer"],
            "session_id": session_id,
            "trace_id": trace_id,
            "sources": sources,
            "files": files,
        }

    @staticmethod
    def _extract_sources_and_files(
        agent_response: dict,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Recorre los ToolMessage de la corrida y separa dos cosas:

        - `sources`: una cita por cada tool externa que el agente usó para responder
          (RAG en Qdrant, PokeAPI, SuperheroAPI, Neon, etc.), para que el frontend
          las muestre como fuentes. Para retrieve_documents se preservan los
          contexts detallados (page_content + metadata + score); tools como
          get_pokemon/get_superhero aportan además una ficha estructurada
          (structured_content = {"image_url", "fields", ...}) para que el frontend
          la muestre como tarjeta en vez de texto plano.
        - `files`: archivos generados por una tool (ej. generate_pptx) que el
          frontend debe ofrecer para descargar, detectados porque su
          structured_content trae "data_base64" (ver pptx_controller en
          03_mcp_server). No se citan como fuente: son el entregable en sí."""
        messages = agent_response.get("messages", [])

        tool_calls_by_id: Dict[str, Dict[str, Any]] = {}
        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls or []:
                    tool_calls_by_id[call["id"]] = call

        sources: List[Dict[str, Any]] = []
        files: List[Dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, ToolMessage):
                continue

            tool_name = message.name or "tool"
            tool_input = tool_calls_by_id.get(message.tool_call_id, {}).get("args")

            artifact = getattr(message, "artifact", None)
            structured = artifact.get("structured_content") or {} if isinstance(artifact, dict) else {}

            data_base64 = structured.get("data_base64")
            if data_base64:
                files.append(
                    {
                        "tool": tool_name,
                        "filename": structured.get("filename") or f"{tool_name}.bin",
                        "mime_type": structured.get("mime_type") or "application/octet-stream",
                        "data_base64": data_base64,
                    }
                )
                continue

            if tool_name == RETRIEVER_TOOL_NAME:
                contexts = structured.get("contexts") or []
                if not contexts:
                    continue
                sources.append(
                    {
                        "tool": tool_name,
                        "label": _tool_source_label(tool_name),
                        "input": tool_input,
                        "content": None,
                        "contexts": contexts,
                    }
                )
            else:
                title = structured.get("title")
                image_url = structured.get("image_url")
                image_link_only = structured.get("image_link_only", False)
                fields = structured.get("fields") or []
                items = structured.get("items") or []

                content = _stringify_tool_content(message.content).strip()
                if len(content) > MAX_SOURCE_CONTENT_CHARS:
                    content = content[:MAX_SOURCE_CONTENT_CHARS].rstrip() + "…"

                if not content and not image_url and not fields and not items:
                    continue

                sources.append(
                    {
                        "tool": tool_name,
                        "label": _tool_source_label(tool_name),
                        "input": tool_input,
                        "content": content or None,
                        "title": title,
                        "image_url": image_url,
                        "image_link_only": image_link_only,
                        "fields": fields,
                        "items": items,
                        "contexts": [],
                    }
                )
        return sources, files

    @staticmethod
    def _parse_agent_response(agent_response: dict) -> dict:
        messages = agent_response.get("messages", [])
        answer = messages[-1].content if messages else ""

        input_tokens = 0
        output_tokens = 0
        for message in messages:
            usage = getattr(message, "usage_metadata", None)
            if usage:
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)

        return {
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }