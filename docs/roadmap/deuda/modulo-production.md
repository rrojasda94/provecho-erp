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
- ✅ 2026-09-09 **`plan_produccion`** (bloque `feat/produccion-plan-de-
  produccion`). Cronograma fijo por línea/turno (RN-PRD-007/012, único
  por `almacen_id, fecha, turno, linea_produccion` — `turno`/
  `linea_produccion` texto libre, no FK a `turno_sucursal`: una cocina de
  producción central no siempre tiene sucursal). `crear` (`planificado`)
  → `agregar_orden` liga una `orden_produccion` nueva (`origen="plan"`)
  → `iniciar` reserva los insumos de **todas** sus órdenes en `inventory`
  (`reserva_stock.tipo="produccion"`, referenciada por
  `orden_produccion.id` — el tipo de reserva que existía desde ADR-028
  sin ningún productor) y pasa a `en_ejecucion`; si algo no alcanza,
  `StockInsuficiente` interrumpe `iniciar` entero (la sesión hace
  rollback sola, sin reservas a medias) → `registrar_consumo` cierra la
  reserva de la orden al salir el insumo de verdad → `cerrar` libera lo
  que ninguna orden llegó a consumir. Pendiente: el listener de
  `inventory.stock_bajo_minimo` (`feat/produccion-orden-por-necesidad`)
  todavía no vincula la orden que crea al plan del día si existe — sigue
  naciendo suelta.
- ✅ 2026-09-09 **`checklist_inocuidad_turno`** (bloque
  `feat/produccion-checklist-inocuidad`). Bioseguridad, superficies,
  limpieza intermedia, equipos de frío (JSONB `[{equipo, temperatura_c,
  rango_min, rango_max, dentro_rango}]`, `dentro_rango` calculado por el
  servidor) e indicio de plaga (RN-CDP-002); único por `almacen_id, fecha,
  turno`. `POST /production/checklists` calcula `estado`
  (`aprobado`|`bloqueado`) — nunca lo decide quien lo registra: cualquier
  falla bloquea la cocina entera (más estricto que la letra de RN-CDP-005,
  que solo habla de detener "ese equipo" — mismo criterio que
  `data-model.md` §7 y el SOP de inocuidad). Sin checklist `aprobado`
  vigente del día en un almacén `tipo=produccion`, `crear_orden_produccion`
  y `registrar_consumo` rechazan con 409 `cocina_bloqueada`
  (`application/errors.py::CocinaBloqueada`). Publica
  `production.equipo_frio_fuera_rango` (por cada equipo fuera de rango) y
  `production.cocina_bloqueada`, ambos nivel `urgente` en el catálogo de
  `reports` (áreas `gerencia`, `cocina`) — el primero estaba documentado en
  `events.md` desde antes pero el código nunca lo publicó. Nuevo permiso
  `production.verificar_inocuidad` (seeder + `jefe_cocina`) y pantalla
  `/produccion/inocuidad`. Simplificación documentada: `orden_produccion`
  no registra en qué turno se creó, así que "vigente" es el checklist más
  reciente del almacén ese día, sin distinguir turno — una vez bloqueada
  la cocina, sigue bloqueada hasta que un checklist nuevo (de cualquier
  turno) la reapruebe.
- ⬜ **`reporte_produccion`** consolidado automático al cierre de jornada
  (RN-DOC-010), visado por el jefe de cocina, no redactado a mano.
  Bloque `feat/produccion-reporte-de-jornada`.
- ✅ 2026-09-09 **Merma → `accounting`** (bloque
  `feat/produccion-desecho-a-contabilidad`, ADR-100). No se reusó
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
- ✅ 2026-09-09 **Conteo cíclico del almacén de producción** (bloque
  `fix/inventario-cdp-001-y-conteo-produccion`). Nunca estuvo bloqueado por
  `inventory`: el conteo cíclico (`inventory/application/conteos.py`) es
  genérico por `almacen_id`, nunca consulta `almacen.tipo`. Lo que faltaba
  era cobertura de test explícita — `tests/test_conteos.py::
  test_conteo_ciclico_funciona_igual_en_almacen_de_produccion` abre,
  registra y cierra un conteo sobre un almacén `produccion` con el mismo
  resultado (ajuste por diferencia) que sobre el central, cerrando RN-PRD-016.
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
- ✅ 2026-09-09 **`production` no escuchaba `inventory.stock_bajo_minimo`**
  (bloque `feat/produccion-orden-por-necesidad`). Nuevo `production/
  application/listeners.py::on_stock_bajo_minimo`, registrado en
  `src/core/app.py`: si el artículo tiene receta BOM y la empresa tiene
  **una sola** cocina de producción, crea sola una orden `borrador`
  `origen=ajuste_por_necesidad` (columna nueva; `creado_por` pasa a
  nullable porque esta orden no tiene humano detrás), `cantidad_planeada`
  redondeada al rendimiento de la receta sobre `stock_minimo ×
  parametro_empresa production/factor_reposicion (semilla 2) − cantidad`,
  idempotente por SKU y día. No crea nada con cero o más de una cocina, ni
  si ya hay una orden del mismo artículo sin cerrar control de calidad en
  ese almacén (RN-PRD-007/011).
- ✅ 2026-09-09 **RN-CDP-001 sin enforcement** (bloque
  `fix/inventario-cdp-001-y-conteo-produccion`).
  `inventory.application.transferencias._validar_almacenes` rechaza con
  409 un despacho de un almacén `produccion` a uno `sucursal`; el mismo
  origen sigue pudiendo despachar al central, que es el tramo real
  (`tests/test_transferencias.py::
  test_produccion_no_despacha_directo_a_sucursal`).
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
- ✅ 2026-09-09 **Seeder sin datos de producción** (bloque
  `feat/produccion-semilla-y-pantalla-con-permisos`). `seed()` ahora crea
  `jefecocina1` (PIN 123456, rol `jefe_cocina`) y el almacén `WH-PROD`
  (tipo `produccion`, abastecido por el central). La receta BOM (insumo +
  subreceta con `articulo_id`) no se agregó a `seed()` sino a
  `python -m src.seeders.e2e`: un artículo real en el catálogo de la
  empresa de `seed()` rompía 21 tests de una docena de suites que asumen
  ese catálogo vacío salvo lo que cada una crea (colisión de
  `categoria_udm.nombre`, que es UNIQUE, y de conteos exactos de
  artículos/stock). `pdv_demo.py`/`pizzas_demo.py` siguen sin receta de
  producción — quedan fuera porque son seeders de demo, no de desarrollo
  ni de CI.
- ✅ 2026-09-09 **Frontend sin gates de permiso ni paginación server**
  (mismo bloque). `/produccion` ahora recibe `permisos={usuario.permisos}`
  y gatea "+ Nueva orden"/Consumo detrás de `production.crear` y
  Completar detrás de `production.completar` (patrón de
  `inventario/transferencias`); pagina con `?page=`/`page_size` en vez de
  pedir solo la primera página. La **ficha de detalle** sigue pendiente:
  bloque `feat/produccion-ficha-y-consumo-sugerido`.
- ⬜ **Frontend del diálogo de completar sigue mandando
  `evidencia_destruccion_url`**: `ordenes-cliente.tsx` no llama a `POST
  /ordenes/{id}/evidencia` antes de completar — `feat/produccion-
  evidencia-como-archivo` (2026-09-09) fue backend-only. El campo viaja y
  el backend lo ignora en silencio; el desecho queda bloqueado en 409
  hasta que se suba la evidencia por otro medio (Swagger, `curl`). Bloque
  `feat/produccion-ficha-y-consumo-sugerido` o uno dedicado.
- ⬜ **La orden por ajuste de necesidad no se vincula al plan del día**:
  `production/application/listeners.py::on_stock_bajo_minimo`
  (`feat/produccion-orden-por-necesidad`) crea la orden suelta; con
  `plan_produccion` ya modelado (`feat/produccion-plan-de-produccion`,
  2026-09-09) falta que la ligue al plan `planificado`/`en_ejecucion` de
  ese almacén y esa fecha si existe uno solo, para que la reposición
  automática entre al mismo cronograma y no aparezca como un plan
  independiente en el tablero del jefe de cocina.
