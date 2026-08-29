# ADR-082 — La compra directa reutiliza `orden_compra`, no es un modelo nuevo

- Estado: aceptado
- Fecha: 2026-08-29
- Contexto: módulo `purchases`, deuda del slice (compra sin OC previa)
- Relacionado: `src/modules/purchases/README.md`, `docs/architecture/events.md`

## Contexto

Hoy la única forma de sustentar una compra con un `Comprobante` es
`dar_conformidad_comprobante`, que exige una `OrdenCompra` ya en estado
`recibida`/`recibida_parcial`. No hay ningún camino para registrar una
compra a un proveedor informal cuando lo único que existe es la factura
que llegó — el flujo real de compras chicas del día a día (mercado,
ferretería, imprevistos). El README del slice ya reconocía esta deuda.

## Decisión

`registrar_compra_directa` crea una `OrdenCompra` normal con
`origen="directa"` (columna nueva, default `"oc"`), la lleva directo a
`emitida` (sin pasar por `emitir_orden_compra` ni el umbral de
aprobación — es gasto ya incurrido, no un compromiso futuro), y
encadena `recibir_orden_compra()` + `dar_conformidad_comprobante()`
reusados **tal cual**.

Se descartó modelar `CompraDirecta` como entidad separada porque:

- El evento `purchases.compra_recibida` sale con el mismo contrato que ya
  consumen `inventory` (entra stock) y `accounting` (asienta la compra) —
  cero cambios en esos dos listeners.
- `dar_conformidad_comprobante` ya acepta cualquier OC en `recibida`, así
  que el pago programado en `accounting` sale por el mismo camino que
  cualquier OC normal, sin código nuevo en ese módulo.
- Una entidad aparte hubiera obligado a duplicar `Item`/`Recepción` y a
  registrar una segunda suscripción idéntica en dos módulos — el mismo
  hecho de dominio (una compra que entró a almacén) modelado dos veces.

## Consecuencias

- Las pantallas de OC listan compras directas junto con las normales;
  donde importa distinguirlas se filtra por `origen`. Es correcto: la
  "compra" del dominio es la OC ya recibida (ver comentario en
  `application/queries_publicas.py`), con o sin borrador/emisión previos.
- El pago de una compra directa sigue el camino normal de cuentas por
  pagar (`accounting.pagos.registrar_pago`) — **no** pasa por
  `caja_chica_movimiento`, porque ese modelo no existe todavía. Sigue
  como deuda separada en `purchases/README.md`.
- Una compra directa nunca pasa por el umbral de aprobación de
  `purchases.aprobar`: si en el futuro se necesita aprobar gasto
  informal por monto, es una regla nueva sobre este mismo camino, no un
  cambio de modelo.

## Alternativas descartadas

- **Modelo `CompraDirecta` aparte.** Descartado arriba — duplica
  contrato de eventos y listeners por una entidad que en los hechos es
  una OC que nace recibida.
- **Forzar siempre una OC en borrador antes de recibir.** No resuelve el
  caso real: la factura ya llegó y la compra ya ocurrió: no hay nada que
  "pedir" de antemano.
