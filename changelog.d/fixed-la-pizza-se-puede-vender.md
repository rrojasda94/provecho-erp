- **No se podía vender una pizza** (2026-08-12, ADR-038). `GET /sales/carta`
  armaba los grupos de opciones leyendo el producto **padre**, pero los
  sabores cuelgan de la **variante**, que es el producto que se prepara
  (RN-COM-022/023). La carta devolvía `extras: []`, el PDV no dibujaba
  "Sabor", habilitaba Guardar sin elegir ninguno, y el servidor —que sí mira
  los grupos de la variante— rechazaba el pedido con
  `409 'Sabor' exige elegir 1, llegaron 0`. El cajero veía un error que la
  pantalla nunca le dejó evitar, y como sin venta confirmada no hay comanda,
  tampoco llegaba nada al KDS. Ahora cada variante viaja con su propio
  `extras[]` (aditivo, sin migración) y el PDV ofrece los de la presentación
  elegida — que son exactamente los que el servidor acepta. Cambiar de tamaño
  limpia lo ya elegido: los ids son de otra variante.
- **Los sabores del catálogo de demo se creaban sin precio de lista** y la
  carta descarta todo extra sin precio vigente, así que no habrían aparecido
  igual. Se les fija precio 0: el sabor no cobra aparte, pero "vale cero" y
  "no tiene precio" son cosas distintas, y la carta hace bien en no ofrecer
  la segunda.
- **El lienzo de nodos no se podía cablear** (ADR-035, tercera enmienda).
  `conectar()`/`desconectar()` estaban escritos, probados y enchufados, pero
  todos los `<Handle>` llevaban `isConnectable={false}`: react-flow no deja ni
  empezar el arrastre desde un puerto deshabilitado, así que era código
  inalcanzable. Se habilitan los puertos, las aristas se cortan **solo** donde
  el dominio admite desvincular, y `Supr` se suma al `Backspace` de fábrica.
- **Un nodo con acciones ya no se traga sus propios clicks**: `Tarjeta`
  deshabilitaba el `<button>` del nodo cuando no tenía `onToggle`, y un
  `<button disabled>` anula lo que contiene — con eso "receta" y "quitar"
  estaban muertos en el nodo de grupo.
- **El grupo se retira desde su nodo**: `BorrarGrupo` existía como componente
  y no estaba montado en ninguna pantalla, así que la única forma de borrar un
  grupo era el endpoint. Sigue **soltando** sus opciones, no borrándolas.
- **Una acción de estructura del lienzo refresca también la lista de recetas**
  (`router.refresh()`): un tamaño o una opción recién creados mostraban
  `receta` en el pie en vez del nombre de la suya hasta recargar a mano.
