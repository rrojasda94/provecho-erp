# Deuda técnica — Observabilidad y salud (tras las implementaciones de 2026-07-26)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-08-04 **GlitchTip autoalojado** (decisión del usuario sobre las
  dos que ADR-006 dejaba abiertas). Pesa que los datos no salgan del VPS: un
  reporte de error lleva rutas, parámetros y trazas, y aunque
  `_limpiar_evento` redacta PIN/tokens/cabeceras antes de enviar nada, lo
  que nunca sale de la máquina no hay que confiar en que esté bien
  redactado. Costo aceptado: un Postgres, un Redis y dos procesos más en el
  mismo VPS. Stack en `docker-compose.observabilidad.yml`, guía en
  `docs/engineering/observabilidad.md`.
  **Pendiente del usuario**: crear el proyecto en GlitchTip y pegar su DSN
  en `SENTRY_DSN` — sin ese paso el código sigue sin reportar nada.
- ✅ 2026-08-04 **Colector de logs: Loki + Alloy + Grafana** (decisión del
  usuario). El ERP ya emitía una línea de JSON por evento; lo que faltaba
  era que no muriera en `docker logs`. Alloy descubre los contenedores por
  el socket de Docker (montado **solo lectura**) y empuja a Loki; Grafana
  arranca con el datasource provisionado, porque sin él Loki es un agujero
  de solo escritura que nadie va a consultar por `curl` a las 2 a.m.
  `nivel`/`flujo`/`entorno` son etiquetas; `request_id` y `usuario_id`
  **no** —tienen tantos valores como requests y harían explotar el índice—
  y se filtran con LogQL, con el enlace ya armado en Grafana.
- ⬜ **Contratar el monitor externo** (ver *Cuando haya servidor*,
  punto 3) y darle de alta las tres sondas
  (`/health` 1 min, `/health/ready` 5 min, `/health/backups` 1 h). Sin
  monitor, los endpoints no alertan a nadie: el ERP expone, el monitor avisa
  (ADR-007). **Es lo único que no se puede resolver dentro del VPS**: un
  monitor que corre en la misma máquina no avisa cuando la máquina se cae.
- ⬜ **Métricas siguen faltando**: Loki guarda logs, no series temporales.
  Prometheus + node-exporter serían dos contenedores más; se difiere hasta
  que haya tráfico que justifique mirarlas.
- ⬜ **Métricas** (CPU, memoria, latencia, disponibilidad) y **trazas de
  rendimiento**: `SENTRY_TRACES_SAMPLE_RATE` está en 0. Subirlo cuando haya
  tráfico real que valga la pena perfilar.
- ✅ 2026-07-26 **Health check profundo**: `/health/ready` comprueba base de
  datos, Redis y profundidad de la cola; `/health/backups` comprueba
  frescura. Liveness quedó separado y sin dependencias a propósito.
- ✅ 2026-08-04 **Salud del worker**: ahora se pregunta, no se infiere.
  Una tarea de beat (`core.latido_worker`, cada minuto) escribe una clave en
  Redis con TTL de 3 min, y `/health/ready` la lee. Motivo del cambio: la
  cola solo delata al worker **cuando hay trabajo** — con cola vacía, un
  worker muerto y uno ocioso se ven idénticos, y en un restaurante la cola
  está vacía la mayor parte del día, justo cuando conviene enterarse
  temprano. Se usa TTL en vez de comparar timestamps para que la clave
  desaparezca sola y nadie tenga que decidir "cuán viejo es demasiado
  viejo". Degrada sin sacar de rotación: sin worker la caja sigue vendiendo,
  lo que se posterga es el comprobante y la alerta de cocina.
- ✅ **Handler de listener que revienta** — **la entrada estaba obsoleta**
  (verificado 2026-08-04): `EventBus._despachar` ya envuelve cada handler en
  `try/except` y registra con `log.exception`, así que un listener roto no
  arrastra al publicador ni impide que corran los demás. Se agregó el test
  que faltaba para congelarlo
  (`test_un_listener_que_revienta_no_arrastra_al_publicador`).
- ✅ 2026-08-04 **Flujo `auditoria` con contenido**: cada registro de
  auditoría emite además al logger `provecho.auditoria` (desde 2026-08-08
  lo hace `src.shared.auditoria.registrar`, antes `AuditLogRepo`). No es duplicar por gusto: la
  tabla es el rastro legal (consultable, con su retención) y el log es lo
  que un colector externo puede vigilar en vivo — si alguien borrara la
  fila, la línea ya salió del proceso. **Solo metadatos**: `datos_antes`/
  `datos_despues` pueden traer PII (Ley 29733) y ese detalle se queda en la
  tabla.
