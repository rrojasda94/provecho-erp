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

**Precio server-side (2026-07-27):** `lista_precio` + `precio` (migración
`d4b1f0a7c3e9`). El PDV ya no manda el monto — ver sección propia abajo.

**Slice PDV (2026-07-28, migración `d7e3b8c14f52`, ADR-018):** cierra los
cuatro huecos que el punto de venta necesitaba y el modelo no daba.

- `mesa` (`sucursal_id`, `numero` único por sucursal, `zona`, `capacidad`,
  `activa`) + `venta.mesa_id` / `venta.comensales`. La mesa **no guarda
  ocupación**: está ocupada si tiene una venta en `orden`. El mapa
  (`GET /sales/mesas/mapa`) es lectura derivada.
  `venta.referencia_atencion` **se conserva** como texto libre para
  takeout/delivery ("Carlos", "Rappi #1042").
- `grupo_cobro` (entero, default 1) en `venta_item`, `pago` y
  `comprobante` (RN-COM-018): una orden se divide en cuentas, cada una con
  sus pagos y **su propio comprobante**. La venta pasa a `pagada` recién
  cuando ninguna cuenta queda con saldo.
- `comprobante.receptor_num_doc` / `receptor_nombre` (RN-CPP-003): el
  DNI/RUC que el cajero teclea al cobrar, sin exigir cliente registrado.
  11 dígitos → factura; 8, `00000000` o vacío → boleta.
- Descuento manual de orden en `venta` (`descuento_modo`,
  `descuento_valor`, `descuento_motivo`, `descuento_autorizado_por`,
  RN-COM-017), con permiso propio `sales.aplicar_descuento` (supervisor,
  no cajero). Se prorratea entre grupos de cobro.
- **Cliente identificado por teléfono** (migración `e1c4a9d6b038`):
  `persona.numero_documento`/`tipo_documento` pasan a nullable. Registrar a
  una persona natural exige **teléfono**, no DNI (RN-PTS-004) — el
  documento se completa después con
  `PATCH /sales/clientes/{id}/documento`. Para facturar a una empresa el
  **RUC sigue siendo obligatorio**. Sin documento (o con `00000000`) el
  cliente **no cuenta como identificado** y queda fuera de las promociones
  para clientes registrados (RN-PTS-005) — regla derivada
  `rules.cliente_identificado`, no una columna. Búsqueda de caja por
  teléfono, documento o nombre en `GET /sales/clientes/buscar?q=`
  (RN-PTS-006). **Trabajador y usuario siguen exigiendo documento**: esa
  validación vive en `users.application.admin`, no en el esquema.
- **Nombre/razón social vía Factiliza en alta nueva** (2026-08-02):
  documento (DNI/RUC) que la persona todavía no tiene registrado consulta
  `FactilizaClient.consultar_dni`/`consultar_ruc` (RENIEC/SUNAT,
  `src/shared/integrations/factiliza/`) para el nombre real, en vez de
  confiar en lo tecleado en caja. Documento ya visto no vuelve a consultar.
  Sin respuesta de Factiliza (o no encontrado) cae a lo tecleado — el alta
  nunca se bloquea.

**Cierre para alfa (2026-07-28, migraciones `f2a8c15e94d7` y `b6d41e07af92`):**

- **Extras** (RN-COM-021): un extra **es** un `producto_comercial` con
  `es_extra=True` y su propia receta, que se ejecuta en la sucursal y se
  suma a la del producto al agregarse. Modelarlo así le da gratis precio
  server-side por lista, aparición en la carta y descuento de insumos por
  el mismo evento. Lo propio es `producto_comercial_extra` (qué producto
  admite qué extra, con tope) y `venta_item.padre_venta_item_id` (de qué
  línea cuelga). Hereda el grupo de cobro del padre y su consumo se
  multiplica por el plato.
- **Anular líneas enviadas** (RN-COM-020):
  `POST /ventas/{id}/anular-lineas`, con autorización de supervisor y
  motivo; publica `sales.lineas_anuladas` → inventory repone. Quitar todas
  anula la orden. Antes de enviar, el pedido vive en el PDV y no pasa
  por acá.
- **Precuenta** (RN-COM-019): `GET /ventas/{id}/precuenta`, documento **no
  fiscal**, opcionalmente por cuenta. No cambia el estado ni se audita.
- **Autorización de supervisor** (RN-AUD-005): `POST /auth/autorizar`
  (módulo `users`) verifica PIN + permiso y devuelve una elevación de 3
  minutos acotada a esa acción. Descuento y anulación de líneas la exigen;
  `autorizado_por` sale de ahí, nunca del cuerpo del request.

Diferido a un slice posterior: `variante_producto`, `combo`, `promocion`,
`carrito`, `central_pedidos`, `cuenta_puntos`/`puntos_movimiento`,
`carta_disputa_pago`.

> **Descuento ≠ promoción.** `venta.descuento_*` es un acto humano
> autorizado, con motivo y responsable. Las **promociones** se definen por
> marca/sucursal, son condicionales y automáticas (ej. segunda pizza a
> mitad de precio si el cliente pide dos del mismo tamaño, en días
> vigentes, sobre el precio base de la más barata y sin extras) y exigen un
> motor de reglas que **todavía no existe**. Quien lo construya no debe
> reutilizar estos campos: mezclarlos haría imposible auditar cuál
> descuento fue humano y cuál automático. Ver ADR-018 y `ROADMAP.md`.

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
la función cuando `marketing` exista como módulo. Ampliado 2026-07-26
(ADR-012) con tres funciones más, consumidas por `core.dashboard_router` y
por `accounting` (reconciliación de cierre de caja): `resumen_ventas_del_dia`
(cantidad+total del día), `total_efectivo_cobrado` (pagos en efectivo
confirmados de un punto de venta desde una fecha) y `puntos_venta_de_empresa`
(IDs de `punto_venta` de una empresa — `accounting` no importa `PuntoVenta`
directo, no es organización transversal como `Persona`/`Sucursal`).

Deuda del slice (ver ROADMAP): nota de crédito post-pago, webhook de
pasarela (pago nace `confirmado`), apertura/cierre de caja enlazados a la
venta.

## Precio server-side (implementado 2026-07-27)

RN-PRC-003: en PDV, kiosko y web el precio es fijo e innegociable. Antes
el request traía `precio_unitario` y el servidor lo aceptaba: cualquier
cliente podía fijar el monto a cobrar. Ahora `VentaItemIn` solo lleva
producto y cantidad, y `crear_venta` resuelve el precio contra
`lista_precio`.

- **`lista_precio`**: marca + ámbito opcional (`sucursal_id`, `canal`,
  `modalidad` — NULL = aplica a todas, RN-MDC-003), `es_promocional`,
  `vigente_desde`/`vigente_hasta`, `activa`.
- **`precio`**: monto de un producto dentro de una lista. Único por
  (lista, producto) y **sin endpoint de edición**: corregir un precio es
  una lista nueva, para que el histórico quede auditable (RN-PRC-005),
  igual que una OC en `purchases`.
- **Resolución** (`domain/rules.elegir_lista_precio`, función pura): de
  las listas vigentes y de ámbito compatible gana la promocional; a
  igualdad, la más específica; luego la de vigencia más reciente. Al
  vencer la promoción el precio regular vuelve solo — no hay nada que
  revertir a mano.
- **Sin precio vigente no hay venta**: `PrecioNoDefinido` → 409. Un
  producto sin precio tampoco aparece en la carta.
- **Descuentos**: salen de listas promocionales, no del cliente; hoy el
  ítem nace en 0.

| Método | Ruta | Permiso |
|--------|------|---------|
| POST/GET | `/listas-precio` | `gestionar_catalogo` / `leer` |
| POST | `/listas-precio/{id}/precios` | `gestionar_catalogo` |
| GET | `/carta?sucursal_id&canal&modalidad` | `sales.leer` |

`GET /carta` es lo que el PDV/kiosko renderiza: catálogo vendible con el
precio ya resuelto, en vez de que el cliente traiga uno propio.

**Excepción del replay offline (ADR-009)**: el lote que empuja el hub usa
`VentaItemSyncIn`, que **sí** lleva `precio_unitario`. Una venta ya
cobrada conserva el precio al que se cobró; recotizarla en la nube
cambiaría el monto si la promoción venció entre el corte y la
sincronización.

**Pendiente para el modo offline del PDV** (ADR-009, ver
`docs/architecture/adr/ADR-009-modo-offline-pdv.md`): `crear_venta`/
`registrar_pago` necesitan aceptar un `id: uuid.UUID | None` opcional para
que el hub local de sucursal y la nube compartan el mismo UUID al
sincronizar, sin tabla de mapeo. Ya es posible sin migración —
`UuidPkMixin` genera el UUID en Python al construir el objeto, no en la
base— falta solo el parámetro. No implementado todavía.

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

## Cumplimiento de pedido — KDS y entrega (implementado 2026-07-25/27)

Implementa `PROC-OPE-002` ([workflows.md](../../../docs/domain/workflows.md#cumplimiento-de-pedido),
RN-CUP-001..012). El área dueña del proceso es Operaciones; el código vive
en `sales` porque el avance se persiste en `venta_item` — el área de
negocio no obliga a crear un módulo nuevo.

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
  `sales.pedido_listo`.
- **Entrega**: `POST /sales/ventas/{id}/entrega` cierra el pedido completo
  y publica `sales.venta_entregada` (disparador de la encuesta de
  marketing, RN-COM-007). Exige todos los ítems en `listo` (RN-CUP-005),
  permiso propio distinto del de cocina (RN-CUP-006) y es idempotente:
  repetirla no reemite el evento. Por eso el bump del KDS **no** llega a
  `entregado` — devuelve 409 apuntando a este endpoint.
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
| POST | `/sales/ventas/{id}/entrega` | `sales.entregar_pedido` |

Roles seed: `cocinero` (kds.operar, **no** entrega), `despachador`
(kds.operar + entrega), cajero opera y entrega; supervisor configura.

## Sincronización con el hub de sucursal (implementado 2026-07-27)

`application/sincronizacion.py` declara el contrato de este módulo con el
hub local de cada sucursal (ADR-009 fase 2). Es la única parte de `sales`
que sabe del modo offline; el motor vive en `core/sync` y no conoce
ninguna entidad de negocio.

- **Hacia el hub** (`RECURSOS`): `producto_comercial`, `medio_pago`,
  `punto_venta`, `kds_pantalla` — la carta del local, sus medios de cobro,
  sus cajas y sus pantallas de cocina, filtrados por la marca/sucursal del
  hub.
- **Hacia la nube** (`pendientes` / `aplicar`): las ventas, cobros y
  anulaciones que ocurrieron durante el corte se reproducen **por los
  mismos casos de uso** (`crear_venta`, `registrar_pago`, `anular_venta`),
  conservando `id`, `idempotency_key`, `fecha_orden`, `numero_orden` y
  quién vendió. Un commit por ítem: una venta que la nube rechaza no
  arrastra al resto del lote.
- El hub **no** empuja movimientos de inventario: los genera el listener de
  la nube al recibir la venta (empujarlos duplicaría el consumo).
- `tasks.encolar` es no-op en un hub — la emisión a SUNAT es siempre de la
  nube, después del sync.

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
  `sales.descuento_aplicado` (RN-COM-017 — alimenta el reporte de
  descuentos), `sales.lineas_anuladas` (RN-COM-020 — inventory repone lo
  que ya no se prepara), `sales.carrito_abandonado` (analítica de embudo,
  RN-COM-013).
- Escucha: nada (consulta stock vía contrato público de inventory).
- Integraciones: Factiliza (facturación electrónica), Izipay, Meta API (pedidos por WhatsApp).
