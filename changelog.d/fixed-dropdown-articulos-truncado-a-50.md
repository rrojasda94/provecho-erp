- **El selector de artículos (inventario, orden de compra, importador de
  recetas) solo mostraba los primeros 50, ordenados por nombre.** Los tres
  pedían `/inventory/articulos` sin `page_size`, así que caían en el default
  de paginación (50) en vez del máximo (200) que ya usan otras pantallas del
  repo. Con más de 50 artículos activos, cualquiera después del corte
  alfabético simplemente no llegaba al selector — no era un bug de creación
  de artículos, el artículo existía y no aparecía en ningún desplegable.
  Anotado en ROADMAP: si el catálogo supera 200, hace falta un combobox con
  búsqueda server-side.
