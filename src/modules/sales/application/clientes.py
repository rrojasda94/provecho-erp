"""Alta y búsqueda de cliente desde el punto de venta (PROC-COM-002).

Registrar es opcional: vender a cliente anónimo siempre es válido
(RN-PER-005). Se registra cuando el cliente quiere factura, delivery a su
dirección, o acumular puntos.

**Qué se exige según el caso (RN-PTS-002):**

- *Persona natural*: basta el **teléfono**. Mucha gente no quiere dar su
  DNI en el mostrador, y negarse a registrarla por eso pierde al cliente.
  El documento se completa después con `actualizar_documento`.
- *Empresa (factura)*: el **RUC es obligatorio**. Sin él no hay factura.

Un cliente sin documento (o con el genérico `00000000`) queda **fuera de
las promociones para clientes registrados con documento**: existe, compra y
recibe su comprobante, pero `rules.cliente_identificado` lo deja afuera del
programa. El nombre y los datos siguen viviendo en `persona`, fuente única
(RN-GEN-007) — no se duplican en `cliente`.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Cliente
from src.modules.sales.infrastructure.repositories import ClienteRepo
from src.modules.users.infrastructure.models import Empresa, Persona
from src.shared.integrations.factiliza import nombres_desde_dni, razon_social_desde_ruc

TIPOS_DOCUMENTO_NATURAL = ("dni", "ce", "pasaporte")


def grupo_de_empresa(session: Session, empresa_id: uuid.UUID) -> uuid.UUID:
    """El cliente es del grupo, no de la empresa (RN-PTS-001). El PDV solo
    conoce su empresa, así que el grupo se deriva acá y nunca llega desde el
    request: un `grupo_id` de cliente permitiría escribir en otro tenant."""
    empresa = session.get(Empresa, empresa_id)
    if empresa is None:
        raise NoEncontrado("empresa no encontrada")
    return empresa.grupo_id


def _partir_nombre(nombre: str) -> tuple[str, str]:
    """`persona` guarda nombres y apellidos por separado; en caja se teclea
    todo junto. Sin apellido se usa `-`, no una cadena vacía, para que el
    nombre impreso en el comprobante no quede con un espacio colgando."""
    nombres, _, apellidos = nombre.strip().partition(" ")
    return nombres, (apellidos.strip() or "-")


def _persona_por_documento(session: Session, numero_documento: str) -> Persona | None:
    return session.scalar(
        select(Persona).where(Persona.numero_documento == numero_documento)
    )


def _completar_persona(
    persona: Persona,
    telefono: str | None,
    direccion: str | None,
    fecha_nacimiento: date | None,
    ubicacion: dict | None = None,
) -> None:
    """Rellena solo lo que falte: la persona ya existía por otro motivo
    (trabajador, otro registro) y no se pisa lo que ya dio."""
    if telefono and not persona.telefono:
        persona.telefono = telefono
    if direccion and not persona.domicilio:
        persona.domicilio = direccion
    if fecha_nacimiento and not persona.fecha_nacimiento:
        persona.fecha_nacimiento = fecha_nacimiento
    # La ubicación se escribe solo si vino la dirección con ella: anclar
    # un punto sin haber tocado el texto dejaría los dos contando
    # historias distintas.
    if direccion and ubicacion and not persona.ubicacion_place_id:
        for campo, valor in ubicacion.items():
            setattr(persona, campo, valor)


def crear_cliente(
    session: Session,
    *,
    grupo_id: uuid.UUID,
    nombre: str,
    telefono: str | None = None,
    numero_documento: str | None = None,
    email: str | None = None,
    direccion: str | None = None,
    fecha_nacimiento: date | None = None,
    tipo_documento: str = "dni",
    ubicacion_place_id: str | None = None,
    ubicacion_lat: Decimal | None = None,
    ubicacion_lng: Decimal | None = None,
    ubicacion_plus_code: str | None = None,
    ubicacion_distrito: str | None = None,
    consultar_documento: bool = True,
) -> Cliente:
    """RUC de 11 dígitos crea un cliente jurídico; el resto, uno natural con
    su `persona`. El tipo NO se pide al cajero: lo decide el documento,
    igual que el tipo de comprobante (RN-CPP-003).

    `consultar_documento=False` salta la consulta a SUNAT/RENIEC y usa el
    nombre tal cual viene. Lo usa la carga masiva (ADR-052): una planilla de
    trescientos clientes serían trescientas llamadas externas secuenciales
    dentro de un solo request, contra una cuota. Cuando el cliente se edita de
    a uno, SUNAT vuelve a mandar.
    """
    ubicacion = {
        "ubicacion_place_id": ubicacion_place_id,
        "ubicacion_lat": ubicacion_lat,
        "ubicacion_lng": ubicacion_lng,
        "ubicacion_plus_code": ubicacion_plus_code,
        "ubicacion_distrito": ubicacion_distrito,
    }
    nombre = (nombre or "").strip()
    telefono = (telefono or "").strip() or None
    numero_documento = (numero_documento or "").strip() or None
    if not nombre:
        raise ReglaNegocio("el cliente necesita nombre o razón social")
    if numero_documento and not rules.documento_receptor_valido(numero_documento):
        raise ReglaNegocio("el documento debe tener 8 dígitos (DNI) u 11 (RUC)")

    repo = ClienteRepo(session)
    if numero_documento and len(numero_documento) == rules.LARGO_RUC:
        # Sin `ubicacion`: el cliente jurídico no tiene columna de
        # dirección —hoy termina en `contacto`— y por lo tanto tampoco
        # dónde anclarla. Queda anotado en la deuda del ROADMAP.
        return _crear_juridico(
            repo,
            grupo_id,
            nombre,
            numero_documento,
            direccion,
            telefono,
            consultar_documento,
        )

    # Natural: el teléfono sustituye al documento como forma de encontrarlo
    # después. Sin ninguno de los dos el registro no sirve para nada.
    if not telefono:
        raise ReglaNegocio(
            "un cliente sin documento necesita teléfono para poder identificarlo"
        )
    if tipo_documento not in TIPOS_DOCUMENTO_NATURAL:
        raise ReglaNegocio(f"tipo de documento inválido: {tipo_documento}")

    persona = _persona_por_documento(session, numero_documento) if numero_documento else None
    if persona is None:
        nombres, apellidos = _partir_nombre(nombre)
        if (
            consultar_documento
            and numero_documento
            and len(numero_documento) == rules.LARGO_DNI
        ):
            nombres, apellidos = nombres_desde_dni(numero_documento, nombres, apellidos)
        persona = Persona(
            nombres=nombres,
            apellidos=apellidos,
            # `00000000` es "sin documento", no un documento: se guarda NULL
            # para no chocar contra el UNIQUE con el siguiente anónimo.
            tipo_documento=tipo_documento if rules.cliente_identificado(numero_documento) else None,
            numero_documento=(
                numero_documento if rules.cliente_identificado(numero_documento) else None
            ),
            telefono=telefono,
            email=email,
            domicilio=direccion,
            fecha_nacimiento=fecha_nacimiento,
            **ubicacion,
        )
        session.add(persona)
        session.flush()
    else:
        # `persona` es única por documento y la comparten users/rrhh: si ya
        # existe (un trabajador que compra, por ejemplo) se reutiliza en vez
        # de duplicarla, y se completa lo que le falte.
        _completar_persona(
            persona, telefono, direccion, fecha_nacimiento, ubicacion
        )
        existente = repo.por_persona(grupo_id, persona.id)
        if existente is not None:
            raise Conflicto("esa persona ya está registrada como cliente")

    return repo.add(
        Cliente(grupo_id=grupo_id, tipo="natural", persona_id=persona.id)
    )


def _crear_juridico(
    repo: ClienteRepo,
    grupo_id: uuid.UUID,
    razon_social: str,
    ruc: str,
    direccion: str | None,
    telefono: str | None,
    consultar_documento: bool = True,
) -> Cliente:
    existente = repo.por_ruc(grupo_id, ruc)
    if existente is not None:
        raise Conflicto(f"ya existe un cliente con RUC {ruc}")
    if consultar_documento:
        razon_social = razon_social_desde_ruc(ruc, razon_social)
    return repo.add(
        Cliente(
            grupo_id=grupo_id,
            tipo="juridico",
            razon_social=razon_social,
            ruc=ruc,
            contacto=direccion or telefono,
        )
    )


def actualizar_documento(
    session: Session,
    *,
    cliente_id: uuid.UUID,
    numero_documento: str,
    tipo_documento: str = "dni",
) -> Cliente:
    """Completa el documento de un cliente registrado solo por teléfono.

    Es el camino normal, no una excepción: el cliente da su DNI cuando le
    conviene (una factura, entrar al programa de puntos) y desde ese momento
    cuenta como identificado (RN-PTS-002).
    """
    cliente = ClienteRepo(session).get(cliente_id)
    if cliente is None or cliente.deleted_at is not None:
        raise NoEncontrado("cliente no encontrado")
    numero_documento = (numero_documento or "").strip()
    if not rules.cliente_identificado(numero_documento):
        raise ReglaNegocio("el documento no puede ser vacío ni el genérico 00000000")
    if not rules.documento_receptor_valido(numero_documento):
        raise ReglaNegocio("el documento debe tener 8 dígitos (DNI) u 11 (RUC)")

    if cliente.tipo == "juridico":
        if len(numero_documento) != rules.LARGO_RUC:
            raise ReglaNegocio("un cliente jurídico se identifica con RUC (11 dígitos)")
        cliente.ruc = numero_documento
        return cliente

    if tipo_documento not in TIPOS_DOCUMENTO_NATURAL:
        raise ReglaNegocio(f"tipo de documento inválido: {tipo_documento}")
    ajeno = _persona_por_documento(session, numero_documento)
    if ajeno is not None and ajeno.id != cliente.persona_id:
        raise Conflicto(f"el documento {numero_documento} ya pertenece a otra persona")
    persona = session.get(Persona, cliente.persona_id)
    if persona is None:
        raise NoEncontrado("la persona del cliente no existe")
    persona.numero_documento = numero_documento
    persona.tipo_documento = tipo_documento
    return cliente


def editar_cliente(
    session: Session,
    cliente_id: uuid.UUID,
    *,
    consultar_documento: bool = True,
    **campos,
) -> Cliente:
    """Corrige un cliente **jurídico**. Campo `None` = no tocar.

    Solo jurídico porque es lo único que `cliente` guarda por su cuenta: en
    uno natural el nombre, el teléfono, el documento y la dirección viven en
    su `persona` (RN-GEN-007, fuente única) y se corrigen desde ahí. Duplicar
    esos campos acá sería crear la segunda fuente que esa regla existe para
    evitar.

    El documento tiene su propio caso de uso (`actualizar_documento`), que
    aplica las reglas de identificación; este no lo toca.
    """
    repo = ClienteRepo(session)
    cliente = repo.get(cliente_id)
    if cliente is None or cliente.deleted_at is not None:
        raise NoEncontrado("cliente no encontrado")
    if cliente.tipo != "juridico":
        raise ReglaNegocio(
            "los datos de un cliente natural viven en su persona "
            "(RN-GEN-007): se corrigen desde Personas"
        )

    ruc = (campos.get("ruc") or "").strip()
    if ruc:
        if len(ruc) != rules.LARGO_RUC or not ruc.isdigit():
            raise ReglaNegocio("un cliente jurídico se identifica con RUC (11 dígitos)")
        ajeno = repo.por_ruc(cliente.grupo_id, ruc)
        if ajeno is not None and ajeno.id != cliente.id:
            raise Conflicto(f"ya existe un cliente con RUC {ruc}")
        cliente.ruc = ruc

    razon_social = (campos.get("razon_social") or "").strip()
    if razon_social:
        cliente.razon_social = razon_social
    if campos.get("contacto") is not None:
        cliente.contacto = campos["contacto"].strip() or None
    # Mismo criterio que el alta: SUNAT manda sobre lo tecleado — salvo en la
    # carga masiva, que no puede consultar una vez por fila (ADR-052).
    if consultar_documento and (ruc or razon_social):
        cliente.razon_social = razon_social_desde_ruc(cliente.ruc, cliente.razon_social)
    return cliente


def q_listado(session: Session, *, grupo_id: uuid.UUID, q: str | None = None):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026).

    Es la misma de `buscar` sin el `LIMIT`: la caja pide las primeras 20
    coincidencias y el back-office pagina el padrón entero, pero *qué* es un
    cliente del grupo y por qué campos se lo encuentra tiene que ser una sola
    definición — si no, la pantalla y la caja terminan mostrando universos
    distintos.
    """
    consulta = (
        select(Cliente)
        .outerjoin(Persona, Persona.id == Cliente.persona_id)
        .where(Cliente.grupo_id == grupo_id, Cliente.deleted_at.is_(None))
    )
    q = (q or "").strip()
    if q:
        patron = f"%{q}%"
        consulta = consulta.where(
            or_(
                Persona.telefono.ilike(patron),
                Persona.numero_documento.ilike(patron),
                Persona.nombres.ilike(patron),
                Persona.apellidos.ilike(patron),
                Cliente.razon_social.ilike(patron),
                Cliente.ruc.ilike(patron),
            )
        )
    return consulta.order_by(Cliente.created_at.desc())


def personas_de(
    session: Session, clientes_: list[Cliente]
) -> dict[uuid.UUID, Persona]:
    """Las personas de una página de clientes, en una consulta.

    `q_listado` devuelve `Cliente` a secas porque `paginar` sabe contar y
    cortar un `Select` de una entidad, no de dos. Resolver la persona acá
    cuesta una consulta por página; hacerlo fila por fila costaría N.
    """
    ids = {c.persona_id for c in clientes_ if c.persona_id is not None}
    if not ids:
        return {}
    return {
        p.id: p for p in session.scalars(select(Persona).where(Persona.id.in_(ids)))
    }


def buscar(
    session: Session, *, grupo_id: uuid.UUID, q: str, limite: int = 20
) -> list[tuple[Cliente, Persona | None]]:
    """Busca por teléfono, documento o nombre — en caja se pregunta lo que
    el cliente recuerde. Devuelve el cliente junto a su persona para que el
    llamador arme el nombre sin volver a consultar."""
    if not (q or "").strip():
        return []
    encontrados = list(
        session.scalars(q_listado(session, grupo_id=grupo_id, q=q).limit(limite))
    )
    personas = personas_de(session, encontrados)
    return [(c, personas.get(c.persona_id)) for c in encontrados]
