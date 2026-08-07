# Máquinas de estado

Ciclo de vida de las entidades con estados. Cada transición puede disparar un
evento ([../architecture/events.md](../architecture/events.md)) y está sujeta a
reglas ([business-rules.md](business-rules.md)). Ninguna transición borra
historia (RN-GEN-002).

## Orden de compra

```mermaid
stateDiagram-v2
    [*] --> borrador
    borrador --> emitida: emitir (RN-CMP-001)
    emitida --> recibida_parcial: recepción parcial
    emitida --> recibida: recepción total
    recibida_parcial --> recibida: completar recepción
    borrador --> anulada
    emitida --> anulada
    recibida_parcial --> anulada
```

Eventos: `purchases.oc_emitida` (→emitida), `purchases.compra_recibida`
(→recibida_parcial/recibida).

## Solicitud de insumos

```mermaid
stateDiagram-v2
    [*] --> pendiente
    pendiente --> aprobada: supervisor aprueba
    pendiente --> rechazada: supervisor rechaza
    pendiente --> cancelada: el local la da de baja (RN-INV-010)
    aprobada --> cancelada: libera las reservas (RN-INV-010)
    aprobada --> despachada: salida (RN-INV-001)
    despachada --> recibida: local recibe
```

`en_picking` **no existe** (ADR-020, cerrado como descartado 2026-08-07):
entre `aprobada` y `despachada` no cambia qué se puede hacer, así que sería
un estado que alguien tiene que marcar a mano sin que gobierne nada.

## Transferencia

```mermaid
stateDiagram-v2
    [*] --> en_transito: salida descuenta origen
    en_transito --> recibida: entrada suma destino (RN-INV-002, RN-INV-003)
```

Evento: `inventory.transferencia_recibida` (→recibida).

`en_transito` es el llamado "Almacén de Transporte": no es una ubicación
física, sino el estado del inventario ya descontado de origen y aún no
ingresado a destino. En este estado se puede asignar transportista y
vehículo, con seguimiento GPS y registro de tiempos de ruta/entrega; los
insumos son inamovibles (no cambian de destino) y deben coincidir
exactamente con la guía de remisión (RN-TRP-001/002).

## Venta

**Alcance (2026-07-14): Venta termina en el envío del pedido a cocina y el
cobro** — RN-COM-005. Los estados de preparación/entrega no son de
`venta`: viven en [Cumplimiento de pedido](#cumplimiento-de-pedido)
(`PROC-OPE-002`), abajo.

```mermaid
stateDiagram-v2
    [*] --> orden: confirmar (RN-COM-001, Orden de Pedido)
    orden --> pagada: pago adelantado (autoatención, RN-POS-005)
    pagada --> facturada: comprobante aceptado por SUNAT (RN-COM-003, recomendado)
    orden --> facturada: comprobante antes de pago (RN-COM-006, no recomendable)
    facturada --> anulada: nota de crédito
    pagada --> anulada
```

Pago y comprobante no siguen un orden único: el pago puede ser adelantado,
y el comprobante puede emitirse antes del pago aunque no es recomendable
(RN-COM-006).

Eventos: `sales.venta_confirmada`, `sales.pago_registrado`,
`sales.comprobante_emitido`, `sales.venta_anulada`.

## Cumplimiento de pedido

`PROC-OPE-002` — no es parte de Venta. **La máquina corre por ítem de
venta**, no por venta: cada ítem lo prepara la estación que le toca, y el
pedido hereda el estado de su ítem más atrasado (RN-CUP-003). Persistida
en `venta_item.estado_preparacion`.

```mermaid
stateDiagram-v2
    [*] --> pendiente: venta confirmada (sales.venta_confirmada)
    pendiente --> en_preparacion: la estación toma el ítem
    en_preparacion --> listo: ítem terminado
    listo --> entregado: entrega al cliente (RN-CUP-005)
```

Secuencial y sin retroceso (RN-CUP-002): no se salta ni se revierte un
estado. Estado del pedido completo = estado del ítem más atrasado; cuando
todos llegan a `listo` se emite `sales.pedido_listo`, y cuando la entrega
se registra, `sales.venta_entregada`.

Lo que **no** es un estado de esta máquina, a propósito:

- **Entrega fallida** (cliente ausente, rechazo) no es un estado del ítem:
  el ítem sigue `listo` y el intento se registra aparte con su motivo
  (RN-CUP-008). Un pedido no entregado no puede quedar indistinguible de
  uno entregado.
- **Devolución** ocurre después de la entrega y se resuelve por nota de
  crédito y merma, no retrocediendo el avance (RN-CUP-010/012).
- **Pago al finalizar** (mesa, RN-POS-005) es una transición de *Venta*
  (`orden → pagada`), habilitada por la entrega del último pedido de la
  atención (RN-CUP-009) — el "servicio terminado" que antes no tenía dueño
  es hoy la salida de este proceso.

## Custodia de efectivo

```mermaid
stateDiagram-v2
    [*] --> en_caja: primera apertura de caja
    en_caja --> en_supervisor: cierre de caja (RN-MDP-002)
    en_supervisor --> en_caja: custodia local en sucursal, siguiente apertura (RN-MDP-006)
    en_supervisor --> en_contabilidad: traslado a oficinas, entrega verificada
    en_contabilidad --> disponible: contabilidad confirma valores
    disponible --> en_caja: apertura de caja (RN-MDP-002)
```

Cada transición exige que el receptor confirme que los valores son
correctos antes de tomar responsabilidad (RN-MDP-002). El ciclo normal es
`en_caja → en_supervisor → (en_contabilidad → disponible | directo) →
en_caja`: tras el cierre, el fondo/caja chica se queda en la sucursal
(custodia local) o viaja a contabilidad, según RN-MDP-006.

## Periodo contable

```mermaid
stateDiagram-v2
    [*] --> abierto
    abierto --> cerrado: cierre (RN-CTB-002)
    cerrado --> [*]
```

> Al dar estados a una entidad nueva: modelar aquí su máquina antes de
> implementar las transiciones.
