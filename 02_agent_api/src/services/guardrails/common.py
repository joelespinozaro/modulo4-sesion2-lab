"""Utilidades compartidas por las 8 capas del pipeline InputGuardrail (HU SEC-001).

Provee helpers para hashear mensajes (nunca se loguea texto plano potencialmente
sensible), construir la respuesta estándar de bloqueo (`jump_to: "end"`) y cargar
configuración versionada desde `config/guardrails/`.
"""
import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "guardrails"

DEFAULT_BLOCK_MESSAGE = (
    "Lo sentimos, no podemos procesar tu mensaje. Por favor, reformula tu "
    "consulta o contacta a soporte si crees que se trata de un error."
)

_block_counts_lock = threading.Lock()
_block_counts: Dict[str, int] = {}


def hash_message(text: str) -> str:
    """Hashea el mensaje (sha256) para no exponer PII/secretos en logs."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def load_yaml_config(filename: str) -> Dict[str, Any]:
    """Carga un archivo YAML de configuración desde config/guardrails/."""
    path = CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _increment_block_count(layer: str) -> int:
    with _block_counts_lock:
        _block_counts[layer] = _block_counts.get(layer, 0) + 1
        return _block_counts[layer]


def get_block_counts() -> Dict[str, int]:
    """Snapshot de los contadores de bloqueo en memoria, por capa."""
    with _block_counts_lock:
        return dict(_block_counts)


def log_block(
    logger,
    layer: str,
    message: str,
    reason: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Registra un bloqueo sin exponer el mensaje en texto plano.

    Cumple el criterio de auditoría de la HU: capa que bloqueó, timestamp
    (agregado automáticamente por el logger), hash del mensaje y motivo.
    El timestamp se agrega automáticamente por el formatter de logging.
    """
    count = _increment_block_count(layer)
    log_extra = {
        "guardrail_layer": layer,
        "message_hash": hash_message(message),
        "block_reason": reason,
        "layer_block_count": count,
    }
    if extra:
        log_extra.update(extra)
    logger.warning("InputGuardrail bloqueó un mensaje en %s: %s", layer, reason, extra=log_extra)


def block_result(text: str = DEFAULT_BLOCK_MESSAGE) -> Dict[str, Any]:
    """Construye el payload estándar para cortar la ejecución del agente."""
    return {
        "messages": [{"role": "assistant", "content": text}],
        "jump_to": "end",
    }


def get_latest_human_message(state: Dict[str, Any]) -> Optional[Any]:
    """Devuelve el mensaje humano más reciente del estado (el mensaje entrante actual).

    En este proyecto el historial de la conversación se antepone manualmente
    a la lista de `messages` en cada invocación (ver `AgentService.chat`), por
    lo que el mensaje del usuario que hay que validar es siempre el ÚLTIMO de
    la lista, no el primero.
    """
    messages = state.get("messages") or []
    if not messages:
        return None
    last_message = messages[-1]
    if getattr(last_message, "type", None) != "human":
        return None
    return last_message


def get_latest_human_text(state: Dict[str, Any]) -> Optional[str]:
    """Extrae el contenido de texto del mensaje humano más reciente, si existe."""
    message = get_latest_human_message(state)
    if message is None:
        return None
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    return None
