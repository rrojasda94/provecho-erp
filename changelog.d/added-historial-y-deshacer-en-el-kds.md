- **Un toque ya no despacha el plato: hacen falta dos** (2026-08-26). Tachar un
  ítem encadenaba `pendiente → en_preparacion → listo` y lo mandaba a la
  estación siguiente de una sola vez. En una cocina eso es un problema físico:
  el roce de un delantal contra la tablet despachaba algo que nadie había
  empezado. Ahora el primer toque marca la línea **en preparación** —que es lo
  que las demás pantallas ven mientras tanto— y el segundo es el que la manda
  a la siguiente. El botón «Todo listo» sigue haciendo los dos pasos de una:
  es el atajo de quien sí terminó el pedido entero.
- **Se puede deshacer un paso** (`POST /kds/items/{id}/retroceder`, enmienda a
  RN-CUP-002). Deshace exactamente lo que hizo el toque anterior, que no
  siempre es lo mismo: el avance tiene dos ejes —`estado_preparacion` y
  `etapa_kds`— y tachar en una estación intermedia mueve el segundo sin tocar
  el primero. Así que `listo` vuelve a `en_preparacion` en la misma estación;
  una línea empujada al eslabón siguiente vuelve al anterior; y
  `en_preparacion` en la primera estación vuelve a `pendiente`. La cadena que
  recorre son solo las estaciones que atienden **su** categoría: deshacer una
  bebida no la manda a un horno por el que nunca pasó.
- **Historial de entregas** (`GET /kds/pantallas/{id}/historial`). La cola
  descarta los pedidos en cuanto se entregan, y hasta ahora eso era todo lo
  que la cocina podía ver: uno entregado por error desaparecía de la pantalla
  sin dejar dónde buscarlo. La vista muestra lo despachado del día de negocio
  con su hora, atenuado —está para consultarse, no para trabajarse—. No hace
  polling: el historial no cambia solo.
- **Deshacer una entrega** (`POST /sales/ventas/{id}/deshacer-entrega`). El
  toque sobre la tarjeta de al lado en despacho: el pedido desaparecía y el
  que sí salió seguía ahí, y el único arreglo era anular la venta —que es otra
  cosa completamente—. Devuelve los ítems a `listo` y reabre el consumo de
  personal que la entrega había cerrado. Mismo permiso que entregar
  (`sales.entregar_pedido`) y no uno nuevo: quien puede dar por entregado un
  pedido es exactamente quien tiene que poder corregirse. **No mira el
  comprobante a propósito**: se emite al cobrar, no al entregar, y bloquear el
  deshacer cuando hay boleta apagaría esto justo para el delivery pagado por
  adelantado, que es donde más se usa.
