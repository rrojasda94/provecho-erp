# Staging

Runbook y bitácora del entorno de staging. Complementa
[devops.md](devops.md) — acá va lo específico de *este* servidor, no lo
general del despliegue.

**Nunca poner acá:** contraseñas, tokens, passphrases, ni el contenido de
`.env`. Esos viven en el gestor de contraseñas de quien los generó y en el
`.env` del servidor (fuera del repo, permisos 600).

## Datos del servidor

| Dato | Valor |
|---|---|
| Proveedor | DigitalOcean |
| Nombre del droplet | `provecho-staging` |
| Región | NYC3 |
| Tamaño | 2 vCPU / 4 GB RAM / 80 GB SSD (~$24/mes) |
| IP pública | `165.227.120.112` |
| SO | Ubuntu 24.04 LTS |
| Dominio frontend | `staging.majambo.com.pe` |
| Dominio API | `api-staging.majambo.com.pe` |
| Usuario de la app | `app` (sudo, sin login root, sin login por contraseña) |
| Llave SSH | `renato-provecho` — privada en `~/.ssh/provecho_droplet` (tu PC, nunca en el repo) |

> La IP puede cambiar si el droplet se recrea (ya pasó una vez durante el
> setup inicial, 2026-08-23). Si cambia: actualizar los dos registros A del
> dominio y esta tabla.

## Decisiones tomadas

- **Factiliza en staging: activo**, con el token de QA que ya usa
  desarrollo (`FACTILIZA_BASE_URL` de QA). Los comprobantes emitidos en
  staging no son reales ante SUNAT.
- **WhatsApp: en espera.** `WHATSAPP_TOKEN` queda vacío por ahora — la
  encuesta de satisfacción sigue funcionando por enlace público, sin envío.
- **Base de datos:** Postgres dentro del propio droplet (no gestionado). Para
  staging los datos son desechables; no vale la pena pagar un Postgres
  gestionado aparte. Ver `docker-compose.staging.yml`.
- **Proxy/TLS:** Caddy (certificado HTTPS automático), no nginx+certbot a
  mano.

## Setup ya hecho (2026-08-23)

- [x] Droplet creado, llave SSH `renato-provecho` verificada
- [x] Usuario `app` (sudo) creado, con contraseña propia para `sudo`
- [x] Docker instalado, `app` en el grupo `docker`
- [x] Firewall (`ufw`): solo 22/80/443
- [x] DNS: `staging.majambo.com.pe` y `api-staging.majambo.com.pe` →
      `165.227.120.112`
- [x] Token de GitHub (`read:packages`) generado, para `docker login ghcr.io`
      — vive solo en la sesión del servidor, nunca en el repo
- [x] Login root/password cerrado por SSH (`PermitRootLogin no`,
      `PasswordAuthentication no`), confirmado con `app` entrando y `root`
      rechazado — la Droplet Console de DigitalOcean también entra como
      root, así que quedó sin acceso a propósito (usar `sudo -i` desde `app`)
- [x] Droplet recreado una vez (la llave SSH no había quedado marcada al
      crear el primero) — IP final `165.227.120.112`, DNS actualizado
- [x] `docker-compose.staging.yml` + `Caddyfile` escritos y copiados a mano
      al servidor (todavía no commiteados — ver «Pendiente»)
- [x] `release.yml` arreglado para publicar también la imagen del frontend
      (`ghcr.io/rrojasda94/provecho-erp-web`)
- [x] `.env` real creado en el servidor (`~/provecho-staging/.env`,
      `POSTGRES_PASSWORD`/`JWT_SECRET` generados ahí mismo, nunca en un chat)
- [x] `docker login ghcr.io` en el servidor con el token de lectura
- [x] Stack levantado (`docker compose -f docker-compose.staging.yml up -d`),
      migración + seeder corridos por el servicio `init`
- [x] **Login probado en el navegador — funciona.** `admin` / PIN `123456`
      en `https://staging.majambo.com.pe`

## Bug encontrado y resuelto (2026-08-23)

**`ALLOWED_HOSTS` solo con el dominio público rompe el tráfico interno.**
El `HEALTHCHECK` del contenedor pega a `http://127.0.0.1:8000/health`
(`Host: 127.0.0.1`) y el frontend le habla a la API por la red de Docker
(`API_INTERNAL_URL=http://api:8000`, `Host: api:8000`) — ninguno de los dos
pasa por el dominio público, así que `TrustedHostMiddleware` los rechazaba
con 400. El login fallaba en el navegador ("Error 400") aunque el dominio
público funcionaba perfecto por `curl`.

Arreglo: `ALLOWED_HOSTS=api-staging.majambo.com.pe,api,localhost,127.0.0.1`.
Ya corregido en `.env.staging.example` y documentado en
`devops.md#despliegue-en-vps-nginxcaddy-delante`. **Aplicar el mismo
criterio si algún día se arma un compose de producción con el frontend
adentro.**

## Bug encontrado y resuelto (2026-08-24)

**Caddy cachea la IP del upstream y devuelve 502 después de cada redeploy.**
`reverse_proxy api:8000` resuelve el nombre en la red de Docker **una vez, al
arrancar**. Un `docker compose up -d` que recrea `api` le asigna una IP nueva,
y Caddy —que no se recreó— sigue hablándole a la vieja. El síntoma es un 502
en `https://api-staging.majambo.com.pe` con la API perfectamente sana:
`api` figura `Up (healthy)` y `curl http://127.0.0.1:8000/health/ready`
responde. Pasó desplegando la 0.7.2.

Lo delata el `docker compose ps -a`: `caddy` con 21 horas de vida y `api` con
4 minutos.

Parche de hoy: `docker compose restart caddy` después de cada despliegue, ya
incorporado al comando de arriba. **La solución de fondo es que Caddy
re-resuelva el DNS solo** (`dynamic a` en el `Caddyfile`), anotada en
[`deuda/ci-cd.md`](../roadmap/deuda/ci-cd.md) — no se aplicó de una porque un
`Caddyfile` inválido deja staging sin proxy, y hay que validarlo contra el
servidor antes de recargarlo.

## Pendiente

- [x] Commiteado y en PR: [#91](https://github.com/rrojasda94/provecho-erp/pull/91)
      — falta merge (CI verde + revisión)
- [x] Cron de backup diario en el droplet — **no usa `src/backups/backup.py`**
      (la imagen de la API no trae `postgresql-client` ni `boto3`): en su
      lugar `scripts/backup-staging.sh` hace `pg_dump` desde el propio
      contenedor `db`, con retención de 30 días. Probado a mano, OK.
- [x] Cron de purga semanal de postulantes (`python -m src.modules.rrhh.purga`,
      vía `docker compose exec api`)
- [x] Monitor externo (UptimeRobot) dado de alta contra `/health`,
      `/health/ready`, `/health/backups`
- [ ] **`scripts/desplegar.sh` no está en el droplet** (2026-08-24): el repo
      nunca se clonó ahí, así que el script que este runbook manda correr no
      existe y el despliegue falla con `No such file or directory`. Mientras
      tanto, desplegar con el `docker compose` equivalente (ver Despliegue,
      abajo). Anotado en [`deuda/ci-cd.md`](../roadmap/deuda/ci-cd.md).
- [ ] **Errores de backend encontrados probando staging** — se están
      revisando en otra sesión de trabajo, no repetir el diagnóstico acá
- [ ] **Cambio de recetas en camino** (mencionado 2026-08-23, sin detalle
      todavía): al terminar, sube por el flujo normal (PR → CI verde →
      merge → `release.yml` publica `latest` → `docker compose pull && up -d`
      en el servidor — ver sección Despliegue de `devops.md`)

## Comandos de referencia

Entrar al servidor:

```bash
ssh -i "$env:USERPROFILE\.ssh\provecho_droplet" app@165.227.120.112
```

Ver estado del stack (una vez levantado):

```bash
docker compose -f docker-compose.staging.yml ps
docker compose -f docker-compose.staging.yml logs -f api
```

Desplegar una versión nueva. `scripts/desplegar.sh` haría esto mismo y
además esperaría a `/health/ready`, pero **el repo no está en el droplet**
(ver Pendiente), así que hoy va a mano desde la carpeta del compose:

```bash
PROVECHO_IMAGE=ghcr.io/rrojasda94/provecho-erp:0.7.2 PROVECHO_WEB_IMAGE=ghcr.io/rrojasda94/provecho-erp-web:0.7.2 docker compose -f docker-compose.staging.yml up -d --pull always
docker compose -f docker-compose.staging.yml restart caddy
```

El servicio `init` corre `alembic upgrade head` antes de que arranque `api`
(`depends_on: service_completed_successfully`), así que la migración no
necesita paso aparte. **El `restart caddy` no es opcional** — ver el bug de
abajo. Después, confirmar:

```bash
curl -fsS https://api-staging.majambo.com.pe/health/ready && echo OK
```

Si eso da 502, el diagnóstico es de una línea: comparar el `CREATED`/`STATUS`
de `caddy` contra el de `api` en `docker compose ps -a`. Si Caddy es mucho
más viejo, es esto.
