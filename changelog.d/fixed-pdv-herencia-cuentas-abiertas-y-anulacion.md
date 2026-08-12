- **La pizza seguía sin poder elegir sabor** (2026-08-12, ADR-042). El arreglo
  anterior (ADR-038) servía para el catálogo del **seeder**, que cuelga el
  grupo de la variante, y dejaba roto el armado **a mano**: el lienzo cuelga
  "+ grupo" del nodo activo, y el nodo activo es el padre mientras el producto
  no tiene tamaños. El recorrido natural —crear "Pizza", armarle los sabores,
  y recién después agregar Personal/Mediana/Familiar— deja los sabores en el
  padre y las variantes vacías. Mientras el lugar donde quedó colgado el grupo
  importe, siempre va a haber una mitad de los casos rota, así que ahora **una
  variante ofrece lo suyo más lo del padre**, y la venta acepta exactamente lo
  que la carta ofreció. El vínculo propio gana sobre el heredado: si la
  Familiar declara su propio "extra queso", manda su tope. Sin migración: es
  una regla de lectura, y los dos catálogos que hay hoy funcionan sin tocar
  sus datos.
- **El cajero no podía anular un pedido ya enviado**: `sales.anular` es un
  permiso de supervisor, así que el botón del PDV devolvía 403 sin decir qué
  hacer y el pedido quedaba en cocina. El permiso sigue siendo de supervisor;
  lo que faltaba era el camino del cajero, que es el mismo que ya existía para
  quitar una línea enviada (RN-COM-020): la pide él y la firma un supervisor
  con su PIN en el mismo terminal. El PDV lo intenta sin firma primero — quien
  ya tiene el permiso no debería teclear su propio PIN para anular su pedido —
  y solo pide la firma si el servidor dice que no le alcanza. El endpoint
  entra con `sales.cobrar` **o** `sales.anular`: son roles disjuntos —el
  cajero cobra y no anula, el supervisor anula y no cobra— y exigir los dos
  habría dejado afuera a los dos.
- **Los pedidos enviados y sin cobrar no se veían**: existían como una nota al
  pie del mapa de mesas, y encima filtrando fuera los de mesa, así que un
  "para llevar" solo se encontraba entrando a Mesas y bajando, y uno de mesa
  había que reconocerlo por el color de una celda. Ahora es una pestaña propia
  ("Cuentas") con todo lo que falta cobrar —mesa, para llevar y delivery en la
  misma lista, con su total— porque esa es la pregunta de la caja y no es una
  pregunta sobre el salón. El mapa de mesas sigue siendo el mapa de mesas.
