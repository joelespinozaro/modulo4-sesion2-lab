from src.entities.chatbot_entities import WahaRequest
from typing import Dict, Any, Optional
import uuid

# Namespace fijo para derivar un UUID determinístico a partir del número/chatId
# de WAHA. Mismo teléfono -> mismo UUID siempre, preservando la memoria de
# conversación sin requerir que session_id en la BD deje de ser tipo UUID.
_SESSION_NAMESPACE = uuid.UUID("a3f1c2d4-5b6e-4f7a-8c9d-0e1f2a3b4c5d")

def _phone_to_session_id(phone: str) -> str:
    return str(uuid.uuid5(_SESSION_NAMESPACE, phone))

def map_to_chatbot_payload(request: WahaRequest) -> Dict[str, str]:
    return {
        "question": request.payload.body,
        "user": request.payload.from_,
        "session_id": _phone_to_session_id(request.payload.from_)
    }

def map_to_send_text_payload(
    user: str, 
    response_text: str, 
    session: str,
    reply_to: Optional[str] = None,
    link_preview: bool = True,
    link_preview_high_quality: bool = False
) -> Dict[str, Any]:
    return {
        "chatId": user,
        "reply_to": reply_to,
        "text": response_text,
        "linkPreview": link_preview,
        "linkPreviewHighQuality": link_preview_high_quality,
        "session": session
    }

def map_to_send_sendSeen(user: str, session: str) -> Dict[str, Any]:
    return {
        "session": session,
        "chatId": user
    }

def map_to_send_presence_payload(user: str, presence: str) -> Dict[str, Any]:
    return {
        "chatId": user,
        "presence": presence
    }