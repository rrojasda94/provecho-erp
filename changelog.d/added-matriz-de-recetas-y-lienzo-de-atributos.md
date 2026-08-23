- **El recetario se edita en grilla** (`/catalogo/recetas/matriz`, ADR-057).

  Insumos en las filas, recetas en las columnas, gramajes en las celdas.
  Corregir el queso de las tres presentaciones de ocho pizzas eran
  veinticuatro fichas abiertas de a una.

  - **Se pega un rectángulo desde Excel.** La identidad de una celda es
    `(receta, insumo, condición)` y no un id de línea, que es lo que hace
    posible pegar algo que no trae ids: el servidor resuelve solo si es alta,
    edición o borrado. También se copia, en el mismo formato.
  - **Vaciar la celda borra la línea**: en una grilla es la forma natural de
    decir "este insumo no va acá".
  - **Se guarda por lote y solo lo que cambió.** Cada celda va en su propio
    `SAVEPOINT`: pegar cuarenta y perderlas todas por una mal escrita es el
    modo de falla que hace que nadie vuelva a pegar nada.
  - La celda muestra lo tecleado (`450/3`), no el resultado; el número lo
    calcula el servidor (RN-COM-024) y la vista previa va debajo.

- **El lienzo dibuja atributos y carga el árbol de una vez** (ADR-058).

  - `GET /sales/productos/{id}/arbol` reemplaza **una petición por variante**:
    con tres tamaños y ocho sabores eran 27 idas a la red para dibujar un
    árbol.
  - El atributo se dibuja como el grupo y el valor como la opción: el gesto es
    el mismo y el lienzo no gana nada con una segunda forma de mostrarlo.
  - **Lo excluido se apaga, no se oculta** (RN-COM-038), y elegir un valor
    suelta los que quedan excluidos por él, para no mostrar un plato que la
    venta va a rechazar.
  - **El producto y los tamaños guardan dónde quedaron** (`lienzo_pos`). Es lo
    que ADR-035 §5 había dejado fuera con un argumento que valía mientras el
    árbol lo dictaba una topología fija.

- **API de atributos**: crear, agregar valores, ofrecerlos en un producto,
  fijar el precio extra, retirar un valor —que lo **desactiva**, no lo borra,
  porque hay ventas que lo nombran— y declarar exclusiones.

- `recetas.editar_item` acepta `unidad_medida_id` y redondea con los decimales
  de **la unidad de la línea**: quien teclea gramos espera que 24.4 sea 24, no
  tres decimales de un kilo.
