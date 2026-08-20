- **Exportar es la plantilla con los datos adentro** (2026-08-20, ADR-051).
  Hasta ahora lo único que bajaba era una plantilla **vacía** de recetas: servía
  para la primera carga y para nada más — corregir el rendimiento de treinta
  recetas ya cargadas exigía abrir treinta fichas. Ahora las tres entidades
  tienen `…/exportar` en el mismo formato que `…/plantilla`: lo que baja se
  edita en Excel y se vuelve a subir sin traducir nada. Exportar pide permiso de
  **lectura**, no de escritura: son los mismos datos del listado, empaquetados.
- **El catálogo de artículos se carga de golpe** (RN-INV-023):
  `GET /inventory/articulos/plantilla`, `/exportar`, `POST /importar/validar`
  (multipart) e `/importar`. Dos hojas —`Artículos` y `SKUs`— con la misma
  revisión en dos fases que ADR-046 fijó para recetas. Desbloquea de paso la
  peor arista del importador de recetas: cuando el archivo nombraba un insumo
  que no existía, la única salida era irse a `/inventario/articulos` y crearlo a
  mano, uno por uno.
- **El padrón de clientes se carga de golpe** (RN-PTS-007):
  `GET /sales/clientes/plantilla`, `/exportar`, `POST /importar/validar` e
  `/importar`, con permiso propio **`sales.gestionar_clientes`**. Reescribir el
  padrón del grupo desde una planilla no es el mismo acto que registrar a
  alguien en el mostrador, que es lo que hace el cajero con `sales.crear`.
- **La carga de clientes no consulta a SUNAT ni a RENIEC.** `crear_cliente`
  pregunta por el nombre cuando se registra de a uno; trescientas filas serían
  trescientas llamadas externas secuenciales dentro de un solo request, contra
  una cuota (ver `fixed-consulta-documento-visible-y-con-cuota.md`). Se agregó
  `consultar_documento=False` y la planilla manda sobre el nombre; cuando el
  cliente se edita de a uno, SUNAT vuelve a mandar.
- **La E/S de `.xlsx` vive una sola vez, en `src/shared/planilla.py`**: abrir,
  mapear la cabecera, descartar filas vacías, el tope de filas, y convertir una
  celda a texto, número, booleano, fecha o UUID. Lo que **no** se construyó es
  un motor genérico con descriptores de columnas: qué hojas tiene cada libro y
  qué cuenta como "ya existe" son tres significados distintos, y un DSL que
  exprese los tres se lee peor que los tres archivos planos que evita. La regla
  de módulos ya lo hacía imposible de todos modos —`sales` no puede importar de
  `inventory`— y `shared` es el único domicilio legal.
- **Se lee por nombre de cabecera, no por posición de columna.** El parser de
  ADR-046 leía la columna 0, así que agregar `ID` a la izquierda habría roto en
  silencio cualquier archivo ya llenado. Ahora agregar o reordenar columnas no
  rompe nada, y una columna que falta da un error que **la nombra**.
- **La fase de validación pasa a tener `response_model`.** Devolvía un dict
  crudo, así que `openapi.json` la documentaba como `{}` y los tipos del
  frontend no los verificaba nadie — el mismo agujero para las tres entidades.
- Costo aceptado: los **SKU solo se crean**, no se editan (no existe
  `editar_sku`); uno con el código ya usado se informa y no se toca. Y el
  código interno de un artículo sigue siendo de **4 caracteres únicos en todo
  el grupo**: el importador lo exige y valida su largo por fila en vez de
  autogenerarlo, porque un código inventado termina tecleado en una orden de
  compra. Ambas quedan registradas en la deuda del módulo.
