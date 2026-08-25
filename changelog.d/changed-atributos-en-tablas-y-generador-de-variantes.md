- **Los atributos vuelven a la tabla** (2026-08-24, ADR-063). El lienzo
  —el canvas que dibujaba tamaños, atributos y recetas— se borró entero: no
  resultó un lugar de trabajo usable, y quien reportaba que no podía ver ni
  crear extras ni mitades tenía razón, aunque la API existía desde ADR-055.
  En su lugar: una pantalla `/catalogo/atributos` para el vocabulario
  (nombre, modo de variante, valores), una sección «Atributos» en la ficha
  del producto (qué ofrece, con qué sobreprecio, sus exclusiones) y una
  columna «Condición» en el editor de receta, que resuelve de paso el hueco
  que ADR-058 había dejado anotado: la ficha de receta suelta ahora sabe qué
  producto la usa y muestra nombres, no UUID.
- **Nuevo generador de combinaciones** (`POST
  /sales/productos/{id}/variantes`, RN-COM-039): materializa las variantes de
  un atributo en modo `siempre`, respeta las exclusiones declaradas
  (RN-COM-038), es idempotente y nunca borra ni desactiva una variante ya
  generada. `modo_variante = 'dinamica'` queda fuera de este cambio a
  propósito, por no tocar el camino de la venta.
- **Se corrige un bug del editor de receta anterior al lienzo**: el filtro de
  insumos ya usados comparaba solo por artículo, así que era imposible poner
  el mismo insumo en dos líneas con condición distinta — el caso exacto de la
  pizza mitad-y-mitad que motivó ADR-056. Ahora filtra por
  `(insumo, condición)`.
- No afecta al PDV: verificado que `GET /carta` y el camino de venta no leen
  nada del lienzo ni de las pantallas nuevas.
