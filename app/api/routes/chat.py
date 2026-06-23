from fastapi import APIRouter, Header, HTTPException

from app.application.auth_service import AuthService
from app.application.chat_service import ChatService


def create_chat_router(chat_service: ChatService, auth_service: AuthService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/chat")
    async def chat(
        question: str,
        conversation_id: str | None = None,
        authorization: str | None = Header(default=None),
    ):
        user = _require_user(auth_service, authorization)
        return chat_service.ask(question, user.id, conversation_id)

    @router.get("/api/conversations")
    async def list_conversations(authorization: str | None = Header(default=None)):
        user = _require_user(auth_service, authorization)
        return chat_service.list_conversations(user.id)

    @router.get("/api/conversations/{conversation_id}/messages")
    async def get_messages(
        conversation_id: str,
        authorization: str | None = Header(default=None),
    ):
        user = _require_user(auth_service, authorization)
        return chat_service.get_messages(conversation_id, user.id)

    return router


def _require_user(auth_service: AuthService, authorization: str | None):
    token = _extract_bearer_token(authorization)
    user = auth_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token
