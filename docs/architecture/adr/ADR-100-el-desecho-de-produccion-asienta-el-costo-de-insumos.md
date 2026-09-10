# ADR-100: El desecho de producción asienta contra el costo de insumos, no como merma de `inventory`

## Estado

Aceptado (2026-09-09)

## Contexto

`completar_orden_produccion` con resultado `no_conforme_desechado` registra
`merma_cantidad`/`merma_motivo`/`evidencia_destruccion_url` en la orden
(RN-PRD-014/015), pero nunca disparaba ningún asiento contable: el lote no
conforme se pierde sin que el balance se entere.

La reacción obvia sería reusar `inventory.merma_registrada` (D 6599 / H 201,
`inventory.domain.plantillas`), que ya hace exactamente esto para
mercadería que se desecha. No aplica acá: esa merma opera sobre una
`reserva_stock` de un SKU **que ya está en el almacén** (ADR-028). El
producto terminado de una orden de producción solo ingresa al almacén
cuando `completar_orden_produccion` publica `production.orden_completada`,
y eso **solo ocurre en el caso `conforme`** — un producto desechado nunca
llegó a existir como stock, así que no hay ninguna reserva que apartar ni
desechar.

Lo que sí es una pérdida real y medible es el costo de los insumos que
`registrar_consumo` ya descontó del almacén (`costo_insumos`, calculado al
completar). Ese descuento de stock ya ocurrió en `inventory` — el `SKU` del
insumo bajó de verdad —, pero **nunca tuvo su asiento**: no hay listener de
`production.consumo_registrado` en `accounting` (decisión de
`accounting/domain/plantillas.py`: "el circuito es el de mercaderías […] y
no el de producción […] que el ERP no lleva"). Contablemente, esos insumos
siguen "existiendo" en la cuenta 201 hasta que algo los saque. Cuando la
orden termina `conforme`, ese algo nunca llega — es la misma simplificación
de no llevar el circuito de manufactura completo (21/23/24) — pero cuando
termina desechada, el insumo consumido **de verdad se perdió** y hay una
pérdida real que reportar. Este es el primer punto en el que se le pone
número.

La mano de obra (`costo_mano_obra`) no entra al monto de este asiento: las
horas-hombre de cocina ya se reconocen como gasto de personal por la vía de
planilla (RRHH), independiente de en qué orden trabajó cada quien —
sumarla acá la contaría dos veces.

## Decisión

- Nuevo evento `production.orden_desechada`, publicado únicamente cuando
  `resultado == "no_conforme_desechado"` (además del ya existente
  `production.no_conformidad_detectada`, que sigue yendo a `reports` para
  el escalamiento — este es solo el hecho contable):
  ```
  {orden_produccion_id, almacen_id, articulo_id, merma_cantidad,
   merma_motivo, monto, registrado_por}
  ```
  `monto = costo_insumos` de la orden (ya calculado, valorizado al momento
  del consumo — no se recalcula en `accounting`, mismo criterio que
  `inventory.merma_registrada`/`consumo_personal_valorizado`).
- Nueva plantilla PCGE `production.orden_desechada`: `D 6599 (rol merma) /
  H 201 (rol existencia)`, `monto_es="neto"` — mismas cuentas que la merma
  de `inventory`, mismo circuito de mercaderías, desglosado por la
  categoría del **artículo producido** (no de los insumos: es el producto
  que se declaró no conforme).
- `accounting.application.listeners.on_orden_desechada` sigue el molde de
  `on_merma_registrada`: descarta `monto <= 0`, resuelve la empresa desde
  `almacen_id`, genera el asiento.

## Consecuencias

- El desecho de producción por fin tiene consecuencia contable: la cuenta
  201 baja por el costo de los insumos perdidos, con su contrapartida en
  gasto por merma (6599) — la misma cuenta donde cae cualquier otra merma
  del ERP.
- El reproceso (`no_conforme_reprocesado`) sigue sin generar ni merma ni
  asiento (RN-PRD): el insumo no se perdió, se corrigió, y el detalle de la
  corrección queda en el reporte de escalamiento, no en el libro contable.
- **No se resuelve** el hueco de fondo: `production.consumo_registrado` (el
  caso normal, sin desecho) sigue sin asiento propio, y una orden
  `conforme` no mueve nada de 201/23/21 tampoco. Este ADR no lleva el
  circuito de producción completo — sigue siendo deuda técnica declarada,
  documentada en `docs/roadmap/deuda/modulo-production.md` — solo asienta
  el caso en el que la pérdida es cierta e irreversible.
- El monto excluye mano de obra a propósito: ya se reconoce como gasto de
  planilla, sumarla acá duplicaría el gasto.

## Alternativas consideradas

- **Reusar `inventory.merma_registrada`**: descartada — exige una
  `reserva_stock` sobre un SKU que ya está en el almacén, y el producto
  desechado nunca llegó a estarlo (ver Contexto).
- **Publicar `orden_completada` igual para el desecho, con
  `cantidad_producida=0`**, y dejar que el listener existente de
  `inventory` decida: descartada — `on_orden_completada` está escrito para
  sumar stock, no para no sumar nada; forzarlo a manejar el caso 0
  complica un listener que hoy es simple, para un caso que merece su propio
  evento y su propia plantilla.
- **Asentar contra 23 (Productos en proceso)** en vez de 201: más purista
  (el insumo ya no es materia prima, es trabajo en curso), pero exige llevar
  la cuenta 23 en algún momento anterior — que es exactamente el circuito de
  producción completo que `accounting/domain/plantillas.py` decidió no
  construir. Se pospone hasta que exista esa decisión.
