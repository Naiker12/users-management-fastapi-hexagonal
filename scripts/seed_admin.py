import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from users_management.config import get_settings
from users_management.domain import User, UserRole, UserStatus
from users_management.infrastructure import Security, UserRepository, make_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea el administrador inicial en PostgreSQL.")
    parser.add_argument(
        "--prompt-db-password",
        action="store_true",
        help="Pide la contraseña de base de datos sin mostrarla ni guardarla en .env.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.admin_password or settings.admin_password == "REEMPLAZAR":
        raise SystemExit("Define ADMIN_PASSWORD en .env antes de crear el administrador.")
    if args.prompt_db_password:
        database_password = getpass.getpass("Contraseña de base de datos Supabase: ")
        if not database_password:
            raise SystemExit("La contraseña de base de datos no puede estar vacía.")
        settings = settings.model_copy(update={"db_password": database_password})

    engine = make_engine(settings)
    try:
        with Session(engine) as session:
            repository = UserRepository(session)
            email = User.normalize_email(settings.admin_email)
            if repository.by_email(email):
                print(f"El administrador {email} ya existe.")
                return
            user = User(name="Administrador", email=email,
                        password_hash=Security.hash_password(settings.admin_password),
                        role=UserRole.ADMIN, status=UserStatus.ACTIVE)
            repository.save(user)
            print(f"Administrador {email} creado.")
    except OperationalError as exc:
        if "password authentication failed" in str(exc).lower():
            raise SystemExit(
                "Supabase rechazó la contraseña de base de datos. Usa la Database password "
                "del proyecto (no la API key) y revisa que el usuario coincida con la cadena "
                "Session pooler."
            ) from None
        reason = str(getattr(exc, "orig", exc)).splitlines()[0]
        raise SystemExit(f"No se pudo conectar con Supabase: {reason}") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
