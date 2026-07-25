from decimal import Decimal

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
    # Monto sobre el cual emitir una OC exige permiso purchases.aprobar
    # (RN-CMP — umbral configurable, valor semilla a ajustar por el negocio).
    purchases_umbral_aprobacion_oc: Decimal = Decimal("2000")
    # Tarifa única de mano de obra para costeo de producción (RN-PRD-018)
    # — valor semilla, ajustar cuando el negocio defina la tarifa real.
    production_costo_hora_mano_obra: Decimal = Decimal("15.00")
    # Monto sobre el cual ejecutar un pago a proveedor exige permiso
    # accounting.pago_aprobar (RN-CTB-005) — valor semilla.
    accounting_umbral_aprobacion_pago: Decimal = Decimal("2000")


settings = Settings()
