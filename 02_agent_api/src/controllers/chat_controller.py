from typing import List, Optional
from sqlalchemy.orm import Session
from src.repositories.models.history import History
from src.services.agent_service import AgentService
from src.services.history_service import HistoryService

async def handle_chat(
    question: str,
    user: str,
    session_id: Optional[str],
    db: Session,
) -> dict:
    service = AgentService(db)
    return await service.chat(question=question, user=user, session_id=session_id)

def get_history(session_id: str, db: Session) -> List[History]:
    service = HistoryService(db)
    return service.get_by_session(session_id)

def get_sessions(user: str, db: Session) -> List[str]:
    service = HistoryService(db)
    return service.get_sessions_by_user(user)