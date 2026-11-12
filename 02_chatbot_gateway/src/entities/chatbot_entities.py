from pydantic import BaseModel, Field
from typing import List, Dict, Any

class MessagePayload(BaseModel):
    id: str
    timestamp: int
    from_: str = Field(alias="from")
    fromMe: bool
    body: str
    hasMedia: bool
    ack: int
    _data: Dict[str, Any]

class WahaRequest(BaseModel):
    event: str
    session: str
    payload: MessagePayload
