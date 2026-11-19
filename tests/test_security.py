from unittest.mock import MagicMock

from users_management.config import Settings
from users_management.domain import User
from users_management.infrastructure import EmailSender, Security, UserRepository, make_engine


def test_bcrypt_and_jwt_round_trip():
    config = Settings(jwt_secret="0123456789abcdef0123456789abcdef", jwt_expiration_seconds=900)
    security = Security(config)
    hashed = security.hash_password("secret")
    assert security.verify_password("secret", hashed)
    assert not security.verify_password("wrong", hashed)
    user = User(name="Ana", email="ana@example.com", password_hash=hashed)
    claims = security.decode(security.token(user))
    assert claims["sub"] == str(user.id)


def test_console_email_adapter_does_not_send_external_mail(caplog):
    caplog.set_level("INFO", logger="users_management.infrastructure")
    sender = EmailSender(Settings(email_provider="console"))
    sender.send("ana@example.com", "Hello", "Body")
    assert "ana@example.com" in caplog.text


def test_repository_save_and_get():
    session = MagicMock()
    repository = UserRepository(session)
    user = User(name="Ana", email="ana@example.com", password_hash="hash")
    repository.save(user)
    row = session.add.call_args.args[0]
    assert row.email == "ana@example.com"
    session.get.return_value = row
    assert repository.get(user.id).id == user.id


def test_make_engine_encodes_credentials_and_ssl():
    config = Settings(db_username="user+name", db_password="p@ss", db_ssl_mode="require")
    engine = make_engine(config)
    assert engine.url.username == "user+name"
    assert engine.url.password == "p@ss"
    assert engine.dialect.name == "postgresql"
    engine.dispose()


def test_security_rejects_invalid_password_hash():
    security = Security(Settings(jwt_secret="0123456789abcdef0123456789abcdef"))
    assert not security.verify_password("x", "not-a-hash")


def test_repository_delete_missing_user():
    session = MagicMock()
    session.get.return_value = None
    assert not UserRepository(session).delete("missing")
    session.delete.assert_not_called()


def test_repository_delete_existing_user():
    session = MagicMock()
    session.get.return_value = object()
    assert UserRepository(session).delete("id")
    session.delete.assert_called_once()
    session.commit.assert_called_once()


def test_repository_list_and_email_lookup():
    session = MagicMock()
    row = MagicMock()
    row.id = User(name="Ana", email="ana@example.com", password_hash="hash").id
    row.name = "Ana"
    row.email = "ana@example.com"
    row.password = "hash"
    row.role = "MEMBER"
    row.status = "PENDING"
    row.created_at = User(name="A", email="a@b.com", password_hash="x").created_at
    row.updated_at = row.created_at
    session.scalar.return_value = row
    session.scalars.return_value.all.return_value = [row]
    repo = UserRepository(session)
    assert repo.by_email("ana@example.com").name == "Ana"
    assert repo.list()[0].email == "ana@example.com"


def test_smtp_email_adapter_sends_message(monkeypatch):
    captured = {}

    class SMTP:
        def __init__(self, host, port, timeout):
            captured["connection"] = (host, port, timeout)
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def starttls(self):
            captured["tls"] = True
        def login(self, username, password):
            captured["login"] = (username, password)
        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr("users_management.infrastructure.smtplib.SMTP", SMTP)
    settings = Settings(email_provider="smtp", smtp_username="sender@example.com",
                        smtp_password="password", smtp_from_address="sender@example.com")
    EmailSender(settings).send("to@example.com", "Subject", "Body")
    assert captured["tls"]
    assert captured["message"]["To"] == "to@example.com"
