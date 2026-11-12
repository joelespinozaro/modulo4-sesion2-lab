from typing import List

from sqlalchemy.orm import Session

from src.repositories.models.error_type import ErrorType
from src.services.error_type_service import ErrorTypeService


def get_error_types(db: Session) -> List[ErrorType]:
    service = ErrorTypeService(db)
    return service.get_all()
