# ADR-069 — Las mesas se numeran solas, se retiran de a una y tienen plano

- **Estado:** aceptada
- **Fecha:** 2026-08-27
- **Contexto:** `sales` (`mesa`, mapa de mesas, reportes), PDV
- **Relacionado:** ADR-018 (creó `mesa` y el mapa de ocupación), ADR-004
  (alcance por tenant), ADR-024 (catálogo de reportes, sin query builder)

## Contexto

ADR-018 dejó `mesa` con alta manual y sin baja de verdad: `POST /sales/mesas`
recibía el número a mano, no existía `PATCH`, y `desactivar_mesa` solo apagaba
`activa` sin mirar si la mesa tenía historia. Nada de eso tenía pantalla —
las únicas mesas que existían eran las doce del seeder de demo
(`src/seeders/pdv_demo.py`), y una sucursal nueva quedaba con el mapa del PDV
diciendo «esta sucursal no tiene mesas configuradas todavía» sin ninguna
salida. El pedido fue completar ese CRUD: crear, editar, retirar, y además
saber qué mesa prefiere la gente por sucursal.

`desactivar_mesa` también tenía un hueco de tenant: era la única de las cuatro
rutas que no llamaba `tenant.exigir_sucursal`, así que un supervisor podía
desactivar la mesa de otra empresa conociendo su id.

## Decisión

### El número lo asigna el sistema, nunca el cliente

`crear_mesa` ya no recibe `numero`: toma `max(numero de mesas activas) + 1`.
El salón se numera 1..n sin huecos por construcción — no hay forma de crear
"la mesa 7" salteando la 5 y la 6, y "Mesa 3" significa siempre la misma mesa
en el historial de ventas, porque el número no se vuelve a tocar.

### Solo se retira la mesa de número más alto

`eliminar_mesa` rechaza con 409 cualquier retiro que no sea el de `numero`
máximo ("el salón se numera 1..n; retira primero la mesa N"). Es la única
regla que mantiene 1..n exacto sin dos alternativas peores:

- **Renumerar el resto** (borrar la 3 de 8 y correr 4..8 a 3..7) mantiene el
  rango pero reescribe a qué mesa apuntó una venta ya cerrada — un reporte de
  ayer diría "Mesa 4" de una mesa que hoy es la 3.
- **Dejar el hueco** (borrar la 3 y quedar 1, 2, 4..8) conserva el historial
  pero rompe la regla que se pidió: secuencial del 1 al n.

Una mesa que nunca tuvo ventas se borra de verdad; una que sí las tuvo queda
`activa=False`, conservando su número y su celda para cuando la próxima mesa
que se crea la reactive en el mismo lugar en vez de insertar una fila nueva
— así se evita chocar contra el único de `(sucursal_id, numero)`.

Ni editar ni retirar proceden si la mesa tiene una orden abierta
(`venta.estado = "orden"`, sin importar la fecha — el propio ADR-018 dejó el
control de `desactivar_mesa` mirando solo la fecha de hoy, que dejaba pasar
una orden abierta desde ayer). Mover o renombrar una mesa que el mozo está
sirviendo confunde más de lo que ordena.

### El plano es una grilla de celdas, no coordenadas libres

`mesa.pos_x`/`pos_y` son enteros (columna, fila), base 0, únicos por
sucursal. El croquis del salón se arma arrastrando una mesa de celda a celda
en una grilla de `rules.MESA_COLUMNAS = 12` columnas — ni el modelo ni la
UI cargan con posición en píxeles, rotación, forma de la mesa o zoom. `zona`
sigue siendo la etiqueta de texto libre que ya era ("Salón", "Terraza"); el
plano no la reemplaza, solo ubica.

Se eligió celda sobre píxel porque lo único que hace falta es "estas dos
mesas no están una encima de la otra" y "cuál va antes en la fila" — un
croquis, no un editor de planos arquitectónico. Si algún día hace falta
rotar una mesa redonda contra una rectangular, esa decisión se revisa con
más columnas, no reescribiendo esta.

### Se quita `mesa.deleted_at`

`Mesa` tenía `SoftDeleteMixin` desde ADR-018 pero nada escribía `deleted_at`
—el borrado siempre fue `activa=False`—, así que era una segunda fuente de
verdad muerta que ya se había colado en dos lecturas (`por_numero`,
`de_sucursal`) filtrando una columna que ninguna escritura tocaba. Con el
borrado real (fila sin historia) o `activa=False` (fila con historia) como
únicos dos estados, mantener la columna era el mismo riesgo que describe
ADR-018 para `mesa.ocupada`: dos fuentes de verdad para un mismo hecho se
desincronizan el primer día que alguien las use distinto.

### `DELETE /sales/mesas/{id}` reemplaza `POST /mesas/{id}/desactivar`

La ruta vieja no tenía llamadores en `frontend/` (nadie la usaba) y era la
única de las cuatro sin `tenant.exigir_sucursal` — el hueco descrito arriba.
La ruta nueva pasa por `scope.exigir_mesa`, el mismo patrón que ya usan
`exigir_cliente` y `exigir_venta`.

### El reporte de preferencia reutiliza el criterio de "ingreso real"

`mesas_preferidas` vive en `application/queries_publicas.py` y reusa el
predicado `_ventas_en_rango` que ya comparten `ventas_por_dia`,
`ventas_por_usuario` y el resto de reportes de venta (`estado` en
`pagada`/`facturada`). Si el ranking de mesas usara otro criterio, un
gerente podría leer un total de "mesas preferidas" que no cuadra con
"ventas por sucursal" del mismo rango — mismo mes, dos números.

Se agrega al catálogo de `core/reportes` (ADR-024): un `Reporte` declarado
con sus columnas, sin endpoint propio ni query builder. La etiqueta de cada
fila lleva la sucursal adentro ("CH1 · Mesa 4") porque el gráfico de barras
solo dibuja una columna de etiqueta y "Mesa 4" se repite entre locales.

### Dónde vive la pantalla

`/ventas/mesas`, no `/organizacion/...`. El permiso es `sales.gestionar_mesas`
(ya existía, sin uso) y el propio `README.md` del módulo ya distinguía
"configurar el salón" (esto) de la identidad fiscal del punto de venta que sí
vive en Organización (ADR-059).

## Alternativas descartadas

- **Numeración manual con validación de rango.** Más libertad para el
  administrador, más formas de dejar un hueco o de dos personas pidiendo el
  mismo número a la vez. El pedido explícito fue 1..n sin negativos ni
  huecos; automático es la única forma de garantizarlo sin un lock adicional.
- **Retirar cualquier mesa y renumerar el resto.** Ver arriba — reescribe el
  historial.
- **Coordenadas libres (x, y en píxeles) para el plano.** Permite mesas
  redondas, rotación, zonas superpuestas — nada de lo que se pidió. Cuesta un
  editor de arrastre con colisión geométrica en vez de una comparación de
  enteros, y la UI del PDV pasaría de una grilla CSS a un canvas.
- **Un endpoint propio para el ranking de mesas en vez del catálogo de
  reportes.** El catálogo ya resuelve tablero, filtro de sucursales y
  permisos; un endpoint aparte duplicaría eso para una sola consulta.

## Consecuencias

- **Migración `a1f9c3e7b204`**: agrega `pos_x`/`pos_y` (backfill desde
  `numero`, para que las mesas existentes aparezcan ya ordenadas en el
  croquis), agrega `uq_mesa_sucursal_posicion`, quita `mesa.deleted_at`.
- El seeder de demo (`pdv_demo.py`) pasa a asignar `pos_x`/`pos_y` explícitos
  en vez de dejar el valor por defecto — doce mesas con el mismo `(0, 0)`
  habrían chocado contra el nuevo único.
- El mapa de mesas del PDV (`GET /sales/mesas/mapa`) y la nueva pantalla
  admin comparten la misma grilla de 12 columnas vía `gridColumn`/`gridRow`
  en CSS — ninguna reescribe el layout, solo cambia de dónde sale la
  posición de cada celda.
- Deuda anotada en `ROADMAP.md`: el plano es uno solo por sucursal (no
  separa por `zona`) y `mesas.mapa()` sigue siendo N+1 sobre los ítems de
  cada venta abierta (ya lo era desde ADR-018).
