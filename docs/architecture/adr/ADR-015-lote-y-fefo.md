# ADR-015 — Lote y FEFO: `stock_lote` como detalle de `stock`, control opcional por artículo

- Estado: aceptado
- Fecha: 2026-07-27

## Contexto

El slice 1 de `inventory` (2026-07-25) dejó el stock como una sola cifra
por almacén/SKU. Sirve para saber cuánto hay, pero no para lo que un
restaurante necesita todos los días: **qué vence primero y qué no se puede
despachar**. Sin lote no hay FEFO, no hay bloqueo de vencidos
(RN-VNC-001..003), no hay trazabilidad de producto terminado (RN-LOT-002/003)
y quedan bloqueadas cuatro deudas de otros módulos: merma contable, guía de
remisión, costeo por lote y conteo del almacén de producción.

El modelo de datos ya describía `lote` y `stock_lote` (§3, §4); faltaba
decidir cómo conviven con el `stock` ya construido y con los artículos para
los que un lote no tiene ningún sentido.

## Decisión

**1. `stock_lote` es detalle de `stock`, no su reemplazo.**
`stock.cantidad` sigue siendo la cifra que consultan el PDV y el dashboard,
y sigue siendo la única que puede quedar negativa-nunca. Para un artículo
con control de lote, la suma de sus `stock_lote` cuadra con ella.

Alternativa descartada: eliminar `stock` y derivar el total sumando lotes.
Habría obligado a reescribir consulta de stock, dashboard, sincronización
con el hub y el flag `bajo_minimo` — todo para una cifra que ya funciona,
y penalizando cada lectura con un `GROUP BY` que hoy no existe.

**2. El control de lote es opcional por artículo (`articulo.controla_lote`).**
El queso y la masa lo llevan; las servilletas no. Alternativa descartada:
lote obligatorio para todo artículo — convierte cada recepción de
suministros en captura de datos inventados, y la operación termina
poniendo códigos falsos, que es peor que no tener lote. El mismo criterio
que RN-COD-001 ya aplica al código de barras: su ausencia no impide
gestionar el artículo.

**3. FEFO se resuelve al registrar la salida, no como una sugerencia aparte.**
`registrar_salida` ordena los lotes con saldo por `fecha_vencimiento`
(los que no vencen van al final, y entre ellos manda el más antiguo: FEFO
degrada a FIFO) y reparte la cantidad. Un `lote_id` explícito en la salida
es el **override** del lote sugerido.

Alternativa descartada: un endpoint "sugerir lote" que el cliente consulta
y después obedece — dos llamadas, una ventana de carrera entre ambas, y
nada obliga a respetar la sugerencia. El listado ordenado
(`GET /inventory/lotes`) sigue existiendo para que el almacenero vea qué le
va a tocar; la garantía vive en el servidor.

**4. Un movimiento de inventario por lote consumido.**
Una salida de 8 kg que toma 5 de un lote y 3 de otro genera **dos**
`movimiento_inventario`, cada uno con su `lote_id`. Alternativa descartada:
un movimiento agregado más una tabla de detalle — duplica el rastro que
`movimiento_inventario` ya es, por definición, el único lugar donde vive.
Consecuencia asumida: `POST /inventory/movimientos` devuelve una **lista**
de movimientos, y `ajuste.movimiento_id` apunta al primero (todos comparten
`referencia`, así que la traza completa es una consulta por referencia).

**5. El vencido se bloquea cuando el picking lo toca, más un barrido a demanda.**
`disponibles_fefo` bloquea el lote vencido que encuentra todavía disponible
y publica `inventory.lote_vencido_detectado`; `POST /inventory/lotes/bloquear-vencidos`
hace lo mismo sin esperar a que haya una salida. Alternativa descartada:
una tarea Celery beat diaria — infraestructura periódica nueva para un caso
que el momento del picking ya cubre, y que además no alertaría a nadie
mientras el consumidor del evento (notificación a `users`, memorándum vía
`rrhh`) no exista.

**6. Nada entra sin lote si el artículo lo controla.**
Un ingreso sin `lote_id` de un artículo con control crea (o reusa) el lote
del día, en vez de rechazarse. Así ningún camino de ingreso —ajuste
positivo, carga inicial, producción sin datos de vencimiento— deja stock
fuera de la trazabilidad ni descuadra `stock` contra `stock_lote`. Una
**salida** sin lote, en cambio, sí se rechaza: debe pasar por
`registrar_salida`.

Excepción explícita y registrada en el código: si el total alcanza pero
ningún lote lo respalda (stock cargado antes de activar el control, o todo
lo demás bloqueado por vencimiento), la salida se completa igual con un
movimiento sin lote. La operación física ya ocurrió; ese movimiento es el
rastro de la discrepancia, no su ocultamiento.

## Consecuencias

- El hub de sucursal replica `lote` y `stock_lote` (ADR-009): sin la fecha
  de vencimiento, una venta offline no podría aplicar FEFO y elegiría un
  lote distinto al que elige la nube.
- La recepción de compra transporta `lote_codigo` y `fecha_vencimiento`
  declarados por el proveedor (RN-VNC-002); producción hereda el mismo
  camino y crea su lote con `origen=produccion`.
- La reposición por venta anulada entra al lote del día, no al lote del que
  salió: el evento de anulación no transporta los movimientos originales.
  Queda como deuda en el ROADMAP.
- Los campos de trazabilidad de fabricación del modelo de datos
  (manipulador, envasador, línea, variables de proceso, QR) **no** se
  implementan acá: pertenecen al slice de `production` que los produce.
