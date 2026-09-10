- **El módulo `production` solo se podía probar como `admin`** (2026-09-09,
  bloque `feat/produccion-semilla-y-pantalla-con-permisos` del plan de deuda de
  producción). Ningún seeder creaba un usuario con rol `jefe_cocina`, un
  almacén tipo `produccion`, ni una receta con `articulo_id` — sin esa receta,
  `POST /production/ordenes` rechaza toda orden con 409. `seed()` ahora crea
  `jefecocina1` (PIN 123456) y el almacén `WH-PROD`, abastecido por el central.
  La receta BOM (insumo + subreceta) fue a `python -m src.seeders.e2e` y no a
  `seed()`: un artículo real en el catálogo de la empresa base rompía 21 tests
  de una docena de suites que asumen ese catálogo vacío salvo lo que cada una
  crea, incluida una colisión de `categoria_udm.nombre` (columna UNIQUE) contra
  media docena de fixtures que crean su propia categoría "Peso" a mano después
  de llamar a `seed()`.
- **La pantalla de producción no distinguía quién podía qué.** `/produccion`
  mostraba "+ Nueva orden" y los botones de Consumo/Completar a cualquiera con
  `production.leer`, sin gatear por `production.crear`/`production.completar`
  como sí hace `inventario/transferencias`. Ahora recibe `permisos` del
  servidor y oculta cada acción sin su permiso. De paso, la lista paginaba solo
  con la primera página del servidor sin forma de ver el resto — ahora navega
  con `?page=` como `/auditoria`.
  Costo aceptado: la ficha de detalle de una orden sigue sin existir (queda en
  `feat/produccion-ficha-y-consumo-sugerido`), y `pdv_demo.py`/`pizzas_demo.py`
  no tienen su propia receta de producción — son seeders de demo, no de
  desarrollo ni de CI.
