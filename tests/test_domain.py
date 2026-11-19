import pytest

from users_management.domain import InvalidUserData, User, UserRole, UserStatus


def test_email_is_trimmed_and_lowercase():
    assert User.normalize_email(" Ana@Example.COM ") == "ana@example.com"


@pytest.mark.parametrize("value", ["", "no-es-correo", "a@b", "a b@example.com"])
def test_invalid_email_is_rejected(value):
    with pytest.raises(InvalidUserData):
        User.normalize_email(value)


def test_name_is_trimmed_and_length_checked():
    assert User.validate_name(" Ana ") == "Ana"
    with pytest.raises(InvalidUserData):
        User.validate_name(" ")


def test_user_defaults_and_enum_values():
    user = User(name="Ana", email="ana@example.com", password_hash="hash")
    assert user.role == UserRole.MEMBER
    assert user.status == UserStatus.PENDING
    assert user.id is not None
