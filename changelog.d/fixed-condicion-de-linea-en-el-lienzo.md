- **La receta de la mitad-y-mitad se veía en plano, sin decir qué mitad lleva
  cada insumo** (enmienda de ADR-056). Con el catálogo de Charlie's cargado,
  el lienzo de `Pizza MitadxMitad Familiar` listaba sus 26 líneas seguidas
  —`Salame Picado` tres veces— y el nodo `Americana F` respondía "no tiene
  receta todavía", que es falso: sus insumos son líneas condicionadas de la
  receta del tamaño.

  El dato estaba bien. `receta_item.aplica_valores` existe desde ADR-056 y el
  motor de descuento lo respeta; lo que faltaba era que la API de la receta
  lo devolviera y lo aceptara. Hasta ahora solo lo tocaba la matriz, y la
  matriz muestra UUID.

  - `GET /inventory/recetas/{id}` devuelve la condición de cada línea, como
    **lista de texto y siempre lista, nunca `null`**: el editor no tiene que
    distinguir dos formas de "sin condición".
  - `POST`/`PATCH .../items` la aceptan. En el `PATCH` los tres estados
    importan: ausente no toca la condición, `[]` la borra y una lista la
    reemplaza. Sin distinguir "no lo edito" de "lo limpio", cambiar un
    gramaje habría borrado la condición de rebote.
  - Tocar el nodo de un sabor abre **sus** líneas y agrega las nuevas ya
    condicionadas a él. En el nodo del tamaño, cada línea muestra su
    condición con nombre ("Mitad 1 F: Americana, Hawaiana") y se edita ahí
    mismo, con casillas agrupadas por atributo y un botón "Aplicar" — un
    `PATCH` por casilla podía dejar el cambio a medias en un 409.
  - El mismo insumo ya se puede repetir con **otra** condición desde el
    editor, que es el caso que todo el modelo existe para resolver: el jamón
    en la Mitad 1 y en la Mitad 2 son dos líneas de la misma receta.

- **Duplicar una receta perdía la condición de sus líneas** (encontrado al
  hacer lo anterior). `duplicar_receta` copiaba artículo, cantidad, expresión
  y merma, y dejaba afuera `aplica_valores`, `unidad_medida_id` y `orden`.
  Duplicar la mitad-y-mitad daba 26 líneas sin condición: una receta que
  descuenta todos los insumos de todas las mitades, siempre, sin que nada lo
  diga hasta cuadrar el mes.

- **La pestaña "Plato" también sumaba las líneas condicionadas como si
  aplicaran siempre** (misma enmienda). El costo simulado del plato quedaba
  por encima del real, y con las condiciones ya visibles en la otra pestaña
  el contraste se notaba más que antes.

  `fusionar()` ahora usa `aplicaAVariante` — un puerto literal de la regla
  del servidor (`inventory/domain/rules.aplica_a_variante`, RN-COM-037):
  mismo agrupado por atributo, mismo Y entre grupos y O dentro de cada uno.
  Es la duplicación que ADR-056 §5 evitó en el backend, aceptada acá a
  propósito — la alternativa era un endpoint nuevo por cada clic en un
  sabor, para un número que ya es una simulación. Las dos implementaciones
  se prueban con los mismos casos, para que un día que diverjan se note en
  la suite.
