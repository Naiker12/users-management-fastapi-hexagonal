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
    brevo_base_url: str = "https://api.brevo.com"
    brevo_api_key: str = ""
    brevo_from_address: str = ""
    brevo_from_name: str = "Gestion de Usuarios"
    brevo_connect_timeout: float = 2.0
    brevo_read_timeout: float = 5.0
    brevo_retry_max_attempts: int = 3
    brevo_retry_initial_delay: float = 0.5
    brevo_retry_multiplier: float = 2.0
    brevo_circuit_failure_threshold: float = 50.0
    brevo_circuit_window_size: int = 10
    brevo_circuit_minimum_calls: int = 5
    brevo_circuit_open_duration: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
