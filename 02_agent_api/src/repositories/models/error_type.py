from sqlalchemy import Column, Integer, String

from src.repositories.models.history import Base


class ErrorType(Base):
    __tablename__ = "error_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(40), nullable=False)
