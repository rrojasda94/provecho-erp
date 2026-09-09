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
- ✅ 2026-09-09 **Merma → `accounting`** (bloque
  `feat/produccion-desecho-a-contabilidad`, ADR-098). No se reusó
  `inventory.merma_registrada` a propósito: esa merma opera sobre una
  `reserva_stock` de un SKU que ya está en el almacén, y el producto
  terminado de una orden desechada **nunca entró a inventory** (solo se
  publica `orden_completada` en el caso `conforme`) — no hay reserva que
  apartar. Nuevo evento propio `production.orden_desechada`
  (`{orden_produccion_id, almacen_id, articulo_id, merma_cantidad,
  merma_motivo, monto, registrado_por}`, `monto = costo_insumos` de la
  orden — la mano de obra queda afuera porque ya se reconoce como gasto de
  planilla) y su plantilla PCGE (`D 6599 / H 201`, mismo circuito que la
  merma de `inventory`, desglosado por la categoría del artículo
  producido). Reproceso (`no_conforme_reprocesado`) sigue sin generar
  merma ni asiento (RN-PRD — solo detalle en el reporte de escalamiento).
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

- ✅ 2026-09-09 **Costeo tipeado, no calculado** (bloque
  `feat/produccion-costeo-real`). `registrar_consumo` costea al
  `costo_promedio` vigente del artículo (`inventory.application.
  queries_publicas.costo_promedio_de_articulos`) cuando la línea no manda
  `costo_unitario` explícito. Nuevo `GET /ordenes/{id}/consumo-sugerido`
  explota la receta BOM (`inventory.application.queries_publicas.
  consumo_sugerido_de_receta`, misma cuenta que `recetas.costo_linea`)
  escalada a `cantidad_planeada`, con la merma esperada de cada línea ya
  aplicada. `GET /ordenes/{id}` pasa a devolver los consumos reales con
  `desviacion_desperdicio` (`peso_desperdicio_real` contra lo que
  `receta_item.merma_pct` esperaba) — antes se guardaba y nunca se
  contrastaba contra nada, que es literalmente lo que exige RN-PRD-018.
  `orden.costo_teorico_insumos` queda de snapshot al registrar el consumo
  para esa comparación al completar. `consumo_produccion_item.
  unidad_medida_id` (nullable = la del artículo, mismo criterio que
  `receta_item`) permite teclear en otra UdM de la misma categoría
  (RN-UDM-005); se guarda ya convertida.
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
- ✅ 2026-09-09 **Tarifa de mano de obra global, no por empresa** (mismo
  bloque). `production/application/tarifas.py::costo_hora_mano_obra_de`
  lee `parametro_empresa` `production/costo_hora_mano_obra` (ADR-014/068,
  mismo patrón que `sales.application.tarifa_delivery`), con
  `settings.production_costo_hora_mano_obra` como semilla mientras
  Gerencia no apruebe ninguna propuesta.
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
- ✅ 2026-09-09 **Doble mecanismo de evidencia para RN-PRD-015** (bloque
  `feat/produccion-evidencia-como-archivo`). `orden_produccion.
  evidencia_destruccion_url` (string libre) desaparece: la evidencia se
  registra vía `POST /ordenes/{id}/evidencia` como `Archivo`
  (`orden.evidencia_archivo_id`, `src/shared/adjuntos.py` — extraído de
  `marketing.application.adjuntos`, que ya validaba MIME/tamaño para lo
  mismo). `completar_orden_produccion` con `no_conforme_desechado` exige
  que ya exista; el mismo id viaja en `production.no_conformidad_
  detectada.evidencia_id` y `reports.application.escalamientos.abrir` lo
  usa como default de `reporte_escalamiento.evidencia_id` (la FK que ya
  existía) sin que el usuario lo vuelva a pegar a mano al abrir el
  escalamiento. Migración con datos: toda `evidencia_destruccion_url` no
  nula se convierte en `Archivo` antes de borrar la columna.
- ✅ 2026-09-09 **Horas-hombre tipeadas a mano** (bloques `feat/rrhh-horas-
  asistidas-contrato-publico` + `feat/produccion-horas-hombre-desde-rrhh`).
  `CompletarOrdenIn.horas_hombre` (número libre) se reemplaza por
  `trabajadores[]` (`trabajador_id` + horas opcionales): sin horas
  explícitas se imputa toda la asistencia real del día
  (`rrhh.queries_publicas.horas_asistidas`); con ellas, tope lo asistido
  (409 si se excede, 409 si no marcó ese día — RN-RRHH-009).
  `orden_produccion.horas_hombre` pasa a ser el agregado (`Σ horas` de la
  nueva `orden_produccion_trabajador`). Nuevo `GET
  /production/trabajadores-disponibles` (`rrhh.queries_publicas.
  trabajadores_activos`) alimenta el picker del diálogo de completar.
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
