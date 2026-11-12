from typing import List, Optional

from sqlalchemy.orm import Session

from src.repositories.models.ragas_evaluation import RagasEvaluation


class RagasRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, evaluation: RagasEvaluation) -> RagasEvaluation:
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def get_by_id(self, evaluation_id: str) -> Optional[RagasEvaluation]:
        return (
            self.db.query(RagasEvaluation)
            .filter(RagasEvaluation.id == evaluation_id)
            .first()
        )

    def get_all(self, limit: int = 50) -> List[RagasEvaluation]:
        return (
            self.db.query(RagasEvaluation)
            .order_by(RagasEvaluation.evaluated_at.desc())
            .limit(limit)
            .all()
        )
