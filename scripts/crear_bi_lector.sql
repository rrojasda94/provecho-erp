-- Crea (o repara) el rol bi_lector cuando BI_LECTOR_PASSWORD no estaba
-- puesta la vez que corrió `alembic upgrade head` de
-- alembic/versions/832ff01ed33f_vistas_bi_y_rol_de_solo_lectura.py: esa
-- migración solo crea el rol si la variable existe en ese momento, y una
-- vez marcada como aplicada no se vuelve a correr sola. Es exactamente el
-- mismo bloque "Rol de solo lectura" de esa migración, para cuando hay que
-- provisionarlo aparte, después del hecho (ADR-083 Fase C).
--
-- Uso:
--   docker compose -f docker-compose.staging.yml exec -T db \
--     psql -U provecho -d provecho -v bi_lector_password='<generar una>' \
--     -f - < scripts/crear_bi_lector.sql
--
-- Generar la contraseña con:
--   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
-- y guardarla también como BI_LECTOR_PASSWORD en el .env de este droplet,
-- para que quede documentada igual que si la migración la hubiera leído.

-- Sin `IF NOT EXISTS`/`DO $$` a propósito: el bloque de la migración original
-- lo necesitaba por ser una migración (debe tolerar correr sobre una base
-- que ya lo tenga). Este script es un fix puntual para cuando se confirmó
-- que el rol NO existe (`\du bi_lector` vacío) — si ya existe, `CREATE ROLE`
-- falla con un error claro en vez de hacer nada en silencio, que es preferible
-- acá. Además, la sustitución de variable de psql (`:'var'`) no está
-- garantizada dentro de un bloque `DO $$ ... $$`, así que mejor evitarlo.
CREATE ROLE bi_lector LOGIN PASSWORD :'bi_lector_password';
ALTER ROLE bi_lector SET statement_timeout = '120s';
GRANT CONNECT ON DATABASE provecho TO bi_lector;
GRANT USAGE ON SCHEMA public TO bi_lector;
GRANT SELECT ON vw_bi_ventas TO bi_lector;
GRANT SELECT ON vw_bi_pagos TO bi_lector;
GRANT SELECT ON vw_bi_inventario_movimientos TO bi_lector;
GRANT SELECT ON vw_bi_stock TO bi_lector;
GRANT SELECT ON vw_bi_compras TO bi_lector;
GRANT SELECT ON vw_bi_contabilidad TO bi_lector;
GRANT SELECT ON vw_bi_caja TO bi_lector;
GRANT SELECT ON vw_bi_produccion TO bi_lector;
GRANT SELECT ON vw_bi_rrhh_asistencia TO bi_lector;
GRANT SELECT ON vw_bi_marketing_encuestas TO bi_lector;
GRANT SELECT ON bi_alcance_usuario TO bi_lector;
