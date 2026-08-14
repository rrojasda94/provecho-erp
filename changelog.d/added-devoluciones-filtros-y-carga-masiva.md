- **Las devoluciones se pueden usar** (2026-08-13, RN-INV-019/020). La API
  estaba completa —registrar, anular, detalle, listar— y la pantalla era una
  tabla de solo lectura: la única forma de registrar una devolución era
  llamar al endpoint a mano. Ahora hay formulario de registro, botón de
  anular y ficha por devolución con qué se devolvió, por qué, a dónde fue y
  quién la registró o anuló. El destino solo aparece para una devolución de
  cliente: a proveedor la mercadería se va y no hay nada que decidir.
- **Registrar y anular una devolución quedan en `audit_log`**: mueven stock
  real y hasta ahora solo dejaban el evento que avisa a compras o comercial,
  que responde otra pregunta. Anular es además el movimiento con el que se
  podría tapar un faltante, así que tiene que decir quién lo hizo.
- **`GET /inventory/skus`**: no existía listado de SKUs, así que ninguna
  pantalla podía ofrecer "qué se mueve". Va con el nombre del artículo,
  porque el código de un SKU no le dice nada a nadie.
- **El catálogo de recetas se filtra por tipo y categoría** (RN-COM-030). El
  tipo **se deriva** de si la receta produce un artículo (subreceta) o no
  (producto de venta): no se agregó columna, que sería un segundo lugar
  donde puede estar mal. Los filtros viajan en la URL, así que el listado se
  filtra en el servidor —donde están las recetas— y se comparte pegando el
  enlace.
- **El recetario se carga de golpe desde un `.xlsx`** (ADR-046, RN-COM-031).
  Se descarga una plantilla con ejemplos e instrucciones, se sube llena, y
  **antes de guardar nada** la pantalla dice qué entra y qué no: unidad
  desconocida, rendimiento inválido, receta repetida, o ingredientes que
  nombran una receta que la otra hoja no declara —el error de tipeo más
  común del formato—. Un insumo que el catálogo no reconoce no cancela la
  carga: se elige cuál es o se omite esa línea **a la vista**, y lo que se
  elige se aplica a todas las recetas que lo nombran. Una receta que no
  entra se informa y no arrastra a las demás (un `SAVEPOINT` por receta). La
  cantidad acepta aritmética tecleada (`450/3`) igual que en la pantalla,
  porque el importador reusa los mismos casos de uso.
- Se eligió `.xlsx` sobre CSV porque Excel en configuración regional peruana
  usa `;` y coma decimal: abrir y guardar un CSV convierte `0.5` en `0,5` y
  corrompe el archivo en silencio.
