from typing import List

from sqlalchemy.orm import Session

from src.repositories.models.error_type import ErrorType


class ErrorTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> List[ErrorType]:
        return self.db.query(ErrorType).all()
