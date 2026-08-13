- **Una orden ya enviada a cocina admite líneas nuevas** (2026-08-12,
  ADR-043, RN-COM-029). El PDV respondía "Este pedido ya se envió, usa + para
  abrir uno nuevo", así que la mesa que pide una bebida diez minutos después
  terminaba con dos cuentas, que se cobran por separado y se entregan por
  separado. Ahora `POST /ventas/{id}/items` las suma a la misma orden, con el
  mismo permiso que crearla y sin firma de nadie: agregar es lo que el
  negocio quiere que pase, no saca nada del inventario y el rastro queda
  igual. El evento republicado lleva **el incremento** y no el acumulado, así
  que inventory descuenta solo lo nuevo y contabilidad no asienta la venta
  dos veces.
- **Quitar lo recién enviado dejó de necesitar al supervisor**: quitar una
  línea exigía su PIN **siempre**, incluso treinta segundos después de un
  error de tecleo. Un control que se ejecuta veinte veces por turno deja de
  ser un control — se termina dejando la sesión del encargado abierta en la
  caja, que es justo lo que RN-AUD-005 quiere evitar. Ahora hay ventana de
  **5 minutos**: dentro, lo corrige quien opera la caja; fuera, lo firma un
  supervisor como antes (RN-COM-020). La ventana de la orden entera se mide
  contra su **última** línea —una mesa larga sigue teniendo algo recién
  mandado— y un lote necesita firma si **alguna** de sus líneas salió de
  ella, porque si no bastaría con acompañar la vieja de una nueva. El PDV
  intenta sin firma y la pide recién cuando el servidor la exige.
- **Los pedidos vacíos ya no se apilan sin poder cerrarse**: cada toque del
  "+" abría otra pestaña, y ninguna se podía descartar, así que la columna
  derecha se llenaba de pedidos que no eran nada. Ahora el "+" reusa el
  borrador vacío que ya esté abierto —un pedido sin líneas y sin destino no
  es distinto de otro igual— y una pestaña sin líneas y sin enviar se
  descarta con su "×". Una con líneas o ya enviada no: eso es "Anular
  pedido", que repone inventario y queda auditado.
