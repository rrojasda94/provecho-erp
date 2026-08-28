- **Un aumento con promoción asentaba el precio de lista** (2026-08-28,
  ADR-076). `POST /ventas/{id}/items` publica "lo confirmado en esta
  operación" (ADR-043 §3) y eso era el precio de lista de lo que entró. Con
  una promoción de por medio dejan de ser lo mismo: la segunda pizza de un
  2x1 entra por S/ 40 y no le suma un sol al total, así que contabilidad
  asentaba S/ 40 que la caja nunca cobró y los libros dejaban de cuadrar con
  el turno. Ahora se publica **cuánto sube lo que hay que cobrar**. El delta
  puede ser negativo —agregar una gaseosa que dispara un "20 % desde S/ 50"—
  y se publica tal cual: el asiento sigue a la caja, y taparlo con un cero
  dejaría los libros por encima de lo cobrado.
