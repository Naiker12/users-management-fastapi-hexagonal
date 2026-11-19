from uuid import uuid4

import pytest

from users_management.application import UserService
from users_management.domain import (
    InvalidCredentials,
    InvalidUserData,
    User,
    UserAlreadyExists,
    UserNotFound,
    UserRole,
    UserStatus,
)


class FakeRepository:
    def __init__(self, user=None):
        self.user = user

    def by_email(self, email):
        return self.user if self.user and self.user.email == email else None

    def save(self, user):
        self.user = user
        return user

    def get(self, user_id):
        return self.user if self.user and self.user.id == user_id else None

    def list(self):
        return [self.user] if self.user else []

    def update(self, user):
        self.user = user
        return user

    def delete(self, user_id):
        if self.get(user_id):
            self.user = None
            return True
        return False


class FakeSecurity:
    class Config:
        jwt_expiration_seconds = 900
    settings = Config()

    @staticmethod
    def hash_password(password):
        return f"hashed:{password}"

    @staticmethod
    def verify_password(password, hashed):
        return hashed == f"hashed:{password}"

    @staticmethod
    def token(user):
        return "token"


class FakeEmail:
    def __init__(self):
        self.messages = []

    def send(self, *message):
        self.messages.append(message)


def make_service(user=None):
    repo, email = FakeRepository(user), FakeEmail()
    return UserService(repo, FakeSecurity(), email), repo, email


def test_create_user_normalizes_and_notifies():
    service, repo, email = make_service()
    user = service.create({"name": " Ana ", "email": "ANA@example.com", "password": "Clave1234!"})
    assert user.email == "ana@example.com"
    assert user.name == "Ana"
    assert user.password_hash == "hashed:Clave1234!"
    assert user.status == UserStatus.PENDING
    assert email.messages[0][0] == user.email
    assert repo.user == user


@pytest.mark.parametrize("payload", [
    {"name": " ", "email": "ana@example.com", "password": "Clave1234!"},
    {"name": "Ana", "email": "ana@example.com", "password": "short"},
    {"name": "Ana", "email": "ana@example.com", "password": "Clave1234!", "role": "ROOT"},
])
def test_create_rejects_invalid_data(payload):
    service, _, _ = make_service()
    with pytest.raises(InvalidUserData):
        service.create(payload)


def test_create_rejects_duplicate_email():
    existing = User(name="Ana", email="ana@example.com", password_hash="hash")
    service, _, _ = make_service(existing)
    with pytest.raises(UserAlreadyExists):
        service.create({"name": "Ana", "email": "ana@example.com", "password": "Clave1234!"})


def test_get_list_update_delete():
    original = User(name="Ana", email="ana@example.com", password_hash="hashed:Clave1234!",
                    role=UserRole.MEMBER, status=UserStatus.ACTIVE)
    service, repo, email = make_service(original)
    assert service.get(original.id) == original
    assert service.list() == [original]
    changed = service.update(original.id, {"name": "Ana Maria", "status": "BLOCKED"})
    assert changed.name == "Ana Maria"
    assert changed.password_hash == original.password_hash
    assert changed.status == UserStatus.BLOCKED
    assert email.messages[-1][0] == changed.email
    service.delete(original.id)
    assert repo.user is None
    with pytest.raises(UserNotFound):
        service.get(uuid4())
    with pytest.raises(UserNotFound):
        service.delete(uuid4())


def test_update_password_and_rejects_bad_values():
    original = User(name="Ana", email="ana@example.com", password_hash="old",
                    status=UserStatus.ACTIVE)
    service, _, _ = make_service(original)
    changed = service.update(original.id, {"password": "newsecret", "role": "ADMIN"})
    assert changed.password_hash == "hashed:newsecret"
    assert changed.role == UserRole.ADMIN
    with pytest.raises(InvalidUserData):
        service.update(original.id, {"status": "GONE"})
    with pytest.raises(InvalidUserData):
        service.update(original.id, {"password": "tiny"})


def test_login_checks_active_status_and_password():
    active = User(name="Admin", email="admin@example.com", password_hash="hashed:secret",
                  role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    service, _, _ = make_service(active)
    assert service.login("ADMIN@example.com", "secret") == ("token", 900)
    with pytest.raises(InvalidCredentials):
        service.login("admin@example.com", "bad")
    inactive = User(name="Ana", email="ana@example.com", password_hash="hashed:secret",
                    status=UserStatus.PENDING)
    service, _, _ = make_service(inactive)
    with pytest.raises(InvalidCredentials):
        service.login("ana@example.com", "secret")
