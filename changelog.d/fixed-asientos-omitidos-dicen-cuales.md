- **El aviso de asientos no escritos no decía cuáles** (2026-09-23, enmienda a
  ADR-089). Contaba por motivo y nada más. Ahora despliega cada uno: fecha,
  operación en palabras, documento con enlace a su ficha (venta, OC, orden de
  producción, activo…), motivo y detalle, y cubre los últimos 30 días en vez
  de acumular desde siempre. Además, un listener contable que fallaba con una
  excepción solo quedaba en el log: ahora se anota como omisión con motivo
  **error** y el mensaje, así que aparece en el mismo aviso (migración
  `d8e2f4a6b1c3`).
