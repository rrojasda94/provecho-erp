"""Terminales de marcaje: alta, código de activación, enrolamiento, revocación.

El admin crea el registro desde el back-office (nace inactivo, con un
código de 6 dígitos vigente 30 minutos) y la tablet lo teclea una vez en el
pad para quedar enrolada. De ahí en más, cada marcación manda el secreto
del terminal; el router la rechaza sin uno válido de esa sucursal
(RN-RRHH-023, ADR-079).

El secreto es aleatorio, no una contraseña humana, así que se hashea con
SHA-256 y no Argon2id — mismo criterio que `TokenAgente`
(`src/modules/users/infrastructure/models/token_agente.py`). No se importa
esa utilidad del módulo `users`: es infraestructura interna de otro módulo
y los módulos no se prestan el uno al otro (CLAUDE.md), así que el hash se
recalcula acá con las mismas cuatro líneas.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import Conflicto, NoEncontrado
from src.modules.rrhh.infrastructure.models import TerminalMarcaje
from src.modules.rrhh.infrastructure.repositories import TerminalMarcajeRepo
from src.modules.users.infrastructure.models import Sucursal

CODIGO_VIGENCIA = timedelta(minutes=30)


def _hash(secreto: str) -> str:
    return hashlib.sha256(secreto.encode()).hexdigest()


def _nuevo_codigo() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def crear(session: Session, *, sucursal_id: uuid.UUID, nombre: str) -> tuple[TerminalMarcaje, str]:
    """Da de alta un terminal inactivo y devuelve `(fila, código)`.

    El código se muestra una sola vez, en el momento de crear — igual que
    el token de un agente: perderlo no es grave, se puede pedir uno nuevo.
    """
    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None:
        raise NoEncontrado(f"sucursal {sucursal_id} no encontrada")
    repo = TerminalMarcajeRepo(session)
    if repo.por_nombre(sucursal_id, nombre) is not None:
        raise Conflicto(f"la sucursal ya tiene un terminal '{nombre}'")

    codigo = _nuevo_codigo()
    terminal = repo.add(
        TerminalMarcaje(
            sucursal_id=sucursal_id,
            nombre=nombre,
            codigo=codigo,
            codigo_expira_en=datetime.now(UTC) + CODIGO_VIGENCIA,
            activo=False,
        )
    )
    return terminal, codigo


def listar(session: Session, sucursal_id: uuid.UUID) -> list[TerminalMarcaje]:
    return TerminalMarcajeRepo(session).list_de_sucursal(sucursal_id)


def revocar(session: Session, terminal_id: uuid.UUID) -> None:
    """Apaga el terminal: borrado lógico, libera el nombre para otra tablet.

    No hace falta más: sin fila viva no hay `secreto_hash` que resuelva, así
    que el siguiente marcaje desde esa tablet cae directo al 403.
    """
    terminal = TerminalMarcajeRepo(session).get(terminal_id)
    if terminal is None:
        raise NoEncontrado("terminal no encontrado")
    terminal.deleted_at = datetime.now(UTC)


def enrolar(session: Session, *, sucursal_id: uuid.UUID, codigo: str) -> str:
    """Valida el código y devuelve el secreto en claro (una sola vez).

    El código vencido o ya usado da el mismo error: distinguirlos solo le
    diría a quien está probando códigos al azar cuál sigue vigente.
    """
    repo = TerminalMarcajeRepo(session)
    terminal = repo.get_por_codigo(sucursal_id, codigo)
    ahora = datetime.now(UTC)
    expira = terminal.codigo_expira_en if terminal else None
    if expira is not None and expira.tzinfo is None:
        expira = expira.replace(tzinfo=UTC)  # SQLite devuelve naive.
    if terminal is None or expira is None or expira <= ahora:
        raise Conflicto("código inválido o vencido")

    secreto = secrets.token_urlsafe(32)
    terminal.secreto_hash = _hash(secreto)
    terminal.codigo = None
    terminal.codigo_expira_en = None
    terminal.activo = True
    return secreto


def resolver_terminal(
    session: Session, secreto: str, sucursal_id: uuid.UUID
) -> TerminalMarcaje | None:
    """El terminal activo dueño de este secreto, para esta sucursal, o
    `None`.

    Devuelve `None` en vez de lanzar: un secreto de otra sucursal falla
    igual que uno inexistente (403, no 404 — el router decide el código,
    mismo criterio que `pad_asistencia.sucursal_de` para el trabajador),
    y distinguir los dos motivos solo le serviría a quien está probando
    secretos al azar.
    """
    terminal = TerminalMarcajeRepo(session).get_por_secreto_hash(_hash(secreto))
    if terminal is None or not terminal.activo or terminal.sucursal_id != sucursal_id:
        return None
    return terminal
