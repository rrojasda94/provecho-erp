- **El rol `comprador` nunca veía el formulario de nueva orden de compra.**
  La página pide en paralelo órdenes, proveedores, almacenes y el catálogo de
  artículos (`/inventory/articulos`) — pero el seeder nunca le dio a
  `comprador` el permiso `inventory.leer`, así que ese último fetch volvía
  403 y tumbaba la pantalla entera con un mensaje que además culpaba al
  permiso equivocado ("no tienes permiso para ver órdenes de compra", cuando
  el 403 venía de inventory). Se agregó el permiso al rol y la página ya no
  cae completa si solo falla el catálogo de artículos — se muestra igual, con
  el aviso correcto y sin el selector de producto poblado.
