# ADR-094 — La reposición vuelve al lote del que salió

- Estado: aceptado
- Fecha: 2026-09-06
- Contexto: `src/modules/inventory/application/listeners.py`
- Relacionado: ADR-015 (lote y FEFO), RN-LOT-001..005

## Contexto

`on_venta_anulada` (y las dos rutas que comparten el mismo handler:
`lineas_anuladas`, `nota_credito_emitida`) repone stock llamando
`stock_uc.registrar_movimiento` sin `lote_id`. Sin `lote_id` explícito, un
ingreso a un artículo con control de lote entra al **lote del día**
(`stock.py::registrar_movimiento`) — no al lote del que la venta lo sacó.

El propio código lo tenía anotado desde que se escribió:

```python
# ponytail: la reposición por anulación entra al lote del día, no al lote
# del que salió — el movimiento original no viaja en el evento.
```

El diagnóstico estaba equivocado en una cosa: el movimiento original **no
necesitaba viajar en el evento**. `movimiento_inventario.referencia` ya
guarda el `venta_id` desde el primer día —es como `IncidenciaInventario` y
el reporte de omitidos saben de qué venta hablan— y cada lote que FEFO tomó
al vender deja su propia fila (`movimiento_inventario`, una por lote,
ADR-015). El dato para reponer al lote correcto siempre estuvo en la base;
solo faltaba leerlo antes de reponer.

## Decisión

**`_reponer` reconstruye los lotes de la salida original por `referencia`
y reparte la reposición entre ellos, en el mismo orden en que salieron.**
"El mismo orden en que salieron" es, por construcción de FEFO, el orden de
vencimiento — y se ordena por `lote.fecha_vencimiento`, no por
`movimiento_inventario.ts`: dos movimientos del mismo reparto FEFO pueden
compartir el mismo instante (misma transacción, `func.now()` a nivel de
segundo en SQLite) y el orden de `ts` deja de ser confiable como
desempate.

**Una reposición parcial —nota de crédito por menos de lo vendido— entra
primero a donde salió primero, sin pasarse de lo que ese lote entregó.**
No hay forma de saber qué unidad física vuelve; es la asunción más simple
y la más conservadora, y coincide con lo que FEFO ya asume sobre el
inventario: lo que vence antes es lo que primero se mueve, en cualquier
dirección.

**Sin rastro, cae al comportamiento de siempre.** Una venta anterior a
este cambio, o un SKU que por otro motivo no dejó movimientos con esa
`referencia`, repone al lote del día — el mismo camino que existía antes,
no una regresión ni un error nuevo.

**No se tocó `sales`.** Ni el payload de `ventas.py`, ni el de
`notas_credito.py`, ni el contrato del evento `sales.venta_anulada`
(`lineas_anuladas`, `nota_credito_emitida` lo comparten). El dato que
faltaba era de `inventory` y vivía en `inventory`.

## Consecuencias

- El costo es contable, no solo de trazabilidad: con volumen bajo la
  diferencia entre "repuso al lote correcto" y "repuso al lote del día" no
  se nota, pero con un artículo de alta rotación y varios lotes activos, la
  valorización FIFO/FEFO del stock puede desviarse mes a mes si nunca se
  corrige. Esto lo cierra.
- `tests/test_reposicion_al_lote.py` prueba los cinco casos: un solo lote,
  reposición total repartida entre dos, reposición parcial que prioriza el
  primero, reposición parcial que agota el primero y sigue al segundo, y
  el camino sin rastro.
