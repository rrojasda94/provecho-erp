# ADR-008 — Entrega continua: imagen publicada en GHCR, despliegue manual por ahora

- Estado: aceptado
- Fecha: 2026-07-26

## Contexto

La CI corría `ruff` + `pytest` + `eslint` + `build`, pero **nadie comprobaba
que la imagen Docker construyera**: un `Dockerfile` roto se descubría al
desplegar. Tampoco se validaba que Alembic tuviera una sola cabeza, cosa que
falla en `upgrade head` durante el despliegue y no en el merge que la creó.

Del lado del despliegue: todavía **no existe el servidor**. Escribir un job
de despliegue por SSH contra una máquina que no existe produce automatización
que nadie puede probar y que casi seguro tiene mal las rutas, el usuario y
los nombres de servicio.

## Decisión

Separar **entrega** de **despliegue**, y automatizar solo lo primero:

1. **CI** (`ci.yml`) gana tres verificaciones: cabeza única de Alembic,
   construcción de la imagen **y arranque real del contenedor** (se levanta y
   se le pide `/health`, lo que valida el `CMD`, el usuario sin privilegios y
   el `HEALTHCHECK`), más `pip-audit` en modo informativo.
2. **Entrega continua** (`release.yml`): cada push a `main` publica una
   imagen en **GHCR** (`ghcr.io`). Los tags `v*` publican además la versión
   exacta.
3. **Despliegue**: manual y documentado (`docker compose -f
   docker-compose.prod.yml pull && up -d`) hasta que exista el VPS.

Se agrega `docker-compose.prod.yml` porque el `docker-compose.yml` actual es
**solo de desarrollo**: monta el código, corre `uvicorn --reload` y levanta un
Postgres con contraseña de juguete. Desplegar con ese archivo publicaría una
configuración de desarrollo.

## Consecuencias

- La imagen corre como **usuario sin privilegios** (`provecho`, uid 10001) y
  trae `HEALTHCHECK` apuntando a `/health` (liveness, que no toca
  dependencias — ADR-007), así que un reinicio por ese chequeo significa que
  el proceso realmente murió.
- En producción **debe fijarse la etiqueta de versión**, no `latest`: es lo
  que permite volver atrás a una versión conocida. `latest` sirve para
  staging.
- La base de datos **no** está en el compose de producción: es gestionada
  (Supabase u otro Postgres propio) vía `DATABASE_URL`. Un Postgres dentro
  del mismo compose no tendría backups ni failover.
- En producción la API publica solo en `127.0.0.1:8000` y Redis no publica
  puerto: el proxy es la única puerta de entrada.
- `pip-audit` es informativo, no bloqueante: un aviso en una dependencia
  transitiva no puede frenar un arreglo urgente en caja. Pasa a bloqueante
  cuando haya rutina de revisión.
- `alembic upgrade head` sigue siendo un paso **explícito** del despliegue,
  no algo que la aplicación haga al arrancar (ver Alternativas).

## Alternativas descartadas

- **Job de despliegue por SSH ahora** — descartado: sin servidor no se puede
  probar, y automatización no probada da falsa confianza. Se escribe cuando
  exista el VPS, que es también cuando se conocen rutas y usuario reales.
- **Docker Hub como registro** — descartado: GHCR viene con el repositorio,
  autentica con el `GITHUB_TOKEN` del propio workflow (sin secreto que rotar)
  y no tiene los límites de descarga de Docker Hub.
- **Migrar al arrancar la aplicación** (`upgrade head` en el entrypoint) —
  descartado: con varias réplicas, todas migrarían a la vez, y una migración
  fallida dejaría el contenedor en bucle de reinicio en lugar de detenerse
  con un error claro. La migración es un paso del despliegue.
- **Despliegue tipo pull (GitOps, Watchtower)** — descartado por ahora:
  actualizar solo porque salió una imagen nueva quita el control de *cuándo*
  se despliega, que en un restaurante importa (no en hora pico).
- **Publicar también la imagen del frontend** — descartada por ahora: su
  `Dockerfile` sigue siendo de desarrollo (`npm run dev`), sin build de
  producción. Queda en deuda técnica.
