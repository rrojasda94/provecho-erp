- **El CDR no se podía descargar desde la pantalla** (2026-09-05, hallazgo #18
  de la auditoría del 2026-08-30). La API lo servía desde siempre
  —`/comprobantes/{id}/descargar/cdr`— y Comprobantes ofrecía solo PDF y XML.
  El CDR es la constancia de que SUNAT recibió y aceptó el comprobante: es
  justo lo que se muestra cuando alguien discute si el documento existe.
- **`inventory.ajustar` era un permiso que no autorizaba nada** (2026-09-05).
  Estaba sembrado y otorgado al `almacenero`, y ningún endpoint lo exigía —
  quien lo miraba en la pantalla de roles creía estar dando o quitando algo.
  El ajuste real se reparte entre `inventory.solicitar_ajuste` y
  `inventory.aprobar_ajuste`, que sí existen y están separados a propósito.
  Sale del seeder; en una base ya sembrada la fila queda y no concede nada.
