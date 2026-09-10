"""Kilometraje de un vehículo: registro de odómetro (RN-VEH-004/005)."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from src.modules.assets.application.errors import ReglaNegocio
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.models import LecturaOdometro, Vehiculo
from src.modules.assets.infrastructure.repositories import LecturaOdometroRepo


def registrar_lectura(
    session: Session,
    vehiculo: Vehiculo,
    *,
    km: int,
    fecha: date,
    origen: str,
    registrado_por: uuid.UUID,
    nota: str | None = None,
) -> LecturaOdometro:
    """El punto único por el que pasa cualquier kilometraje nuevo — lo llama
    tanto el registro manual como `combustible.registrar_carga` y
    `ordenes.realizar_orden`, así que RN-VEH-005 se cumple sin importar por
    dónde entró el dato."""
    if not rules.odometro_valido(km, vehiculo.kilometraje_actual):
        raise ReglaNegocio(f"el odómetro no puede retroceder: {km} < {vehiculo.kilometraje_actual}")
    lectura = LecturaOdometroRepo(session).add(
        LecturaOdometro(
            vehiculo_id=vehiculo.activo_id,
            fecha=fecha,
            km=km,
            origen=origen,
            registrado_por=registrado_por,
            nota=nota,
        )
    )
    vehiculo.kilometraje_actual = km
    return lectura


def q_lecturas(session: Session, vehiculo_id: uuid.UUID):
    return LecturaOdometroRepo(session).q_de_vehiculo(vehiculo_id)
