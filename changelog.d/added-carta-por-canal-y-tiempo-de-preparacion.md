- **Carta por canal y tiempo de preparación por producto** (2026-09-19). La
  ficha del producto en el ERP suma "Dónde se vende y cuánto tarda": se marca
  en qué canales se vende (PDV, sitio web, delivery, agente IA; todos
  marcados = en todos) y cuántos minutos tarda en salir de cocina. Sacar un
  producto de "Sitio web" lo quita de la carta de la web **y** de lo que el
  checkout acepta (la carta es la lista blanca del pedido), sin tocar listas
  de precio: es lo que faltaba para retirar cajas, propinas y otros ítems que
  solo existen en el mostrador. RN-COM-044 y RN-COM-045; migración
  `e0abbeea6a86` (dos columnas NULL-ables, sin backfill).

- **El tiempo de espera del sitio depende de lo que se pide** (2026-09-19).
  Antes era 30 min + 5 por cada orden abierta, igual para una botella de agua
  que para seis pizzas. Ahora es preparación (el mayor tiempo entre los
  productos) + cola (solo si hay algo que cocinar) + viaje en delivery, con
  piso de 5 minutos: recoger una botella de agua dice "5-10 min". El
  checkout manda el carrito al cotizar. Costo aceptado: hay que cargar el
  tiempo de cada producto; sin él, se usa la base de 30 min como antes.
  RN-WEB-011, ADR-105 §4 enmendado.

- **Filtros de la carta del sitio más claros** (2026-09-19). Se quitaron
  "Precio hasta" (comparaba contra el precio más bajo de las presentaciones y
  engañaba) y "Solo disponibles" (lo agotado ahora se ve con su etiqueta, al
  final). "Tamaño" solo aparece si la categoría elegida tiene presentaciones,
  con los tamaños en el orden de la carta, y ya no deja pasar productos sin
  presentaciones. Los filtros viven en la URL (`?q=&cat=&tam=`): volver
  atrás desde un producto no los pierde.
