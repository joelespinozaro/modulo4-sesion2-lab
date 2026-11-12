from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.controllers.ragas_controller import handle_evaluate
from src.dto.api_entities import EvaluateRequest, EvaluateResponse, MetricResult
from src.repositories import get_db

router = APIRouter()


@router.post("/api/evaluate", response_model=EvaluateResponse, tags=["evaluation"])
def evaluate(
    request: EvaluateRequest,
    db: Session = Depends(get_db),
) -> EvaluateResponse:
    result = handle_evaluate(
        trace_ids=request.trace_ids,
        session_id=request.session_id,
        ground_truths=request.ground_truths,
        db=db,
    )
    metrics = [
        MetricResult(metric=k, score=v)
        for k, v in (result.metrics or {}).items()
    ]
    return EvaluateResponse(
        evaluation_id=result.id,
        evaluated_at=result.evaluated_at,
        trace_ids=result.trace_ids,
        llm_judge=result.llm_judge,
        metrics=metrics,
        langsmith_url=result.langsmith_run_url,
    )
