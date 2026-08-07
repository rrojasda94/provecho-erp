"""Carga los valores propuestos de `parametro_empresa` (ADR-014).

Deja cada uno en estado **`propuesto`**, nunca `vigente`: el mecanismo
completo de ADR-014 es que un parámetro no surte efecto hasta que Gerencia
lo aprueba, y un seeder que sembrara valores vigentes lo saltearía por la
puerta de atrás. Después de correr esto, los parámetros aparecen en
`/gerencia/parametros` esperando aprobación.

El sustento de cada valor —de dónde sale, qué pasa si está mal y cuándo
revisarlo— vive en `docs/gerencia/propuesta-parametros-operativos.md`. Acá
va solo el resumen que Gerencia ve en pantalla al decidir.

Idempotente: no vuelve a proponer un código que ya tenga una fila en
cualquier estado. Reproponer sobre una propuesta rechazada sería insistir
con lo mismo sin que nadie lo haya pedido.

Correr: `python -m src.seeders.parametros`
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.modules.users.infrastructure.models import Empresa, Usuario
from src.shared.models import ParametroEmpresa

# Rangos salariales como **múltiplo de la RMV**, no como monto fijo: la RMV
# cambia por decreto y un monto en soles queda desactualizado en silencio.
# Ver la propuesta para los siete perfiles y por qué son esos siete.
RANGOS_SALARIALES = {
    "limpieza_apoyo": ("1.00", "1.10", "Puesto de entrada, sin requisito de experiencia"),
    "atencion_cliente": ("1.05", "1.30", "Maneja dinero y es la cara del local"),
    "cocina": ("1.10", "1.45", "Oficio con curva real; el techo saca hora punta solo"),
    "chofer_repartidor": ("1.10", "1.35", "Licencia vigente, vehículo y cobranza en ruta"),
    "encargado_almacen": ("1.40", "1.80", "Responde por el inventario del grupo"),
    "encargado_compras": ("1.50", "2.00", "Negocia con proveedores y maneja caja chica"),
    "jefe_comercial": ("2.00", "2.80", "Jefatura con metas y personal a cargo"),
}

PROPUESTAS: list[tuple[str, str, dict, str | None, str]] = [
    (
        "purchases",
        "oc_umbral",
        {"monto": "2000.00", "divisa": "PEN"},
        "S/ 2000.00",
        "Confirma el valor semilla. Es el de menor base propia: no hay "
        "histórico de OC todavía. Cae en el rango correcto —cuatro veces la "
        "caja chica y sobre un pedido semanal de dos locales— y mantenerlo no "
        "cambia ningún comportamiento actual. Revisar con 3 meses de OC reales.",
    ),
    (
        "sales",
        "margen_minimo",
        {"porcentaje": 60},
        None,
        "Food cost objetivo 32 % + empaque 3 % + comisión de medio de pago "
        "4 % = 39 % de costo variable → 61 % de margen. Se propone 60 % como "
        "piso, no como objetivo. La exoneración de IGV por Amazonía "
        "(RN-IMP-001) lo vuelve alcanzable: el precio no carga 18 %.",
    ),
    (
        "inventory",
        "margen_error_ajuste",
        {"porcentaje": 2, "piso": "20.00", "divisa": "PEN"},
        "2 % o S/ 20.00",
        "Confirma el 2 % semilla y le agrega un piso absoluto. Un margen solo "
        "porcentual castiga a las categorías baratas: 2 % de S/ 30 en "
        "servilletas son 60 céntimos y cualquier diferencia escala, hasta que "
        "la alerta se vuelve ruido que nadie mira. El piso se evalúa contra la "
        "diferencia valorizada al costo promedio del artículo.",
    ),
    (
        "purchases",
        "monto_caja_chica",
        {"monto": "500.00", "divisa": "PEN", "reposicion_en": "150.00"},
        "S/ 500.00",
        "Cubre una semana de imprevistos con proveedor informal y ni un sol "
        "más: un fondo grande deja de ser emergencia y se vuelve una vía de "
        "compra paralela que esquiva la OC. Se repone al bajar de S/ 150 para "
        "que nadie se quede sin fondo un sábado.",
    ),
    (
        "accounting",
        "plazo_envio_comprobante",
        {"dias_habiles": 5, "desde": "cierre_de_mes"},
        None,
        "Plazo **interno**, no la fecha de SUNAT: el vencimiento real depende "
        "del último dígito del RUC y se lee del cronograma del año. 5 días "
        "hábiles le dejan al contador ~1 semana de holgura sea cual sea el "
        "dígito, y es exigible porque no depende de terceros.",
    ),
    (
        "sales",
        "incentivo_meta_pct",
        {"porcentaje": 3, "base": "excedente_sobre_meta", "techo_rmv": "0.5"},
        None,
        "Bono **grupal por sucursal**, no comisión individual: en un local de "
        "comida la venta es de equipo y una comisión por ticket hace que el "
        "cajero compita por el cliente que más gasta y apure el guion. Sobre "
        "el excedente y no sobre la venta total, porque lo demás paga por la "
        "venta que igual iba a ocurrir. Requiere aprobación conjunta de "
        "Comercial + RRHH + Gerencia (política comercial §3).",
    ),
]

PROPUESTAS += [
    (
        "rrhh",
        f"rango_salarial_{perfil}",
        {"minimo_rmv": minimo, "maximo_rmv": maximo},
        f"{minimo} – {maximo} RMV",
        f"{razon}. Expresado en múltiplos de RMV y no en soles: la RMV cambia "
        "por decreto y un monto fijo queda desactualizado sin que nadie lo "
        "note. **Confirmar la RMV vigente antes de aprobar** — "
        "`marco-legal-laboral.md` la registra en S/ 1,130 con nota de "
        "verificar. Falta contrastar contra avisos reales de Tarapoto.",
    )
    for perfil, (minimo, maximo, razon) in RANGOS_SALARIALES.items()
]


def sembrar_propuestas(session: Session) -> int:
    """Propone los valores para cada empresa. Devuelve cuántos creó."""
    admin = session.scalar(select(Usuario).where(Usuario.username == "admin"))
    if admin is None:
        raise RuntimeError("no existe el usuario admin: correr antes el seeder base")

    creados = 0
    for empresa in session.scalars(select(Empresa)):
        for modulo, codigo, valor, display, motivo in PROPUESTAS:
            ya_existe = session.scalar(
                select(ParametroEmpresa).where(
                    ParametroEmpresa.empresa_id == empresa.id,
                    ParametroEmpresa.modulo == modulo,
                    ParametroEmpresa.codigo == codigo,
                )
            )
            if ya_existe is not None:
                continue
            session.add(
                ParametroEmpresa(
                    empresa_id=empresa.id,
                    modulo=modulo,
                    codigo=codigo,
                    valor=valor,
                    valor_display=display,
                    estado="propuesto",
                    propuesto_por_id=admin.id,
                    motivo=motivo,
                )
            )
            creados += 1
    return creados


def main() -> None:
    with SessionLocal() as session:
        creados = sembrar_propuestas(session)
        session.commit()
    print(
        f"Propuestas de parámetro creadas: {creados}. "
        "Gerencia las aprueba en /gerencia/parametros."
    )


if __name__ == "__main__":
    main()
