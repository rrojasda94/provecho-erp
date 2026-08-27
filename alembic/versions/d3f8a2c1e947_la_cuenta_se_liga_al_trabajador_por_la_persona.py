"""la cuenta se liga al trabajador por la persona

El vinculo cuenta<->trabajador vivia en dos columnas que nadie sincronizaba:
`usuario.persona_id` (vinculado desde Usuarios) y `trabajador.usuario_id`
(vinculado desde RRHH > Trabajadores, el unico que leia el pad de asistencia).
Vincular desde Usuarios no habilitaba el pad — ADR-070.

Desde ahora `usuario.persona_id` es la unica arista: una persona viva tiene a
lo mas una cuenta viva (`uq_usuario_persona_viva`). `trabajador.usuario_id`
deja de ser columna — el modelo lo deriva con una subconsulta
(`column_property`) que busca la cuenta cuya `persona_id` es la del
trabajador. Una persona puede tener mas de una fila `trabajador` (recontratado:
una cesada + una activa) y ambas comparten la misma cuenta; eso es correcto.

El backfill mueve el vinculo de `trabajador.usuario_id` a `usuario.persona_id`
solo donde la cuenta todavia no tiene persona. Antes de tocar nada, dos
chequeos abortan la migracion en vez de morir en la violacion del indice:
una persona con dos cuentas vivas ya hoy, o una persona con dos trabajadores
que apuntan a cuentas *distintas* (el backfill fabricaria el choque).

Revision ID: d3f8a2c1e947
Revises: c4d17b93e0af
Create Date: 2026-08-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd3f8a2c1e947'
down_revision: str | None = 'c4d17b93e0af'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_usuario = sa.table(
    'usuario',
    sa.column('id', sa.Uuid()),
    sa.column('persona_id', sa.Uuid()),
    sa.column('deleted_at', sa.DateTime(timezone=True)),
)
_trabajador = sa.table(
    'trabajador',
    sa.column('id', sa.Uuid()),
    sa.column('persona_id', sa.Uuid()),
    sa.column('usuario_id', sa.Uuid()),
    sa.column('deleted_at', sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Suciedad ya existente: una persona con dos cuentas vivas. Nada en el
    # código de antes lo impedía (deuda anotada en
    # docs/roadmap/deuda/modulo-rrhh.md); si pasó, el índice de abajo
    # reventaría a mitad de camino sin decir por qué.
    dobles_cuenta = bind.execute(
        sa.select(_usuario.c.persona_id, sa.func.count())
        .where(_usuario.c.persona_id.is_not(None), _usuario.c.deleted_at.is_(None))
        .group_by(_usuario.c.persona_id)
        .having(sa.func.count() > 1)
    ).all()
    if dobles_cuenta:
        ids = ", ".join(str(persona_id) for persona_id, _ in dobles_cuenta)
        raise RuntimeError(
            "hay personas con más de una cuenta viva, no se puede crear "
            f"uq_usuario_persona_viva: resolver a mano antes de migrar — {ids}"
        )

    # 2) El backfill fabricaría el mismo choque si dos trabajadores de una
    # persona apuntan a cuentas distintas (dato inconsistente previo, no un
    # caso de recontratación real — ahí las dos filas comparten cuenta).
    filas_trabajador = bind.execute(
        sa.select(_trabajador.c.persona_id, _trabajador.c.usuario_id)
        .where(_trabajador.c.usuario_id.is_not(None), _trabajador.c.deleted_at.is_(None))
    ).all()
    cuentas_por_persona: dict = {}
    for persona_id, usuario_id in filas_trabajador:
        cuentas_por_persona.setdefault(persona_id, set()).add(usuario_id)
    conflictivas = [pid for pid, cuentas in cuentas_por_persona.items() if len(cuentas) > 1]
    if conflictivas:
        ids = ", ".join(str(pid) for pid in conflictivas)
        raise RuntimeError(
            "hay personas cuyos trabajadores apuntan a cuentas distintas, "
            f"el backfill de persona_id fabricaría un choque: resolver a mano — {ids}"
        )

    # 3) Backfill: solo donde la cuenta todavía no tiene persona propia.
    op.execute(
        sa.text(
            "UPDATE usuario SET persona_id = t.persona_id "
            "FROM trabajador t "
            "WHERE t.usuario_id = usuario.id "
            "AND usuario.persona_id IS NULL "
            "AND usuario.deleted_at IS NULL "
            "AND t.deleted_at IS NULL"
        )
    )

    op.create_index(
        'uq_usuario_persona_viva',
        'usuario',
        ['persona_id'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
        sqlite_where=sa.text('deleted_at IS NULL'),
    )

    # SQLite no borra una columna con FK sin batch mode.
    with op.batch_alter_table('trabajador') as batch:
        batch.drop_constraint(
            op.f('fk_trabajador_usuario_id_usuario'), type_='foreignkey'
        )
        batch.drop_column('usuario_id')


def downgrade() -> None:
    op.add_column('trabajador', sa.Column('usuario_id', sa.Uuid(), nullable=True))
    with op.batch_alter_table('trabajador') as batch:
        batch.create_foreign_key(
            op.f('fk_trabajador_usuario_id_usuario'), 'usuario', ['usuario_id'], ['id']
        )
    # Repuebla desde usuario.persona_id: sin esto, un downgrade real (no solo
    # el ciclo de CI) perdería todos los vínculos hechos después del upgrade.
    op.execute(
        sa.text(
            "UPDATE trabajador SET usuario_id = u.id "
            "FROM usuario u "
            "WHERE u.persona_id = trabajador.persona_id "
            "AND u.deleted_at IS NULL "
            "AND trabajador.deleted_at IS NULL"
        )
    )
    op.drop_index('uq_usuario_persona_viva', table_name='usuario')
