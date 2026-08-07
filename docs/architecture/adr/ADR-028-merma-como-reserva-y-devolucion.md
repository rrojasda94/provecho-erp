# ADR-028 — La merma es una reserva, no una tabla; y qué es una devolución

- **Fecha:** 2026-08-06
- **Estado:** Aceptada
- **Contexto:** cierre de la deuda "slices grandes" del módulo `inventory`
  (`stock_merma`, `devolucion`) — ver ROADMAP → Deuda técnica.

## Contexto

`docs/architecture/data-model.md` venía anticipando dos entidades desde el
modelado inicial:

- **`stock_merma`**, descrita como "subtipo de stock reservado".
- **`devolucion`**, con origen (`proveedor` | `sucursal` | `cliente`),
  motivo, destino e ítems.

Entre medio se construyó `reserva_stock` (ADR-020), que ya tenía `tipo`
con el valor `merma` y un `motivo` (`devolucion` | `rechazo_sucursal` |
`auditoria`) esperando productor, y `transferencia`, genérica por almacén
de origen y destino.

## Decisión

### 1. No hay tabla `stock_merma`. La merma es una `reserva_stock`.

Lo que RN-INV-012 pide —"stock no apto para la actividad económica,
pendiente de auditoría y desecho"— es exactamente lo que una reserva ya
significa: **está físicamente ahí y no se puede comprometer**. El
disponible es `físico − Σ reservas activas`, así que apartar merma como
reserva la saca de la venta sin más código.

Una tabla aparte habría duplicado almacén, SKU, cantidad y estado para
decir lo mismo, y —peor— habría obligado a **restar dos cosas distintas**
al calcular el disponible. Dos restas es una que alguien se olvida.

Lo único que le faltaba a `reserva_stock` era `lote_id`: la merma **es** un
lote concreto —lo vencido o dañado no es "algo de ese SKU"— y el desecho
tiene que sacar ese y no el que FEFO elegiría, que puede ser justamente el
bueno. Esa columna es toda la migración.

### 2. La merma tiene dos pasos, y eso es la regla.

`registrar` aparta; `resolver` decide (RN-INV-019). No se fusionan en uno:

- **Registrar no descuenta stock.** El producto sigue en el estante hasta
  que alguien lo tire, y el conteo cíclico lo va a encontrar. Descontarlo
  al apartarlo haría que el conteo lo declarara sobrante al día siguiente.
- **El asiento va al desechar, no al registrar.** Mientras la auditoría no
  decide, no hay pérdida: `reintegro` devuelve la mercadería a disponible.
  Asentar antes obligaría a reversar la mitad de los asientos.
- **Lo resuelve otro usuario** (`aprobar_ajuste`, no `solicitar_ajuste`):
  quien declara que algo no sirve no firma su baja. Es la misma segregación
  del ajuste y usa los mismos permisos — un permiso nuevo para la misma
  idea sería una segunda matriz que mantener.

El estado `pendiente_desecho` del enum **queda sin uso**, a propósito:
separar "autorizado para destruir" de "destruido" exige la evidencia en
video que pide RN-PRD-015, y eso es un slice con su propio adjunto, no un
estado suelto.

### 3. `devolucion` cubre proveedor y cliente. Sucursal→central no.

La devolución **sucursal → central sigue siendo una transferencia**: tiene
despacho, tránsito, recepción y diferencias registradas, que es
literalmente lo que ADR-020 ya construyó. Modelarla otra vez sería un
segundo camino para el mismo movimiento de stock y dos lugares donde el
número puede quedar distinto.

Lo que no tenía camino, y por eso existe la entidad:

- **A proveedor**: la mercadería **sale**. Se descuenta tomando el lote
  declarado (obligatorio si el artículo controla lote: el reclamo tiene que
  decir qué se rechaza) y se publica `inventory.devolucion_a_proveedor`
  para que `purchases` gestione el reclamo o la nota de crédito.
- **De cliente**: la mercadería **entra**, y `destino` decide qué pasa:
  `reintegro` la suma a disponible; `desecho` y `auditoria` la ingresan y
  **acto seguido la apartan como merma** — está en el almacén pero no puede
  venderse, y sin ese segundo paso la próxima venta se la lleva.

`reporte_dirigido_a` se **deriva** del origen (almacén si devolvemos,
comercial si nos devuelven — RN-INV-020) y se guarda en la fila: el reporte
es del momento, no del criterio de hoy.

`anular` repone con movimientos contrarios y suelta las mermas que la
devolución había apartado. No borra la fila: que alguien se equivocó
también es parte del rastro.

### 4. La guía de remisión gana un segundo emisor.

`guia_remision.transferencia_id` pasa a nullable y aparece `devolucion_id`.
Una devolución a proveedor viaja por la vía pública igual que un traslado y
**SUNAT no distingue el motivo** para exigir la guía. Motivo de traslado
`13` (otros) y no `04`: `04` es "entre establecimientos de la misma
empresa", y declarar eso cuando el destino es otro contribuyente sería
declarar algo falso.

El `lugar_destino` se teclea. `proveedor` no tiene dirección modelada, y
esto cae en la misma categoría que el chofer y la placa: lo que el sistema
no puede saber. El RUC del receptor sí sale del proveedor, por el contrato
público `purchases::proveedor_para_guia`.

## Consecuencias

- El modelo de datos documentaba `stock_merma` como entidad; queda
  registrado que **no se implementa** y por qué. Cualquier lectura futura
  del data-model tiene que llegar acá.
- `reserva_stock` pasa a tener dos productores reales (`solicitud` y
  `merma`). Siguen sin productor `produccion` y `carrito`, y eso no es
  deuda de `inventory`: construirle un productor a un tipo cuyo caso de uso
  no existe es inventar el caso de uso.
- `inventory.merma_registrada` gana consumidor en `accounting` (asiento por
  `regla_asiento`, valorizado al `costo_promedio` por el emisor).
- `inventory.devolucion_a_proveedor` se publica pero **`purchases` todavía
  no lo consume**: el reclamo y la nota de crédito al proveedor son deuda
  declarada de ese módulo, no de este.
- La devolución de cliente **no cruza con `sales`**: no toca la venta ni
  emite nota de crédito. Eso ya existe por su lado (RN-CPP-009) y unirlos
  exigiría decidir si la nota de crédito dispara la devolución o al revés
  — una decisión que no hace falta tomar hoy.

## Alternativas descartadas

- **Tabla `stock_merma` como el data-model anticipaba.** Duplica
  `reserva_stock` y parte el cálculo del disponible en dos restas.
- **Merma en un solo paso (registrar y desechar juntos).** Perdería el
  estado "pendiente de auditoría" que RN-INV-012 pide explícitamente, y
  haría imposible el `reintegro`.
- **Modelar la devolución sucursal→central acá.** Ver punto 3: sería un
  segundo camino para lo que `transferencia` ya hace completo.
- **Derivar `lugar_destino` de una dirección del proveedor.** Exigiría una
  columna nueva en `proveedor` que alguien tiene que llenar antes de poder
  devolver nada — mismo criterio que llevó a no crear `vehiculo` (ADR-027).
