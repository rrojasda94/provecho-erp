# Deuda técnica — Frontend (F2 — arquitectura y UX, documento 2026-07-27, actualizado tras ADR-013)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-08-12 **El sistema visual, cerrado (ADR-037).** Lo que se salda y lo
  que queda:
  - **Tokens que faltaban** (F2.3): elevación (`--sombra-1..3`), estados
    semánticos (`--status-*` con su `-surface`), escala de letra
    (`--font-scale`), y el bloque de modo oscuro. Sigue sin tokenizarse el
    espaciado —la escala de Tailwind alcanza— y los estados hover/focus, que
    viven como clases de componente.
  - **`@custom-variant dark` faltaba en `globals.css`.** Tailwind v4 no
    declara la variante `dark` por estrategia de clase: las decenas de clases
    `dark:` que `shadcn add` ya había dejado escritas en `components/ui/**`
    **no compilaban a nada**. No fallaban ni avisaban. Solo se descubre
    mirando el navegador.
  - **Preferencias de accesibilidad en el perfil** (F2.14): implementadas, con
    tres columnas nuevas en `usuario` y `PATCH /users/me/preferencias`.
  - **Paleta de comandos** (F2.29) y **esqueletos por módulo** (F2.31).
  - **Ayuda contextual por campo** (`CampoFormulario`), pendiente de ui-ux.md
    desde julio.
  - **Sigue abierto**: el breadcrumb por ruta recorrida (especificado, sin
    construir), los `<dialog>` a mano de trece pantallas —hoy vestidos por
    descendencia desde `.erp`, que es un parche con fecha de vencimiento—, y
    la auditoría de contraste par por par sobre las pantallas ya construidas.
    Los tokens cumplen AA; las combinaciones concretas de cada pantalla no se
    verificaron una por una.

- ✅ 2026-08-10 **El ERP no sabía corregir nada.** Sabía crear y listar; un
  RUC mal tecleado o un cargo que cambió solo se arreglaban por `curl`. El
  diagnóstico no era el que parecía: **el backend ya tenía `PATCH` para casi
  todo** —personas, usuarios, proveedores, artículos, categorías, unidades de
  medida, trabajadores, cuentas contables, divisas y los cinco de
  organización—; lo que faltaba era la pantalla. Cada listado se había
  construido con el mismo molde (`TablaDatos` + un `<dialog>` de alta) y ahí
  se detuvo.
  - **Botón "Editar" en la fila** de seis pantallas existentes y **ocho rutas
    nuevas** (Personas, Clientes, Categorías, Unidades de medida, y el módulo
    Organización con sus cuatro). Detalle en `CHANGELOG.md`.
  - **`components/formulario/dialogo-formulario.tsx`**: el shell del diálogo
    estaba copiado en siete pantallas y con la edición encima habrían sido
    veinte. Las altas ya existentes se migraron en el mismo cambio — dejar dos
    formas de hacer lo mismo es peor que la duplicación que se venía a sacar.
  - **Módulo `organizacion` nuevo en `lib/modulos.ts`**, con
    `prefijoPermiso: "organizacion."`. No es una sección de Gerencia ni de
    Usuarios porque el permiso real es `organizacion.gestionar`: colgarlo de
    otro prefijo se lo escondería justo a quien sí lo tiene. Fundar empresa y
    renombrar grupo aparecen solo para la cuenta de administración
    (`esCuentaDeAdministracion`, misma condición que `_solo_superusuario`).
  - **Dos bugs encontrados al verificar en el navegador**, que es para lo que
    sirve verificar en el navegador:
    1. **React 19 resetea solo el formulario** cuando la acción va en el prop
       `action` de `<form>`, también cuando la acción devolvió error: corregir
       un RUC y errarle al plazo de crédito dejaba el diálogo abierto con el
       RUC viejo de vuelta. La acción se despacha ahora a mano dentro de una
       transición. Es el mismo candado que `e2e/caja.spec.ts` ya probaba para
       el conteo de caja, y que el resto de los formularios no tenía.
    2. El **seeder de e2e** sembraba `id_interno` de ocho caracteres en una
       columna `String(4)` (ver Deuda → CI/CD y el fragmento de changelog):
       SQLite no aplica el largo, Postgres sí.
  - **Verificado end-to-end** (API + Next contra la SQLite desechable de e2e,
    por navegador): alta y corrección de persona con el 409 de versión
    desactualizada mostrado y el formulario intacto; sucursal a `inactiva`;
    documento completado a un cliente natural con `identificado` pasando a
    "Sí" y el botón desapareciendo; `id_interno` duplicado devolviendo un 409
    legible dentro del diálogo; nombre visible de una cuenta persistido. Sin
    errores de consola.
  - **Deuda que deja**: desde un `PATCH` sigue sin poderse *vaciar* un campo
    opcional (`null` = "no tocar"); solo `frecuencia_conteo` tiene centinela
    (`quitar_frecuencia`). El resto se cambia por otro valor, no se borra. El
    día que una pantalla lo pida de verdad, es un centinela por campo o un
    `Field` con valor especial — no un `None` ambiguo.
  - **Fuera de alcance a propósito**: las licencias de marca a empresa
    (N:N) siguen otorgándose por API; `asiento_contable_config` de una
    categoría también (es un `dict` de configuración contable, no un campo de
    formulario).

- ✅ 2026-08-07 **Un fetch caído se dibujaba igual que "no hay datos".** El
  patrón `.catch(() => setLista([]))` estaba en cuatro lugares y dejó sin
  diagnóstico posible un fallo real: una venta con pago dividido no salía en
  la pestaña "Cobrados" del PDV, la venta **sí** estaba en la base, y lo
  único que la pantalla mostraba era una lista vacía — idéntica a la de un
  día sin ventas. Ahora hay un clasificador compartido
  (`frontend/lib/carga.ts`, sin dependencias, 7 casos en `lib/carga.test.ts`)
  y la regla queda escrita en `docs/product/frontend-architecture.md` §F2.10:
  **el vacío es solo para la respuesta exitosa sin filas**. El status se lee
  por forma y no por `instanceof` porque hay dos clases de error de API en el
  proyecto (`ApiError` servidor / `ErrorApi` navegador) y a un Server
  Component pueden llegarle las dos; `Falla` guarda el mensaje del servidor
  como `detalle` para no obligar a abrir DevTools. En el PDV el reintento es
  en sitio y no "recargá la página": recargar el PDV pierde los borradores
  abiertos. En el dashboard **solo el 403** sigue tragándose —ahí el catch es
  deliberado: que falte un permiso no puede dejar el tablero en blanco—; red,
  5xx y 401 se muestran con reintento (`router.refresh()`), que además tapa
  el agujero de que un error de red tumbara la página entera por no existir
  `error.tsx`.
- ⬜ **Cuatro cargas del PDV siguen con el patrón viejo**: carta, medios de
  pago, POS y caja abierta (`frontend/app/pdv/use-datos-pdv.ts`). La de la
  carta es la que más incomoda — un error de red se lee como "ningún producto
  tiene precio vigente para esta sucursal", que manda a revisar precios en
  vez de la red. No se tocaron en el cambio de 2026-08-07 por alcance; se
  migran a `Lista<T>` cuando se toque cada una.
- ⬜ **`.pdv-fallo` y `AvisoFallo` son dos componentes para lo mismo**: el
  PDV corre sobre su paleta oscura propia y el shell sobre Tailwind. Se
  unifican cuando el PDV migre a shadcn (ver punto de abajo), no antes.

- ⬜ **Migrar a `@tanstack/react-table` v9** (2026-08-08). La v9 renombró la
  API pública: `useReactTable` pasa a `ReactTable` + `createCoreRowModel`,
  `VisibilityState` deja de exportarse y `ColumnDef` toma dos genéricos. Toca
  `components/tabla/tabla-datos.tsx` y las 13 pantallas que lo usan, así
  que es trabajo propio y no un bump — se hace solo, con su verificación. El
  PR #37 la subió sin migrar nada; el CI la atrapó (jobs `frontend` y `e2e`
  en rojo) y el PR se mergeó igual, dejando `main` roto un día (ver CI/CD,
  2026-08-08). Se volvió a pinear en `^8.21.3` y el major quedó en `ignore`
  en `.github/dependabot.yml`: quitar esa entrada al hacer la migración.
- **34 hallazgos del React Compiler quedaron en `warn`** (2026-08-07). Al
  subir a Next 16 entra `eslint-plugin-react-hooks` 7, que trae las reglas
  del React Compiler. Son dos patrones repartidos en 30 archivos:
  - `react-hooks/error-boundaries` (18): Server Components que arman el JSX
    de retorno **dentro** del `try`. React no renderiza el componente en ese
    momento, así que el `catch` no atrapa nada de lo que falle al renderizar
    — el error de red sí se atrapa, el de render no. El arreglo es mover el
    `return` fuera del `try` y dejar en el `catch` solo el estado de error.
  - `react-hooks/set-state-in-effect` (16): `setState` en el cuerpo de un
    `useEffect`, que provoca un render en cascada.
  No se arreglaron en el mismo cambio a propósito: es refactor de cómo el
  frontend carga datos, no parte de subir de major, y mezclarlo dejaba un
  diff imposible de revisar. Están en `warn` (visibles en cada corrida, no
  bloquean) en `frontend/eslint.config.mjs`. Pasarlas a `error` al cerrarlas.
- **`middleware.ts` quedó deprecado** (2026-08-07). Next 16 renombró la
  convención a `proxy`; el archivo sigue funcionando y solo avisa. No se
  migró junto con el major porque ahí vive el nonce de la CSP y el cambio
  merece su propia verificación. `npx @next/codemod@canary
  middleware-to-proxy .` cuando se haga. Se vuelve obligatorio en Next 17.
- **ESLint 10 y TypeScript 7 quedan fuera hasta que su cadena publique**
  (2026-08-07). No es estar atrasado: ninguna versión publicada de
  `eslint-plugin-react` (7.37.5, peer `^9.7`), `eslint-plugin-jsx-a11y`
  (6.10.2) ni `eslint-plugin-import` (2.32.0) acepta ESLint 10, y con él el
  lint muere con un `TypeError` en `react/display-name` — ESLint 10 quitó
  `context.getFilename()`. TypeScript 7 choca con `typescript-eslint`
  (`>=4.8.4 <6.1.0`): npm resuelve el conflicto **sacando**
  `@typescript-eslint/eslint-plugin` del árbol, con lo que el lint sigue en
  verde habiendo dejado de revisar TypeScript. Los dos majors están en
  `ignore` en `.github/dependabot.yml` — quitar cada entrada cuando su
  bloqueante publique soporte.
- ✅ 2026-08-04 **ADR-013 por fin instalado.** La decisión era de
  2026-07-27 y **nunca se había ejecutado**: `package.json` no tenía ni
  shadcn ni Base UI, así que cada pantalla venía resolviendo con `<dialog>`
  nativo y `<select>` a mano. Ahora sí: `shadcn init --base base` (Base UI,
  **cero paquetes de Radix** — verificado en `package.json`, que es lo que
  la decisión "sin Radix" exigía) + 14 componentes generados en
  `components/ui/`.
  **Costo no previsto: hubo que subir a Tailwind v4.** El flag `--base base`
  solo existe en shadcn v4, que asume Tailwind v4; quedarse en v3 obligaba a
  shadcn v2, que es Radix. Se corrió el codemod oficial y se corrigió a mano
  lo que dejó mal: `@theme` con variables autorreferenciales
  (`--color-primary: var(--color-primary)`), PostCSS todavía apuntando al
  plugin viejo, y —lo más silencioso— shadcn había pisado la tipografía
  (`--font-heading: var(--font-sans)`), que habría dejado los títulos sin
  Anton. `tailwind.config.ts` desapareció: v4 es CSS-first y el tema vive en
  `globals.css`, en tres capas (marca → roles semánticos → utilidades) para
  que cambiar de marca siga siendo tocar seis colores.
  Los **colores del preset se descartaron**, como manda el propio ADR: los
  roles de shadcn (`--primary`, `--destructive`, `--chart-1..5`…) apuntan a
  la paleta Provecho, no al gris neutro de fábrica.
  Librerías autorizadas por el usuario e integradas: **Recharts** (tooltip
  con hit-testing, que era lo que faltaba de verdad — no el dibujo),
  **dnd-kit** (reemplaza el arrastre HTML5 propio; arrastre por asa y
  accesible por teclado), **react-day-picker** (calendario del rango
  personalizado) y **sonner** (los avisos del tablero pasaron de un `<span>`
  gris a toasts).
- ✅ 2026-08-12 **Rastro de navegación y "volver" histórico** (ADR-039):
  `<Rastro>` en las nueve fichas que cableaban su propio `← Sección`. El
  rastro se deriva de la ruta contra `MODULOS`/`SUBMENUS` y el `←` usa el
  historial propio, con el padre como fallback.
- ⬜ **Las fichas de artículo y de SKU no están enlazadas desde ninguna
  pantalla** (encontrado 2026-08-12 al probar el rastro):
  `/inventario/articulos/{id}` y `/inventario/skus/{id}` existen, tienen su
  ficha construida y solo se alcanzan tecleando la URL o desde el botón de
  destino de un reporte. El listado de artículos no abre la ficha de ninguna
  de sus filas.
- ⬜ **El rastro no llega al PDV, al KDS ni al lienzo**: viven fuera de
  `(app)` y tienen su propia barra. Es decisión tomada (ADR-039), no olvido;
  se revisa si alguna de las tres deja de ser una pantalla de una sola tarea.
- ⬜ **Login y PDV siguen sin migrar a shadcn**: el login conserva sus
  clases `.login-*` en `@layer components` y el PDV su CSS propio. Funcionan;
  se migran cuando se los toque, no antes. (El login se tocó el 2026-08-15
  por ADR-050 y **no** se migró: cambiar la forma de pedir el PIN y la
  librería de componentes en el mismo diff dejaba imposible revisar cuál de
  las dos cosas rompió qué.)
- ⬜ **`components/ui/**` exento del límite de complejidad de ESLint**: es
  código generado por el CLI y se regenera en cada `shadcn add`. Si alguna
  vez se edita a mano de forma sustancial, deja de ser generado y el override
  hay que revisarlo.

- ✅ 2026-08-03 **`npm audit` en cero.** Eran 4 vulnerabilidades altas:
  `brace-expansion` (la resolvió `npm audit fix`) y tres que colgaban de
  `next`. Diagnóstico: `next` **no** estaba marcado por CVEs propias — su
  `via` en el JSON del audit es exactamente `["postcss", "sharp"]`, o sea
  todo venía de que Next pinea `postcss@8.4.31` y arrastra `sharp<0.35`.
  Subir de major no arregla nada: **Next 16 pinea el mismo postcss**, y
  `npm audit fix --force` proponía `next@9.3.3` — un downgrade de 6 majors.
  Solución: `overrides` de `postcss`/`sharp` a las versiones parcheadas en
  `frontend/package.json`, y el rango de `next` subido a `^15.5.22` (que ya
  era lo instalado; `^15.3.0` daba la impresión falsa de estar atrasado).
  `tsc`, `next lint` y `next build` limpios después del cambio.

Detalle completo por sección en `docs/product/frontend-architecture.md`.
De las 6 prioridades que este documento marcaba como bloqueantes del
alfa, **ADR-013** (misma fecha, sesión distinta — arquitectura frontend:
Tailwind + Base UI, shell estilo Odoo, gate por permiso) resolvió 5:

- ✅ **F2.6 Layout general**: home de apps + sidebar por módulo (patrón
  Odoo), filtrado por permiso.
- ✅ **F2.4 Componentes base**: Tailwind CSS sobre los tokens existentes +
  Base UI (no Radix, no kit estilizado) para overlays/combobox/dialog.
- ✅ **F2.28 Permisos visuales por rol**: `GET /users/me` ya devuelve
  `permisos: string[]`; el home filtra módulos visibles, cada
  `layout.tsx` de módulo repite el check server-side.
- ✅ **F2.2 Arquitectura de carpetas**: convención por módulo definida
  (`app/(app)/[modulo]/layout.tsx` + `components/{ui,shell}`).
- ✅ **F2.8 Gestión de estado**: confirmado sin Zustand/Redux hasta que el
  carrito POS lo justifique.

- ✅ 2026-08-02 **F2.11 Tablas**: TanStack Table (headless, sin atar a un
  design system). v1 implementado (orden, búsqueda, filtro, paginación);
  v2 (congelar/mover columnas, selección masiva, scroll virtual, totales)
  diferido hasta que una pantalla real lo pida — mismas APIs, no es
  migración de librería. Componente reusable en
  `frontend/components/tabla/tabla-datos.tsx`.

**Primera implementación en código** (2026-08-02, no solo spec): shell Odoo
completo (`frontend/app/(app)/`) — home de apps con grid filtrado por
`permisos` de `/users/me`, sidebar + guard real server-side por
`[modulo]/layout.tsx` (no solo UX: entrar por URL sin el permiso cae en
"Sin permiso", no en datos). Tailwind CSS instalado, mapeado a los tokens
ya existentes (`globals.css`), sin hex nuevo. El dashboard existente se
relocalizó como primera app del shell y de paso dejó de leer `empresa_id`
del JWT sin verificar — ahora sale de `/users/me`.

**Pantallas reales** (listado TanStack + alta con `<dialog>` nativo, sin
shadcn/ui todavía — ningún formulario construido necesitó overlay
complejo):

- **Compras → Proveedores** (2026-08-02, natural agregado el mismo día):
  toggle jurídico/natural en el diálogo; natural usa `PersonaPicker`
  (componente reusable, `components/persona-picker/`) contra
  `/personas/buscar` con debounce — no un `<select>` con todo el
  catálogo, que no escala pasadas unas pocas decenas de personas.
  `ProveedorOut.persona_id` no viajaba y se agregó: sin eso, un proveedor
  natural no tenía forma de mostrarse por nombre en la tabla.
- **Compras → Órdenes de compra** (2026-08-02): ítems dinámicos (agregar/
  quitar fila, total en vivo), `idempotency_key` client-generada.
  Requirió 2 endpoints GET que no existían y bloqueaban la pantalla:
  `/api/v1/purchases/ordenes-compra` (listado) y `/api/v1/almacenes`
  (nuevo, `users`, catálogo de referencia sin `require_permission` a
  propósito pero sí escopado por tenant).
- **Inventario → Artículos** (2026-08-02): requirió
  `GET /api/v1/inventory/unidades-medida`, que tampoco existía — sin
  eso el selector de `unidad_medida_id` (obligatorio para crear) queda
  vacío. CRUD de escritura de `unidad_medida`/`categoria_udm` agregado el
  mismo día (ver Deuda técnica → Transversal) — ✅ **ya tiene pantalla
  propia** desde el 2026-08-10 (`/inventario/categorias` y
  `/inventario/unidades-medida`).
- **RRHH → Trabajadores** (2026-08-02): alta usa `PersonaPicker` (mismo
  componente que Proveedores). El gap de RBAC que esta pantalla encontró
  (`GET /personas` exigía `users.gestionar`) se cerró el mismo día con
  `GET /personas/buscar` + permiso `personas.leer` — ver Deuda técnica.
- **Ventas**: el tile del home apuntaba a `/ventas` (404); corregido a
  `/pdv` — el PDV es pantalla completa fuera del shell a propósito
  (ADR-013), no una ruta bajo `(app)`.
- **Cocina (KDS)** (2026-08-03, `frontend/app/kds/`): segunda pantalla
  completa fuera del shell, táctil y oscura como el PDV. Tarjeta por
  pedido; **un toque tacha el ítem preparado** (patrón de la *preparation
  display* de Odoo, cuya documentación se revisó antes de diseñarla) y
  "Todo listo" tacha el pedido entero. El toque encadena
  `en_preparacion → listo` porque la API solo avanza de a un estado.
  Como el avance vive en `venta_item.estado_preparacion` y ninguna
  pantalla guarda estado propio, lo tachado en una estación aparece en
  toda otra pantalla de la sucursal que muestre ese pedido — hoy con
  polling de 3 s (pausado si la pestaña está oculta). Sin "recall": el
  retroceso lo prohíbe RN-CUP-002, tocar un ítem tachado avisa en vez de
  deshacer. En pantallas de `despacho` y solo con `sales.entregar_pedido`
  aparece "Entregar" (RN-CUP-006). Estación elegida en la URL
  (`/kds?pantalla=<id>`) para que cada tablet la deje en favoritos; sin ese
  parámetro `/kds` muestra el **tablero de estaciones**, que es a la vez el
  selector y la configuración (alta/edición/baja lógica de `kds_pantalla`
  con `kds.configurar`, filtro por categorías contra
  `GET /inventory/categorias`). Antes las pantallas solo se creaban por
  API: una sucursal nueva no tenía forma de arrancar su cocina desde la UI.
  De paso, el cliente HTTP de navegador se extrajo a `lib/cliente-api.ts`
  (lo compartían PDV y KDS). **Un solo cambio de backend**, encontrado
  justamente al verificar end-to-end: `cola_pantalla` devolvía a una
  pantalla de preparación solo los ítems `pendiente`/`en_preparacion`, así
  que tachar un ítem lo hacía desaparecer de la tarjeta — lo contrario de
  lo que necesita la cocina. Ahora la estación ve todos sus ítems con su
  estado y el pedido sale de su cola cuando terminó todo lo suyo (test
  `test_item_tachado_sigue_visible_hasta_terminar_la_estacion`).
  **Verificación end-to-end** (2026-08-03, stack Docker completo, datos
  reales): venta takeout de 3 ítems creada por API; ambas estaciones
  ("Horno" preparación, "Pase / Despacho") creadas **desde la UI**; tachar
  "Inca Kola" en una tablet y verla tachada (`line-through`) en una
  segunda tablet de la misma estación sin tocarla, por polling; "Todo
  listo" → los 3 ítems en `listo` en la BD; la pantalla de despacho
  muestra el pedido LISTO con "Entregar"; entrega registrada → ítems
  `entregado` y ambas colas vacías. `tsc`, `next lint`, `next build` y los
  12 tests de `tests/test_kds.py` en verde.

Verificado end-to-end en Docker con datos reales, por API y por navegador
(curl + interacción real): crear artículo → aparece en tabla; crear OC de
2 ítems → total correcto; crear trabajador → nombre resuelto; crear
proveedor natural con `PersonaPicker` → nombre resuelto en la tabla. Sin
errores de consola.

- **Usuarios** (2026-08-04): cuentas con sus roles editables **en la fila**
  —asignar y quitar rol es lo que más se hace acá y un modal por cambio
  sería un clic de más cada vez—, alta de cuenta, activar/desactivar y
  filtro por rol. Subpantalla **Roles** como acordeón, no tabla: cada rol
  tiene decenas de permisos y una celda con 30 etiquetas no se lee; el
  selector de permisos va agrupado por módulo (`optgroup`) porque el
  catálogo pasa los 90. Requirió **dos GET que no existían y sin los cuales
  la pantalla era inútil**: `GET /users/{id}/roles` (el token trae nombres,
  no ids, así que no se podía desasignar nada) y `GET /roles/{id}/permisos`
  (asignar un rol sin ver qué habilita es justo el error a evitar).
- **Contabilidad** (2026-08-04): cinco pantallas. *Asientos* — listado,
  alta manual con líneas dinámicas y **cuadre en vivo** (RN-CTB-001: el
  error típico es un monto de más y verlo antes de enviar ahorra el viaje),
  y anulación por asiento inverso. *Periodos* — abrir y cerrar; se sumó al
  verificar la pantalla end-to-end: el primer asiento de una empresa nueva
  falla con "no hay periodo contable abierto" y hasta ahora abrirlo era
  exclusivamente por API, o sea que la pantalla de asientos no se podía
  estrenar sin curl. *Plan de cuentas* — listado y alta con cuenta padre. *Pagos a proveedor* — cola filtrada a pendientes por
  defecto, con ejecutar (medio de pago + constancia) y rechazar; el nombre
  del proveedor se resuelve contra `/purchases/proveedores` y si el contador
  no tiene ese permiso la pantalla sigue viva mostrando el id, mismo
  criterio que Proveedores con las personas. *Caja* — turnos abiertos con
  su efectivo esperado, leídos del reporte `estado_caja` del catálogo
  (ADR-024) en vez de recalcular el mismo número por segunda vez; abrir y
  cerrar siguen por API porque cada paso exige el PIN del encargado
  (RN-MDP-002) y esa pantalla va con el PDV.
- **Producción** (2026-08-04): órdenes con su ciclo real —crear, registrar
  el consumo que la cocina sacó de verdad, cerrar con el control de
  calidad—. La columna de acciones muestra **solo el paso que aplica** al
  estado de la orden (consumo en `borrador`, completar en `en_proceso`):
  ofrecer el otro solo invita al 409. El diálogo de cierre cambia según el
  resultado (cantidad producida si es conforme, evidencia de destrucción si
  se desecha). Requirió `GET /production/ordenes` **paginado, que no
  existía**: solo se podía ver una orden sabiendo su id, o sea que la cocina
  no tenía forma de mirar su propia jornada.
- **Marketing** (2026-08-04): *Campañas* con el ciclo brief → aprobada → en
  curso → cerrada; la tabla dice **qué campo del brief falta** en vez de
  fallar recién al aprobar, y el botón de aprobar aparece solo si el usuario
  tiene `marketing.campana_aprobar` — quien redacta el brief no lo aprueba
  (RN-MKT-003), así que ofrecerlo a todos sería prometer un 403.
  *Contenido* con el calendario de piezas y sus dos validaciones de marca
  como etiquetas que se tocan (RN-MKT-001/002); publicar queda deshabilitado
  hasta que las dos estén. Requirió `GET /marketing/piezas` (tampoco
  existía) y `GET /api/v1/marcas` en `users`: el de `sales` exige
  `sales.leer` y pedirle eso a un usuario de marketing para llenar un
  `<select>` sería abrirle la carta entera.
- **Gerencia** (2026-08-04): *Parámetros* como bandeja —filtrada a
  pendientes por defecto— con las tres salidas de ADR-014 Addendum: aprobar,
  aprobar **modificando el valor**, o rechazar con motivo obligatorio. El
  formulario de propuesta obliga a elegir **qué clase de magnitud** es el
  valor (monto con divisa, cantidad con unidad de medida, o adimensional),
  que es exactamente lo que RN-GER-010 exige y lo que el backend responde
  422 si falta. *Decisiones* con el acta (RN-GER-002): el campo de
  condiciones aparece y se vuelve obligatorio solo al elegir "aprobado con
  condiciones", y el botón de firmar solo existe con `gerencia.decidir` —
  el área ejecutora lee pero no firma (RN-GER-005). *Divisas* con sus
  decimales, que son los que deciden el redondeo de todo importe en esa
  moneda.
- **Ventas — back-office** (2026-08-04): la jornada de una sucursal por
  fecha y estado, con totales (cobradas, monto, sin cobrar), el comprobante
  de cada venta y sus dos acciones reales: **reintentar la emisión** que
  SUNAT rechazó —mostrando el detalle del rechazo y los intentos— y
  **anular** una orden que nunca se cobró. Los filtros viven en la URL: la
  jornada de una sucursal en una fecha es una dirección que se comparte.
  El tile del home pasó a apuntar acá y el PDV se abre desde su sidebar;
  antes el tile iba directo al PDV y lo administrativo no tenía puerta.
- ✅ 2026-08-04 **Deriva de esquema detectada y con guard permanente**
  (`src/core/esquema.py`). Hallada al abrir la pantalla de Gerencia: la base
  local de Docker estaba seis migraciones atrás y —peor— tenía
  `1805c0904c5c` marcada como aplicada sin que `decision_gerencial`
  existiera, así que `GET /decisiones-gerenciales` respondía 500 con CI en
  verde (`alembic check` compara modelo contra migraciones **sobre una base
  limpia**, no contra la base real; por eso no lo vio). Ahora hay
  `python -m src.core.esquema` —tablas del modelo que faltan en la base, más
  revisión de `alembic_version` contra la cabeza del repo— y el mismo
  chequeo corre **al arrancar**: en producción aborta, en desarrollo avisa
  (`src/main.py`). Se compara solo existencia de tablas, no columnas: el
  grueso del daño con muy poco código, sin los falsos positivos de comparar
  tipos por dialecto. 8 tests. Base local ya corregida.
- ✅ 2026-08-04 **Supabase corregida** (autorizado por el usuario). Estaba en
  `b6d1e83f47ac` con cinco tablas ausentes: `decision_gerencial` —de una
  revisión que ya figuraba aplicada, el mismo defecto de marca falsa que la
  local— y `alerta_pedido`, `notificacion`, `pos_tarjeta` y `tablero`, de
  cuatro migraciones que nunca corrieron. Se creó primero la tabla de la
  revisión marcada con el SQL de esa misma revisión y después
  `alembic upgrade head`. Quedó en `f3a1c62d90b4`, 95 tablas, sin deriva
  (`python -m src.core.esquema` → 0) y con los datos previos intactos. Las
  cuatro migraciones eran aditivas (tablas nuevas y una columna nullable),
  por eso no hubo que tocar datos.
- ⬜ **La jornada pide el comprobante venta por venta** (N+1 contra la API):
  aceptable para un día de una sucursal, no para un histórico. Si aparece
  el listado de varios días, el comprobante tiene que venir en el listado
  o en un endpoint por lote.
- ⬜ **Marketing sin pantalla de leads ni de encuestas**: el backend las
  tiene (`/leads`, `/encuestas`, atribución lead→venta) pero la UI cubre
  campañas y contenido. Van cuando haya campañas reales corriendo.
- ⬜ **Producción sin plan ni checklist de inocuidad**: la pantalla cubre la
  orden ad-hoc, que es lo único que el backend implementa hoy
  (`plan_produccion` y `checklist_inocuidad_turno` siguen en deuda del
  módulo).
- ✅ 2026-08-06 **Pruebas e2e del flujo del dinero — verdes y en CI.**
  `frontend/e2e/caja.spec.ts` recorre abrir caja → vender → cobrar → cerrar
  contra la API real (SQLite desechable sembrado por `src/seeders/e2e.py`),
  más RN-POS-011. Corre con `npm run test:e2e` desde `frontend` y como job
  `e2e` de `ci.yml`, con `test-results/` subido como artefacto cuando falla.
  Cuatro corridas seguidas en verde, una de ellas con `.next` borrado.
  Lo que estaba roto y por qué, que es lo que vale del episodio:
  1. ✅ El `env` del `webServer` de Playwright **no llega** al proceso hijo
     en este entorno. La API corría contra el `.env` del repo —o sea contra
     **Supabase**— y Next se iba al `localhost:8000` por defecto, donde en
     Windows la conexión no rebota: se cuelga. Resuelto con dos lanzadores
     (`e2e/servidor-api.mjs`, `e2e/servidor-web.mjs`) que fijan la variable
     dentro del proceso que la usa.
  2. ✅ `waitForURL` no sirve tras una Server Action: el `redirect` lo
     resuelve el cliente y nunca dispara el evento `load`. Se espera el
     contenido del destino.
  3. ✅ **La prueba se saltaba el tipo de orden.** El PDV no deja cobrar sin
     él (RN-COM-005), así que el primer "Cobrar" abría el diálogo de tipo y
     no el de cobro. No era un bug de la pantalla: era la prueba tomando un
     atajo que el cajero no tiene. Ahora pasa por el candado —"Para llevar",
     el único que no pide dato extra— y recién después cobra.
  4. ✅ **El `SyntaxError: Unexpected end of JSON input` era el timeout
     disfrazado.** El presupuesto del test eran 90 s y `next dev` compila
     cada ruta la primera vez que alguien la pide —login, home, PDV, la ruta
     de proxy—; la corrida moría a mitad de camino y el `expect` que quedaba
     colgando era el que aparecía en el reporte. Como cada corrida dejaba la
     caché más tibia, el fallo se movía de paso en paso, que es exactamente
     lo que hace pensar en flakiness. Con 240 s el recorrido completo entra
     en ~96 s. **No hizo falta pasar a `build`+`start`**, y con eso queda sin
     efecto lo que decía este punto sobre el origen de las Server Actions.
- ✅ 2026-08-06 **Los tres casos que la estrategia da por justificados,
  cubiertos.** `docs/engineering/testing-strategy.md` limita el e2e a tres
  cosas y ninguna es una regla de negocio; con el flujo del dinero ya verde,
  faltaban las otras dos. **7 casos** en total.
  `e2e/sesion.spec.ts` (nuevo): una ruta protegida sin sesión manda al
  login; el login deja el token en cookie **httpOnly** —se afirma el
  atributo, que no se ve en ninguna pantalla y por eso se rompe en
  silencio— y el logout la mata de verdad (la ruta protegida vuelve a
  rebotar, no solo cambia la pantalla); y el **gate de módulo por permiso**
  probado **entrando por URL directa**: el cajero no ve Catálogo ni
  escribiendo `/catalogo/productos`, y el admin sí. El par importa — un gate
  que esconde el módulo para *todos* pasaría por bueno con la mitad de la
  prueba, y es justo el agujero que la enmienda a ADR-013 cerró.
  `e2e/caja.spec.ts` suma el candado que faltaba: **un rechazo del servidor
  deja el formulario abierto con lo tecleado**. Recontar el cajón entero
  porque alguien erró seis dígitos del PIN es la clase de fricción que
  termina en un conteo inventado, y ese conteo es la evidencia sobre la que
  se calcula el descuadre del turno.
  Seeder: `cajero_e2e` (rol `cajero`), el usuario con menos permisos que
  igual opera una pantalla — es con él que se verifica qué **no** se ve.
  Helpers compartidos en `e2e/util.ts` (no es `.spec.ts` a propósito:
  Playwright solo recolecta `*.spec.ts`).
  Deuda que deja: fuera del PDV, el resto de las pantallas del ERP sigue sin
  prueba, y el job tarda ~5 min porque levanta Next en modo desarrollo.
- ✅ 2026-08-06 **Test de contrato cliente↔servidor** — el que la estrategia
  declaraba prioridad desde el 2026-08-05, por encima de más e2e.
  `frontend/lib/contrato.test.ts`: **58 casos en ~250 ms**, sin servidores.
  Son **dos capas, y la primera pesa más**:
  **(1) El tipo.** Los cinco cuerpos de request del PDV viajaban como
  `Record<string, unknown>` — o sea sin contrato del lado del cliente, que
  es exactamente por donde entró el bug de ADR-025. Tipados desde
  `openapi.json` (`VentaNueva`, `PagoNuevo`, `AperturaCajaNueva`,
  `CierreCajaNuevo`, `MovimientoCajaNuevo`), `tsc` los verifica en **cada
  punto de llamada** y ya corre en CI vía `npm run build`.
  **Tiparlos destapó cinco desacuerdos el mismo día**: `modalidad` podía
  viajar `null` (el guard existía, el tipo no lo sabía); `pos_verificados`
  estaba tipado con `PosVerificado` —lo que se **lee**, con `serie`— cuando
  el request es `PosVerificadoIn` sin ella; y `custodia`/
  `descuadre_atribucion` eran `string` suelto sobre dos columnas `Enum`, que
  es la misma clase de agujero que se cerró el 2026-08-05 en el schema del
  servidor y seguía abierta del lado del cliente.
  **(2) El test.** Por cada una de las 19 operaciones de `lib/pdv.ts`, con
  `fetch` intervenido: que la ruta y el método existan en el contrato, que
  el cuerpo valide contra su `requestBody`, y —alimentando al cliente con
  una respuesta **generada desde el contrato**— que la sepa leer. Esto
  último es lo que caza ADR-026: el cliente recibe `{items, total, …}` de
  verdad y tiene que devolver un array.
  El validador cubre solo lo que se rompe en silencio (requerido que no
  viaja, campo que el contrato no conoce, tipo equivocado). `pattern`,
  `minimum` y enums los rechaza el servidor con un 422 que se ve; replicarlo
  sería mantener dos validadores desincronizándose — y si algún día hace
  falta, la respuesta es una librería de JSON Schema, no hacer crecer eso.
  **Verificado por mutación**, que es lo único que prueba que un test verde
  pueda ponerse rojo: reintroducidos los dos bugs históricos más un endpoint
  renombrado, los tres fallan nombrando la operación y el campo.
  `npm test` entra al job `frontend` de CI: los 72 casos del frontend
  **nunca habían corrido en CI** (el job hacía solo `lint` y `build`).
- ✅ 2026-08-06 **Contrato extendido al resto del frontend** — **162 casos
  en ~350 ms**. Cubre en dos profundidades, y la diferencia importa:
  **(a) Los cuatro módulos importables** —`pdv` (19 operaciones),
  `catalogo` (20), `kds` (7), `reportes` (6)— exponen la API como objeto
  llamable y se ejercitan de verdad: ruta, método, cuerpo y lectura de la
  respuesta. Cada lista se compara contra el objeto real del módulo, así que
  **una operación nueva sin caso hace fallar el test** en vez de quedar sin
  cubrir. El arnés ahora respeta el código de respuesta del contrato: un
  `204` se responde vacío de verdad, que es la rama de `pedir` que existe
  porque pedirle `.json()` a una respuesta sin cuerpo revienta.
  **(b) Todo el resto** —Compras, Inventario, RRHH, Gerencia, Contabilidad,
  Marketing, Usuarios— llama desde Server Components y Server Actions, que
  piden `next/headers` y un request y **no se pueden importar** en un
  `node --test`. Para esos hay un escaneo del código fuente: toda ruta que
  el frontend nombra debe existir en el contrato con ese método. **~170
  llamadas** en un test de 14 ms. Caza lo que antes no cazaba nada: un
  endpoint renombrado en el backend rompe veinte pantallas y el diff de
  `openapi.json` no sabe quién lo llamaba.
  Un caso no se puede resolver estáticamente —
  `marketing/campanas/${id}/${paso}`, donde el último segmento toma tres
  valores literales— y en vez de dejarlo como agujero se declara con sus
  tres valores y se verifican **todos**. El test además exige un piso de
  llamadas encontradas: si alguien cambia cómo se llama a la API, el escaneo
  devolvería cero y pasaría por vacío.
  **Cinco mutaciones, cinco rojos**: los dos bugs históricos, un endpoint
  renombrado en `lib/`, otro renombrado en un Server Action, y una operación
  nueva sin caso. `npm test` pasa de 72 a **176 casos**.
  Deuda que deja, sin adornos: **el cuerpo que arman las pantallas del
  back-office no está verificado** — de esas solo se comprueba la ruta. Se
  cierra moviendo sus llamadas a módulos importables como los cuatro que ya
  lo son, no escribiendo otro tipo de test.
- ⬜ **Los enums de la base no tienen una sola fuente en el frontend**: la
  pantalla de caja repite los valores de `custodia`, `descuadre_atribucion`
  y los estados en constantes propias. Mientras el `pattern` del schema los
  valide, un desalineado da 422 y no una fila corrupta —que era el problema
  real—, pero generar estas listas desde `openapi.json` evitaría tener que
  acordarse. No antes de que haya un tercer lugar que las repita.
- ⬜ **La bandeja de notificaciones no se abre en la pantalla del PDV ni en
  el KDS**: las dos viven fuera del shell (`app/pdv`, `app/kds`) y no llevan
  barra superior. Un cajero no se entera de un pedido demorado por la
  campana; se entera por el KDS. Va cuando exista push (mismo pendiente).

Todo lo demás (theming multi-marca, accesibilidad — catálogo ya definido,
tiempo real de KDS, i18n, hardware, testing — Playwright ya decidido por
ADR-013, observabilidad, printing, productividad, multitarea) tiene
decisión tomada, está correctamente diferido, o depende de un módulo
backend que todavía no llega a pantalla.
- ⬜ **La cadena de estaciones se ordena tecleando un número** (2026-08-13,
  ADR-044): el formulario de estación pide "Paso en la cocina" como entero.
  Es correcto y se explica en dos líneas, pero reordenar tres estaciones
  obliga a editar tres veces, e insertar una en el medio exige el truco de
  dejar huecos (0, 10, 20). Arrastrar la lista sería la interfaz honesta —
  `@dnd-kit` ya está en el proyecto (lo usa el tablero de reportes).
- ⬜ **El pinpad no muestra el PIN ni siquiera un instante** (2026-08-13,
  ADR-045): solo puntos. Es lo correcto para una caja a la vista del
  público, pero sin un "ojo" para revelar, un error de tecleo solo se
  descubre al fallar el envío — y fallar cuesta un intento del lockout.
  Falta el botón de revelar mientras se mantiene pulsado.
- ⬜ **El bloqueo del PDV no avisa antes de bloquear** (2026-08-13): a los
  5 minutos aparece de golpe. Quien está contando efectivo al lado de la
  caja no toca la pantalla y se la encuentra bloqueada sin haber podido
  evitarlo. Un aviso a los 4:30 con "seguir aquí" lo resuelve.

- ✅ 2026-08-15 **El login se teclea en el pinpad** (ADR-050, enmienda a
  ADR-045). `app/login/page.tsx` seguía pidiendo el PIN en un
  `<input type="password" autocomplete="current-password">`: el patrón exacto
  que ADR-045 había eliminado dentro del PDV, en la pantalla que más veces se
  cruza y desde la misma tablet de la caja. El pinpad salió de `app/pdv/` a
  `components/pinpad/` y su CSS de `pdv.css` a `globals.css`, pidiendo los
  colores a los tokens `--pdv-*` **con respaldo** en los del back office
  (`var(--pdv-rojo, var(--primary))`): una sola regla sirve a la paleta
  oscura del mostrador y al modo claro/oscuro de ADR-037. De paso, el login
  dejó de tratar igual al 401, al 423 y al 429.
  - **Deuda que deja, dos puntos concretos:**
    - ⬜ **`frontend/app/pdv/pinpad.tsx` quedó como re-export de una línea.**
      Es un puente a propósito: había otra rama trabajando sobre
      `app/pdv/dialogos.tsx` (900 líneas) y cambiarle el `import` desde acá
      era un conflicto garantizado sobre un archivo que este cambio no tenía
      por qué tocar. **Se borra** cambiando los dos `import Pinpad from
      "./pinpad"` de `dialogos.tsx` y `bloqueo.tsx` a
      `@/components/pinpad/pinpad`, en la rama que los toque.
    - ⬜ **El overlay de bloqueo del PDV se pinta con tokens que no existen
      ahí** (encontrado al mover el CSS). `BloqueoPorInactividad` se monta
      como **hermano** de `<main className="pdv">` en `app/pdv/page.tsx`, no
      dentro, y los `--pdv-*` están definidos en `.pdv`/`.pdv-vacio`: cada
      `var(--pdv-bg)` / `var(--pdv-texto)` de `.pdv-bloqueo` es inválido al
      calcular y la declaración entera queda en `unset`, o sea overlay con el
      fondo blanco del navegador en vez de la paleta oscura del PDV. El
      pinpad de adentro ya no lo sufre —sus reglas llevan respaldo—, el
      overlay sí. Se arregla montándolo dentro de `.pdv` o repitiendo los
      tokens en `.pdv-bloqueo`; no se hizo acá porque cambia cómo se ve una
      pantalla que este cambio no venía a tocar y merece su verificación.
    - ⬜ **`frontend/app/cambiar-pin/` sigue con tres
      `<input type="password">`** (PIN actual, nuevo y repetido). Es el
      último PIN del ERP que se escribe en un campo. No entró acá porque es
      otro flujo y otra decisión de diseño —tres pinpads en una pantalla, o
      uno con tres pasos— y mezclarla dejaba un cambio imposible de revisar.
      Mientras tanto es un campo `type="password"` que el navegador ofrece
      guardar, con el mismo defecto que ADR-045 describe.
