from app.infrastructure.database.postgres_history import PostgresChatHistory, StoredUser


class AuthService:
    def __init__(self, history: PostgresChatHistory) -> None:
        self.history = history

    def signup(self, name: str, email: str, password: str):
        clean_name = name.strip()
        clean_email = email.strip().lower()

        if len(clean_name) < 2:
            return {"detail": "Name must be at least 2 characters."}
        if "@" not in clean_email or "." not in clean_email:
            return {"detail": "Please enter a valid email address."}
        if len(password) < 6:
            return {"detail": "Password must be at least 6 characters."}

        try:
            user = self.history.create_user(clean_name, clean_email, password)
        except ValueError as error:
            return {"detail": str(error)}

        token = self.history.create_session(user.id)
        return {"token": token, "user": self._serialize_user(user)}

    def login(self, email: str, password: str):
        user = self.history.authenticate_user(email, password)
        if user is None:
            return {"detail": "Invalid email or password."}

        token = self.history.create_session(user.id)
        return {"token": token, "user": self._serialize_user(user)}

    def get_user_by_token(self, token: str | None) -> StoredUser | None:
        if not token:
            return None
        return self.history.get_user_by_session(token)

    def logout(self, token: str | None) -> None:
        if token:
            self.history.delete_session(token)

    @staticmethod
    def _serialize_user(user: StoredUser):
        return {"id": user.id, "name": user.name, "email": user.email}
