- **Inventario no se podía arrancar, y de ahí en adelante nada funcionaba**
  (2026-09-04). Los almacenes se veían vacíos, el conteo abría sin nada que
  contar, y un requerimiento aprobado no se podía despachar. La causa era una
  sola y estaba antes de todo lo demás: la fila de `stock` nacía **sola con el
  primer movimiento**, así que un almacén recién dado de alta era invisible en
  todas partes y no existía ninguna acción para salir de ese cero. Sin filas,
  el conteo se armaba vacío, el requerimiento de la jornada salía vacío
  ("nada está bajo mínimo", cuando en realidad no había nada declarado) y ni
  siquiera se podía aprobar un pedido, porque reservar exige disponible > 0.
  Ahora un almacén declara qué artículos maneja
  (`POST /inventory/almacenes/{id}/articulos`, botón "Agregar artículos" en la
  pantalla de stock): **una fila en cero significa que el almacén maneja ese
  artículo**, y con eso el resto del módulo ya funcionaba sin tocarlo. La
  cantidad de partida entra como movimiento `carga_inicial`, que no pide
  aprobación de un segundo usuario —no corrige nada— pero solo se admite
  mientras ese (almacén, SKU) no tenga historia: con movimientos, corregir el
  saldo vuelve a ser un ajuste con dos firmas (RN-INV-006).
- **Un requerimiento aprobado no tenía cómo despacharse** (2026-09-04). El
  backend estaba completo desde el slice de transferencias —despachar mueve el
  stock, cierra la reserva y deja la solicitud en `despachada`— y **ninguna
  pantalla lo llamaba**: el central llegaba al detalle del pedido y no
  encontraba ningún botón, y lo que sí se despachaba quedaba `en_transito`
  para siempre porque tampoco había dónde recibirlo. Se agregan la pantalla de
  picking (cantidad editable por línea: despachar de menos es el caso real y
  la diferencia queda anotada), la pantalla de Traslados con su botón de
  recibir, y el filtro `almacen_abastecedor_id` en `GET /solicitudes` — la
  bandeja del que despacha, que era la pregunta que no se podía hacer: se
  podía consultar "qué pedí" pero no "qué me piden".
- **El seeder crea `almacen1` y `aprobador1`** (2026-09-04). Inventario exige
  dos personas distintas —quien pide un ajuste o un requerimiento no puede
  aprobarlo— y con solo `admin` y `cajero1` el circuito no se podía cerrar ni
  para probarlo. Es lo que dejó staging trabado: nadie podía cargar stock.
