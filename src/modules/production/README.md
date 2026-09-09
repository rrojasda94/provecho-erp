# Módulo `production` — Producción de subrecetas

**Estado (2026-07-25):** slice core implementado (código, sin operación
real — primera cocina de producción planeada para 2027,
`docs/produccion/README.md`). Se construyó antes de esa fecha por pedido
explícito, siguiendo el mismo patrón slice-por-slice que
purchases/inventory/sales.

## Objetivo

Planificar y ejecutar la elaboración de subrecetas en cocina de
producción según cronograma + necesidad de Almacén Central, con control
de calidad obligatorio y trazabilidad completa por lote.

## Entidades

`plan_produccion` (cronograma: fecha, turno, línea de producción/tipo de
receta, origen `cronograma_fijo`|`ajuste_por_necesidad`), `orden_produccion`
(articulo_id subreceta, cantidad, almacen_id, plan_produccion_id opcional,
control_calidad_resultado, desperdicio/merma, costeo automático:
horas_hombre, costo_insumos, costo_mano_obra, costo_real_unitario —
RN-PRD-018), `consumo_produccion_item` (detalle de insumos consumidos por
orden: cantidad, costo_unitario, peso_desperdicio_real, tipo_desperdicio —
contrastado contra `receta_item.merma_pct`), `checklist_inocuidad_turno`
(bioseguridad, superficies, limpieza intermedia, equipos_frio JSONB,
plaga_indicio — bloquea la cocina si algo falla, RN-CDP-005),
`reporte_produccion` (jornada, visado_por, consolidado automático al
cierre). Detalle en `docs/architecture/data-model.md` §7.

`reporte_escalamiento` (origen `produccion`) vive en `reports` desde
ADR-036 — no en `shared`, como decía `data-model.md` §6 antes de que el
módulo existiera — y `lote` está modelada por `inventory`; `production`
las reutiliza, no las duplica. La no conformidad se escala **desde el
reporte** que emite `production.no_conformidad_detectada`, no desde la orden.

## Estado (slice core implementado 2026-07-25)

Operativo en `/api/v1/production`: `orden_produccion`, ad-hoc o colgada de
un `plan_produccion` (bloque `feat/produccion-plan-de-produccion`,
2026-09-09), crear (borrador) → registrar
consumo real de insumos (`consumo_produccion_item`, transición a
`en_proceso`) → completar con resultado de control de calidad
(`conforme` | `no_conforme_reprocesado` | `no_conforme_desechado`).
Costeo automático al completar (RN-PRD-018): `costo_insumos` (suma de
consumo real), `costo_mano_obra` (`horas_hombre` × tarifa por empresa
`production/costo_hora_mano_obra` en `parametro_empresa`, con
`settings.production_costo_hora_mano_obra` como semilla — ADR-014/068,
bloque `feat/produccion-costeo-real`), `costo_real_unitario`.
`horas_hombre` es el agregado de `orden_produccion_trabajador` (`Σ horas`):
`CompletarOrdenIn.trabajadores[]` imputa trabajadores concretos, cada uno
tope su propia asistencia real del día (`rrhh.queries_publicas.
horas_asistidas`, 409 si se excede o si no marcó — RN-RRHH-009, bloque
`feat/produccion-horas-hombre-desde-rrhh`), no el número libre de antes.
Resuelve la receta de la subreceta vía el nuevo `receta.articulo_id`
(nullable — liga una receta a la subreceta que produce, distinto del uso
existente `producto_comercial.receta_id` de venta directa). Capas
`domain/rules.py`, `infrastructure/repositories.py`, `application/`
(`ordenes.py`, `tarifas.py`), `api/`. Migración `f78501175fba` aplicada.

`registrar_consumo` costea cada línea al `costo_promedio` vigente del
artículo si no viene `costo_unitario` explícito, y admite tecleer la
cantidad en otra UdM de la misma categoría (`unidad_medida_id`,
RN-UDM-005) — se guarda ya convertida a la del artículo. `GET
/ordenes/{id}/consumo-sugerido` explota la receta BOM escalada a la
cantidad planeada, con la merma esperada de cada línea ya aplicada, para
prellenar el consumo en vez de calcularlo a mano. `GET /ordenes/{id}`
detalla los consumos reales con su `desviacion_desperdicio` (real vs. lo
que `receta_item.merma_pct` espera). `costo_teorico_insumos` queda de
snapshot al registrar el consumo, para comparar contra `costo_insumos`
(lo real) al completar (bloque `feat/produccion-costeo-real`, 2026-09-09).

| Método | Ruta | Permiso |
|--------|------|---------|
| POST | `/ordenes` | `production.crear` |
| GET | `/ordenes/{id}` | `production.leer` |
| GET | `/ordenes/{id}/consumo-sugerido` | `production.leer` |
| GET | `/trabajadores-disponibles` | `production.completar` |
| POST | `/ordenes/{id}/consumo` | `production.crear` |
| POST | `/ordenes/{id}/evidencia` | `production.completar` |
| POST | `/ordenes/{id}/completar` | `production.completar` |
| POST | `/planes` | `production.planificar` |
| GET | `/planes` | `production.leer` |
| GET | `/planes/{id}` | `production.leer` |
| POST | `/planes/{id}/ordenes` | `production.planificar` |
| POST | `/planes/{id}/iniciar` | `production.planificar` |
| POST | `/planes/{id}/cerrar` | `production.planificar` |
| POST | `/checklists` | `production.verificar_inocuidad` |
| GET | `/checklists` | `production.leer` |
| GET | `/checklists/{id}` | `production.leer` |
| POST | `/reportes-jornada/generar` | `production.visar_reporte_jornada` |
| GET | `/reportes-jornada` | `production.leer` |
| GET | `/reportes-jornada/{id}` | `production.leer` |
| POST | `/reportes-jornada/{id}/visar` | `production.visar_reporte_jornada` |
| POST | `/ordenes/{id}/ordenes-hijas` | `production.crear` |

`plan_produccion` (`application/planes.py`, bloque `feat/produccion-plan-
de-produccion`, 2026-09-09) es el cronograma fijo por línea/turno
(RN-PRD-007/012, único por `almacen_id, fecha, turno, linea_produccion`):
`crear` (`planificado`) → `agregar_orden` liga una `orden_produccion` con
`origen="plan"` → `iniciar` reserva los insumos de todas sus órdenes en
`inventory` (`reserva_stock.tipo="produccion"`, referenciada por
`orden_produccion.id` — un tipo de reserva que existía desde ADR-028 sin
ningún productor) y pasa a `en_ejecucion`; `StockInsuficiente` interrumpe
`iniciar` entero, sin reservas a medias → `registrar_consumo` cierra la
reserva de la orden cuando el insumo sale de verdad → `cerrar` libera lo
que ninguna orden llegó a consumir. `turno`/`linea_produccion` son texto
libre, no un catálogo con FK: `turno_sucursal` (RRHH) está atado a una
sucursal y una cocina de producción central no siempre tiene una.

`checklist_inocuidad_turno` (`application/inocuidad.py`, bloque
`feat/produccion-checklist-inocuidad`, 2026-09-09) registra bioseguridad,
superficies, limpieza intermedia, equipos de frío (JSONB, `dentro_rango` lo
calcula el servidor) y posible indicio de plaga por turno — único por
`almacen_id, fecha, turno`. `POST /checklists` calcula `estado`
(`aprobado`|`bloqueado`, RN-CDP-002/005): nunca lo decide quien lo llena.
Sin un checklist `aprobado` vigente del día en un almacén `tipo=produccion`,
`crear_orden_produccion` y `registrar_consumo` rechazan con 409
`cocina_bloqueada` — `application/inocuidad.py::exigir_cocina_habilitada`
usa el checklist más reciente del día, sin distinguir turno (`orden_
produccion` no registra en cuál se creó).

`reporte_produccion` (`application/reportes_jornada.py`, bloque
`feat/produccion-reporte-de-jornada`, 2026-09-09) consolida las órdenes
que cerraron control de calidad ese día en un almacén (RN-DOC-010) —
único por `almacen_id, jornada`. `generar_reporte_jornada` recalcula el
existente mientras no esté visado; una vez visado (`visado_por`/
`visado_at`) queda congelado, y `POST /reportes-jornada/{id}/visar` es el
único acto humano sobre el documento: se visa, no se redacta. El barrido
de Celery `production.generar_reportes_de_jornada_vencidos` (cada 15 min)
genera el de cada almacén `tipo=produccion` pasada la
`hora_cierre_jornada` de su empresa (`parametro_empresa`, semilla
`settings.production_hora_cierre_jornada`, ADR-014/068) — `POST
/reportes-jornada/generar` hace lo mismo a demanda. La orden aporta al
reporte por `orden_produccion.completado_at` (columna nueva, se fija al
completar): `updated_at` no sirve porque cualquier `flush` (p. ej.
`registrar_consumo`) lo pisa antes de que la orden cierre.

`orden_produccion.orden_padre_id` (bloque
`feat/produccion-subrecetas-anidadas`, 2026-09-09, RN-PRD-020) resuelve el
BOM de varios niveles: `GET /ordenes/{id}/consumo-sugerido` marca
`requiere_orden_hija` en la línea cuyo artículo tiene receta propia y no
alcanza el disponible del almacén (`inventory.application.reservas.
disponible`); `POST /ordenes/{id}/ordenes-hijas` crea esa orden, en el
mismo almacén, con `origen="subreceta_anidada"`. La orden padre rechaza
`registrar_consumo` con 409 mientras tenga una hija que no llegó a
`conforme` — el insumo que la hija fabrica todavía no existe como stock
real. Sin tope de niveles (una subreceta puede colgar de otra) y sin
riesgo de ciclo: una fila nueva no puede referenciarse a sí misma al
crearse.

`GET /trabajadores-disponibles` (`?area=`) lista los trabajadores activos
de la empresa vía `rrhh.queries_publicas.trabajadores_activos` — el picker
del diálogo de completar, para imputar mano de obra a alguien que RRHH ya
tiene como activo en vez de un nombre tipeado.

`POST /ordenes/{id}/evidencia` registra la evidencia de destrucción ya
subida al storage (`nombre`, `mime_type`, `tamano_bytes`, `url_storage`,
mismo contrato que `marketing.AdjuntoCreate`) como `Archivo`
(`orden.evidencia_archivo_id`, `shared/adjuntos.py`) — `completar` con
`no_conforme_desechado` exige que ya exista una (RN-PRD-015, bloque
`feat/produccion-evidencia-como-archivo`, 2026-09-09). Reemplaza al string
libre `evidencia_destruccion_url` que se tecleaba en el mismo `completar`
sin que nadie pudiera verificarlo.

Eventos: publica `production.consumo_registrado` (inventory descuenta
insumos, tipo `consumo_produccion`), `production.orden_completada`
(inventory suma stock del artículo terminado, tipo `produccion_entrada`,
y recalcula su `costo_promedio` — mismo listener/patrón que
`purchases.compra_recibida`) y `production.no_conformidad_detectada`
(sin consumidor todavía). Rol semilla `jefe_cocina`.

Deuda del slice (ver
[plan de deuda](../../../docs/roadmap/deuda-production-2026-09-09.md) y
[`docs/roadmap/deuda/modulo-production.md`](../../../docs/roadmap/deuda/modulo-production.md)):
sin ítems propios pendientes del plan original — quedan los bloques de
frontend heredados de bloques anteriores (ver "Pendiente de frontend"
abajo). Ya saldado: lote/trazabilidad
del producto terminado, auditoría e idempotencia de consumo/completar, el
asiento contable del desecho (ADR-098) (2026-09-09), el costeo real
—`costo_promedio` por defecto, consumo sugerido desde la BOM, tarifa de
mano de obra por empresa y desviación de desperdicio real vs. esperado
(2026-09-09)—, la evidencia de destrucción como `Archivo` en vez de
string libre (2026-09-09), las horas-hombre imputadas desde la
asistencia real de RRHH en vez de tipeadas a mano (2026-09-09), la orden
por ajuste de necesidad al cruzar `inventory.stock_bajo_minimo` en vez de
que alguien la cree a mano (2026-09-09), el plan de producción con
reserva de insumos al iniciar (2026-09-09), el checklist de inocuidad
de turno que bloquea crear orden y registrar consumo sin uno `aprobado`
vigente (2026-09-09), el reporte de producción de la jornada,
consolidado automático al cierre y visado por el jefe de cocina
(2026-09-09), y las subrecetas anidadas (BOM de varios niveles) con
orden hija y bloqueo de consumo en la padre (2026-09-09).

Pendiente de frontend: el diálogo de completar todavía manda
`evidencia_destruccion_url` como texto libre (`ordenes-cliente.tsx`) en
vez de subir la evidencia vía `POST .../evidencia` antes de completar —
`feat/produccion-evidencia-como-archivo` fue backend-only. La ficha
`/produccion/ordenes/[id]` (bloque `feat/produccion-subrecetas-anidadas`,
2026-09-09) ya existe con el árbol padre/hijas y el consumo sugerido con
`requiere_orden_hija`, pero solo con eso — el resto del alcance de B6f
(desviación de desperdicio, costo teórico vs. real, lote generado,
trazabilidad, diálogo de consumo prellenado) sigue pendiente. Bloque
`feat/produccion-ficha-y-consumo-sugerido` (B6f) o uno dedicado a esto.

## Casos de uso

- Definir plan de producción del periodo (cronograma fijo por línea/turno,
  evita contaminación cruzada — `POST /planes`); iniciarlo reserva los
  insumos de todas sus órdenes, cerrarlo libera lo que no se consumió.
- Generar orden de producción, desde el plan (`POST /planes/{id}/ordenes`)
  o por ajuste ante alerta de stock mínimo de `inventory` (RN-PRD-007/011),
  o suelta, ad-hoc.
- Ejecutar orden: consumir insumos/subrecetas, producir lote(s) con
  código y trazabilidad completa (manipulador, envasador, variables de
  proceso). Si un insumo es a su vez una subreceta sin disponible
  suficiente (BOM de varios niveles), fabricarla primero con su propia
  orden hija (`POST /ordenes/{id}/ordenes-hijas`, RN-PRD-020) — la padre
  no admite su consumo hasta que la hija llegue a `conforme`.
- Control de calidad de la orden antes de habilitar despacho: conforme,
  no conforme reprocesado, o no conforme desechado.
- No conformidad (cualquier resultado no conforme) emite el reporte, y desde
  ahí se abre el `reporte_escalamiento` (origen `produccion`, ADR-036);
  desecho exige evidencia de destrucción ya adjuntada (`POST .../evidencia`,
  RN-PRD-015) — la misma evidencia viaja en el payload y llena
  `reporte_escalamiento.evidencia_id` sin pedirla dos veces.
- Calcular costo real de la orden automáticamente (insumos consumidos +
  mano de obra) — nunca a mano; el desperdicio real por insumo se
  registra por tipo y peso, contrastado contra el esperado de la receta
  (RN-PRD-018).
- Verificar checklist de inocuidad al inicio de turno (`POST /checklists`),
  incluyendo temperatura de cada equipo de frío; bloquear la cocina y
  alertar a Gerencia y Cocina si algo falla (RN-CDP-002/005) — sin un
  checklist `aprobado` vigente ese día, ni crear orden ni registrar
  consumo pasan.
- Consolidar reporte de producción al cierre de jornada (`POST
  /reportes-jornada/generar` o el barrido automático de Celery pasada la
  `hora_cierre_jornada` de la empresa) y visarlo (`POST
  /reportes-jornada/{id}/visar`) — se visa, no se redacta (RN-DOC-010).
- Conteo cíclico del almacén propio (tipo `produccion`), mismo esquema
  que `inventory` en Almacén Central — el reporte se genera
  automáticamente a partir de los conteos físicos registrados; el jefe de
  cocina visa, no lo redacta a mano.
- Evaluar viabilidad técnica de nuevo producto o mejora de receta a
  pedido de `sales`/Comercial (RN-PRD-017) — completa la ficha, no la
  origina.

## Reglas

- Toda orden de producción pasa control de calidad antes de despachar
  (RN-PRD-013); nunca se salta este paso por presión de cronograma.
- No conformidad siempre genera reporte de escalamiento, se corrija o se
  deseche (RN-PRD-014); desecho sin evidencia de destrucción ya adjuntada
  (`POST /ordenes/{id}/evidencia`) no completa la orden (RN-PRD-015).
- Cambio de receta/subreceta notifica con urgencia a quienes fabrican y
  actualiza costos el mismo día (RN-PRD-009).
- Nunca despacha directo a sucursal, solo a Almacén Central (RN-CDP-001).
- Ningún documento de conteo o reporte de producción se llena a mano: se
  genera desde los datos ya registrados en el ERP (peso de balanza,
  lectura QR, horas-hombre); el rol humano es visar, no transcribir.
- Equipo de frío fuera de rango bloquea la cocina y alerta a Gerencia de
  inmediato (RN-CDP-005), igual criterio que la falla de frío en
  apertura de sucursal (RN-SUC-009).

## Flujo

Plan de producción (o necesidad urgente) → orden de producción → consumo
de insumos → elaboración → control de calidad → (conforme: empacado →
almacén de producción → despacho a Almacén Central) | (no conforme:
reproceso o desecho con evidencia → reporte de escalamiento).

## Relaciones

- Escucha: `inventory.stock_bajo_minimo` (`application/listeners.py::
  on_stock_bajo_minimo`, bloque `feat/produccion-orden-por-necesidad`,
  2026-09-09, RN-PRD-007/011): si el SKU es de un artículo con receta BOM y
  la empresa tiene **una sola** cocina de producción (almacén `tipo=
  produccion`), crea sola una orden `borrador` con `origen=ajuste_por_
  necesidad`, `cantidad_planeada = stock_minimo × factor_reposicion −
  cantidad` redondeada al rendimiento de la receta (factor en
  `parametro_empresa production/factor_reposicion`, semilla `2`) e
  `idempotency_key=f"necesidad:{sku_id}:{fecha}"`. No crea nada si ya hay
  una orden del mismo artículo sin cerrar control de calidad en ese
  almacén, ni si hay cero o más de una cocina (ahí sigue quedando solo el
  aviso de `reports`, para que Gerencia decida a mano).
- Publica: `production.consumo_registrado` (consumido por `inventory` para
  descontar insumos vía FEFO), `production.orden_completada` (consumido
  por `inventory` para sumar producto terminado y recalcular
  `costo_promedio`), `production.no_conformidad_detectada` (con
  `evidencia_id` si ya se adjuntó, consumido por `reports`, que abre el
  `reporte_escalamiento` con esa misma evidencia sin pedirla de nuevo;
  consumido por Comercial/Gerencia ante reincidencia),
  `production.orden_desechada`
  (solo cuando el resultado es `no_conforme_desechado`, consumido
  por `accounting` para el asiento por el costo de insumos consumidos —
  **no** es `inventory.merma_registrada`: el producto terminado de una
  orden desechada nunca ingresó a inventory, así que no hay reserva que
  apartar; ver ADR-098). Reproceso (`no_conforme_reprocesado`)
  correctamente no genera merma ni asiento, solo el detalle de la
  corrección en el reporte de escalamiento.
  `production.equipo_frio_fuera_rango` (por cada equipo de frío fuera de
  rango del checklist, RN-CDP-005) y `production.cocina_bloqueada` (al
  quedar el checklist `bloqueado`, RN-CDP-002/005) se publican desde
  `application/inocuidad.py::crear_checklist` (bloque
  `feat/produccion-checklist-inocuidad`, 2026-09-09), consumidos por
  `reports` (alerta a Gerencia y Cocina, nivel `urgente`).
  `production.reporte_produccion_generado` (bloque
  `feat/produccion-reporte-de-jornada`, 2026-09-09), sin actor —lo genera
  un barrido o el endpoint manual, no un acto de alguien—, consumido por
  `reports` (aviso a Gerencia y Cocina, nivel `aviso`).
