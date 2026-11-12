import json
import time
from typing import Any, Dict, List, Optional
import uuid

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from src.services.tools import get_weather, retrieve_documents
from src.repositories.history_repository import HistoryRepository
from src.repositories.models.history import History
from src.utils.environment import (
    HISTORY_LIMIT,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "Eres un asistente útil y amigable. Responde siempre en español. "
    "Sé conciso en tus respuestas. "
    "SIEMPRE que la pregunta trate sobre la academia, sus programas, cursos, "
    "temarios, precios, duración, requisitos, certificaciones o cualquier "
    "información institucional, DEBES usar la herramienta retrieve_documents "
    "para consultar la base de conocimiento antes de responder; no respondas "
    "esos temas de memoria. Si la herramienta no encuentra información "
    "relevante, dilo explícitamente en tu respuesta."
)

RETRIEVER_TOOL_NAME = "retrieve_documents"

class AgentService:
    def __init__(self, db: Session) -> None:
        self._repo = HistoryRepository(db)
        self._llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY)
        self._agent = create_agent(
            model=self._llm,
            tools=[get_weather, retrieve_documents],
            system_prompt=SYSTEM_PROMPT,
        )

    async def chat(self, question: str, user: str, session_id: Optional[str]) -> dict:
        logger.info(f"Pregunta entrante de {user}: {question}")

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
        agent_response = await self._agent.ainvoke(
            {"messages": [*history_messages, HumanMessage(content=question)]}
        )
        result = self._parse_agent_response(agent_response)
        retrieved_contexts = self._extract_retrieved_contexts(agent_response)
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
                retrieved_contexts=(
                    json.dumps(retrieved_contexts, ensure_ascii=False)
                    if retrieved_contexts
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
                "retrieved_contexts_count": len(retrieved_contexts or []),
            },
        )

        logger.info(f"Respuesta a la pregunta: {result['answer']}")

        return {
            "user": user,
            "answer": result["answer"],
            "session_id": session_id,
            "trace_id": trace_id,
        }

    @staticmethod
    def _extract_retrieved_contexts(agent_response: dict) -> List[Dict[str, Any]]:
        contexts: List[Dict[str, Any]] = []
        for message in agent_response.get("messages", []):
            if isinstance(message, ToolMessage) and message.name == RETRIEVER_TOOL_NAME:
                artifact = getattr(message, "artifact", None)
                if artifact:
                    contexts.extend(artifact)
        return contexts

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