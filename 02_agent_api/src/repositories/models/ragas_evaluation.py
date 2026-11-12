from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB

from src.repositories.models.history import Base


class RagasEvaluation(Base):
    __tablename__ = "ragas_evaluations"

    id = Column(String, primary_key=True, nullable=False)          # UUID como string
    trace_ids = Column(JSONB, nullable=False)                      # lista de trace_ids evaluados
    evaluated_at = Column(DateTime, server_default=func.now(), nullable=False)
    metrics = Column(JSONB, nullable=False)                        # {"faithfulness": 0.9, ...}
    llm_judge = Column(String, nullable=False, default="gpt-4o-mini")
    langsmith_run_url = Column(String, nullable=True)
