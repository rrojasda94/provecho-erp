- **Extras y Mitad x Mitad en el sitio, con las mismas reglas que el PDV**
  (2026-09-19). En el detalle de una pizza el cliente elige tamaño, los sabores de
  cada mitad (el mismo sabor en las dos mitades no se ofrece) y hasta 3 extras,
  con el precio a la vista; el carrito distingue la misma pizza con otros
  sabores o extras y el pedido muestra lo elegido. Antes un producto con sabores
  obligatorios **no se podía pedir por la web**: la carta pública recortaba los
  extras y atributos y `crear_venta` rechazaba la línea con "falta elegir…".
  Ahora la carta pública (solo el detalle de cada producto, no la lista) trae
  extras, sabores y pares excluidos; la API valida la línea **antes de cobrar**
  —con Izipay el pago va primero— y el total sale igual al que `sales` cobra
  (probado contra las líneas de la venta). RN-WEB-017; ADR-105 §6 estaba mal
  diagnosticado y se corrige (`sales` ya tenía el modelo). Migración
  `5c1a7e90d4b3` (dos columnas JSON en `storefront_pedido_item`). Costo aceptado:
  el tope de 3 extras vive en el sitio (regla de la marca), no en el ERP; sin
  "sin cebolla" todavía.
