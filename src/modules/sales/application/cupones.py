"""Cupón de promoción: emisión desde la landing pública y canje en caja.

Dos superficies muy distintas y un solo cupón entre las dos:

- **Emitir** lo hace el cliente, sin cuenta, desde su teléfono (ADR-059).
  Nadie lo autenticó, así que este archivo no confía en nada de lo que
  llega salvo el número que el cliente teclea, y no devuelve más que un
  booleano y el código que él mismo acaba de escribir.
- **Canjear** lo hace el cajero, con `sales.cobrar` y sin PIN de supervisor:
  el cupón *es* la autorización. Es la diferencia con
  `ventas.aplicar_descuento`, que sí exige que un supervisor firme
  (RN-COM-017) porque ahí el margen se regala a criterio de alguien.

El descuento se aplica sobre `venta.descuento_*` con motivo `cupon`. Esos
campos son el único lugar del que `total_a_cobrar` y el prorrateo al
comprobante leen; un segundo canal de descuento obligaría a tocar la
aritmética del dinero, y el motivo propio ya alcanza para distinguir en el
reporte qué se regaló a criterio y qué se había prometido en una campaña.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.sales.application import clientes as clientes_app
from src.modules.sales.application import ventas as ventas_app
from src.modules.sales.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import (
    Cliente,
    Cupon,
    PromocionCupon,
    Venta,
)
from src.modules.sales.infrastructure.repositories import (
    ClienteRepo,
    CuponRepo,
    PromocionCuponRepo,
    VentaRepo,
)
from src.modules.users.infrastructure.models import Persona
from src.shared import auditoria, fechas

PROMOCION_NO_DISPONIBLE = "la promoción no está disponible"
CUPON_YA_USADO = "este cupón ya fue usado"
CUPON_VENCIDO = "este cupón ya venció"


def promocion_vigente(
    session: Session, grupo_id: uuid.UUID | None = None
) -> PromocionCupon:
    """La promoción que hoy emite cupones, o el 409 que lo explica.

    Se resuelve acá y no en el router porque las dos puertas —la landing y
    la caja— tienen que ver exactamente la misma promoción; si cada una la
    buscara a su manera, terminarían emitiendo contra una y canjeando
    contra otra.

    `grupo_id=None` es la landing pública, que no tiene tenant: el cliente
    que escanea el QR no es usuario del ERP y un `grupo_id` que viniera en
    el request sería una forma de escribir en otro tenant. Con dos
    promociones activas corta con un 409 en vez de elegir una — un
    descuento repartido contra la campaña equivocada no se nota hasta que
    alguien cuadra los números.
    """
    activas = PromocionCuponRepo(session).activas(grupo_id)
    if not activas:
        raise Conflicto(PROMOCION_NO_DISPONIBLE)
    if len(activas) > 1:
        raise Conflicto("hay más de una promoción de cupón activa")
    promocion = activas[0]
    if not rules.promocion_emite(promocion.estado, promocion.vigente_hasta, fechas.hoy()):
        raise Conflicto(PROMOCION_NO_DISPONIBLE)
    return promocion


def _cliente_por_documento(
    session: Session, grupo_id: uuid.UUID, numero_documento: str
) -> Cliente | None:
    return session.scalar(
        select(Cliente)
        .join(Persona, Persona.id == Cliente.persona_id)
        .where(
            Cliente.grupo_id == grupo_id,
            Cliente.deleted_at.is_(None),
            Persona.numero_documento == numero_documento,
        )
    )


def _cliente_por_telefono(
    session: Session, grupo_id: uuid.UUID, telefono: str
) -> Cliente | None:
    """El segundo camino para reconocer a alguien que ya está en el padrón.

    Existe porque en caja se registra con solo teléfono (RN-PTS-002): media
    base está cargada sin documento, y sin este `else` toda esa gente
    entraría como cliente nuevo y terminaría duplicada contra su propio
    registro anterior.
    """
    return session.scalar(
        select(Cliente)
        .join(Persona, Persona.id == Cliente.persona_id)
        .where(
            Cliente.grupo_id == grupo_id,
            Cliente.deleted_at.is_(None),
            Persona.telefono == telefono,
        )
    )


def esta_registrado(
    session: Session, *, numero_documento: str, telefono: str = ""
) -> bool:
    """Lo ÚNICO que la landing puede preguntar sobre alguien.

    Devuelve un booleano y nada más — ni el nombre, ni el teléfono, ni el
    cupón. Quien pregunta no está autenticado, y una respuesta más rica
    convertiría este endpoint en un buscador del padrón para cualquiera.

    El grupo sale de la promoción activa y nunca del request: un `grupo_id`
    que viniera de afuera dejaría preguntar por el padrón de otro tenant.
    """
    grupo_id = promocion_vigente(session).grupo_id
    numero_documento = (numero_documento or "").strip()
    telefono = (telefono or "").strip()
    if numero_documento and _cliente_por_documento(session, grupo_id, numero_documento):
        return True
    return bool(telefono) and _cliente_por_telefono(session, grupo_id, telefono) is not None


def _emitir(
    session: Session, promocion: PromocionCupon, cliente: Cliente, codigo: str
) -> Cupon:
    hoy = fechas.hoy()
    return CuponRepo(session).add(
        Cupon(
            promocion_id=promocion.id,
            cliente_id=cliente.id,
            codigo=codigo,
            estado="activo",
            vigente_hasta=rules.vencimiento_cupon(hoy, promocion.vigencia_cupon_dias),
        )
    )


def _dni_valido(numero_documento: str) -> str:
    numero_documento = (numero_documento or "").strip()
    if not numero_documento:
        raise ReglaNegocio("el DNI es obligatorio para participar")
    if not rules.cliente_identificado(numero_documento):
        raise ReglaNegocio("ese número de documento no es válido")
    if len(numero_documento) != rules.LARGO_DNI or not numero_documento.isdigit():
        raise ReglaNegocio("el DNI son 8 dígitos")
    return numero_documento


def _exigir_canjeable(cupon: Cupon) -> None:
    """Un cupón que existe pero ya no sirve, y por qué.

    Los dos motivos se distinguen a propósito: «ya lo usaste» y «se te
    venció» llevan al cliente a cosas distintas, y un mensaje único los
    dejaría a los dos parados frente a la caja sin saber cuál les tocó.
    """
    if cupon.estado == "canjeado":
        raise Conflicto(CUPON_YA_USADO)
    if not rules.cupon_vigente(cupon.estado, cupon.vigente_hasta, fechas.hoy()):
        raise Conflicto(CUPON_VENCIDO)


def _sin_documento(session: Session, cliente: Cliente) -> bool:
    """¿A esta ficha todavía se le puede poner un documento?

    Solo si no tiene ninguno. `rules.cliente_identificado` deja afuera al
    genérico `00000000`, que es «sin documento» escrito de otra forma.
    """
    persona = session.get(Persona, cliente.persona_id) if cliente.persona_id else None
    if persona is None:
        return False
    return not rules.cliente_identificado(persona.numero_documento or "")


def _resolver_cliente(
    session: Session,
    *,
    grupo_id: uuid.UUID,
    numero_documento: str,
    nombre: str,
    telefono: str,
    fecha_nacimiento: date | None,
    direccion: str | None,
    ubicacion: dict | None,
) -> tuple[Cliente, bool]:
    """El cliente de este registro y si ya estaba en el padrón.

    Busca por documento y después por teléfono. El segundo intento no es
    redundante: en caja se da de alta con solo teléfono (RN-PTS-002), así
    que media base está sin documento y sin este camino toda esa gente
    entraría como nueva y quedaría duplicada contra su propia ficha.

    **El teléfono solo vale si esa persona no tiene documento todavía.** Es
    la diferencia entre completar una ficha a medias y reescribir la
    identidad de alguien: este endpoint no autentica a nadie, así que sin
    ese candado bastaría saber un teléfono ajeno para cambiarle el DNI a su
    dueño —y quedarse, de paso, con su historial de compras—. Un teléfono
    que ya pertenece a alguien identificado se ignora y el registro sigue
    como cliente nuevo: dos fichas que comparten teléfono son un problema de
    calidad de datos que alguien limpia; una identidad pisada, no.
    """
    cliente = _cliente_por_documento(session, grupo_id, numero_documento)
    if cliente is not None:
        _completar_datos(
            session,
            cliente,
            telefono=telefono,
            fecha_nacimiento=fecha_nacimiento,
            direccion=direccion,
            ubicacion=ubicacion,
        )
        return cliente, True

    cliente = _cliente_por_telefono(session, grupo_id, telefono)
    if cliente is not None and _sin_documento(session, cliente):
        clientes_app.actualizar_documento(
            session, cliente_id=cliente.id, numero_documento=numero_documento
        )
        _completar_datos(
            session,
            cliente,
            fecha_nacimiento=fecha_nacimiento,
            direccion=direccion,
            ubicacion=ubicacion,
        )
        return cliente, True

    return (
        clientes_app.crear_cliente(
            session,
            grupo_id=grupo_id,
            nombre=nombre,
            telefono=telefono,
            numero_documento=numero_documento,
            direccion=direccion,
            fecha_nacimiento=fecha_nacimiento,
            **(ubicacion or {}),
        ),
        False,
    )


def registrar_y_emitir(
    session: Session,
    *,
    numero_documento: str,
    nombre: str,
    telefono: str,
    fecha_nacimiento: date | None = None,
    direccion: str | None = None,
    ubicacion: dict | None = None,
) -> tuple[Cupon, bool]:
    """Registra al cliente si hace falta y le entrega su cupón.

    Devuelve `(cupon, ya_estaba_registrado)`. Los tres caminos posibles —no
    existía, existía sin cupón, existía con cupón— terminan igual de bien:
    el cliente escaneó un QR que le prometió un descuento y tiene que
    irse con uno, o con la razón exacta por la que no.

    El único caso que no entrega cupón es el ya canjeado, y ahí devolver
    otro sería regalar el segundo 10 % que la promoción dice que no existe.

    El grupo lo pone la promoción, nunca el request: acá no hay tenant que
    validar —el cliente no es usuario del ERP— y un `grupo_id` de afuera
    sería permiso para escribir en otro.
    """
    promocion = promocion_vigente(session)
    grupo_id = promocion.grupo_id
    numero_documento = _dni_valido(numero_documento)
    telefono = (telefono or "").strip()
    if not telefono:
        raise ReglaNegocio("el teléfono es obligatorio para participar")

    cliente, ya_estaba = _resolver_cliente(
        session,
        grupo_id=grupo_id,
        numero_documento=numero_documento,
        nombre=nombre,
        telefono=telefono,
        fecha_nacimiento=fecha_nacimiento,
        direccion=direccion,
        ubicacion=ubicacion,
    )

    existente = CuponRepo(session).por_cliente(promocion.id, cliente.id)
    if existente is not None:
        _exigir_canjeable(existente)
        return existente, ya_estaba

    cupon = _emitir(session, promocion, cliente, numero_documento)
    event_bus.publish(
        "sales.cliente_registrado_en_promocion",
        {
            "promocion_id": str(promocion.id),
            # El nombre y no solo el id: `marketing` empareja la promoción
            # con SU campaña por nombre, y no puede leer `promocion_cupon`
            # —es una tabla de `sales`— sin entrar por donde no debe.
            "promocion_nombre": promocion.nombre,
            "cliente_id": str(cliente.id),
            "cupon_id": str(cupon.id),
            "ya_estaba_registrado": ya_estaba,
        },
        session=session,
    )
    return cupon, ya_estaba


def _completar_datos(
    session: Session,
    cliente: Cliente,
    *,
    telefono: str | None = None,
    fecha_nacimiento: date | None = None,
    direccion: str | None = None,
    ubicacion: dict | None = None,
) -> None:
    """Rellena en `persona` lo que el cliente acaba de dar y no tenía.

    **No pisa nada.** Los datos de caja los tecleó alguien mirando al
    cliente; lo que llega de una página pública no tiene por qué ganarles.
    Pero completar lo que falta sí, y es la mitad del valor de la campaña:
    media base está cargada con solo teléfono o solo documento, y esta es la
    única vez que esa gente entrega el resto.

    Mismo criterio que `clientes._completar_persona` — la ubicación se
    escribe solo si vino con la dirección, porque anclar un punto sin haber
    tocado el texto dejaría a los dos contando historias distintas.
    """
    persona = session.get(Persona, cliente.persona_id) if cliente.persona_id else None
    if persona is None:
        return
    if telefono and not persona.telefono:
        persona.telefono = telefono
    if fecha_nacimiento and not persona.fecha_nacimiento:
        persona.fecha_nacimiento = fecha_nacimiento
    if direccion and not persona.domicilio:
        persona.domicilio = direccion
        for campo, valor in (ubicacion or {}).items():
            if valor is not None and getattr(persona, campo, None) is None:
                setattr(persona, campo, valor)


def _venta_para_cupon(session: Session, venta_id: uuid.UUID) -> Venta:
    venta = VentaRepo(session).get(venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if venta.estado != "orden":
        raise Conflicto(f"la venta está {venta.estado}; no admite cupón")
    if not rules.admite_cobro(venta.tipo):
        raise Conflicto("un consumo de personal ya vale cero: no admite cupón")
    # Un solo descuento por orden: `venta.descuento_*` es una fila, no una
    # lista, y encimar el cupón sobre uno manual borraría el otro sin que
    # nadie se entere.
    if venta.descuento_modo is not None:
        raise Conflicto(
            "la venta ya tiene un descuento; quítalo antes de aplicar el cupón"
        )
    if venta.cliente_id is None:
        raise ReglaNegocio(
            "el cupón es de un cliente: identifícalo en la venta antes de canjearlo"
        )
    return venta


def canjear(
    session: Session,
    *,
    venta_id: uuid.UUID,
    codigo: str,
    actor_id: uuid.UUID,
) -> tuple[Cupon, Decimal]:
    """Aplica el cupón a la venta y lo apaga para siempre.

    El orden importa: primero se valida todo, después se marca canjeado y
    recién al final se toca la venta. Al revés, un cupón podría quedar
    quemado por una venta que después rechaza el descuento.
    """
    venta = _venta_para_cupon(session, venta_id)
    cliente = ClienteRepo(session).get(venta.cliente_id)
    if cliente is None or cliente.deleted_at is not None:
        raise NoEncontrado("cliente no encontrado")
    promocion = promocion_vigente(session, cliente.grupo_id)

    codigo = (codigo or "").strip()
    cupon = CuponRepo(session).por_codigo(promocion.id, codigo)
    if cupon is None:
        raise NoEncontrado("ese código no corresponde a ningún cupón")
    # El cupón es nominal. Sin esto, quien conozca un DNI ajeno se lleva el
    # descuento de otro — que es justo el costo que ADR-059 acota atándolo
    # al cliente de la venta.
    if cupon.cliente_id != venta.cliente_id:
        raise ReglaNegocio("ese cupón es de otro cliente")
    _exigir_canjeable(cupon)

    cupon.estado = "canjeado"
    cupon.venta_id = venta.id
    cupon.canjeado_at = datetime.now(UTC)
    cupon.canjeado_por = actor_id

    venta.descuento_modo = "porcentaje"
    venta.descuento_valor = promocion.descuento_porcentaje
    venta.descuento_motivo = rules.MOTIVO_CUPON
    # Quien lo aplicó, no quien lo autorizó: acá no autorizó nadie, el cupón
    # ya venía ganado. La columna se llama `autorizado_por` por el descuento
    # manual (RN-COM-017) y el motivo `cupon` es lo que distingue los dos
    # casos en el reporte.
    venta.descuento_autorizado_por = actor_id
    venta.total = ventas_app.total_a_cobrar(session, venta)

    monto = ventas_app.calcular_monto_descuento(
        session, venta, venta.descuento_modo, venta.descuento_valor
    )
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="cupon",
        entidad_id=cupon.id,
        accion="canjear",
        datos_antes={"estado": "activo"},
        datos_despues={
            "estado": "canjeado",
            "venta_id": str(venta.id),
            "codigo": cupon.codigo,
            "monto": str(monto),
        },
        sucursal_id=venta.sucursal_id,
    )
    event_bus.publish(
        "sales.cupon_canjeado",
        {
            "cupon_id": str(cupon.id),
            "promocion_id": str(promocion.id),
            "cliente_id": str(cupon.cliente_id),
            "venta_id": str(venta.id),
            "monto": str(monto),
        },
        session=session,
    )
    return cupon, monto


def listar_promociones(
    session: Session, *, grupo_id: uuid.UUID | None = None
) -> list[PromocionCupon]:
    """Las promociones de cupón que el back-office puede ver.

    Filtra por grupo y no por empresa porque el cupón es del cliente, y el
    cliente es del grupo (RN-PTS-001). `None` es el superusuario sin empresa
    asignada, que ve todo — mismo criterio que `Tenant.filtro_empresa`.
    """
    return PromocionCuponRepo(session).listar(grupo_id)


def terminar(
    session: Session, *, promocion_id: uuid.UUID, actor_id: uuid.UUID
) -> PromocionCupon:
    """El derecho reservado de cortar la promoción en cualquier momento.

    Deja de emitir cupones nuevos y no toca los ya emitidos: quien alcanzó a
    registrarse cumplió su parte del trato.
    """
    promocion = PromocionCuponRepo(session).get(promocion_id)
    if promocion is None:
        raise NoEncontrado("promoción no encontrada")
    if promocion.estado == "terminada":
        raise Conflicto("la promoción ya está terminada")
    promocion.estado = "terminada"
    promocion.terminada_at = datetime.now(UTC)
    promocion.terminada_por = actor_id
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="promocion_cupon",
        entidad_id=promocion.id,
        accion="terminar",
        datos_antes={"estado": "activa"},
        datos_despues={"estado": "terminada"},
    )
    return promocion
