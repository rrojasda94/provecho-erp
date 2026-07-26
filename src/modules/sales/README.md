# Módulo `sales` — Ventas y PDV

## Objetivo

Registrar ventas por sucursal en todos los canales (PDV humano, agente de IA,
delivery), cobrar (efectivo / Izipay) y emitir comprobantes
electrónicos vía **Factiliza** (proveedor elegido 2026-07-26, reemplaza a
Nubefact).

## Entidades

`producto_comercial`, `receta`, `receta_item`, `lista_precio`, `venta`,
`venta_item`, `pago`, `comprobante`, `cliente`. Detalle en `docs/architecture/data-model.md` §3, §6.

**Estado de implementación (2026-07-20):** modelado el núcleo del slice
Venta — `cliente`, `punto_venta`, `producto_comercial`, `venta`,
`venta_item` (`src/modules/sales/infrastructure/models/`). `venta_item`
guarda su propio `precio_unitario` (snapshot), por eso no depende de
`lista_precio`/`precio` para existir. `venta.estado` implementado con el
enum vigente (`orden`|`pagada`|`facturada`|`anulada`, RN-COM-005) — no
el enum viejo de 8 estados. `venta.numero_orden` (RN-COM-014) es el
correlativo por sucursal+día que ve el personal; `cliente.usuario_id`
(RN-COM-015) es la cuenta web opcional, nunca requerida en sucursal/
Central de Pedidos.

**Cobro (PROC-COM-002, mismo día):** `medio_pago` (catálogo por
empresa), `pago` (RN-COM-002/016 — una venta admite varios `pago`, pago
dividido confirmado como caso real; suma de montos debe igualar
`venta.total`). `comprobante` vive en `shared` (transversal a sales/
purchases/accounting, no en este módulo). `punto_venta.serie_boleta`/
`serie_factura` (series SUNAT separadas) alimentan el `comprobante.serie`
al emitir.

Diferido a un slice posterior: `modificador`, `variante_producto`,
`combo`, `lista_precio`, `precio`, `promocion`, `carrito`,
`central_pedidos`, `cuenta_puntos`/`puntos_movimiento`,
`carta_disputa_pago`.

## Estado (slice PDV implementado 2026-07-25)

Operativo en `/api/v1/sales`: crear venta (= confirmar orden, con
correlativo por sucursal+día e idempotencia), cobrar (pagos parciales;
al cubrir el total → `pagada`), anular orden no pagada (repone stock),
CRUD de productos comerciales y medios de pago. Capas `domain/rules.py`,
`infrastructure/repositories.py`, `application/` (`ventas.py`,
`catalogo.py`), `api/`. Sin migración — esquema ya existía.

| Método | Ruta | Permiso |
|--------|------|---------|
| POST | `/ventas` | `sales.crear` |
| GET | `/ventas/{id}` | `sales.leer` |
| POST | `/ventas/{id}/pagos` | `sales.cobrar` |
| POST | `/ventas/{id}/anular` | `sales.anular` |
| POST/GET/PATCH | `/productos[/{id}]` | `gestionar_catalogo` / `leer` |
| POST/GET | `/medios-pago` | `gestionar_catalogo` / `leer` |
| GET | `/clientes?grupo_id=` | `sales.leer_clientes_externos` |

**Kiosk y Central de Pedidos NO son módulos**: son clientes del mismo
contrato `POST /ventas` (`punto_venta.canal = kiosko|web|trabajador`),
igual que agente_ia. El carrito vive en el cliente, no en el servidor.

Eventos: publica `sales.venta_confirmada` (inventory descuenta insumos
por receta + merma % + empaque según modalidad), `sales.venta_pagada`,
`sales.venta_anulada` (inventory repone).

**Contrato público de lectura** (`application/queries_publicas.py`,
primero de este tipo en el repo — ver
`docs/architecture/events.md#eventos-vs-contratos-públicos-de-lectura`):
`listar_clientes_para_analisis` expone `cliente` (join con `persona` si es
natural) para que `marketing`/`comercial` lo consuman sin importar el
dominio de `sales` — hoy vía `GET /clientes`, mañana vía import directo de
la función cuando `marketing` exista como módulo.

Deuda del slice (ver ROADMAP): precio server-side vía `lista_precio`
(hoy el PDV manda `precio_unitario`), nota de crédito post-pago, webhook
de pasarela (pago nace `confirmado`), apertura/cierre de caja enlazados a
la venta.

## Facturación electrónica (implementado 2026-07-26)

Adaptador: `src/shared/integrations/factiliza/` — `client.py` (HTTP,
`POST /invoice/send`) y `mapper.py` (traducción a catálogos SUNAT). El
dominio nunca llama a la API.

**Flujo.** Al cubrirse el total de la venta, `registrar_pago` crea el
`comprobante` en estado `pendiente` dentro de la misma transacción; el
router encola el envío **después del commit** (el worker es otro proceso y
solo puede ver filas confirmadas). La tarea Celery
`sales.emitir_comprobante` envía a Factiliza y persiste el veredicto.

- **Aceptado** → `estado_emision=aceptado`, se guarda el `hash`, la venta
  pasa a `facturada` y se publica `sales.comprobante_emitido`.
- **Rechazado por SUNAT** → `rechazado` + motivo en `detalle_emision`. No
  reintenta: es un veredicto sobre los datos, no un fallo de transporte.
- **Factiliza no responde** → `FactilizaError`; la cola reintenta con
  espera creciente (1, 2, 4, 8 min) hasta `MAX_INTENTOS_EMISION`. La caja
  nunca se bloquea (RN-COM-003).

**Boleta vs factura** (`rules.tipo_comprobante`): factura solo si el
cliente es jurídico y tiene RUC; en todo otro caso boleta, incluido el
cliente anónimo (RN-PER-005 — `CLIENTES VARIOS`, doc. tipo `0`). La serie
sale de `punto_venta.serie_boleta`/`serie_factura` y se congela en el
comprobante; el correlativo es max+1 por (empresa, serie), con el UNIQUE
cortando la carrera.

**IGV.** Los precios de carta incluyen IGV: el mapper desglosa hacia atrás
(S/118 = S/100 de valor + S/18). Si la empresa es de zona
`amazonia_ley27037` la venta sale **exonerada** (afectación `20`,
`monto_Oper_Exoneradas`, IGV cero) — RN-IMP-001, el caso real de Majambo
en Tarapoto. El régimen lo declara la empresa, no la venta.

**Sin `FACTILIZA_TOKEN` la emisión queda desactivada**: se venden y cobran
igual, y los comprobantes se acumulan `pendiente` para enviarlos cuando la
credencial exista.

| Método | Ruta | Permiso |
|--------|------|---------|
| GET | `/ventas/{id}/comprobante` | `sales.leer` |
| POST | `/comprobantes/{id}/reintentar` | `sales.emitir_comprobante` |

Diferido: nota de crédito (`/note/send`), descarga de PDF/XML/CDR,
guía de remisión (`/despatch-*`), consulta de estado en SUNAT.

## KDS (implementado 2026-07-25)

Pantallas de cocina configurables por sucursal en `/api/v1/kds`. El
avance vive en `venta_item.estado_preparacion`
(`pendiente → en_preparacion → listo → entregado`, sin retroceso) —
fuente única: toda pantalla lee el mismo estado, por eso el avance
mostrado siempre es el real. El frontend refresca por polling; push en
tiempo real (Redis/WebSocket) es deuda declarada.

- **`kds_pantalla`**: sucursal + tipo (`preparacion` | `despacho`) +
  `categoria_ids` (filtro por categorías de producto comercial; vacío =
  todas). `producto_comercial.categoria_id` (nuevo, reusa `categoria`)
  rutea cada ítem a su estación (pizzas → horno, bebidas → barra).
- **Preparación**: ve ítems pendientes/en curso de sus categorías; bump
  por ítem (`POST /kds/items/{id}/avanzar`).
- **Despacho**: ve pedidos con ítems listos + `estado_pedido` agregado
  (el ítem más atrasado manda); al estar todo listo se publica
  `sales.pedido_listo`; marca entrega y el pedido sale de las colas.
- **Comanda**: `POST /kds/ventas/{id}/comanda` → texto plano 32 cols
  (térmica 58 mm) + contador `comanda_impresa_veces` (reimpresión
  marcada y auditable).
- **`venta.referencia_atencion`** ("Mesa 5", "Carlos", "Rappi #1042"):
  texto libre que el PDV envía al crear la venta — visible en toda
  tarjeta KDS y en la comanda, para aclarar de quién es el pedido sin
  exigir cliente registrado (RN-PER-005 sigue: cliente anónimo válido).

| Método | Ruta | Permiso |
|--------|------|---------|
| POST/PATCH | `/kds/pantallas[/{id}]` | `kds.configurar` |
| GET | `/kds/pantallas` \| `/{id}/cola` | `kds.operar` |
| POST | `/kds/items/{id}/avanzar` | `kds.operar` |
| GET | `/kds/ventas/{id}/avance` | `kds.operar` |
| POST | `/kds/ventas/{id}/comanda` | `kds.operar` |

Roles seed: `cocinero` (kds.operar), cajero también opera; supervisor
configura.

## Casos de uso

- CRUD de productos comerciales y recetas (separados de artículos inventariables).
- Crear venta (carrito) → confirmar → cobrar → emitir comprobante.
- Venta por agente de IA: mismo contrato API, usuario tipo `agente_ia`.
- Anulación / nota de crédito (con permiso y auditoría).
- Precios por sucursal/canal mediante listas de precio.
- `lista_precio` con flag `es_promocional` + `vigencia_inicio`/`vigencia_fin`:
  al vencer, el precio regular se restaura automáticamente sin intervención
  manual (soporta el flujo de Comercial de ofertas/promociones con fin
  obligatorio).
- Cálculo de margen de contribución por producto (`precio - costo_variable`,
  donde `costo_variable` = costo de receta vía `inventory` + empaque +
  comisión de canal) expuesto a Comercial para su evaluación de precio —
  el módulo calcula, Comercial decide y aprueba el precio final.

## Reglas

- Confirmar venta exige stock suficiente de los insumos de la receta (o política
  configurable de venta sin stock, por definir).
- `idempotency_key` obligatoria al confirmar venta y al registrar pago.
- Comprobante se encola a Factiliza (worker Celery, reintentos); la venta no se
  bloquea por caída del proveedor.
- El PDV usa el branding de la marca de la sucursal (config del módulo de ajustes).
- Cambio de precio regular pasa por `lista_precio` nueva versión, nunca
  edición directa del precio vigente (auditable, igual que OC en
  `purchases`); ligado a la ficha de evaluación de margen de Comercial.

## Flujo

Producto comercial → receta → confirmar venta → evento `sales.venta_confirmada`
→ inventory descuenta insumos del almacén del local → pago → comprobante.

## Relaciones

- Publica: `sales.venta_confirmada`, `sales.venta_anulada`, `sales.pago_registrado`,
  `sales.comprobante_emitido` (comprobante aceptado por SUNAT vía Factiliza),
  `sales.carrito_abandonado` (analítica de embudo, RN-COM-013).
- Escucha: nada (consulta stock vía contrato público de inventory).
- Integraciones: Factiliza (facturación electrónica), Izipay, Meta API (pedidos por WhatsApp).
