# Deuda técnica — Contrato de API (tras la implementación de 2026-07-26 — ADR-010)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ⬜ **Campos que la API sirve y nadie lee** (2026-09-05, lo que queda del
  hallazgo #18). El informe de la auditoría los enumeraba; el roadmap
  resumido no, y adivinar cuáles son mirando el código es exactamente cómo se
  borra un campo que sí usaba alguien. Hace falta cruzarlo contra el informe
  —o repetir el barrido— antes de tocar nada: un campo servido de más cuesta
  poco, y quitarlo mal cuesta una pantalla rota.

- ✅ 2026-08-04 **Paginación real** (`{items, total, page, page_size}`,
  ADR-026): `src/shared/paginacion.py` (sobre `Pagina[T]`, dependencia de
  query params con `page_size` máximo 200, y `paginar()` que cuenta y corta
  **en la base**). Aplicada a los **18 listados operativos** —ventas del
  día, artículos, stock, movimientos, solicitudes, transferencias,
  proveedores, órdenes de compra, asientos, pagos a proveedor, trabajadores,
  postulantes, campañas, leads, personas, usuarios y notificaciones— y **no**
  a los catálogos de configuración (roles, divisas, unidades de medida,
  medios de pago, mesas, plan de cuentas…): la frontera es qué hace crecer
  la tabla, no cuántas filas tiene hoy. Cada repo expone `q_list()` (la
  consulta sin ejecutar) junto a su `list()`, así que solo el router cambia.
  Frontend migrado (5 fetchers) y `openapi.json` regenerado.
  `tests/test_paginacion.py` (9 casos).
- ✅ **Los controles de paginación de la tabla son del cliente, no del
  servidor** (cerrado 2026-09-23, enmienda a ADR-026). `TablaDatos` acepta
  `servidor={{ total, page, pageSize, q }}`: buscar y paginar cambian la URL
  y el Server Component vuelve a pedir. Lo usan Artículos y el libro
  contable (Asientos, que ganó `?q=` sobre la glosa). El resto de los
  listados trae **todas** las páginas con `apiFetchCompleto`/`apiFetchTodas`
  (`lib/api.ts`): ~45 llamadas cortaban en silencio en la fila 200 —o en la
  50, donde ni se pasaba `page_size`—, incluidos proveedores, trabajadores y
  usuarios. `AvisoRecortado` quedó solo en Producción, que pagina con enlaces.
- ⬜ **Pasar a `servidor` los listados que crezcan a decenas de miles**
  (traslados, ajustes, conteos, facturas de proveedor): hoy los trae enteros
  de a 200, que alcanza para años de un grupo de este tamaño pero no escala
  sin techo. Hace falta `?q=` en cada endpoint antes de migrar su pantalla.
- ⬜ **Listados que quedaron fuera de la primera pasada** (misma regla, una
  línea cada uno cuando su pantalla exista): `stock-lote` (devuelve tuplas,
  no entidades), clientes del contrato público de `sales`, arqueos, conteos
  y movimientos de caja.
- ⬜ **Paginación por cursor** para tablas que lleguen a cientos de miles de
  filas: `OFFSET` profundo es caro y una lista que cambia mientras se
  navega repite filas. El sobre no cambiaría, sí cómo se piden las páginas
  (ADR-026, alternativa evaluada y diferida).
- ⬜ **`responses={...}` por endpoint**: documentar en OpenAPI qué código de
  error devuelve cada operación específica (hoy es una convención global en
  `api-guidelines.md`, no anotada endpoint por endpoint). Mejora real pero
  mecánica sobre ~100 rutas ya en producción — incremental, al tocar cada
  router por otra razón.
- ⬜ **Ejemplos de request/response** en los schemas Pydantic
  (`json_schema_extra`): el contrato exportado no trae ejemplos, solo tipos.
- ⬜ **Publicar el contrato fuera del repo** (portal de API) si aparece un
  consumidor externo real que lo pida — descartado por ahora en ADR-010.
