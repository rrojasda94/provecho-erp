"""Seeder de desarrollo: organización real del Grupo Majambo (empresa,
marca licenciada, sucursales CH1/CH2 y almacén central WH1), roles/permisos
semilla y usuario `admin` (PIN 123456).

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
    Almacen,
    Empresa,
    Grupo,
    LicenciaMarca,
    Marca,
    Permiso,
    Rol,
    RolPermiso,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared.models import Divisa
from src.shared.parametros import MODULOS

# Moneda de la operación (RN-PRC-004). `decimales` es configurable por divisa.
DIVISAS = [("PEN", "Sol peruano", "S/", 2)]

# --- Organización real del Grupo Majambo ---
GRUPO = "Grupo Majambo"
MARCA = "Charlie's Pizzas"
EMPRESA_RUC = "20450311520"
EMPRESA_RAZON_SOCIAL = "Inversiones Turísticas y Alimentarias Majambo EIRL"
SEDE_CASTILLA = "Jr. Ramón Castilla 248 - Tarapoto"

# nombre → (dirección, tenencia). La tenencia decide predial/arbitrios
# (RN-IMP-004); ambas sucursales operan en local alquilado.
SUCURSALES = {
    "CH1": (SEDE_CASTILLA, "alquilada"),
    "CH2": ("Jr. Lamas 299 - Tarapoto", "alquilada"),
}

# Central: abastece a los almacenes de sucursal y a producción, y no cuelga
# de ninguna sucursal (`sucursal_id` NULL).
ALMACEN_CENTRAL = ("WH1", SEDE_CASTILLA)

# Matriz semilla (authorization.md). "*" = todo (solo admin, entornos internos).
PERMISOS = [
    ("*", "Acceso total (solo entornos internos)"),
    ("users.gestionar", "Administrar usuarios, roles y permisos"),
    (
        "personas.anonimizar",
        "Anonimizar datos de una persona — derecho de cancelación (Ley 29733)",
    ),
    (
        "personas.leer",
        "Buscar personas para asociarlas a otro registro (trabajador, proveedor "
        "natural) — solo nombre y documento, no la ficha completa",
    ),
    ("sales.crear", "Crear venta"),
    ("sales.cobrar", "Cobrar venta"),
    ("sales.leer", "Consultar ventas"),
    ("sales.anular", "Anular orden no pagada"),
    ("sales.gestionar_catalogo", "CRUD de productos comerciales y medios de pago"),
    (
        "sales.emitir_nota_credito",
        "Acreditar una venta ya cobrada con nota de crédito (RN-CPP-009)",
    ),
    ("sales.emitir_comprobante", "Reintentar la emisión de un comprobante a SUNAT"),
    (
        "sales.aplicar_descuento",
        "Autorizar un descuento manual sobre una orden (RN-COM-017)",
    ),
    ("sales.gestionar_mesas", "Configurar las mesas del salón de una sucursal"),
    ("kds.configurar", "Crear y configurar pantallas KDS"),
    ("kds.operar", "Operar KDS: cola, avance de ítems, comanda"),
    (
        "sales.entregar_pedido",
        "Registrar la entrega del pedido al cliente (PROC-OPE-002)",
    ),
    ("sales.crear_pedido", "Crear pedido (canal agente IA)"),
    ("inventory.transferir", "Despachar una transferencia entre almacenes"),
    ("inventory.recepcion", "Recepcionar mercadería y transferencias"),
    ("inventory.emitir_guia", "Emitir la guía de remisión de un traslado"),
    ("inventory.solicitar_insumos", "Crear y cancelar solicitudes de insumos"),
    ("inventory.aprobar_solicitud", "Aprobar o rechazar solicitudes de insumos"),
    ("inventory.liberar_reserva", "Liberar a mano una reserva de stock"),
    ("inventory.ajustar", "Ajustar inventario"),
    ("inventory.leer", "Consultar stock y catálogo"),
    ("inventory.gestionar_catalogo", "CRUD de artículos, categorías y SKUs"),
    ("inventory.registrar_movimiento", "Registrar movimiento de stock"),
    ("inventory.solicitar_ajuste", "Solicitar ajuste de inventario"),
    ("inventory.aprobar_ajuste", "Aprobar ajuste de inventario"),
    ("inventory.contar", "Abrir, registrar y cerrar conteos de inventario"),
    (
        "inventory.ver_stock_esperado",
        "Ver el stock esperado durante un conteo (sin esto el conteo es a ciegas)",
    ),
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
    (
        "accounting.caja_retirar",
        "Autorizar el retiro de efectivo del cajón durante el turno (RN-MDP-007)",
    ),
    (
        "accounting.caja_relevar",
        "Entregar o recibir el efectivo en la cadena de custodia: apertura, "
        "cierre y traslado a contabilidad (RN-MDP-002)",
    ),
    (
        "accounting.caja_reabrir",
        "Autorizar la reapertura de un cierre de caja para recontar (RN-MDP-005)",
    ),
    (
        "accounting.pos_administrar",
        "Inventariar los POS de pago con tarjeta: serie, código de comercio, "
        "estado y terminal de emergencia (RN-POS-009/010)",
    ),
    ("marketing.leer", "Consultar campañas, contenido, leads y encuestas"),
    ("marketing.campana_gestionar", "Crear, editar el brief, lanzar y cerrar campañas"),
    (
        "marketing.campana_aprobar",
        "Aprobar el brief de una campaña para que salga a canal (RN-MKT-003)",
    ),
    (
        "marketing.contenido_gestionar",
        "Planificar, validar y publicar piezas de contenido (RN-MKT-001/002)",
    ),
    ("marketing.lead_gestionar", "Registrar leads y atribuirlos a la venta real"),
    (
        "marketing.encuesta_gestionar",
        "Enviar la encuesta de satisfacción y registrar su respuesta (RN-COM-007)",
    ),
    ("dashboard.leer", "Consultar el dashboard gerencial (ventas, stock, caja)"),
    (
        "gerencia.gestionar_parametros_empresa",
        "Aprobar, rechazar o modificar parámetros operativos por empresa (ADR-014)",
    ),
    (
        "gerencia.decidir",
        "Firmar el acta de una decisión gerencial (RN-GER-002)",
    ),
    (
        "gerencia.leer_decisiones",
        "Consultar actas de decisión gerencial — el área ejecutora las necesita "
        "sin poder decidir (RN-GER-005)",
    ),
    ("sales.leer_clientes_externos", "Consultar clientes para análisis fuera de sales"),
    (
        "inventory.leer_solicitudes_externas",
        "Consultar el resumen de solicitudes de insumos por artículo/sucursal "
        "fuera de inventory (negociación de volumen con proveedores)",
    ),
    ("rrhh.leer", "Consultar trabajadores, contratos, nómina y documentos de RRHH"),
    ("rrhh.trabajador_gestionar", "Crear, actualizar y cesar trabajadores"),
    ("rrhh.contrato_gestionar", "Crear, firmar y finalizar contratos laborales"),
    ("rrhh.postulante_gestionar", "Gestionar postulantes y su avance en el tablero"),
    (
        "rrhh.convocatoria_gestionar",
        "Crear, publicar y cerrar convocatorias de personal (RN-RRHH-013)",
    ),
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
] + [
    # Un permiso por módulo: cada área propone parámetros de lo suyo y de nada
    # más (ADR-014 Addendum). Gerencia sigue siendo quien aprueba.
    (f"{modulo}.proponer_parametro", f"Proponer un cambio de parámetro de {modulo}")
    for modulo in MODULOS
]

ROLES = {
    "admin": ["*"],
    "supervisor": [
        # **No aprueba órdenes de compra** (decisión 2026-08-05): una OC sobre
        # el umbral es una decisión de plata y la toma un administrador. El
        # suplente en ausencia del titular es *otro administrador*, no el
        # encargado de turno — si no, el suplente termina siendo quien está
        # más cerca del proveedor.
        "purchases.leer",
        "sales.leer",
        "sales.anular",
        "sales.gestionar_catalogo",
        "sales.emitir_comprobante",
        # Acreditar devuelve plata: es acto de supervisor, no del cajero
        # que emitio (RN-CPP-009).
        "sales.emitir_nota_credito",
        "sales.entregar_pedido",
        # El descuento y el salón los autoriza el supervisor, nunca el
        # cajero que lo pide (RN-COM-017).
        "sales.aplicar_descuento",
        "sales.gestionar_mesas",
        "kds.configurar",
        "kds.operar",
        "inventory.leer",
        "inventory.gestionar_catalogo",
        # El ajuste de inventario sí lo aprueba el supervisor (decisión
        # 2026-08-05): está en el local, ve el faltante y decide en el
        # momento. Nunca quien lo solicitó — esa segregación vive en el
        # dominio (`solicitar_ajuste` ≠ `aprobar_ajuste`), no en el rol.
        "inventory.aprobar_ajuste",
        "inventory.ver_stock_esperado",
        # El encargado aprueba lo que pide su gente, no lo pide él.
        "inventory.aprobar_solicitud",
        "inventory.liberar_reserva",
        "sales.leer_clientes_externos",
        "accounting.pago_aprobar",
        "accounting.arqueo_registrar",
        "accounting.caja_retirar",
        # También opera caja cuando le toca cubrir el turno; el candado de
        # que nadie se releve a sí mismo vive en el dominio, no en el rol.
        "accounting.caja_operar",
        # El encargado entrega el fondo al abrir y recibe el efectivo al
        # cerrar: es la contraparte del cajero en la cadena de custodia
        # (RN-MDP-002), y quien autoriza recontar un cierre (RN-MDP-005).
        "accounting.caja_relevar",
        "accounting.caja_reabrir",
        # Marketing arma el brief; quien lo aprueba nunca es quien lo escribe.
        "marketing.leer",
        "marketing.campana_aprobar",
        "dashboard.leer",
        "rrhh.leer",
        "rrhh.permiso_aprobar",
        "rrhh.asistencia_marcar",
        # Lee el acta pero no la firma: decidir es de Gerencia (RN-GER-002),
        # ejecutar es del área (RN-GER-005).
        "gerencia.leer_decisiones",
    ],
    "cajero": [
        "sales.crear",
        "sales.cobrar",
        "sales.leer",
        "sales.entregar_pedido",
        "kds.operar",
        "accounting.caja_operar",
    ],
    # Cocina avanza la preparación pero NO cierra la entrega (RN-CUP-006).
    "cocinero": ["kds.operar", "sales.leer"],
    "despachador": ["kds.operar", "sales.leer", "sales.entregar_pedido"],
    # Cuenta y solicita el ajuste, pero no lo aprueba ni ve el stock
    # esperado mientras cuenta: el conteo es a ciegas (RN-INV-005/006).
    "almacenero": [
        "inventory.transferir",
        "inventory.recepcion",
        # La guía la emite el almacén (RN-GDR-002).
        "inventory.emitir_guia",
        "inventory.ajustar",
        "inventory.leer",
        "inventory.registrar_movimiento",
        "inventory.solicitar_ajuste",
        "inventory.contar",
        "inventory.solicitar_insumos",
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
        # Alta de proveedor natural liga a una persona existente.
        "personas.leer",
        # Qué se pide más y desde dónde, para negociar volumen (contrato
        # público de inventory).
        "inventory.leer_solicitudes_externas",
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
        # Contabilidad recibe el efectivo trasladado, inventaría los POS y
        # autoriza recontar un cierre (RN-MDP-002/005, RN-POS-010).
        "accounting.caja_relevar",
        "accounting.caja_reabrir",
        "accounting.pos_administrar",
        "dashboard.leer",
    ],
    "rrhh_admin": [
        "rrhh.leer",
        # Alta de trabajador liga a una persona existente.
        "personas.leer",
        "rrhh.trabajador_gestionar",
        "rrhh.contrato_gestionar",
        "rrhh.postulante_gestionar",
        "rrhh.convocatoria_gestionar",
        "rrhh.socio_gestionar",
        "rrhh.nomina_gestionar",
        "rrhh.disciplina_gestionar",
        "rrhh.permiso_solicitar",
        "rrhh.permiso_aprobar",
        "rrhh.asistencia_marcar",
        "rrhh.capacitacion_gestionar",
    ],
    # Marketing atrae demanda y cuida la marca; no se aprueba su propio
    # brief — eso lo valida Gerencia (RN-MKT-003, RN-GER-007).
    "marketing": [
        "marketing.leer",
        "marketing.campana_gestionar",
        "marketing.contenido_gestionar",
        "marketing.lead_gestionar",
        "marketing.encuesta_gestionar",
        "sales.leer_clientes_externos",
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


def _seed_organizacion(session: Session) -> None:
    """Grupo, empresa, marca licenciada, sucursales y almacén central."""
    grupo, _ = _get_or_create(session, Grupo, nombre=GRUPO)
    empresa, _ = _get_or_create(
        session,
        Empresa,
        ruc=EMPRESA_RUC,
        defaults=dict(
            grupo_id=grupo.id,
            razon_social=EMPRESA_RAZON_SOCIAL,
            domicilio_fiscal=SEDE_CASTILLA,
            tipo="operativa",
            zona_tributaria="amazonia_ley27037",
        ),
    )
    # `_get_or_create` no toca lo ya creado: el domicilio fiscal se sincroniza
    # aparte para que un seed viejo quede con la dirección vigente.
    empresa.domicilio_fiscal = SEDE_CASTILLA

    marca, _ = _get_or_create(
        session,
        Marca,
        grupo_id=grupo.id,
        nombre=MARCA,
        defaults=dict(tipo="restaurante"),
    )
    # La marca es del grupo; la empresa la opera vía licencia (data-model §1).
    _get_or_create(session, LicenciaMarca, empresa_id=empresa.id, marca_id=marca.id)

    for nombre, (direccion, tenencia) in SUCURSALES.items():
        _get_or_create(
            session,
            Sucursal,
            empresa_id=empresa.id,
            nombre=nombre,
            defaults=dict(
                marca_id=marca.id,
                direccion=direccion,
                estado="activa",
                tenencia=tenencia,
            ),
        )

    nombre_almacen, direccion_almacen = ALMACEN_CENTRAL
    _get_or_create(
        session,
        Almacen,
        empresa_id=empresa.id,
        nombre=nombre_almacen,
        defaults=dict(tipo="central", sucursal_id=None, direccion=direccion_almacen),
    )


def seed(session: Session) -> None:
    _seed_organizacion(session)

    # --- Divisas (RN-GER-010: sin divisa, ningún monto puede declarar unidad) ---
    for codigo, nombre, simbolo, decimales in DIVISAS:
        _get_or_create(
            session,
            Divisa,
            codigo=codigo,
            defaults=dict(nombre=nombre, simbolo=simbolo, decimales=decimales),
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

    # Sin `usuario_sucursal` el JWT sale sin `empresa_id` y toda operación
    # escopada responde 403 "usuario sin empresa asignada" (ADR-004): una
    # instalación nueva quedaba inutilizable hasta asignar sucursales a mano.
    for sucursal in session.scalars(select(Sucursal)):
        if session.get(UsuarioSucursal, (admin.id, sucursal.id)) is None:
            session.add(UsuarioSucursal(usuario_id=admin.id, sucursal_id=sucursal.id))

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
