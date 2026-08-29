- **Las listas desplegables se filtran escribiendo** (2026-08-29). Ninguno de
  los desplegables del ERP tenía búsqueda: elegir un insumo entre miles era
  bajar la lista a mano. El componente nuevo (`components/ui/combobox`) filtra
  ignorando tildes —"gase" encuentra "Gáseosa"—, busca también por código y
  pone adelante lo que empieza con lo tecleado. Los enumerados fijos del código
  —estados, tipos, modalidades— siguen siendo `<select>` nativos a propósito:
  ponerle un buscador a tres opciones estorba más de lo que ayuda.
- **`GET /inventory/articulos` acepta `?q=`** (2026-08-29). Se buscaba en el
  cliente sobre lo ya recibido, y con un techo de 200 filas por página eso deja
  invisible casi todo el catálogo sin avisar: parece que el artículo no existe.
  Es el único catálogo que lo necesita —SKUs y cuentas contables se devuelven
  sin paginar—, así que se agregó solo ahí en vez de a los cuatro endpoints que
  se habían previsto.
- **Los desplegables de listas largas ya no se quedan en las primeras 50
  filas** (2026-08-29). Los catálogos que alimentan un campo se piden ahora al
  tope de página (200) en vez del defecto, y el de artículos —que no cabe ni en
  200— busca contra la base. Antes la pantalla mostraba una página y no decía
  que hubiera más: buscar un insumo que existía devolvía "sin resultados".
- **`GET /inventory/articulos` acepta `?tipo=` repetido** (2026-08-29). "Qué se
  puede producir" son las subrecetas **y** la mercadería, y con un solo tipo por
  petición la pantalla resolvía ese "o" filtrando las cincuenta filas que le
  habían llegado. Un solo `tipo` sigue funcionando igual.
- **Los 62 desplegables alimentados por la API se buscan escribiendo**
  (2026-08-29). Sucursales, almacenes, marcas, unidades de medida, categorías,
  cuentas contables, recetas, artículos, proveedores, roles y permisos. Los 52
  restantes —estados, tipos, modalidades, meses, paginación— siguen siendo
  `<select>` nativos a propósito. En el PDV y el KDS se conservaron sus clases
  propias (`pdv-selector-sucursal`, `kds-campo`): son pantallas táctiles con su
  propio sistema visual y no heredan los estilos del ERP.
