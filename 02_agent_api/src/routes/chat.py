from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.controllers.chat_controller import get_history, get_sessions, handle_chat
from src.repositories import get_db
from src.dto.api_entities import ChatRequest, ChatResponse, HistoryItem, UserSessionsResponse

chat_router = APIRouter()

@chat_router.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    result = await handle_chat(
        question=request.question,
        user=request.user,
        session_id=request.session_id,
        db=db,
    )
    return ChatResponse(**result)


@chat_router.get("/api/history/{session_id}", response_model=List[HistoryItem], tags=["history"])
def history(session_id: str, db: Session = Depends(get_db)) -> List[HistoryItem]:
    return get_history(session_id=session_id, db=db)


@chat_router.get("/api/sessions/{user}", response_model=UserSessionsResponse, tags=["history"])
def sessions_by_user(user: str, db: Session = Depends(get_db)) -> UserSessionsResponse:
    session_ids = get_sessions(user=user, db=db)
    return UserSessionsResponse(user=user, sessions=[str(s) for s in session_ids])