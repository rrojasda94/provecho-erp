# Bitácora de construcción — Provecho ERP

Registro de lo construido y lo pendiente. Actualizar en cada cambio relevante.

Este archivo es un **tablero**: estado actual por módulo, decisiones pendientes
transversales e índice de deuda técnica. El detalle narrativo completo de cada
módulo — todo lo construido, fecha por fecha, con sus ADRs y decisiones — vive en
[`docs/roadmap/historial/`](docs/roadmap/historial/), un archivo por módulo.

Este archivo llegó a tener 1413 líneas mezclando, sin orden fijo, una tabla de
estado inicial, una bitácora de parches por fecha, slices de desarrollo por
módulo y una lista suelta de pendientes — el mismo tema (ej. RRHH) terminaba
descrito en tres lugares con estados que ya no coincidían. Se reorganizó el
2026-09-06 aplicando el mismo criterio que ya se usó con la Deuda técnica
(ver más abajo): un archivo por módulo en `docs/roadmap/`, y este archivo como
índice. **No se borró contenido** — todo el historial narrativo original sigue
completo en `docs/roadmap/historial/<modulo>.md`, solo reordenado
cronológicamente y con el estado vigente marcado cuando una entrada posterior
corregía a una anterior.

## Estado por módulo

Leyenda: `✅ Completo` (operativo, sin trabajo pendiente conocido más allá de
deuda técnica menor) · `🔶 En curso` (slice(s) en producción, quedan piezas por
construir) · `⏳ Pendiente` (especificado, sin código) · `🗑️ Descartado` (se
decidió no hacerlo).

| Módulo / área | Estado | Resumen | Historial |
| --- | --- | --- | --- |
| Fundaciones y arquitectura (core, CI/CD, seguridad base, observabilidad, backups, offline/hub, frontend, UX) | 🔶 En curso | Núcleo transversal construido y operando en staging; falta primer despliegue completo de producción y el droplet de BI/Superset. | [`fundaciones-y-arquitectura.md`](docs/roadmap/historial/fundaciones-y-arquitectura.md) |
| `users` (auth JWT+PIN, RBAC, organización) | ✅ Completo | Auth, RBAC con restricciones, refresh rotativo, lockout, token de agente IA, CRUD de organización, reseteo de PIN y consulta RENIEC/SUNAT en producción desde 2026-07-25; los cambios recientes son ajustes, no funcionalidad faltante. | [`modulo-users.md`](docs/roadmap/historial/modulo-users.md) |
| `inventory` (catálogo, stock, lotes/FEFO, conteo, abastecimiento, recetas) | 🔶 En curso | Catálogo, stock por almacén, lote/FEFO, conteo cíclico, abastecimiento interno, recetas/variantes, abastecedor de respaldo, devoluciones y planillas .xlsx operables de punta a punta; deuda menor pendiente. | [`modulo-inventory.md`](docs/roadmap/historial/modulo-inventory.md) |
| `purchases` (proveedores, órdenes de compra) | 🔶 En curso | Ciclo de OC completo con idempotencia y umbral configurable, recepción a inventario, conformidad de comprobante y compra directa; pendiente caja chica para compra directa y reconciliación completa con contabilidad. | [`modulo-purchases.md`](docs/roadmap/historial/modulo-purchases.md) |
| `assets` (activos, mantenimiento, combustible, documentos con vencimiento) | 🔶 En curso | Activo/vehículo, kilometraje y consumo de combustible con detección de anomalía, cronograma de mantenimiento con aviso anticipado y documentos con vencimiento (SOAT, licencias, certificados), todo operativo desde 2026-09-09; `flota`, alta automática desde compras y depreciación siguen pendientes. | [`modulo-assets.md`](docs/roadmap/historial/modulo-assets.md) |
| `sales` (PDV, KDS, catálogo de venta) | 🔶 En curso | PDV/KDS/catálogo operativo con mesas, cupones, cocina por estaciones, variantes/restas y delivery; queda el motor de promociones condicionales completo, la entidad `entrega` y tarifa de delivery por sucursal. | [`modulo-sales.md`](docs/roadmap/historial/modulo-sales.md) |
| `production` (orden de producción) | 🔶 En curso | Slice core implementado desde 2026-07-25 (consumo, calidad, costeo); la primera cocina de producción central real está planeada para 2027, hoy la producción ocurre en cocinas de sucursal. | [`modulo-production.md`](docs/roadmap/historial/modulo-production.md) |
| `accounting` (libro contable + tesorería) | 🔶 En curso | PCGE, periodos, asientos automáticos/manuales, libro mayor, estados financieros, ciclo de caja/custodia y pago a proveedor en producción desde 2026-09-05; deuda declarada en fecha real del asiento y registro de préstamos/traspasos. | [`modulo-accounting.md`](docs/roadmap/historial/modulo-accounting.md) |
| `rrhh` (contratación, legajo, asistencia, planilla) | 🔶 En curso | Ciclo laboral, contratación/convocatoria, ARCO de postulante, asistencia PAD, terminal de marcaje y legajo+permisos construidos y probados; boletas/liquidaciones (nómina) siguen por API a propósito. | [`modulo-rrhh.md`](docs/roadmap/historial/modulo-rrhh.md) |
| `marketing` (campañas, leads, encuestas, agencias) | 🔶 En curso | Core operativo completo (campañas, contenido, leads con atribución, encuestas por WhatsApp, evaluación de agencias); queda deuda declarada, 2 ítems de alto impacto. | [`modulo-marketing.md`](docs/roadmap/historial/modulo-marketing.md) |
| `reports` (catálogo de reportes + Gerencia/dashboards) | 🔶 En curso | Motor de consulta y emisión/distribución construidos y en uso, catálogo cerrado, escalamiento y matriz de áreas editable; edición de reglas de distribución sigue por API y el BI autoservicio (Superset) sin desplegar. | [`modulo-reports.md`](docs/roadmap/historial/modulo-reports.md) |
| `delivery` (reparto propio: repartidores, rutas, seguimiento público) | 🔶 En curso | Slices 2-3 implementados 2026-09-09 (ADR-098): repartidores, tablero de despacho, ciclo completo de ruta/entrega con ruteo real (Google Routes) u heurístico, GPS de flota y enlace público de seguimiento con mapa, convergiendo con `sales` por evento en los dos sentidos. Falta la PWA del repartidor, el tablero en el frontend del ERP y el aviso automático por WhatsApp. | [`modulo-delivery.md`](docs/roadmap/historial/modulo-delivery.md) |
| Calidad y auditorías transversales | 🔶 En curso | Rondas periódicas de auditoría de punta a punta (Ola 1 a Ola 4, ago-sep 2026) que encuentran y corrigen bugs cruzando varios módulos a la vez, antes de sumar funcionalidad nueva. | [`calidad-y-auditorias.md`](docs/roadmap/historial/calidad-y-auditorias.md) |

## Pendientes de decisión (registro vivo)

Marcar aquí cuando cada uno se resuelva (y actualizar el doc que lo
contiene, buscando su `[[ COMPLETAR ]]`):

- ✅ 2026-07-27 **Mecanismo para los valores operativos configurables**
  (umbral de OC, margen de contribución mínimo,
  margen de error de ajuste, monto de caja chica, plazo de envío de
  comprobantes, rangos salariales): decidido con el usuario que **no son
  valores fijos** — se configuran en `parametro_empresa` por empresa, los
  gestiona Gerencia, y un cambio puede sustentarse en un acta
  (`decision_gerencial`) cuando amerite (no obligatorio para un ajuste
  rutinario). Ver ADR-014, `data-model.md` §8c, RN-GER-008 y
  `docs/gerencia/politica-gerencia.md#parámetros-operativos-configurables`.
  **Ampliado 2026-08-02** (ADR-014 Addendum, RN-GER-009): cada parámetro
  se configura **desde el módulo al que pertenece**, pero el cambio **no
  surte efecto hasta que Gerencia lo aprueba** en su sección de
  aprobaciones (aceptar / rechazar / modificar). Implementado: entidad,
  migración `a71c9f4b2e60`, endpoints `/api/v1/parametros[/{id}/aprobar|
  /rechazar]`, un permiso por módulo `<modulo>.proponer_parametro`.
  Lo que queda abierto por cada uno de los puntos de abajo ya **no es el
  mecanismo** (resuelto e implementado) sino que **el área proponga y
  Gerencia apruebe el valor real** — trabajo de configuración/negocio, no
  bloquea código:
  **Propuestos 2026-08-05** con su sustento en
  `docs/gerencia/propuesta-parametros-operativos.md` y cargados como
  `estado='propuesto'` (`python -m src.seeders.parametros`, idempotente):
  13 filas esperando en `/gerencia/parametros`. Cada propuesta declara de
  dónde sale el número, **qué pasa si está mal** y cuándo revisarlo — un
  parámetro mal puesto no rompe nada, distorsiona una decisión diaria
  durante meses sin que nadie lo note.
  - 🔶 `purchases/oc_umbral` — propuesto S/ 2,000 (confirma el semilla).
    **El de menor base**: no hay histórico de OC contra el cual calibrarlo.
    Sigue abierto si hace falta un umbral separado para activos.
  - 🔶 `sales/margen_minimo` — propuesto 60 %, desde food cost 32 % +
    empaque 3 % + comisión 4 %, y alcanzable porque Amazonía exonera el IGV.
  - 🔶 `sales/incentivo_meta_pct` — propuesto bono **grupal por sucursal**,
    3 % del excedente sobre la meta, techo 0.5 RMV. Sigue necesitando la
    aprobación conjunta de Comercial + RRHH + Gerencia (política §3).
  - 🔶 `inventory/margen_error_ajuste` — propuesto 2 % **más piso de
    S/ 20**: el porcentaje solo castiga a las categorías baratas y vuelve
    ruido la alerta. El piso **exige código**, ver deuda de inventory.
  - 🔶 `purchases/monto_caja_chica` — propuesto S/ 500 con reposición al
    bajar de S/ 150.
  - 🔶 `accounting/plazo_envio_comprobante` — propuesto 5 días hábiles
    desde el cierre. Es plazo **interno**: el vencimiento real de SUNAT
    depende del último dígito del RUC.
  - 🔶 `rrhh/rango_salarial_<perfil>` × 7 — propuestos como **múltiplo de
    RMV** (1.00–2.80 según perfil), no en soles. Dos cosas antes de
    aprobar: **confirmar la RMV vigente** (el marco legal la registra en
    S/ 1,130 con nota de verificar) y contrastar contra avisos reales de
    Tarapoto — la propuesta tiene la estructura de responsabilidad, no el
    mercado local.
  Quedan **fuera** de este mecanismo por ser decisión de rol, no de valor
  (resueltas 2026-08-05 con el usuario):
  - ✅ 2026-08-05 **El suplente de OC es otro administrador**, no el
    encargado de turno: una OC sobre el umbral es una decisión de plata.
    Consecuencia en código: se **retiró** `purchases.aprobar` del rol
    `supervisor`, que lo tenía desde el slice inicial y contradecía esta
    decisión. Revocado también en la BD dev — el seeder solo agrega.
  - ✅ 2026-08-05 **Los ajustes de inventario los aprueba el supervisor**
    de turno: está en el local, ve el faltante y decide en el momento. Ya
    tenía `inventory.aprobar_ajuste`; queda confirmado y comentado. El
    "supervisor de logística" como rol aparte se descarta: sería un rol
    nuevo para una sola capacidad que el supervisor ya ejerce. La
    segregación que importa —quien solicita no aprueba— vive en el dominio,
    no en el rol.
- ✅ 2026-07-20 `reporte_escalamiento`: definido con el usuario — cadena
  atención al cliente → supervisor (redacta solución) → comercial/gerencia
  (acciones reportadas); se almacena para mejora continua
  (`data-model.md` §6). **Implementado el 2026-08-09** (ADR-036) en
  `src/modules/reports/`, no en `shared`: ancla al `reporte_emitido` y no a la
  venta, y el escalón se resuelve con áreas + encargado de turno porque el ERP
  no tiene jerarquía organizacional.
- ✅ 2026-07-27 Cumplimiento de pedido: **UN** proceso — `PROC-OPE-002`
  (área Operaciones), con Preparación y Despacho/Entrega como etapas
  internas, no dos procesos. Razones: un solo resultado (entra Orden de
  Pedido, sale pedido entregado) sin artefacto de traspaso; la máquina de
  estados ya implementada (`venta_item.estado_preparacion`) es una sola y
  las pantallas KDS `preparacion`/`despacho` son vistas de ella; "Producción"
  ya nombra la cocina de producción central (`PROC-PRD-001`, 2027) y
  reusarlo rompía la nomenclatura. Desbloquea `sales.venta_entregada` y
  `marketing.encuesta_enviada`; se separa como v2.0 si el reparto llega a
  tener ruteo/flota/liquidación propios.
- ✅ 2026-07-22 Módulo `marketing`: README/contrato propio —
  `src/modules/marketing/README.md` + área documentada en `docs/marketing/`.
- ✅ 2026-07-24 Área Contabilidad documentada — `docs/contabilidad/`
  (tesorería + finanzas + registro en un responsable, supervisada por
  Gerencia); resuelve el pendiente "Contabilidad: procesos y plantillas" y
  confirma CAJ/TES/ACT bajo Contabilidad. Incluye auditoría interna en dos
  niveles (RN-CTB-009): Contabilidad audita a Compras/Almacén/cajas de
  sucursal; Gerencia audita a Contabilidad. Propuestos PROC-CTB-006..013.
  Pendientes de este mismo pendiente: separar tesorería/registro al salir de
  REMYPE, y llevar entidades contables (asiento, plan de cuentas, activo
  fijo, conciliación) a `data-model.md` en su slice.
- ⬜ Tratamiento de contratos vigentes al salir de REMYPE (~jul 2027).
- ✅ 2026-08-05 Entidades de **Comercial-estrategia** y **RRHH-proceso**
  llevadas a `data-model.md`. `convocatoria` y `postulante` ya estaban
  desde el slice de contratación (2026-08-01) — la entrada las seguía
  listando como pendientes. Especificadas ahora, sin implementar:
  `meta_venta` + `meta_venta_seguimiento` y `hallazgo_mercado` en §6;
  `entrevista`, `plan_induccion` + `plan_induccion_item`,
  `evaluacion_periodo_prueba`, `evaluacion_desempeno` y `capacitacion` +
  `capacitacion_asistente` en §8b.
  Tres decisiones que valen más que las tablas: (a) **la escala 1-4 es la
  misma en toda la organización** —entrevista, periodo de prueba, desempeño
  comercial— para poder comparar a una persona consigo misma a lo largo del
  tiempo, y los criterios van en JSONB porque cada puesto pregunta lo suyo;
  (b) **evaluación de desempeño y capacitación viven en `rrhh` aunque las
  ejecute Comercial**: su artefacto termina en el file personal y `sales`
  no puede ser dueño de datos de `trabajador` — Comercial produce, RRHH
  custodia, y `evaluador_id` deja visible que el evaluador fue de otra
  área; (c) **el seguimiento de la meta es tabla, no columna**: guardar
  solo el cumplimiento final convierte la meta en un número que se mira
  cuando ya no hay nada que hacer, que es justo lo que el SOP quiere
  evitar. Falta el slice que las implemente.
- ✅ 2026-08-05 BPMN de las cuatro áreas nuevas, con sus PROC registrados
  en el maestro y su narrativa en `workflows.md` (el enfoque era *primero
  SOP, luego BPMN*, y los SOPs ya estaban estables):
  **PROC-RRH-001** Incorporación de personal ·
  **PROC-CMP-001 v2.0** Compras (los tres caminos: informal con caja chica,
  preferente sin cotización, estándar/activo con RFQ) ·
  **PROC-COM-003** Definición y revisión de precio ·
  **PROC-INV-001 v0.2** Abastecimiento de locales, que además pasa de
  Borrador a **Vigente**: el ciclo está implementado (ADR-020) y el traslado
  ya emite guía (ADR-027).
- ✅ 2026-08-05 BPMN de las dos contingencias:
  **PROC-RRH-002** personal faltante en la apertura (RN-RRHH-011 — el local
  **abre igual**, el pago extra del reemplazo se le descuenta al faltante
  salvo constancia médica) y **PROC-RRH-003** tardanza o falta del encargado
  (RN-RRHH-010 — hasta 30 min es memorándum y *no es sanción*, más de 30 min
  o falta es amonestación). Ninguna de las dos tiene soporte en código
  todavía: son proceso, no pantalla.
- ✅ 2026-07-27 Catálogo de paletas de accesibilidad y niveles de tamaño de
  fuente — propuesta técnica definida (dos paletas: Provecho estándar y
  un modo alto contraste/daltonismo inspirado en Okabe-Ito que cubre
  protanopía+deuteranopía; 4 niveles de tamaño de fuente vía
  `--font-scale`). `docs/product/ui-ux.md#catálogo-de-paletas-y-tamaños-de-fuente-propuesta-técnica-2026-07-27`.
  Sujeta a ajuste si aparece validación real con usuarios daltónicos/baja
  visión. Sin implementar todavía.
- ✅ 2026-07-27 Grupo Majambo **no tiene tema propio** — Provecho es el
  único tema fuera de PDV/Kiosk (`docs/product/ui-ux.md`).
- ✅ 2026-08-24 **Dónde trabaja alguien y qué datos alcanza son dos cosas**
  (ADR-062, migración `b6d29f10c47e`, RN-RRHH-019). No se podía asignar un
  trabajador a una sucursal ni un supervisor a varias: `trabajador` no tenía
  local (la asistencia no tenía a qué sucursal atribuirse) y `usuario_sucursal`
  tenía endpoints desde el slice inicial **pero ninguna pantalla** — fuera del
  seeder nadie repartía alcance. Ahora `trabajador.sucursal_id` (nullable) es
  el **centro de labores**, un hecho laboral de RRHH, y `usuario_sucursal`
  sigue siendo el **alcance de datos** de la cuenta; se editan por separado en
  RRHH → Trabajadores y Usuarios → Cuentas. Un supervisor sobre varios locales
  son **varias filas**: se descartó una tabla `zona` porque hoy ningún reporte,
  permiso ni regla la nombra —sería una entidad con tenant, seeder y CRUD para
  ahorrar dos clics—. De paso se cerraron dos agujeros del endpoint que ya
  existía: no validaba tenant (se podía dar acceso al local de otra empresa del
  grupo) y no auditaba. Nuevo `GET /users/{id}/sucursales`. Tests en
  `tests/test_rrhh.py` y `tests/test_organizacion_crud.py`.
- ✅ 2026-08-23 **Droplet de staging levantado** (DigitalOcean, ver
  [`docs/engineering/staging.md`](docs/engineering/staging.md) para IP,
  dominios y bitácora — nunca secretos ahí). Usuario `app` sin root/password
  por SSH, firewall, Docker, DNS de `staging.majambo.com.pe` y
  `api-staging.majambo.com.pe` ya resueltos. Escrito en el repo:
  `docker-compose.staging.yml`, `Caddyfile` (TLS automático, elegido sobre
  nginx+certbot para no mantener renovación a mano), `.env.staging.example`,
  `scripts/desplegar.sh` y `release.yml` publicando también la imagen del
  frontend (`ghcr.io/rrojasda94/provecho-erp-web`) — antes solo publicaba el
  backend, staging no habría tenido pantallas.
- ⬜ **Falta para terminar el primer despliegue de staging:**
  1. `.env` real en el servidor (`JWT_SECRET`/`POSTGRES_PASSWORD` generados
     ahí, nunca en una conversación — un secreto que la pasó deja de serlo).
  2. `docker login ghcr.io` con el token de lectura ya generado.
  3. Primer `docker compose -f docker-compose.staging.yml up -d` y
     verificación de `/health/ready`.
  4. Cron de backup diario (`python -m src.backups.backup`) y purga semanal
     de postulantes (`python -m src.modules.rrhh.purga`) dados de alta en
     el droplet.
  5. Monitor externo (healthchecks.io/UptimeRobot) contra `/health`,
     `/health/ready`, `/health/backups` — es lo único que no se puede
     resolver dentro del VPS (ADR-007).
- ✅ 2026-08-27 **La landing pública del QR tiene dominio propio**
  (`clientes.majambo.com.pe`, ADR-080). El QR de la mesa apuntaba a
  `staging.majambo.com.pe/reconocerte`: un nombre que dice «staging» y cuya
  raíz es el ERP entero. El recorte va en el `Caddyfile` —no en
  `middleware.ts`, cuyo `matcher` excluye los prefetch y dejaría el guard
  esquivable con una cabecera— y solo deja pasar `/reconocerte*`,
  `/_next/static/*`, `/_next/image*`, `/marcas/*` y el favicon; el resto
  redirige 302 a la landing. Verificado con `caddy validate` + `caddy adapt` y
  un Caddy local contra el dev server: las dos trampas de sintaxis que caza
  ese paso (`redir` sin `*`, orden de los `handle`) producen configuraciones
  **válidas** que hacen otra cosa. **No es un control de seguridad** y **no es
  el padrón real**: `/login` sigue público en el otro dominio, y lo que se
  registre cae en la base desechable de staging. Nada de esto llega al droplet
  hasta que alguien copie el `Caddyfile` a mano — ver `staging.md` y
  `deuda/ci-cd.md`.
- ⬜ **Producción sigue parqueada** (decisión 2026-08-05): dominio real,
  decidir dónde vive la copia on-premise de los backups, y stack de
  observabilidad (`docker-compose.observabilidad.yml`) — todo eso se retoma
  cuando exista la máquina de producción, staging no la reemplaza.

## Deuda técnica pendiente (backlog)

Registro vivo de deuda técnica declarada al cerrar cada slice — para que no
se olvide. Marcar ✅ al resolverse en el slice indicado.

Vive en [`docs/roadmap/deuda/`](docs/roadmap/deuda/), **un archivo por área**.
Estaba todo acá —2.000 líneas en una sola sección— y era donde caían casi
todos los conflictos de merge: dos ramas de módulos distintos chocaban por
compartir archivo, no por contradecirse. Las referencias en prosa del tipo
«ver ROADMAP → Deuda técnica → Frontend» siguen valiendo: el área es el
nombre del archivo.

| Área | Archivo | ⬜ abiertos | ✅ cerrados |
| --- | --- | --- | --- |
| Transversal | [`transversal.md`](docs/roadmap/deuda/transversal.md) | 1 | 35 |
| Seguridad (tras el endurecimiento base de 2026-07-26) | [`seguridad.md`](docs/roadmap/deuda/seguridad.md) | 12 | 6 |
| Dashboard y caja (tras la implementación de 2026-07-26 — ADR-012) | [`dashboard-y-caja.md`](docs/roadmap/deuda/dashboard-y-caja.md) | 6 | 17 |
| Protección de datos personales (tras la implementación de 2026-07-26 — ADR-011) | [`proteccion-de-datos-personales.md`](docs/roadmap/deuda/proteccion-de-datos-personales.md) | 8 | 1 |
| Contrato de API (tras la implementación de 2026-07-26 — ADR-010) | [`contrato-de-api.md`](docs/roadmap/deuda/contrato-de-api.md) | 6 | 1 |
| Modo offline del PDV (tras la fase 2 de 2026-07-27 — ADR-009) | [`modo-offline-del-pdv.md`](docs/roadmap/deuda/modo-offline-del-pdv.md) | 10 | 3 |
| CI/CD (tras la implementación de 2026-07-26) | [`ci-cd.md`](docs/roadmap/deuda/ci-cd.md) | 6 | 5 |
| Observabilidad y salud (tras las implementaciones de 2026-07-26) | [`observabilidad-y-salud.md`](docs/roadmap/deuda/observabilidad-y-salud.md) | 3 | 6 |
| Backups (tras la implementación de 2026-07-26) | [`backups.md`](docs/roadmap/deuda/backups.md) | 4 | 1 |
| Módulo inventory (slices siguientes) | [`modulo-inventory.md`](docs/roadmap/deuda/modulo-inventory.md) | 1 | 55 |
| Módulo sales (slices siguientes) | [`modulo-sales.md`](docs/roadmap/deuda/modulo-sales.md) | 51 | 28 |
| Módulo purchases (slices siguientes) | [`modulo-purchases.md`](docs/roadmap/deuda/modulo-purchases.md) | 7 | 3 |
| Módulo assets (slice core — deuda declarada) | [`modulo-assets.md`](docs/roadmap/deuda/modulo-assets.md) | 8 | 1 |
| Módulo production (slices siguientes) | [`modulo-production.md`](docs/roadmap/deuda/modulo-production.md) | 8 | 1 |
| Módulo accounting (slices siguientes) | [`modulo-accounting.md`](docs/roadmap/deuda/modulo-accounting.md) | 8 | 3 |
| Módulo rrhh (slice completo — deuda declarada) | [`modulo-rrhh.md`](docs/roadmap/deuda/modulo-rrhh.md) | 11 | 4 |
| Módulo marketing (slice core — deuda declarada) | [`modulo-marketing.md`](docs/roadmap/deuda/modulo-marketing.md) | 5 | 2 |
| Frontend (F2 — arquitectura y UX, documento 2026-07-27, actualizado tras ADR-013) | [`frontend.md`](docs/roadmap/deuda/frontend.md) | 11 | 24 |
