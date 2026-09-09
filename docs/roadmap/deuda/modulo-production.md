# Deuda técnica — Módulo production (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

Plan completo de cómo saldar esta deuda (bloques, orden, decisiones tomadas):
[`docs/roadmap/deuda-production-2026-09-09.md`](../deuda-production-2026-09-09.md).

- ✅ 2026-07-25 **Migración Alembic** `f78501175fba` (orden_produccion,
  consumo_produccion_item, receta.articulo_id) aplicada a la BD dev
  (Supabase).
- ✅ 2026-08-09 **`reporte_escalamiento` real** (ADR-036): la entidad existe,
  vive en `reports` (no en `shared`, ver el ADR) y la cadena se abre **desde
  el reporte** que emite `production.no_conformidad_detectada`.
  `registrado_por` se agregó al payload para que el reporte diga quién
  cerró la orden.
- ⬜ **`plan_produccion`** (cronograma fijo por tipo de receta/turno,
  evita contaminación cruzada): hoy toda orden se crea ad-hoc, sin plan.
  Bloque `feat/produccion-plan-de-produccion`.
- ⬜ **`checklist_inocuidad_turno`**: bioseguridad, superficies, equipos
  de frío (JSONB), indicio de plaga — bloquea la cocina si algo falla
  (RN-CDP-005), igual criterio que falla de frío en apertura de sucursal.
  Bloque `feat/produccion-checklist-inocuidad`.
- ⬜ **`reporte_produccion`** consolidado automático al cierre de jornada
  (RN-DOC-010), visado por el jefe de cocina, no redactado a mano.
  Bloque `feat/produccion-reporte-de-jornada`.
- ⬜ **Merma → `accounting`**: `no_conforme_desechado` registra
  `merma_cantidad`/`merma_motivo` en la orden pero nunca dispara un asiento
  contable. **No está bloqueado por `inventory`** — al revisar el 2026-09-09
  se confirmó que `stock_merma` nunca existió como tabla: la merma de
  `inventory` vive en `reserva_stock` (tipo `merma`, ADR-028) desde
  2026-08-06, con evento `inventory.merma_registrada` y asiento propio en
  `accounting`. El bloqueo real es de diseño interno de `production`: el
  producto terminado de una orden desechada **nunca entró a inventory**
  (solo se publica `orden_completada` en el caso `conforme`), así que no
  hay stock que reservar como merma — publicar `inventory.merma_registrada`
  no aplica aquí. La solución es un asiento propio de `production` contra
  el costo de insumos de la orden (ver el plan, bloque
  `feat/produccion-desecho-a-contabilidad`). Reproceso
  (`no_conforme_reprocesado`) correctamente no genera merma ni asiento
  (RN-PRD — solo detalle en el reporte de escalamiento).
- ✅ 2026-09-09 **Lote/trazabilidad del producto terminado** (bloque
  `feat/produccion-lote-trazabilidad-auditoria`). `CompletarOrdenIn` acepta
  `fecha_vencimiento`, `lote_codigo` y `trazabilidad` (JSONB libre:
  manipulador, envasador, línea, variables de proceso — RN-LOT-002/003);
  se persisten en la orden y, cuando el resultado es `conforme`, viajan en
  el payload de `production.orden_completada` — el listener de `inventory`
  ya sabía leerlos (ADR-015), solo faltaba que `production` los mandara.
  Sin ellos, el lote sigue naciendo sin vencimiento (FEFO cae a FIFO), que
  sigue siendo válido para quien no los declare. QR queda fuera de este
  bloque: no hay todavía dónde imprimirlo.
- ⬜ **Subrecetas anidadas**: una orden que consume otra subreceta (con su
  propia orden de producción) no está resuelta — hoy `registrar_consumo`
  espera insumos ya disponibles en stock. Bloque
  `feat/produccion-subrecetas-anidadas`.
- ⬜ **Conteo cíclico del almacén de producción**: **no está bloqueado por
  `inventory`** — al revisar el 2026-09-09 se confirmó que el conteo
  cíclico (`inventory/application/conteos.py`) es genérico por
  `almacen_id`, nunca consulta `almacen.tipo`, y el tipo `produccion` ya es
  un valor válido (`tests/test_production.py` lo usa). Lo que falta es
  cobertura de test explícita sobre un almacén `produccion` — no capacidad
  nueva. Bloque `fix/inventario-cdp-001-y-conteo-produccion`.
- ✅ 2026-09-09 **Segregación quien crea vs. quien completa la orden**: se
  evaluó y se decide **no exigirla**. `production.crear`/`production.completar`
  siguen siendo permisos distintos, pero nada impide que el mismo usuario
  tenga ambos y haga las dos acciones — a diferencia de `inventory.ajuste`,
  que sí exige aprobador≠solicitante. Razón: una cocina de producción tiene
  personal reducido (jefe de cocina + cocineros) y exigir un segundo
  usuario para cerrar el control de calidad de cada orden no aporta control
  real a esa escala; lo que sí importa es que quede auditado quién hizo
  cada paso, que se resuelve con `auditoria.registrar` (bloque
  `feat/produccion-lote-trazabilidad-auditoria`), no con una regla de
  negocio nueva. Reabrir si el negocio pasa a operar con turnos rotativos o
  más de un jefe de cocina por local.

## Deuda no declarada hasta esta revisión (2026-09-09)

Encontrada al auditar el módulo para el plan de deuda, sin ítem propio
hasta ahora:

- ⬜ **Costeo tipeado, no calculado**: `registrar_consumo` recibe
  `costo_unitario` desde el cliente en vez de leer
  `articulo.costo_promedio`; no hay "consumo sugerido" desde la receta BOM
  (`inventory.application.recetas.detalle_receta` ya calcula el costo
  teórico y no se usa); `peso_desperdicio_real`/`tipo_desperdicio` se
  guardan pero nunca se contrastan contra `receta_item.merma_pct`, que es
  literalmente lo que exige RN-PRD-018. Bloque `feat/produccion-costeo-real`.
- ✅ 2026-09-09 **Sin auditoría** (mismo bloque). `crear_orden_produccion`,
  `registrar_consumo` y `completar_orden_produccion` llaman a
  `auditoria.registrar` (ADR-031), con `datos_antes`/`datos_despues` y la
  IP del request (`Depends(client_ip)`, patrón de `reports`) — incluido el
  desecho, que es acto de plata y de autoridad por definición.
- ✅ 2026-09-09 **Idempotencia parcial** (mismo bloque). `registrar_consumo`
  y `completar_orden_produccion` aceptan `idempotency_key` opcional
  (columnas `consumo_idempotency_key`/`cierre_idempotency_key`, únicas y
  nullable): un reintento de red con la misma clave devuelve la orden tal
  como quedó, sin duplicar el consumo ni volver a cerrar la orden.
- ⬜ **Tarifa de mano de obra global, no por empresa**:
  `production_costo_hora_mano_obra` vive en `.env`
  (`src/config/settings.py`) en vez de `parametro_empresa`, a diferencia
  del resto del ERP (ADR-014/068). El módulo `"production"` ya está
  habilitado en `src/shared/parametros.py` y el permiso
  `production.proponer_parametro` ya se siembra — nadie lo usa todavía.
  Bloque `feat/produccion-costeo-real`.
- ⬜ **`production` no escucha `inventory.stock_bajo_minimo`**: el README
  del módulo dice "Escucha: `inventory.stock_bajo_minimo` (dispara orden
  por necesidad, RN-PRD-007)" pero no existe
  `production/application/listeners.py` ni se registra ningún handler en
  `src/core/app.py`. El evento sí se publica desde 2026-08-06. Bloque
  `feat/produccion-orden-por-necesidad`.
- ⬜ **RN-CDP-001 sin enforcement**: "una cocina de producción nunca
  despacha a un almacén de sucursal directamente" no tiene ningún control
  en `inventory.application.transferencias._validar_almacenes` — hoy nada
  impide despachar de un almacén `produccion` a uno `sucursal`. Bloque
  `fix/inventario-cdp-001-y-conteo-produccion`.
- ⬜ **Doble mecanismo de evidencia para RN-PRD-015**:
  `orden_produccion.evidencia_destruccion_url` es un string libre, mientras
  `reporte_escalamiento.evidencia_id` es una FK a `archivo` (con storage
  S3 real). Son dos formas de cumplir la misma regla y ninguna llena la
  otra. Bloque `feat/produccion-evidencia-como-archivo`.
- ⬜ **Horas-hombre tipeadas a mano**: `CompletarOrdenIn.horas_hombre` es un
  número libre pese a que RRHH ya tiene asistencia/marcación real
  (`asistencia`, `marcacion`); falta el contrato público de lectura.
  Bloques `feat/rrhh-horas-asistidas-contrato-publico` +
  `feat/produccion-horas-hombre-desde-rrhh`.
- ⬜ **Seeder sin datos de producción**: ningún seeder (`seed.py`, `e2e.py`,
  `pdv_demo.py`, `pizzas_demo.py`) crea un usuario con rol `jefe_cocina`,
  un almacén tipo `produccion`, ni una receta con `articulo_id` — sin esa
  receta, crear una orden se rechaza con 409. El módulo no se puede
  ejercitar en dev/staging sin el comodín de `admin`. Bloque
  `feat/produccion-semilla-y-pantalla-con-permisos`.
- ⬜ **Frontend sin gates de permiso ni ficha de detalle**: la pantalla
  `/produccion` no distingue `production.crear` de `production.completar`
  al mostrar botones, no recibe `usuario.permisos`, no tiene ficha `[id]`
  pese a que `GET /ordenes/{id}` existe, y pagina en el cliente en vez de
  con `page_size`. Bloques `feat/produccion-semilla-y-pantalla-con-permisos`
  y `feat/produccion-ficha-y-consumo-sugerido`.
