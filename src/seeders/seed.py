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
from src.modules.marketing.application.plantillas import crear_plantilla
from src.modules.marketing.infrastructure.models import EncuestaPlantilla
from src.modules.reports.domain import catalogo as emisiones
from src.modules.reports.infrastructure.models import (
    Area,
    AreaMiembro,
    ReglaDestinatario,
    ReglaDistribucion,
)
from src.modules.sales.infrastructure.models import MedioPago, PromocionCupon
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
        "organizacion.gestionar",
        "Administrar grupo, empresas, marcas, licencias de marca, sucursales y "
        "almacenes — separado de `users.gestionar`: dar de alta un local no es "
        "administrar usuarios",
    ),
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
    (
        "sales.registrar_consumo_personal",
        "Autorizar la comida del personal, sin precio ni cobro (RN-COM-025)",
    ),
    ("sales.gestionar_mesas", "Configurar las mesas del salón de una sucursal"),
    (
        "sales.gestionar_clientes",
        "Administrar el padrón de clientes del grupo, incluida la carga masiva "
        "por planilla (RN-PTS-007) — distinto de registrar a alguien en caja",
    ),
    ("kds.configurar", "Crear y configurar pantallas KDS"),
    ("kds.operar", "Operar KDS: cola, avance de ítems, comanda"),
    (
        "sales.entregar_pedido",
        "Registrar la entrega del pedido al cliente (PROC-OPE-002)",
    ),
    (
        "sales.gestionar_promociones",
        "Dar de alta y terminar promociones (ADR-076) y campañas de cupón "
        "(ADR-061). No es `sales.aplicar_descuento`: crear una regla que "
        "regala margen todos los días no es firmar un descuento puntual",
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
        "Recibir el efectivo en la cadena de custodia: del cajón al "
        "encargado, del encargado a contabilidad y de ahí a disponible "
        "(RN-MDP-002). No interviene en abrir ni cerrar (RN-MDP-008)",
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
        "Enviar la encuesta de satisfacción, escribir su guion de preguntas y "
        "registrar respuestas (RN-COM-007)",
    ),
    (
        "marketing.agencia_evaluar",
        "Comparar propuestas de agencia contra hacerlo interno, con criterios "
        "ponderados (RN-MKT-006)",
    ),
    (
        "marketing.agencia_decidir",
        "Validar con cuál se va la campaña: agencia o interna. Quien evalúa no "
        "decide (RN-MKT-006, RN-GER-007)",
    ),
    ("dashboard.leer", "Consultar el dashboard gerencial (ventas, stock, caja)"),
    (
        "auditoria.leer",
        "Consultar el rastro de cambios (`audit_log`) — quién tocó qué y cuándo",
    ),
    (
        "users.resetear_pin",
        # 255 caracteres es el largo de `permiso.descripcion`, y Postgres lo
        # hace cumplir aunque SQLite no: pasarse rompe el seeder entero.
        "Devolver la cuenta de otro al PIN por defecto, obligándole a "
        "cambiarlo al entrar. Aparte de `users.gestionar`: RRHH atiende el "
        "'me olvidé el PIN' sin crear cuentas ni repartir roles, y administrar "
        "usuarios no trae de arrastre entrar como cualquiera",
    ),
    (
        "consulta.documento",
        "Consultar un DNI o RUC contra RENIEC/SUNAT para prellenar un alta. "
        "Es un permiso propio y no una consecuencia de poder crear personas: "
        "cada consulta gasta cuota del proveedor y trae datos personales de "
        "alguien que todavía no es nadie en el sistema",
    ),
    ("reports.leer", "Ver los reportes que el ERP me entregó a mí"),
    (
        "reports.leer_todo",
        "Ver todos los reportes emitidos de la empresa, no solo los propios",
    ),
    (
        "reports.leer_matriz",
        "Ver el mapa de distribución: qué hecho llega a qué área y a quién. "
        "Permiso aparte de `reports.leer` porque revela la estructura "
        "organizacional (ADR-033)",
    ),
    (
        "reports.administrar",
        "Editar áreas y reglas de distribución: decidir quién recibe qué",
    ),
    (
        "reports.escalar",
        "Elevar un reporte que no se pudo resolver en el propio nivel "
        "(RN-CTP-004)",
    ),
    (
        "reports.escalamiento_resolver",
        "Registrar lo actuado en un escalamiento y darlo por resuelto. "
        "Separado de `reports.escalar` por lo mismo que solicitar y aprobar "
        "un ajuste: quien eleva no es quien cierra",
    ),
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
    (
        "rrhh.asistencia_marcar",
        "Registrar o corregir a mano la asistencia de un trabajador desde el "
        "back-office — distinto de marcar en el pad del local",
    ),
    (
        "rrhh.asistencia_terminal",
        "Abrir el pad de marcación de asistencia de una sucursal — el pad no "
        "marca por nadie: cada marcación la firma el PIN del trabajador",
    ),
    (
        "rrhh.turno_gestionar",
        "Configurar los turnos de trabajo de una sucursal y su hora límite de "
        "marcaje de salida",
    ),
    (
        "rrhh.terminal_gestionar",
        "Autorizar o revocar el dispositivo que puede marcar asistencia en "
        "una sucursal — nunca lo tiene la cuenta de servicio del pad",
    ),
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
        # La comida del personal sale del inventario sin cobro: la firma el
        # encargado del turno, no quien la va a comer (RN-COM-025).
        "sales.registrar_consumo_personal",
        "sales.gestionar_mesas",
        # Reescribir el padrón del grupo desde una planilla no es el mismo
        # acto que registrar a alguien en el mostrador (ADR-052).
        "sales.gestionar_clientes",
        # Cortar la campaña de cupón: el derecho que la empresa se reserva
        # en los términos de la landing (ADR-061).
        "sales.gestionar_promociones",
        # **No configura pantallas KDS** (decisión 2026-08-24): dar de alta,
        # renombrar o borrar una estación cambia por dónde pasa la comanda de
        # todos los turnos, no solo del suyo. Es alta de infraestructura del
        # local, como el punto de venta (ADR-059), y la firma un
        # administrador. El supervisor opera lo que ya está montado.
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
        # También opera caja cuando le toca cubrir el turno.
        "accounting.caja_operar",
        # El encargado **recibe** el efectivo que el cajero dejó en el cajón
        # al cerrar (`en_caja → en_supervisor`, RN-MDP-002/008): es la
        # contraparte del cajero en la cadena de custodia y quien autoriza
        # recontar un cierre (RN-MDP-005). Ya no interviene en la apertura —
        # el turno lo abre el cajero solo (ADR-049).
        "accounting.caja_relevar",
        "accounting.caja_reabrir",
        # Marketing arma el brief; quien lo aprueba nunca es quien lo escribe.
        # Misma lógica con la agencia: Marketing evalúa, acá se firma.
        "marketing.leer",
        "marketing.campana_aprobar",
        "marketing.agencia_decidir",
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
    # Cuenta de servicio del pad de asistencia (ADR-065): la tablet del
    # comedor queda logueada con esto y nada más. Lo único que puede hacer es
    # listar los nombres de quienes marcan en ese local y registrar una
    # marcación firmada con el PIN del trabajador — una tablet robada no
    # marca por nadie ni ve un sueldo.
    "terminal_asistencia": ["rrhh.asistencia_terminal"],
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
        # Contabilidad audita a Compras, Almacén y las cajas de sucursal
        # (RN-CTB-009): sin el rastro, auditar es preguntar de buena fe.
        "auditoria.leer",
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
        # El horario laboral es de RRHH, no del local: el turno define contra
        # qué hora se mide la tardanza y hasta cuándo hay que marcar salida.
        "rrhh.turno_gestionar",
        # Igual criterio: autorizar el dispositivo que marca por un local es
        # alta de infraestructura del ciclo laboral, no del local en sí.
        "rrhh.terminal_gestionar",
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
        "marketing.agencia_evaluar",
        "sales.leer_clientes_externos",
    ],
}

# Todo rol que puede ser destinatario de un reporte necesita `reports.leer`
# para abrir su propia bandeja. Se agrega acá y no repitiendo la línea dentro
# de cada lista porque olvidarla en uno deja a ese rol recibiendo reportes que
# no puede abrir — y eso se descubre en producción, no en el diff.
# Las cuentas de servicio (`agente_ia`, `hub_sucursal`) quedan fuera: no hay
# nadie del otro lado que lea una bandeja.
for _rol in (
    "supervisor",
    "cajero",
    "cocinero",
    "despachador",
    "almacenero",
    "comprador",
    "jefe_cocina",
    "contador",
    "rrhh_admin",
    "marketing",
):
    ROLES[_rol].append("reports.leer")

# Consultar un documento lo necesita quien da de alta a alguien: RRHH al
# contratar, compras al registrar un proveedor, y caja al identificar a un
# cliente para su factura. `supervisor` porque también da altas. No se le da
# al resto: cada consulta gasta cuota de Factiliza y trae datos personales de
# quien todavía no es nadie en el sistema.
for _rol in ("rrhh_admin", "comprador", "cajero", "supervisor"):
    ROLES[_rol].append("consulta.documento")

# Resetear un PIN lo hace RRHH, que es quien recibe al trabajador que no
# puede entrar. `admin` ya lo tiene por el comodín. **No** se le da a
# `supervisor`: poder entrar como cualquiera de su turno rompe la
# segregación con la que está armado el ciclo de caja (ADR-025) — el mismo
# motivo por el que un encargado no se releva a sí mismo.
ROLES["rrhh_admin"].append("users.resetear_pin")

# Ver el mapa completo de distribución es de quien supervisa la operación y de
# quien la audita. **Administrarlo** —decidir quién recibe qué— queda solo en
# `admin`, por lo mismo que `purchases.aprobar`: cambiar a quién le llega un
# descuadre de caja es una decisión de gobierno, no de turno.
ROLES["supervisor"].append("reports.leer_matriz")
ROLES["contador"].append("reports.leer_matriz")

# Elevar lo puede hacer quien está en la operación y se topa con algo que no
# le corresponde resolver; cerrarlo, quien responde por el nivel. Que sean dos
# permisos evita que el mismo turno abra y cierre su propio escalamiento sin
# que nadie más lo mire.
for _rol in ("supervisor", "cajero", "jefe_cocina", "despachador", "almacenero"):
    ROLES[_rol].append("reports.escalar")
# `jefe_cocina` cierra los suyos porque RN-PRD-014 lo dice con todas las
# letras: «el jefe de cocina redacta el hallazgo y la acción tomada». Sin
# esto, una no conformidad solo la podía cerrar alguien sin `production.leer`
# — o sea, nadie: la doble puerta de RN-REP-002 también aplica al
# escalamiento, así que hace falta el permiso del módulo *y* el de resolver.
for _rol in ("supervisor", "contador", "jefe_cocina"):
    ROLES[_rol].append("reports.escalamiento_resolver")

# Qué roles componen cada área semilla. El área es «de qué me entero» y el rol
# es «qué puedo hacer»: se parecen, y por eso hay que decir el mapeo en vez de
# suponerlo. `comercial` cae en supervisión porque hoy no hay un rol comercial
# —cuando lo haya, es una línea acá.
ROLES_POR_AREA = {
    "almacen": ("almacenero",),
    "gerencia": ("admin", "supervisor"),
    "comercial": ("supervisor",),
    "cocina": ("jefe_cocina", "cocinero"),
    "caja": ("cajero",),
    "contabilidad": ("contador",),
    "rrhh": ("rrhh_admin",),
}

# Usuarios de desarrollo (username, rol). Todos con PIN 123456 y acceso a todas
# las sucursales sembradas. Prohibido en producción — ver `main()`.
USUARIOS_SEMILLA = (
    ("admin", "admin"),
    ("cajero1", "cajero"),
)


def _seed_distribucion(session: Session, roles: dict) -> None:
    """Áreas semilla y una regla por emisión, por empresa (ADR-033).

    Sin esto el módulo arranca con la matriz llena de huecos: los trece hechos
    del catálogo ocurrirían y no le llegarían a nadie. Se siembra lo que cada
    emisión declara en `areas_sugeridas`/`dinamicos_sugeridos`, que es la
    distribución que el ERP tenía cableada antes de este módulo — el punto es
    que ahora se puede cambiar sin tocar código.

    Todas las reglas se siembran **generales** (`sucursal_id` nulo): valen
    para toda la empresa hasta que alguien escriba una específica de un local,
    que le gana (RN-REP-008).

    Idempotente, como todo el seeder.
    """
    for empresa in session.scalars(select(Empresa)):
        areas = {}
        for codigo, nombre in emisiones.AREAS_BASE:
            area, _ = _get_or_create(
                session,
                Area,
                empresa_id=empresa.id,
                codigo=codigo,
                defaults=dict(nombre=nombre),
            )
            areas[codigo] = area
            for nombre_rol in ROLES_POR_AREA.get(codigo, ()):
                rol = roles.get(nombre_rol)
                if rol is None:
                    continue
                _get_or_create(
                    session,
                    AreaMiembro,
                    area_id=area.id,
                    rol_id=rol.id,
                    usuario_id=None,
                    sucursal_id=None,
                )

        for emision in emisiones.CATALOGO:
            regla, creada = _get_or_create(
                session,
                ReglaDistribucion,
                empresa_id=empresa.id,
                codigo_emision=emision.codigo,
                sucursal_id=None,
                defaults=dict(nivel=emision.nivel, canal="bandeja", activa=True),
            )
            if not creada:
                # No se reescriben los destinatarios de una regla que ya
                # existe: el seeder corre sobre bases vivas y pisar lo que un
                # administrador configuró sería deshacerle el trabajo.
                continue
            for codigo_area in emision.areas_sugeridas:
                area = areas.get(codigo_area)
                if area is not None:
                    session.add(
                        ReglaDestinatario(
                            regla_id=regla.id, tipo="area", area_id=area.id
                        )
                    )
            for dinamico in emision.dinamicos_sugeridos:
                session.add(
                    ReglaDestinatario(
                        regla_id=regla.id, tipo="dinamico", dinamico=dinamico
                    )
                )


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


# Guion de la encuesta de satisfacción que trae el ERP de fábrica
# (RN-COM-007). Ramifica a propósito: quien puntúa bajo dice **qué** falló y
# quien puntúa alto dice si recomendaría. Preguntarles las dos cosas a todos
# alarga la encuesta y baja la tasa de respuesta, que es la única métrica que
# hace que el resto sirva.
ENCUESTA_SEMILLA = "Satisfacción post-entrega"
ENCUESTA_SALUDO = "¿Cómo te fue con tu pedido? Son 2 preguntas rápidas."
ENCUESTA_PREGUNTAS = [
    {
        "codigo": "puntaje",
        "texto": "Del 1 al 5, ¿qué tal estuvo tu pedido?",
        "tipo": "escala",
        "opciones": [
            {"valor": "1", "etiqueta": "Muy malo"},
            {"valor": "2", "etiqueta": "Malo"},
            {"valor": "3", "etiqueta": "Regular"},
            {"valor": "4", "etiqueta": "Bueno"},
            {"valor": "5", "etiqueta": "Excelente"},
        ],
        "es_puntaje": True,
        "siguiente_codigo": "recomendaria",
        "saltos": {"1": "que_fallo", "2": "que_fallo", "3": "que_fallo"},
    },
    {
        "codigo": "que_fallo",
        "texto": "¿Qué fue lo que no salió bien?",
        "tipo": "opcion",
        "opciones": [
            {"valor": "comida", "etiqueta": "La comida"},
            {"valor": "atencion", "etiqueta": "La atención"},
            {"valor": "tiempo", "etiqueta": "La demora"},
            {"valor": "otro", "etiqueta": "Otra cosa"},
        ],
        "siguiente_codigo": "comentario",
    },
    {
        "codigo": "recomendaria",
        "texto": "¿Nos recomendarías a un amigo?",
        "tipo": "si_no",
        "siguiente_codigo": "comentario",
    },
    {
        "codigo": "comentario",
        "texto": "¿Quieres contarnos algo más? (o escribe '-' para terminar)",
        "tipo": "texto",
        "obligatoria": False,
    },
]


#: Con qué se cobra desde el primer arranque (RN-MDP-002). Los tres que se
#: usan en un local peruano; el resto se da de alta desde el catálogo.
MEDIOS_PAGO = [
    ("Efectivo", "efectivo"),
    ("Yape", "billetera_digital"),
    ("Tarjeta", "tarjeta_debito"),
]


def _seed_medios_pago(session: Session) -> None:
    """Sin un medio de pago no se puede cobrar: el PDV no ofrece ninguno y
    el cobro sale sin `medio_pago_id`. Misma razón que `usuario_sucursal`
    —una instalación nueva tiene que quedar operable— y por eso va acá y no
    en un seeder de demo: `docker-compose.staging.yml` corre solo éste.

    Por empresa, porque el catálogo lo es (cada una pacta su pasarela)."""
    for empresa in session.scalars(select(Empresa)):
        for nombre, tipo in MEDIOS_PAGO:
            _get_or_create(
                session,
                MedioPago,
                empresa_id=empresa.id,
                nombre=nombre,
                defaults=dict(direccion="cobro", tipo=tipo),
            )


def _seed_encuesta(session: Session, creado_por) -> None:
    """Plantilla de encuesta activa por empresa. Sin una activa, `POST
    /marketing/encuestas` responde 409 y el módulo llega inutilizable a la
    primera instalación."""
    for empresa in session.scalars(select(Empresa)):
        existente = session.scalar(
            select(EncuestaPlantilla).where(
                EncuestaPlantilla.empresa_id == empresa.id,
                EncuestaPlantilla.nombre == ENCUESTA_SEMILLA,
            )
        )
        if existente is not None:
            continue
        crear_plantilla(
            session,
            empresa_id=empresa.id,
            nombre=ENCUESTA_SEMILLA,
            saludo=ENCUESTA_SALUDO,
            preguntas=ENCUESTA_PREGUNTAS,
            creado_por=creado_por,
            activa=True,
        )


def _seed_promocion_cupon(session: Session) -> None:
    """La campaña «Queremos RE-conocerte» (ADR-061).

    Va en el seeder y no en la migración porque es un dato de negocio, no
    de esquema: una migración que inserta la campaña la resucitaría en cada
    `downgrade`/`upgrade`, incluso después de que alguien la terminó a
    propósito. `_get_or_create` no toca la fila si ya existe, así que
    re-sembrar una base donde la promoción se cortó no la vuelve a prender.
    """
    grupo = session.scalar(select(Grupo).where(Grupo.nombre == GRUPO))
    if grupo is None:
        return
    _get_or_create(
        session,
        PromocionCupon,
        grupo_id=grupo.id,
        nombre=settings.sales_promocion_cupon_nombre,
        defaults=dict(
            descuento_porcentaje=settings.sales_promocion_cupon_porcentaje,
            vigente_hasta=settings.sales_promocion_cupon_fin,
            vigencia_cupon_dias=settings.sales_promocion_cupon_vigencia_dias,
            estado="activa",
        ),
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

    # --- Usuarios semilla (PIN 123456) ---
    sucursales = list(session.scalars(select(Sucursal)))
    usuarios = {}
    for username, nombre_rol in USUARIOS_SEMILLA:
        usuario, _ = _get_or_create(
            session,
            Usuario,
            username=username,
            defaults=dict(pin_hash=hash_pin("123456"), tipo="humano", activo=True),
        )
        usuarios[username] = usuario
        if session.get(UsuarioRol, (usuario.id, roles[nombre_rol].id)) is None:
            session.add(
                UsuarioRol(usuario_id=usuario.id, rol_id=roles[nombre_rol].id)
            )

        # Sin `usuario_sucursal` el JWT sale sin `empresa_id` y toda operación
        # escopada responde 403 "usuario sin empresa asignada" (ADR-004): una
        # instalación nueva quedaba inutilizable hasta asignar sucursales a mano.
        for sucursal in sucursales:
            if session.get(UsuarioSucursal, (usuario.id, sucursal.id)) is None:
                session.add(
                    UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id)
                )

    admin = usuarios["admin"]

    _seed_medios_pago(session)
    _seed_encuesta(session, admin.id)
    _seed_distribucion(session, roles)
    _seed_promocion_cupon(session)

    session.commit()
    print("Seed OK (idempotente). Usuarios PIN 123456: " + ", ".join(
        f"{u}/{r}" for u, r in USUARIOS_SEMILLA
    ))


def main() -> None:
    if settings.environment.lower() in ("production", "prod"):
        sys.exit("ABORTADO: el seeder está prohibido en producción.")
    with SessionLocal() as session:
        seed(session)


if __name__ == "__main__":
    main()
