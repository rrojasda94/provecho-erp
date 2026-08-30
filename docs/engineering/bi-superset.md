# BI (Superset) — runbook

Runbook y bitácora del droplet del BI autoservicio (ADR-083 Fase C).
Complementa [staging.md](staging.md) (el droplet del que este depende) y
[devops.md](devops.md). Mismo criterio que ese archivo:

**Nunca poner acá:** contraseñas, tokens, passphrases, ni el contenido de
`.env`. Esos viven en el gestor de contraseñas de quien los generó y en el
`.env` del droplet (fuera del repo, permisos 600).

## Por qué un droplet aparte

Ver ADR-083, "Dónde corre": el volumen real es decenas de consultas al mes
sobre miles de filas, sin apuro de latencia. Agrandar el droplet de
staging (2 vCPU/4 GB, donde vive caja/PDV) para esto no se justificaba, y
compartir recursos entre una consulta analítica pesada y el cobro es
exactamente el riesgo que separar en dos máquinas evita.

## Datos del servidor (a completar al crearlo)

| Dato | Valor |
|---|---|
| Proveedor | DigitalOcean, misma cuenta y región que `provecho-staging` |
| Nombre del droplet | `provecho-bi` |
| Tamaño | 1 vCPU / 1 GB RAM (~$8/mes, tier Premium Intel/AMD) |
| Red | En la **misma VPC privada** que `provecho-staging` — sin eso no llega a Postgres sin exponerlo a internet |
| IP pública | `167.99.125.141` |
| IP privada (VPC) | `10.17.0.6` según `ip addr` **en el propio droplet BI** — pero no es la IP que hay que abrir en `pg_hba.conf`/firewall de staging, ver nota abajo |
| SO | Ubuntu 24.04 LTS, igual que staging |
| Dominio | `bi.majambo.com.pe` |
| Usuario de la app | `app` (sudo, sin login root, sin login por contraseña) — mismo criterio que staging |
| Llave SSH | Reusar `renota-provecho`/`provecho_droplet` o generar una nueva — decisión de quien lo crea |
| Swap | 2 GB (`fallocate`) — con 1 GB de RAM al límite, una consulta puntual pesada no debe matar el proceso |

> **La IP privada que ve el droplet BI de sí mismo no es la que ve Postgres
> del otro lado.** `ip addr` en el droplet BI reporta `10.17.0.6`, pero
> DigitalOcean enruta el tráfico de la VPC a través de un gateway que hace
> NAT: staging ve la conexión llegar desde `10.108.0.2` (confirmado con
> `SELECT inet_client_addr();` corrido en esa sesión). La IP que va en
> `pg_hba.conf` y en el firewall del droplet de staging es **esta segunda**,
> no la que muestra `ip addr` en el droplet BI — confundirlas hace perder
> tiempo pensando que hay un problema de región/subred cuando no lo hay.
> Al escribirla en `pg_hba.conf`, siempre con el sufijo `/32`: sin él,
> Postgres interpreta el siguiente token de la línea (el método de auth,
> p. ej. `scram-sha-256`) como la máscara y falla el arranque completo con
> `invalid IP mask` — tumba TODO staging, no solo la conexión nueva.

## Decisiones tomadas

- **Sin Postgres propio**: la metadata de Superset vive en un esquema
  (`superset`) de la Postgres del droplet de staging, con su propio rol
  (`superset_meta`, `scripts/superset_provision_db.sql`) — sin acceso a
  ninguna tabla de Provecho ni a las vistas `vw_bi_*`. La conexión ANALÍTICA
  (la que sí lee `vw_bi_*`) usa un rol distinto, `bi_lector` (ADR-083 Fase
  A), registrada desde la UI de Superset o `scripts/superset_init.py`.
- **Sin Celery, sin Redis, sin Alerts & Reports**: no entran cómodos en
  1 GB. Las consultas corren sincrónicas. Ver ADR-083.
- **Imagen propia** (`deploy/bi/Dockerfile`), no `apache/superset:6.1.0`
  directo: ese tag "lean" no trae `psycopg2` — ver "Bugs encontrados"
  abajo.
- **Proxy/TLS**: Caddy, mismo criterio que staging.

## Antes de crear el droplet: en el de STAGING

Dos cambios ahí, ninguno en el droplet BI:

1. **Postgres acepta conexiones desde la VPC.** Por defecto el `db` del
   compose de staging solo escucha dentro de su propia red de Docker. Hace
   falta:
   - Publicar el puerto 5432 del contenedor `db` a la interfaz de la VPC
     del droplet de staging (no a `0.0.0.0`, no a la IP pública).
   - `pg_hba.conf`: una línea `host provecho superset_meta <rango-CIDR-de-
     la-VPC> scram-sha-256` (y otra igual para `bi_lector`, ya necesaria
     desde la Fase A si Superset no corriera en el mismo host).
   - Firewall de DigitalOcean (`ufw` o ídem) del droplet de staging: abrir
     5432 **solo** a la IP privada del droplet BI, nunca a `0.0.0.0/0`.
2. **Crear `bi_lector` con contraseña real**, si la migración de Fase A se
   corrió alguna vez sin `BI_LECTOR_PASSWORD` en el entorno (no crea el rol
   sin ella, ver `alembic/versions/832ff01ed33f_...py`). Confirmar con:
   ```bash
   psql "$DATABASE_URL" -c "\du bi_lector"
   ```

## Crear el droplet BI

- [ ] Droplet creado en la misma VPC que staging, 1 vCPU/1 GB
- [ ] Swap de 2 GB
- [ ] Docker + Docker Compose instalados, usuario `app` en el grupo `docker`
- [ ] Firewall (`ufw`): solo 22/80/443
- [ ] DNS: `bi.majambo.com.pe` → IP pública del droplet BI
- [ ] Repo clonado (o al menos `docker-compose.bi.yml`, `deploy/bi/`,
      `scripts/superset_provision_db.sql` y `scripts/superset_init.py`
      copiados)

## Aprovisionar

En el droplet de **staging** (una vez, contra la Postgres real):

```bash
psql "$DATABASE_URL" -v superset_meta_password='<generar uno>' \
     -f scripts/superset_provision_db.sql
```

En el droplet **BI**:

```bash
cp .env.bi.example .env
# completar SUPERSET_SECRET_KEY, SUPERSET_METADATA_DATABASE_URI (con la IP
# privada de staging), SUPERSET_ADMIN_PASSWORD, OAUTH_BI_CLIENT_ID/SECRET
# (mismos valores que en el .env de staging)

docker compose -f docker-compose.bi.yml build
docker compose -f docker-compose.bi.yml up -d
docker compose -f docker-compose.bi.yml logs -f superset-init  # hasta que termine
```

Y desde cualquier máquina con red hacia el droplet BI (o dentro de él):

```bash
python scripts/superset_init.py \
  --superset-url https://bi.majambo.com.pe \
  --admin-username admin --admin-password '<SUPERSET_ADMIN_PASSWORD>' \
  --pg-host <IP privada del droplet de staging> --pg-port 5432 \
  --pg-database provecho --bi-lector-password '<BI_LECTOR_PASSWORD>'
```

Verificación mínima tras aprovisionar (ver ADR-083, "Verificación — Fase
C-D"): entrar como un usuario de una sola sucursal y confirmar que un
dataset `vw_bi_*` solo muestra esa sucursal. Es la prueba que decide si el
diseño sirve — no alcanza con que Superset arranque.

## Bugs encontrados al ensayar esta fase (localmente, antes de tocar el droplet real)

Los cuatro se comprobaron con Docker contra una Postgres desechable, no se
infirieron de la documentación de Superset:

- **La imagen "lean" de `apache/superset` no trae `psycopg2`.**
  `ModuleNotFoundError` al correr `superset db upgrade`. Resuelto con
  `deploy/bi/Dockerfile` — una capa que instala `psycopg2-binary`.
- **Ese `pip install` tiene que apuntar al venv de Superset
  (`/app/.venv`), no al `pip` del sistema.** `pip install` a secas
  "funciona" pero instala en el lugar que Superset no usa; el venv además
  no tiene `pip` propio (`No module named pip`) — se resolvió con
  `uv pip install --python /app/.venv/bin/python psycopg2-binary`, que sí
  viene en la imagen.
- **`current_username()` en la cláusula de RLS no es SQL de Postgres.**
  Es un macro de **Jinja** de Superset (`{{ current_username() }}`, con
  llaves) que Superset interpola por su cuenta antes de mandar la consulta
  — sin las llaves, Postgres literalmente no tiene esa función.
  `scripts/superset_init.py` ya lo escribe bien.
- **Sin `ENABLE_TEMPLATE_PROCESSING: True`, ese macro tampoco se
  interpola** aunque esté bien escrito: la RLS queda comparando contra el
  texto literal `{{ current_username() }}`, nadie coincide nunca, y la
  consulta responde `200` con cero filas para todo el mundo — sin ningún
  error que lo delate. Ya está en `deploy/bi/superset_config.py`.
- **El rol `Gamma` de fábrica no alcanza los datos por sí solo**: sin
  `datasource_access` explícito por dataset, `POST /chart/data` devuelve
  403 `DATASOURCE_SECURITY_ACCESS_ERROR` aunque el usuario ya tenga el rol
  correcto. `scripts/superset_init.py` se lo otorga al rol `ProvechoBI`
  (los diez datasets, ni uno más — es exactamente lo único que la conexión
  `bi_lector` puede ver).

## Bugs encontrados contra el droplet real (no los detectó el CI de PR #130)

Los cinco aparecieron recién al ensayar contra Postgres/Superset reales — el
Docker local de la sección anterior no los reprodujo porque no hay proxy TLS
ni build de imagen final de por medio en ese ensayo:

- **`superset_init.py` (el script que registra la conexión `bi_lector` y
  arma la RLS) necesita `httpx`**, no solo `psycopg2-binary`. Faltaba en
  `deploy/bi/Dockerfile` — `ModuleNotFoundError` al correrlo.
- **`AUTH_TYPE = AUTH_OAUTH` necesita `authlib`**, tampoco instalado en la
  imagen — mismo síntoma. Los dos se resolvieron agregando ambos paquetes
  al `uv pip install` de `deploy/bi/Dockerfile`.
- **Indentación de YAML rompía `create-admin`.** El `command: >` (folded
  scalar) de `docker-compose.bi.yml` tenía las líneas de
  `--username`/`--firstname`/`--email`/`--password` con 2 espacios más que
  sus hermanas — en un folded scalar, una línea con *más* indentación que
  el resto no se pliega con un espacio, se preserva como bloque aparte, y
  `sh -c` la interpretó como un comando nuevo (`--username: not found`).
  Corregido igualando la indentación de todas las líneas del bloque.
- **Sin `ENABLE_PROXY_FIX = True`, Superset arma su `redirect_uri` en
  `http://`** aunque el dominio público sea `https://`: Caddy le habla por
  HTTP dentro de la red de Docker (TLS termina en Caddy), y sin el
  middleware `ProxyFix` de Werkzeug, Superset no tiene forma de saber que
  la conexión real llegó por HTTPS. La comparación de `redirect_uri` en
  `src/core/oauth/servicio.py` es exacta, no por prefijo — el esquema
  equivocado alcanza para que el login falle con `server_error` genérico.
- **Authlib manda `client_id`/`client_secret` por HTTP Basic por
  default** (RFC 6749 §2.3.1), pero `POST /oauth/token`
  (`src/core/oauth/router.py`) los espera como campos del form. FastAPI
  responde 422 antes de llegar a la lógica de negocio, sin ningún log de
  OAuth que lo explique — del lado de Superset solo aparece
  `Error returning OAuth user info: 'access_token'`, porque el token nunca
  llegó. Se agregó `"token_endpoint_auth_method": "client_secret_post"` a
  `client_kwargs` en `deploy/bi/superset_config.py`.

## Pendiente

- [x] Todo lo de la sección "Crear el droplet BI" — corrió contra el
      droplet real (`167.99.125.141`), login SSO confirmado de punta a
      punta con el usuario `admin`
- [ ] Fase D: permiso `bi.acceder` ya seedeado (Fase B); falta la entrada
      de navegación en `frontend/lib/modulos.ts` y los tableros embebidos
      en `/dashboard`
- [ ] **Verificación de fondo pendiente**: la prueba de RLS solo corrió con
      `admin` (superusuario, esperable que vea todo). Falta loguearse con un
      usuario `supervisor`/`contador` de una sola sucursal y confirmar que
      un dataset `vw_bi_*` de verdad se filtra a esa sucursal — y que
      "SQL Lab" no aparece en su menú (ver comentario en
      `deploy/bi/superset_config.py`: "SQL Lab es la puerta que ningún
      permiso de fila cierra"). Sin esto, Fase C no está probada, solo el
      login lo está.
- [ ] `docs/security/authorization.md` y ADR-083: marcar Fase C como hecha
      una vez que la verificación de RLS de arriba haya pasado
