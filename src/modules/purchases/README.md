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
razón social/RUC propios; `ProveedorOut.persona_id` viaja desde 2026-08-02,
antes un proveedor natural no tenía forma de mostrarse por nombre en un
listado; el jurídico consulta Factiliza —`consultar_ruc`, RENIEC/SUNAT—
para la razón social real en vez de confiar en lo tecleado, mismo criterio
que `sales.crear_cliente`, ver ADR-005; desde 2026-08-12 la pantalla puede
**preguntar antes de guardar** con `GET /consulta/ruc/{n}`, que además
prellena `direccion`/`provincia`/`pais` — ADR-041) y ciclo de OC tipo `insumo`: crear (borrador,
idempotente) → emitir (permiso `purchases.aprobar` exigido si el total
supera el umbral vigente en `parametro_empresa` — `shared`, módulo
`purchases`, código `oc_umbral`; sin fila configurada cae al valor semilla
`purchases_umbral_aprobacion_oc`) → recibir
(total o parcial, nunca más de lo ordenado) → anular (solo antes de
cualquier recepción). Capas `domain/rules.py`,
`infrastructure/repositories.py`, `application/` (`proveedores.py`,
`ordenes.py`), `api/`. Migración `4ff85f833b29` aplicada.

| Método | Ruta | Permiso |
|--------|------|---------|
| POST/GET/PATCH | `/proveedores[/{id}]` | `purchases.crear` / `leer` — ver *Qué se corrige de un proveedor* |
| POST | `/ordenes-compra` | `purchases.crear` |
| GET | `/ordenes-compra` | `purchases.leer` — listado; tenant vía join a `almacen` (la orden no tiene `empresa_id` propio) |
| GET | `/ordenes-compra/{id}` | `purchases.leer` |
| POST | `/ordenes-compra/{id}/emitir` | `purchases.crear` (+ `aprobar` sobre umbral) |

### Qué se corrige de un proveedor (y qué no)

`PATCH /proveedores/{id}` acepta **razón social y RUC** desde el 2026-08-10.
Antes no: un RUC mal tecleado llega hasta la factura electrónica y la única
salida era tocar la base. La corrección **vuelve a consultar SUNAT**, igual
que el alta — corregir el RUC es justo el caso en que lo tecleado estaba mal,
así que reconsultar es el punto del cambio y no un efecto colateral.

Los dos campos valen **solo sobre un proveedor jurídico** (409 si no): en uno
natural el nombre y el documento viven en su `persona` (RN-GEN-007) y se
corrigen desde `PATCH /personas/{id}`. Darle razón social propia a un natural
crearía la segunda fuente que esa regla existe para evitar.

**`tipo` y `persona_id` no son editables.** Cambiarlos convierte al proveedor
en otro y deja sus órdenes de compra apuntando a algo que ya no es; el camino
correcto es darlo de baja y crear el que corresponde.

La condición de pago mantiene su regla del alta: pasar a `credito` sin
`plazo_dias_credito` es 409, porque `accounting` no tendría vencimiento que
calcular. `clasificacion` y `condicion_pago` son `Literal` en el schema — las
columnas son `Enum` con CHECK, así que sin eso un valor inválido moría en el
flush con un 500 en vez de un 422 legible.
| POST | `/ordenes-compra/{id}/recepciones` | `purchases.recepcionar` |
| POST | `/ordenes-compra/{id}/anular` | `purchases.anular` |
| POST | `/ordenes-compra/{id}/conformidad-comprobante` | `purchases.dar_conformidad` |

Eventos: publica `purchases.oc_emitida` y `purchases.compra_recibida`
(inventory suma stock en el almacén destino y recalcula
`articulo.costo_promedio` — promedio ponderado solo contra el stock del
almacén que recibe, ver `ponytail:` en
`inventory/application/listeners.py`), `purchases.oc_anulada` y
`purchases.comprobante_conforme` (2026-07-25 — registra `comprobante`
recibido, transversal en `src/shared/models/`, y dispara en `accounting`
la cola de pago a proveedor, `application/pagos.registrar_pago`). Rol
semilla `comprador` (crear/leer/recepcionar/anular/dar_conformidad).

**`purchases.aprobar` es solo del `admin`** (decisión 2026-08-05). Una OC
sobre el umbral es una decisión de plata: el suplente en ausencia del
titular es *otro administrador*, no el encargado de turno — si no, el
suplente termina siendo quien está más cerca del proveedor. El rol
`supervisor` lo tenía desde el slice inicial y se le retiró. Ojo al
desplegar: el seeder solo agrega permisos, así que en una base ya sembrada
hay que revocarlo a mano (ver ROADMAP → Deuda técnica → Seguridad).

Deuda del slice (ver ROADMAP): `cotizacion` (camino no-preferente sin
modelar — hoy toda OC insumo emite sin cotización comparativa),
OC tipo `activo` + `requerimiento_activo` con doble aprobación,
`compra_directa` + `caja_chica_compras`/`caja_chica_movimiento` +
`rendicion_caja_chica` (compra a proveedor informal), `evaluacion_proveedor`
automática por recepción, listener de `inventory.devolucion_a_proveedor`.
La OC no queda marcada como "pagada" tras el pago (RN-CMP-014 vive del
lado de `accounting`, `orden_compra.estado` no tiene ese valor todavía).

## Dirección del proveedor anclada al mapa (2026-08-22, ADR-053)

`proveedor` lleva el `UbicacionMixin` de `core/model_base`. Convive con
`BuscarDocumento`: lo que llega de SUNAT sigue prellenando el texto —que es el
domicilio **declarado**, no siempre el almacén al que uno va a recoger— y
después se puede anclar en el mapa. Corregir el texto a mano suelta el punto
(`shared/ubicacion.py`).

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
  (umbral por empresa en `parametro_empresa`, con fallback al valor semilla
  de config — ver `docs/architecture/data-model.md` §8c).
- OC tipo `activo` requiere `requerimiento_activo.aprobado_area = true` y
  `requerimiento_activo.aprobado_gerencia = true` antes de permitir emisión
  — bloqueo a nivel de dominio, no solo de UI.
- `compra_directa` exige comprobante adjunto antes de guardarse; sin
  comprobante no se persiste.
- `purchases` **no ejecuta pagos** — solo registra el `comprobante`
  recibido como conforme (`purchases.dar_conformidad`, exige OC con
  recepción registrada) y lo entrega (evento `purchases.comprobante_conforme`)
  a `accounting`, que decide y ejecuta el pago según la condición de la
  ficha del proveedor (RN-CMP-014).
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
- Consume el contrato público de lectura de `inventory`:
  `queries_publicas.solicitudes_resumen_para_negociacion`
  (`GET /api/v1/inventory/solicitudes/resumen`, permiso
  `inventory.leer_solicitudes_externas`, sembrado en el rol `comprador`) —
  qué artículo pide más cada sucursal, para negociar volumen con
  proveedores. Mismo patrón que `sales.cliente` (ver
  `docs/architecture/events.md`).
