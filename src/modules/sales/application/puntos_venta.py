"""Alta y edición de puntos de venta: la caja de una sucursal.

Hasta ahora esto solo existía en el seeder, así que una sucursal nueva no
podía vender hasta que alguien corriera un script contra la base. Acá vive
el alta real, con las reglas que el seeder daba por buenas porque escribía
las series a mano:

- La **serie no se repite dentro de la empresa** (RN-CPP-007): el
  correlativo de un comprobante es único por `(empresa, serie)`, así que dos
  cajas que compartan una serie se pisan al emitir.
- La **nota de crédito numera en serie propia** (RN-CPP-009): las cuatro
  series de una misma caja tienen que ser distintas entre sí.
- La **autoatención cobra por adelantado** (RN-POS-005): `web` y `kiosko` no
  pueden quedar en `al_finalizar`, porque no hay quién persiga al cliente.

Lo que la unicidad de serie **no** hace es vivir en el esquema: `punto_venta`
no tiene `empresa_id` (se alcanza por `sucursal`) y la regla abarca cuatro
columnas des-pivoteadas. El candado que de verdad impide emitir un duplicado
ya existe y está en la otra punta: `UNIQUE(comprobante.empresa_id, serie,
correlativo)`. Ver ADR-059.

El alcance por tenant no vive acá sino en el router (ADR-004).
"""

import re
import uuid

from sqlalchemy.orm import Session

from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.infrastructure.models import PuntoVenta
from src.modules.sales.infrastructure.repositories import PuntoVentaRepo
from src.shared import auditoria

CANALES = ("trabajador", "web", "kiosko")
POLITICAS_PAGO = ("adelantado", "al_finalizar")
MODALIDADES = ("mesa", "takeout", "delivery")
# Canales sin cajero delante: nadie cobra al final si el cliente se va
# (RN-POS-005).
CANALES_AUTOATENCION = ("web", "kiosko")

# Serie SUNAT: letra del tipo de comprobante + tres alfanuméricos. `B` cubre
# boleta y su nota de crédito (B001, BC01); `F`, factura y la suya.
SERIE = re.compile(r"^[BF][A-Z0-9]{3}$")
CAMPOS_SERIE = ("serie_boleta", "serie_factura", "serie_nc_boleta", "serie_nc_factura")

EDITABLES = (
    "canal",
    "hardware_id",
    "politica_pago",
    "modalidades_habilitadas",
    *CAMPOS_SERIE,
)


def _normalizar_serie(valor: str | None, campo: str) -> str | None:
    if valor is None:
        return None
    serie = valor.strip().upper()
    if not SERIE.match(serie):
        raise ReglaNegocio(
            f"{campo}: '{valor}' no es una serie válida — se espera una letra "
            "B o F y tres caracteres, por ejemplo B001 o FC01"
        )
    return serie


def _validar_canal(
    *,
    canal: str,
    politica_pago: str,
    hardware_id: str | None,
    modalidades: list | None,
) -> None:
    if canal not in CANALES:
        raise ReglaNegocio(f"canal inválido: '{canal}'")
    if politica_pago not in POLITICAS_PAGO:
        raise ReglaNegocio(f"política de pago inválida: '{politica_pago}'")
    if canal in CANALES_AUTOATENCION and politica_pago != "adelantado":
        raise ReglaNegocio(
            f"un punto de venta '{canal}' cobra por adelantado: no hay cajero "
            "que persiga el pago al final (RN-POS-005)"
        )
    if canal == "web" and hardware_id:
        raise ReglaNegocio("un punto de venta web no tiene hardware asociado")
    if modalidades is not None and (
        not modalidades or set(modalidades) - set(MODALIDADES)
    ):
        raise ReglaNegocio(
            f"modalidades_habilitadas: se esperan una o más de {', '.join(MODALIDADES)}"
        )


def _validar_series(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    series: dict[str, str | None],
    excluir_id: uuid.UUID | None = None,
) -> None:
    for campo in ("serie_boleta", "serie_factura"):
        if not series.get(campo):
            raise ReglaNegocio(f"{campo} es obligatoria: sin ella la caja no emite")

    propias = [s for s in series.values() if s]
    if len(set(propias)) != len(propias):
        raise ReglaNegocio(
            "las series del punto de venta tienen que ser distintas entre sí: "
            "la nota de crédito numera aparte del documento que corrige "
            "(RN-CPP-009)"
        )
    ocupadas = PuntoVentaRepo(session).series_en_uso(empresa_id, excluir_id)
    choque = sorted(set(propias) & ocupadas)
    if choque:
        raise Conflicto(
            f"la empresa ya usa la serie {', '.join(choque)} en otra caja; "
            "el correlativo es único por empresa y serie (RN-CPP-007)"
        )


def _empresa_de(session: Session, sucursal_id: uuid.UUID) -> uuid.UUID:
    empresa_id = PuntoVentaRepo(session).empresa_de_sucursal(sucursal_id)
    if empresa_id is None:
        raise NoEncontrado("sucursal no encontrada")
    return empresa_id


def crear_punto_venta(
    session: Session,
    *,
    sucursal_id: uuid.UUID,
    canal: str,
    serie_boleta: str,
    serie_factura: str,
    politica_pago: str,
    serie_nc_boleta: str | None = None,
    serie_nc_factura: str | None = None,
    hardware_id: str | None = None,
    modalidades_habilitadas: list | None = None,
    actor_id: uuid.UUID | None = None,
) -> PuntoVenta:
    empresa_id = _empresa_de(session, sucursal_id)
    series = {
        "serie_boleta": _normalizar_serie(serie_boleta, "serie_boleta"),
        "serie_factura": _normalizar_serie(serie_factura, "serie_factura"),
        "serie_nc_boleta": _normalizar_serie(serie_nc_boleta, "serie_nc_boleta"),
        "serie_nc_factura": _normalizar_serie(serie_nc_factura, "serie_nc_factura"),
    }
    _validar_canal(
        canal=canal,
        politica_pago=politica_pago,
        hardware_id=hardware_id,
        modalidades=modalidades_habilitadas,
    )
    _validar_series(session, empresa_id=empresa_id, series=series)
    punto = PuntoVentaRepo(session).add(
        PuntoVenta(
            sucursal_id=sucursal_id,
            canal=canal,
            hardware_id=hardware_id,
            politica_pago=politica_pago,
            modalidades_habilitadas=modalidades_habilitadas,
            **series,
        )
    )
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="punto_venta",
        entidad_id=punto.id,
        accion="crear",
        sucursal_id=sucursal_id,
        empresa_id=empresa_id,
        datos_despues={"canal": canal, **{k: v for k, v in series.items() if v}},
    )
    return punto


def editar_punto_venta(
    session: Session,
    punto_venta_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    **campos,
) -> PuntoVenta:
    """No se cambia de sucursal: la caja es del local, y sus comprobantes y
    aperturas ya emitidos cuelgan de ahí. Cambiar la serie sí se permite —
    `comprobante.serie` es una copia congelada al emitir, así que lo ya
    emitido no se toca y el correlativo nuevo arranca donde corresponda.
    """
    repo = PuntoVentaRepo(session)
    punto = repo.get(punto_venta_id)
    if punto is None:
        raise NoEncontrado("punto de venta no encontrado")
    empresa_id = _empresa_de(session, punto.sucursal_id)

    for campo in CAMPOS_SERIE:
        if campo in campos:
            campos[campo] = _normalizar_serie(campos[campo], campo)
    propuesto = {campo: campos.get(campo, getattr(punto, campo)) for campo in EDITABLES}
    _validar_canal(
        canal=propuesto["canal"],
        politica_pago=propuesto["politica_pago"],
        hardware_id=propuesto["hardware_id"],
        modalidades=propuesto["modalidades_habilitadas"],
    )
    _validar_series(
        session,
        empresa_id=empresa_id,
        series={campo: propuesto[campo] for campo in CAMPOS_SERIE},
        excluir_id=punto.id,
    )

    antes = {}
    for campo in EDITABLES:
        if campo not in campos or getattr(punto, campo) == campos[campo]:
            continue
        antes[campo] = str(getattr(punto, campo))
        setattr(punto, campo, campos[campo])
    if antes:
        auditoria.registrar(
            session,
            usuario_id=actor_id,
            entidad="punto_venta",
            entidad_id=punto.id,
            accion="editar",
            sucursal_id=punto.sucursal_id,
            empresa_id=empresa_id,
            datos_antes=antes,
            datos_despues={c: str(getattr(punto, c)) for c in antes},
        )
    return punto
