- **Las promociones se aplican solas** (2026-08-28, ADR-076). Era la deuda
  más vieja del PDV: el ERP sabía bajar un total de dos formas —el descuento
  manual que firma un supervisor y el cupón que trae el cliente— y le faltaba
  la tercera, la regla que el pedido cumple sin que nadie intervenga.
  Entidad `promocion` con vigencia (fechas, días de la semana y franja
  horaria, que puede cruzar la medianoche), ámbito por marca, sucursal, canal
  y modalidad, y cuatro tipos de condición: **N×M** —que cubre 2x1, 3x2 y "la
  segunda a mitad de precio", porque el beneficio es un porcentaje sobre lo
  liberado y no un "gratis" sí/no—, **X unidades** de un producto o
  categoría, **combo** a precio fijo o con uno gratis, y **monto mínimo**,
  que con piso cero es el precio de una franja horaria. Alta en Comercial →
  Promociones con `sales.gestionar_promociones`.
- **Lo aplicado no toca `venta.descuento_*`** (2026-08-28). Va a
  `venta_promocion`, tabla propia. Es la frontera que la deuda ya exigía: si
  el motor escribiera en esos campos, el reporte de descuentos no podría
  distinguir lo que regaló una persona de lo que aplicó una regla — y esa
  distinción es el único motivo por el que el descuento manual guarda motivo
  y autorizador.
- **Cada unidad la descuenta una sola promoción** (2026-08-28). Gana la de
  mayor prioridad y lo liberado es siempre lo más barato del conjunto. Sin
  eso, un 2x1 y un "20 % en pizzas" se cobraban los dos sobre la misma pizza.
  Acumular es una decisión explícita por promoción, no el comportamiento por
  defecto. Y la promoción baja el total **antes** que el descuento manual: al
  revés, un porcentaje firmado sobre un pedido ya promocionado regalaría el
  doble de lo aprobado.
- **Se reevalúan en cada cambio del pedido** (2026-08-28). La que deja de
  cumplirse porque se quitó un producto desaparece; la que se completa con un
  aumento se activa. El PDV las muestra en el ticket con su nombre: el cajero
  no las pide ni las firma, pero tiene que poder explicarlas.
