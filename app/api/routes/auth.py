from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.application.auth_service import AuthService


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def create_auth_router(auth_service: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/auth")

    @router.post("/signup")
    async def signup(payload: SignupRequest):
        result = auth_service.signup(payload.name, payload.email, payload.password)
        if "detail" in result:
            raise HTTPException(status_code=400, detail=result["detail"])
        return result

    @router.post("/login")
    async def login(payload: LoginRequest):
        result = auth_service.login(payload.email, payload.password)
        if "detail" in result:
            raise HTTPException(status_code=401, detail=result["detail"])
        return result

    @router.get("/me")
    async def me(authorization: str | None = Header(default=None)):
        user = auth_service.get_user_by_token(_extract_bearer_token(authorization))
        if user is None:
            raise HTTPException(status_code=401, detail="Please log in.")
        return {"user": AuthService._serialize_user(user)}

    @router.post("/logout")
    async def logout(authorization: str | None = Header(default=None)):
        auth_service.logout(_extract_bearer_token(authorization))
        return {"ok": True}

    return router


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token
