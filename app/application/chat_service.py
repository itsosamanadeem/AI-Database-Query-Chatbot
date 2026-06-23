from uuid import UUID

from app.infrastructure.database.postgres_history import PostgresChatHistory


class ChatService:
    def __init__(
        self,
        agent,
        history: PostgresChatHistory,
        history_context_limit: int,
    ) -> None:
        self.agent = agent
        self.history = history
        self.history_context_limit = history_context_limit

    def ask(self, question: str, user_id: str, conversation_id: str | None = None):
        clean_question = question.strip()
        if not clean_question:
            return {"detail": "Question cannot be empty."}

        active_conversation_id = self._get_or_create_conversation(
            clean_question, user_id, conversation_id
        )
        previous_messages = self.history.get_recent_messages(
            active_conversation_id, user_id, self.history_context_limit
        )
        messages = [
            {"role": message.role, "content": message.content}
            for message in previous_messages
        ]
        messages.append({"role": "user", "content": clean_question})

        self.history.add_message(active_conversation_id, "user", clean_question)
        response = self.agent.invoke({"messages": messages})
        answer = self._extract_answer(response)
        self.history.add_message(active_conversation_id, "assistant", answer)

        return {
            "conversation_id": active_conversation_id,
            "answer": answer,
        }

    def get_messages(self, conversation_id: str, user_id: str):
        try:
            UUID(conversation_id)
        except ValueError:
            return {"conversation_id": conversation_id, "messages": []}

        if not self.history.conversation_exists(conversation_id, user_id):
            return {"conversation_id": conversation_id, "messages": []}

        return {
            "conversation_id": conversation_id,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in self.history.get_messages(conversation_id, user_id)
            ],
        }

    def list_conversations(self, user_id: str):
        return {
            "conversations": [
                {
                    "id": conversation.id,
                    "title": conversation.title,
                    "updated_at": conversation.updated_at.isoformat(),
                }
                for conversation in self.history.list_conversations(user_id)
            ]
        }

    def _get_or_create_conversation(
        self, question: str, user_id: str, conversation_id: str | None
    ) -> str:
        if conversation_id:
            try:
                UUID(conversation_id)
            except ValueError:
                conversation_id = None

        if conversation_id and self.history.conversation_exists(conversation_id, user_id):
            return conversation_id

        return self.history.create_conversation(question, user_id)

    @staticmethod
    def _extract_answer(response) -> str:
        if isinstance(response, str):
            return response

        response_messages = response.get("messages") if isinstance(response, dict) else None
        if isinstance(response_messages, list) and response_messages:
            last_message = response_messages[-1]
            content = getattr(last_message, "content", None)

            if content is None and isinstance(last_message, dict):
                content = last_message.get("content")

            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict) and part.get("text"):
                        parts.append(part["text"])
                return "\n".join(parts)

        if isinstance(response, dict):
            return (
                response.get("answer")
                or response.get("output")
                or "The query completed, but no readable answer was returned."
            )

        return "The query completed, but no readable answer was returned."
