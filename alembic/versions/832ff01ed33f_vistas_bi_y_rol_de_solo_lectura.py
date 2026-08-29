"""vistas bi y rol de solo lectura

Capa semantica para el BI autoservicio (ADR-082, Fase A). Superset no toca
tablas base: solo ve estas vistas `vw_bi_*` y `bi_alcance_usuario`, a traves
de un rol de Postgres (`bi_lector`) que no tiene GRANT sobre ninguna otra
tabla. ADR-024 sigue vigente para `src/core/reportes/` — esto no abre un
constructor de consultas ahi, abre uno en un producto aparte, detras de una
puerta que la aplicacion no controla.

Cada vista repite el mismo criterio que ya usan `queries_publicas.py` de cada
modulo, para que el BI y el catalogo cerrado nunca se contradigan sobre el
mismo rango:

- Fecha de negocio, nunca `created_at`: `venta.fecha_orden` (agrupar por UTC
  partiria en dos la noche de un local que cierra pasada medianoche).
- "Ingreso real" = `venta.estado in ('pagada', 'facturada')`, igual que
  `sales/queries_publicas._ESTADOS_CON_INGRESO`.
- RRHH expone tardanzas y horas extra, nunca remuneracion — mismo limite que
  `rrhh/queries_publicas.nombres_por_usuario`.
- Todas llevan `empresa_id` y, si el hecho es de local, `sucursal_id` +
  `marca_id`: son las columnas contra las que filtra la RLS de Superset.
  `marca_id` no es dimension de ningun reporte del catalogo hoy — es un join
  de un salto (`sucursal.marca_id`) que aqui se resuelve una sola vez.

`bi_alcance_usuario` expande el mismo alcance que `Tenant.sucursal_ids`
resuelve en Python (`src/core/tenant.py`): un superusuario (permiso `*`) sale
con todas las sucursales de su empresa; el resto, con las de
`usuario_sucursal`. Es el puente entre los dos puntos de aplicacion del
tenant, y el motivo de que exista `tests/test_bi_alcance.py` — si esta vista
diverge de `Tenant`, alguien ve una sucursal que no deberia.

De paso, dos indices que el catalogo de reportes ya necesitaba y el BI vuelve
impostergables (sin ellos, una consulta de un anio completo escanea la tabla
entera): `venta(fecha_orden, estado)` y `movimiento_inventario(ts, almacen_id)`.

Revision ID: 832ff01ed33f
Revises: dfb195b14433
Create Date: 2026-08-29

"""

import os
from collections.abc import Sequence

from alembic import op

revision: str = "832ff01ed33f"
down_revision: str | None = "dfb195b14433"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrasena del rol de solo lectura. Se lee de variable de entorno para no
# dejarla en texto plano en el historial de migraciones — el mismo criterio
# que `settings` usa para toda credencial. En un entorno donde no se define
# (ej. e2e sobre SQLite, que ni siquiera llega a `upgrade()` de Postgres para
# esto) el rol simplemente no se crea con clave utilizable; nadie levanta
# Superset ahi.
_BI_LECTOR_PASSWORD_ENV = "BI_LECTOR_PASSWORD"

_VISTAS = (
    "vw_bi_ventas",
    "vw_bi_pagos",
    "vw_bi_inventario_movimientos",
    "vw_bi_stock",
    "vw_bi_compras",
    "vw_bi_contabilidad",
    "vw_bi_caja",
    "vw_bi_produccion",
    "vw_bi_rrhh_asistencia",
    "vw_bi_marketing_encuestas",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (suite de tests y e2e) no tiene roles ni las funciones de
        # ventana/regex que usan algunas vistas de abajo. El BI no corre ahi.
        return

    # --- Indices que el catalogo de reportes ya debia y el BI hace impostergables
    op.create_index(
        "ix_venta_fecha_orden_estado", "venta", ["fecha_orden", "estado"]
    )
    op.create_index(
        "ix_movimiento_inventario_ts_almacen",
        "movimiento_inventario",
        ["ts", "almacen_id"],
    )
    op.create_index("ix_asiento_fecha_empresa", "asiento", ["fecha", "empresa_id"])
    op.create_index(
        "ix_asistencia_fecha_trabajador", "asistencia", ["fecha", "trabajador_id"]
    )

    # --- Vistas de negocio -----------------------------------------------
    op.execute("""
        CREATE VIEW vw_bi_ventas AS
        SELECT
            v.id AS venta_id,
            vi.id AS venta_item_id,
            v.fecha_orden AS fecha,
            s.empresa_id,
            v.sucursal_id,
            s.marca_id,
            m.nombre AS marca_nombre,
            s.nombre AS sucursal_nombre,
            v.canal,
            v.modalidad,
            v.tipo,
            v.estado,
            v.usuario_id,
            pc.id AS producto_comercial_id,
            pc.nombre AS producto_nombre,
            pc.categoria_id,
            vi.cantidad,
            vi.precio_unitario,
            vi.descuento,
            (vi.cantidad * vi.precio_unitario - vi.descuento) AS importe_linea,
            v.total AS total_venta
        FROM venta v
        JOIN venta_item vi ON vi.venta_id = v.id
        JOIN sucursal s ON s.id = v.sucursal_id
        JOIN marca m ON m.id = s.marca_id
        JOIN producto_comercial pc ON pc.id = vi.producto_comercial_id
        WHERE v.estado IN ('pagada', 'facturada')
    """)

    op.execute("""
        CREATE VIEW vw_bi_pagos AS
        SELECT
            p.id AS pago_id,
            v.fecha_orden AS fecha,
            s.empresa_id,
            v.sucursal_id,
            s.marca_id,
            m.nombre AS marca_nombre,
            s.nombre AS sucursal_nombre,
            p.medio_pago_id,
            mp.nombre AS medio_pago_nombre,
            p.estado,
            p.pasarela,
            p.monto,
            p.vuelto
        FROM pago p
        JOIN venta v ON v.id = p.venta_id
        JOIN sucursal s ON s.id = v.sucursal_id
        JOIN marca m ON m.id = s.marca_id
        JOIN medio_pago mp ON mp.id = p.medio_pago_id
    """)

    op.execute("""
        CREATE VIEW vw_bi_inventario_movimientos AS
        SELECT
            mi.id AS movimiento_id,
            mi.ts AS fecha,
            a.empresa_id,
            a.sucursal_id,
            s.marca_id,
            mi.almacen_id,
            a.nombre AS almacen_nombre,
            art.id AS articulo_id,
            art.nombre AS articulo_nombre,
            art.categoria_id,
            mi.tipo,
            mi.motivo_ajuste,
            mi.cantidad
        FROM movimiento_inventario mi
        JOIN sku ON sku.id = mi.sku_id
        JOIN articulo art ON art.id = sku.articulo_id
        JOIN almacen a ON a.id = mi.almacen_id
        LEFT JOIN sucursal s ON s.id = a.sucursal_id
    """)

    op.execute("""
        CREATE VIEW vw_bi_stock AS
        SELECT
            st.id AS stock_id,
            a.empresa_id,
            a.sucursal_id,
            s.marca_id,
            st.almacen_id,
            a.nombre AS almacen_nombre,
            art.id AS articulo_id,
            art.nombre AS articulo_nombre,
            art.categoria_id,
            st.cantidad,
            st.stock_minimo,
            st.stock_maximo
        FROM stock st
        JOIN sku ON sku.id = st.sku_id
        JOIN articulo art ON art.id = sku.articulo_id
        JOIN almacen a ON a.id = st.almacen_id
        LEFT JOIN sucursal s ON s.id = a.sucursal_id
    """)

    op.execute("""
        CREATE VIEW vw_bi_compras AS
        SELECT
            oc.id AS orden_compra_id,
            oci.id AS orden_compra_item_id,
            COALESCE(oc.fecha_emision::date, oc.created_at::date) AS fecha,
            a.empresa_id,
            a.sucursal_id,
            oc.almacen_destino_id,
            a.nombre AS almacen_nombre,
            oc.proveedor_id,
            pr.razon_social AS proveedor_nombre,
            oc.tipo,
            oc.estado,
            art.id AS articulo_id,
            art.nombre AS articulo_nombre,
            oci.cantidad,
            oci.costo_unitario,
            (oci.cantidad * oci.costo_unitario) AS importe_linea
        FROM orden_compra oc
        JOIN orden_compra_item oci ON oci.orden_compra_id = oc.id
        JOIN almacen a ON a.id = oc.almacen_destino_id
        JOIN proveedor pr ON pr.id = oc.proveedor_id
        JOIN articulo art ON art.id = oci.articulo_id
    """)

    op.execute("""
        CREATE VIEW vw_bi_contabilidad AS
        SELECT
            al.id AS asiento_linea_id,
            a.id AS asiento_id,
            a.fecha,
            a.empresa_id,
            a.origen,
            a.evento_origen,
            a.estado,
            cc.id AS cuenta_contable_id,
            cc.codigo AS cuenta_codigo,
            cc.nombre AS cuenta_nombre,
            cc.tipo AS cuenta_tipo,
            al.tipo AS movimiento_tipo,
            al.monto
        FROM asiento_linea al
        JOIN asiento a ON a.id = al.asiento_id
        JOIN cuenta_contable cc ON cc.id = al.cuenta_contable_id
    """)

    op.execute("""
        CREATE VIEW vw_bi_caja AS
        SELECT
            cc.id AS cierre_id,
            cc.created_at::date AS fecha,
            s.empresa_id,
            pv.sucursal_id,
            s.marca_id,
            s.nombre AS sucursal_nombre,
            cc.cajero_id,
            cc.custodia,
            cc.estado,
            cc.descuadre_monto
        FROM cierre_caja cc
        JOIN apertura_caja ac ON ac.id = cc.apertura_caja_id
        JOIN punto_venta pv ON pv.id = ac.punto_venta_id
        JOIN sucursal s ON s.id = pv.sucursal_id
    """)

    op.execute("""
        CREATE VIEW vw_bi_produccion AS
        SELECT
            op.id AS orden_produccion_id,
            op.created_at::date AS fecha,
            a.empresa_id,
            a.sucursal_id,
            op.almacen_id,
            a.nombre AS almacen_nombre,
            art.id AS articulo_id,
            art.nombre AS articulo_nombre,
            op.estado,
            op.cantidad_planeada,
            op.cantidad_producida,
            op.horas_hombre,
            op.costo_insumos,
            op.costo_mano_obra,
            op.costo_real_unitario,
            op.merma_cantidad
        FROM orden_produccion op
        JOIN almacen a ON a.id = op.almacen_id
        JOIN articulo art ON art.id = op.articulo_id
    """)

    # RRHH: nombre y cargo, nunca remuneracion — mismo limite que
    # `rrhh/queries_publicas.nombres_por_usuario`.
    op.execute("""
        CREATE VIEW vw_bi_rrhh_asistencia AS
        SELECT
            asi.id AS asistencia_id,
            asi.fecha,
            t.empresa_id,
            t.sucursal_id,
            s.marca_id,
            t.id AS trabajador_id,
            t.cargo,
            t.area,
            asi.tardanza_min,
            asi.horas_extra
        FROM asistencia asi
        JOIN trabajador t ON t.id = asi.trabajador_id
        LEFT JOIN sucursal s ON s.id = t.sucursal_id
    """)

    op.execute("""
        CREATE VIEW vw_bi_marketing_encuestas AS
        SELECT
            e.id AS encuesta_id,
            e.fecha_envio::date AS fecha,
            s.empresa_id,
            v.sucursal_id,
            s.marca_id,
            s.nombre AS sucursal_nombre,
            e.canal,
            e.destino,
            e.estado,
            e.puntaje
        FROM encuesta_satisfaccion e
        JOIN venta v ON v.id = e.venta_id
        JOIN sucursal s ON s.id = v.sucursal_id
    """)

    # --- Puente de alcance (equivalente a Tenant.sucursal_ids) ------------
    op.execute("""
        CREATE VIEW bi_alcance_usuario AS
        SELECT u.username, s.empresa_id, s.id AS sucursal_id
        FROM usuario u
        JOIN usuario_sucursal us ON us.usuario_id = u.id
        JOIN sucursal s ON s.id = us.sucursal_id
        WHERE u.deleted_at IS NULL AND s.deleted_at IS NULL
        UNION
        -- Superusuario (permiso '*') sin sucursales asignadas: mismo criterio
        -- que `Tenant.exigir_sucursal` — ve todo. Se le abre a todas las
        -- sucursales de todas las empresas porque, a diferencia del JWT, esta
        -- vista no tiene un `empresa_id` de sesion del cual partir.
        SELECT u.username, s.empresa_id, s.id AS sucursal_id
        FROM usuario u
        JOIN usuario_rol ur ON ur.usuario_id = u.id
        JOIN rol_permiso rp ON rp.rol_id = ur.rol_id
        JOIN permiso perm ON perm.id = rp.permiso_id AND perm.codigo = '*'
        CROSS JOIN sucursal s
        WHERE u.deleted_at IS NULL
          AND perm.deleted_at IS NULL
          AND s.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM usuario_sucursal us2 WHERE us2.usuario_id = u.id
          )
    """)

    # --- Rol de solo lectura ------------------------------------------------
    password = os.environ.get(_BI_LECTOR_PASSWORD_ENV)
    if password:
        # Comillas dobladas, no parametro: DDL no acepta bind params y el
        # valor sale de una variable de entorno de despliegue, no de input
        # de cliente.
        password_sql = password.replace("'", "''")
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_lector') THEN
                    CREATE ROLE bi_lector LOGIN PASSWORD '{password_sql}';
                END IF;
            END
            $$;
        """)
        # Mismo criterio que `SessionReportes`: un dataset pesado tarda de
        # verdad, pero tiene que tener techo. A nivel de rol porque Superset
        # abre su propio pool y no pasa por `connect_args` de este proyecto.
        op.execute("ALTER ROLE bi_lector SET statement_timeout = '120s'")
        # GRANT ... ON DATABASE no acepta una funcion como nombre: el nombre
        # sale de la propia conexion de la migracion, no de `settings`, para
        # que esto funcione igual en staging/prod que en un Postgres local.
        db_name = bind.engine.url.database
        op.execute(f'GRANT CONNECT ON DATABASE "{db_name}" TO bi_lector')
        op.execute("GRANT USAGE ON SCHEMA public TO bi_lector")
        for vista in (*_VISTAS, "bi_alcance_usuario"):
            op.execute(f"GRANT SELECT ON {vista} TO bi_lector")
    else:
        # Sin contrasena en el entorno (dev local, CI) se crean las vistas
        # igual —son las que valida `tests/test_bi_alcance.py`— pero no el
        # rol: nadie deja un rol de base de datos con clave vacia.
        pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP VIEW IF EXISTS bi_alcance_usuario")
    for vista in reversed(_VISTAS):
        op.execute(f"DROP VIEW IF EXISTS {vista}")

    # `DROP OWNED BY` no acepta `IF EXISTS` sobre el rol: si nunca se creo
    # (entorno sin BI_LECTOR_PASSWORD) directamente no hay nada que soltar.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_lector') THEN
                DROP OWNED BY bi_lector;
                DROP ROLE bi_lector;
            END IF;
        END
        $$;
    """)

    op.drop_index("ix_asistencia_fecha_trabajador", table_name="asistencia")
    op.drop_index("ix_asiento_fecha_empresa", table_name="asiento")
    op.drop_index(
        "ix_movimiento_inventario_ts_almacen", table_name="movimiento_inventario"
    )
    op.drop_index("ix_venta_fecha_orden_estado", table_name="venta")
