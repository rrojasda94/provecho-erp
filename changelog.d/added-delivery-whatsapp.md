- **El reparto propio avisa al cliente por WhatsApp** (ADR-098, slice 6):
  cuando la ruta sale (`pedido_en_camino`), cuando entrega
  (`pedido_entregado`) y cuando falla (`entrega_fallida`) se manda una
  plantilla aprobada por Meta con el mismo adaptador que ya usa la
  encuesta de satisfacción de `marketing`
  (`shared/integrations/whatsapp`); un fallo de transporte reintenta
  (Celery, hasta 4 veces con backoff), un rechazo de Meta no — queda
  escrito en `entrega.aviso_error` sin volver a intentar el mismo envío.
  Sin teléfono del cliente, sin WhatsApp configurado o en un hub de
  sucursal (que no corre Celery, ADR-009) no se encola nada: el tablero
  de despacho siempre ofrece el enlace de seguimiento para copiar o
  mandar por `wa.me`, esté o no habilitado el envío automático. También
  quedó la notificación in-app (`users.notificar_a`): al repartidor
  cuando le asignan una ruta, y a quien despachó si una entrega falla o
  si la venta de una entrega ya `en_ruta` se anula (RN-DLV-006). Costo
  aceptado: el "contacto de la sucursal" de la plantilla de fallo es solo
  su nombre — `Sucursal` no tiene teléfono propio
  (`docs/roadmap/deuda/modulo-delivery.md`).
