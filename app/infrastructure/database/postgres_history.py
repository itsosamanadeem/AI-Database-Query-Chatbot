from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from uuid import uuid4

from sqlalchemy import create_engine, text


@dataclass(frozen=True)
class StoredMessage:
    role: str
    content: str


@dataclass(frozen=True)
class StoredConversation:
    id: str
    title: str
    updated_at: datetime


@dataclass(frozen=True)
class StoredUser:
    id: str
    name: str
    email: str


@dataclass(frozen=True)
class PendingClarification:
    original_question: str
    clarification_question: str


class PostgresChatHistory:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url)

    def initialize(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS app_users (
                        id UUID PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS auth_sessions (
                        token_hash TEXT PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES app_users(id)
                            ON DELETE CASCADE,
                        expires_at TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS chat_conversations (
                        id UUID PRIMARY KEY,
                        user_id UUID REFERENCES app_users(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    ALTER TABLE chat_conversations
                    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES app_users(id)
                    ON DELETE CASCADE
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id BIGSERIAL PRIMARY KEY,
                        conversation_id UUID NOT NULL REFERENCES chat_conversations(id)
                            ON DELETE CASCADE,
                        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS pending_clarifications (
                        conversation_id UUID PRIMARY KEY
                            REFERENCES chat_conversations(id) ON DELETE CASCADE,
                        original_question TEXT NOT NULL,
                        clarification_question TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_updated
                    ON chat_conversations (user_id, updated_at DESC)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created
                    ON chat_messages (conversation_id, created_at, id)
                    """
                )
            )

    def create_user(self, name: str, email: str, password: str) -> StoredUser:
        user_id = str(uuid4())
        clean_name = " ".join(name.strip().split())
        clean_email = email.strip().lower()
        password_hash = self._hash_password(password)

        with self.engine.begin() as connection:
            existing = connection.execute(
                text("SELECT 1 FROM app_users WHERE email = :email"),
                {"email": clean_email},
            ).first()
            if existing is not None:
                raise ValueError("An account with this email already exists.")

            connection.execute(
                text(
                    """
                    INSERT INTO app_users (id, name, email, password_hash)
                    VALUES (:user_id, :name, :email, :password_hash)
                    """
                ),
                {
                    "user_id": user_id,
                    "name": clean_name,
                    "email": clean_email,
                    "password_hash": password_hash,
                },
            )

        return StoredUser(id=user_id, name=clean_name, email=clean_email)

    def authenticate_user(self, email: str, password: str) -> StoredUser | None:
        clean_email = email.strip().lower()
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id, name, email, password_hash
                    FROM app_users
                    WHERE email = :email
                    """
                ),
                {"email": clean_email},
            ).mappings().first()

        if row is None or not self._verify_password(password, row["password_hash"]):
            return None

        return StoredUser(id=str(row["id"]), name=row["name"], email=row["email"])

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO auth_sessions (token_hash, user_id, expires_at)
                    VALUES (:token_hash, :user_id, :expires_at)
                    """
                ),
                {
                    "token_hash": token_hash,
                    "user_id": user_id,
                    "expires_at": expires_at,
                },
            )
        return token

    def get_user_by_session(self, token: str) -> StoredUser | None:
        token_hash = self._hash_token(token)
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM auth_sessions WHERE expires_at <= NOW()")
            )
            row = connection.execute(
                text(
                    """
                    SELECT app_users.id, app_users.name, app_users.email
                    FROM auth_sessions
                    JOIN app_users ON app_users.id = auth_sessions.user_id
                    WHERE auth_sessions.token_hash = :token_hash
                      AND auth_sessions.expires_at > NOW()
                    """
                ),
                {"token_hash": token_hash},
            ).mappings().first()

        if row is None:
            return None

        return StoredUser(id=str(row["id"]), name=row["name"], email=row["email"])

    def delete_session(self, token: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM auth_sessions WHERE token_hash = :token_hash"),
                {"token_hash": self._hash_token(token)},
            )

    def create_conversation(self, first_message: str, user_id: str) -> str:
        conversation_id = str(uuid4())
        title = self._make_title(first_message)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chat_conversations (id, user_id, title)
                    VALUES (:conversation_id, :user_id, :title)
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "title": title,
                },
            )
        return conversation_id

    def conversation_exists(self, conversation_id: str, user_id: str) -> bool:
        with self.engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT 1
                    FROM chat_conversations
                    WHERE id = :conversation_id AND user_id = :user_id
                    """
                ),
                {"conversation_id": conversation_id, "user_id": user_id},
            ).first()
        return result is not None

    def list_conversations(
        self, user_id: str, limit: int = 30
    ) -> list[StoredConversation]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT id, title, updated_at
                    FROM chat_conversations
                    WHERE user_id = :user_id
                    ORDER BY updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"user_id": user_id, "limit": limit},
            ).mappings()
            return [
                StoredConversation(
                    id=str(row["id"]),
                    title=row["title"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def get_recent_messages(
        self, conversation_id: str, user_id: str, limit: int
    ) -> list[StoredMessage]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT role, content
                    FROM (
                        SELECT
                            chat_messages.role,
                            chat_messages.content,
                            chat_messages.created_at,
                            chat_messages.id
                        FROM chat_messages
                        JOIN chat_conversations
                            ON chat_conversations.id = chat_messages.conversation_id
                        WHERE chat_messages.conversation_id = :conversation_id
                          AND chat_conversations.user_id = :user_id
                        ORDER BY chat_messages.created_at DESC, chat_messages.id DESC
                        LIMIT :limit
                    ) recent_messages
                    ORDER BY recent_messages.created_at ASC, recent_messages.id ASC
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "limit": limit,
                },
            ).mappings()
            return [
                StoredMessage(role=row["role"], content=row["content"])
                for row in rows
            ]

    def get_messages(self, conversation_id: str, user_id: str) -> list[StoredMessage]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT chat_messages.role, chat_messages.content
                    FROM chat_messages
                    JOIN chat_conversations
                        ON chat_conversations.id = chat_messages.conversation_id
                    WHERE chat_messages.conversation_id = :conversation_id
                      AND chat_conversations.user_id = :user_id
                    ORDER BY chat_messages.created_at ASC, chat_messages.id ASC
                    """
                ),
                {"conversation_id": conversation_id, "user_id": user_id},
            ).mappings()
            return [
                StoredMessage(role=row["role"], content=row["content"])
                for row in rows
            ]

    def get_pending_clarification(
        self, conversation_id: str, user_id: str
    ) -> PendingClarification | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        pending_clarifications.original_question,
                        pending_clarifications.clarification_question
                    FROM pending_clarifications
                    JOIN chat_conversations
                        ON chat_conversations.id = pending_clarifications.conversation_id
                    WHERE pending_clarifications.conversation_id = :conversation_id
                      AND chat_conversations.user_id = :user_id
                    """
                ),
                {"conversation_id": conversation_id, "user_id": user_id},
            ).mappings().first()

        if row is None:
            return None

        return PendingClarification(
            original_question=row["original_question"],
            clarification_question=row["clarification_question"],
        )

    def set_pending_clarification(
        self,
        conversation_id: str,
        original_question: str,
        clarification_question: str,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO pending_clarifications (
                        conversation_id,
                        original_question,
                        clarification_question
                    )
                    VALUES (
                        :conversation_id,
                        :original_question,
                        :clarification_question
                    )
                    ON CONFLICT (conversation_id) DO UPDATE
                    SET original_question = EXCLUDED.original_question,
                        clarification_question = EXCLUDED.clarification_question,
                        created_at = NOW()
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "original_question": original_question,
                    "clarification_question": clarification_question,
                },
            )

    def clear_pending_clarification(self, conversation_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DELETE FROM pending_clarifications
                    WHERE conversation_id = :conversation_id
                    """
                ),
                {"conversation_id": conversation_id},
            )

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO chat_messages (conversation_id, role, content)
                    VALUES (:conversation_id, :role, :content)
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "role": role,
                    "content": content,
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE chat_conversations
                    SET updated_at = NOW()
                    WHERE id = :conversation_id
                    """
                ),
                {"conversation_id": conversation_id},
            )

    def dispose(self) -> None:
        self.engine.dispose()

    @staticmethod
    def _make_title(message: str) -> str:
        title = " ".join(message.strip().split())
        if not title:
            return "New conversation"
        return title[:77] + "..." if len(title) > 80 else title

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000
        ).hex()
        return f"pbkdf2_sha256${salt}${digest}"

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        try:
            algorithm, salt, expected_digest = password_hash.split("$", 2)
        except ValueError:
            return False

        if algorithm != "pbkdf2_sha256":
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 260000
        ).hex()
        return hmac.compare_digest(digest, expected_digest)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
