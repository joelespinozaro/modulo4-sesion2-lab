from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.repositories.history_repository import HistoryRepository
from src.repositories.models.history import History


class HistoryService:
    def __init__(self, db: Session) -> None:
        self._repo = HistoryRepository(db)

    def get_by_session(self, session_id: str) -> List[History]:
        return self._repo.get_all_by_session_id(session_id)

    def get_sessions_by_user(self, user: str) -> List[str]:
        return self._repo.get_sessions_by_user(user)

    def get_by_trace_id(self, trace_id: str) -> Optional[History]:
        return self._repo.get_by_trace_id(trace_id)

    def save_feedback(
        self,
        trace_id: str,
        is_ok: bool,
        error_type_id: Optional[int],
        observations: Optional[str],
    ) -> History:
        record = self._repo.get_by_trace_id(trace_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"trace_id '{trace_id}' not found")
        return self._repo.save_feedback(
            trace_id=trace_id,
            is_ok=is_ok,
            error_type_id=error_type_id,
            observations=observations,
        )