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
    (
        "personas.anonimizar",
        "Anonimizar datos de una persona — derecho de cancelación (Ley 29733)",
    ),
    ("sales.crear", "Crear venta"),
    ("sales.cobrar", "Cobrar venta"),
    ("sales.leer", "Consultar ventas"),
    ("sales.anular", "Anular orden no pagada"),
    ("sales.gestionar_catalogo", "CRUD de productos comerciales y medios de pago"),
    ("sales.emitir_comprobante", "Reintentar la emisión de un comprobante a SUNAT"),
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
    ("purchases.crear", "CRUD de proveedores, crear y emitir OC bajo el umbral"),
    ("purchases.leer", "Consultar proveedores y órdenes de compra"),
    ("purchases.recepcionar", "Registrar recepción de una OC"),
    ("purchases.anular", "Anular una OC sin recepción registrada"),
    ("purchases.aprobar", "Aprobar orden de compra"),
    (
        "purchases.dar_conformidad",
        "Dar conformidad al comprobante recibido (dispara el pago)",
    ),
    ("production.crear", "Crear orden de producción y registrar consumo"),
    ("production.leer", "Consultar órdenes de producción"),
    ("production.completar", "Registrar control de calidad y completar la orden"),
    (
        "accounting.cuenta_administrar",
        "Administrar plan de cuentas y mapeo de asientos automáticos",
    ),
    ("accounting.periodo_administrar", "Abrir y cerrar periodos contables"),
    ("accounting.asiento_manual", "Registrar y anular asientos manuales"),
    ("accounting.leer", "Consultar plan de cuentas, asientos y periodos"),
    (
        "accounting.pago_gestionar",
        "Registrar, ejecutar y rechazar pagos a proveedor bajo el umbral",
    ),
    ("accounting.pago_aprobar", "Aprobar pagos a proveedor sobre el umbral"),
    ("accounting.caja_operar", "Abrir y cerrar caja (PROC-CTB-001/002)"),
    ("accounting.arqueo_registrar", "Registrar arqueo de caja (sorpresa o programado)"),
    ("dashboard.leer", "Consultar el dashboard gerencial (ventas, stock, caja)"),
    ("gerencia.gestionar_reglas_aprobacion", "Administrar la matriz de aprobaciones"),
    ("sales.leer_clientes_externos", "Consultar clientes para análisis fuera de sales"),
    ("rrhh.leer", "Consultar trabajadores, contratos, nómina y documentos de RRHH"),
    ("rrhh.trabajador_gestionar", "Crear, actualizar y cesar trabajadores"),
    ("rrhh.contrato_gestionar", "Crear, firmar y finalizar contratos laborales"),
    ("rrhh.postulante_gestionar", "Gestionar postulantes y su estado de selección"),
    ("rrhh.socio_gestionar", "Administrar socios y participación societaria"),
    ("rrhh.nomina_gestionar", "Emitir boletas de pago y liquidaciones de beneficios sociales"),
    (
        "rrhh.disciplina_gestionar",
        "Emitir memorándums, amonestaciones, actas y certificados de trabajo",
    ),
    ("rrhh.permiso_solicitar", "Solicitar vacaciones, licencias y permisos"),
    ("rrhh.permiso_aprobar", "Aprobar o rechazar solicitudes de permiso"),
    ("rrhh.asistencia_marcar", "Marcar entrada y salida de asistencia"),
    ("rrhh.capacitacion_gestionar", "Administrar pactos de permanencia por capacitación"),
    ("sync.leer", "Descargar catálogo, stock y RBAC de la sucursal hacia su hub"),
    ("sync.empujar", "Reproducir en la nube las ventas y cobros de un hub offline"),
]

ROLES = {
    "admin": ["*"],
    "supervisor": [
        "purchases.aprobar",
        "purchases.leer",
        "sales.leer",
        "sales.anular",
        "sales.gestionar_catalogo",
        "sales.emitir_comprobante",
        "kds.configurar",
        "kds.operar",
        "inventory.leer",
        "inventory.gestionar_catalogo",
        "inventory.aprobar_ajuste",
        "sales.leer_clientes_externos",
        "accounting.pago_aprobar",
        "accounting.arqueo_registrar",
        "dashboard.leer",
        "rrhh.leer",
        "rrhh.permiso_aprobar",
        "rrhh.asistencia_marcar",
    ],
    "cajero": [
        "sales.crear",
        "sales.cobrar",
        "sales.leer",
        "kds.operar",
        "accounting.caja_operar",
    ],
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
    # Cuenta de servicio del hub de sucursal (ADR-009): lo mínimo para
    # replicar hacia abajo y reproducir hacia arriba. Nada de gestión de
    # catálogo, RRHH ni contabilidad — un hub robado no es un admin.
    "hub_sucursal": ["sync.leer", "sync.empujar"],
    "comprador": [
        "purchases.crear",
        "purchases.leer",
        "purchases.recepcionar",
        "purchases.anular",
        "purchases.dar_conformidad",
    ],
    "jefe_cocina": [
        "production.crear",
        "production.leer",
        "production.completar",
    ],
    "contador": [
        "accounting.cuenta_administrar",
        "accounting.periodo_administrar",
        "accounting.asiento_manual",
        "accounting.leer",
        "accounting.pago_gestionar",
        "accounting.arqueo_registrar",
        "dashboard.leer",
    ],
    "rrhh_admin": [
        "rrhh.leer",
        "rrhh.trabajador_gestionar",
        "rrhh.contrato_gestionar",
        "rrhh.postulante_gestionar",
        "rrhh.socio_gestionar",
        "rrhh.nomina_gestionar",
        "rrhh.disciplina_gestionar",
        "rrhh.permiso_solicitar",
        "rrhh.permiso_aprobar",
        "rrhh.asistencia_marcar",
        "rrhh.capacitacion_gestionar",
    ],
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
