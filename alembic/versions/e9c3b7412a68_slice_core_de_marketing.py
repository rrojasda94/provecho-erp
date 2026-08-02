"""slice core de marketing: campana, contenido, lead, material y encuesta

Primer código del módulo `marketing` (data-model.md §8d), que hasta hoy
existía solo como README de spec.

`encuesta_satisfaccion` vivía descrita en §6 (ventas) porque su disparador
es `sales.venta_entregada`, pero la tabla pertenece a marketing: quien
decide a qué venta entregada encuestar es Marketing, no la caja.

`campana.aprobada_por` apunta a `usuario`, no a `decision_gerencial`: ni
`presupuesto_anual` ni `decision_gerencial` existen como tablas todavía
(ver ROADMAP → Deuda técnica → marketing). Cuando existan, la referencia
se agrega sin migrar datos: hoy no hay campañas cargadas.

Revision ID: e9c3b7412a68
Revises: a7f2c81e4b95
Create Date: 2026-08-01 18:40:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e9c3b7412a68"
down_revision = "a7f2c81e4b95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campana",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("empresa_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("marca_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "notoriedad",
                "impulso_venta",
                "lanzamiento",
                "medios",
                "evento",
                name="tipo_campana",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("objetivo", sa.String(length=255), nullable=True),
        sa.Column("publico_objetivo", sa.String(length=255), nullable=True),
        sa.Column("presupuesto", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("kpi", sa.String(length=255), nullable=True),
        sa.Column("canal", sa.String(length=50), nullable=False),
        sa.Column(
            "estado",
            sa.Enum(
                "brief",
                "aprobada",
                "en_curso",
                "cerrada",
                name="estado_campana",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("creado_por", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("aprobada_por", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        sa.ForeignKeyConstraint(["marca_id"], ["marca.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["aprobada_por"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", "nombre"),
        sa.UniqueConstraint("idempotency_key"),
    )

    op.create_table(
        "pieza_contenido",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("campana_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("marca_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("titulo", sa.String(length=150), nullable=False),
        sa.Column("canal", sa.String(length=50), nullable=False),
        sa.Column("fecha_publicacion", sa.Date(), nullable=False),
        sa.Column("pertinente_marca", sa.Boolean(), nullable=False),
        sa.Column("uso_marca_validado", sa.Boolean(), nullable=False),
        sa.Column(
            "estado",
            sa.Enum(
                "planificada",
                "publicada",
                "descartada",
                name="estado_pieza_contenido",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "metricas",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("creado_por", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campana_id"], ["campana.id"]),
        sa.ForeignKeyConstraint(["marca_id"], ["marca.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "lead",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("campana_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("canal", sa.String(length=50), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "contacto",
                "visita",
                "cupon",
                "registro",
                name="tipo_lead",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("contacto", sa.String(length=120), nullable=True),
        sa.Column("cliente_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("venta_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campana_id"], ["campana.id"]),
        sa.ForeignKeyConstraint(["cliente_id"], ["cliente.id"]),
        sa.ForeignKeyConstraint(["venta_id"], ["venta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )

    op.create_table(
        "implementacion_material_sucursal",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("campana_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sucursal_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("verificado_por", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("completa", sa.Boolean(), nullable=False),
        sa.Column("incidencia", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campana_id"], ["campana.id"]),
        sa.ForeignKeyConstraint(["sucursal_id"], ["sucursal.id"]),
        sa.ForeignKeyConstraint(["verificado_por"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campana_id", "sucursal_id", "fecha"),
    )

    op.create_table(
        "encuesta_satisfaccion",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("venta_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("cliente_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "canal",
            sa.Enum("pos", "whatsapp", "link", name="canal_encuesta", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "fecha_envio", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("fecha_respuesta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("puntaje", sa.Integer(), nullable=True),
        sa.Column("comentario", sa.String(length=500), nullable=True),
        sa.Column(
            "estado",
            sa.Enum(
                "enviada",
                "respondida",
                "expirada",
                name="estado_encuesta",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("enviada_por", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["venta_id"], ["venta.id"]),
        sa.ForeignKeyConstraint(["cliente_id"], ["cliente.id"]),
        sa.ForeignKeyConstraint(["enviada_por"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("venta_id"),
    )


def downgrade() -> None:
    op.drop_table("encuesta_satisfaccion")
    op.drop_table("implementacion_material_sucursal")
    op.drop_table("lead")
    op.drop_table("pieza_contenido")
    op.drop_table("campana")
