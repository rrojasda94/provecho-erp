"""CRUD de proveedores. Natural liga a `persona` (party model, RN-GEN-007);
jurídico trae razón social/RUC propios."""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.purchases.application.errors import NoEncontrado, ReglaNegocio
from src.modules.purchases.domain import rules
from src.modules.purchases.infrastructure.models import Proveedor
from src.modules.purchases.infrastructure.repositories import ProveedorRepo
from src.modules.users.infrastructure.models import Persona
from src.shared.integrations.factiliza import razon_social_desde_ruc


def crear_proveedor(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    tipo: str,
    condicion_pago: str,
    persona_id: uuid.UUID | None = None,
    razon_social: str | None = None,
    ruc: str | None = None,
    contacto: str | None = None,
    formal: bool = True,
    clasificacion: str = "regular",
    plazo_dias_credito: int | None = None,
    afecto_igv: bool = True,
    sujeto_spot: bool = False,
    porcentaje_deteccion: Decimal | None = None,
) -> Proveedor:
    if tipo == "natural":
        if persona_id is None:
            raise ReglaNegocio("proveedor natural requiere persona_id")
        if session.get(Persona, persona_id) is None:
            raise NoEncontrado(f"persona {persona_id} no encontrada")
        razon_social = None
        ruc = None
    elif tipo == "juridico":
        if not razon_social or not ruc:
            raise ReglaNegocio("proveedor jurídico requiere razon_social y ruc")
        persona_id = None
        razon_social = razon_social_desde_ruc(ruc, razon_social)
    else:
        raise ReglaNegocio(f"tipo de proveedor inválido: {tipo}")

    if clasificacion not in rules.CLASIFICACIONES_PROVEEDOR:
        raise ReglaNegocio(f"clasificación inválida: {clasificacion}")
    if condicion_pago not in rules.CONDICIONES_PAGO:
        raise ReglaNegocio(f"condición de pago inválida: {condicion_pago}")
    if condicion_pago == "credito" and not plazo_dias_credito:
        raise ReglaNegocio("condición 'credito' requiere plazo_dias_credito")

    return ProveedorRepo(session).add(
        Proveedor(
            empresa_id=empresa_id,
            tipo=tipo,
            persona_id=persona_id,
            razon_social=razon_social,
            ruc=ruc,
            contacto=contacto,
            formal=formal,
            clasificacion=clasificacion,
            condicion_pago=condicion_pago,
            plazo_dias_credito=plazo_dias_credito,
            afecto_igv=afecto_igv,
            sujeto_spot=sujeto_spot,
            porcentaje_deteccion=porcentaje_deteccion,
        )
    )


def listar_proveedores(session: Session, empresa_id: uuid.UUID | None = None) -> list[Proveedor]:
    return ProveedorRepo(session).list(empresa_id)


def editar_proveedor(session: Session, proveedor_id: uuid.UUID, **campos) -> Proveedor:
    proveedor = ProveedorRepo(session).get(proveedor_id)
    if proveedor is None:
        raise NoEncontrado("proveedor no encontrado")
    for campo, valor in campos.items():
        if valor is not None:
            setattr(proveedor, campo, valor)
    return proveedor
