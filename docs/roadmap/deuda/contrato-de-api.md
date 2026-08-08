# Deuda técnica — Contrato de API (tras la implementación de 2026-07-26 — ADR-010)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

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
- ⬜ **Los controles de paginación de la tabla son del cliente, no del
  servidor**: `tabla-datos.tsx` (TanStack) pagina de a 10 **sobre las filas
  que ya recibió**, así que "página 1 de 1" habla de la página del servidor,
  no del total. Con 50 filas por request no se nota; falta cablear
  `page`/`page_size` a los controles antes de la primera sucursal con meses
  de historia.
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
