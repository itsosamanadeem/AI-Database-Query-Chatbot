from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import create_auth_router
from app.api.routes.chat import create_chat_router
from app.application.auth_service import AuthService
from app.application.chat_service import ChatService
from app.core.config import Settings
from app.infrastructure.ai.agent import create_database_agent
from app.infrastructure.ai.model import create_chat_model
from app.infrastructure.ai.tools import create_database_tools
from app.infrastructure.database.sql_server import SqlServerDatabase
from app.infrastructure.database.postgres_history import PostgresChatHistory


settings = Settings.from_environment()
database = SqlServerDatabase(settings.database_url())
chat_history = PostgresChatHistory(settings.history_database_url())
auth_service = AuthService(chat_history)
model = create_chat_model(settings)
tools = create_database_tools(database, model)
agent = create_database_agent(model, tools)
chat_service = ChatService(
    agent,
    chat_history,
    settings.chat_history_context_limit,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    chat_history.initialize()
    yield
    chat_history.dispose()
    database.dispose()


app = FastAPI(
    title="DataQuery AI",
    description="Natural-language interface for querying SQL Server views.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(create_auth_router(auth_service))
app.include_router(create_chat_router(chat_service, auth_service))

frontend_directory = Path(__file__).resolve().parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_directory), name="static")


@app.get("/", include_in_schema=False)
async def frontend():
    return FileResponse(frontend_directory / "index.html")
