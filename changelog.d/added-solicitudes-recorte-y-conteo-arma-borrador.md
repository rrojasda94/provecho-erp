- **Aprobar un requerimiento recorta por SKU, con pantalla** (ADR visto en
  `docs/architecture/adr/`). `SolicitudAprobar.aprobadas` existía desde
  ADR-020 sin llamador — el diálogo «Aprobar» arranca con lo pedido en cada
  línea y deja bajarlo antes de enviar; en 0 la línea queda fuera y no
  reserva nada.
- **Cerrar un conteo cíclico arma o pone al día el borrador del
  requerimiento del almacén contado** (RN-INV-026, ADR-093). Todo cierre,
  no solo el general — el refresco es aditivo y no pisa lo que el turno ya
  tecleó. Un almacén sin abastecedor propio (el central) no rompe el
  cierre.
