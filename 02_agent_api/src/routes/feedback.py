from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.controllers.chat_controller import handle_feedback
from src.dto.api_entities import FeedbackRequest, FeedbackResponse
from src.repositories import get_db

router = APIRouter()


@router.post("/api/feedback", response_model=FeedbackResponse, tags=["feedback"])
def feedback(request: FeedbackRequest, db: Session = Depends(get_db)) -> FeedbackResponse:
    return handle_feedback(
        trace_id=request.trace_id,
        is_ok=request.is_ok,
        error_type_id=request.error_type_id,
        observations=request.observations,
        db=db,
    )
