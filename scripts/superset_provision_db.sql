-- Rol y esquema para la METADATA de Superset (ADR-082 Fase C) — dashboards,
-- usuarios de Superset, conexiones guardadas. NO tiene nada que ver con
-- `bi_lector` (Fase A): ese es de solo lectura sobre `vw_bi_*`, este es de
-- lectura/escritura pero solo sobre SU PROPIO esquema, cero acceso a las
-- tablas de Provecho.
--
-- Se corre UNA VEZ, a mano, como superusuario, contra la Postgres del
-- droplet de staging (la misma base — Superset no trae la suya, ver
-- ADR-082). Ver docs/engineering/bi-superset.md para el paso a paso
-- completo, incluida la conexión remota por VPC.
--
-- Uso:
--   psql "$DATABASE_URL" -v superset_meta_password='<generar uno>' \
--        -f scripts/superset_provision_db.sql

\set ON_ERROR_STOP on

-- `\gexec` y no un `DO $$ ... $$`: psql NO interpola `:'variable'` dentro de
-- bloques con comillas de a dos ($$), así que la sustitución quedaba
-- literal y el servidor la veía como un `:` suelto (comprobado a mano). Acá
-- la sustitución ocurre antes de que el bloque siquiera exista: el SELECT
-- arma el texto del CREATE ROLE y `\gexec` lo ejecuta, o no arma ninguna
-- fila (y no ejecuta nada) si el rol ya existe.
SELECT 'CREATE ROLE superset_meta LOGIN PASSWORD ' || quote_literal(:'superset_meta_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'superset_meta')
\gexec

CREATE SCHEMA IF NOT EXISTS superset AUTHORIZATION superset_meta;

-- Solo su propio esquema. Nunca `public` (ahí viven las tablas de Provecho
-- y las vistas `vw_bi_*`) — si algún día Superset necesita leerlas, es
-- por la conexión analítica con `bi_lector`, no con este rol.
GRANT ALL ON SCHEMA superset TO superset_meta;
REVOKE ALL ON SCHEMA public FROM superset_meta;

ALTER ROLE superset_meta SET search_path TO superset;
