# Módulo `purchases` — Compras

## Objetivo

Gestionar proveedores y el ciclo orden de compra → recepción → entrada al
almacén central, con costos trazables. Cubre también compra menor sin OC
(proveedor informal, vía caja chica) y compra de activos/equipamiento con
validación cruzada de área solicitante y gerencia.

## Entidades

`proveedor` (incluye flag `formal`/`informal` y condición
`zona_amazonia` para IGV), `orden_compra` (tipo `insumo` | `activo`),
`orden_compra_item`, `recepcion_compra`, `recepcion_item`, `cotizacion`
(dirección `de_proveedor`), `caja_chica_compras`, `caja_chica_movimiento`,
`compra_directa` (compra sin OC a proveedor informal, sustentada solo con
comprobante), `evaluacion_proveedor` (indicador calculado + registro
cualitativo), `requerimiento_activo` (ficha de especificación + validación
de área/gerencia, ligada a la OC de tipo `activo`). Detalle en
`docs/architecture/data-model.md` §5.

## Estado (slice core implementado 2026-07-25)

Operativo en `/api/v1/purchases`: CRUD de proveedores (natural liga a
`persona` — mismo party model que `cliente`, RN-GEN-007 — jurídico trae
razón social/RUC propios) y ciclo de OC tipo `insumo`: crear (borrador,
idempotente) → emitir (permiso `purchases.aprobar` exigido si el total
supera el umbral configurable `purchases_umbral_aprobacion_oc`) → recibir
(total o parcial, nunca más de lo ordenado) → anular (solo antes de
cualquier recepción). Capas `domain/rules.py`,
`infrastructure/repositories.py`, `application/` (`proveedores.py`,
`ordenes.py`), `api/`. Migración `4ff85f833b29` aplicada.

| Método | Ruta | Permiso |
|--------|------|---------|
| POST/GET/PATCH | `/proveedores[/{id}]` | `purchases.crear` / `leer` |
| POST | `/ordenes-compra` | `purchases.crear` |
| GET | `/ordenes-compra/{id}` | `purchases.leer` |
| POST | `/ordenes-compra/{id}/emitir` | `purchases.crear` (+ `aprobar` sobre umbral) |
| POST | `/ordenes-compra/{id}/recepciones` | `purchases.recepcionar` |
| POST | `/ordenes-compra/{id}/anular` | `purchases.anular` |

Eventos: publica `purchases.oc_emitida` y `purchases.compra_recibida`
(inventory suma stock en el almacén destino y recalcula
`articulo.costo_promedio` — promedio ponderado solo contra el stock del
almacén que recibe, ver `ponytail:` en
`inventory/application/listeners.py`) y `purchases.oc_anulada`. Rol
semilla `comprador` (crear/leer/recepcionar/anular); `supervisor` y
`admin` tienen `purchases.aprobar`.

Deuda del slice (ver ROADMAP): `cotizacion` (camino no-preferente sin
modelar — hoy toda OC insumo emite sin cotización comparativa),
OC tipo `activo` + `requerimiento_activo` con doble aprobación,
`compra_directa` + `caja_chica_compras`/`caja_chica_movimiento` +
`rendicion_caja_chica` (compra a proveedor informal), `evaluacion_proveedor`
automática por recepción, `comprobante` recibido y evento
`purchases.comprobante_conforme` (accounting aún no lo consume), listener
de `inventory.devolucion_a_proveedor`.

## Casos de uso

- CRUD de proveedores, con alta condicionada a verificación de RUC
  activo/habido (proveedores formales) — proveedores informales se
  registran sin RUC obligatorio.
- Crear OC (borrador) → emitir → recibir (total o parcial) → cerrar/anular.
  - **Camino simplificado**: si `proveedor.clasificacion == preferente` y
    el ítem es recurrente, la OC se emite sin `cotizacion` previa
    vinculada; el sustento es el `requerimiento_almacen` + la
    `recepcion_compra`/factura.
  - **Tipo `activo`**: exige `requerimiento_activo` con validación de área
    solicitante y de gerencia (dos aprobaciones distintas, ambas
    registradas) antes de permitir la emisión, además de mínimo 2
    `cotizacion` vinculadas — no aplica el camino simplificado.
- Registrar `compra_directa` (sin OC): proveedor informal, comprobante
  obligatorio, cargo a `caja_chica_movimiento`.
- Gestionar `caja_chica_compras`: fondo fijo, movimientos de gasto,
  rendición semanal (cierre de periodo) que Contabilidad concilia y repone.
- Recepción registra cantidades reales y actualiza costo promedio del
  artículo; genera/actualiza `evaluacion_proveedor.indicador_automatico`
  (cumplimiento de plazo, conformidad, variación de precio) en cada
  recepción — sin proceso batch aparte.
- Aprobación de OC sobre monto umbral (`purchases.aprobar`, permiso
  existente) es independiente de la validación de gerencia para OC tipo
  `activo` (esta última no es un permiso de monto, es una validación de
  contenido/especificación).

## Reglas

- OC emitida es inmutable; correcciones vía nueva versión o anulación
  (auditadas).
- Recepciones parciales permitidas; no recibir más de lo ordenado sin
  permiso especial.
- `idempotency_key` en emisión de OC, recepción y `compra_directa`.
- Aprobación de OC sobre monto umbral requiere permiso `purchases.aprobar`
  (umbral configurable).
- OC tipo `activo` requiere `requerimiento_activo.aprobado_area = true` y
  `requerimiento_activo.aprobado_gerencia = true` antes de permitir emisión
  — bloqueo a nivel de dominio, no solo de UI.
- `compra_directa` exige comprobante adjunto antes de guardarse; sin
  comprobante no se persiste.
- `purchases` **no ejecuta pagos** — solo marca el comprobante como
  `conforme` y lo entrega (evento) a `accounting`, que decide y ejecuta el
  pago según la condición de la ficha del proveedor.
- Cierre de `caja_chica_compras` (rendición) requiere que
  `gasto_total + efectivo_restante == fondo_fijo`; si no cuadra, el cierre
  queda `con_diferencia` y no repone el fondo hasta resolverse.

## Flujo

Proveedor → Cotización (o camino simplificado) → Orden de Compra →
Recepción → Almacén Central (evento a `inventory`) → Comprobante conforme
→ evento a `accounting` (pago). Rama paralela: Proveedor informal →
Compra directa → Caja chica → Rendición semanal → `accounting`.

## Relaciones

- Escucha: `inventory.devolucion_a_proveedor` (gestiona reclamo/nota de
  crédito con el proveedor).
- Publica: `purchases.compra_recibida` (inventory suma stock),
  `purchases.oc_emitida` (accounting provisiona),
  `purchases.comprobante_conforme` (accounting ejecuta pago según
  condición del proveedor),
  `purchases.caja_chica_rendida` (accounting concilia y repone fondo),
  `purchases.evaluacion_proveedor_actualizada` (informativo, sin
  consumidor obligatorio todavía).
