# ADR-078 — El pedido sale de la cola al entregarse, no al facturarse

- **Estado:** aceptada — **enmienda ADR-044**
- **Fecha:** 2026-08-28
- **Contexto:** `sales` (`kds.cola_pantalla`, `kds._estacion`)
- **Relacionado:** ADR-044 (cadena de estaciones), ADR-075 (la tanda del
  aumento), RN-CUP-004, RN-CUP-014

## Contexto

El turno de prueba de la 0.8.0 lo reportó así: «cuando se envía el pedido, no
siempre se envía al KDS. Sin embargo los aumentos sí».

El "no siempre" era la pista. No había un envío que fallara: **el KDS no
recibe nada, hace polling sobre `venta`.** Un pedido aparece en cocina por el
mero hecho de existir con un estado que la cola mire. Y la cola miraba dos
cosas de menos.

### `facturada` no estaba en la lista

`cola_pantalla` filtraba `estado in ('orden', 'pagada')`. Pero
`emitir_comprobante` pasa la venta a `facturada` en cuanto Factiliza acepta
—una tarea async, a segundos del cobro—.

En el flujo *para llevar* o *delivery*, donde el cajero arma el pedido y
pulsa **Cobrar** directo, la venta nace, pasa a `pagada` y a `facturada` casi
de inmediato: **la cocina podía no verla nunca**. En una mesa no pasaba,
porque la orden se envía primero y se queda en `orden` mientras dure la
comida — que es justo por qué los aumentos sí llegaban: solo existen sobre
una orden abierta.

`historial_pantalla` ya usaba la lista completa. La cola se había quedado
corta, y la inconsistencia entre las dos era la señal.

### Una categoría sin estación dejaba la línea invisible

`_estacion` recorre la cadena buscando la primera pantalla con
`orden >= desde` que atienda la categoría del producto. Si ninguna la
declaraba —el producto sin `categoria_id`, o su categoría fuera de todos los
`categoria_ids`— devolvía `None`, y `_items_de_pantalla` la descartaba antes
de ponerla en ninguna tarjeta.

La línea se quedaba `pendiente` para siempre. Como despacho exige que algo
esté `listo`, tampoco llegaba ahí: un pedido cuyas líneas fueran todas de
categorías no ruteadas era **invisible en todo el KDS**, y el aviso que
existía para explicarlo —"hay líneas sin estación asignada"— vivía en una
pantalla a la que ese pedido nunca llegaba.

## Decisión

### Lo que saca un pedido de la cola es entregarlo

`ESTADOS_EN_COCINA = ("orden", "pagada", "facturada", "cerrada")`, la misma
lista que el historial. La salida real ya existía y no se toca: el pedido
desaparece cuando todas sus líneas están `entregado`.

Cobrar y preparar son dos ejes distintos. Que un pedido esté pagado no dice
nada sobre si la cocina lo hizo, y usar el estado del cobro como si lo dijera
es lo que hacía desaparecer comida sin preparar.

### Si ninguna estación declara la categoría, la atiende la primera

Es la tolerancia que `_estacion` ya documentaba —«si el eslabón exacto ya no
existe, la línea cae a la siguiente que sí la acepte en vez de quedar
invisible»— llevada hasta el final. Antes cubría el caso de una estación
desactivada; no cubría el de una categoría que nadie declaró nunca.

El descarte se mide sobre la cadena entera y no desde `desde`: así una
huérfana ya bumpeada termina en `None` —lista— en vez de volver a caer en la
primera estación y quedar girando.

`_items_de_pantalla` acompaña: una línea es de la pantalla si esta declara su
categoría **o** si la línea cayó ahí por no tener quién la declare. Sin la
segunda mitad el filtro la tiraba antes de que nadie llegara a preguntarle su
estación.

**Una comanda mal ruteada se arregla mirando la tarjeta; una comanda
invisible, no.** Ese es todo el criterio: es preferible que el pedido salga
en la estación equivocada —donde alguien lo ve y lo reclama— a que no salga
en ninguna.

## Alternativas descartadas

- **Sacar el pedido de la cola al facturarse y avisar aparte.** Es el estado
  anterior con una notificación encima: el pedido ya no está donde el
  cocinero mira.
- **Rechazar la venta si alguna línea no tiene estación.** Convierte un
  problema de configuración del KDS en una caja que no puede cobrar. El local
  se queda sin vender por una categoría mal cargada.
- **Mostrar la línea huérfana en todas las estaciones.** Dos cocineros
  preparando el mismo plato es peor que uno preparando lo que no le toca.
- **Un campo `enviado_a_kds` en la venta.** Un estado más que mantener
  sincronizado con el que ya existe, y que se desincroniza el día que alguien
  escriba en `venta_item` sin pasar por el caso de uso.

## Consecuencias

- Sin migración: las dos son reglas de lectura de la cola.
- Un pedido cobrado y facturado sigue en la pantalla de cocina hasta que se
  entrega. Es más carga visible en la cola, y es la correcta: era comida sin
  preparar que ya no se veía.
- El aviso "hay líneas sin estación asignada" de la pantalla de despacho deja
  de dispararse para los pedidos nuevos. Se conserva porque los viejos —los
  que quedaron `pendiente` sin estación— siguen ahí hasta que alguien los
  cierre.
- Cierra el reporte «el pedido no siempre llega al KDS» del turno de prueba
  de la 0.8.0.
