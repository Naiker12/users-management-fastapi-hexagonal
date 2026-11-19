from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = 8080
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "postgres"
    db_username: str = "postgres"
    db_password: str = ""
    db_ssl_mode: str = "disable"
    db_schema: str = "crud_usuarios"
    jwt_secret: str = ""
    jwt_expiration_seconds: int = 900
    admin_email: str = "admin@example.com"
    admin_password: str = ""
    email_provider: str = "console"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_from_name: str = "Gestion de Usuarios"


@lru_cache
def get_settings() -> Settings:
    return Settings()
