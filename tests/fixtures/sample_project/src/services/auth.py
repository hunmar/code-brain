from src.models.user import User, AdminUser


class AuthService:
    def __init__(self, user_repo):
        self.user_repo = user_repo

    def authenticate(self, email: str, password: str) -> User | None:
        user = self.user_repo.find_by_email(email)
        if user and self._verify(password):
            return user
        return None

    def _verify(self, password: str) -> bool:
        return len(password) >= 8
