from decimal import Decimal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

JWT_SECRET_MIN_LEN = 32
_PLACEHOLDER_SECRETO = "change-me"
_PASSWORD_DB_POR_DEFECTO = "provecho:provecho@"


class Settings(BaseSettings):
    """Configuración de la aplicación, leída de variables de entorno y .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "provecho"
    environment: str = "local"
    debug: bool = False
    database_url: str = "postgresql+psycopg://provecho:provecho@localhost:5432/provecho"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = _PLACEHOLDER_SECRETO
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    # Endurecimiento HTTP. Listas en .env separadas por coma.
    allowed_hosts: list[str] = ["*"]
    cors_origins: list[str] = ["http://localhost:3000"]
    hsts_max_age_segundos: int = 31536000  # 1 año; solo se emite en producción
    # Rate limit por IP del login (el lockout de `usuario` es por cuenta y no
    # frena un ataque que rota usernames desde la misma IP).
    rate_limit_login_intentos: int = 10
    rate_limit_login_ventana_segundos: int = 60
    # Monto sobre el cual emitir una OC exige permiso purchases.aprobar
    # (RN-CMP — umbral configurable, valor semilla a ajustar por el negocio).
    purchases_umbral_aprobacion_oc: Decimal = Decimal("2000")
    # Tarifa única de mano de obra para costeo de producción (RN-PRD-018)
    # — valor semilla, ajustar cuando el negocio defina la tarifa real.
    production_costo_hora_mano_obra: Decimal = Decimal("15.00")
    # Monto sobre el cual ejecutar un pago a proveedor exige permiso
    # accounting.pago_aprobar (RN-CTB-005) — valor semilla.
    accounting_umbral_aprobacion_pago: Decimal = Decimal("2000")
    # RMV vigente (RN-PER-001: subvención de practicante no menor a 1 RMV
    # con jornada máxima) — valor semilla, ajustar según MTPE.
    rrhh_rmv_vigente: Decimal = Decimal("1130")
    # Facturación electrónica (Factiliza → SUNAT). Por defecto apunta al
    # entorno QA: emitir contra producción exige cambiar la URL a conciencia.
    factiliza_base_url: str = "https://apife-qa.factiliza.com/api/v1"
    factiliza_token: str = ""
    factiliza_timeout_segundos: float = 30.0
    igv_porcentaje: Decimal = Decimal("18")
    # Cola de emisión de comprobantes (Celery). Por defecto reusa Redis.
    celery_broker_url: str = ""
    # --- Observabilidad -----------------------------------------------------
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    # JSON siempre en producción; acá se fuerza también fuera de ella.
    log_json: bool = False
    # Vacío = sin reporte de errores (local y tests no envían nada).
    # Compatible con Sentry y con GlitchTip autoalojado.
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0
    # Tareas encoladas a partir de las cuales se reporta la cola atascada
    # (la de comprobantes se vacía sola; si crece, el worker murió).
    health_cola_maxima: int = 100
    # Horas sin backup a partir de las cuales el chequeo pasa a `caido`.
    # 26 y no 24: deja margen para que el cron diario corra sin falsa alarma.
    health_backup_max_horas: int = 26
    # --- Backups ------------------------------------------------------------
    backup_dir: str = "backups"
    backup_retencion_dias: int = 30
    # DSN de una base DESECHABLE donde probar la restauración. El backup que
    # nunca se restauró no es un backup; sin esto solo se valida el archivo.
    backup_verify_database_url: str = ""
    # Copia fuera del servidor (S3 o compatible). Sin credenciales, el
    # backup queda solo en disco local y se avisa.
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def es_produccion(self) -> bool:
        return self.environment.lower() in {"production", "produccion", "prod"}

    @field_validator("allowed_hosts", "cors_origins", mode="before")
    @classmethod
    def _lista_por_comas(cls, valor: object) -> object:
        """Acepta `a,b` en .env además de la lista JSON de pydantic."""
        if isinstance(valor, str):
            return [item.strip() for item in valor.split(",") if item.strip()]
        return valor

    @model_validator(mode="after")
    def _exigir_endurecimiento_en_produccion(self) -> "Settings":
        """Falla al arrancar si producción quedó con valores de desarrollo.
        Un ERP que bootea con `JWT_SECRET=change-me` es un ERP sin auth."""
        if not self.es_produccion:
            return self
        fallas = []
        if self.jwt_secret == _PLACEHOLDER_SECRETO:
            fallas.append("JWT_SECRET sigue siendo el placeholder")
        elif len(self.jwt_secret) < JWT_SECRET_MIN_LEN:
            fallas.append(f"JWT_SECRET debe tener al menos {JWT_SECRET_MIN_LEN} caracteres")
        if self.debug:
            fallas.append("DEBUG debe ser false")
        if _PASSWORD_DB_POR_DEFECTO in self.database_url:
            fallas.append("DATABASE_URL usa la contraseña por defecto")
        if "*" in self.allowed_hosts:
            fallas.append("ALLOWED_HOSTS no puede ser '*'")
        if "*" in self.cors_origins:
            fallas.append("CORS_ORIGINS no puede ser '*'")
        if fallas:
            raise ValueError(
                "Configuración insegura para ENVIRONMENT=production: " + "; ".join(fallas)
            )
        return self


settings = Settings()
