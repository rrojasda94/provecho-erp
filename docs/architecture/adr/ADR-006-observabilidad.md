# ADR-006 — Observabilidad: logs estructurados propios, errores a Sentry

- Estado: aceptado
- Fecha: 2026-07-26

## Contexto

El ERP tenía tres puntos que fallaban en silencio absoluto: un comprobante
que agotaba sus reintentos contra Factiliza, un backup nocturno que no
corría, y el rate limit desactivándose por una caída de Redis. Ninguno
avisaba a nadie. `security.md` ya declaraba tres flujos de logs
(aplicación, seguridad, auditoría) que en el código no existían.

## Decisión

Dos piezas separadas, porque resuelven problemas distintos:

1. **Logs estructurados con la biblioteca estándar** (`logging` + un
   formateador JSON propio, ~120 líneas). Sin dependencia nueva.
2. **Reporte de errores con `sentry-sdk`**, apuntando a Sentry SaaS o a
   GlitchTip autoalojado — hablan el mismo protocolo, así que **la elección
   del backend no es una decisión de arquitectura**: es un DSN en `.env` y
   puede cambiarse sin tocar código.

El flujo de cada log se deriva del nombre del logger (`provecho.seguridad.*`
→ flujo `seguridad`) en lugar de pasarse como parámetro, para que agregar
logging a un módulo no obligue a recordar un argumento extra.

La correlación es un `request_id` por request, propagado por `contextvar`,
devuelto en la cabecera `X-Request-ID` y en el cuerpo de todo error 500.

## Consecuencias

- `sentry-sdk` va en las **dependencias base**, no en un extra opcional. Como
  extra, un despliegue que olvidara instalarlo se quedaría justo sin la pieza
  que avisa que algo falla — el modo de fallo que este ADR viene a cerrar.
- Sin `SENTRY_DSN` no se envía un solo byte: local y tests quedan mudos por
  defecto, sin necesidad de configurar nada.
- **Redacción obligatoria** antes de escribir un log y antes de enviar a un
  tercero: PIN, contraseñas, tokens, `Authorization`, `Cookie`. Un log que
  guarda lo que la autenticación protege es una brecha. Con
  `send_default_pii=False` y sin cuerpo de request, por Ley 29733 (el ERP
  maneja datos de trabajadores y clientes).
- Se inicializa en tres componentes etiquetados (`api`, `worker`, `backups`),
  no solo en la API: los otros dos eran justamente los que fallaban callados.
- `configurar_logging` etiqueta su handler y retira solo el propio, para no
  desconectar a un colector externo que ya esté escuchando el root logger.
- Queda pendiente el **colector**: hoy el JSON sale a stdout y muere en
  `docker logs`/journald. Elegir destino (Loki u otro) es una decisión
  posterior que este diseño no bloquea — el formato ya es el que un colector
  espera.

## Alternativas descartadas

- **`structlog`** — resuelve bien el problema, pero es una dependencia para
  algo que la biblioteca estándar cubre en unas decenas de líneas. La
  complejidad de `structlog` se paga cuando hay procesadores encadenados y
  binding de contexto en muchos puntos; acá hay un formateador y un
  `contextvar`.
- **Solo logs, sin reporte de errores** — más barato, pero nadie lee logs de
  madrugada. El agrupamiento de errores repetidos y la alerta al momento son
  precisamente lo que no se construye a mano.
- **Elegir ya entre Sentry SaaS y GlitchTip** — innecesario: el protocolo es
  el mismo y la decisión no afecta al código. Se difiere al despliegue.
- **Agente de métricas (Prometheus/OpenTelemetry) en este paso** — descartado
  por ahora: sin tráfico real que perfilar, agrega infraestructura que nadie
  mira. `SENTRY_TRACES_SAMPLE_RATE` queda en 0, listo para subirse cuando
  haya algo que medir.

## Addendum (2026-08-04) — resuelta la elección diferida

Este ADR difirió a propósito la elección entre **Sentry SaaS** y
**GlitchTip autoalojado**, porque el protocolo es el mismo y la decisión no
tocaba el código. Se resolvió al desplegar: **GlitchTip, en el mismo VPS**.

Lo que inclinó la balanza no fue el precio sino el dato. Un reporte de error
del ERP lleva rutas, parámetros y trazas internas; `_limpiar_evento` redacta
PIN, tokens y cabeceras de autorización antes de enviar nada y
`send_default_pii` está en `False`, pero **lo que nunca sale de la máquina
no hay que confiar en que esté bien redactado**. Con un ERP que maneja datos
de trabajadores y clientes bajo Ley 29733, esa diferencia pesa más que el
mantenimiento extra.

Costo aceptado: un Postgres, un Redis y dos procesos más en el mismo VPS.

`src/core/sentry.py` **no cambió una línea**, que es exactamente lo que este
ADR predijo al diferir la decisión.

En el mismo movimiento se cerró la otra pieza que faltaba: el **colector de
logs**. El ERP ya emitía una línea de JSON por evento, pero moría en
`docker logs` — consultable solo entrando al servidor y perdido al recrear
el contenedor. Ahora **Alloy** (el agente vigente de Grafana; Promtail quedó
como legado) descubre los contenedores por el socket de Docker montado en
solo lectura y los empuja a **Loki**, con **Grafana** para consultarlos.

Decisión de diseño que importa: `nivel`, `flujo` y `entorno` son etiquetas
de Loki; `request_id` y `usuario_id` **no**. Loki crea un flujo por
combinación de etiquetas, y esos dos tienen tantos valores distintos como
requests: ponerlos en el índice lo haría explotar. Quedan en el cuerpo y se
filtran con LogQL, con el enlace ya provisionado en Grafana para la consulta
que uno hace siempre — todas las líneas de un request del que un usuario se
quejó.

Todo vive en `docker-compose.observabilidad.yml`, **aparte del ERP**: si el
stack se cae, el restaurante sigue vendiendo. Guía operativa en
`docs/engineering/observabilidad.md`.

**Sigue pendiente el monitor externo** (ADR-007): es lo único que no se puede
resolver dentro del VPS, porque un monitor que corre en la misma máquina no
avisa cuando la máquina se cae.
