from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.repositories.models.ragas_evaluation import RagasEvaluation
from src.services.ragas_service import RagasService


def handle_evaluate(
    trace_ids: Optional[List[str]],
    session_id: Optional[str],
    ground_truths: Optional[Dict[str, str]],
    db: Session,
) -> RagasEvaluation:
    service = RagasService(db)
    return service.evaluate(
        trace_ids=trace_ids,
        session_id=session_id,
        ground_truths=ground_truths,
    )
