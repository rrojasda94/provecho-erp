# Módulo `inventory` — Inventarios, almacenes y transferencias

## Objetivo

Mantener stock exacto y auditable por almacén (central, producción, sucursal),
y gestionar el flujo solicitud → aprobación → picking → transferencia → recepción.

## Entidades

**Estado de implementación (2026-07-20):** modeladas las entidades base de
productos como dependencia del slice Venta — `articulo`, `sku`, `receta`,
`receta_item` (`src/modules/inventory/infrastructure/models/`), además
del bloque transversal ya existente (`categoria`, `categoria_udm`,
`unidad_medida`). `stock`, movimientos, transferencias, `lote` y demás
del flujo de almacén siguen pendientes del slice de Inventario.

`articulo` (tipos `insumo` | `subreceta` | `mercaderia` | `empaque` |
`repuesto` | `suministro` — enum extensible), `categoria`, `stock`,
`stock_lote` (detalle por lote — base de FEFO/FIFO), `stock_merma`
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

## Estado (slice 1 implementado 2026-07-25)

Operativo: catálogo (CRUD artículos/categorías/SKUs), stock por almacén y
ajuste con segregación de funciones. Capas `domain/rules.py`,
`infrastructure/` (modelos `stock`, `movimiento_inventario`, `ajuste` +
`repositories.py`), `application/` (`catalogo.py`, `stock.py`, `ajustes.py`),
`api/`. Migración `be914c92a94b`. Reusa auth/RBAC de `users`.

Endpoints `/api/v1/inventory`:

| Método | Ruta | Permiso |
|--------|------|---------|
| POST/GET | `/categorias` | `gestionar_catalogo` / `leer` |
| POST/GET/PATCH | `/articulos[/{id}]` | `gestionar_catalogo` / `leer` |
| POST | `/skus` | `gestionar_catalogo` |
| GET | `/stock` | `leer` |
| POST | `/movimientos` | `registrar_movimiento` |
| POST | `/ajustes` | `solicitar_ajuste` |
| POST | `/ajustes/{id}/aprobar` \| `/rechazar` | `aprobar_ajuste` |

Reglas ya aplicadas: stock solo cambia vía `movimiento_inventario`; salida no
deja stock negativo; ajuste `solicitar` ≠ `aprobar` y aprobador ≠ solicitante;
alerta `bajo_minimo` derivada en la consulta; evento
`inventory.ajuste_fuera_margen` al aprobar fuera de margen.

`application/stock.py::contar_bajo_minimo(session, empresa_id)` (nuevo
2026-07-26, ADR-012): cuenta filas bajo mínimo escopadas por empresa (vía
`Almacen.empresa_id` — mismo import de modelo permitido que ya usa
`application/listeners.py`), consumido por `core.dashboard_router` para el
dashboard gerencial.

**Diferido (deuda del módulo):** `stock_lote`/FEFO, `reserva_stock`, conteo
cíclico, transferencias/`solicitud_insumos`, devolución, guía de remisión,
listeners de eventos (`sales.venta_confirmada` → consumo por receta),
contexto de tenant desde el JWT (hoy `empresa_id` viene en el body).

## Sincronización con el hub de sucursal (implementado 2026-07-27)

`application/sincronizacion.py` declara qué replica este módulo hacia el
hub local (ADR-009 fase 2): unidades de medida, categorías, artículos,
SKU, recetas y el `stock` del almacén de esa sucursal. Sin stock local, la
primera venta offline fallaría al descontar insumos — el listener
`sales.venta_confirmada` corre también dentro del hub.

`stock` es el único recurso que el hub además escribe por su cuenta. La
nube gana en el pull, y eso es correcto porque el ciclo **empuja antes de
jalar**: para cuando el hub lee el stock de la nube, la nube ya procesó
las ventas del corte.

`registrar_movimiento` acepta un `id` client-generado (mismo motivo que en
`sales`), aunque hoy el sync no empuja movimientos.

## Flujo

Solicitud (local) → aprobación (supervisor) → picking/packing (central) →
salida → transferencia en tránsito → recepción (local) → stock actualizado.

## Relaciones

- Escucha: `sales.venta_confirmada` (descuenta insumos según receta),
  `purchases.compra_recibida` (suma stock central),
  `production.orden_completada` (consume insumos, produce subrecetas).
- Publica: `inventory.stock_consumido` (auditoría del descuento por venta/
  producción), `inventory.stock_bajo_minimo`, `inventory.transferencia_recibida`,
  `inventory.merma_registrada` (accounting recibe para su reporte de
  pérdidas), `inventory.devolucion_a_proveedor` (purchases gestiona
  reclamo/nota de crédito), `inventory.ajuste_fuera_margen` (accounting/
  administrador reciben alerta de auditoría),
  `inventory.lote_vencido_detectado` (notifica y dispara memorándum al
  responsable si el lote vencido seguía disponible).
