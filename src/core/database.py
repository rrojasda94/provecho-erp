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


def connect_args(url: str) -> dict:
    """`connect_timeout` es parámetro de libpq: solo va en Postgres.

    El `e2e` levanta la API contra un SQLite desechable y su driver no
    entiende la opción — pasársela revienta el arranque.
    """
    return {"connect_timeout": CONNECT_TIMEOUT_SEGUNDOS} if url.startswith("postgresql") else {}


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args(settings.database_url),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
