# Observabilidad: errores, logs y salud

Tres preguntas distintas, tres herramientas distintas:

| Pregunta | Herramienta | Dónde |
|---|---|---|
| ¿Algo se rompió? | **GlitchTip** | `http://localhost:8088` |
| ¿Qué pasó antes de que se rompiera? | **Loki** vía **Grafana** | `http://localhost:3002` |
| ¿Está vivo ahora? | `/health/*` + monitor externo | ver ADR-007 |

Las tres viven en `docker-compose.observabilidad.yml`, **aparte del ERP**.
Son ocho contenedores que no son el negocio: si se caen, el restaurante
sigue vendiendo, y poder pararlos sin tocar `docker-compose.prod.yml` es
justo lo que se quiere el día que el VPS ande corto de memoria.

```bash
docker compose -f docker-compose.observabilidad.yml up -d
```

## Por qué GlitchTip y no Sentry SaaS

Decisión del 2026-08-04. ADR-006 dejó las dos abiertas porque **el código es
el mismo**: GlitchTip habla el protocolo de Sentry y `src/core/sentry.py` no
cambia una línea.

Pesa que los datos no salgan del VPS. Un reporte de error del ERP lleva
rutas, parámetros y trazas internas, y aunque `_limpiar_evento` redacta PIN,
tokens y cabeceras de autorización antes de enviar nada (y `send_default_pii`
está en `False`), lo que nunca sale de la máquina no hay que confiar en que
esté bien redactado.

El costo: hay que mantenerlo. Es un Postgres, un Redis y dos procesos más en
el mismo VPS.

## Puesta en marcha (una sola vez)

1. Completar en `.env` del host: `GLITCHTIP_DB_PASSWORD`,
   `GLITCHTIP_SECRET_KEY` (`openssl rand -hex 32`) y
   `GRAFANA_ADMIN_PASSWORD`. El compose **falla al arrancar** si faltan —
   preferible a levantar con una clave por defecto.
2. `docker compose -f docker-compose.observabilidad.yml up -d`
3. Entrar a `http://localhost:8088`, crear la cuenta (el registro abierto
   está deshabilitado: la primera cuenta es la del administrador) y crear la
   organización y el proyecto `provecho`.
4. Copiar el DSN del proyecto a `SENTRY_DSN` del `.env` **del ERP** y
   reiniciar `api`, `worker` y `beat`.
5. Comprobar que llega: forzar un error en un entorno de prueba y verlo
   aparecer en GlitchTip.

Sin el paso 4, el código sigue sin reportar nada — es exactamente el estado
en que estaba antes de esta decisión.

## Logs: por qué Loki con Alloy

El ERP ya emite **una línea de JSON por evento** cuando `LOG_JSON=true` o
`ENVIRONMENT=production` (`src/core/logging_config.py`), con `nivel`,
`flujo`, `logger`, `request_id` y `usuario_id`. Antes eso moría en
`docker logs`: consultable solo entrando al servidor, y perdido al recrear
el contenedor.

**Alloy** (el agente vigente de Grafana; Promtail quedó como legado) descubre
los contenedores por el socket de Docker —montado **solo lectura**— y empuja
sus logs a Loki. No hay que tocar la aplicación: ya escribe a stdout, que es
lo correcto para un contenedor.

### Qué es etiqueta y qué no

Loki crea un flujo por combinación de etiquetas, así que las etiquetas son
deliberadamente pocas y de cardinalidad baja: `nivel`, `flujo`, `entorno`,
más `servicio`/`contenedor`/`proyecto` que vienen de Docker.

`request_id` y `usuario_id` **no son etiquetas** — tienen tantos valores
distintos como requests, y ponerlos en el índice lo haría explotar. Quedan
en el cuerpo y se filtran con LogQL:

```logql
{entorno="production"} | json | request_id="a1b2c3..."
```

Grafana ya trae ese enlace armado: en cualquier línea de log, el
`request_id` es clicable y trae todas las demás líneas del mismo request.
Es la consulta que uno hace siempre cuando alguien reporta "me dio error"
con su identificador.

### Consultas útiles

```logql
# Todo lo que falló hoy en producción
{entorno="production", nivel="ERROR"}

# Flujo de seguridad: logins fallidos, lockouts, elevaciones
{flujo="seguridad"}

# Auditoría: quién tocó qué (metadatos; el detalle está en `audit_log`)
{flujo="auditoria"}

# La cocina: alertas de pedido demorado
{proyecto="provecho"} |= "pedido_demorado"
```

## Retención

90 días en ambos (GlitchTip por `GLITCHTIP_MAX_EVENT_LIFE_DAYS`, Loki por
`retention_period` + el compactor, que es quien la aplica de verdad). Más
que eso en un VPS es disco que nadie va a mirar; menos, y una regresión
estacional queda sin comparación.

**El log NO reemplaza al `audit_log`.** La tabla es el rastro legal, con su
propia retención; el log estructurado es lo que se vigila en vivo y lleva
solo metadatos, porque `datos_antes`/`datos_despues` pueden traer PII
(Ley 29733) que no debe salir del proceso.

## Puertos

| Servicio | Por defecto | Variable |
|---|---|---|
| GlitchTip | 8088 | `GLITCHTIP_PORT` |
| Grafana | 3002 | `GRAFANA_PORT` |
| Loki | 3100 | `LOKI_PORT` |

No son los "obvios" (8080, 3000/3001) porque esos chocan: en el host de
desarrollo el 8080 lo tenía otro servicio del negocio y el **3001 lo ocupa
`com.docker.backend`** cuando corre Docker Desktop. Son variables porque cada
host colisiona distinto.

## Qué contenedores se vigilan

Alloy ve **todo el host**, no solo este proyecto. Por defecto se filtra al
proyecto de compose `provecho-erp` (`ALLOY_PROYECTOS`), y no es un detalle
cosmético: al levantarlo por primera vez en un host que además corría otros
proyectos, Alloy empezó a mandar meses de logs ajenos a este Loki. Tres
problemas de una vez —logs de otras aplicaciones accesibles a quien tenga
Grafana, disco lleno de historia que nadie pidió, y Loki rechazándolos en
masa por antiguos, lo que llenaba el log de Alloy de errores que tapaban los
de verdad.

Para vigilar además otro proyecto:

```bash
ALLOY_PROYECTOS="provecho-erp|otro-proyecto"
```

## Seguridad

Los tres puertos se publican en `127.0.0.1`, no en `0.0.0.0`: son consolas
internas. El proxy decide cuáles se exponen y con qué autenticación delante.
**Ninguna de las tres debería quedar abierta a internet sin auth** — la de
Grafana y GlitchTip dan acceso a los errores y logs del ERP, que incluyen
información del negocio.

`ENABLE_open_USER_REGISTRATION` y `ENABLE_ORGANIZATION_CREATION` están en
`false`: sin eso, cualquiera con la URL se registra y ve los errores.

## Lo que sigue faltando

- **Monitor externo**: los endpoints `/health/*` no alertan a nadie por sí
  solos — el ERP expone, el monitor avisa (ADR-007). Hay que contratarlo y
  dar de alta las tres sondas: `/health` cada minuto, `/health/ready` cada
  5, `/health/backups` cada hora. Es lo único de observabilidad que no se
  puede resolver dentro del VPS: un monitor que corre en la misma máquina no
  avisa cuando la máquina se cae.
- **Métricas** (CPU, memoria, latencia): Loki guarda logs, no series
  temporales. Prometheus + node-exporter serían dos contenedores más; se
  difiere hasta que haya tráfico que justifique mirarlas.
- **Trazas de rendimiento**: `SENTRY_TRACES_SAMPLE_RATE` sigue en 0. GlitchTip
  las soporta parcialmente; subirlo cuando haya algo que perfilar.
