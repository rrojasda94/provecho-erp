# ADR-026 — Paginación de colecciones: qué se pagina y qué no

- Estado: aceptado
- Fecha: 2026-08-04

## Contexto

Ninguna colección de la API paginaba. `api-guidelines.md` llegó a afirmar
lo contrario y se corrigió en 2026-07-26 documentando el formato real
(array plano), dejando la paginación como deuda declarada en ADR-010.

Hoy hay ~60 endpoints de colección y las primeras pantallas reales ya están
construidas sobre ellos. El costo de cambiar el formato crece con cada
pantalla nueva: hacerlo ahora toca 5 fetchers, hacerlo en tres meses toca
veinte.

La decisión difícil no es *cómo* paginar —`LIMIT`/`OFFSET` con un `COUNT`—
sino **dónde**: paginar todo uniforma el contrato pero obliga a desenvolver
un sobre para leer las once unidades de medida que existen; paginar nada
deja la API sin defensa el día que `movimiento_inventario` tenga un millón
de filas.

## Decisión

**Se pagina lo que crece con la operación. No se paginan los catálogos de
configuración.**

La frontera es el origen del volumen, no el tamaño actual de la tabla:

- **Paginado** — cada fila nace de una operación del negocio: una venta, un
  movimiento de stock, una orden de compra, una persona, un postulante, una
  notificación. Su tamaño crece solo, sin que nadie lo decida, y nadie lo
  puede acotar.
- **Plano** — cada fila la crea alguien configurando el sistema: roles,
  permisos, divisas, unidades de medida, categorías, medios de pago,
  sucursales, almacenes, puntos de venta, mesas, pantallas KDS, listas de
  precio, plan de cuentas, periodos contables. Un humano las escribe una por
  una; son decenas y se consumen enteras (llenar un `<select>`, pintar la
  carta del PDV).

Los 18 endpoints paginados en esta primera pasada: ventas del día,
artículos, stock, movimientos de inventario, solicitudes, transferencias,
proveedores, órdenes de compra, asientos, pagos a proveedor, trabajadores,
postulantes, campañas, leads, personas, usuarios y notificaciones.

Piezas:

- `src/shared/paginacion.py` — el sobre `Pagina[T]`
  (`{items, total, page, page_size}`), la dependencia `paginacion` que
  valida los query params y `paginar(session, consulta, p)`, que cuenta y
  corta.
- Cada repositorio expone `q_list(...)` (la consulta **sin ejecutar**) junto
  a su `list(...)` de siempre. El router pagina la consulta; el resto del
  código sigue llamando a `list()` sin enterarse.

El corte va **en la base**: traer 10 000 filas para quedarse con 50 tendría
el mismo costo que no paginar.

`page_size` tiene techo duro de 200. Sin él, `page_size=1000000` es una
forma cómoda de tumbar la API con una sola petición autenticada.

## Alternativas descartadas

- **Paginar todo, sin excepciones.** Contrato uniforme, pero cada
  `<select>` del frontend paga un `.items` y un `COUNT(*)` sobre una tabla
  de once filas. La uniformidad no es gratis cuando la mitad de los
  endpoints no la necesitan.
- **Cursor / keyset (`?desde=<id>`).** Es lo correcto para volúmenes
  grandes y para listas que cambian mientras se navegan, y no sufre el
  `OFFSET` caro de las páginas profundas. Pero no da `total` —y "página 3
  de 12" es justo lo que pide una pantalla de gestión— ni permite saltar a
  una página arbitraria. Se reevalúa si aparece una tabla con cientos de
  miles de filas; el sobre no cambia, cambia cómo se piden.
- **`COUNT(*) OVER ()` en la misma consulta.** Ahorra un viaje a la base,
  pero obliga a cada listado a devolver una columna extra y a sacarla antes
  de serializar. Dos consultas simples valen más que una acoplada.
- **Paginación en memoria** (traer todo y cortar en Python). Es media hora
  de trabajo y deja el problema exactamente donde estaba, con el agravante
  de que el contrato ya diría que está resuelto.

## Consecuencias

- Los 18 endpoints devuelven `{items, total, page, page_size}`: **cambio de
  contrato**, no compatible hacia atrás. El frontend ya está migrado
  (5 fetchers) y `docs/architecture/openapi.json` regenerado.
- Un cliente que no manda `page`/`page_size` recibe las primeras 50 filas.
  Antes recibía todo: **un listado con más de 50 filas se ve truncado hasta
  que el cliente pagine**. Es el punto que hay que mirar al construir cada
  pantalla nueva.
- Los controles de paginación de `tabla-datos.tsx` (TanStack) son
  **del cliente**: parten en páginas de 10 las filas ya recibidas. Ahora
  paginan una página del servidor, no la tabla entera. Cablearlos a
  `page`/`page_size` queda anotado en el ROADMAP.
- Los listados que componen DTOs (`/inventory/stock`) paginan la consulta
  base y componen solo las filas de la página.
- Fuera de esta pasada, con la misma regla y una línea cada uno cuando su
  pantalla exista: `stock-lote` (devuelve tuplas, no entidades), clientes
  del contrato público de `sales`, arqueos, conteos y movimientos de caja.
