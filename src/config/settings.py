from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación, leída de variables de entorno y .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "provecho"
    environment: str = "local"
    debug: bool = False
    database_url: str = "postgresql+psycopg://provecho:provecho@localhost:5432/provecho"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7


settings = Settings()
