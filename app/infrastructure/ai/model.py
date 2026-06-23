from langchain_ollama import ChatOllama

from app.core.config import Settings


def create_chat_model(settings: Settings) -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
    )
