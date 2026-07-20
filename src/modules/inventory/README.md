# Módulo `inventory` — Inventarios, almacenes y transferencias

## Objetivo

Mantener stock exacto y auditable por almacén (central, producción, sucursal),
y gestionar el flujo solicitud → aprobación → picking → transferencia → recepción.

## Entidades

`articulo` (insumo | subreceta), `categoria`, `stock`, `stock_merma`
(subtipo de stock reservado), `movimiento_inventario` (inmutable, solo
inserción), `solicitud_insumos`, `solicitud_item`, `transferencia`,
`transferencia_item`, `lote` (código, fecha_vencimiento, condiciones de
almacenamiento), `conteo`, `ajuste` (motivo, solicitante, aprobador),
`devolucion` (origen `proveedor` | `sucursal`). Detalle en
`docs/architecture/data-model.md` §3–§4.

## Casos de uso

- CRUD de artículos y categorías.
- Consultar stock por almacén / artículo; alertas de stock mínimo (punto de
  reorden, calculado con el dato de consumo real de `inventory`, definido
  en conjunto con `production` y `accounting` — `inventory` no compra, solo
  alerta; `purchases` ejecuta).
- Ajustes de inventario (con motivo, auditados): solicitar y autorizar son
  permisos distintos (`inventory.solicitar_ajuste` /
  `inventory.aprobar_ajuste`), nunca el mismo usuario.
- Conteo cíclico: registro de conteo físico (opcionalmente "a ciegas", sin
  mostrar el stock esperado según permiso del rol) vs. stock del sistema,
  con diferencia calculada automáticamente.
- Local crea solicitud de insumos → supervisor aprueba/rechaza.
- Almacén central: picking → packing → salida (transferencia en tránsito).
- Local recibe transferencia → stock local sube; diferencias quedan registradas.
- `transferencia` es genérica por `origen_almacen_id`/`destino_almacen_id`
  — cubre tanto central↔sucursal como transferencia lateral sucursal↔sucursal
  (excepción documentada, no cambia el modelo).
- FEFO/FIFO: picking sugiere el lote a tomar según `lote.fecha_vencimiento`
  (o fecha de ingreso si no aplica vencimiento); alerta de próximos a
  vencer con ventana configurable por artículo.
- Registro de merma/desperdicio con motivo (vencimiento, daño, error de
  recepción, plaga, otro) → mueve el stock a `stock_merma` (subtipo
  reservado, no disponible) y expone reporte consolidado a `accounting`.
- Devolución a proveedor: genera evento consumido por `purchases` para
  gestionar reclamo/nota de crédito; devolución sucursal→central usa el
  mismo flujo de `transferencia` con motivo `devolucion`.

## Reglas

- El stock nunca se edita directo: todo cambio pasa por `movimiento_inventario`.
- No despachar más de lo aprobado; no recibir más de lo enviado sin registro de diferencia.
- Transferencia descuenta origen al salir y suma destino al recibirse (en tránsito entre ambos).
- Ajustes requieren permiso `inventory.ajustar` (desglosado en solicitar/aprobar) y motivo obligatorio.
- Ajuste dentro del margen de error configurado (acordado con `accounting`)
  no dispara alarma; fuera de margen sí, y exige investigación documentada
  antes de aprobar.
- Movimiento de salida siempre respeta FEFO/FIFO — el picking no permite
  tomar un lote distinto al sugerido sin override explícito y motivo.

## Flujo

Solicitud (local) → aprobación (supervisor) → picking/packing (central) →
salida → transferencia en tránsito → recepción (local) → stock actualizado.

## Relaciones

- Escucha: `sales.venta_confirmada` (descuenta insumos según receta),
  `purchases.compra_recibida` (suma stock central),
  `production.orden_completada` (consume insumos, produce subrecetas).
- Publica: `inventory.stock_bajo_minimo`, `inventory.transferencia_recibida`,
  `inventory.merma_registrada` (accounting recibe para su reporte de
  pérdidas), `inventory.devolucion_a_proveedor` (purchases gestiona
  reclamo/nota de crédito), `inventory.ajuste_fuera_margen` (accounting/
  administrador reciben alerta de auditoría).
