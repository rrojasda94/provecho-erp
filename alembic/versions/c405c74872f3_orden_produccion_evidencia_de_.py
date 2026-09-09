"""orden_produccion: evidencia de destrucción como archivo

`evidencia_destruccion_url` era un string libre que quien completaba la
orden tecleaba en el mismo `POST .../completar`, sin que nadie pudiera
verificar que apuntara a algo real ni listar qué se subió — mientras que
`reporte_escalamiento.evidencia_id` (ADR-036) ya era una FK a `archivo` con
storage real. Dos mecanismos para la misma regla (RN-PRD-015) y ninguno
llenaba al otro. Ahora la evidencia se registra vía `POST /ordenes/{id}/
evidencia` (`src/shared/adjuntos.py`, mismo mecanismo que
`marketing.application.adjuntos`) y queda como `Archivo`
(`evidencia_archivo_id`).

Migración de datos incluida: toda fila con `evidencia_destruccion_url` no
nula se convierte en un `Archivo` (`origen='subido'`, MIME y tamaño
desconocidos porque el binario original nunca vivió en el ERP —se deja
constancia en el propio `nombre`— y `subido_por` es `creado_por` de la
orden, el dato más cercano disponible, no necesariamente quien subió la
evidencia). El `downgrade` reconstruye la URL desde `archivo.url_storage` y
no borra las filas de `archivo` que crea el `upgrade`: son evidencia real
y no hay forma de saber si algo más las referencia para cuando alguien
revierta esto.

Revision ID: c405c74872f3
Revises: 1dfa85b51a5d
Create Date: 2026-09-09 15:53:27.777771

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c405c74872f3"
down_revision: str | None = "1dfa85b51a5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTIDAD = "orden_produccion"


def upgrade() -> None:
    op.add_column(
        "orden_produccion", sa.Column("evidencia_archivo_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_orden_produccion_evidencia_archivo_id_archivo"),
        "orden_produccion",
        "archivo",
        ["evidencia_archivo_id"],
        ["id"],
    )

    conexion = op.get_bind()
    filas = conexion.execute(
        sa.text(
            """
            SELECT id, evidencia_destruccion_url, creado_por
              FROM orden_produccion
             WHERE evidencia_destruccion_url IS NOT NULL
            """
        )
    ).fetchall()
    for orden_id, url, creado_por in filas:
        archivo_id = uuid.uuid4()
        conexion.execute(
            sa.text(
                """
                INSERT INTO archivo (id, nombre, extension, mime_type,
                                      tamano_bytes, url_storage, origen,
                                      entidad_tipo, entidad_id, subido_por)
                VALUES (:id, :nombre, '', 'application/octet-stream', 0,
                        :url_storage, 'subido', :entidad_tipo, :entidad_id,
                        :subido_por)
                """
            ),
            {
                "id": str(archivo_id),
                "nombre": "evidencia-destruccion (migrada desde URL)",
                "url_storage": url,
                "entidad_tipo": _ENTIDAD,
                "entidad_id": str(orden_id),
                "subido_por": str(creado_por),
            },
        )
        conexion.execute(
            sa.text(
                "UPDATE orden_produccion SET evidencia_archivo_id = :archivo_id "
                "WHERE id = :orden_id"
            ),
            {"archivo_id": str(archivo_id), "orden_id": str(orden_id)},
        )

    op.drop_column("orden_produccion", "evidencia_destruccion_url")


def downgrade() -> None:
    op.add_column(
        "orden_produccion",
        sa.Column("evidencia_destruccion_url", sa.VARCHAR(length=500), nullable=True),
    )

    conexion = op.get_bind()
    conexion.execute(
        sa.text(
            """
            UPDATE orden_produccion o
               SET evidencia_destruccion_url = a.url_storage
              FROM archivo a
             WHERE a.id = o.evidencia_archivo_id
            """
        )
    )

    op.drop_constraint(
        op.f("fk_orden_produccion_evidencia_archivo_id_archivo"),
        "orden_produccion",
        type_="foreignkey",
    )
    op.drop_column("orden_produccion", "evidencia_archivo_id")
