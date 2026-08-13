- **La cocina pasa a ser una cadena de estaciones** (2026-08-13, ADR-044,
  RN-CUP-013). El KDS ruteaba solo por categoría: la pizza aparecía a la vez
  en armado y en horno, cualquiera de los dos podía tacharla, y tacharla la
  dejaba lista sin haber pasado por el horno. Ahora cada estación tiene un
  **paso** (`kds_pantalla.orden`) y cada línea sabe en cuál va
  (`venta_item.etapa_kds`): marcarla en una estación intermedia la manda a la
  siguiente que atienda su categoría, y solo queda `listo` cuando ya no le
  queda ninguna. Una bebida se salta el horno sola, sin configurar
  excepciones. Todo lo ya configurado sigue igual — las dos columnas nacen
  en 0, y una cocina de una estación es una cadena de un eslabón.
- **Despacho deja de ser la pantalla de cocina con otro filtro**: era el
  mismo componente, así que ofrecía tachar ítems en vez de decir qué falta.
  Ahora es una tarjeta por **pedido** con cuántas líneas van, en qué
  estación está cada una y por quién se espera; desde ahí solo se entrega,
  porque marcar preparado es un acto de la estación que preparó
  (RN-CUP-003).
- **La cocina volvió a ver los pedidos de consumo de personal**: el
  `response_model` de la cola filtraba en silencio `tipo` y
  `consumo_motivo` pese a que el servidor los devolvía, así que el aviso que
  la pantalla tenía escrito no se mostraba nunca (RN-COM-025).
- **Los PIN del PDV se teclean en un pinpad, sin campo de formulario**
  (ADR-045, RN-POS-014). Los cuatro sitios que piden PIN —apertura y cierre
  de caja, consumo de personal y firma de supervisor— usaban un
  `<input type="password">`: el navegador ofrecía guardarlo, y con el PIN
  guardado en la caja el turno siguiente entra con la cuenta del anterior y
  toda la auditoría nombra a la persona equivocada (RN-AUD-005). Sin campo
  no hay nada que guardar. Fuera del PDV no cambia nada.
- **La pantalla del PDV se bloquea a los 5 minutos y NO cierra sesión**: la
  caja abierta y el pedido a medio armar siguen donde estaban, y se reabre
  con el PIN de quien tiene la sesión contra el nuevo
  `POST /auth/verificar-pin`. Cerrar sesión habría sido peor que no hacer
  nada: el turno habría dejado la pantalla tocada a propósito para no perder
  el pedido. Un intento fallido cuenta contra el mismo bloqueo de cuenta que
  el login, y no contra un contador propio que sería la vía cómoda para
  probar PINes.
- **El PDV con la caja cerrada decía "la carta está vacía: ningún producto
  tiene precio vigente para esta sucursal"**, que manda a revisar listas de
  precios por nada: la carta no se pide hasta abrir caja, así que vacía
  antes de eso no significa lo mismo. Ahora dice "Abre la caja para ver la
  carta".
- **El seeder no corría contra Postgres**: la descripción de
  `users.resetear_pin` medía 260 caracteres y `permiso.descripcion` es
  `VARCHAR(255)`. SQLite no valida el largo, así que la suite entera pasaba
  en verde y el fallo aparecía recién al sembrar una base real — abortando
  el seeder completo con un `StringDataRightTruncation` que no dice qué
  permiso fue. Se acortó a 248, y hay una prueba que compara cada
  descripción contra el largo declarado en el modelo para que la próxima
  falle donde tiene que fallar.
- **El sabor dejó de salir como un plato aparte en cocina** (ADR-044
  enmendado, RN-CUP-014). Una *Pizza Personal Peperoni* aparecía en la
  tarjeta del KDS como dos ítems —`1 Pizza Personal` y `1 Peperoni`— y en
  despacho contaba "2 de 2" por una sola pizza. El extra es fila propia de
  la venta (tiene receta, precio y rastro), pero `kds.py` no mencionaba
  `padre_venta_item_id` en ninguna parte, así que aplanaba. Ahora viaja
  anidado y se muestra tabulado bajo su plato, igual que las restas; la
  comanda impresa lo sangra en vez de imprimirlo como línea de primer nivel;
  el ruteo por estaciones mira la categoría **del plato**; y marcar el plato
  marca sus extras — sin eso, `pedido_entregable` (que suma todos los ítems)
  habría dejado el pedido sin poder entregarse nunca.
- **Un extra sin categoría colgaba el pedido para siempre**: como ítem
  suelto, ninguna estación filtrada por categoría lo atendía, así que se
  quedaba `pendiente` y el pedido no llegaba a entregable. Todos los extras
  del seeder de pizzas estaban en ese caso.
- **Anular un plato con extras reventaba contra Postgres**:
  `fk_venta_item_padre` es `NO ACTION` y el PDV manda solo el id del plato,
  así que borrarlo dejaba al sabor apuntándolo — `ForeignKeyViolation`.
  SQLite no valida FKs, por eso las pruebas pasaban en verde. Ahora la
  anulación se lleva los hijos y **repone también su insumo**, que antes
  quedaba descontado sin haberse preparado. El fixture de `test_pdv_slice`
  enciende `PRAGMA foreign_keys=ON` para que la próxima falle donde tiene
  que fallar.
