# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added

- **Cumplimiento de pedido — PROC-OPE-002 v1.0** (2026-07-27): cierra el
  pendiente de decisión abierto el 2026-07-14 (qué pasa después de Venta).
  Es **un** proceso del área Operaciones con Preparación y Despacho/Entrega
  como etapas internas, **no** dos procesos: hay un solo resultado y ningún
  artefacto de traspaso entre cocina y despacho; la máquina de estados ya
  implementada (`venta_item.estado_preparacion`) es una sola y las
  pantallas KDS `preparacion`/`despacho` son vistas de ella; y "Producción"
  ya nombra la cocina de producción central (`PROC-PRD-001`), por lo que
  reusar `PRD` para la cocina de sucursal rompía la nomenclatura.
  Especificación completa: registro maestro en `process-nomenclature.md`,
  proceso en `workflows.md`, `CU-OPE-001/002/003` por modalidad en
  `use-cases.md`, **RN-CUP-001..012** en `business-rules.md`, máquina
  oficial en `state-machines.md`, entidad `entrega` en `data-model.md`.
  **Código**: `sales/application/cumplimiento.py::registrar_entrega` +
  `POST /api/v1/sales/ventas/{id}/entrega` (permiso propio
  `sales.entregar_pedido`, rol nuevo `despachador`) — exige todos los ítems
  en `listo` (RN-CUP-005), idempotente, publica `sales.venta_entregada`.
  Eventos nuevos en el catálogo: `sales.venta_entregada` y
  `marketing.encuesta_enviada`; de paso se regulariza `sales.pedido_listo`,
  que el KDS publicaba desde 2026-07-25 sin fila en `events.md`. Sin
  migración: el enum ya tenía `entregado`. `tests/test_kds.py` +5 casos.

- **Dashboard gerencial mínimo + slice de caja (PROC-CTB-001/002)**
  (2026-07-26): ADR-012. `GET /api/v1/dashboard/resumen`
  (`src/core/dashboard_router.py`, permiso `dashboard.leer`): ventas del
  día (cantidad+total), stock bajo mínimo, cajas abiertas — vive en `core`
  y no en un módulo de negocio porque compone lecturas de `sales`,
  `inventory` y `accounting` sin importar el dominio de ninguno directo
  (mismo patrón que `sales.queries_publicas.listar_clientes_para_analisis`,
  extendido con `resumen_ventas_del_dia` y `puntos_venta_de_empresa`;
  `inventory.contar_bajo_minimo` nuevo). Construir esto expuso dos huecos
  reales: `sales` no tenía ningún endpoint de listado de ventas, y
  `accounting` tenía los modelos de caja (`apertura_caja`/`cierre_caja`/
  `arqueo`, migrados desde 2026-07-20) sin ninguna capa de aplicación —
  PROC-CTB-001/002 nunca se había construido. **Slice mínimo, no el
  proceso completo**: `accounting.application.caja` abre, cierra y arquea
  con **reconciliación real** — el cierre calcula
  `monto_esperado = monto_apertura + efectivo cobrado desde la apertura`
  (vía el contrato público de `sales`, `total_efectivo_cobrado` — primera
  vez que un módulo consulta a otro en tiempo real para una escritura
  propia, no solo para un reporte) y lo compara contra el conteo físico;
  sin esa cuenta, un cierre sería un formulario sin ningún valor de
  control. Deliberadamente fuera de esta fase: verificación de series de
  POS y denominaciones (RN-POS-009..013), relevo autenticado por PIN propio,
  `custodia_efectivo` como máquina de estados — ese es un slice de negocio
  del tamaño de los ya construidos para `sales`/`purchases`/`production`,
  no algo para colar bajo "hacer un dashboard". Permisos nuevos:
  `dashboard.leer`, `accounting.caja_operar` (rol `cajero` — abre/cierra su
  propia caja sin permisos de administración), `accounting.arqueo_registrar`
  (`supervisor`/`contador`). **Primer frontend real**: login por PIN +
  pantalla de dashboard en Next.js/React, reemplazando el scaffold por
  defecto. `tests/test_dashboard_caja.py` (16 casos) — incluye un caso de
  flakiness real detectado y corregido: SQLite guarda `created_at` sin
  microsegundos pero SQLAlchemy los agrega al enlazar un `datetime` de
  Python, así que dos eventos en el mismo segundo de reloj comparan mal
  como texto (`"...25" < "...25.000000"`); Postgres (columna timestamp
  real) no tiene este problema — se documentó y se resolvió a nivel de
  prueba, no tocando la lógica de producción.

- **Protección de datos personales — derechos ARCO (Ley 29733)**
  (2026-07-26): ADR-011, migración `dad43729501d`. `docs/security/proteccion-datos-personales.md`
  nuevo: qué datos personales trata el ERP y dónde viven (`persona` es la
  fuente única — RN-GEN-007, casi todo ARCO se resuelve tocando una sola
  entidad), derechos ARCO y su estado (Acceso/Rectificación ya existían;
  Oposición queda como política sin contraparte técnica porque no hay
  marketing automatizado todavía), plazos de conservación por tipo de dato,
  medidas de seguridad ya vigentes (referenciadas a `security.md`/ADR-006/
  ADR-007, no reconstruidas), proceso de brecha de seguridad, y una lista
  separada de pendientes que son **acción del usuario, no de código**
  (registro ante la ANPD, aviso de privacidad público, designación de
  responsable, plazos de retención confirmados con contador/abogado).
  **Cancelación implementada como anonimización irreversible**, no `DELETE`:
  `persona` la referencian `trabajador`/`cliente`/`usuario`, un borrado
  físico rompería esas FK o dejaría planillas/comprobantes sin sustento
  legal (retención tributaria/laboral que prevalece mientras esté vigente).
  `POST /api/v1/personas/{id}/anonimizar` (permiso dedicado
  `personas.anonimizar`, distinto de `users.gestionar` — una acción
  irreversible no hereda un permiso de CRUD normal) sobrescribe
  `nombres`/`apellidos`/`numero_documento`/`fecha_nacimiento`/`domicilio`/
  `telefono`/`email` (RN-PER-007); `numero_documento` es `UNIQUE`, se
  reemplaza por un valor derivado del propio `id`, no un texto fijo. El
  `audit_log` de la acción registra qué campos se anonimizaron y el motivo,
  **nunca el valor real anterior** — guardarlo ahí habría dejado la PII
  accesible para siempre, vaciando de sentido la anonimización.
  `PATCH /personas/{id}` sobre una persona ya anonimizada ahora da 409: no
  hay dato real que rectificar. Sin bloqueo automático cross-módulo (p. ej.
  contra `trabajador.estado=activo`) a propósito — `users` es el módulo más
  foundational del ERP y consultar hacia `rrhh` invertiría la dirección de
  dependencia que todo el código ya asume; se documenta un checklist manual
  en su lugar. `docs/domain/business-rules.md` (RN-PER-007),
  `docs/architecture/data-model.md` y `docs/foundation/glossary.md`
  (Derechos ARCO, Anonimización) actualizados. `tests/test_users_persona.py`
  +5 casos.

- **Contrato OpenAPI exportado y verificado en CI** (2026-07-26): ADR-010.
  `src/core/openapi_export.py` (`python -m src.core.openapi_export`) escribe
  `docs/architecture/openapi.json` desde la app real — determinista (claves
  ordenadas, salto de línea final) para que el diff entre corridas refleje
  solo cambios reales del contrato. `ci.yml` lo regenera y compara contra el
  commiteado: un endpoint que cambió sin actualizar el contrato falla el PR
  que lo causó, no cuando Android/PC/una integración se entera por las
  malas. `TAGS_METADATA` nuevo en `src/core/app.py` describe los 13 tags de
  la API (antes FastAPI solo agrupaba por nombre); un test falla si aparece
  un tag sin su entrada. `app.version` ahora usa `settings.app_version` en
  vez de un `"0.1.0"` hardcodeado aparte (duplicación encontrada de paso).
  **Dos afirmaciones falsas corregidas en `api-guidelines.md`**, detectadas
  al auditar la doc contra el código real: `idempotency_key` siempre viajó
  como **campo del body**, la guía decía "header"; ningún endpoint de
  listado pagina, la guía prometía `{items, total, page, page_size}` — se
  documentó el formato real (array plano) y la paginación real queda en
  deuda técnica en vez de fingirse implementada. `tests/test_openapi_export.py`
  (7 casos).

- **Modo offline del PDV — diseño y plumbing base (fase 1)** (2026-07-26):
  ADR-009. Arquitectura de **hub local dedicado por sucursal** (mini-PC/
  Raspberry Pi, siempre encendido): corre la **misma imagen** del backend
  contra su **propio Postgres local** — no una versión recortada. Los tres
  clientes de PDV (web, Android, PC) le hablan siempre al hub por LAN,
  nunca directo a internet, resolviendo el requisito de "equipos en la
  misma red local se ven entre sí durante un corte". Alcance offline:
  catálogo, ventas/cobro/KDS y —por necesidad lógica, no solo lo pedido—
  RBAC/usuarios (sin eso nadie se autentica en el hub) e inventory/stock (el
  listener `sales.venta_confirmada` ya corre en el mismo proceso). El sync
  hub↔nube **reusa la propia API REST** existente en vez de inventar un
  protocolo de replicación: descendente por `updated_at` (ya presente vía
  `TimestampMixin`), ascendente reintentando las mismas llamadas idempotentes
  que el hub ya ejecutó offline (`idempotency_key` ya exigida en ventas/
  pagos). Comprobantes se crean `pendiente` en el hub pero **la emisión a
  Factiliza ocurre solo en la nube**, tras sincronizar — el hub no necesita
  Celery/Redis/worker. `src/core/sync/estado_conexion.py`: detector de
  conectividad con racha de fallos antes de declarar `offline` (un timeout
  puntual no basta) y recuperación inmediata al primer éxito;
  `GET /health/sync` — siempre 200 (a diferencia de `/health/ready`, estar
  offline es el modo de diseño del hub, no un fallo: sacarlo de rotación por
  eso sería contraproducente). `DEPLOYMENT_MODE=hub` con validación de
  config que aborta el arranque si falta algo (sucursal, URL de sync,
  credenciales de la cuenta de servicio). `docker-compose.hub.yml` +
  `.env.hub.example` nuevos. **Fase 2 (motor de sync real) queda
  explícitamente pendiente**: requiere primero extender `crear_venta`/
  `registrar_pago`/movimientos para aceptar un `id` client-generado (ya
  posible sin migración — `UuidPkMixin` genera el UUID en Python, no en la
  base), evitando así una tabla de mapeo hub-id↔nube-id. Fix de paso en
  `.gitignore`: `.env.hub.example` quedaba tapado por la regla `.env.*`, el
  mismo tipo de trampa que `backups/` en el commit anterior.
  `tests/test_offline_hub.py` (17 casos).

- **Entrega continua — imagen en GHCR y CI endurecida** (2026-07-26):
  `ci.yml` gana tres verificaciones que no existían. **Cabeza única de
  Alembic**: dos ramas que crean migraciones en paralelo hacían fallar
  `upgrade head` durante el despliegue, no en el merge que lo causó.
  **Job `imagen`**: nadie comprobaba que el `Dockerfile` siquiera
  construyera — ahora además se levanta el contenedor y se le pide `/health`,
  lo que valida el `CMD`, el usuario sin privilegios y el `HEALTHCHECK`.
  **`pip-audit`** informativo (no bloquea: un aviso en una dependencia
  transitiva no puede frenar un arreglo urgente en caja). Se suman caché de
  pip/npm y `npm ci` en vez de `npm install`. `release.yml` nuevo: cada push
  a `main` publica la imagen en **GHCR**, y los tags `v*` publican además la
  versión exacta — GHCR y no Docker Hub porque autentica con el
  `GITHUB_TOKEN` del propio workflow, sin secreto que rotar.
  **`docker-compose.prod.yml` nuevo**: el `docker-compose.yml` existente es
  solo de desarrollo (monta el código, `uvicorn --reload`, Postgres con
  contraseña de juguete) y desplegarlo habría publicado esa configuración; el
  de producción no incluye base de datos (gestionada vía `DATABASE_URL`),
  publica la API solo en `127.0.0.1` y no expone el puerto de Redis. El
  `Dockerfile` pasa a correr como usuario sin privilegios (uid 10001) y trae
  `HEALTHCHECK`. **El despliegue sigue siendo manual y documentado**
  (ADR-008): automatizar por SSH contra un servidor que todavía no existe
  daría automatización imposible de probar. `alembic upgrade head` queda como
  paso explícito del despliegue y no al arrancar la aplicación — con varias
  réplicas todas migrarían a la vez y una migración fallida dejaría el
  contenedor en bucle de reinicio en lugar de fallar con un error legible.

- **Chequeos de salud y alertas** (2026-07-26): `src/core/health.py` +
  `health_router.py`. `/health` queda como **liveness** puro, sin tocar
  dependencias — si fallara por la base de datos, el orquestador reiniciaría
  en bucle un proceso sano. `/health/ready` es **readiness**: base de datos
  (crítica → `caido` + 503), Redis y profundidad de la cola de tareas
  (degradan a 200 con estado `degradado`, porque sin Redis el rate limit
  falla abierto y los comprobantes esperan, pero la caja tiene que seguir
  vendiendo). `/health/backups` va aparte a propósito: que falte un backup es
  grave, pero devolver 503 en readiness sacaría la API de rotación y dejaría
  al restaurante sin vender. Ese endpoint cubre el caso que el reporte de
  errores **no puede** cubrir — un backup que falla avisa por Sentry, pero
  uno que nunca corrió (cron desactivado, servidor reinstalado) no genera
  ningún evento; solo se detecta preguntando por la frescura del archivo
  (umbral 26 h, con margen sobre el cron diario). **El ERP no alerta por su
  cuenta**: expone estado y un monitor externo avisa (ADR-007) — alertas que
  viven en el servidor monitoreado dejan de avisar justo cuando ese servidor
  cae. Los tres endpoints son públicos (un monitor no puede autenticarse) y
  devuelven estados, nunca hostnames, DSN ni errores crudos. Los endpoints se
  extrajeron a su propio router: `create_app` había superado el umbral de
  complejidad de ruff. `tests/test_health.py` (20 casos).

- **Observabilidad — logs estructurados y reporte de errores** (2026-07-26):
  `src/core/logging_config.py` y `src/core/sentry.py`. Los logs salen en JSON
  (una línea por evento) en producción y en texto legible en local, con los
  **tres flujos** que `security.md` ya declaraba —`app`, `seguridad`,
  `auditoria`— derivados del nombre del logger, sin parámetro extra en cada
  llamada. **Correlación por `request_id`**: se genera por request (o se
  respeta el `X-Request-ID` entrante, para seguir una traza que venía del
  proxy), viaja en un `contextvar`, sale en la cabecera de toda respuesta y
  se devuelve en el cuerpo del error 500 — sin él, un "me dio error" de un
  cajero no se cruza con ningún log. **Redacción** de PIN, contraseñas,
  tokens y cabeceras `Authorization`/`Cookie` antes de escribir el log y
  antes de salir hacia Sentry (`send_default_pii=False`, Ley 29733). El
  flujo `seguridad` estrena usuarios reales: login fallido, bloqueo de
  cuenta, reuso de refresh token y rate limit superado. Reporte de errores
  activo en los tres componentes que hasta ahora fallaban en silencio —
  `api`, `worker` (señal `celeryd_init`: un comprobante que agotaba
  reintentos contra Factiliza no avisaba a nadie) y `backups` (un fallo de
  madrugada quedaba solo en el log del cron). Sirve igual para Sentry o
  GlitchTip autoalojado; sin `SENTRY_DSN` no se envía un solo byte.
  `sentry-sdk` va en dependencias base a propósito: como extra opcional, un
  despliegue que lo olvidara se quedaría justo sin lo que avisa que algo
  falla. `configurar_logging` etiqueta su handler y retira solo el propio,
  para no desconectar a un colector externo (ni a pytest).
  `tests/test_observabilidad.py` (33 casos).

- **Backups automáticos con restauración probada** (2026-07-26):
  `src/backups/backup.py` (`python -m src.backups.backup`) encadena dump →
  verificación → restauración de prueba → copia externa → purga, y sale con
  código 1 si algo falla para que el cron pueda alertar. `pg_dump
  --format=custom` con la contraseña por `PGPASSWORD` (nunca en `argv`, que
  `ps` expone). La verificación comprueba la firma del dump y que
  `pg_restore --list` traiga las tablas críticas — detecta el dump truncado
  por disco lleno, que a simple vista parece sano. Con
  `BACKUP_VERIFY_DATABASE_URL` restaura de verdad contra una base desechable
  y cuenta filas; se niega a restaurar sobre la base de origen, porque
  `pg_restore --clean` borra el esquema destino. La purga por retención
  **nunca borra el backup más reciente**, aunque esté vencido: si el cron
  llevaba meses caído, borrarlo dejaría al ERP sin ninguna copia. Copia a S3
  (o compatible) detrás de credenciales, con `boto3` como dependencia
  opcional `[backups]` para no cargarla en la imagen de la API. **Frecuencia
  revisada de mensual+incremental a diaria con retención de 30 días**
  (`glossary.md`, `security.md`): un negocio que vende todos los días no
  puede perder un mes de caja, y el dump completo pesa megas. Runbook de
  restauración y línea de cron en `docs/engineering/devops.md`.
  `tests/test_backups.py` (17 casos). Verificación pendiente: el camino feliz real (pg_dump contra Postgres) no se pudo ejecutar en la máquina de desarrollo — falta `postgresql-client`.

- **Facturación electrónica — Factiliza (SUNAT)** (2026-07-26): migración
  `b3d7f21ac094`. **Cambio de proveedor: Factiliza reemplaza a Nubefact**
  (decisión del usuario); las columnas `comprobante.estado_nubefact`/
  `respuesta_nubefact` se sustituyen por `estado_emision`
  (`no_aplica|pendiente|aceptado|rechazado|error`), `hash_proveedor`,
  `detalle_emision`, `intentos_emision` y `respuesta_proveedor`. Adaptador
  nuevo en `src/shared/integrations/factiliza/`: `client.py` (`POST
  /invoice/send`, Bearer) y `mapper.py` (traducción a catálogos SUNAT 01/
  06/07/51/52 + leyenda 1000 en letras vía `num2words`). Cola nueva:
  `src/core/celery_app.py` + tarea `sales.emitir_comprobante` con reintento
  exponencial, y servicio `worker` en `docker-compose.yml`.
  `sales.registrar_pago` crea el `comprobante` `pendiente` al cubrirse el
  total y el router encola el envío **después del commit**; aceptado →
  venta `facturada` + `sales.comprobante_emitido`; rechazo de SUNAT se
  guarda como veredicto sin reintentar; fallo de transporte reintenta.
  Boleta vs factura por `rules.tipo_comprobante` (factura solo con cliente
  jurídico + RUC; anónimo → `CLIENTES VARIOS`). **IGV desglosado hacia
  atrás** desde el precio de carta, y **exoneración automática** para
  empresas de zona `amazonia_ley27037` (RN-IMP-001 — el caso real de
  Majambo en Tarapoto). Sin `FACTILIZA_TOKEN` la emisión queda desactivada
  y los comprobantes se acumulan pendientes: la caja nunca se bloquea
  (RN-COM-003). Permiso `sales.emitir_comprobante` + endpoints
  `GET /ventas/{id}/comprobante` y `POST /comprobantes/{id}/reintentar`.
  Dependencias nuevas: `httpx` (pasa de dev a runtime), `num2words`.
  `tests/test_facturacion_electronica.py` (23 casos).

- **Endurecimiento de producción — rate limit, secretos y HTTPS**
  (2026-07-26): `src/core/rate_limit.py` nuevo — límite por IP con contador
  en Redis (ventana fija), aplicado a `/auth/login` y `/auth/refresh`
  (10/min configurable); el lockout por cuenta no frenaba a quien rota
  usernames desde una misma IP. Fail-open si Redis no responde: una caída de
  Redis no puede dejar sin operar al restaurante. `settings` valida la
  configuración al arrancar y **aborta** con `ENVIRONMENT=production` si
  `JWT_SECRET` es el placeholder o mide menos de 32 caracteres, si
  `DEBUG=true`, si `DATABASE_URL` conserva la contraseña por defecto o si
  `ALLOWED_HOSTS`/`CORS_ORIGINS` quedaron en `*`. `create_app` suma
  `TrustedHostMiddleware`, CORS con orígenes explícitos (antes no había CORS:
  el frontend no podía llamar a la API), cabeceras `X-Content-Type-Options`/
  `X-Frame-Options`/`Referrer-Policy` en toda respuesta, `HSTS` solo en
  producción, y `/docs` + `/openapi.json` deshabilitados en producción.
  Dockerfile arranca uvicorn con `--proxy-headers` (detrás de nginx la IP
  real llega en `X-Forwarded-For`; sin esto el rate limit y el `audit_log`
  registraban la IP del proxy). `docker-compose.yml` toma la contraseña de
  Postgres de `POSTGRES_PASSWORD`. Runbook de rotación de credenciales y
  custodia de `.env`, y guía de despliegue tras nginx/Caddy, en
  `docs/engineering/devops.md`; `docs/security/security.md` actualizado.
  `tests/test_security.py` (13 casos).

- **`rrhh`: slice completo — ciclo laboral** (2026-07-25): migración
  `9e1b6a4c7d23`, 12 tablas nuevas sobre `trabajador` (que solo tenía modelo,
  sin capa de aplicación). `application/trabajadores.py` completa el ciclo
  crear/actualizar/cesar (RN-PER-002: `locacion_servicios` fuerza
  `registra_asistencia=false`). `contratos.py`: `contrato_laboral`
  borrador→firmado→finalizado (RN-RRHH-012). `postulantes.py`: exige
  `consentimiento_datos` antes de guardar CV (RN-PER-004). `socios.py`:
  participación societaria. `nomina.py`: `boleta_pago`/`liquidacion_bss`
  idempotentes por `idempotency_key` (RN-RRHH-001/003, flag
  `dentro_de_plazo` de 48h). `disciplina.py`: `memorandum`/`amonestacion`/
  `acta`/`certificado_trabajo` (RN-RRHH-002/004/007). `permisos.py`:
  `solicitud_permiso` pendiente→aprobada/rechazada (RN-RRHH-005).
  `capacitacion.py`: `pacto_permanencia` con reembolso proporcional al
  tiempo no cumplido (RN-RRHH-006). `asistencia.py`: marcar entrada/salida,
  bloqueado para trabajadores que no registran asistencia. 11 permisos
  `rrhh.*` nuevos, rol `rrhh_admin`, `supervisor` gana lectura/aprobación de
  permisos y marcado de asistencia. Constante `rrhh_rmv_vigente` en
  settings (RN-PER-001). Endpoints bajo `/api/v1/rrhh`. `tests/test_rrhh.py`
  (17 casos). Diferido: ver ROADMAP — eventos `rrhh.*` sin consumidor
  todavía, `contrato`/`solicitud` transversales, cálculo automático de
  PLAME.

- **Pago a proveedor (PROC-CTB-003) — tesorería en `accounting`** (2026-07-25):
  migración `cbf904a9fc1b` (`movimiento_dinero`). `feat(purchases)`: nuevo
  `application/comprobantes.py::dar_conformidad_comprobante` (permiso
  `purchases.dar_conformidad`) registra el `comprobante` recibido
  (transversal, `shared`), lo liga a la última `recepcion_compra` de la OC
  y publica `purchases.comprobante_conforme` (empresa_id, condición de
  pago, `sujeto_spot`/`porcentaje_deteccion`, monto). `feat(accounting)`:
  `application/pagos.py` — `registrar_pago` encola un `movimiento_dinero`
  `pendiente` (idempotente por `comprobante_id`, RN-CTB-008), `ejecutar_pago`
  exige permiso `accounting.pago_gestionar` y revisa el umbral configurable
  (`regla_aprobacion`, código `pago_umbral`, RN-CTB-005 — sobre el umbral
  exige además `accounting.pago_aprobar`) antes de generar el asiento vía
  `regla_asiento` (evento `accounting.pago_ejecutado`; sin mapeo
  configurado, el pago igual se ejecuta y el asiento se omite),
  `rechazar_pago` cierra la cola sin ejecutar. Nuevo helper compartido
  `asientos.crear_asiento_automatico_si_hay_regla` (usado también por
  `application/listeners.py`, dedup de la búsqueda de `regla_asiento`).
  Endpoints `/api/v1/accounting/pagos-proveedor` (registrar, listar,
  ejecutar, rechazar) y `/api/v1/purchases/ordenes-compra/{id}/conformidad-comprobante`.
  Roles: `comprador` gana `purchases.dar_conformidad`; `contador` gana
  `accounting.pago_gestionar`; `supervisor` gana `accounting.pago_aprobar`.
  Tests en `tests/test_accounting.py`. Deuda: detracción SPOT se calcula
  pero el asiento no la desglosa en cuenta propia; `purchases` no marca la
  OC como pagada; `rechazar_pago` no libera el comprobante para reintentar
  — ver ROADMAP.
- **Módulo `accounting` — slice core (libro contable)** (2026-07-25): migración
  `5402d99333fa` (`cuenta_contable`, `periodo_contable`, `asiento`,
  `asiento_linea`, `regla_asiento`) aplicada. Endpoints `/api/v1/accounting`:
  plan de cuentas (permiso `accounting.cuenta_administrar`), abrir/cerrar
  periodo contable (`accounting.periodo_administrar`, RN-CTB-010), asiento
  manual con cuadre obligatorio debe=haber (`accounting.asiento_manual`,
  RN-CTB-001) y anulación por asiento inverso — nunca borra/edita
  (RN-CTB-002). `regla_asiento` (nuevo): mapeo configurable evento→cuentas
  por empresa, mismo criterio que `regla_aprobacion` (RN-CTB-011: sin regla
  configurada, el asiento automático se omite y loguea, nunca bloquea el
  proceso de origen). **Listener** (`application/listeners.py`) genera
  asiento automático para los 3 eventos que sus módulos de origen ya
  publican en código: `purchases.oc_emitida`, `purchases.compra_recibida`,
  `sales.venta_confirmada` — se agregó `empresa_id` al payload de
  `oc_emitida` y `total` al de `venta_confirmada` (campos aditivos,
  `events.md` actualizado). Rol semilla `contador`. Tests en
  `tests/test_accounting.py`. Deuda registrada en ROADMAP (resto de eventos
  aún no publicados por sus módulos, pago a proveedor, conciliación
  bancaria, arqueo backend, ciclo de caja sin conectar al libro contable,
  activo fijo/ITAN).
- **Persona CRUD + lock optimista + matriz de aprobaciones + contrato
  público de lectura** (2026-07-25): migración `af8a246e2c25`.
  - `feat(users)`: CRUD de `persona` sin Delete (`POST/GET/PATCH
    /api/v1/personas`, permiso `users.gestionar`) — antes solo se creaba
    de rebote vía trabajador/cliente/proveedor. `PATCH` exige `version`
    vigente (lock optimista, `VersionedMixin` nuevo en
    `src/core/model_base.py`): dos ediciones concurrentes ya no se pisan
    en silencio, la segunda recibe 409.
  - `feat(shared)`: `regla_aprobacion` (nuevo, `src/shared/`) — la matriz
    de aprobaciones deja de ser solo un documento con `[[COMPLETAR]]`;
    umbral de OC de `purchases` migrado a leerla (con fallback al valor
    semilla de config si la empresa no configuró ninguna fila). Admin en
    `/api/v1/reglas-aprobacion`, permiso
    `gerencia.gestionar_reglas_aprobacion`.
  - `feat(sales)`: primer contrato público de lectura cross-módulo del
    repo (`application/queries_publicas.py`) — `GET /api/v1/sales/clientes`
    expone `cliente` (join con `persona` si es natural) para que
    `marketing`/`comercial` lo consuman sin importar el dominio de
    `sales`, permiso `sales.leer_clientes_externos`. Patrón documentado en
    `docs/architecture/events.md` para replicar cuando `inventory`
    implemente `solicitud_insumos` (caso `purchases` ↔ `inventory`, hoy
    bloqueado).
  - Tests: `tests/test_users_persona.py` (CRUD + lock optimista),
    `tests/test_sales_clientes_publico.py`, nuevo caso en
    `tests/test_purchases.py` (override de umbral por empresa).
- **Módulo `production` — slice core** (2026-07-25): migración
  `f78501175fba` (orden_produccion, consumo_produccion_item,
  receta.articulo_id) aplicada. Construido antes de tiempo (primera
  cocina real planeada 2027) a pedido explícito del usuario, mismo
  patrón slice-por-slice. `receta.articulo_id` nuevo (nullable) liga una
  receta a la subreceta que produce — separado del uso existente de
  `producto_comercial.receta_id`. Endpoints
  `/api/v1/production`: crear orden ad-hoc (sin plan/cronograma),
  registrar consumo real de insumos, completar con resultado de control
  de calidad (`conforme`/`no_conforme_reprocesado`/`no_conforme_desechado`)
  y costeo automático (`costo_insumos` + `costo_mano_obra` vía tarifa
  configurable `production_costo_hora_mano_obra` → `costo_real_unitario`).
  Desecho exige merma + motivo + evidencia (RN-PRD-015). **Listeners en
  inventory**: `consumo_registrado` descuenta insumos,
  `orden_completada` suma el producto terminado y recalcula su
  `costo_promedio` (mismo patrón que `purchases.compra_recibida`). Rol
  semilla `jefe_cocina`. Sin migración generada aún. Tests en
  `tests/test_production.py`. Deuda registrada en ROADMAP (cronograma,
  checklist de inocuidad, reporte consolidado, reporte de escalamiento
  real, merma→accounting, lote/trazabilidad, subrecetas anidadas).
- **Módulo `purchases` — slice core** (2026-07-25): migración `4ff85f833b29`
  (proveedor, orden_compra, orden_compra_item, recepcion_compra,
  recepcion_item) aplicada a la BD dev (Supabase). Endpoints
  `/api/v1/purchases`: CRUD de proveedores (natural liga a `persona`,
  mismo party model que `cliente`, RN-GEN-007; jurídico con razón
  social/RUC propios), ciclo de OC tipo `insumo` (crear borrador →
  emitir → recibir total/parcial → anular), todo con idempotencia.
  Emitir exige `purchases.aprobar` si el total supera el umbral
  configurable `purchases_umbral_aprobacion_oc` (semilla: 2000). Eventos
  `purchases.oc_emitida` / `compra_recibida` / `oc_anulada`. **Listener
  en inventory**: `compra_recibida` suma stock en el almacén destino y
  recalcula `articulo.costo_promedio` (promedio ponderado). Rol semilla
  `comprador`. Tests en `tests/test_purchases.py`. Deuda registrada en
  ROADMAP (cotización, OC tipo `activo` + `requerimiento_activo`,
  compra_directa + caja chica, evaluación de proveedor automática,
  comprobante recibido, devolución a proveedor).
- **Módulo `sales` — KDS** (2026-07-25): migración `7672566bf189` —
  `kds_pantalla` (pantallas por sucursal, tipo preparación/despacho, filtro
  por categorías de producto comercial), `venta_item.estado_preparacion`
  (pendiente → en_preparacion → listo → entregado, sin retroceso; fuente
  única del avance: todas las pantallas muestran el progreso real del
  pedido), `producto_comercial.categoria_id` (ruteo a estaciones),
  `venta.comanda_impresa_veces`, `venta.referencia_atencion` (migración
  `617845c27651` — "Mesa 5"/"Carlos"/"Rappi #1042", texto libre visible en
  tarjetas KDS y comanda sin exigir cliente registrado). Endpoints
  `/api/v1/kds`: CRUD de pantallas,
  cola por pantalla, bump de ítems, avance de pedido y comanda imprimible
  (texto 32 cols para térmica 58 mm, reimpresión marcada). Evento
  `sales.pedido_listo` al completarse todos los ítems. Permisos
  `kds.configurar`/`kds.operar`; rol `cocinero` en el seeder. Fix en el
  listener de inventory: cierre de sesión sin rollback en early-return
  (rompía transacción compartida en tests SQLite). Tests en
  `tests/test_kds.py`. Deuda: tiempo real (WebSocket/Redis), impresión
  física ESC/POS, alertas de demora, estados de entrega según proceso de
  cumplimiento.
- **Módulo `sales` — slice PDV** (2026-07-25): sin migración (esquema del
  slice Venta/Cobro ya existía). Endpoints `/api/v1/sales`: crear venta
  (correlativo `numero_orden` por sucursal+día, idempotencia por
  `idempotency_key`, total server-side), cobro con pagos parciales (suma ==
  total → `pagada`, sin sobrepago), anulación de orden no pagada, CRUD de
  productos comerciales y medios de pago. Eventos `sales.venta_confirmada` /
  `venta_pagada` / `venta_anulada`. **Listener en inventory**: consume insumos
  por receta (+merma % + empaque según modalidad RN-EMP-003) al confirmar y
  repone al anular; nunca bloquea la venta (omisiones se loguean). Kiosk y
  Central de Pedidos definidos como clientes del mismo contrato de venta, no
  módulos. Permisos `sales.anular` y `sales.gestionar_catalogo` en el seeder.
  Tests en `tests/test_sales.py`. Deuda registrada en ROADMAP (precio
  server-side, comprobante, nota de crédito, webhook pasarela, enlace caja,
  subrecetas anidadas).
- **Módulo `inventory` — slice core** (2026-07-25): migración `be914c92a94b`
  con 3 tablas (`stock`, `movimiento_inventario` insert-only, `ajuste`).
  Endpoints `/api/v1/inventory`: CRUD de artículos/categorías/SKUs, consulta de
  stock por almacén con alerta `bajo_minimo`, registro de movimientos (el stock
  nunca se edita directo; salida no deja negativo) y ajuste con segregación de
  funciones (`inventory.solicitar_ajuste` ≠ `inventory.aprobar_ajuste`, y el
  aprobador no puede ser el solicitante; al aprobar genera el movimiento y
  refleja el stock). Evento `inventory.ajuste_fuera_margen`. Permisos nuevos en
  el seeder, asignados a roles `almacenero`/`supervisor`. Reusa el auth/RBAC de
  `users`. Tests en `tests/test_inventory.py`. Diferido: lote/FEFO,
  `reserva_stock`, conteo, transferencias, devolución, guía de remisión,
  listeners de eventos, tenant desde el JWT.
- **Módulo `users` — slice auth + RBAC + CRUD** (2026-07-25): primer código de
  negocio del ERP. Migración `c16d615f6afd` con 7 tablas (`rol`, `permiso`,
  `usuario_rol`, `rol_permiso`, `usuario_sucursal`, `refresh_token`,
  `audit_log`) + columnas de lockout (`intentos_fallidos`, `bloqueado_hasta`)
  en `usuario`, aplicada a la BD dev. Endpoints `POST /api/v1/auth/login`
  (username + PIN 6 dígitos, Argon2id), `/auth/refresh` (rotativo con
  detección de reuso que revoca la cadena), `/auth/logout`, `GET /users/me`, y
  CRUD admin de usuarios/roles/permisos/asignaciones bajo `require_permission`
  (deny por defecto, comodín `*`). Access token JWT (claims: sub, tipo, roles,
  sucursales, empresa_id) 15 min + refresh 7 días. Lockout tras 5 intentos
  fallidos (ventana 15 min). Seeder `src/seeders/seed.py` (idempotente,
  prohibido en prod): org base Majambo + matriz de roles/permisos + `admin`
  (PIN `123456`). Tests en `tests/test_users_auth.py`. Router montado en
  `src/core/app.py`. Pendiente: aplicar restricciones JSONB por permiso.
- **Área Contabilidad** (2026-07-24): `docs/contabilidad/` (política de
  segregación de funciones/supervisión de Gerencia, marco legal tributario PE,
  perfil de contador/tesorero), 3 SOPs nuevos en
  `docs/diagrams/Procesos/Contabilidad/` (Tesorería: pago a proveedor
  PROC-CTB-003, conciliación bancaria PROC-CTB-004; Control: arqueo sorpresa
  PROC-CTB-005), 4 plantillas en `docs/templates/contabilidad/`. Reglas
  RN-CTB-004 a RN-CTB-009 (incluye auditoría interna: Contabilidad audita a las
  áreas operativas aguas arriba pero no a sí misma; su tesorería la audita
  Gerencia — modelo de control en dos niveles). Glosario: Tesorería, Finanzas,
  Flujo de caja, Conciliación bancaria, Arqueo, Auditoría interna, Orden de
  pago, Detracción, Activo No Corriente, Depreciación, Periodo contable.
  Nomenclatura: CAJ/TES/ACT confirmadas bajo Contabilidad. Eventos
  `accounting.pago_ejecutado`, `accounting.pago_requiere_aprobacion`,
  `accounting.arqueo_registrado`. Spec `src/modules/accounting/README.md`
  actualizada (tesorería/finanzas). Propuestos PROC-CTB-006..013 (reposición
  caja chica, flujo de caja, cierre de periodo, depósito, activo fijo, contador
  externo, auditoría de almacén, conciliación de facturas/comprobantes).
- **Área RRHH** (2026-07-19): `docs/rrhh/` (marco legal laboral REMYPE,
  perfiles de puesto), 13 SOPs en
  `docs/diagrams/Procesos/Recursos-Humanos/` (Reclutamiento, Contratación,
  Inducción), 9 plantillas en `docs/templates/rrhh/`. Reglas RN-RRHH-012 a
  RN-RRHH-014; RN-RRHH-005 corregida (15 días de vacaciones REMYPE).
- **Área Compras** (2026-07-19): `docs/compras/` (marco legal-tributario
  Amazonía/SPOT, perfil de encargado), 11 SOPs en
  `docs/diagrams/Procesos/Compras/` (Proveedores, Cotización-OC,
  Recepción-Pago, Caja-Chica, Activos-Equipamiento), 6 plantillas.
  Reglas RN-CMP-008 a RN-CMP-017. Spec `src/modules/purchases/README.md`
  actualizada (3 caminos de compra, caja chica, OC tipo activo, pago lo
  ejecuta accounting).
- **Área Comercial** (2026-07-19): `docs/comercial/` (política de
  precio/margen/promociones/metas, perfil de jefe comercial), 9 SOPs
  nuevos en `docs/diagrams/Procesos/Comercial/` (Estrategia-Mercado,
  Precios-Promociones, Metas-Desempeno), 5 plantillas. Reglas RN-CML-001
  a RN-CML-006; glosario: Margen de Contribución. Spec
  `src/modules/sales/README.md` actualizada (vigencia de promoción,
  margen de contribución, precio por nueva versión).
- **Área Almacén y Logística** (2026-07-19): `docs/almacen-logistica/`
  (política FEFO/FIFO, conteo/ajuste, perfiles de almacén y chofer),
  8 SOPs nuevos en `docs/diagrams/Procesos/Logistica-Almacen/`
  (Conteo-Auditoria, Vencimientos-Mermas, Transporte-Transferencias),
  6 plantillas. Spec `src/modules/inventory/README.md` actualizada
  (lote, merma, ajuste solicitar/aprobar, transferencia lateral).
- **Área Producción** (2026-07-20, spec a futuro — primera cocina de
  producción planeada 2027): `docs/produccion/` (política de cronograma,
  calidad/no conformidad, inocuidad, inventario de cocina, soporte a
  I+D+i; perfiles de jefe de cocina y cocinero), 4 SOPs nuevos en
  `docs/diagrams/Procesos/Produccion/` (Planificacion, Calidad-Inocuidad,
  Inventario-Cocina, Soporte-IDI), 5 plantillas en
  `docs/templates/produccion/`. Reglas RN-PRD-011 a RN-PRD-017; entidad
  `plan_produccion` nueva, `orden_produccion`/`reporte_escalamiento`
  ampliadas. Nuevo módulo `src/modules/production/README.md` (spec
  técnica, sin implementar) y evento
  `production.no_conformidad_detectada`.
- **Producción — costeo, desperdicio e inocuidad** (2026-07-20, mismo
  día): tabla de desperdicio por insumo/tipo/peso en `orden-produccion.md`;
  costeo real automático (insumos + mano de obra, RN-PRD-018); reporte de
  conteo de cocina pasa a autogenerado, el jefe de cocina solo visa;
  verificación de temperatura de equipos de frío con alerta automática a
  Gerencia (RN-CDP-005). Nuevas entidades `consumo_produccion_item` y
  `checklist_inocuidad_turno`; evento `production.equipo_frio_fuera_rango`.
- **Área Gerencia** (2026-07-22, versión ligera — autoridad/estrategia/
  control, sin módulo backend): `docs/gerencia/` (política de gobierno
  corporativo + matriz de aprobaciones como fuente única de umbrales,
  perfil de Gerente General), 2 plantillas en `docs/templates/gerencia/`
  (acta de decisión gerencial, evaluación de nuevo mercado/marca). Reglas
  RN-GER-001 a RN-GER-006; entidad transversal `decision_gerencial`
  (`data-model.md` §8c); glosario: Gerente General, Matriz de
  aprobaciones, Acta de decisión gerencial. Sin PROC ni evento ni módulo
  (la facultad de aprobar es RBAC, no una tabla).
- **Área Marketing** (2026-07-22): `docs/marketing/` (política de uso de
  marca/contenido/campañas, perfil de jefe de Marketing), 6 SOPs en
  `docs/diagrams/Procesos/Marketing/` (Marca-Contenido, Campanas,
  Proveedores-Agencias), 4 plantillas. Reglas RN-MKT-001 a RN-MKT-007;
  entidades `campana`, `pieza_contenido`, `lead`,
  `implementacion_material_sucursal` (`data-model.md` §8d); eventos
  `marketing.campana_lanzada`, `marketing.lead_generado`; PROC-MKT-001
  (Campaña de marketing, Borrador). Módulo `src/modules/marketing/README.md`
  (spec técnica). Glosario: Lead, Campaña, Naming, Jefe de Marketing.
  Frontera: Marketing atrae leads, Comercial cierra.
- **Presupuesto anual (Gerencia)** (2026-07-22): RN-GER-007, PROC-GER-001
  (reunión anual donde cada área presenta propuesta y Gerencia designa
  presupuesto + límite de gasto autónomo), SOP `definicion-presupuesto-anual.md`,
  plantilla `propuesta-presupuesto-anual.md`, fila en la matriz de
  aprobaciones. Ajuste Marketing: RN-MKT-001 (Marketing gestiona las
  marcas sin burocracia extra), RN-MKT-006 (agencias las evalúa Marketing
  y valida Gerencia, no pasan por Compras; el material sí).
- **Reglas de conducta laboral** (2026-07-22): RN-RRHH-015 (uniforme
  completo/limpio/presentable en jornada), RN-RRHH-016 (no contratar
  parientes de 1.er/2.º grado), RN-RRHH-017 (no relaciones sentimentales
  en el mismo centro ni con subordinación directa), RN-RRHH-018 (no usar
  conocimiento ni recursos de la empresa para terceros/beneficio personal).
- ADR-004: aislamiento de tenant por filtro de aplicación con
  `empresa_id` obligatorio + tests (RLS de Postgres como refuerzo futuro).
- Catálogo de eventos completado con los eventos ya declarados en las
  specs de módulos: `inventory.merma_registrada`,
  `inventory.devolucion_a_proveedor`, `inventory.ajuste_fuera_margen`,
  `inventory.lote_vencido_detectado` (nuevo — lote vencido hallado
  disponible notifica y dispara memorándum), `purchases.comprobante_conforme`,
  `purchases.caja_chica_rendida`, `purchases.evaluacion_proveedor_actualizada`,
  `users.sesion_iniciada`, `accounting.asiento_generado`,
  `accounting.periodo_cerrado` (`docs/architecture/events.md`).
- Modelo de datos: entidades `plantilla`, `flota`, `combo`/`combo_item`,
  `stock_lote` (stock por lote — hace implementable FEFO/FIFO),
  `ajuste`, `apertura_caja`, `cierre_caja`, `arqueo`,
  `reporte_escalamiento` (definición mínima, por validar), y bloque de
  Compras (`caja_chica_compras`, `caja_chica_movimiento`,
  `compra_directa`, `rendicion_caja_chica`, `evaluacion_proveedor`,
  `requerimiento_activo`); `articulo.tipo` gana `suministro` (consumo
  interno: limpieza, oficina) y queda declarado como enum extensible.
- Glosario: "Horario laboral" y "Horario de atención" (términos oficiales,
  reemplazan "horario de trabajo").
- Repositorio git inicializado (commit inicial con el estado
  pre-correcciones para trazabilidad).
- Modelado de BD — bloque transversal + organización (11 tablas):
  `persona`, `grupo`, `empresa`, `marca`, `licencia_marca`, `sucursal`,
  `almacen`, `categoria`, `categoria_udm`, `unidad_medida`, `archivo`.
  Modelos SQLAlchemy 2.0 tipados en
  `src/modules/{users,inventory}/infrastructure/models/` y
  `src/shared/models/`; mixins comunes (`UuidPkMixin`, `TimestampMixin`,
  `SoftDeleteMixin`, `JsonB`) en `src/core/model_base.py`; naming
  convention de constraints en `Base.metadata`; registro central
  `src/core/models_registry.py` cableado a Alembic; migración inicial
  Alembic validada contra Postgres 16 (ciclo upgrade/downgrade/upgrade);
  tests de esquema (`tests/test_models.py`).
- Puerto de Postgres en el host movido a **5433** (`docker-compose.yml`,
  `.env.example`) — el 5432 local lo ocupa la plataforma de Charlie's
  Pizzas; dentro de la red de compose sigue siendo `db:5432`.
- **BD de desarrollo movida a Supabase** (Postgres gestionado): la
  migración inicial (`a06c1d0a0913`) se aplicó contra el proyecto
  Supabase del usuario — 11 tablas + `alembic_version` verificadas.
  Motivo: visualización (Table Editor) y disponibilidad en línea de cara
  al despliegue futuro. Explícitamente **no** se activa Supabase
  Auth/RLS — sigue rigiendo `users` (JWT+PIN+Argon2id+RBAC) y el
  aislamiento de tenant por filtro de aplicación (ADR-004). Detalle y
  cómo alternar con el contenedor Docker local:
  `docs/engineering/devops.md`. Connection string solo en `.env`
  (gitignorado), plantilla sin secretos en `.env.example`.
- `reporte_escalamiento` definido con el negocio: cadena atención al
  cliente → supervisor (redacta solución) → comercial/gerencia; se
  almacena para mejora continua (`data-model.md` §6).
- **Slice Venta — núcleo de datos** (11 tablas nuevas, 22 en total):
  `usuario` (mínimo), `trabajador` (nuevo módulo `src/modules/rrhh/`),
  `articulo`/`sku`/`receta`/`receta_item` (base de productos, inventory),
  `cliente`/`punto_venta`/`producto_comercial`/`venta`/`venta_item`
  (nuevo módulo `src/modules/sales/`). Conecta venta con cliente y
  trabajador para habilitar historial de compras del cliente y ranking
  de ventas por trabajador — ambos probados en
  `tests/test_venta_slice.py`. Migración `08c7aa59dd6e` aplicada y
  verificada en Supabase (ciclo upgrade/downgrade/upgrade).
- **`venta.numero_orden`** (RN-COM-014, nueva): correlativo legible por
  sucursal y día (único junto a `sucursal_id`+`fecha_orden`) — lo que ve
  el personal en cocina/mostrador/KDS; distinto de `idempotency_key`
  (técnico) y del correlativo del comprobante (fiscal). Aplica tenga o
  no `cotizacion_id` la venta.
- **`cliente.usuario_id`** opcional (RN-COM-015, nueva): cuenta de
  autoservicio web — nunca requerida para comprar en sucursal o Central
  de Pedidos, esas ventas enrutan al mismo `cliente` sin login.
  Migración `90116965bfa8` aplicada y verificada en Supabase.
- **Slice Cobro y Comprobante (PROC-COM-002) + ciclo de caja
  (PROC-CTB-001/002)** — 8 tablas nuevas (30 en total): `medio_pago`
  (catálogo por empresa, decisión 2026-07-20), `pago` (RN-COM-016 —
  pago dividido confirmado real, suma de montos debe igualar
  `venta.total`), `comprobante` (nuevo módulo transversal en
  `src/shared/models/` — sirve a sales/purchases/accounting, correlativo
  único por empresa+serie, RN-CPP-007), `apertura_caja`,
  `custodia_efectivo`, `cierre_caja`, `arqueo` (nuevo módulo
  `src/modules/accounting/`, ciclo completo de caja). `punto_venta` gana
  `serie_boleta`/`serie_factura` (series SUNAT separadas por punto de
  venta, decisión 2026-07-20) — `comprobante.serie` las copia como
  snapshot inmutable al emitir. 3 tests nuevos
  (`tests/test_cobro_caja_slice.py`): pago dividido, unicidad de
  correlativo, cadena apertura→custodia→cierre. 13/13 tests pasan.
  Migración `8cde35e4f3f2` aplicada y verificada en Supabase (ciclo
  upgrade/downgrade/upgrade).

- Branding Provecho aplicado: paleta, tipografías (Anton Italic + Inter) y
  tokens CSS (`docs/product/ui-ux.md`).
- ADR-003: Izipay como pasarela de pago.
- `PROC-COM-002` Cobro y Emisión de Comprobante de Pago v1.0: narrativa +
  Mermaid en `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Comercial/PROC-COM-002-v1.0.bpmn` (detalle del
  paso "cobro" de `PROC-COM-001`, RN-COM-005).
- `PROC-CTB-002` Apertura de caja v1.0: narrativa + Mermaid en
  `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Contabilidad/PROC-CTB-002-v1.0.bpmn`. Nuevas
  reglas RN-POS-009 a RN-POS-013 y RN-MDP-006.
- `PROC-OPE-001` Apertura de sucursal v1.0: nueva área `OPE` (Operaciones)
  en `process-nomenclature.md`; narrativa + Mermaid en
  `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Operaciones/PROC-OPE-001-v1.0.bpmn` (checklist
  físico de apertura, recepción de pedido, limpieza, apertura de caja
  referenciada). Nuevas reglas RN-SUC-006 a RN-SUC-012, RN-PER-006 y
  RN-RRHH-009 a RN-RRHH-011. Glosario: agrega "Supervisor" (Actores) y
  "Alarma" (Recursos).
- SOPs de limpieza (14) y de lavado de menaje en
  `docs/diagrams/Procesos/Operaciones/Limpieza/`.
- SOPs de procesos comerciales/caja/apertura (9) derivados de los BPMN
  vigentes, en `Comercial/Ventas/`, `Comercial/Cobros/`,
  `Contabilidad/Caja/` y `Operaciones/Apertura-Sucursal/`.
- SOPs de `PROC-INV-001` (3): conteo de insumos y envío de requerimiento,
  picking y despacho en almacén central, recepción y devoluciones en
  local — nueva área `Logistica-Almacen` en
  `docs/diagrams/Procesos/`.

### Changed

- **RN-COM-007 reactivada** (2026-07-27): la encuesta de satisfacción
  vuelve a tener disparador (`sales.venta_entregada`) tras quedar sin él
  desde el recorte de alcance de Venta del 2026-07-14. Desbloquea
  `encuesta_satisfaccion` en el módulo `marketing`.
- **El bump del KDS ya no marca `entregado`** (2026-07-27):
  `POST /kds/items/{id}/avanzar` devuelve 409 apuntando al endpoint de
  entrega. Antes, cualquiera con `kds.operar` cerraba el pedido ítem por
  ítem, lo que dejaba decorativo cualquier permiso de entrega; ahora la
  entrega exige `sales.entregar_pedido` y cierra la venta completa de una
  vez (RN-CUP-005/006). Cambio de contrato para clientes del KDS que
  usaran ese estado.
- **Documentación al día con lo construido** (2026-07-26): tres ADR nuevos
  para decisiones que se habían tomado sin registrar —
  **ADR-005** (Factiliza como proveedor de facturación electrónica; deja
  constancia de que **Nubefact nunca fue un ADR**, era un supuesto heredado
  del scaffold que arrastraron trece archivos), **ADR-006** (logs con la
  biblioteca estándar en vez de `structlog`; Sentry/GlitchTip intercambiables
  por DSN, así que elegir backend no es decisión de arquitectura) y
  **ADR-007** (backups por `pg_dump` + cron y no Celery beat, porque el
  backup debe correr justo cuando la aplicación está caída; salud expuesta a
  un monitor externo). Barrido de las trece menciones obsoletas a Nubefact en
  `data-model.md`, `overview.md`, `tech-stack.md`, `marco-legal-contabilidad.md`,
  `diagrams/modules.md`, `business-rules.md`, `domain-model.md`,
  `state-machines.md`, `workflows.md`, `glossary.md` y `vision.md`.
  `overview.md` documenta ahora la infraestructura de operación de
  `src/core/` (tabla archivo → responsabilidad) y `src/backups/`, más el
  índice completo de ADR; `00_PROJECT.md` y el `README.md` raíz actualizados
  con salud, backups y observabilidad.

### Fixed

- `data-model.md` §6 `venta.estado`: seguía con el enum viejo de 8
  estados; corregido al enum vigente desde 2026-07-14
  (`orden|pagada|facturada|anulada`, RN-COM-005) — `state-machines.md`
  ya lo tenía correcto, quedaron desalineados.
- `data-model.md` §3 `articulo`: le faltaba `empresa_id` directo,
  rompiendo la convención de tenant (ADR-004) porque `categoria_id` es
  opcional.

### Changed

- `PROC-CMP-001` Compras v1.0 → v2.0: tres caminos de compra (informal/
  caja chica, preferente sin cotización comparativa, estándar/activo con
  RFQ) y ejecución del pago trasladada a Contabilidad (Compras solo
  sustenta el comprobante conforme). Registro maestro y `workflows.md`
  actualizados.
- Identidad de nombres unificada: **Provecho** = ERP, **Grupo Majambo** =
  grupo empresarial (corregido `docs/00_PROJECT.md`, aclarado en
  `CLAUDE.md`).
- Referencias de ADR normalizadas a 3 dígitos (`ADR-001`..`ADR-004`);
  ruta corregida en `CLAUDE.md` (`docs/architecture/adr/`).
- Entidad `contrato` reubicada como transversal (antes aparecía dentro de
  la sección de Inventario del data-model); referencia rota de
  `contrato_laboral` corregida.
- Specs de módulos sincronizadas con el catálogo de eventos (secciones
  Publica/Escucha de sales, inventory, purchases, accounting) y mapa
  `docs/diagrams/modules.md` regenerado.
- `docs/diagrams/README.md` actualizado a la convención real: SOPs
  primero y BPMN después, taxonomía `Procesos/<Área>/<Grupo>/`, versiones
  antiguas de BPMN se conservan para análisis.

- `PROC-INV-001` Abastecimiento de locales v0.1 → v0.2: detalla el conteo
  de fin de jornada en sucursal (balanzas, lector QR, ventana de 5 min
  fuera de refrigeración, alerta por margen de error RN-INV-015, cálculo
  de sugerido por punto de reorden RN-INV-013). Sigue en Borrador —
  picking/packing/transporte en almacén central aún sin este nivel de
  detalle.
- `PROC-CTB-001` Cierre de caja v1.0 → v1.1: agrega la bifurcación de
  custodia del fondo/caja chica (local en sucursal vs. traslado a
  oficinas de contabilidad, RN-MDP-006); RN-MDP-002 ampliada para cubrir
  la cadena de custodia en sentido inverso (apertura). Máquina de estados
  "Custodia de efectivo" actualizada en `docs/domain/state-machines.md`.
- Referencias a Mercadopago eliminadas (decisión: Izipay).
- Docs reorganizados por tema (`foundation/`, `domain/`, `architecture/`,
  `engineering/`, `security/`, `product/`) en vez de numeración plana;
  índice y orden de lectura en `docs/00_PROJECT.md`.
- Nuevos documentos de conocimiento: glosario (lenguaje ubicuo), filosofía del
  negocio, reglas de negocio (separadas del modelo de dominio), catálogo de
  eventos, máquinas de estado, autorización (RBAC, separada de seguridad).
- `AI_RULES` → `engineering/engineering-guide.md` (guía extensa; `/CLAUDE.md`
  la resume y apunta a ella).

### Removed

- Borradores duplicados de Venta: carpeta `docs/diagrams/Procesos/Ventas/`
  (BPMN/BPM de borrador — el vigente es
  `Comercial/PROC-COM-001-v1.0.bpmn`) y `docs/diagrams/Ventas.bpm`.
  `Cobro-PROC-COM-002-v1.0.bpmn.bpm` renombrado a
  `PROC-COM-002-v1.0.bpm` (archivo de proyecto Bizagi, doble extensión
  corregida).

## [0.1.0] - 2026-07-04

### Added

- Scaffold inicial: modular monolith (FastAPI + Next.js + PostgreSQL).
- Core: app factory, settings por entorno, sesión SQLAlchemy, event bus interno.
- Endpoint `/health` con tests.
- Especificaciones (contratos) de módulos: users, inventory, sales, purchases, accounting.
- Documentación: arquitectura, ADRs, modelo de negocio, modelo de datos v1.
- Docker Compose (api, web, postgres, redis), CI con GitHub Actions.
- Reglas de desarrollo en `CLAUDE.md`.
