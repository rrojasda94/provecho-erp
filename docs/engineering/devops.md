# DevOps

## Docker

Todo corre en Docker. `docker compose up --build` levanta db (PostgreSQL 16),
redis, api (FastAPI), worker (Celery — emisión de comprobantes) y web
(Next.js).

**Local y servidor NO usan el mismo archivo** (corregido 2026-07-26, antes
esta guía afirmaba lo contrario): `docker-compose.yml` es de desarrollo
—monta el código, corre `uvicorn --reload` y trae un Postgres con contraseña
de juguete— y `docker-compose.prod.yml` es el de servidor. Ver
[Despliegue](#despliegue).

**Dos variables para la URL de la API en `web`, no una** (desde el
dashboard de 2026-07-26, ADR-012): `NEXT_PUBLIC_API_URL` es la vista del
**navegador** (fuera de los contenedores: `localhost`, puerto publicado);
`API_INTERNAL_URL` es la vista del **proceso de Next.js** (Server Actions/
Server Components, dentro del contenedor `web`) — usa el nombre del
servicio (`http://api:8000`), porque `web` y `api` son contenedores
distintos sin ningún `localhost` en común.

## Base de datos: Postgres en Supabase (desarrollo)

Desde 2026-07-20 el `DATABASE_URL` de desarrollo apunta a un proyecto
**Supabase** (Postgres gestionado) en vez del contenedor `db` local —
decisión del usuario para tener la BD visualizable (Table Editor) y
disponible en línea de cara al despliegue futuro. Nada del código cambia:
Supabase es Postgres real, Alembic corre igual.

**Límite explícito — no usar Supabase Auth ni RLS todavía:**
`users` (JWT + PIN + Argon2id + RBAC) sigue siendo la única fuente de
autenticación/autorización, y el aislamiento de tenant sigue por filtro de
aplicación (ADR-004, `empresa_id` obligatorio) — no por Row-Level Security
de Postgres. Activar Auth/RLS de Supabase encima crearía dos sistemas de
permisos compitiendo. Si en el futuro se evalúa RLS como refuerzo, es una
decisión aparte que actualiza ADR-004, no una consecuencia automática de
usar Supabase como hosting.

Connection string vive solo en `.env` (nunca en el repo — ver
`.env.example` para el formato, con el contenedor `db` local como
default documentado).

## Docker local (contenedor `db`) — sigue disponible

El servicio `db` de `docker-compose.yml` sigue existiendo para trabajar
sin conexión a internet o en CI; puerto de host **5433** (el 5432 local
lo ocupa la plataforma de Charlie's Pizzas — ver comentario en
`docker-compose.yml`). Cambiar `DATABASE_URL` en `.env` alterna entre
Supabase y el contenedor local.

## Entornos

`local → development → testing → staging → production`, cada uno con su
`.env` (plantilla: `.env.example`). Variable `ENVIRONMENT` controla el modo.
Secretos nunca en el repo.

Con `ENVIRONMENT=production` la aplicación **no arranca** si la configuración
quedó con valores de desarrollo (`src/config/settings.py`): `JWT_SECRET`
placeholder o menor a 32 caracteres, `DEBUG=true`, `DATABASE_URL` con la
contraseña por defecto, o `ALLOWED_HOSTS`/`CORS_ORIGINS` en `*`. Es una
falla de arranque deliberada: preferimos un despliegue caído a un ERP
publicado sin autenticación real.

## Despliegue en VPS (nginx/Caddy delante)

TLS termina en el proxy; la aplicación nunca escucha en HTTPS directamente.

1. El proxy redirige `80 → 443` y hace `proxy_pass` a `127.0.0.1:8000`.
2. El proxy envía `X-Forwarded-For` y `X-Forwarded-Proto` (nginx:
   `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` y
   `proxy_set_header X-Forwarded-Proto $scheme;`; Caddy lo hace solo).
3. uvicorn corre con `--proxy-headers` (ya está en el `CMD` del Dockerfile) y
   con `FORWARDED_ALLOW_IPS=<IP del proxy>`. **Nunca `*`**: permitiría a
   cualquiera falsificar su IP y saltarse el rate limit del login.
4. `ALLOWED_HOSTS` con el dominio real y `CORS_ORIGINS` con el origen del
   frontend — ambos exactos, sin comodines.

La cabecera `Strict-Transport-Security` la emite la propia aplicación cuando
`ENVIRONMENT=production` (un año, `includeSubDomains`), junto con
`X-Content-Type-Options`, `X-Frame-Options` y `Referrer-Policy`.

En producción `/docs` y `/openapi.json` quedan deshabilitados: el mapa de la
API expone esquemas y nombres de permisos.

## Rotación de credenciales

Runbook mínimo. Frecuencia base: anual, e **inmediata** ante sospecha de
filtración o salida de alguien con acceso a producción.

- **`JWT_SECRET`** — generar con
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`, reemplazar
  en `.env` y reiniciar. Los access token vigentes (15 min) quedan inválidos,
  pero el refresh token se valida contra hash en base de datos, no contra el
  secreto: los clientes renuevan solos y nadie vuelve a loguearse. No hace
  falta ventana de convivencia de dos secretos.
- **Contraseña de Postgres** — cambiar en el gestor (Supabase o `ALTER ROLE`),
  actualizar `DATABASE_URL` y reiniciar la aplicación.
- **Tokens de integraciones** (Factiliza, Izipay, Google, Meta) — revocar en
  el proveedor primero, luego actualizar `.env`.
- **PIN de usuario comprometido** — se resetea desde el CRUD de `users`; no
  requiere despliegue.

Tras cualquier rotación: verificar `/health`, un login real y un refresh.

## Custodia de secretos

`.env` vive solo en el servidor, fuera del repo, con permisos `600` y dueño
el usuario que corre la aplicación (`chmod 600 .env && chown app:app .env`).
Nunca se copia por chat ni por correo. El repositorio solo contiene
`.env.example` con placeholders. Un secreto que llegó a un commit se
considera quemado: rotarlo, no borrarlo del historial y darlo por seguro.

## CI/CD

GitHub Actions. Ver ADR-008 para el porqué de separar entrega de despliegue.

**`ci.yml`** — en cada push a `main` y en cada PR:

| Job | Qué verifica |
|-----|--------------|
| `backend` | `ruff check`, `pytest`, y que Alembic tenga **una sola cabeza** |
| `imagen` | que el `Dockerfile` construya **y que el contenedor arranque** y responda `/health` |
| `seguridad` | `pip-audit` (informativo, no bloquea) |
| `frontend` | `eslint` + `build` |

El chequeo de cabeza única atrapa el caso en que dos ramas crean migraciones
en paralelo: `alembic upgrade head` falla durante el despliegue, no en el
merge que lo causó. El job `imagen` cubre lo que nadie comprobaba — que la
imagen siquiera construyera — y de paso valida el `CMD`, el usuario sin
privilegios y el `HEALTHCHECK`.

**`release.yml`** — entrega continua del artefacto: cada push a `main`
publica la imagen en GHCR (`ghcr.io/<repo>:latest`); los tags `v*` publican
además la versión exacta (`:1.2.3`, `:1.2`).

### Despliegue

Manual mientras no exista el servidor. `docker-compose.yml` es **solo
desarrollo** (monta el código, `--reload`, Postgres con contraseña de
juguete); producción usa `docker-compose.prod.yml`.

```bash
export PROVECHO_IMAGE=ghcr.io/<repo>:1.2.3   # fijar versión, nunca latest
docker compose -f docker-compose.prod.yml pull
alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
curl -fsS https://ERP/health/ready
```

En producción se fija la **etiqueta de versión**, no `latest`: es lo que
permite volver a una versión conocida. `alembic upgrade head` es un paso
explícito y no algo que la aplicación haga al arrancar — con varias réplicas
todas migrarían a la vez, y una migración fallida dejaría el contenedor en
bucle de reinicio en vez de detenerse con un error legible.

La base de datos no está en el compose de producción: es gestionada, apuntada
por `DATABASE_URL`. La API publica solo en `127.0.0.1:8000` y Redis no
publica puerto — el proxy es la única puerta de entrada.

## Migraciones

Solo Alembic, versionadas en `alembic/versions/`. Nunca modificar la DB a
mano en producción. `alembic upgrade head` como paso de despliegue.

### Verificar que la base y el modelo cuentan la misma historia

```bash
docker compose exec api python -m src.core.esquema
```

Sale `0` si el esquema está al día y `1` con el detalle si no. Responde dos
preguntas que fallan distinto:

- **Faltan tablas que el modelo declara.** Mira el estado real, no el
  marcador: atrapa la migración *marcada y no corrida*, la aplicada a
  medias y la base restaurada de un backup viejo.
- **La revisión no coincide con la cabeza del repo.** Mira el marcador:
  atrapa el despliegue al que le falta `alembic upgrade head` aunque todas
  las tablas existan (una migración que solo agrega columnas o índices no
  se nota en la lista de tablas).

El mismo chequeo corre **al arrancar el servidor** (`src/main.py`): en
producción **aborta el arranque**, en desarrollo solo deja un warning en el
log. Mismo criterio que la validación de configuración: un ERP que arranca
contra un esquema incompleto atiende requests hasta que alguien toca la
pantalla equivocada, y ahí el error aparece lejos de su causa.

**Por qué existe** (2026-08-04): las dos bases de desarrollo —la local de
Docker y la de Supabase— tenían `alembic_version` en una revisión
*posterior* a la que crea `decision_gerencial`, sin que la tabla existiera.
`alembic current` decía "al día", el CI estaba verde (`alembic check` compara
modelo contra migraciones **sobre una base limpia**, no contra la base real)
y `GET /decisiones-gerenciales` respondía 500. Se descubrió abriendo la
pantalla, que es exactamente lo que este comando evita.

Se compara solo la **existencia de tablas**, no columnas ni tipos: es el
grueso del daño con muy poco código, y comparar columna a columna contra
`Base.metadata` da falsos positivos por detalles de dialecto. Para eso ya
está `alembic check` en CI.

## Monitoreo y observabilidad

Implementado 2026-07-26 (`src/core/logging_config.py`, `src/core/sentry.py`).

**Logs.** Una línea de JSON por evento en producción (`LOG_JSON=true` lo
fuerza fuera de ella); texto legible en local. Campos fijos: `ts`, `nivel`,
`flujo`, `logger`, `mensaje`, `app`, `entorno`, más `request_id` y el
contexto que cada llamada agregue por `extra=`.

**Tres flujos**, derivados del nombre del logger para no arrastrar un
parámetro en cada llamada:

| Flujo | Logger | Qué registra |
|-------|--------|--------------|
| `seguridad` | `provecho.seguridad.*` | login fallido, bloqueo de cuenta, reuso de refresh token, rate limit superado |
| `auditoria` | `provecho.auditoria.*` | espejo del `audit_log` de base de datos |
| `app` | cualquier otro | acceso HTTP, errores, listeners, tareas |

**Correlación.** Cada request recibe un `request_id` (se respeta el
`X-Request-ID` entrante, para seguir una traza que ya venía del proxy o del
frontend) que viaja en un `contextvar`, sale en la cabecera `X-Request-ID`
de toda respuesta y aparece en cada línea de log del request. Un error no
controlado devuelve `{"detail": "Error interno", "request_id": "..."}`: sin
ese identificador, un "me dio error" de un cajero no se puede cruzar con
ningún log.

**Datos sensibles.** PIN, contraseñas, tokens, cabeceras `Authorization` y
`Cookie` se redactan antes de escribir el log y antes de salir hacia Sentry
(`CLAVES_SENSIBLES` en `logging_config.py`). El ERP maneja datos de
trabajadores y clientes (Ley 29733): `send_default_pii=False` y nunca se
adjunta el cuerpo del request.

**Reporte de errores.** `SENTRY_DSN` vacío = no se envía un solo byte, que
es el caso de local y de los tests. El DSN sirve igual para **Sentry** (SaaS,
tiene plan gratis) y para **GlitchTip** autoalojado, que habla el mismo
protocolo — la decisión de cuál usar no cambia el código. Se inicializa en
tres componentes, etiquetados con el tag `componente`:

- `api` — en `create_app()`.
- `worker` — en la señal `celeryd_init`; sin esto, un comprobante que agota
  sus reintentos contra Factiliza falla en silencio.
- `backups` — en el `main()` del comando; un backup que falla de madrugada
  no lo lee nadie.

`sentry-sdk` va en las dependencias base a propósito: como extra opcional,
un despliegue que olvidara instalarlo se quedaría justo sin lo que avisa que
algo falla.

Pendiente: métricas (CPU, memoria, latencia, disponibilidad), trazas de
rendimiento (`SENTRY_TRACES_SAMPLE_RATE` está en 0) y envío de los logs a un
colector. Ver ROADMAP → Deuda técnica → Observabilidad.

## Chequeos de salud y alertas

Implementado 2026-07-26 (`src/core/health.py`, ADR-007). **El ERP no manda
alertas por su cuenta**: expone su estado y un monitor externo hace el aviso.
Un sistema de alertas que vive en el servidor que monitorea deja de avisar
exactamente cuando ese servidor cae.

| Endpoint | Qué responde | Devuelve 503 cuando |
|----------|--------------|---------------------|
| `GET /health` | Liveness: el proceso responde | nunca |
| `GET /health/ready` | Readiness: base de datos, Redis, cola de tareas | cae una dependencia crítica |
| `GET /health/backups` | Horas desde el último backup | pasaron más de `HEALTH_BACKUP_MAX_HORAS` (26) |

Criterios:

- **La base de datos es crítica** → `caido` y 503. Sin ella el ERP no atiende
  nada.
- **Redis y la cola son degradantes, no críticos** → 200 con estado
  `degradado`. Sin Redis el rate limit falla abierto y los comprobantes
  esperan, pero la caja tiene que poder seguir vendiendo.
- **Los backups no entran en el readiness.** Que falte un backup es grave,
  pero devolver 503 por eso sacaría la API de rotación y dejaría al
  restaurante sin vender. Por eso tienen endpoint propio.
- **Liveness no toca dependencias.** Si fallara por la base de datos, el
  orquestador reiniciaría en bucle un proceso perfectamente sano.
- Los endpoints son **públicos** (un monitor externo no puede loguearse), así
  que devuelven estados y nunca hostnames, DSN ni errores crudos. El detalle
  va al log.

**Monitor externo** (elegir uno: healthchecks.io, UptimeRobot, Uptime Kuma
autoalojado):

| Sondear | Cada | Alerta si |
|---------|------|-----------|
| `https://ERP/health` | 1 min | no responde 200 |
| `https://ERP/health/ready` | 5 min | responde 503, o `status` = `degradado` sostenido |
| `https://ERP/health/backups` | 1 h | responde 503 |

El de backups es el que cubre el hueco que el reporte de errores no puede
cubrir: un backup que **falla** avisa por Sentry, pero uno que **nunca
corrió** (cron desactivado, servidor reinstalado) no genera ningún evento.
Solo se detecta preguntando por la frescura del último archivo.

Nginx puede usar `/health/ready` como `proxy_next_upstream` para sacar de
rotación un nodo que perdió la base de datos.

## Backups

Implementado en `src/backups/backup.py` (2026-07-26). **Diarios, retención
30 días** — el criterio anterior de "mensual e incremental" implicaba perder
hasta 30 días de ventas; un dump completo de este ERP pesa megas, lo
incremental no compra nada y complica la restauración.

```bash
python -m src.backups.backup
```

Cuatro pasos en un solo comando, y sale con código 1 si cualquiera falla
(para que el cron lo pueda alertar):

1. **Dump** — `pg_dump --format=custom` a `BACKUP_DIR`. La contraseña viaja
   por `PGPASSWORD`, nunca en `argv`: `ps` lo muestra a cualquier usuario del
   servidor.
2. **Verificación del archivo** — firma del dump + `pg_restore --list` y
   comprobación de que trae las tablas críticas (`venta`, `comprobante`,
   `movimiento_inventario`, `usuario`). Detecta el caso frecuente y peor: un
   dump truncado por disco lleno, que parece sano.
3. **Restauración probada** — si `BACKUP_VERIFY_DATABASE_URL` apunta a una
   base desechable, restaura ahí de verdad y cuenta filas. **Es la única
   prueba real de que el backup sirve**; sin esa variable el comando avisa
   que solo validó el archivo. El script se niega a restaurar sobre la base
   de origen (`pg_restore --clean` borra el esquema antes de escribir).
4. **Copia externa y purga** — sube a S3 si hay credenciales, y borra lo que
   excede la retención. La purga **nunca borra el backup más reciente**,
   aunque esté fuera de retención: si el cron llevaba meses caído, borrarlo
   dejaría al ERP sin ninguna copia.

**Requisitos.** `postgresql-client` en el host (`pg_dump`, `pg_restore`,
`psql`), con versión de cliente **mayor o igual** a la del servidor — un
cliente viejo contra un Postgres nuevo falla. Para la copia externa:
`pip install -e ".[backups]"` (boto3 es dependencia opcional; la imagen de
la API no la carga).

**Programación — cron del host**, no Celery beat: el backup debe correr
justo cuando la aplicación está caída, que es cuando más falta hace.

```cron
0 3 * * * cd /srv/provecho && .venv/bin/python -m src.backups.backup >> /var/log/provecho-backup.log 2>&1
```

**Restaurar de verdad** (incidente real, no prueba):

```bash
pg_restore -h HOST -U provecho -d provecho --clean --if-exists --no-owner backups/provecho-AAAAMMDD-HHMMSS.dump
```

Pendiente: alerta cuando el backup falla o cuando no hubo uno en 48 h — hoy
solo queda en el log. Ver ROADMAP → Deuda técnica → Backups.

## Purga de datos de postulantes (Ley 29733)

Anonimiza las fichas de candidatos no contratados cuyo plazo de conservación
declarado ya venció (RN-PER-004). Sin esto el aviso de privacidad promete un
plazo que el sistema no cumple. Mismo criterio que los backups —cron del
host, no Celery beat— y semanal alcanza: el plazo se mide en meses.

```cron
30 3 * * 0 cd /srv/provecho && .venv/bin/python -m src.modules.rrhh.purga >> /var/log/provecho-purga.log 2>&1
```

El plazo por ficha se fija al crearla con
`RRHH_PLAZO_CONSERVACION_POSTULANTE_MESES` (12 por defecto); el comando nunca
toca a un postulante contratado, cuya retención es laboral y no la del aviso
de privacidad. **Pendiente: darlo de alta en el servidor** — hasta entonces
el plazo no se aplica en la práctica.

## Modo offline del PDV — hub local de sucursal

Fase 1 (diseño + plumbing) 2026-07-26; fase 2 (motor de sync) 2026-07-27.
Arquitectura completa y alternativas descartadas:
[ADR-009](../architecture/adr/ADR-009-modo-offline-pdv.md).

Un mini-PC o Raspberry Pi **dedicado, siempre encendido**, en la LAN de cada
sucursal, corre **la misma imagen** del backend contra su **propio Postgres
local**. Todos los dispositivos del local (PDV web, Android, PC, KDS) le
hablan siempre al hub, nunca directo a internet — el hub decide si tiene
camino a la nube; los clientes ni se enteran.

### Desplegar un hub

```bash
cp .env.hub.example .env
# completar JWT_SECRET (el mismo que la nube), HUB_EMPRESA_ID,
# HUB_SUCURSAL_ID, CLOUD_SYNC_URL y la cuenta de servicio del hub.
docker compose -f docker-compose.hub.yml up -d
docker compose -f docker-compose.hub.yml exec api alembic upgrade head
curl http://localhost:8000/health/sync
```

A diferencia de `docker-compose.prod.yml` (que solo escucha en loopback
detrás de un proxy), el hub publica el puerto **a toda la LAN**: es
justamente lo que los dispositivos del local necesitan alcanzar. Sin
Celery/Redis/worker — la emisión de comprobantes a Factiliza ocurre solo en
la nube, después de sincronizar, así que el hub no necesita cargar esa cola.

### Detector de conectividad

`src/core/sync/estado_conexion.py` pinguea el `/health` (liveness) de la
nube. Una racha de `SYNC_FALLOS_PARA_OFFLINE` fallos seguidos (no uno solo —
un timeout puntual de red no puede tumbar el estado) declara `offline`; un
solo éxito vuelve a `en_linea` de inmediato. Expuesto en
`GET /health/sync`, **siempre 200**: a diferencia de `/health/ready`, estar
offline es el modo de diseño del hub durante un corte, no un fallo — sacarlo
de rotación por eso sería exactamente lo contrario de lo necesario. Es
diagnóstico para que un monitor externo avise si lleva offline demasiado
tiempo, no una señal de "dejá de servir".

### Alta de la cuenta de servicio del hub

Antes de levantar el hub hay que crearle su cuenta **en la nube**: una por
sucursal, con el rol `hub_sucursal` (solo `sync.leer` y `sync.empujar`) y
alcance a esa única sucursal — de ahí sale el tenant que la API de sync
aplica a todo lo que el hub pide.

```bash
# en el servidor de la nube
python -m src.seeders.hub --sucursal <HUB_SUCURSAL_ID> --username hub_tarapoto
# el PIN se pide por consola; va a CLOUD_SYNC_PIN en el .env del hub
```

Idempotente: repetirlo no duplica nada. `--rotar-pin` cambia el PIN de una
cuenta ya existente.

### Motor de sync

El hub corre **dos procesos** (servicios `api` y `sync` del compose):

| Proceso | Qué hace |
|---------|----------|
| `api` | Atiende a los dispositivos de la LAN. Nunca depende de internet. |
| `sync` | `python -m src.core.sync.runner`: cada `SYNC_INTERVALO_SEGUNDOS`, un ciclo. |

Separados a propósito: si el sync se traba, el PDV del local sigue
vendiendo. Un ciclo es **empujar y después jalar**, en ese orden (el porqué,
en el ADR):

1. **Push** — las ventas, cobros y anulaciones del corte se reproducen en la
   nube por `POST /sync/push`, con su mismo `id`, `idempotency_key`,
   `fecha_orden` y `numero_orden`. La nube las procesa con los mismos casos
   de uso de siempre: descuenta su propio stock y prepara los comprobantes.
   El hub **no** empuja movimientos de inventario (los genera el listener de
   la nube; empujarlos duplicaría el consumo).
2. **Pull** — `GET /sync/pull` por recurso, incremental por `updated_at`.
   Baja organización, RBAC (incluido `pin_hash`, sin el cual nadie se
   autentica offline), catálogo de inventario, stock y catálogo comercial.

`GET /sync/recursos` lista el contrato vigente: qué baja un hub y por qué
necesita cada tabla.

### Diagnóstico del sync

`GET /health/sync` (sin auth, siempre 200) muestra el estado de conexión y
**el avance por recurso**, leído de la tabla `sync_watermark`:

```json
{"aplica": true, "estado": "en_linea", "recursos": [
  {"direccion": "pull", "recurso": "producto_comercial",
   "marca": "2026-07-27T10:00:00+00:00", "ultimo_ok": "2026-07-27T10:01:00+00:00",
   "ultimo_error": null}]}
```

Qué mirar cuando algo no cuadra:

- `ultimo_error` con texto → ese recurso **no avanza** y se reintenta cada
  ciclo. Es a propósito: perder una venta en silencio es peor. Los demás
  recursos siguen sincronizando.
- `ultimo_ok` viejo en todos los recursos → el runner está caído o la nube
  no responde; revisar `docker compose -f docker-compose.hub.yml logs sync`.
- `estado: offline` → no hay internet. El local sigue vendiendo; no hay nada
  que hacer más que esperar (o revisar el enlace).

### Después de una migración de esquema

Un hub que estuvo días sin conexión necesita su propio `alembic upgrade
head` antes de sincronizar contra una nube ya migrada — mismo runbook que la
nube (ADR-008), repetido por sucursal:

```bash
docker compose -f docker-compose.hub.yml exec api alembic upgrade head
```
