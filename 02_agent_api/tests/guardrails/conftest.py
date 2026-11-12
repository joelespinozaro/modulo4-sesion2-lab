import pytest
from langchain_core.messages import AIMessage, HumanMessage


def build_state(question: str, history: list | None = None) -> dict:
    """Construye un estado de agente con el mismo shape que usa AgentService.chat:
    historial previo (Human/AI intercalados) + el mensaje humano actual al final.
    """
    messages = list(history or [])
    messages.append(HumanMessage(content=question))
    return {"messages": messages}


@pytest.fixture
def sample_history() -> list:
    return [
        HumanMessage(content="Hola, ¿qué cursos tienen?"),
        AIMessage(content="Tenemos cursos de IA, Data y Cloud."),
    ]
