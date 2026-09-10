"""Alta, edición y baja de un activo (equipamiento o vehículo).

Un vehículo es un activo con una fila `vehiculo` 1:1 (data-model.md
§Recursos): las dos se crean en la misma llamada porque un activo `tipo=
"vehiculo"` sin su fila `vehiculo` es un dato a medio escribir, no un
equipamiento con un campo de más.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.assets.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.models import Activo, LecturaOdometro, Vehiculo
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    LecturaOdometroRepo,
    VehiculoRepo,
)
from src.shared import auditoria, fechas


def crear_activo(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    tipo: str,
    id_interno: str,
    nombre: str,
    creado_por: uuid.UUID,
    sucursal_id: uuid.UUID | None = None,
    categoria: str | None = None,
    marca: str | None = None,
    modelo: str | None = None,
    numero_serie: str | None = None,
    etiqueta_codigo: str | None = None,
    fecha_compra: date | None = None,
    valor_compra: Decimal | None = None,
    vida_util_meses: int | None = None,
    proveedor_id: uuid.UUID | None = None,
    comprobante_compra_id: uuid.UUID | None = None,
    responsable_trabajador_id: uuid.UUID | None = None,
    notas: str | None = None,
    # Solo si tipo == "vehiculo":
    placa: str | None = None,
    tipo_vehiculo: str | None = None,
    numero_motor: str | None = None,
    numero_chasis: str | None = None,
    tenencia: str = "propio",
    kilometraje_inicial: int | None = None,
) -> Activo:
    if tipo not in rules.TIPOS_ACTIVO:
        raise ReglaNegocio(f"tipo de activo inválido: {tipo}")

    repo = ActivoRepo(session)
    existente = session.scalar(
        select(Activo).where(
            Activo.empresa_id == empresa_id,
            Activo.id_interno == id_interno,
            Activo.deleted_at.is_(None),
        )
    )
    if existente is not None:
        raise Conflicto(f"ya existe un activo con id_interno {id_interno}")

    activo = repo.add(
        Activo(
            empresa_id=empresa_id,
            sucursal_id=sucursal_id,
            tipo=tipo,
            id_interno=id_interno,
            nombre=nombre,
            categoria=categoria,
            marca=marca,
            modelo=modelo,
            numero_serie=numero_serie,
            etiqueta_codigo=etiqueta_codigo,
            fecha_compra=fecha_compra,
            valor_compra=valor_compra,
            vida_util_meses=vida_util_meses,
            proveedor_id=proveedor_id,
            comprobante_compra_id=comprobante_compra_id,
            responsable_trabajador_id=responsable_trabajador_id,
            notas=notas,
        )
    )

    if tipo == "vehiculo":
        if not placa or not tipo_vehiculo:
            raise ReglaNegocio("un vehículo requiere placa y tipo_vehiculo")
        if VehiculoRepo(session).get_by_placa(placa) is not None:
            raise Conflicto(f"la placa {placa} ya está registrada")
        VehiculoRepo(session).add(
            Vehiculo(
                activo_id=activo.id,
                placa=placa,
                tipo_vehiculo=tipo_vehiculo,
                numero_motor=numero_motor,
                numero_chasis=numero_chasis,
                tenencia=tenencia,
                kilometraje_actual=kilometraje_inicial,
            )
        )
        if kilometraje_inicial is not None:
            LecturaOdometroRepo(session).add(
                LecturaOdometro(
                    vehiculo_id=activo.id,
                    fecha=fecha_compra or fechas.hoy(),
                    km=kilometraje_inicial,
                    origen="manual",
                    registrado_por=creado_por,
                    nota="Kilometraje inicial al registrar el vehículo",
                )
            )

    auditoria.registrar(
        session,
        entidad="activo",
        accion="crear",
        entidad_id=activo.id,
        usuario_id=creado_por,
        datos_despues={"tipo": tipo, "id_interno": id_interno, "nombre": nombre},
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
    )
    return activo


def editar_activo(
    session: Session,
    activo_id: uuid.UUID,
    *,
    nombre: str | None = None,
    sucursal_id: uuid.UUID | None = None,
    categoria: str | None = None,
    marca: str | None = None,
    modelo: str | None = None,
    numero_serie: str | None = None,
    etiqueta_codigo: str | None = None,
    valor_compra: Decimal | None = None,
    vida_util_meses: int | None = None,
    responsable_trabajador_id: uuid.UUID | None = None,
    notas: str | None = None,
) -> Activo:
    activo = ActivoRepo(session).get(activo_id)
    if activo is None:
        raise NoEncontrado("activo no encontrado")
    for campo, valor in (
        ("nombre", nombre),
        ("sucursal_id", sucursal_id),
        ("categoria", categoria),
        ("marca", marca),
        ("modelo", modelo),
        ("numero_serie", numero_serie),
        ("etiqueta_codigo", etiqueta_codigo),
        ("valor_compra", valor_compra),
        ("vida_util_meses", vida_util_meses),
        ("responsable_trabajador_id", responsable_trabajador_id),
        ("notas", notas),
    ):
        if valor is not None:
            setattr(activo, campo, valor)
    return activo


def dar_baja_activo(
    session: Session, activo_id: uuid.UUID, *, actor_id: uuid.UUID, motivo: str
) -> Activo:
    """Baja del activo (RN-ACT-001/002 lo condicionan a depreciación total en
    `accounting`, deuda declarada: hoy es un acto administrativo del
    responsable del activo, no contable)."""
    activo = ActivoRepo(session).get(activo_id)
    if activo is None:
        raise NoEncontrado("activo no encontrado")
    if activo.estado == "de_baja":
        raise Conflicto("el activo ya está de baja")
    estado_antes = activo.estado
    activo.estado = "de_baja"
    activo.archivado = True
    auditoria.registrar(
        session,
        entidad="activo",
        accion="dar_baja",
        entidad_id=activo.id,
        usuario_id=actor_id,
        datos_antes={"estado": estado_antes},
        datos_despues={"estado": "de_baja", "motivo": motivo},
        empresa_id=activo.empresa_id,
        sucursal_id=activo.sucursal_id,
    )
    return activo


def q_activos(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    tipo: str | None = None,
    sucursal_id: uuid.UUID | None = None,
):
    return ActivoRepo(session).q_list(empresa_id, tipo=tipo, sucursal_id=sucursal_id)
