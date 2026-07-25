"""Seeder de desarrollo: organización base, roles/permisos semilla y usuario
`admin` (PIN 123456).

Idempotente: se puede correr varias veces. PROHIBIDO en producción.

Uso:
    python -m src.seeders.seed
"""

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.database import SessionLocal
from src.modules.users.infrastructure.models import (
    Empresa,
    Grupo,
    Marca,
    Permiso,
    Rol,
    RolPermiso,
    Usuario,
    UsuarioRol,
)
from src.modules.users.infrastructure.security import hash_pin

# Matriz semilla (authorization.md). "*" = todo (solo admin, entornos internos).
PERMISOS = [
    ("*", "Acceso total (solo entornos internos)"),
    ("users.gestionar", "Administrar usuarios, roles y permisos"),
    ("sales.crear", "Crear venta"),
    ("sales.cobrar", "Cobrar venta"),
    ("sales.leer", "Consultar ventas"),
    ("sales.anular", "Anular orden no pagada"),
    ("sales.gestionar_catalogo", "CRUD de productos comerciales y medios de pago"),
    ("kds.configurar", "Crear y configurar pantallas KDS"),
    ("kds.operar", "Operar KDS: cola, avance de ítems, comanda"),
    ("sales.crear_pedido", "Crear pedido (canal agente IA)"),
    ("inventory.transferir", "Transferir stock"),
    ("inventory.recepcion", "Recepcionar mercadería"),
    ("inventory.ajustar", "Ajustar inventario"),
    ("inventory.leer", "Consultar stock y catálogo"),
    ("inventory.gestionar_catalogo", "CRUD de artículos, categorías y SKUs"),
    ("inventory.registrar_movimiento", "Registrar movimiento de stock"),
    ("inventory.solicitar_ajuste", "Solicitar ajuste de inventario"),
    ("inventory.aprobar_ajuste", "Aprobar ajuste de inventario"),
    ("purchases.aprobar", "Aprobar orden de compra"),
]

ROLES = {
    "admin": ["*"],
    "supervisor": [
        "purchases.aprobar",
        "sales.leer",
        "sales.anular",
        "sales.gestionar_catalogo",
        "kds.configurar",
        "kds.operar",
        "inventory.leer",
        "inventory.gestionar_catalogo",
        "inventory.aprobar_ajuste",
    ],
    "cajero": ["sales.crear", "sales.cobrar", "sales.leer", "kds.operar"],
    "cocinero": ["kds.operar", "sales.leer"],
    "almacenero": [
        "inventory.transferir",
        "inventory.recepcion",
        "inventory.ajustar",
        "inventory.leer",
        "inventory.registrar_movimiento",
        "inventory.solicitar_ajuste",
    ],
    "agente_ia": ["sales.crear_pedido"],
}


def _get_or_create(session: Session, model, defaults=None, **filtros):
    inst = session.scalar(select(model).filter_by(**filtros))
    if inst is not None:
        return inst, False
    inst = model(**filtros, **(defaults or {}))
    session.add(inst)
    session.flush()
    return inst, True


def seed(session: Session) -> None:
    # --- Organización base (Grupo Majambo) ---
    grupo, _ = _get_or_create(session, Grupo, nombre="Grupo Majambo")
    _get_or_create(
        session,
        Empresa,
        ruc="20450311520",
        defaults=dict(
            grupo_id=grupo.id,
            razon_social="Inversiones Turísticas y Alimentarias Majambo EIRL",
            domicilio_fiscal="Tarapoto, San Martín",
            tipo="operativa",
            zona_tributaria="amazonia_ley27037",
        ),
    )
    _get_or_create(
        session,
        Marca,
        grupo_id=grupo.id,
        nombre="Charlie's Pizzas",
        defaults=dict(tipo="restaurante"),
    )

    # --- Permisos ---
    permisos = {}
    for codigo, desc in PERMISOS:
        p, _ = _get_or_create(
            session, Permiso, codigo=codigo, defaults=dict(descripcion=desc)
        )
        permisos[codigo] = p

    # --- Roles + asignación de permisos ---
    roles = {}
    for nombre, codigos in ROLES.items():
        rol, _ = _get_or_create(session, Rol, nombre=nombre)
        roles[nombre] = rol
        for codigo in codigos:
            if session.get(RolPermiso, (rol.id, permisos[codigo].id)) is None:
                session.add(
                    RolPermiso(rol_id=rol.id, permiso_id=permisos[codigo].id)
                )

    # --- Usuario admin (PIN 123456) ---
    admin, creado = _get_or_create(
        session,
        Usuario,
        username="admin",
        defaults=dict(pin_hash=hash_pin("123456"), tipo="humano", activo=True),
    )
    if session.get(UsuarioRol, (admin.id, roles["admin"].id)) is None:
        session.add(UsuarioRol(usuario_id=admin.id, rol_id=roles["admin"].id))

    session.commit()
    print("Seed OK. admin/123456 con rol admin. Usuario nuevo:" if creado else
          "Seed OK (idempotente). admin ya existía.")


def main() -> None:
    if settings.environment.lower() in ("production", "prod"):
        sys.exit("ABORTADO: el seeder está prohibido en producción.")
    with SessionLocal() as session:
        seed(session)


if __name__ == "__main__":
    main()
