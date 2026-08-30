- **La orden de compra era «un ente aislado e inútil»** (2026-08-30). Emitir,
  recibir, anular y dar conformidad existen como endpoints y con test verde
  desde que existe el módulo; lo que faltaba era quién los llamara. El listado
  ofrecía «Editar» y **solo** en `borrador`: una OC emitida no tenía ninguna
  acción en ninguna pantalla. Ahora hay ficha (`/compras/ordenes-compra/[id]`)
  con las cuatro acciones según estado y permiso, el historial de recepciones
  y la factura que la sustenta. El formulario de recepción viene precargado
  con lo que falta y pide lote y vencimiento solo donde significan algo
  (RN-VNC-002).
- **No se podía crear una compra con su factura.**
  `POST /purchases/compras-directas` existe desde el 2026-08-29 (ADR-082) y
  ninguna pantalla lo llamaba. Ahora `/compras/directas` registra la compra y
  el papel en un paso y termina en la ficha de la OC que crea. Ruta propia y
  no un diálogo del listado: la paleta de comandos lee `SUBMENUS`, y un
  diálogo escondido no se puede buscar por nombre.
- **Las facturas recibidas no se podían listar.** No había ningún endpoint de
  lectura de comprobantes recibidos —el de `sales` es de los emitidos—, así
  que una factura registrada solo se volvía a ver entrando a su OC, si uno
  recordaba cuál. Nuevo `GET /purchases/comprobantes` (paginado, por proveedor
  y por rango de fechas, abierto también a `accounting.leer`) y la pantalla
  `/compras/facturas`.
- **La columna «origen» que ADR-082 prometió.** Sus Consecuencias decían que
  las pantallas de OC distinguirían la compra directa «donde importa» y nunca
  se hizo: ahora hay columna y filtro.
