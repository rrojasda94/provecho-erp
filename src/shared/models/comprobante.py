"""Comprobante: entidad transversal — sirve a `sales` emitiendo y a
`purchases`/`accounting` recibiendo. Vive en `shared`, no en un módulo
dueño único (Clean Architecture: ningún módulo importa el dominio de
otro).

`compra_id` queda sin FK a propósito — referencia `orden_compra.id`, dominio
de `purchases`; un FK cruzaría el módulo dueño único (CLAUDE.md: nunca
importar el dominio de otro módulo), mismo criterio que
`accounting.MovimientoDinero.proveedor_id`/`orden_compra_id`. El conjunto
válido de `tipo` según `direccion` (RN-CPP-001/002) se valida en el
dominio, no en el esquema.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class Comprobante(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "comprobante"
    __table_args__ = (
        # La unicidad de un comprobante no es una sola: depende de quién lo
        # emitió, y hasta 2026-08-30 acá había una constraint global
        # `(empresa, serie, correlativo)` que las mezclaba.
        #
        # El nuestro no se repite dentro de la empresa. El del proveedor no se
        # repite dentro de **ese proveedor**: dos proveedores distintos emiten
        # F001-1 el mismo día y los dos son válidos. Con una sola constraint,
        # la primera factura recibida bloqueaba ese número en toda la empresa
        # —incluida nuestra propia serie, que es la que se declara a SUNAT—.
        Index(
            "uq_comprobante_emitido",
            "empresa_id",
            "serie",
            "correlativo",
            unique=True,
            sqlite_where=text("direccion = 'emitido'"),
            postgresql_where=text("direccion = 'emitido'"),
        ),
        # `emisor_num_doc IS NOT NULL` explícito y no confiado al
        # comportamiento de NULL: un `ticket_compra` informal puede no
        # identificar al emisor, y ahí no hay unicidad que imponer. Escribirlo
        # deja dicho que es a propósito. (`NULLS NOT DISTINCT` sería lo
        # equivalente en Postgres 15+, pero los tests corren sobre SQLite.)
        Index(
            "uq_comprobante_recibido",
            "empresa_id",
            "emisor_num_doc",
            "serie",
            "correlativo",
            unique=True,
            sqlite_where=text(
                "direccion = 'recibido' AND emisor_num_doc IS NOT NULL"
            ),
            postgresql_where=text(
                "direccion = 'recibido' AND emisor_num_doc IS NOT NULL"
            ),
        ),
        # Una venta dividida tiene varios comprobantes: se busca por
        # (venta, grupo) al cobrar cada cuenta.
        Index("ix_comprobante_venta_grupo", "venta_id", "grupo_cobro"),
        # La ficha de una OC pide sus comprobantes por acá, y `compra_id` no
        # tiene FK (es de otro módulo) así que tampoco tenía índice.
        Index("ix_comprobante_compra_id", "compra_id"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    # Si direccion=emitido.
    venta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venta.id"), nullable=True
    )
    # Cuenta de la venta que este comprobante documenta (RN-COM-018). Una
    # venta dividida entre varios pagadores emite un comprobante por grupo,
    # por eso `venta_id` dejó de ser único. Vale 1 en toda venta sin dividir.
    grupo_cobro: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    # Receptor tecleado en caja cuando no hay `cliente` registrado: el PDV
    # pide DNI o RUC al cobrar y eso decide boleta/factura (RN-CPP-003).
    # Cuando vienen informados ganan sobre `venta.cliente_id` al armar el
    # envío a SUNAT; si están vacíos se usa el cliente de la venta como antes.
    receptor_num_doc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    receptor_nombre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Si direccion=recibido — FK diferida (purchases sin tablas de recepción aún).
    compra_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # Origen de la serie si direccion=emitido.
    punto_venta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("punto_venta.id"), nullable=True
    )
    direccion: Mapped[str] = mapped_column(
        Enum("emitido", "recibido", name="direccion_comprobante", native_enum=False)
    )
    tipo: Mapped[str] = mapped_column(
        Enum(
            "boleta",
            "factura",
            "nc",
            "rhe",
            "ticket_compra",
            name="tipo_comprobante",
            native_enum=False,
        )
    )
    # Snapshot de punto_venta.serie_boleta/serie_factura al emitir —
    # inmutable aunque el punto de venta cambie de serie después.
    serie: Mapped[str] = mapped_column(String(10))
    correlativo: Mapped[int] = mapped_column(Integer)
    sustento: Mapped[str] = mapped_column(
        Enum(
            "efectivo",
            "voucher_medio_pago",
            "movimiento_bancario",
            "contrato_credito",
            name="sustento_comprobante",
            native_enum=False,
        )
    )
    # --- Documento recibido (direccion="recibido") ---------------------------
    # RUC (11) o DNI (8, un RHE de persona natural) de QUIEN EMITIÓ el papel.
    # En un comprobante emitido queda NULL: el emisor somos nosotros y eso ya
    # lo dice `empresa_id`. Es la columna que hace posible partir la unicidad
    # por dirección — sin ella, dos proveedores no pueden tener el mismo
    # F001-1.
    emisor_num_doc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    # La fecha que trae el papel del proveedor, que es la que manda en el
    # Registro de Compras — no la del día en que alguien lo tecleó, que es lo
    # único que había (`created_at`). `Date` y no `DateTime`: una factura
    # declara un día, no una hora.
    #
    # Solo se llena en `direccion="recibido"`. Para un comprobante emitido la
    # fecha del documento se deriva de `created_at` en hora del negocio
    # (`sales.application.comprobantes.fecha_emision`), y tener dos verdades
    # sobre lo mismo es peor que no tener ninguna.
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Importe total del documento, IGV incluido. Hasta ahora el importe de una
    # compra se tomaba implícitamente de `orden_compra.total`, que es la base
    # de lo recibido: una factura que difiera —por IGV, redondeo o un flete
    # que la OC no tenía— no se podía representar.
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    # ¿La operación lleva IGV? NULL = lo decide el default de la empresa
    # (`shared.tributos`). Se marca donde alguien tiene el documento delante:
    # al cobrar, en el PDV, y al dar conformidad a la factura del proveedor.
    # Existe porque el régimen de la empresa no alcanza: Grupo Majambo vende
    # exonerado por Amazonía y aun así compra con IGV a proveedores de fuera
    # de la región, crédito fiscal que sin esta columna no se registraba.
    # Vive acá y no en `venta` ni en `orden_compra` porque **el IGV nace con
    # el comprobante**: el crédito fiscal se toma con el comprobante anotado
    # y el débito con el comprobante emitido (ADR-081).
    gravado_igv: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # --- Nota de crédito (tipo="nc", catálogo 09 de SUNAT) -------------------
    # A qué comprobante corrige. Una NC sin documento afectado no existe:
    # SUNAT la rechaza y contablemente no significa nada.
    afecta_comprobante_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comprobante.id"), nullable=True
    )
    motivo_nc: Mapped[str | None] = mapped_column(String(2), nullable=True)
    motivo_nc_descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Qué se devolvió, cuando la NC es parcial: lista de
    # {venta_item_id, cantidad}. NULL = la NC cubre el comprobante entero.
    # JSONB y no tabla propia porque la fuente de verdad de las líneas sigue
    # siendo `venta_item`: esto solo congela cuánto de cada una se acreditó.
    detalle_nc: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    # Se llena en el comprobante AFECTADO cuando una NC total suya es
    # aceptada. Que exista es lo que impide cobrarlo o notacreditarlo otra
    # vez, y lo que habilita reemitir el corregido.
    anulado_por_nc_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comprobante.id"), nullable=True
    )
    # --- Emisión electrónica (solo direccion=emitido) ------------------------
    # `pendiente` nace al cobrar; la cola lo lleva a `aceptado`/`rechazado`.
    # `error` = fallo de transporte, reintentable. Un comprobante recibido
    # (compra) se queda en `no_aplica`: no lo emitimos nosotros.
    estado_emision: Mapped[str] = mapped_column(
        Enum(
            "no_aplica",
            "pendiente",
            "aceptado",
            "rechazado",
            "error",
            name="estado_emision_comprobante",
            native_enum=False,
        ),
        default="no_aplica",
    )
    # Hash del documento devuelto por el proveedor (respaldo ante SUNAT).
    hash_proveedor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Motivo del último rechazo/error, para mostrar sin abrir el JSON.
    detalle_emision: Mapped[str | None] = mapped_column(Text, nullable=True)
    intentos_emision: Mapped[int] = mapped_column(Integer, default=0)
    respuesta_proveedor: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
