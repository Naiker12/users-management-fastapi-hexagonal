"""Read-only deployment diagnostic; never prints passwords or connection URIs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from users_management.config import get_settings
from users_management.infrastructure import make_engine


def main():
    settings = get_settings()
    print(f"Host: {settings.db_host}; puerto: {settings.db_port}")
    print(f"Usuario: {settings.db_username}; SSL: {settings.db_ssl_mode}")
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            print("Conexion PostgreSQL: OK")
            exists = connection.execute(text(
                "SELECT to_regclass('crud_usuarios.users') IS NOT NULL"
            )).scalar()
            if not exists:
                raise SystemExit("Falta crud_usuarios.users: ejecutar db/schema.sql.")
            count = connection.execute(text(
                "SELECT count(*) FROM crud_usuarios.users "
                "WHERE role='ADMIN' AND status='ACTIVE'"
            )).scalar()
            print(f"Tabla: OK; administradores activos: {count}")
    except SQLAlchemyError as exc:
        reason = str(getattr(exc, "orig", exc)).lower()
        if "enoidentifier" in reason:
            message = "El pooler no recibe tenant: revisar DB_USERNAME postgres.<project-ref>."
        elif "password authentication failed" in reason:
            message = "Supabase rechazo DB_PASSWORD."
        else:
            message = f"Fallo de conexion ({type(exc).__name__}); revisar logs del servidor."
        raise SystemExit(message) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
