from __future__ import annotations

from typing import Protocol
from uuid import UUID

from users_management.domain import (
    InvalidCredentials,
    InvalidUserData,
    User,
    UserNotFound,
    UserRole,
    UserStatus,
)


class UserRepositoryPort(Protocol):
    def by_email(self, email: str) -> User | None: ...
    def save(self, user: User) -> User: ...
    def get(self, user_id: UUID) -> User | None: ...
    def list(self) -> list[User]: ...
    def update(self, user: User) -> User: ...
    def delete(self, user_id: UUID) -> bool: ...


class PasswordSecurityPort(Protocol):
    settings: object
    def hash_password(self, password: str) -> str: ...
    def verify_password(self, password: str, hashed: str) -> bool: ...
    def token(self, user: User) -> str: ...


class EmailSenderPort(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class EmailNotificationPort(Protocol):
    def user_created(self, user: User, temporary_password: str) -> None: ...
    def user_updated(self, user: User) -> None: ...


class EmailNotificationService:
    def __init__(self, sender: EmailSenderPort):
        from pathlib import Path
        self.sender = sender
        self.template_directory = Path(__file__).with_name("templates")

    def _render(self, template: str, values: dict[str, str]) -> str:
        import html
        content = (self.template_directory / template).read_text(encoding="utf-8")
        for key, value in values.items():
            content = content.replace("{{" + key + "}}", html.escape(value))
        return content

    def user_created(self, user: User, temporary_password: str) -> None:
        body = self._render("user-created.html", {
            "name": user.name,
            "email": user.email,
            "password": temporary_password,
            "role": user.role.value,
        })
        self.sender.send(user.email, "Usuario creado", body)

    def user_updated(self, user: User) -> None:
        body = self._render("user-updated.html", {
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "status": user.status.value,
        })
        self.sender.send(user.email, "Usuario actualizado", body)


class UserService:
    def __init__(self, repository: UserRepositoryPort, security: PasswordSecurityPort,
                 email: EmailNotificationPort):
        self.repository, self.security, self.email = repository, security, email

    def create(self, data: dict) -> User:
        name = User.validate_name(data["name"])
        email = User.normalize_email(data["email"])
        password = data["password"]
        if len(password) < 8:
            raise InvalidUserData("La contraseña debe tener al menos 8 caracteres.")
        if self.repository.by_email(email):
            from users_management.domain import UserAlreadyExists
            raise UserAlreadyExists("Ya existe un usuario con ese correo.")
        try:
            role = UserRole(data.get("role", "MEMBER"))
        except ValueError as exc:
            raise InvalidUserData("Rol inválido.") from exc
        user = self.repository.save(User(name=name, email=email,
                           password_hash=self.security.hash_password(password), role=role))
        self.email.user_created(user, password)
        return user

    def get(self, user_id: UUID) -> User:
        user = self.repository.get(user_id)
        if user is None:
            raise UserNotFound("Usuario no encontrado.")
        return user

    def list(self) -> list[User]:
        return self.repository.list()

    def update(self, user_id: UUID, data: dict) -> User:
        current = self.get(user_id)
        name = User.validate_name(data.get("name", current.name))
        email = User.normalize_email(data.get("email", current.email))
        password = data.get("password")
        if password is not None and len(password) < 8:
            raise InvalidUserData("La contraseña debe tener al menos 8 caracteres.")
        try:
            role = UserRole(data.get("role", current.role.value))
            status = UserStatus(data.get("status", current.status.value))
        except ValueError as exc:
            raise InvalidUserData("Rol o estado inválido.") from exc
        updated = User(id=current.id, name=name, email=email,
                       password_hash=self.security.hash_password(password) if password else current.password_hash,
                       role=role, status=status, created_at=current.created_at)
        result = self.repository.update(updated)
        self.email.user_updated(result)
        return result

    def delete(self, user_id: UUID) -> None:
        if not self.repository.delete(user_id):
            raise UserNotFound("Usuario no encontrado.")

    def login(self, email: str, password: str) -> tuple[str, int]:
        user = self.repository.by_email(User.normalize_email(email))
        if (user is None or user.status != UserStatus.ACTIVE
                or not self.security.verify_password(password, user.password_hash)):
            raise InvalidCredentials("Correo o contraseña incorrectos.")
        return self.security.token(user), self.security.settings.jwt_expiration_seconds
