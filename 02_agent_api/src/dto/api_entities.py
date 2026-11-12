from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

class ChatRequest(BaseModel):
    question: str
    user: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    user: str
    answer: str
    session_id: UUID
    trace_id: UUID

class HistoryItem(BaseModel):
    question: str
    answer: str
    trace_id: UUID
    session_id: UUID
    user: Optional[str] = None
    retrieved_contexts: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class UserSessionsResponse(BaseModel):
    user: str
    sessions: List[str]