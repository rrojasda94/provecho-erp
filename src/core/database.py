from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config.settings import settings

# Nombres deterministas de constraints — necesarios para que las
# migraciones Alembic puedan alterarlos/eliminarlos por nombre.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa compartida; cada módulo define sus modelos sobre ella."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


#: Segundos que se espera a que Postgres acepte la conexión. Sin límite, un
#: servidor que deja de responder —que no rechaza: acepta el TCP y se queda
#: callado— clava el request para siempre en `psycopg.wait_conn`, y el ERP no
#: da error sino que se queda mudo. En caja, mudo es peor que roto.
CONNECT_TIMEOUT_SEGUNDOS = 5


def connect_args(url: str, *, statement_timeout_segundos: int) -> dict:
    """`connect_timeout` y `options` son de libpq: solo van en Postgres.

    El `e2e` levanta la API contra un SQLite desechable y su driver no
    entiende ninguna de las dos — pasárselas revienta el arranque, así que
    fuera de Postgres el plazo simplemente no existe (SQLite tampoco sabe
    cancelar una consulta por tiempo).

    El plazo se pide por nombre y sin valor por defecto: quien abre un engine
    tiene que decir si es de operación o de reportes, que es justamente la
    decisión que este cambio existe para no dejar implícita.
    """
    if not url.startswith("postgresql"):
        return {}
    return {
        "connect_timeout": CONNECT_TIMEOUT_SEGUNDOS,
        # Milisegundos: la unidad de `statement_timeout` en Postgres. El 0 que
        # deja pasar `settings` significa "sin límite" también acá.
        "options": f"-c statement_timeout={statement_timeout_segundos * 1000}",
    }


def _crear_engine(statement_timeout_segundos: int):
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args=connect_args(
            settings.database_url,
            statement_timeout_segundos=statement_timeout_segundos,
        ),
    )


#: El engine de todo el ERP. Plazo corto: una consulta de caja que tarda más
#: que esto no está lenta, está trabada, y en el mostrador un error se maneja
#: mejor que una pantalla que no vuelve.
engine = _crear_engine(settings.db_statement_timeout_segundos)

#: El engine de los reportes (`src/core/reportes/` y el módulo `reports`).
#: Mismo destino, plazo largo: un reporte que cruza tres meses de ventas
#: tarda de verdad, y matarlo con el plazo del cobro sería romper un reporte
#: sano. Cuesta un pool de conexiones aparte —el precio de que una consulta
#: pesada tampoco se coma las conexiones que necesita la caja.
engine_reportes = _crear_engine(settings.db_statement_timeout_reportes_segundos)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
SessionReportes = sessionmaker(
    bind=engine_reportes, autoflush=False, expire_on_commit=False
)
