# ADR-069 — Mover líneas no repone inventario ni reclasifica el asiento

- **Estado:** aceptada
- **Fecha:** 2026-08-27
- **Contexto:** `sales` (PDV, KDS), `accounting` (asientos automáticos)
- **Relacionado:** [ADR-018](ADR-018-cobro-dividido-mesa-y-descuento-de-orden.md)
  (`grupo_cobro`, mesa tipada — deja escrito que esta decisión se revisaría si
  aparecía la transferencia entre mesas), [ADR-043](ADR-043-orden-abierta-ventana-de-correccion.md)
  (ventana de corrección de una orden ya enviada), [ADR-044](ADR-044-cadena-de-estaciones-del-kds.md)
  (estado de preparación por ítem).

## Contexto

En el PDV pasan dos cosas seguido y ninguna se podía resolver desde el
terminal:

1. Un producto se carga en la mesa o el pedido equivocado — confusión al
   tomar la orden — y hay que corregirlo después de que la comanda ya salió a
   cocina.
2. Un comensal quiere pagar solo lo suyo y dejar el resto de la mesa abierto
   ("dividir la cuenta").

Antes de esta ADR, la única forma de mover un producto era `anular_lineas`
(repone inventario, exige firma de supervisor tras 5 minutos) seguido de
`agregar_lineas` en la otra orden (que vuelve a descontar el insumo y no
conserva el avance de cocina). Para separar la cuenta, `grupo_cobro`
(ADR-018) ya existía en `venta_item`, `pago` y `comprobante`, pero solo se
podía asignar al crear la línea — la selección múltiple del PDV
(mantener presionado un producto) no tenía ninguna acción de servidor detrás.

Las dos necesidades son la misma operación vista desde dos ángulos: reasignar
líneas ya existentes a un destino `(orden, grupo de cobro)`. Mover entre
mesas cambia la orden; separar la cuenta cambia el grupo.

## Decisión

### 1. Un solo caso de uso: `ventas.mover_lineas`

`POST /sales/ventas/{venta_id}/mover-lineas`. Tres formas del mismo destino:

| parámetro | efecto |
|---|---|
| `destino_venta_id` | mueve a otra orden ya abierta (otra mesa, takeout, delivery) |
| `destino_mesa_id` | abre la orden en una mesa libre y mueve ahí |
| solo `grupo_cobro` | misma orden, otra cuenta — "cobrar seleccionados" |

Sin migración: las dos columnas que necesita (`venta_item.venta_id`,
`venta_item.grupo_cobro`) ya existían.

### 2. Solo sobre órdenes ya enviadas, sin PIN de supervisor

Un borrador que el PDV todavía no envió a cocina se corrige localmente
(borrar la línea y volver a tocar el producto); mover no aplica ahí.

A diferencia de `anular_lineas`, mover **no exige autorización de
supervisor**. Anular repone inventario — es plata que sale del almacén sin
que nadie la haya usado, y eso necesita firma (RN-COM-020). Mover no: el
producto sigue existiendo, sigue siendo la responsabilidad de alguna orden
abierta que se va a pagar o a anular, y anular sí pide firma cuando toque. El
rastro de quién movió qué queda en `audit_log` (una entrada por venta
afectada) y en el evento `sales.lineas_movidas`.

### 3. El insumo no vuelve al almacén

`mover_lineas` **no publica ningún evento de `inventory`**. El insumo salió
del almacén cuando la línea se creó (`sales.venta_confirmada`) y sigue
afuera: el plato existe, solo cambió de cuenta. Publicar una reposición y un
consumo lo dejaría en el mismo lugar físico con dos movimientos de más en el
kárdex.

### 4. El estado de KDS viaja con la línea, sin tocarlo

`estado_preparacion` y `etapa_kds` no se modifican al mover. Un plato que ya
está `en_preparacion` sigue `en_preparacion` en la orden destino — no se
vuelve a cocinar, y la cadena de estaciones (ADR-044) sigue su curso normal
para esa fila. `cola_pantalla` filtra por `venta_item.venta_id`
(RN-CUP-003 sigue valiendo: el ítem es la fuente de verdad, la pantalla es un
filtro), así que la tarjeta simplemente cambia de pedido en el siguiente poll.

Consecuencia aceptada: el pedido origen puede volverse entregable (si se le
quitó el último ítem pendiente) o el destino puede "resucitar" (si se le
sumó un ítem pendiente a un pedido ya entregado). `pedido_entregable` se
recalcula sobre los ítems que realmente tiene cada venta después del
traslado — es correcto, no un efecto secundario a corregir.

### 5. Sin asiento de reclasificación

`regla_asiento` mapea una única cuenta debe/haber por (empresa, evento): el
asiento de `sales.venta_confirmada` de la orden origen y el de la orden
destino postean contra las **mismas** cuentas contables. Mover una línea de
una a otra no cambia el mayor, ni el balance, ni el resultado del período —
solo desalinea qué `referencia_origen` "explica" cada asiento.

Se evaluó generar un asiento de reclasificación (debe X / haber X sobre esas
mismas dos cuentas) y se descartó: no mueve ningún saldo, y sí infla el
libro con un movimiento que se cancela contra sí mismo en el instante de
crearse. `crear_asiento_automatico` es además idempotente por
`(empresa, evento, referencia_origen)`, así que ni siquiera permite corregir
el asiento existente sin un camino nuevo que rompa esa garantía.

Queda como deuda documentada (`docs/roadmap/deuda/modulo-sales.md`): un
reporte que cruce "ventas del día" contra "asientos por venta" puede mostrar
un asiento de S/ X en una venta que hoy factura menos, y viceversa, aunque la
suma de la sucursal cuadre siempre.

### 6. Evento nuevo: `sales.lineas_movidas`

Registrado en `docs/architecture/events.md` antes de publicarse. Lo consume
hoy solo `reports` (analítica / auditoría gerencial). `movimiento_id` viaja
desde el día uno para que un consumidor futuro pueda ser idempotente sin
cambiar el contrato.

## Alternativas descartadas

- **Reusar `anular_lineas` + `agregar_lineas`.** Descontaría inventario dos
  veces (una de más) y perdería el avance de cocina — el plato volvería a
  `pendiente` en la orden destino aunque ya estuviera listo.
- **Exigir PIN de supervisor siempre.** Máxima fricción para un caso que
  ocurre varias veces por turno (confusión de mesa al tomar el pedido);
  frena exactamente el caso real, que se detecta recién al pedir la cuenta.
- **Asiento de reclasificación por traslado.** Ver punto 5: no corrige nada
  que estuviera mal, y agrega ruido al libro.
- **Entidad `cuenta_venta` independiente (ADR-018 revisitada).** Seguía sin
  hacer falta: `venta_id` + `grupo_cobro` alcanzan para expresar "otra orden"
  y "otra cuenta" con las columnas que ya existen.

## Consecuencias

- `venta_item.venta_id` y `venta_item.grupo_cobro` dejan de ser inmutables
  tras la creación de la línea; su única vía de cambio autorizada es
  `mover_lineas`.
- El hub offline (ADR-009) **no replica este traslado**: `sincronizacion.py`
  solo tiene verbos para crear, cobrar y anular una venta completa, el mismo
  hueco que ya tenían `agregar_lineas` y `anular_lineas`. Se agrava porque
  los `venta_item.id` no son estables entre el hub y la nube — un traslado
  identificado por esos ids no tiene contra qué reproducirse. Documentado en
  `docs/roadmap/deuda/modo-offline-del-pdv.md`.
- El reporte de asientos por venta puede no cuadrar con el detalle de
  productos de esa venta después de un traslado (punto 5). El total de la
  sucursal sí cuadra siempre.
- RN-COM-018 (cobro dividido) queda enmendada: la selección del PDV ahora
  asigna `grupo_cobro` en tiempo real vía `mover_lineas`, no solo al crear la
  línea. RN-CUP-003 queda enmendada: la línea conserva su `estado_preparacion`
  al cambiar de venta.
