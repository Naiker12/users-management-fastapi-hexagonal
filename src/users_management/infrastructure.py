from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote_plus

import bcrypt
import jwt
from sqlalchemy import DateTime, String, create_engine, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from users_management.config import Settings
from users_management.domain import User, UserAlreadyExists, UserRole, UserStatus

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = ( {"schema": "crud_usuarios"}, )

    id: Mapped[object] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


def make_engine(settings: Settings):
    password = quote_plus(settings.db_password)
    url = (f"postgresql+psycopg://{quote_plus(settings.db_username)}:{password}@"
           f"{settings.db_host}:{settings.db_port}/{settings.db_name}")
    connect_args = {}
    connect_args["connect_timeout"] = 10
    if settings.db_ssl_mode.lower() not in {"disable", ""}:
        connect_args["sslmode"] = settings.db_ssl_mode.lower()
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def to_domain(row: UserRow) -> User:
        return User(name=row.name, email=row.email, password_hash=row.password,
                    role=UserRole(row.role), status=UserStatus(row.status), id=row.id,
                    created_at=row.created_at, updated_at=row.updated_at)

    def save(self, user: User) -> User:
        row = UserRow(id=user.id, name=user.name, email=user.email,
                      password=user.password_hash, role=user.role.value, status=user.status.value,
                      created_at=user.created_at, updated_at=user.updated_at)
        self.session.add(row)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise UserAlreadyExists("Ya existe un usuario con ese correo.") from exc
        return self.to_domain(row)

    def get(self, user_id) -> User | None:
        row = self.session.get(UserRow, user_id)
        return self.to_domain(row) if row else None

    def by_email(self, email: str) -> User | None:
        row = self.session.scalar(select(UserRow).where(UserRow.email == email))
        return self.to_domain(row) if row else None

    def list(self) -> list[User]:
        rows = self.session.scalars(select(UserRow).order_by(UserRow.created_at)).all()
        return [self.to_domain(row) for row in rows]

    def update(self, user: User) -> User:
        row = self.session.get(UserRow, user.id)
        if row is None:
            return self.save(user)
        row.name, row.email, row.password = user.name, user.email, user.password_hash
        row.role, row.status = user.role.value, user.status.value
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise UserAlreadyExists("Ya existe un usuario con ese correo.") from exc
        self.session.refresh(row)
        return self.to_domain(row)

    def delete(self, user_id) -> bool:
        row = self.session.get(UserRow, user_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True


class Security:
    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except (ValueError, TypeError):
            return False

    def token(self, user: User) -> str:
        import time
        now = int(time.time())
        return jwt.encode({"sub": str(user.id), "email": user.email,
                           "iat": now, "exp": now + self.settings.jwt_expiration_seconds},
                          self.settings.jwt_secret, algorithm="HS256")

    def decode(self, token: str) -> dict:
        return jwt.decode(token, self.settings.jwt_secret, algorithms=["HS256"])


class EmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        if self.settings.email_provider == "smtp":
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_address}>"
            message["To"] = to
            message.set_content("Este mensaje contiene una versión HTML. Abre el correo en un cliente compatible.")
            message.add_alternative(body, subtype="html")
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)
        else:
            logger.info("Correo simulado para %s: %s\n%s", to, subject, body)
