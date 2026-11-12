from typing import List

from sqlalchemy.orm import Session

from src.repositories.error_type_repository import ErrorTypeRepository
from src.repositories.models.error_type import ErrorType


class ErrorTypeService:
    def __init__(self, db: Session) -> None:
        self._repo = ErrorTypeRepository(db)

    def get_all(self) -> List[ErrorType]:
        return self._repo.get_all()
