"""encuesta por nodos, evaluación de agencia y métricas de campaña

Cierra cuatro deudas declaradas del módulo marketing (ROADMAP → Deuda
técnica → marketing):

1. **Encuesta sin envío real.** `encuesta_plantilla` + `encuesta_pregunta`
   convierten el guion en dato: la conversación avanza nodo por nodo y cada
   respuesta decide la siguiente pregunta. `encuesta_satisfaccion` suma el
   estado de esa conversación (en qué nodo está, a qué teléfono se mandó,
   hasta cuándo vale) porque una respuesta suelta que llega por WhatsApp tres
   horas después no se puede interpretar sin él.
2. **Evaluación de agencia (RN-MKT-006).** `evaluacion_agencia` +
   `opcion_agencia`: criterios ponderados congelados antes de ver las
   propuestas, y la opción interna compitiendo con las agencias.
3. **Eventos sin consumidor.** `campana_metrica` es el acumulado que
   mantienen los listeners del propio módulo.
4. **Contenido sin adjunto.** No agrega tabla: cuelga de `archivo`
   (`src/shared/models/archivo.py`), que ya es polimórfico.

`token_publico` y `fecha_expiracion` nacen NOT NULL pero se agregan
nullables y se rellenan: si hubiera encuestas cargadas, una columna
obligatoria sin valor por defecto haría fallar la migración en la primera
fila. Las filas viejas quedan con `plantilla_id` NULL y se responden con un
puntaje suelto, como antes.

Revision ID: c1f80b6a2d34
Revises: e7c390a5b41f
Create Date: 2026-08-08 10:20:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c1f80b6a2d34"
down_revision = "e7c390a5b41f"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "encuesta_plantilla",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("empresa_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("marca_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("saludo", sa.String(length=300), nullable=False),
        sa.Column("despedida", sa.String(length=300), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.Column("creado_por", sa.Uuid(as_uuid=True), nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        sa.ForeignKeyConstraint(["marca_id"], ["marca.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", "nombre"),
    )

    op.create_table(
        "encuesta_pregunta",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("plantilla_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("codigo", sa.String(length=30), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("texto", sa.String(length=300), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "escala",
                "opcion",
                "si_no",
                "texto",
                name="tipo_pregunta_encuesta",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("opciones", _JSON, nullable=True),
        sa.Column("siguiente_codigo", sa.String(length=30), nullable=True),
        sa.Column("saltos", _JSON, nullable=True),
        sa.Column("es_puntaje", sa.Boolean(), nullable=False),
        sa.Column("obligatoria", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["plantilla_id"], ["encuesta_plantilla.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Nombre explícito: la convención nombra por la primera columna y las
        # dos empiezan por `plantilla_id`, así que se pisarían.
        sa.UniqueConstraint("plantilla_id", "codigo", name="uq_encuesta_pregunta_codigo"),
        sa.UniqueConstraint("plantilla_id", "orden", name="uq_encuesta_pregunta_orden"),
    )

    # --- Estado de la conversación en la encuesta --------------------------
    op.add_column(
        "encuesta_satisfaccion",
        sa.Column("plantilla_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "encuesta_satisfaccion",
        sa.Column("pregunta_actual_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "encuesta_satisfaccion", sa.Column("destino", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "encuesta_satisfaccion",
        sa.Column(
            "conversacion_abierta",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "encuesta_satisfaccion",
        sa.Column("token_publico", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "encuesta_satisfaccion",
        sa.Column("fecha_expiracion", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "encuesta_satisfaccion",
        sa.Column("mensaje_externo_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "encuesta_satisfaccion",
        sa.Column("error_envio", sa.String(length=255), nullable=True),
    )
    op.execute(
        "UPDATE encuesta_satisfaccion "
        "SET token_publico = replace(gen_random_uuid()::text, '-', ''), "
        "    fecha_expiracion = fecha_envio + interval '72 hours' "
        "WHERE token_publico IS NULL"
    )
    op.alter_column("encuesta_satisfaccion", "token_publico", nullable=False)
    op.alter_column("encuesta_satisfaccion", "fecha_expiracion", nullable=False)
    op.create_unique_constraint(
        "uq_encuesta_satisfaccion_token_publico",
        "encuesta_satisfaccion",
        ["token_publico"],
    )
    # El webhook busca la encuesta abierta por teléfono en cada mensaje: sin
    # índice es un scan de toda la tabla por cada "sí" que llega.
    op.create_index(
        "ix_encuesta_satisfaccion_destino", "encuesta_satisfaccion", ["destino"]
    )
    # Nombres según la convención del proyecto
    # (`fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`), para
    # que el esquema real coincida con el que genera `Base.metadata`.
    op.create_foreign_key(
        "fk_encuesta_satisfaccion_plantilla_id_encuesta_plantilla",
        "encuesta_satisfaccion",
        "encuesta_plantilla",
        ["plantilla_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_encuesta_satisfaccion_pregunta_actual_id_encuesta_pregunta",
        "encuesta_satisfaccion",
        "encuesta_pregunta",
        ["pregunta_actual_id"],
        ["id"],
    )

    op.create_table(
        "encuesta_respuesta",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("encuesta_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("pregunta_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("valor", sa.String(length=500), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["encuesta_id"], ["encuesta_satisfaccion.id"]),
        sa.ForeignKeyConstraint(["pregunta_id"], ["encuesta_pregunta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("encuesta_id", "pregunta_id"),
    )

    # --- Evaluación agencia vs. interna (RN-MKT-006) -----------------------
    op.create_table(
        "evaluacion_agencia",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("campana_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("objetivo", sa.String(length=255), nullable=False),
        sa.Column(
            "presupuesto_referencia", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("criterios", _JSON, nullable=False),
        sa.Column(
            "estado",
            sa.Enum(
                "borrador",
                "evaluada",
                "decidida",
                name="estado_evaluacion_agencia",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("opcion_elegida_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("decidida_por", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("fecha_decision", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.Column("creado_por", sa.Uuid(as_uuid=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["campana_id"], ["campana.id"]),
        sa.ForeignKeyConstraint(["decidida_por"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "opcion_agencia",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("evaluacion_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "agencia", "interna", name="tipo_opcion_agencia", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        # Sin FK a `proveedor`: es dominio de `purchases` y atar los módulos
        # por la base sería la misma dependencia que el código evita.
        sa.Column("proveedor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("costo", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("plazo_dias", sa.Integer(), nullable=False),
        sa.Column("puntajes", _JSON, nullable=False),
        sa.Column("puntaje_total", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("observacion", sa.String(length=500), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["evaluacion_id"], ["evaluacion_agencia.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Circular a propósito: la evaluación apunta a la propuesta elegida y la
    # propuesta a su evaluación. Se crea al final para que ninguna tabla
    # necesite a la otra al nacer.
    op.create_foreign_key(
        "fk_evaluacion_agencia_opcion_elegida_id_opcion_agencia",
        "evaluacion_agencia",
        "opcion_agencia",
        ["opcion_elegida_id"],
        ["id"],
    )

    # --- Acumulado de campaña (consumidor de los eventos propios) ----------
    op.create_table(
        "campana_metrica",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("campana_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("fecha_lanzamiento", sa.Date(), nullable=True),
        sa.Column("leads_generados", sa.Integer(), nullable=False),
        sa.Column("leads_convertidos", sa.Integer(), nullable=False),
        sa.Column("piezas_publicadas", sa.Integer(), nullable=False),
        sa.Column("encuestas_enviadas", sa.Integer(), nullable=False),
        sa.Column("encuestas_respondidas", sa.Integer(), nullable=False),
        sa.Column("puntaje_suma", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["campana_id"], ["campana.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campana_id"),
    )


def downgrade() -> None:
    op.drop_table("campana_metrica")
    op.drop_constraint(
        "fk_evaluacion_agencia_opcion_elegida_id_opcion_agencia",
        "evaluacion_agencia",
        type_="foreignkey",
    )
    op.drop_table("opcion_agencia")
    op.drop_table("evaluacion_agencia")
    op.drop_table("encuesta_respuesta")
    op.drop_constraint(
        "fk_encuesta_satisfaccion_pregunta_actual_id_encuesta_pregunta",
        "encuesta_satisfaccion",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_encuesta_satisfaccion_plantilla_id_encuesta_plantilla",
        "encuesta_satisfaccion",
        type_="foreignkey",
    )
    op.drop_index("ix_encuesta_satisfaccion_destino", table_name="encuesta_satisfaccion")
    op.drop_constraint(
        "uq_encuesta_satisfaccion_token_publico",
        "encuesta_satisfaccion",
        type_="unique",
    )
    for columna in (
        "error_envio",
        "mensaje_externo_id",
        "fecha_expiracion",
        "token_publico",
        "conversacion_abierta",
        "destino",
        "pregunta_actual_id",
        "plantilla_id",
    ):
        op.drop_column("encuesta_satisfaccion", columna)
    op.drop_table("encuesta_pregunta")
    op.drop_table("encuesta_plantilla")
