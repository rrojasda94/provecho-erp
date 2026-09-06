- **Una lista recortada se veía igual que una completa** (2026-09-05,
  hallazgo #14 de la auditoría del 2026-08-30). Nueve pantallas pedían 200
  filas y paginaban del lado del navegador: funcionaba hasta pasar las 200, y
  ahí el modo de falla era que alguien buscara un artículo, no lo encontrara y
  concluyera **que no existe**. Dos pantallas ya avisaban con el mismo párrafo
  copiado; ahora es un solo componente (`AvisoRecortado`) y está en las nueve:
  artículos, clientes, personas, órdenes de compra, facturas, stock,
  producción, contenido y lotes. Cada aviso dice por qué filtro acotar — uno
  que solo informa no ayuda.
- **`GET /inventory/lotes` devolvía la tabla entera** (2026-09-05, misma
  auditoría). Sin página ni tope: un local que lleva meses acumula miles de
  lotes, y la consulta y el payload crecían sin techo. Ahora tiene tope (500
  por defecto, configurable hasta 2000) y el orden por vencimiento hace que
  ese tope signifique algo — lo que queda afuera es lo que vence más tarde, o
  sea lo que no urge. La pantalla avisa cuando llegó al techo.
  Costo aceptado: **no es paginación de servidor**, es dejar de mentir. Cuál
  de estas pantallas merece paginación real se decide viendo cuáles avisan
  seguido, que es lo que antes no se podía saber. Y los catálogos que llenan
  un `<select>` siguen topados en silencio: ahí el arreglo no es avisar sino
  buscar en el servidor, como ya hacen `PersonaPicker` y `ArticuloPicker`.
  Los dos quedan anotados como deuda.
