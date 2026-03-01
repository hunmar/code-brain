from src.models.user import User


class UserRepository:
    def __init__(self):
        self._users: list[User] = []

    def find_by_email(self, email: str) -> User | None:
        for user in self._users:
            if user.email == email:
                return user
        return None

    def save(self, user: User) -> None:
        self._users.append(user)
