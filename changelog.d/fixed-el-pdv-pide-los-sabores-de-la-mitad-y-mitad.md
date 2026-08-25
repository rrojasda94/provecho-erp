- Corregido: **la pizza MitadXMitad no ofrecía elegir sabores en el PDV, y se
  podía cobrar sin ellos**. El configurador mostraba solo la lista de «Sin…»
  porque la carta leía únicamente `producto_opcion_grupo` —el modelo viejo,
  que en el catálogo real está **vacío**— mientras que los sabores viven en
  `producto_atributo_valor` (ADR-055/056). Sin sabores elegidos ninguna línea
  condicionada de la receta se activa, así que la pizza salía de cocina **sin
  descontar un solo insumo** y el faltante aparecía recién en el conteo del
  mes. Ver ADR-066.
- `GET /carta` devuelve ahora `atributos` y `exclusiones` por producto y por
  variante (aditivo, con default `[]`). El PDV los dibuja como pastillas, una
  elección por atributo, y apaga —sin ocultar— el sabor que ya está puesto en
  la otra mitad.
- **RN-COM-040**: un producto que ofrece atributos no se vende sin elegir un
  valor de cada uno. Se hace cumplir al confirmar la venta y no solo en la
  pantalla, porque el kiosko y la central de pedidos entran por el mismo
  endpoint. Excepción: el replay del hub durante un corte (ADR-009), donde la
  venta ya se preparó y se cobró.
- La carta y el validador salen de la **misma** función. Con el filtro escrito
  dos veces, la pantalla dejaría de ofrecer lo que el servidor exige y el
  producto quedaría invendible: es el modo de falla que este cambio evita por
  construcción.
- La sección «Sin…» arranca **colapsada** y se abre al tocarla. Con una receta
  larga ocupaba toda la pantalla y empujaba fuera de la vista los sabores y
  los extras, que es lo que el cajero viene a elegir.
- El **modo offline** replica las cinco tablas de atributos, y `receta_item`
  replica `aplica_valores`. Sin esto el hub habría rechazado toda venta de
  MitadXMitad durante un corte —justo el caso que el modo offline existe para
  evitar— porque replicaba `expresion` pero no la condición que decide si el
  insumo sale del almacén.
- La **comanda** imprime qué mitades lleva el plato, antes de extras y restas.
  Antes lo decía porque el sabor era un extra; con el modelo nuevo habría
  dejado de decirlo, que es lo único que el pizzero necesita de esa pizza.
- `producto_atributo_valor.precio_extra` **se cobra**. Estaba documentado como
  sumando en cuatro lugares y ningún código lo sumaba: una columna editable
  desde la ficha que no cobraba nada. Se verificó contra la base real que hoy
  ningún valor tiene recargo, así que activarlo no mueve ningún precio.
