- **Crear una lista de precios desde la ficha del producto.** El endpoint
  `POST /sales/listas-precio` existía desde el precio server-side
  (RN-PRC-003), pero no había pantalla para usarlo — solo se podía "fijar"
  precio en una lista ya creada por API. Ahora `/catalogo/productos/{id}`
  tiene un "+ Nueva lista" junto al selector de precio, con `canal`
  (PDV, Agente IA, Delivery, Sitio web). Sirve, por ejemplo, para que
  Charlie's Pizzas cobre distinto en el sitio de marca sin tocar el precio
  del PDV — la lista más específica gana (`elegir_lista_precio`).
