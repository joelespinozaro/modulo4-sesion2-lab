from sqlalchemy import Column, Integer, String, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class History(Base):
    __tablename__ = "history"

    trace_id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    user = Column(String(255), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    retrieved_contexts = Column(Text, nullable=True)