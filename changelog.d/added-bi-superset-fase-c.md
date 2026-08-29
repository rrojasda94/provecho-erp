- **Superset aprovisionado y ensayado de punta a punta** (ADR-083, Fase C):
  `docker-compose.bi.yml`, `deploy/bi/` (Dockerfile, config de Superset,
  Caddyfile), `scripts/superset_provision_db.sql` y
  `scripts/superset_init.py`. Todo corrido de verdad contra un Superset y
  una Postgres reales en Docker local —no solo revisado a ojo— porque no
  hay acceso a la cuenta de DigitalOcean del usuario para llevarlo al
  droplet real todavía; el runbook completo queda en
  `docs/engineering/bi-superset.md`.
- **Cuatro bugs reales que el ensayo local atrapó y ninguna lectura de
  código habría visto**:
  - La imagen "lean" de `apache/superset` (la de producción, sin sufijo
    `-dev`) no trae `psycopg2` — `superset db upgrade` fallaba con
    `ModuleNotFoundError`. Resuelto con una imagen propia de una capa.
  - Ese driver hay que instalarlo en el venv de Superset (`/app/.venv`,
    que no trae `pip` propio), no en el `pip` del sistema — `pip install`
    a secas "funciona" pero instala en el lugar equivocado.
  - `current_username()` sin llaves **no es SQL de Postgres**: es un
    macro de Jinja de Superset (`{{ current_username() }}`) que se
    interpola del lado de Superset antes de mandar la consulta —
    necesario porque la conexión analítica corre siempre como `bi_lector`
    para cualquier usuario de Superset, así que un `current_user` de
    Postgres jamás distinguiría a una persona de otra.
  - Sin la feature flag `ENABLE_TEMPLATE_PROCESSING`, ese macro **tampoco
    se interpola** aunque esté bien escrito: la RLS queda comparando
    contra el texto literal, nadie coincide nunca, y la consulta responde
    `200 OK` con cero filas para todo el mundo — sin ningún error que lo
    delate. Se detectó inspeccionando el SQL efectivo
    (`POST /api/v1/chart/data`), no por inferencia.
  - El rol `Gamma` de fábrica no alcanza los datos sin `datasource_access`
    explícito por dataset (403 `DATASOURCE_SECURITY_ACCESS_ERROR`). El
    script se lo otorga al rol marcador `ProvechoBI` — los diez datasets,
    ni uno más, que es exactamente lo único que la conexión `bi_lector`
    puede ver.
- Pendiente: crear el droplet real (DigitalOcean, VPC, firewall, DNS —
  requiere acceso del usuario) y correr el mismo `scripts/superset_init.py`
  contra la Postgres de staging de verdad. Ver ADR-083 y
  `docs/engineering/bi-superset.md`.
