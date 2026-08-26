- **El reparto se cobra en múltiplos de S/ 0.50** (2026-08-26, RN-COM-042,
  addendum a ADR-054). Base más precio por kilómetro daba el monto exacto —S/
  8.71, S/ 8.89— y el monto exacto es incómodo: el repartidor no lleva monedas
  de un céntimo, el cajero redondea de cabeza, y a partir de ahí el ticket dice
  una cosa y la caja tiene otra. Ahora se redondea **por cercanía**: 8.71 →
  8.50, 8.76 → 9.00, y el empate exacto (x.25, x.75) sube. Se eligió
  `ROUND_HALF_UP` y no el redondeo bancario que `decimal` trae por defecto:
  sobre medio sol, el bancario caería a veces para arriba y a veces para abajo
  sin que nadie que mire el ticket pueda anticiparlo.
- **Se redondea el monto, no la distancia.** `distancia_entrega_km` sigue en
  dos decimales: es una medición, y redondearla al medio kilómetro cambiaría el
  cobro por un motivo que no tiene nada que ver con la plata.
- **Y se redondea en las cuatro salidas.** Las tres ramas «sin distancia»
  —sucursal sin anclar en el mapa, dirección escrita a mano, zona restringida—
  devolvían `tarifa.base` crudo, sin pasar siquiera por `quantize`: una base
  aprobada por error como `3.456` llegaba con tres decimales hasta el ticket.
  Las cuatro pasan ahora por `costo_de`.
