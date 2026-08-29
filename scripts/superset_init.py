"""Aprovisiona Superset por su API REST (ADR-083 Fase C): la conexión
analítica de solo lectura, un dataset por vista `vw_bi_*` y las dos reglas
de RLS. Idempotente — repetirlo no duplica nada.

Fuera de Alembic a propósito (deuda anotada en
docs/roadmap/deuda/dashboard-y-caja.md): estos son objetos internos de
Superset (`database`, `dataset`, `rowlevelsecurity`), no del esquema de
Provecho, y Superset no expone una forma declarativa de versionarlos aparte
de su propia base de metadata.

`ProvechoBI` es un rol casi vacío: además de la RLS, es donde se cuelga el
`datasource_access` de cada dataset — `Gamma` por sí solo NO alcanza los
datos (comprobado a mano: sin esto, `POST /chart/data` devuelve 403
`DATASOURCE_SECURITY_ACCESS_ERROR` aunque el usuario ya tenga el rol). No es
"acceso de más": los diez datasets son exactamente lo único que la conexión
`bi_lector` puede ver, así que otorgar los diez es otorgar toda la conexión,
ni un bit más. `AUTH_ROLES_MAPPING` (superset_config.py) le da a
`supervisor`/`contador` el rol `Gamma` (permisos base de lectura) *y*
`ProvechoBI` — así no hace falta tocar la definición de `Gamma`, que
Superset trae de fábrica y actualiza con cada versión.

Uso:
  python scripts/superset_init.py \\
    --superset-url https://bi.majambo.com.pe \\
    --admin-username admin --admin-password <el de SUPERSET_ADMIN_PASSWORD> \\
    --pg-host <IP privada del droplet de staging> --pg-port 5432 \\
    --pg-database provecho --bi-lector-password <BI_LECTOR_PASSWORD>
"""

import argparse
import sys

import httpx

# Grano de cada vista de ADR-083 (docs/architecture/data-model.md §17).
# `contabilidad` no tiene `sucursal_id`: la RLS de ese grupo solo filtra por
# empresa. El resto sí, y su columna puede venir NULL (un almacén sin
# sucursal, ADR-083 Fase A) — la cláusula lo deja pasar y confía en el
# filtro de empresa para esas filas.
VISTAS_CON_SUCURSAL = (
    "vw_bi_ventas",
    "vw_bi_pagos",
    "vw_bi_inventario_movimientos",
    "vw_bi_stock",
    "vw_bi_compras",
    "vw_bi_caja",
    "vw_bi_produccion",
    "vw_bi_rrhh_asistencia",
    "vw_bi_marketing_encuestas",
)
VISTAS_SOLO_EMPRESA = ("vw_bi_contabilidad",)

# `{{ current_username() }}` es un macro de JINJA de Superset — lo evalúa
# Superset y lo interpola como string ANTES de mandar la consulta a
# Postgres. No es SQL: la conexión analítica corre siempre como `bi_lector`
# (una sola credencial para todos los usuarios de Superset), así que un
# `current_user`/`current_username()` de Postgres devolvería "bi_lector"
# para cualquiera, y `current_username()` a secas ni siquiera existe como
# función de Postgres (comprobado a mano: `function current_username() does
# not exist`). Sin las llaves y las comillas, la RLS queda escrita pero
# rompe la primera vez que alguien la dispara con una consulta real —
# se verificó justamente así al ensayar esta fase.
CLAUSULA_SUCURSAL = (
    "(sucursal_id IS NULL OR sucursal_id IN "
    "(SELECT sucursal_id FROM bi_alcance_usuario "
    "WHERE username = '{{ current_username() }}'))"
    " AND empresa_id IN (SELECT DISTINCT empresa_id FROM bi_alcance_usuario "
    "WHERE username = '{{ current_username() }}')"
)
CLAUSULA_EMPRESA = (
    "empresa_id IN (SELECT DISTINCT empresa_id FROM bi_alcance_usuario "
    "WHERE username = '{{ current_username() }}')"
)

ROL_MARCADOR = "ProvechoBI"
NOMBRE_CONEXION = "BI Provecho (solo lectura)"


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--superset-url", required=True)
    p.add_argument("--admin-username", required=True)
    p.add_argument("--admin-password", required=True)
    p.add_argument("--pg-host", required=True, help="IP privada (VPC), nunca pública")
    p.add_argument("--pg-port", default="5432")
    p.add_argument("--pg-database", default="provecho")
    p.add_argument("--bi-lector-password", required=True)
    return p.parse_args()


class Superset:
    def __init__(self, base_url: str, username: str, password: str):
        self.c = httpx.Client(base_url=base_url.rstrip("/"), timeout=30)
        token = self.c.post(
            "/api/v1/security/login",
            json={"username": username, "password": password, "provider": "db", "refresh": True},
        ).raise_for_status().json()["access_token"]
        self.c.headers["Authorization"] = f"Bearer {token}"
        csrf = self.c.get("/api/v1/security/csrf_token/").raise_for_status().json()
        self.c.headers["X-CSRFToken"] = csrf["result"]

    def _buscar_por_nombre(self, ruta: str, campo: str, valor: str) -> dict | None:
        r = self.c.get(ruta, params={"q": f"(filters:!((col:{campo},opr:eq,value:'{valor}')))"})
        r.raise_for_status()
        filas = r.json()["result"]
        return filas[0] if filas else None

    def conexion_bi_lector(self, pg_host, pg_port, pg_database, password) -> int:
        existente = self._buscar_por_nombre("/api/v1/database/", "database_name", NOMBRE_CONEXION)
        if existente:
            return existente["id"]
        uri = f"postgresql+psycopg2://bi_lector:{password}@{pg_host}:{pg_port}/{pg_database}"
        r = self.c.post(
            "/api/v1/database/",
            json={
                "database_name": NOMBRE_CONEXION,
                "sqlalchemy_uri": uri,
                # Explícito: nadie debe poder abrir SQL Lab contra esta
                # conexión aunque su rol lo permitiera (ADR-083).
                "allow_run_async": False,
                "expose_in_sqllab": False,
            },
        )
        r.raise_for_status()
        return r.json()["id"]

    def dataset(self, db_id: int, tabla: str) -> int:
        existente = self._buscar_por_nombre("/api/v1/dataset/", "table_name", tabla)
        if existente:
            return existente["id"]
        r = self.c.post(
            "/api/v1/dataset/",
            json={"database": db_id, "schema": "public", "table_name": tabla},
        )
        r.raise_for_status()
        return r.json()["id"]

    def _mapa_permisos_datasource_access(self) -> dict[str, int]:
        """`view_menu.name` -> id de permiso, para toda fila
        `datasource_access`. Sin filtro server-side confiable para un campo
        anidado (`view_menu.name`) en esta API — se resuelve trayendo todo
        una vez (unas pocas centenas de filas en una instalación nueva, y
        esto corre solo al aprovisionar, no en cada request)."""
        mapa: dict[str, int] = {}
        pagina = 0
        while True:
            r = self.c.get(
                "/api/v1/security/permissions-resources/",
                params={"q": f"(page:{pagina},page_size:100)"},
            )
            r.raise_for_status()
            filas = r.json()["result"]
            if not filas:
                break
            mapa.update(
                {
                    f["view_menu"]["name"]: f["id"]
                    for f in filas
                    if f["permission"]["name"] == "datasource_access"
                }
            )
            pagina += 1
        return mapa

    def otorgar_acceso_datasets(
        self, rol_id: int, database_name: str, datasets: dict[str, int]
    ) -> None:
        """`Gamma` no alcanza los datos por sí solo (403
        `DATASOURCE_SECURITY_ACCESS_ERROR`, comprobado a mano): cada dataset
        necesita su propio `datasource_access` en el rol. `datasets` es
        tabla -> id de dataset; el nombre del view_menu que Superset genera
        es `[<conexión>].[<tabla>](id:<id>)` — no hay endpoint que lo
        devuelva directo desde el dataset, así que se arma acá."""
        mapa = self._mapa_permisos_datasource_access()
        pv_ids = []
        for tabla, dataset_id in datasets.items():
            clave = f"[{database_name}].[{tabla}](id:{dataset_id})"
            if clave not in mapa:
                raise RuntimeError(f"Superset no generó el permiso para {clave} todavía")
            pv_ids.append(mapa[clave])
        r = self.c.post(
            f"/api/v1/security/roles/{rol_id}/permissions",
            json={"permission_view_menu_ids": pv_ids},
        )
        r.raise_for_status()

    def rol_marcador(self, nombre: str) -> int:
        existente = self._buscar_por_nombre("/api/v1/security/roles/", "name", nombre)
        if existente:
            return existente["id"]
        r = self.c.post("/api/v1/security/roles/", json={"name": nombre})
        r.raise_for_status()
        return r.json()["id"]

    def regla_rls(self, nombre: str, dataset_ids: list[int], rol_id: int, clausula: str) -> None:
        if self._buscar_por_nombre("/api/v1/rowlevelsecurity/", "name", nombre):
            return
        r = self.c.post(
            "/api/v1/rowlevelsecurity/",
            json={
                "name": nombre,
                "filter_type": "Regular",
                "tables": dataset_ids,
                "roles": [rol_id],
                "clause": clausula,
            },
        )
        r.raise_for_status()


def main() -> None:
    a = _argumentos()
    s = Superset(a.superset_url, a.admin_username, a.admin_password)

    db_id = s.conexion_bi_lector(a.pg_host, a.pg_port, a.pg_database, a.bi_lector_password)
    print(f"Conexión '{NOMBRE_CONEXION}': id {db_id}")

    con_sucursal = {t: s.dataset(db_id, t) for t in VISTAS_CON_SUCURSAL}
    solo_empresa = {t: s.dataset(db_id, t) for t in VISTAS_SOLO_EMPRESA}
    print(f"Datasets: {len(con_sucursal) + len(solo_empresa)}")

    rol_id = s.rol_marcador(ROL_MARCADOR)
    print(f"Rol '{ROL_MARCADOR}': id {rol_id}")

    s.otorgar_acceso_datasets(rol_id, NOMBRE_CONEXION, {**con_sucursal, **solo_empresa})
    print("Acceso a los datasets otorgado.")

    s.regla_rls(
        "Alcance por sucursal", list(con_sucursal.values()), rol_id, CLAUSULA_SUCURSAL
    )
    s.regla_rls(
        "Alcance por empresa", list(solo_empresa.values()), rol_id, CLAUSULA_EMPRESA
    )
    print("RLS aplicada.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"Superset respondió {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
