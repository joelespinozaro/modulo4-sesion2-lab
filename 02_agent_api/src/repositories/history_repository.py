from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.repositories.models.history import History


class HistoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, history: History) -> History:
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def get_by_trace_id(self, trace_id: str) -> Optional[History]:
        return self.db.query(History).filter(History.trace_id == trace_id).first()

    def save_feedback(
        self,
        trace_id: str,
        is_ok: bool,
        error_type_id: Optional[int],
        observations: Optional[str],
    ) -> History:
        record = self.get_by_trace_id(trace_id)
        record.is_ok = is_ok
        record.error_type_id = error_type_id
        record.observations = observations
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_session_id(self, session_id: str, limit: int = 10) -> List[History]:
        return (
            self.db.query(History)
            .filter(History.session_id == session_id)
            .order_by(History.created_at.asc())
            .limit(limit)
            .all()
        )

    def get_all_by_session_id(self, session_id: str) -> List[History]:
        return (
            self.db.query(History)
            .filter(History.session_id == session_id)
            .order_by(History.created_at.asc())
            .all()
        )

    def get_sessions_by_user(self, user: str) -> List[str]:
        rows = (
            self.db.query(History.session_id)
            .filter(History.user == user)
            .group_by(History.session_id)
            .order_by(func.max(History.created_at).desc())
            .all()
        )
        return [row.session_id for row in rows]