import tomllib
from datetime import date
from decimal import Decimal
from importlib import metadata
from pathlib import Path
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

JWT_SECRET_MIN_LEN = 32
_PLACEHOLDER_SECRETO = "change-me"
_PASSWORD_DB_POR_DEFECTO = "provecho:provecho@"
#: Cuando se corre desde el fuente sin instalar el paquete (no pasa ni en la
#: imagen ni con `pip install -e ".[dev]"`, que es el primer paso del README).
_VERSION_DESCONOCIDA = "0.0.0"

#: `src/config/settings.py` → la raíz del repo. En la imagen es `/app`, donde
#: el `Dockerfile` copia el `pyproject.toml` junto al código.
_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _version_del_pyproject() -> str | None:
    """El archivo del checkout, que es el que `cortar_version.py` mueve."""
    try:
        with _PYPROJECT.open("rb") as archivo:
            return tomllib.load(archivo)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return None


def _version_del_paquete() -> str:
    """La versión sale de `pyproject.toml`. Tenerla escrita a mano acá fue lo
    que la dejó cuatro releases atrás: `cortar_version.py` movía el CHANGELOG
    y el tag, y este literal no se enteraba.

    **El archivo manda sobre la metadata del paquete instalado**, y no al
    revés, porque en un `pip install -e .` esa metadata se escribe una sola
    vez: el código queda en vivo y la versión no. En una máquina de desarrollo
    eso significa reportar la versión de la rama que estaba abierta el día que
    se instaló —y como `openapi.json` se regenera con esta versión adentro y
    el CI lo compara con `git diff --exit-code`, el contrato se ensucia sin
    que nadie haya tocado un endpoint—. La imagen y CI instalan de cero en
    cada corrida, así que para ellos las dos fuentes dicen lo mismo.

    La metadata queda de respaldo para la instalación no editable, donde el
    paquete vive en `site-packages` y no hay `pyproject.toml` al lado.
    """
    del_archivo = _version_del_pyproject()
    if del_archivo is not None:
        return del_archivo
    try:
        return metadata.version("provecho")
    except metadata.PackageNotFoundError:
        return _VERSION_DESCONOCIDA


class Settings(BaseSettings):
    """Configuración de la aplicación, leída de variables de entorno y .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "provecho"
    environment: str = "local"
    debug: bool = False
    database_url: str = "postgresql+psycopg://provecho:provecho@localhost:5432/provecho"
    # Cuánto deja correr Postgres una consulta antes de cancelarla. Dos plazos
    # y no uno: el cobro de una mesa y un reporte de márgenes del trimestre no
    # aguantan la misma espera, y con un solo número había que elegir entre
    # matar reportes legítimos o dejar la caja colgada. 0 = sin límite.
    db_statement_timeout_segundos: int = 15
    db_statement_timeout_reportes_segundos: int = 120
    # Zona del negocio, no la del servidor: de ella sale "qué día es hoy"
    # para el ERP (`src/shared/fechas.py`). En Docker el sistema corre en UTC,
    # y con eso un cierre de las 20:00 hora Perú caía al día siguiente.
    zona_horaria: str = "America/Lima"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = _PLACEHOLDER_SECRETO
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    # Cuánto puede estar quieta una sesión antes de darse por cerrada
    # (ADR-084). El plazo del refresh es el techo absoluto; esto es el de
    # inactividad, y es el que corta la sesión de una PC que se apagó.
    #
    # Ocho horas y no dos: entre almuerzo y cena una caja puede quedarse sin
    # tocar media tarde, y hacerla volver a entrar ahí es exactamente el
    # problema que ADR-073 vino a arreglar. Un turno completo cabe; una noche,
    # no.
    refresh_inactividad_horas: int = 8
    # Endurecimiento HTTP. Listas en .env separadas por coma.
    #
    # `NoDecode` es lo que hace que esa promesa se cumpla: sin él,
    # pydantic-settings intenta decodificar como JSON todo campo de tipo
    # complejo **antes** de que corra ningún validador, así que
    # `ALLOWED_HOSTS=*` —la línea que trae `.env.example`— reventaba el
    # arranque con `SettingsError` y `_lista_por_comas` no llegaba a ejecutarse
    # nunca. Con `NoDecode` el valor llega crudo al validador de abajo, que es
    # donde siempre se pretendió resolver el formato.
    allowed_hosts: Annotated[list[str], NoDecode] = ["*"]
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    hsts_max_age_segundos: int = 31536000  # 1 año; solo se emite en producción
    # Rate limit por IP del login (el lockout de `usuario` es por cuenta y no
    # frena un ataque que rota usernames desde la misma IP).
    rate_limit_login_intentos: int = 10
    rate_limit_login_ventana_segundos: int = 60
    # Rate limit de la consulta de DNI/RUC (ADR-041). Cada llamada gasta cuota
    # de un proveedor **pago** y trae datos personales de alguien que todavía
    # no es nadie en el sistema, así que el límite no es contra el abuso sino
    # contra el gasto: un bucle mal escrito en una pantalla agota el plan del
    # mes. Dos cuentas y una sola ventana: la del usuario es la que de verdad
    # frena a quien se pasa, la de la IP es el techo del local entero —todas
    # las cajas salen por la misma, y limitar solo por IP dejaría al equipo
    # sin consultar por culpa de uno—.
    consulta_documento_intentos_usuario: int = 20
    consulta_documento_intentos_ip: int = 60
    consulta_documento_ventana_segundos: int = 60
    # Monto sobre el cual emitir una OC exige permiso purchases.aprobar
    # (RN-CMP — umbral configurable, valor semilla a ajustar por el negocio).
    purchases_umbral_aprobacion_oc: Decimal = Decimal("2000")
    # Margen de error tolerado en el ajuste que sale de un conteo, en % del
    # stock esperado (RN-INV-015). Fuera de margen no bloquea el ajuste:
    # lo marca para investigación y dispara la alerta de auditoría.
    inventory_margen_ajuste_pct: Decimal = Decimal("2")
    # Tarifa única de mano de obra para costeo de producción (RN-PRD-018)
    # — valor semilla, ajustar cuando el negocio defina la tarifa real.
    production_costo_hora_mano_obra: Decimal = Decimal("15.00")
    # Monto sobre el cual ejecutar un pago a proveedor exige permiso
    # accounting.pago_aprobar (RN-CTB-005) — valor semilla.
    accounting_umbral_aprobacion_pago: Decimal = Decimal("2000")
    # RMV vigente (RN-PER-001: subvención de practicante no menor a 1 RMV
    # con jornada máxima) — valor semilla, ajustar según MTPE.
    rrhh_rmv_vigente: Decimal = Decimal("1130")
    # Meses que se conservan los datos de un postulante no contratado
    # (RN-PER-004: no hay plazo legal fijo en Perú, lo declara el aviso de
    # privacidad). Se aplica al crear la ficha y lo barre la purga.
    rrhh_plazo_conservacion_postulante_meses: int = 12
    # Días que se conserva la foto de una marcación (RN-RRHH-024, ADR-079).
    # Pasado el plazo la purga borra solo `marcacion.foto`; la fila y el
    # resto de la evidencia (terminal, IP, distancia) se quedan.
    rrhh_marcaje_foto_retencion_dias: int = 90
    # Facturación electrónica (Factiliza → SUNAT). Por defecto apunta al
    # entorno QA: emitir contra producción exige cambiar la URL a conciencia.
    factiliza_base_url: str = "https://apife-qa.factiliza.com/api/v1"
    # Consulta RUC/DNI (RENIEC/SUNAT) — producto distinto de la emisión: host
    # propio (sin sandbox QA separado) **y token propio**. Se contrata y se
    # regenera por separado en el panel de Factiliza, así que el de emisión
    # devuelve 401 acá aunque sea válido — comprobado el 2026-08-22.
    factiliza_consulta_base_url: str = "https://api.factiliza.com/v1"
    factiliza_token: str = ""
    # Son dos productos contratados por separado y Factiliza entrega un token
    # por cada uno. Vacío = se reusa `factiliza_token`, que es lo correcto
    # cuando el plan contratado cubre ambos con una sola credencial. Tenerlo
    # aparte importa además para el día que uno se rote: rotar el de emisión
    # no debería apagar el buscador de DNI del mostrador.
    factiliza_consulta_documento_token: str = ""
    factiliza_timeout_segundos: float = 30.0
    # La consulta de documento se espera con un cajero mirando la pantalla y
    # el botón deshabilitado: medio minuto ahí es un cuelgue. La emisión sí
    # puede tardar (SUNAT de por medio) y corre en cola, por eso van
    # separados.
    factiliza_consulta_timeout_segundos: float = 8.0
    igv_porcentaje: Decimal = Decimal("18")
    # --- WhatsApp Cloud API (Meta) — encuesta de satisfacción ---------------
    whatsapp_base_url: str = "https://graph.facebook.com/v21.0"
    whatsapp_phone_number_id: str = ""
    whatsapp_token: str = ""
    # Token que Meta devuelve en el handshake `GET` del webhook.
    whatsapp_verify_token: str = ""
    # Secreto de la app: firma HMAC de cada webhook entrante. Sin él, el
    # webhook rechaza todo (fail-closed) — es la única prueba de que el
    # mensaje viene de Meta y no de alguien que descubrió la URL.
    whatsapp_app_secret: str = ""
    whatsapp_timeout_segundos: float = 15.0
    # Plantilla aprobada con la que se abre la conversación: fuera de la
    # ventana de 24 h, Meta no acepta otra cosa.
    whatsapp_plantilla_encuesta: str = "encuesta_satisfaccion"
    whatsapp_plantilla_idioma: str = "es"
    # --- Google Maps (direcciones y reparto) --------------------------------
    # Dos claves y no una porque Google no deja restringir la misma por
    # referente HTTP **y** por IP a la vez, y son dos usos con riesgos
    # distintos.
    #
    # La del navegador dibuja el mapa y autocompleta: viaja al cliente a
    # propósito, y lo único que la protege es la restricción por dominio más
    # la cuota diaria de la consola. Vacía = el campo de dirección se comporta
    # como el `<input>` de texto de siempre.
    google_maps_browser_key: str = ""
    # La del servidor calcula la distancia con la que se le cobra el delivery
    # al cliente. NUNCA sale de la API: un número que viaja por el navegador
    # es un número que se puede editar. Vacía = la distancia se estima en
    # línea recta y la cotización se marca aproximada.
    google_maps_server_key: str = ""
    # Map ID de la consola de Google: sin uno, el pin del mapa no se
    # dibuja. `DEMO_MAP_ID` es el que Google publica para desarrollo.
    google_maps_map_id: str = "DEMO_MAP_ID"
    google_routes_base_url: str = "https://routes.googleapis.com"
    google_timeout_segundos: float = 10.0
    # Sesga el autocompletado al país del negocio (ISO 3166-1 alfa-2).
    google_maps_pais: str = "pe"
    # --- Tarifa del delivery propio -----------------------------------------
    # Los tres en 0 = función apagada: el delivery se sigue cobrando como
    # hasta ahora hasta que el negocio defina la tarifa. Nada se enciende solo.
    delivery_tarifa_base: Decimal = Decimal("0")
    delivery_precio_por_km: Decimal = Decimal("0")
    # Pasado este radio se sugiere derivar a una plataforma externa en vez de
    # mandar al repartidor propio. 0 = sin radio máximo.
    delivery_distancia_maxima_km: Decimal = Decimal("0")
    # Distritos donde no se reparte con repartidor propio, separados por coma.
    # Es una lista de nombres y no un polígono a propósito: el distrito ya
    # viene en la respuesta de Google y resuelve el caso real sin traer
    # geometría (ni PostGIS) al proyecto.
    delivery_distritos_restringidos: Annotated[list[str], NoDecode] = []
    # --- Encuesta de satisfacción (marketing) --------------------------------
    # Vigencia de la encuesta enviada. Pasado el plazo, el barrido la expira:
    # una respuesta de dos semanas después no mide la experiencia de ese
    # pedido (RN-COM-007).
    marketing_encuesta_vigencia_horas: int = 72
    # Base pública del formulario de encuesta (canal `link` y el enlace que
    # viaja en el WhatsApp). Vacío = se envía solo el texto, sin enlace.
    marketing_url_publica: str = ""
    # --- Promoción de cupón «Queremos RE-conocerte» (ADR-061) ----------------
    # Valores con los que el seeder crea la campaña. Son semilla, no fuente de
    # verdad: una vez creada, la fila manda —terminarla es un `POST`, no un
    # despliegue— porque la empresa se reserva el derecho de cortarla en
    # cualquier momento y esperar un deploy para eso no sirve.
    sales_promocion_cupon_nombre: str = "Queremos RE-conocerte"
    sales_promocion_cupon_porcentaje: Decimal = Decimal("10")
    # Fin de campaña: «a finales de este año».
    sales_promocion_cupon_fin: date = date(2026, 12, 31)
    # Cada cupón vale un mes desde que se emite.
    sales_promocion_cupon_vigencia_dias: int = 30
    # Cola de emisión de comprobantes (Celery). Por defecto reusa Redis.
    celery_broker_url: str = ""
    # --- Observabilidad -----------------------------------------------------
    # No es un literal: quedó cuatro releases atrás (0.1.0 con el proyecto en
    # 0.5.0) porque nada lo movía, y con él se etiquetan los errores en
    # GlitchTip y la versión de `/docs`. Un `release` congelado hace inútil el
    # "apareció en la versión X" que es la mitad del valor de reportar errores.
    app_version: str = _version_del_paquete()
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
    # El worker anuncia su latido cada minuto (Celery beat) con este TTL.
    # 3× el intervalo: tolera un ciclo perdido sin declararlo muerto.
    health_latido_worker_ttl: int = 180
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
    # --- Modo offline del PDV (ADR-009) --------------------------------------
    # "cloud": la nube central. "hub": instancia local de sucursal — misma
    # imagen, Postgres propio, sincroniza con la nube cuando hay internet.
    deployment_mode: str = "cloud"
    # Requeridos solo si deployment_mode="hub".
    hub_empresa_id: str = ""
    hub_sucursal_id: str = ""
    # Base de la API en la nube contra la que este hub sincroniza.
    cloud_sync_url: str = ""
    # Credenciales de la cuenta de servicio (usuario.tipo=agente_ia) que el
    # hub usa para autenticarse contra la nube — login normal, sin endpoint
    # de auth nuevo.
    cloud_sync_username: str = ""
    cloud_sync_pin: str = ""
    sync_intervalo_segundos: int = 60
    # Filas por página de sync. Holgado a propósito: un bloque de filas con
    # el MISMO `updated_at` más grande que el lote obliga al motor a
    # ensanchar la página para no atascarse (`motor.FACTOR_DESEMPATE`).
    sync_lote_maximo: int = 500
    # Fallos de heartbeat seguidos antes de declarar al hub "offline" — uno
    # solo sería demasiado sensible a un timeout de red puntual.
    sync_fallos_para_offline: int = 3
    # --- OAuth2 para el BI (Superset, ADR-083) -------------------------------
    # Un solo cliente confidencial. Vacíos por defecto: sin `client_secret`
    # nadie puede canjear un código por token, así que un despliegue que
    # olvide configurarlos deja el SSO apagado en vez de abierto.
    oauth_bi_client_id: str = ""
    oauth_bi_client_secret: str = ""
    # Comparado por igualdad exacta contra el `redirect_uri` que manda
    # Superset — nunca por prefijo. Es la única defensa contra reenviar el
    # código de autorización a un destino que no sea Superset.
    oauth_bi_redirect_uri: str = ""
    # TTL del código de un solo uso y del access token, en Redis. El código
    # vive lo que tarda el navegador en rebotar de vuelta a Superset; el
    # token, lo que tarda Superset en llamar a `/oauth/userinfo` una vez —
    # ninguno de los dos se pensó para durar una sesión.
    oauth_bi_codigo_ttl_segundos: int = 60
    oauth_bi_token_ttl_segundos: int = 300
    # Cuenta de servicio de Superset (rol propio, sin `bi.acceder` ni
    # equivalente humano) que Provecho usa para pedir *guest tokens* y
    # embeber tableros en `/dashboard` (ADR-083 Fase D). Vacía = sin
    # embebido — el módulo BI sigue funcionando por SSO directo.
    superset_internal_url: str = ""
    superset_service_username: str = ""
    superset_service_password: str = ""
    # Whitelist de dashboards embebibles: aunque el guest token ya queda
    # acotado por la RLS del dataset (Fase C), no cualquier UUID que alguien
    # mande debe poder pedirse un token — solo los tableros que de verdad se
    # curaron para `/dashboard`. Vacía = ninguno todavía.
    bi_dashboards_embebibles: Annotated[list[str], NoDecode] = []

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def es_produccion(self) -> bool:
        return self.environment.lower() in {"production", "produccion", "prod"}

    @property
    def es_hub(self) -> bool:
        return self.deployment_mode == "hub"

    @field_validator(
        "allowed_hosts",
        "cors_origins",
        "delivery_distritos_restringidos",
        "bi_dashboards_embebibles",
        mode="before",
    )
    @classmethod
    def _lista_por_comas(cls, valor: object) -> object:
        """Acepta `a,b` en .env además de la lista JSON de pydantic.

        Con `NoDecode` en el campo, este validador es el **único** que ve el
        valor, así que también le toca el JSON que antes resolvía
        pydantic-settings. Se prueba JSON solo si la cadena parece una lista:
        un host que empiece con `[` no existe, y probar siempre dejaría un
        `try` alrededor del caso normal.
        """
        if not isinstance(valor, str):
            return valor
        texto = valor.strip()
        if texto.startswith("["):
            import json

            try:
                return json.loads(texto)
            except ValueError:
                pass
        return [item.strip() for item in texto.split(",") if item.strip()]

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
        if self.whatsapp_token and not self.whatsapp_app_secret:
            # El webhook es público: sin secreto no hay forma de distinguir a
            # Meta de cualquiera que descubra la URL. Con WhatsApp apagado no
            # aplica, por eso la condición y no un requisito suelto.
            fallas.append("WHATSAPP_APP_SECRET es obligatorio si hay WHATSAPP_TOKEN")
        if fallas:
            raise ValueError(
                "Configuración insegura para ENVIRONMENT=production: " + "; ".join(fallas)
            )
        return self

    @model_validator(mode="after")
    def _exigir_config_de_hub(self) -> "Settings":
        """Un hub sin saber a qué sucursal pertenece o contra qué nube
        sincronizar arranca "bien" y falla en silencio recién al primer
        ciclo de sync — mejor que no arranque (ADR-009)."""
        if self.deployment_mode not in {"cloud", "hub"}:
            raise ValueError("DEPLOYMENT_MODE debe ser 'cloud' o 'hub'")
        if not self.es_hub:
            return self
        faltantes = [
            nombre
            for nombre, valor in (
                ("HUB_EMPRESA_ID", self.hub_empresa_id),
                ("HUB_SUCURSAL_ID", self.hub_sucursal_id),
                ("CLOUD_SYNC_URL", self.cloud_sync_url),
                ("CLOUD_SYNC_USERNAME", self.cloud_sync_username),
                ("CLOUD_SYNC_PIN", self.cloud_sync_pin),
            )
            if not valor
        ]
        if faltantes:
            raise ValueError(
                "DEPLOYMENT_MODE=hub requiere: " + ", ".join(faltantes)
            )
        return self


settings = Settings()
