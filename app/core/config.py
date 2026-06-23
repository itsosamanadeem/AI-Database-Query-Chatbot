import os
from dataclasses import dataclass

from dotenv import load_dotenv
from sqlalchemy.engine import URL


load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_user: str | None
    db_password: str | None
    db_host: str
    db_port: int
    db_name: str
    db_driver: str
    db_encrypt: str
    db_trust_server_certificate: str
    chat_history_database_url: str
    chat_history_context_limit: int
    ollama_model: str = "llama3.2:3b"
    ollama_base_url: str = "http://localhost:11434"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            db_user=os.getenv("DB_USER"),
            db_password=os.getenv("DB_PASSWORD"),
            db_host=os.getenv("DB_HOST", "172.30.1.118"),
            db_port=int(os.getenv("DB_PORT", "1433")),
            db_name=os.getenv("DB_NAME", "TableauDB"),
            db_driver=os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
            db_encrypt=os.getenv("DB_ENCRYPT", "no"),
            db_trust_server_certificate=os.getenv(
                "DB_TRUST_SERVER_CERTIFICATE", "yes"
            ),
            chat_history_database_url=os.getenv(
                "CHAT_HISTORY_DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@localhost:5435/postgres",
            ),
            chat_history_context_limit=int(
                os.getenv("CHAT_HISTORY_CONTEXT_LIMIT", "12")
            ),
        )

    def database_url(self) -> URL:
        return URL.create(
            "mssql+pyodbc",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={
                "driver": self.db_driver,
                "Encrypt": self.db_encrypt,
                "TrustServerCertificate": self.db_trust_server_certificate,
            },
        )

    def history_database_url(self) -> str:
        return self.chat_history_database_url
