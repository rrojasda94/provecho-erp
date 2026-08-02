# ADR-020 — Abastecimiento interno: reserva, solicitud y transferencia

- Estado: aceptado
- Fecha: 2026-08-01

## Contexto

`inventory` sabía cuánto stock hay en cada almacén, pero no tenía cómo
moverlo entre ellos. Todo el ciclo que los SOP de Almacén ya describen
—conteo de fin de jornada → requerimiento → aprobación → picking →
transferencia en tránsito → recepción en el local— vivía únicamente como
documentación: `solicitud_insumos`, `transferencia` y `reserva_stock`
estaban en `data-model.md` desde el modelado, sin una línea de código.

El hueco tenía consecuencias más allá de "falta una pantalla": sin
reserva, el stock del central es un número que dos sucursales pueden leer
al mismo tiempo y prometerse entero. Entre que un supervisor aprueba un
requerimiento y el central arma el picking pasan horas.

## Decisión

**1. La reserva es una promesa, no un movimiento.** `reserva_stock` no
toca `stock` ni genera `movimiento_inventario`: lo que ya salió del
almacén es un movimiento, y llamarlo reserva sería contar dos veces. El
stock disponible pasa a ser **físico − Σ reservas activas** (RN-INV-009),
y `GET /inventory/stock` expone las tres cifras (`cantidad`, `reservado`,
`disponible`).

**2. Reservar bloquea; consumir no.** Comprometer stock nuevo (aprobar una
solicitud) exige disponible suficiente y falla con 409 si no alcanza. En
cambio una venta o un consumo de producción **nunca** se frenan por una
reserva: esa operación ya ocurrió en el mundo real y negarla en el ERP
solo desincroniza los libros. Es el mismo criterio que ADR-015 aplicó a la
salida FEFO sin lote que la respalde.

La consecuencia aceptada es que el disponible puede quedar **negativo**.
Eso no es un error: es la señal de que hay una promesa sin respaldo y
alguien tiene que liberarla o reponer. Un disponible que nunca puede ser
negativo solo se consigue bloqueando ventas, que es peor.

**3. La solicitud va por almacén, no por sucursal.** El borrador del
modelo decía `solicitud_insumos.sucursal_id`; se implementa
`almacen_solicitante_id` + `almacen_abastecedor_id`. El almacén de
producción también solicita, y la transferencia que sale de la solicitud
opera sobre almacenes: con `sucursal_id` habría que resolver "cuál de sus
almacenes" en cada paso. La sucursal se deriva de `almacen.sucursal_id`.

El abastecedor se copia a la fila al crearla, resuelto desde
`almacen.almacen_abastecedor_id`. Guardarlo y no derivarlo siempre es
deliberado: cambiar de quién se abastece un local no debe reescribir la
historia de lo ya pedido.

**4. `transferencia_item` va por SKU y lote.** El despacho reparte por
FEFO, así que sacar 10 kg puede tomar tres lotes; el destino tiene que
recibir esos mismos tres o la trazabilidad de ADR-015 se corta justo en el
traslado. Una fila por movimiento de salida generado. Recibir aplica la
entrada lote por lote.

**5. Las diferencias se registran, no se corrigen.** No se despacha más de
lo aprobado (RN-INV-001) ni se recibe más de lo enviado (RN-INV-002);
**menos sí**, en los dos casos. Si el central no tenía todo, sale lo que
hay y la diferencia queda en `solicitud_item.cantidad_despachada`. Si al
local le llegaron 28 de 30, entra al stock **lo que de verdad llegó** y la
diferencia viaja en `inventory.transferencia_recibida` para auditarse.
Cuadrar el papel a la fuerza es exactamente lo que hace que el inventario
teórico se despegue del real.

**6. Estados de la solicitud**: `pendiente` → `aprobada` | `rechazada` |
`cancelada`, y el despacho la lleva a `despachada` → `recibida`.
`cancelada` es nuevo respecto del borrador y es lo que hace cumplible
RN-INV-010: cancelar libera las reservas. Una solicitud ya despachada no
se cancela — eso movió stock y se corrige recibiendo o devolviendo.

**7. Se omite el estado `en_picking`** que el borrador listaba. No
gobierna ninguna regla: entre `aprobada` y `despachada` no cambia qué se
puede hacer, y habría exigido un endpoint de transición que nadie
consume. Si el negocio pide ver "el central ya empezó a armarlo", entra
entonces.

**8. Aprobar y solicitar son permisos distintos** (`inventory.solicitar_insumos`
/ `inventory.aprobar_solicitud`) y el aprobador no puede ser quien pidió —
mismo criterio de segregación que el ajuste de inventario (RN-INV-006).
Despachar y recibir reusan `inventory.transferir` e `inventory.recepcion`,
sembrados desde el slice 1 y sin uso hasta ahora.

**9. La transferencia lateral usa la misma entidad.** Sucursal↔sucursal va
con `solicitud_id` en NULL y los ítems en el request. Es una excepción
operativa documentada, no un modelo aparte.

## Consecuencias

- El disponible negativo es un estado alcanzable y visible. Falta una
  alerta que lo mire: hoy solo se ve consultando el stock.
- `reserva_stock` nace con dos tipos sin productor: `produccion` (lo
  emitirá el módulo cuando reserve insumos de una orden) y `carrito` (PDV).
  El tipo `merma` es la base de `stock_merma` (RN-INV-012), que sigue
  pendiente de su slice.
- `transferencia` no lleva vehículo ni tracking: `vehiculo` no existe como
  entidad. Queda `transportista_id` (FK a `usuario`) y el resto en ROADMAP.
- La recepción es de una sola pasada: no hay recepción parcial que deje la
  transferencia en tránsito por el resto. Con un solo viaje por
  transferencia alcanza; si aparece el caso, es un estado más.
- El ciclo no se replica al hub de sucursal (ADR-009): un local sin
  conexión no puede pedir ni recibir. El hub existe para vender offline.
- `guia_remision` sigue pendiente y ahora tiene de dónde colgarse: una
  transferencia entre almacenes de distinta dirección la necesita
  (RN-GDR-002).

## Alternativas descartadas

- **Descontar el stock al aprobar, en vez de reservar** — descartada:
  el stock seguiría físicamente en el estante del central y el ERP diría
  que no está. El conteo cíclico lo marcaría como sobrante todos los días.
- **Calcular el disponible sin tabla, restando solicitudes aprobadas** —
  descartada: ataría el concepto de reserva a una sola de sus fuentes.
  Producción, el carrito del PDV y la merma reservan igual y no son
  solicitudes; RN-INV-012 las declara explícitamente como reservas.
- **Bloquear ventas cuando no hay disponible** — descartada, ver punto 2.
- **`transferencia_item` por SKU, resolviendo el lote al recibir** —
  descartada: el destino elegiría un lote distinto al que salió y la
  trazabilidad se cortaría en el traslado, que es justo donde más importa.
- **Recibir cuadrando siempre contra lo enviado** — descartada: es
  falsificar el inventario. La diferencia es el dato valioso.
