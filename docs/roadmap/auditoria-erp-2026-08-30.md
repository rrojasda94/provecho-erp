# Roadmap — fixes de la auditoría backend↔frontend (2026-08-30)

Origen: auditoría exhaustiva de gap analysis backend↔frontend (sesión
2026-08-30). Informe completo con archivo:línea de cada hallazgo:
https://claude.ai/code/artifact/4052b934-5e96-43dd-bc29-ecf4fe8812b9

Cada bloque = una rama + una sesión de Claude Code + un PR al cerrar.
Nombre de bloque = nombre de rama. Los bloques de una misma ola no tocan
archivos en común entre sí — se pueden trabajar en paralelo, en sesiones y
días distintos. Dentro de un bloque, ir haciendo commits según avance;
abrir el PR cuando el bloque completo esté verde (CI + pruebas).

## Ola 0 — BLOQUEANTE: el inventario no se puede poblar (2026-08-30)

Reportado por el usuario en operación real: «inventario no tiene forma de
agregar productos, las compras tampoco suman, todos los almacenes aparecen
vacíos, el conteo no puede realizarse». Verificado en código: **no es un
problema de permisos ni del camino feliz del backend** (la recepción de OC
sí suma stock; el listener está registrado en `src/core/app.py:326` y hay
tests que lo prueban — `tests/test_purchases.py:273`). Son tres fallos
encadenados:

1. **Crear un artículo NO crea su SKU.** `crear_articulo`
   (`src/modules/inventory/application/catalogo.py:217-247`) solo inserta
   `Articulo`. `POST /inventory/skus` (`routers.py:351`) no tiene pantalla:
   0 llamadas desde el frontend. La **única** vía de UI que crea SKUs es la
   importación por Excel (hoja `SKUS`,
   `importacion_articulos.py:478-491`). Quien da de alta artículos a mano
   queda con artículos sin SKU — y sin SKU **es físicamente imposible que
   exista stock**, porque `Stock` y `StockLote` cuelgan de `sku_id`.
2. **La recepción de compra falla en silencio.** `on_compra_recibida`
   (`src/modules/inventory/application/listeners.py:464-518`) busca el SKU
   activo del artículo; si no lo encuentra, hace `_omitir(tipo="sin_sku")`
   y `continue`. **La API responde 201, la OC pasa a «recibida», y el stock
   nunca entra.** La constancia queda en `IncidenciaInventario`, tabla que
   no tiene endpoint ni pantalla. Además el handler traga toda excepción
   (`listeners.py:515-518`) y el bus la vuelve a tragar
   (`src/core/events.py:63-70`): cualquier otro error también es invisible.
3. **No hay ninguna otra vía de entrada de stock desde la UI.** Sin
   pantalla: carga inicial, alta de SKU, registro de movimiento de entrada,
   creación de lote, **creación de ajuste** (la pantalla de Ajustes solo
   aprueba/rechaza: `ajustes-cliente.tsx:63-68`) y transferencias.

Consecuencia: el conteo **es un efecto, no una causa**. `abrir_conteo`
deriva sus ítems de las filas de `stock` del almacén
(`inventory/application/conteos.py:55-66,116`); almacén vacío → conteo con
cero ítems → no se puede cerrar (`conteo-cliente.tsx:292`). La pantalla sí
está en el menú (`frontend/lib/navegacion.ts:50-64`) y `admin` tiene
comodín `*`, así que **no era falta de permiso**.

### `fix/inventario-entrada-de-stock` — primera y sola, antes que todo

Una sola rama porque los tres fallos son el mismo flujo. Orden sugerido de
commits:

| # | Cambio | Archivos | Por qué |
| --- | --- | --- | --- |
| 1 | **SKU automático al crear artículo** (uno por artículo, código derivado del `id_interno`; los multi-SKU siguen entrando por Excel) | `src/modules/inventory/application/catalogo.py:217-247` | Ataca la raíz: sin esto, todo lo demás sigue sin poder acumular stock. Verificar que la importación por Excel no duplique SKUs |
| 2 | **La recepción deja de fallar en silencio**: devolver en la respuesta los ítems omitidos y su motivo, y mostrarlos en la ficha de OC | `listeners.py:464-518`, `src/modules/purchases/application/ordenes.py:347`, `frontend/app/(app)/compras/ordenes-compra/[id]/orden-compra-cliente.tsx` | Que una recepción que no movió stock no se vea idéntica a una que sí |
| 3 | **Formulario de creación de ajuste** en la pantalla que ya existe (`POST /inventory/ajustes`, permiso `inventory.solicitar_ajuste` ya definido) — cubre carga inicial y correcciones con el flujo de aprobación ya construido | `frontend/app/(app)/inventario/ajustes/` | Es la vía de entrada de stock con menos código nuevo: endpoint, permiso, pantalla y flujo de aprobación ya existen. **Verificar primero** si `crear_ajuste` exige fila de `stock` previa; si la exige, usar `POST /inventory/movimientos` con `tipo: "ajuste"` |
| 4 | **Backfill**: script o migración que cree el SKU faltante de los artículos ya dados de alta a mano | `scripts/` o alembic | Sin esto, los artículos existentes siguen rotos |
| 5 | **403 disfrazado en conteos**: `GET /conteos/{id}` exige `inventory.contar`, pero la página trata todo lo que no es 404 como «No se pudo cargar el conteo» | `frontend/app/(app)/inventario/conteos/[id]/page.tsx:22-26` | Un `supervisor` (que no tiene `inventory.contar` en el seeder, `seed.py:364-374`) ve la fila, hace clic y recibe un error engañoso |
| 6 | **Pruebas**: recepción de artículo sin SKU; alta de artículo → SKU creado; ajuste de entrada → stock visible en `GET /inventory/stock` | `tests/` | Hoy ningún test cubre el camino que falló |

Diagnóstico de datos antes de empezar (dos consultas deciden el alcance del
backfill): `SELECT * FROM incidencia_inventario WHERE tipo = 'sin_sku'` y
contar artículos sin SKU activo.

Sube de prioridad, en consecuencia: `feat/inventario-transferencias-mermas`
pasa de la Ola 3 a la Ola 2 — con el stock ya entrando, mover entre
almacenes es lo siguiente que la operación multi-sucursal necesita.

## Ola 1 — día 1, 6 ramas en paralelo (sin archivos compartidos)

| Rama | Hallazgos | Archivos | Sev. | Esfuerzo |
| --- | --- | --- | --- | --- |
| `fix/ventas-estados-y-emision` | #1 filtro de estados roto + #3 botones reintentar-emisión/NC/anular sin gate + #11 error tragado en líneas de NC | `frontend/app/(app)/ventas/jornada-cliente.tsx`, `frontend/app/(app)/ventas/actions.ts`, `src/modules/sales/api/routers.py:264` | Alto | ~1 día |
| `fix/personas-tipo-documento` | #2 «RUC» en alta de persona → 500 | `frontend/app/(app)/usuarios/personas/personas-cliente.tsx:36`, `src/modules/users/api/schemas.py:90` | Alto | horas |
| `fix/postulacion-publica` | #5 enlace público de postulación sin página | nueva `frontend/app/(publico)/postular/[token]/`, `frontend/app/(app)/rrhh/contratacion/page.tsx:28` | Alto | 1–2 días |
| `fix/rrhh-remuneracion-y-token-supervisor` | #6 remuneración expuesta con solo `rrhh.leer` + #7 token de autorización replayable | `src/modules/rrhh/api/schemas.py:64-80`, `src/modules/users/application/autorizacion.py:106-125` | Medio | ½ día |
| `fix/error-boundary-y-timezone` | #8 falta `app/error.tsx` + #9 hora +5 en fichas server | nuevo `frontend/app/error.tsx`, `frontend/app/(app)/inventario/skus/[id]/page.tsx:167`, `frontend/app/(app)/inventario/devoluciones/[id]/page.tsx:95`, `frontend/Dockerfile` (fijar `TZ`) | Medio | ½ día |
| `fix/errores-422-legibles` | #12 mensaje 422 sin nombre de campo | `frontend/lib/api.ts:50-61`, `frontend/lib/cliente-api.ts:23-34` (helper único, alcance acotado — no tocar los 16 `actions.ts` consumidores todavía) | Medio | ½ día |

## Ola 2 — día 2–3, 5 ramas en paralelo (arrancan sin esperar la ola 1)

| Rama | Hallazgos | Archivos | Sev. | Esfuerzo |
| --- | --- | --- | --- | --- |
| `fix/contabilidad-pagos-rbac` | #3 botones ejecutar/rechazar pago sin gate + #4 diálogo con reset-on-error + #11 rechazo de pago sin feedback | `frontend/app/(app)/contabilidad/pagos/pagos-cliente.tsx` | Alto | 1 día |
| `fix/contabilidad-asientos-rbac` | #3 botón «+ asiento manual» sin gate + #4 diálogo con reset-on-error + #16 cuadre en float sin redondeo | `frontend/app/(app)/contabilidad/asientos-cliente.tsx` | Medio | 1 día |
| `fix/rbac-botones-resto` | #3 botones trabajadores/artículos/devoluciones/OC sin gate | `frontend/app/(app)/rrhh/trabajadores/trabajadores-cliente.tsx`, `frontend/app/(app)/inventario/articulos/articulos-cliente.tsx`, `frontend/app/(app)/inventario/devoluciones/devoluciones-cliente.tsx`, `frontend/app/(app)/compras/ordenes-compra/[id]/orden-compra-cliente.tsx` | Medio | 1–2 días |
| `fix/dialogos-migracion-sweep` | #4 resto de los ~19 diálogos con reset-on-error, migrar a `DialogoFormulario` | `marketing/campanas-cliente.tsx` (2 diálogos), `produccion/ordenes-cliente.tsx`, `gerencia/decisiones/decisiones-cliente.tsx`, `contabilidad/caja/caja-cliente.tsx`, `gerencia/delivery/*`, `gerencia/kds/*`, `gerencia/parametros/parametros-cliente.tsx`, `rrhh/contratacion/*` | Alto | 2–3 días |
| `fix/sesion-expirada-cliente` | #10 sesión muerta sin salida (bucle KDS, campana muda, borradores sin guardar) | `frontend/app/kds/use-cola.ts`, `frontend/components/shell/campana.tsx`, `frontend/app/pdv/use-borradores-pdv.ts` | Medio | ½ día |

Nota: si `fix/dialogos-migracion-sweep` y `fix/contabilidad-pagos-rbac` /
`fix/contabilidad-asientos-rbac` corren al mismo tiempo, coordinar quién
toca `pagos-cliente.tsx`/`asientos-cliente.tsx` primero — esos dos ya
incluyen su propia migración del diálogo, así que el sweep debe *excluirlos*
de su alcance (ya están cubiertos arriba).

## Ola 3 — funcionalidad nueva, arrancar cuando haya capacidad (independientes entre sí y de las olas 1-2)

Cada uno es una pantalla nueva sobre un módulo distinto — sin cruce de
archivos entre ellos.

| Rama | Hallazgo #13 (bloque) | Módulo |
| --- | --- | --- |
| `feat/inventario-transferencias-mermas` | Transferencias, mermas y reservas sin pantalla — **movido a Ola 2** tras la Ola 0 | inventory |
| `feat/rrhh-nomina-permisos-disciplina` | Solicitudes de permiso, nómina, disciplina, contratos, legajo | rrhh |
| `feat/contabilidad-arqueos-libro-mayor` | Arqueos, reglas de asiento, libro mayor, detalle de asiento | accounting |
| `feat/auditoria-pantalla` | Pantalla de auditoría (`GET /api/v1/auditoria`) | core |
| `feat/marketing-leads-encuestas-agencia` | Leads, encuestas, evaluación de agencias | marketing |
| `feat/reports-matriz-edicion` | Edición de áreas/reglas/miembros de distribución | reports |

## Ola 4 — calidad, baja urgencia, en paralelo cuando convenga

| Rama | Hallazgos |
| --- | --- |
| `fix/paginacion-server-side` | #14 `page_size=200` client-side en 17 sitios + lotes sin tope |
| `fix/contrato-tests-y-tipos-duplicados` | #15 extender `test_repo_coherencia` a las ~15 listas de enums + consolidar tipos TS duplicados (`Sucursal` ×14, etc.) |
| `fix/accesibilidad-insignia-aria-live` | #17 píldoras solo-color → `Insignia`, `aria-live` en avisos KDS/PDV |
| `chore/limpieza-menor` | #18 `inventory.ajustar` huérfano, campos servidos e ignorados, CDR no descargable, cookie terminal sin rotación |

## Cómo usar esto en sesiones separadas

Al abrir una sesión nueva, pasarle: *"trabaja el bloque `<nombre-de-rama>`
del roadmap de auditoría, ver `docs/roadmap/auditoria-erp-2026-08-30.md`"*.
Cada sesión: crea la rama, hace commits incrementales según avanza, corre
`ruff`/`eslint`/pruebas, y abre el PR contra `main` solo cuando el bloque
completo esté en verde (los 6 jobs del CI, rama al día con `main`).
