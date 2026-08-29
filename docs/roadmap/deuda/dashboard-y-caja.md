# Deuda técnica — Dashboard y caja (tras la implementación de 2026-07-26 — ADR-012)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ **Seeder sin sucursal semilla** — **la entrada estaba obsoleta**
  (verificado 2026-08-04): `_seed_organizacion` sí crea las sucursales de
  `SUCURSALES` y el bloque final de `seed()` asigna `admin` a todas, así
  que `build_claims` deriva `empresa_id` sin intervención manual. Se
  confirmó levantando el stack y entrando al dashboard con `admin` recién
  sembrado.
- ✅ 2026-08-04 **Ciclo de caja completo** (ADR-025, migración
  `f3a1c62d90b4`). Cuatro deudas cerradas de una: **no se cobra sin caja
  abierta** (`sales.registrar_pago` pregunta por el contrato público
  `accounting.hay_caja_abierta`; el replay del hub es la única excepción,
  porque el cobro ya ocurrió en la sucursal); **el monto sale del conteo
  por denominación** y no del teclado (RN-POS-003/007 — en la apertura la
  diferencia contra lo declarado por el encargado se calcula y no bloquea
  abrir, RN-POS-011); **cada relevo lo firma quien recibe con su PIN**
  (RN-MDP-002, reusando la elevación de `POST /auth/autorizar` con el
  permiso nuevo `accounting.caja_relevar`, y `custodia_efectivo` pasa a ser
  máquina de estados real hasta `disponible`); y **un cierre con faltante
  se corrige sin reescribirse** (reapertura con motivo y autorizador en
  `cierre_caja.correcciones`, solo mientras el efectivo siga en el local).
  Suma `pos_tarjeta` (serie + código de comercio, RN-POS-010; el de
  emergencia es una fila con `sucursal_id` NULL, RN-POS-009) y la
  verificación de terminales al abrir, que marca el averiado y avisa sin
  bloquear. `efectivo_esperado` del reporte de caja y el arqueo ahora
  descuentan `movimiento_caja`. RN-POS-012/013 quedan fuera de código a
  propósito: son organizativas y viven en el SOP. 17 tests nuevos
  (`tests/test_caja_ciclo.py`).
- ✅ 2026-08-15 **El cajero abre y cierra su turno solo** (ADR-049, migración
  `c8b41f60d2a7`, RN-MDP-008; enmienda el punto 3 de ADR-025). Abrir y
  cerrar dejaron de pedir elevación de PIN: basta `accounting.caja_operar`,
  que el rol `cajero` ya tenía. La firma con `accounting.caja_relevar` no se
  debilitó, **se movió a donde la plata cambia de manos**: al cerrar, el
  efectivo queda `en_caja` a nombre del cajero, y el encargado firma la
  recepción después (`en_caja → en_supervisor`). Sin migración de estados —
  `en_caja` ya estaba en el enum y en la tabla de transiciones desde el
  primer día y **el sistema no lo escribía nunca**, porque la custodia nacía
  en `en_supervisor` con la firma que traía el cierre.
  **Lo que arregla en el local**: exigir que un encargado viniera a firmar
  cada apertura se pagaba dejando su sesión abierta en la caja todo el turno
  — la firma que existía para probar quién tenía el efectivo producía el
  escenario que hace imposible probarlo. Y el sistema declaraba entregado a
  las 23:00 lo que se entregaba a las 09:00 del día siguiente, con el
  faltante del medio a nombre de quien no había tocado la plata.
  De paso, la ventana de RN-MDP-005 se ensancha hacia el lado correcto:
  recontar con el efectivo todavía en el cajón pasó de ser un estado
  inalcanzable a ser el caso normal. `apertura_caja.relevo_encargado_id`
  queda NULLABLE (no se borra: las aperturas anteriores conservan quién
  firmó). Contrato: `AbrirCajaIn`/`CerrarCajaIn` pierden `autorizacion`.
  Frontend: los diálogos del PDV pierden el bloque de firma y
  `/contabilidad/caja` muestra el escalón `en_caja` que nunca se había
  podido ver. Recorrido de uso nuevo: `frontend/uso/caja-custodia.spec.ts`.
- ⬜ **El encargado no puede ver los turnos que tiene que recibir** (deuda
  nueva de ADR-049): `GET /accounting/cajas/turnos` exige `accounting.leer`
  y el rol `supervisor` no lo tiene, así que hoy firma la recepción del
  efectivo sobre la pantalla de alguien que sí pueda abrirla. Funciona
  —toda elevación por PIN es así— pero la pantalla donde vive el botón
  "Recibe el encargado" no la puede abrir el encargado. El arreglo
  probablemente sea el patrón que ya usa `GET /cajas/abiertas`: aceptar
  `caja_operar` cuando la consulta viene acotada a una sucursal.
- ⬜ **El cajero no ve los terminales que tiene que verificar al abrir**
  (RN-POS-010, encontrado escribiendo el recorrido de uso de ADR-049):
  `GET /accounting/pos-tarjeta?sucursal_id=` exige `accounting.leer`, el
  cajero no lo tiene, y el PDV se come el 403 con un `.catch(() => [])`. La
  apertura queda sin `pos_verificados`, así que el cierre tampoco cuadra
  tarjetas y **nada lo dice en pantalla**. No lo causó ADR-049 —la apertura
  siempre corrió sobre la sesión del cajero— pero ahora que él es el
  operador esperado la regla queda muerta en la práctica. Mismo arreglo
  candidato que la entrada anterior, más dejar de tragarse ese 403.
- ⬜ **Ya no se sabe quién es el encargado de turno** (deuda nueva de
  ADR-049): `accounting.queries_publicas.encargado_de_turno` salía del
  `relevo_encargado_id` de la caja abierta y devuelve `None` para toda
  apertura nueva. `reports` cae en su respaldo por rol (`supervisor`/`admin`
  de la sucursal, ADR-036), que dejó de ser la excepción y pasó a ser el
  camino normal: los avisos siguen llegando, a más gente y menos dirigidos.
  Recuperarlo de verdad necesita una **fuente propia** —un turno de
  personal—; derivarlo de la caja fue un atajo que funcionó mientras la caja
  obligaba a dos personas.
- ⬜ **El turno de caja no se replica al hub** (deuda nueva de ADR-025): el
  push del hub reproduce el cobro con `exigir_caja_abierta=False` porque la
  nube no conoce la apertura que sí existió en la sucursal. Sincronizar
  `apertura_caja`/`cierre_caja` abre preguntas propias (¿quién cierra un
  turno que empezó offline?) — no antes de que haya un hub real corriendo.
- ✅ 2026-08-04 **El cierre cuadra tarjetas** (RN-POS-004): exige el reporte
  de lote de **cada POS que abrió operativo** —uno averiado no cobró nada,
  así que no se le pide— y contrasta la suma contra lo cobrado con tarjeta
  en el turno (contrato público `sales.total_tarjeta_cobrado`, crédito y
  débito juntos: al arqueo le importa el total que el lote respalda).
  `descuadre_monto` sigue siendo **el del cajón** —es la plata que alguien
  responde— y el de tarjetas viaja en `montos_esperados`/`montos_reales`;
  cualquiera de los dos deja el cierre irregular. Un local sin terminales
  verificados no tiene nada que cuadrar y el cierre no le pide nada.
- ⬜ **Pagos por link de pago sin verificación automática al cierre**
  (RN-POS-008): hoy nada los concilia ni los computa en la caja principal
  de la sucursal. Llega con la integración de pasarela (Izipay).
- ✅ 2026-08-05 **Caja con pantalla, y dos columnas que se estaban
  corrompiendo.** El PDV ya tenía diálogos de apertura y cierre, pero
  hablaban el contrato **anterior** a ADR-025 (`monto_apertura` en vez de
  `monto_declarado`, `relevo_encargado_id` en vez del token de
  `autorizacion`, `monto_real` en vez del conteo por denominación): las dos
  operaciones respondían 422 desde el 2026-08-04 y nadie lo había notado
  porque ningún test cubre esa pantalla. Ahora la apertura pide lo declarado
  por el encargado —y muestra la diferencia contra lo contado sin bloquear,
  RN-POS-011— y la verificación de terminales; el cierre pide el reporte de
  lote de cada POS que abrió operativo, el destino del efectivo y el PIN de
  quien recibe.
  **El hallazgo de fondo**: `cierre_caja.custodia` y
  `cierre_caja.descuadre_atribucion` son **enums** en la base, y el schema
  los declaraba `str` sin validar. La pantalla mandaba texto libre ("Juan el
  encargado" en el destino del efectivo), la escritura pasaba, y la fila
  quedaba **ilegible**: cualquier lectura posterior reventaba con
  `LookupError` al mapear el enum. Se valida con `pattern` en el borde (422)
  y la UI ofrece los valores reales — el destino es *a dónde va la plata*,
  no quién la recibe, que ya lo prueba la firma. Dos tests congelan cada uno.
  Del lado de contabilidad, `GET /accounting/cajas/turnos` (nuevo) lista los
  turnos cerrados con su descuadre y el tramo de custodia, y la pantalla
  `/contabilidad/caja` suma cadena de custodia firmada con PIN, reapertura
  con motivo e inventario de POS. `CajaAbiertaOut` gana `pos_verificados`:
  es lo único que le dice al cierre a qué terminales pedirles lote.
  Verificado en navegador: ciclo completo abrir → cerrar → recibir custodia →
  reapertura rechazada por RN-MDP-005.
- ✅ 2026-08-05 **`GET /ventas` genérico**: rango de fechas (`desde`/`hasta`,
  ambos inclusivos, por defecto hoy), sucursal opcional dentro del alcance
  del tenant y filtro por punto de venta. Un solo endpoint para el PDV y el
  back-office en vez de uno por uso. De paso apareció una **regresión que
  llevaba desde la paginación del 2026-08-04**: el endpoint pasó a devolver
  `{items, total, ...}` y `lib/pdv.ts` lo seguía leyendo como array, así que
  las pestañas de cobrados y de pedidos abiertos del PDV se dibujaban vacías
  sin ningún error visible (`vs.filter is not a function` lo tragaba el
  `.catch`). No había un solo test del listado por HTTP; ahora hay cuatro.
- ⬜ **Caché/paginación del agregador**: cada llamada a
  `/dashboard/resumen` recalcula todo en vivo — aceptable al volumen de hoy,
  revisar si empieza a pesar.
- ✅ 2026-08-29 **`contar_bajo_minimo` traía toda la tabla `stock` de la
  empresa a Python para contarla en un bucle**, en el engine corto del
  dashboard. Detectado al preparar el BI (ADR-081): la carga adicional de
  Superset sobre las mismas tablas iba a hacer notar el full-scan tarde o
  temprano. Ahora es un `COUNT` agregado en SQL
  (`inventory/application/stock.py`).
- ⬜ **RLS del BI (Superset) sincronizada a mano con `Tenant`** (ADR-081): el
  alcance por sucursal/empresa vive en dos puntos de aplicación —los claims
  del JWT y la vista `bi_alcance_usuario`—. `tests/test_bi_alcance.py`
  detecta la divergencia si `Tenant.sucursal_ids` cambia sin que la vista lo
  siga, pero sigue siendo dos lugares que alguien tiene que recordar tocar
  juntos.
- ⬜ **Aprovisionamiento de Superset fuera de Alembic** (ADR-081 Fase C): la
  conexión a la base, los datasets y las reglas RLS de Superset se crean con
  un script propio (`scripts/superset_init.py`, pendiente), no con las
  migraciones del ERP. Un recreo del droplet que no corra ese script deja el
  BI sin RLS.
- ⬜ **El BI (Superset) consulta la base viva, no una réplica de lectura**
  (ADR-081): mitigado con `bi_lector` de solo lectura y `statement_timeout`
  propio de 120 s, pero una consulta pesada de un año completo compite por
  recursos con el PDV. Se paga la réplica cuando eso empiece a notarse, no
  antes.
- ⬜ **Widget de embebido del BI sin construir** (ADR-081 Fase D):
  `GET /bi/dashboards/{id}/guest-token` está hecho y probado, pero
  `BI_DASHBOARDS_EMBEBIBLES` está vacía y no hay ningún dashboard real de
  Superset que embeber todavía — depende del droplet (Fase C) y de que
  alguien cure los primeros tableros. Cuando existan, falta sumar
  `@superset-ui/embedded-sdk` al frontend y el componente que lo monta en
  `/dashboard`.
- ✅ 2026-08-04 **Más indicadores → tablero de reportes** (ADR-024,
  migración `998e335369a1`). Ya no son 3 tarjetas fijas: catálogo cerrado
  de reportes (`src/core/reportes/`) + tableros guardados por usuario
  (`shared/models/tablero.py`). Cinco reportes iniciales —
  `ventas_por_dia` (serie), `ventas_por_sucursal`, `top_productos`,
  `compras_por_proveedor`, `solicitudes_por_articulo`—, rangos preset y
  personalizado, filtro de sucursales por checkbox, tarjetas con ancho
  (1-4/4) y alto ajustables, y visualización tabla/barras/líneas por
  tarjeta. `GET /reportes`, `POST /reportes/{codigo}/datos`, CRUD de
  `/tableros`. Sin constructor de consultas a propósito — el motivo está
  en el ADR. Frontend en `frontend/components/reportes/` (Tailwind,
  gráficos sin librería). 21 tests (`tests/test_reportes.py`) y
  verificación end-to-end en navegador con 290 ventas de muestra.
- ✅ 2026-08-04 **Tres reportes más** (ADR-024 Addendum): `ventas_por_hora`,
  `ventas_por_trabajador` y `margen_por_producto` — 8 en total. Dos
  decisiones que valen más que los reportes: (a) la **hora es la del
  negocio** — se agrupa en SQL sobre UTC (`extract`, lo único portable
  entre SQLite y Postgres) y la etiqueta se corre con
  `fechas.desfase_horas()`; son 24 filas, reetiquetarlas es exacto y no
  obliga a traer todas las ventas. La función falla si la zona configurada
  tuviera un desfase que no sea de horas enteras, así que la suposición
  ("Perú no tiene horario de verano") está verificada y no escrita a mano.
  (b) **costo desconocido no es costo cero**: un producto sin receta sale
  con `costo`/`margen` en `null`, porque cero mostraría 100 % de margen
  sobre un dato que falta. El costo sale de `inventory.recetas.costo_linea`
  —que ya contempla merma— en vez de recalcularse con otro criterio.
  Contratos públicos nuevos: `rrhh.nombres_por_usuario` (el primero de
  `rrhh`; expone nombre y cargo, nada de remuneración ni contratos),
  `inventory.costo_unitario_de_recetas` y tres de `sales`.
- ✅ 2026-08-04 **Exportación a CSV**, botón por tarjeta. Se arma **en el
  cliente**: los datos ya están en el navegador y un endpoint nuevo
  repetiría consulta, RBAC y rango para producir las mismas filas. Escapado
  RFC 4180 (una razón social con coma partiría la fila), BOM UTF-8 (sin él
  Excel abre "Lácteos" como mojibake) y montos crudos, no formateados —
  `S/ 1,234.50` no lo suma ninguna hoja de cálculo. Se exporta lo que se
  ve; para más filas se sube `limite` (tope 500, de seguridad). 11 tests en
  `frontend/lib/reportes.test.ts` (`npm test`).
- ✅ 2026-08-04 **Reordenar tarjetas por arrastre**, con HTML5 nativo — no
  hacía falta librería de drag-and-drop, que fue el motivo por el que se
  había diferido. Cada tarjeta lleva un `uid` estable **solo en el
  cliente** (no se persiste: el orden ya lo da el índice del array) para
  que la clave de React no sea la posición.
- ✅ 2026-08-04 **Tableros compartidos por rol** (`tablero.rol_id`,
  migración `5e1c7775f6ca`). NULL = privado; con rol, lo ve en solo lectura
  quien tenga ese rol y lo edita solo el dueño. Por rol y no por lista de
  personas porque **se administra solo**: alguien cambia de puesto y gana o
  pierde el tablero sin que nadie actualice nada, y quien cesa deja de
  verlo al perder el rol — con una lista habría que sacarlo de cada
  tablero, y el que se olvide es una fuga. Dos guardas: solo se comparte
  hacia un rol propio, y **compartir no expone datos** (cada tarjeta
  revalida el permiso de su módulo, así que quien no tenga `purchases.leer`
  ve la tarjeta en 403). Se comparte la disposición, no el contenido.
- ✅ 2026-08-04 **Caché por tarjeta**: 30 s por (reporte + filtros), en
  memoria del módulo. Un reporte es una foto, no un dato editable — no hay
  nada que invalidar salvo el tiempo. Medido en navegador: reordenar dentro
  de la ventana cuesta **0 peticiones**. Caché de verdad (compartida entre
  usuarios, invalidada por evento) iría del lado del servidor con Redis, y
  eso sigue sin caso real.
- ✅ 2026-08-04 **Alerta de KDS demorado y estado de caja como reporte**
  (migración `d4e21b0c13d0`). 13 reportes en el catálogo (10 + los tres de
  excepciones de inventario sumados el 2026-08-06).
  **`alerta_pedido`** (`sales`) con dos disparadores que convergen: el
  listener de `sales.venta_confirmada` agenda una revisión puntual a 15 min
  (`countdown` de Celery) y un **barrido de Celery beat cada 5 min** repasa
  todo lo que siga en cocina. Se mantienen los dos porque para un sistema de
  alertas el fallo que importa es **no avisar**: la tarea puntual sola se
  pierde si el worker estuvo caído o el broker soltó el mensaje, y el
  barrido solo llegaría con hasta un ciclo de retraso. Convergen sin
  duplicar por `UNIQUE (venta_id, minutos_umbral)` + pre-chequeo, y el
  INSERT va en **SAVEPOINT**: un `rollback()` de sesión se habría llevado
  por delante las alertas que el mismo barrido ya creó (lo encontró un test).
  El umbral es `parametro_empresa` `sales/minutos_alerta_pedido` y **se
  congela en la fila**: subirlo mañana no reescribe lo que ayer fue demora.
  Nuevo evento `sales.pedido_demorado`; nuevo contrato público
  `accounting.estado_de_caja` (horas sin cerrar + efectivo esperado, no solo
  el conteo del KPI). 12 tests (`tests/test_alerta_pedido.py`).
- ✅ 2026-08-04 **Encolar ya no puede colgar el request** (hallazgo derivado
  del listener). `apply_async` conecta al broker **dentro** de la llamada y
  con reintentos: con Redis inalcanzable, cada venta confirmada pagaba
  segundos de DNS fallido — el suite pasó de 5 a 63 minutos y en producción
  habría sido el cajero esperando. Timeouts de 1 s en `celery_app`,
  `retry=False` al encolar la alerta, y `memory://` en los tests (mismo
  criterio que el token de Factiliza en `conftest.py`).
- ✅ 2026-08-04 **La alerta notifica al encargado de turno** (migración
  `7fda1eb759f7`). `users` escucha `sales.pedido_demorado` y crea una
  `notificacion` — entidad nueva, transversal, con `referencia_tipo`/
  `referencia_id` polimórficos y sin FK (mismo criterio que
  `decision_gerencial`).
  **Quién es el "encargado de turno" no necesitó una entidad nueva**: sale
  del `relevo_encargado_id` de la caja abierta, que es exactamente la
  persona a cargo del local en ese momento y ya se registraba al abrir turno
  (RN-MDP-002). Respaldo cuando no hay caja abierta: los `supervisor`/
  `admin` de esa sucursal — un aviso sin destinatario es un aviso perdido.
  **El punto de configuración futuro es una sola función**
  (`notificaciones.destinatarios_de_sucursal`): cambiar la regla no toca ni
  el listener ni la entidad ni la pantalla. 14 tests.
  `GET /notificaciones`, `POST /notificaciones/{id}/leer`,
  `POST /notificaciones/leer-todas` — sin `require_permission` a propósito:
  cada uno ve lo suyo, el filtro es la identidad y no un rol.
- ⬜ **La bandeja no se empuja a ningún lado**: la notificación existe y se
  consulta, pero nadie la manda al teléfono. Falta push/WhatsApp — y cuando
  llegue debe **leer de esta tabla**, no reemplazarla: un aviso que solo
  viajó por push no deja rastro de si alguien lo vio.
- ✅ 2026-08-05 **La bandeja tiene pantalla**: campana en la barra superior
  (`components/shell/campana.tsx`), contador de no leídas y panel con el
  detalle. Muestra **solo lo no leído** —la campana contesta "¿hay algo que
  atender?", y mezclar lo ya visto obliga a releer la lista entera para
  contestar eso— y marca leída **al hacer click en la fila, no al abrir el
  panel**: abrir para mirar de reojo no es haberse enterado. Refresca cada
  60 s, que es el ritmo del barrido de Celery que las genera; pedirlas más
  seguido no adelanta ninguna noticia. Sobre el `Popover` de shadcn que ya
  estaba instalado, sin componente propio de dropdown.
- ⬜ **Preferencias de aviso por usuario**: hoy la regla de destinatarios es
  fija. Se difiere a propósito hasta que haya un caso real ("de noche
  avisar también al dueño", "este local no usa la bandeja") — una tabla de
  preferencias sin nadie que la administre es un formulario más.
- ✅ 2026-08-04 **`efectivo_esperado` descuenta `movimiento_caja`**
  (ADR-025): el reporte de estado de caja y el arqueo usan el mismo cálculo
  que el cierre (`apertura + cobrado + ingresos − retiros`) y el desglose
  viaja en una columna nueva del reporte. Era un techo, no un arqueo.
- ✅ 2026-08-29 **La exportación baja lo que se ve, no el dataset
  completo** (ADR-081 Fase E). `POST /reportes/{codigo}/exportar` corre el
  mismo reporte con el mismo permiso y el mismo rango que `/datos`, pero
  con el tope en `LIMITE_MAXIMO_EXPORTACION` (50 000) en vez de
  `LIMITE_MAXIMO` (500), y arma el `.xlsx` en el servidor
  (`src/shared/planilla.py`, ya usado por la carga masiva de recetas). Los
  montos salen como número real (`Decimal` → `float`), no como texto —a
  diferencia del CSV por tarjeta, acá una fórmula `=SUMA(...)` funciona
  sin que nadie convierta la columna antes. Si algún día 50 000 no
  alcanza, ahí sí hace falta streaming asíncrono — no antes de que lo
  pidan.
- ✅ **`empresa_id` por query param en `/dashboard/resumen`** — **la entrada
  estaba obsoleta** (verificado 2026-08-05): ADR-004 se resolvió el
  2026-07-27 y el endpoint ya deriva la empresa del JWT vía
  `tenant.empresa(empresa_id)`. El query param sobrevive como el escape
  documentado del superusuario sin empresa asignada, igual que en el resto
  de la API — no como la vía normal.
