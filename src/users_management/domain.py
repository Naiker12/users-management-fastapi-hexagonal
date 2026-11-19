from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    REVIEWER = "REVIEWER"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"


class DomainError(Exception):
    """Base for expected domain failures."""


class InvalidUserData(DomainError):
    pass


class UserNotFound(DomainError):
    pass


class UserAlreadyExists(DomainError):
    pass


class InvalidCredentials(DomainError):
    pass


@dataclass(frozen=True)
class User:
    name: str
    email: str
    password_hash: str
    role: UserRole = UserRole.MEMBER
    status: UserStatus = UserStatus.PENDING
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if len(normalized) > 150 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise InvalidUserData("Correo electrónico inválido.")
        return normalized

    @staticmethod
    def validate_name(name: str) -> str:
        normalized = name.strip()
        if not 1 <= len(normalized) <= 100:
            raise InvalidUserData("El nombre debe tener entre 1 y 100 caracteres.")
        return normalized
