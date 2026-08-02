# Módulo `inventory` — Inventarios, almacenes y transferencias

## Objetivo

Mantener stock exacto y auditable por almacén (central, producción, sucursal),
y gestionar el flujo solicitud → aprobación → picking → transferencia → recepción.

## Entidades

**Estado de implementación (2026-08-01):** implementados el bloque
transversal (`categoria`, `categoria_udm`, `unidad_medida`), la base de
productos (`articulo`, `sku`, `receta`, `receta_item`), `stock`,
`movimiento_inventario`, `ajuste`, `lote` + `stock_lote` (FEFO),
`conteo` + `conteo_item` (conteo cíclico) y el ciclo de abastecimiento
interno (`reserva_stock`, `solicitud_insumos` + `solicitud_item`,
`transferencia` + `transferencia_item`). `stock_merma`, `devolucion` y
`guia_remision` siguen pendientes de sus slices.

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
- Conteo cíclico: registro de conteo físico (a ciegas por defecto — el
  stock esperado solo lo ve quien tenga `inventory.ver_stock_esperado`)
  vs. stock del sistema, con diferencia calculada automáticamente. La
  periodicidad la fija la categoría del SKU, y lo no contado en su fecha
  se reporta a almacén y gerencia.
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

## Estado (slice 4 — reserva, solicitud y transferencia, 2026-08-01)

Ciclo completo de abastecimiento interno según ADR-020: el local pide, el
supervisor aprueba y reserva, el central despacha, el local recibe.

- **`reserva_stock` es una promesa, no un movimiento**: no toca `stock` ni
  genera `movimiento_inventario`. `GET /stock` devuelve ahora `cantidad`
  (físico), `reservado` y `disponible` = físico − reservas activas
  (RN-INV-009).
- **Reservar bloquea, consumir no**: aprobar una solicitud exige
  disponible suficiente (409 si no alcanza), pero una venta o un consumo
  de producción **nunca** se frenan por una reserva — ya ocurrieron. El
  disponible puede quedar negativo y eso es la señal de una promesa sin
  respaldo, no un error.
- **La solicitud va por almacén**, no por sucursal: producción también
  solicita. El abastecedor sale de `almacen.almacen_abastecedor_id` y se
  copia a la fila.
- **Estados**: `pendiente` → `aprobada` | `rechazada` | `cancelada`, y el
  despacho la lleva a `despachada` → `recibida`. Cancelar libera las
  reservas (RN-INV-010). `en_picking` no se implementó: no gobierna
  ninguna regla.
- **`transferencia_item` va por SKU y lote**: el despacho reparte por FEFO
  y el destino recibe los mismos lotes que salieron (ADR-015).
- **Las diferencias se registran, no se corrigen**: no se despacha más de
  lo aprobado (RN-INV-001) ni se recibe más de lo enviado (RN-INV-002);
  menos sí en ambos casos. Al destino entra lo que de verdad llegó y la
  diferencia viaja en `inventory.transferencia_recibida`.
- **Transferencia lateral** sucursal↔sucursal: misma entidad con
  `solicitud_id` en NULL e ítems explícitos.

| Método | Ruta | Permiso |
|--------|------|---------|
| GET | `/reservas?almacen_id&sku_id` | `leer` |
| POST | `/reservas/{id}/liberar` | `liberar_reserva` |
| POST/GET | `/solicitudes` | `solicitar_insumos` / `leer` |
| GET | `/solicitudes/{id}` | `leer` |
| POST | `/solicitudes/{id}/aprobar` \| `/rechazar` | `aprobar_solicitud` |
| POST | `/solicitudes/{id}/cancelar` | `solicitar_insumos` |
| POST/GET | `/transferencias` | `transferir` / `leer` |
| GET | `/transferencias/{id}` | `leer` |
| POST | `/transferencias/{id}/recibir` | `recepcion` |

Solicitar y aprobar son permisos distintos y el aprobador no puede ser
quien pidió (RN-INV-006). `transferir` y `recepcion` ya estaban sembrados
desde el slice 1 sin uso: este slice los estrena.

Tests: `tests/test_transferencias.py` (23 casos). Migración `d8b35f1ca207`.

## Estado (slice 3 — conteo cíclico, 2026-08-01)

`conteo` + `conteo_item` según ADR-019. La periodicidad **la fija la
categoría** (`categoria.frecuencia_conteo`: diario / semanal / quincenal /
mensual / semestral / anual, RN-INV-007) — no hay un número universal.
NULL deja la categoría fuera del ciclo.

- **Programa derivado, sin tabla de calendario**: la próxima fecha de una
  categoría en un almacén es el último conteo **cerrado** que la cubrió
  más los días de su frecuencia; si nunca se contó, cuenta desde el alta
  de la categoría. Un conteo general (`categoria_id` NULL) pone al día a
  todas las categorías de ese almacén.
- **Snapshot al abrir**: `cantidad_sistema` se congela al abrir el conteo,
  no al cerrarlo. Un SKU contado que no estaba en el snapshot entra con
  sistema en 0 — es justo el sobrante que el conteo busca.
- **A ciegas por defecto** (RN-INV-005): el detalle omite
  `cantidad_sistema`/`diferencia` salvo permiso
  `inventory.ver_stock_esperado`. `almacenero` cuenta sin verlo.
- **Cerrar solicita, no corrige**: cada diferencia genera un `ajuste`
  `pendiente` con `ajuste.conteo_id`, que aprueba otro usuario
  (RN-INV-006). Los ítems no contados se ignoran: un conteo parcial no
  declara faltante lo que nadie miró. `dentro_margen` sale de
  `INVENTORY_MARGEN_AJUSTE_PCT` (2% por defecto, RN-INV-015); con sistema
  en 0 cualquier diferencia queda fuera de margen.
- **Lo no contado en su fecha se reporta a almacén y gerencia**
  (RN-INV-021): `inventory.conteo_vencido`. El día de vencimiento aún no
  es atraso.

| Método | Ruta | Permiso |
|--------|------|---------|
| PATCH | `/categorias/{id}` | `gestionar_catalogo` |
| GET | `/conteos/programa?almacen_id` | `leer` |
| POST | `/conteos/verificar-vencidos?almacen_id` | `contar` |
| POST | `/conteos` | `contar` |
| GET | `/conteos/{id}` | `contar` (+ `ver_stock_esperado` para el esperado) |
| POST | `/conteos/{id}/cantidades` | `contar` |
| POST | `/conteos/{id}/cerrar` | `contar` |

Cerrar un conteo crea los ajustes con `inventory.contar`, sin exigir
además `solicitar_ajuste`: cerrar el conteo **es** solicitar esos ajustes,
y ninguno mueve stock sin la firma de un aprobador distinto.

`PATCH /categorias/{id}` acepta `quitar_frecuencia: true` para sacar una
categoría del ciclo — mandar `frecuencia_conteo: null` significa "no la
toques", no "bórrala".

Tests: `tests/test_conteos.py` (22 casos). Migración `c4e70a91d5b8`.

## Estado (slice 2 — lote/FEFO, 2026-07-27)

`lote` (código, vencimiento, origen, condición de almacenamiento) y
`stock_lote` (saldo por lote y estado `disponible`/`bloqueado`/`agotado`)
implementados según ADR-015. El control es **opcional por artículo**
(`articulo.controla_lote`): solo los perecibles/trazables mueven stock por
lote.

- **FEFO al salir**: `application/stock.py::registrar_salida` reparte la
  cantidad entre los lotes con saldo, del vencimiento más próximo al más
  lejano (sin vencimiento va al final → FIFO por fecha de ingreso), y
  genera **un movimiento por lote tomado**. Un `lote_id` explícito es el
  override del lote sugerido.
- **Vencidos**: el picking bloquea el lote vencido que encuentra todavía
  disponible y publica `inventory.lote_vencido_detectado`;
  `POST /lotes/bloquear-vencidos` hace el mismo barrido a demanda.
- **Ingresos**: la recepción de compra crea el lote con el código y
  vencimiento declarados por el proveedor (RN-VNC-002) y producción con
  `origen=produccion`. Un ingreso sin lote de un artículo que lo controla
  entra al lote del día — nada queda fuera de la trazabilidad.

| Método | Ruta | Permiso |
|--------|------|---------|
| POST | `/lotes` | `registrar_movimiento` |
| GET | `/lotes?almacen_id&sku_id&por_vencer_dias` | `leer` |
| POST | `/lotes/bloquear-vencidos` | `registrar_movimiento` |

`POST /movimientos` devuelve ahora una **lista** de movimientos (una salida
FEFO puede repartirse entre varios lotes) y acepta `lote_id` opcional.

Tests: `tests/test_lotes.py`. Migración `c9a2f4e18b60`.

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
| GET | `/unidades-medida` | `leer` — catálogo global, sin filtro de tenant (`data-model.md` §3) |
| POST | `/unidades-medida` | `gestionar_catalogo` — CRUD antes diferido (ADR-014 Addendum b); requiere `categoria_udm_id` existente |
| PATCH | `/unidades-medida/{id}` | `gestionar_catalogo` — corrige `decimales` (RN-GER-010) sin recrear la unidad |
| GET/POST | `/categorias-udm` | `leer` / `gestionar_catalogo` |
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

**Diferido (deuda del módulo):** devolución, guía de remisión,
`stock_merma`. Del slice de abastecimiento: el disponible negativo no
tiene alerta, `reserva_stock` nace con tres tipos sin productor
(`produccion`, `carrito`, `merma`), la transferencia no lleva vehículo ni
tracking (`vehiculo` no existe), la recepción es de una sola pasada (sin
parcial) y el ciclo no se replica al hub. Del slice de lote: la reposición por venta anulada entra al
lote del día y no al lote del que salió, y la ventana de alerta de
vencimiento se pasa por request (`por_vencer_dias`) en vez de configurarse
por artículo. Del slice de conteo: el barrido de vencidos es a demanda
(no hay periódico), `inventory.conteo_vencido` no tiene consumidor,
`conteo` no se replica al hub y el margen de ajuste vive en `settings` y
no en `parametro_empresa`. Ver ROADMAP → Deuda técnica → Módulo inventory.

## Sincronización con el hub de sucursal (implementado 2026-07-27)

`application/sincronizacion.py` declara qué replica este módulo hacia el
hub local (ADR-009 fase 2): unidades de medida, categorías, artículos,
SKU, recetas, el `stock` del almacén de esa sucursal y —desde el slice de
lote— `lote` y `stock_lote`. Sin stock local, la primera venta offline
fallaría al descontar insumos — el listener `sales.venta_confirmada` corre
también dentro del hub; sin los lotes, ese descuento no podría aplicar
FEFO y elegiría un lote distinto al que elige la nube.

`stock` y `stock_lote` son los recursos que el hub además escribe por su
cuenta. La
nube gana en el pull, y eso es correcto porque el ciclo **empuja antes de
jalar**: para cuando el hub lee el stock de la nube, la nube ya procesó
las ventas del corte.

`registrar_movimiento` acepta un `id` client-generado (mismo motivo que en
`sales`), aunque hoy el sync no empuja movimientos.

## Flujo

Solicitud (local) → aprobación + reserva (supervisor) → picking/packing
(central) → salida → transferencia en tránsito → recepción (local) → stock
actualizado.

El picking/packing es una etapa operativa del SOP, no un estado del ERP:
entre `aprobada` y `despachada` no cambia qué se puede hacer (ADR-020).

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
  responsable si el lote vencido seguía disponible),
  `inventory.conteo_vencido` (reporte a almacén y gerencia de la categoría
  que no se contó en su fecha, RN-INV-021).
- Contrato público de lectura: `application/queries_publicas.py` — hoy
  `unidad_medida_para_magnitud` (nombre y `decimales` de una UdM, para que
  otro módulo exprese una cantidad con su unidad, RN-GER-010). Mismo criterio
  que `sales.queries_publicas`: devuelve dicts, nunca el ORM, y nadie importa
  `inventory.infrastructure` desde afuera.
