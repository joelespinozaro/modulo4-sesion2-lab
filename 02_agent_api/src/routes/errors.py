from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.controllers.error_type_controller import get_error_types
from src.dto.api_entities import ErrorTypeResponse
from src.repositories import get_db

router = APIRouter()


@router.get("/api/errors", response_model=List[ErrorTypeResponse], tags=["errors"])
def list_error_types(db: Session = Depends(get_db)) -> List[ErrorTypeResponse]:
    return get_error_types(db=db)
