# Módulo `inventory` — Inventarios, almacenes y transferencias

## Objetivo

Mantener stock exacto y auditable por almacén (central, producción, sucursal),
y gestionar el flujo solicitud → aprobación → picking → transferencia → recepción.

## Entidades

**Estado de implementación (2026-08-01):** implementados el bloque
transversal (`categoria`, `categoria_udm`, `unidad_medida`), la base de
productos (`articulo`, `sku`, `receta`, `receta_item`), `stock`,
`movimiento_inventario`, `ajuste`, `lote` + `stock_lote` (FEFO),
`conteo` + `conteo_item` (conteo cíclico) y el ciclo de abastecimiento
interno (`reserva_stock`, `solicitud_insumos` + `solicitud_item`,
`transferencia` + `transferencia_item`) con su `guia_remision` +
`guia_remision_item`, más `incidencia_inventario`, `devolucion` y
`devolucion_item` (2026-08-06). **`stock_merma` no se implementa**: la
merma es una `reserva_stock` de tipo `merma` (ADR-028).

`articulo` (tipos `insumo` | `subreceta` | `mercaderia` | `empaque` |
`repuesto` | `suministro` — enum extensible), `categoria`, `stock`,
`stock_lote` (detalle por lote — base de FEFO/FIFO),
`movimiento_inventario` (inmutable, solo inserción), `reserva_stock` (que
es también donde vive la **merma**, ADR-028), `solicitud_insumos`,
`solicitud_item`, `transferencia`, `transferencia_item`, `lote` (código,
fecha_vencimiento, condiciones de almacenamiento), `conteo`, `ajuste`
(motivo, solicitante, aprobador), `devolucion` + `devolucion_item` (origen
`proveedor` | `cliente`). Detalle en `docs/architecture/data-model.md`
§3–§4.

## Estado (slice 10 — recetas condicionadas y UdM por línea, 2026-08-23)

Migración `e2b7c40d91af`, ADR-056, RN-COM-037, RN-UDM-005.

**`receta_item.aplica_valores`** (JSONB, nullable): array de
`producto_atributo_valor.id`. NULL o `[]` = la línea aplica siempre, que es
el caso de todas las recetas de hoy — por eso no hay backfill.

La regla es la de Odoo 18 (`mrp.bom.line._skip_bom_line` →
`_skip_for_no_variant`), en `domain/rules.aplica_a_variante`: se agrupan los
valores de la condición **por atributo** y la combinación tiene que coincidir
con **al menos uno de cada grupo**. Entre grupos es Y; dentro de un grupo es
O. Es lo que convierte 361 recetas en una de 26 líneas.

> Consecuencia aceptada: media Americana + media Peperoni **no** descuenta el
> jamón si la línea nombra los dos atributos. Es el comportamiento de Odoo y
> el que el archivo de Charlie's asume. La corrección es de **datos** —una
> línea por mitad, a media cantidad— y `test_variantes_odoo.py` prueba las
> dos formas lado a lado.

**`receta_item.unidad_medida_id`** (FK, nullable): NULL = la del artículo.
Si viene, es de la **misma categoría de UdM** (RN-UDM-001) y se convierte por
`ratio` al descontar y al costear. No revierte ADR-023: lo que ADR-023
descartó era una unidad *libre*; ésta es exacta.

**`domain/rules.consumo_de_linea`** es ahora la única cuenta de merma +
conversión. La usan `listeners._consumos_de_items` y `recetas.costo_linea`,
que antes la escribían distinto: el día que una gane un paréntesis, el costo
de un plato deja de cuadrar con lo que salió de la cámara.

**`receta.es_kit`** (booleano, default False) es el `type` de `mrp.bom`
(`normal` | `phantom`). Booleano y no un `tipo` de tres valores porque
`recetas.TIPOS_RECETA` ya significa otra cosa (`subreceta` | `producto`).

**`receta_item.orden`** existe para que exportar dos veces dé el mismo
archivo: sin orden explícito, un diff contra el export anterior no sirve.

`_consumos_de_items` pasa a cargar las líneas **una vez por receta** en vez
de una por ítem, y `GET /inventory/recetas/{id}` devuelve la unidad **de la
línea** cuando la línea eligió una.

## Estado (slice 11 — la matriz de recetas, 2026-08-23)

ADR-057. `GET`/`PUT /inventory/recetas/matriz`: el recetario en grilla,
insumos en las filas y recetas en las columnas.

**La identidad de una celda es `(receta, insumo, condición)`**, no un id de
línea — es lo que permite pegar un rectángulo desde Excel, que no trae ids.
La condición entra en la clave porque desde ADR-056 el mismo insumo puede
estar dos veces en la misma receta si cada línea aplica a otra combinación.

Vaciar la celda borra la línea. Vaciar una que ya estaba vacía **no** es un
error: pegar un rectángulo con huecos no puede reportar cuarenta problemas.

Cada celda entra en su propio `SAVEPOINT` (mismo criterio que ADR-046) y la
respuesta dice qué pasó con cada una, en vez de cortar con un 409.

La ruta va declarada **antes** de `/recetas/{receta_id}`: FastAPI resuelve por
orden y "matriz" entraría como un `receta_id` que no es UUID.

`editar_item` acepta `unidad_medida_id` y redondea con los decimales de **la
unidad de la línea**, no con los del artículo.

## Estado (slice 12 — la condición se lee y se escribe, 2026-08-24)

Enmienda a ADR-056. La columna existía desde el slice 10 y movía stock, pero
**la API de la receta no la exponía**: solo la matriz la tocaba, y la matriz
muestra UUID. Con el catálogo real cargado, el lienzo listaba las 26 líneas
de la mitad-y-mitad en plano, sin decir de qué mitad era cada una.

`GET /inventory/recetas/{id}` devuelve `aplica_valores` por línea: **lista de
texto y siempre lista, nunca `null`** — el editor no distingue dos formas de
"sin condición". Es lo que ya devolvía `MatrizCeldaOut`.

`POST /recetas/{id}/items` acepta `aplica_valores`, y también
`unidad_medida_id` y `orden`, que `agregar_item` recibía desde ADR-056 y
ningún cliente podía usar. Se valida `uuid.UUID` (como `CeldaIn`) y el paso a
texto vive en un solo lugar, `agregar_item`.

`PATCH .../items/{id}` acepta `aplica_valores` con **tres estados**: ausente
o `null` no toca la condición, `[]` la borra —la línea vuelve a aplicar
siempre— y una lista la reemplaza entera. Sin distinguir "no lo edito" de
"lo limpio", cambiar un gramaje borraría la condición de rebote.

Cambiarla tiene el **mismo 409** que crearla: el mismo insumo con la misma
condición es la línea duplicada de siempre. Se saltea el chequeo si la
condición no cambió y se excluye la propia línea, para que reafirmarla sea
idempotente.

`duplicar_receta` **conserva** condición, unidad y orden. Antes los perdía:
duplicar la mitad-y-mitad daba 26 líneas sin condición, o sea una receta que
descuenta todos los insumos de todas las mitades, siempre.

## Casos de uso

- CRUD de artículos y categorías.
- CRUD de **recetas** (ficha técnica): la línea acepta aritmética tecleada
  ("1000/3") y guarda el resultado redondeado a los decimales de la unidad
  del insumo, con la expresión al lado para reeditarla; duplicar clona con
  sufijo "(copy)" y escalar por factor redondea cada línea con **su propia**
  unidad (RN-COM-024, ADR-023).
- Consultar stock por almacén / artículo; alertas de stock mínimo (punto de
  reorden, calculado con el dato de consumo real de `inventory`, definido
  en conjunto con `production` y `accounting` — `inventory` no compra, solo
  alerta; `purchases` ejecuta).
- Ajustes de inventario (con motivo, auditados): solicitar y autorizar son
  permisos distintos (`inventory.solicitar_ajuste` /
  `inventory.aprobar_ajuste`), nunca el mismo usuario.
- Conteo cíclico: registro de conteo físico (a ciegas por defecto — el
  stock esperado solo lo ve quien tenga `inventory.ver_stock_esperado`)
  vs. stock del sistema, con diferencia calculada automáticamente. La
  periodicidad la fija la categoría del SKU, y lo no contado en su fecha
  se reporta a almacén y gerencia.
- Local crea solicitud de insumos → supervisor aprueba/rechaza.
- Almacén central: picking → packing → salida (transferencia en tránsito).
- Local recibe transferencia → stock local sube; diferencias quedan registradas.
- `transferencia` es genérica por `origen_almacen_id`/`destino_almacen_id`
  — cubre tanto central↔sucursal como transferencia lateral sucursal↔sucursal
  (excepción documentada, no cambia el modelo).
- FEFO/FIFO: picking sugiere el lote a tomar según `lote.fecha_vencimiento`
  (o fecha de ingreso si no aplica vencimiento); alerta de próximos a
  vencer con ventana configurable por artículo.
- **Merma** (RN-INV-012, ADR-028): registrar aparta el stock sin sacarlo
  del almacén —sigue en el estante y el conteo lo va a encontrar— y
  resolver decide su destino: `desecho` lo saca y lo asienta como pérdida
  en `accounting`, `reintegro` lo devuelve a disponible. Lo resuelve otro
  usuario, igual que un ajuste.
- **Devolución a proveedor**: la mercadería sale con el lote declarado,
  emite su guía de remisión y publica `inventory.devolucion_a_proveedor`
  para que `purchases` gestione el reclamo o la nota de crédito.
  **De cliente**: entra, y `destino` decide si vuelve al estante o se
  aparta como merma. Sucursal→central sigue siendo una `transferencia`.
  Desde 2026-08-13 **registrar y anular escriben en `audit_log`**: mueven
  stock real, y el evento le avisa a compras o comercial pero no responde
  "quién sacó esto del almacén". La pantalla estuvo en solo lectura hasta
  esa fecha, así que la API completa era inalcanzable por UI.

## Estado (slice 9 — planillas de catálogo, 2026-08-20)

Exportar es la plantilla con los datos adentro (ADR-052): lo que baja se edita
en Excel y se vuelve a subir. La E/S de `.xlsx` vive en `src/shared/planilla.py`
—abrir, mapear cabecera, filas, celda→texto/número/fecha/uuid, escribir— y la
lógica de cada entidad en su propio archivo de `application/`.

**Recetario** (`GET /recetas/exportar`)

| Hoja | Columnas |
|---|---|
| `Recetas` | `ID` · `Receta` · `Rendimiento` · `Unidad` · `Produce el artículo` |
| `Ingredientes` | `Receta` · `Insumo` · `Cantidad` · `Merma %` |
| `Instrucciones` | texto |

- La columna `ID` decide alta o actualización. Recetas se actualizan **solo
  por `ID`**: su única clave natural es el nombre, y el nombre es lo que se
  edita.
- `Ingredientes` **no lleva `ID`** a propósito: la identidad de una línea es
  `(receta, insumo)` y el dominio ya la hace única. Una columna con
  `receta_item.id` sería una segunda verdad que no sobrevive un copiar-pegar.
- `Cantidad` se exporta como `expresion or cantidad`: exportar `150` donde
  alguien escribió `450/3` perdería lo que RN-COM-024 existe para conservar.
- Al actualizar, **los ingredientes que el archivo no menciona se conservan**
  salvo que la revisión pida `quitar` para esa receta, con el número de líneas
  a la vista (RN-COM-031).
- El insumo que falta **se crea desde el diálogo**, con `catalogoApi.crearArticulo`
  — lo crea una persona, no el importador (ADR-046).

**Catálogo de artículos** (`/articulos/plantilla`, `/articulos/exportar`,
`/articulos/importar/validar`, `/articulos/importar` — RN-INV-023)

| Hoja | Columnas |
|---|---|
| `Artículos` | `ID` · `Código` · `Nombre` · `Tipo` · `Unidad` · `Categoría` · `Costo promedio` · `Controla lote` · `Días alerta vencimiento` · `Archivado` |
| `SKUs` | `Artículo` (código interno) · `Código` · `Código de barras` · `Activo` |
| `Instrucciones` | texto |

- Identidad: `ID`, o `Código` (`id_interno`) si el `ID` va vacío.
- **La unidad de un artículo existente no se cambia**: `editar_articulo` la
  excluye a propósito, y una fila que la cambie se reporta como problema en vez
  de ignorarse en silencio.
- El largo de `id_interno` (4) se valida **en el importador**: SQLite no aplica
  el largo de un `VARCHAR`, así que sin eso la fila pasa en verde y revienta
  contra Postgres. Un test ata la constante a la columna del modelo.
- Los SKU **solo se crean**; uno con código ya usado se informa. Ver deuda.

Exportar pide permiso de **lectura** (`inventory.leer`): son los mismos datos
que el listado, solo empaquetados. Plantilla, validar e importar piden
`inventory.gestionar_catalogo`. Las rutas literales van declaradas **antes** de
`/{id}`, o FastAPI las toma como un id que no es UUID.
## Estado (slice 8 — requerimiento de la jornada, 2026-08-19)

`solicitud_insumos` gana el estado `borrador` y `solicitud_item` la columna
`bajo_minimo_al_pedir` (ADR-051, RN-INV-023/024, migración `b5f27ac41e83`).

- **`borrador`**: la lista que el turno junta durante la jornada. Uno por
  almacén, no por usuario —dos listas paralelas del mismo almacén se
  solapan y ninguna queda completa—; `GET /solicitudes/borrador?almacen_id=`
  la crea si no existe (ya cargada con lo que está bajo `stock_minimo`) y si
  existía le suma lo que cayó bajo mínimo desde la última vez, **sin tocar
  lo ya tecleado**. No aparece en `GET /solicitudes` salvo pidiendo
  `estado=borrador`, ni en `solicitudes_resumen_para_negociacion`, ni sube
  al hub: todavía no le pidió nada a nadie.
- **`bajo_minimo_al_pedir`**: si el SKU estaba bajo mínimo cuando entró a la
  lista. Se **estampa al agregar el ítem**, nunca se recalcula —entre pedir
  y aprobar el stock se mueve, y recalcularla contaría otra historia—. Es lo
  que le dice al abastecedor qué es urgencia real y qué es decisión del
  local (ambas preguntas que hasta ahora no tenían dónde vivir).
- `POST/PATCH/DELETE /solicitudes/{id}/items[/{sku_id}]` editan el borrador;
  `POST /solicitudes/{id}/enviar` lo pasa a `pendiente` y **re-resuelve** el
  abastecedor (RN-INV-022 pudo cambiar mientras la lista estaba abierta).
- `GET /conteos` (paginado, faltaba: solo se podía pedir un conteo por su
  `id`) y `GET /solicitudes` / `GET /conteos/programa` ganan `sucursal_id` /
  `marca_id`, resueltos por join a través del almacén — las dos entidades
  van por almacén y sucursal/marca cuelgan de él.
- Pantallas nuevas: `/inventario/solicitudes` (la lista de la jornada +
  aprobar/rechazar/cancelar) y `/inventario/conteos` (abrir, contar a
  ciegas, cerrar viendo los ajustes generados, anular con motivo).

Tests: `tests/test_solicitudes_borrador.py` (10 casos) y los agregados a
`tests/test_conteos.py`. Recorrido de uso:
`frontend/uso/requerimientos.spec.ts`.

## Estado (slice 7 — carga masiva de recetas, 2026-08-13)

- `GET /inventory/skus`: no existía listado y ninguna pantalla podía ofrecer
  "qué se mueve". Va con `articulo_nombre`, porque un código de SKU no le
  dice nada a nadie.
- `GET /inventory/recetas` acepta `tipo` (`subreceta` | `producto`) y
  `categoria_id`. **El tipo se deriva** de `receta.articulo_id`, no hay
  columna (RN-COM-030): guardarlo sería un segundo lugar donde puede estar
  mal. La categoría es la del artículo que produce, así que solo alcanza a
  las subrecetas.
- **Carga masiva** (ADR-046, RN-COM-031): `GET /recetas/plantilla` baja un
  `.xlsx` con ejemplos e instrucciones;
  `POST /recetas/importar/validar` (multipart) dice qué entra y qué no **sin
  guardar nada**; `POST /recetas/importar` crea lo que la pantalla confirmó,
  **revalidando todo** porque lo que vuelve es un JSON que el cliente pudo
  editar. Reusa `crear_receta`/`agregar_item`, así que la cantidad acepta
  aritmética tecleada (RN-COM-024) y el nombre único por empresa se hace
  cumplir en un solo lugar. Cada receta va en su `SAVEPOINT`: un nombre
  repetido a mitad del archivo no se lleva puestas a las que ya entraron ni
  deja una a medias. `plantilla` va declarada **antes** de
  `/recetas/{receta_id}`, o FastAPI la toma como un id que no es UUID.

## Estado (slice 5 — recetas editables, 2026-08-03)

`POST/GET/PATCH /inventory/recetas` + `items` (alta, edición y borrado de
línea), `POST /recetas/{id}/duplicar` y `POST /recetas/{id}/escalar`, más
`GET /inventory/unidades-medida` (los decimales de un campo de cantidad
salen del catálogo, no de una constante del frontend — RN-GER-010). Permiso
`inventory.gestionar_catalogo` para escribir, `inventory.leer` para leer.

La cantidad se expresa **en la unidad del artículo**: no hay UdM en la línea
porque sería una segunda verdad sobre la misma cantidad y la que manda en el
descuento de stock es la del artículo (RN-UDM-001). La aritmética la evalúa
el servidor (`shared/aritmetica.py`, `ast` con lista blanca — nunca `eval`):
si el cliente mandara resultado y expresión por separado, nada garantizaría
que uno corresponda al otro. Migración `b6d1e83f47ac` (`receta_item.expresion`).

Contrato público nuevo: `queries_publicas.receta_resumen`, con el que
`sales` valida la receta que asigna a un producto comercial sin importar el
ORM de `inventory`.

**Tenant (2026-08-06, migración `d5b81e0c37a4`):** `receta` era la única
entidad del catálogo sin `empresa_id` — su CRUD listaba las de todas las
empresas y el hub las replicaba completas. Ahora el listado filtra, cada
ruta por id pasa por `exigir_receta`, el **nombre es único por empresa** (no
por grupo) y un ítem no puede apuntar a un artículo de otra empresa: eso
devuelve **404, no 403**, porque para esa empresa el artículo no existe.
`receta_item` no lleva columna propia — se acota por su receta.

## Reglas

- El stock nunca se edita directo: todo cambio pasa por `movimiento_inventario`.
- No despachar más de lo aprobado; no recibir más de lo enviado sin registro de diferencia.
- Transferencia descuenta origen al salir y suma destino al recibirse (en tránsito entre ambos).
- Ajustes requieren permiso `inventory.ajustar` (desglosado en solicitar/aprobar) y motivo obligatorio.
- Ajuste dentro del margen de error configurado (acordado con `accounting`)
  no dispara alarma; fuera de margen sí, y exige investigación documentada
  antes de aprobar.
- Movimiento de salida siempre respeta FEFO/FIFO — el picking no permite
  tomar un lote distinto al sugerido sin override explícito y motivo
  (`movimiento_inventario.motivo_lote`, RN-LOT-004; tomar el lote que FEFO
  ya sugería no es override y no pide motivo).

## Excepciones: lo que el módulo hace en silencio (2026-08-06)

Tres decisiones deliberadas dejan el stock distinto de lo ideal sin frenar
la operación. Las tres son correctas y ninguna tenía dónde verse — un
`log.warning` no es una superficie. Ahora cada una tiene su reporte en el
catálogo (`src/core/reportes/`, ADR-024), alimentado por
`application/queries_publicas.py`:

| Reporte | Qué muestra | Por qué existe la excepción |
|---|---|---|
| `consumos_omitidos` | Movimientos que el listener no hizo, con su motivo | Una venta nunca se bloquea por inventario (`incidencia_inventario`) |
| `disponible_negativo` | SKUs con más reservado que físico | Reservar exige disponible; consumir no (RN-INV-009) |
| `salidas_sin_lote` | Salidas de artículos con lote que ningún lote respalda | Stock anterior al control de lote, o el resto bloqueado (RN-LOT-005) |

Cuántas incidencias hay (últimos 7 días) también aparece como KPI en el
dashboard gerencial (`GET /dashboard/resumen`,
`incidencias_recientes`) — el detalle de cada una sigue viviendo en
`consumos_omitidos`, el KPI solo avisa que hay algo que revisar.

Además, `inventory.stock_bajo_minimo` se publica **al cruzar** el mínimo,
no cada vez que se está por debajo: con el stock ya bajo, un evento por
venta convierte la alerta en ruido y deja de mirarse justo cuando importa.

Desde 2026-08-06 los tres avisos de este módulo tienen consumidor en
`users` (`destinatarios_de_almacen` → bandeja de notificaciones):
`stock_bajo_minimo` como `aviso`, `lote_vencido_detectado` como `urgente`
—el stock ya se contaba como vendible— y `conteo_vencido` como recordatorio
diario. El almacén central no cuelga de ninguna sucursal, así que ahí no hay
encargado de turno y el destinatario se resuelve por rol dentro de la
empresa.

## Estado (slice 4 — reserva, solicitud y transferencia, 2026-08-01)

Ciclo completo de abastecimiento interno según ADR-020: el local pide, el
supervisor aprueba y reserva, el central despacha, el local recibe.

- **`reserva_stock` es una promesa, no un movimiento**: no toca `stock` ni
  genera `movimiento_inventario`. `GET /stock` devuelve ahora `cantidad`
  (físico), `reservado` y `disponible` = físico − reservas activas
  (RN-INV-009).
- **Reservar bloquea, consumir no**: aprobar una solicitud exige
  disponible suficiente (409 si no alcanza), pero una venta o un consumo
  de producción **nunca** se frenan por una reserva — ya ocurrieron. El
  disponible puede quedar negativo y eso es la señal de una promesa sin
  respaldo, no un error.
- **La solicitud va por almacén**, no por sucursal: producción también
  solicita. El abastecedor sale de `almacen.almacen_abastecedor_id` y se
  copia a la fila. Si ese almacén está **dado de baja** se usa
  `almacen_abastecedor_respaldo_id` (RN-INV-022, ADR-040): sin eso, dar de
  baja el central deja al local sin poder pedir nada. El respaldo cubre
  "no está", no "no tiene" —el faltante se resuelve aprobando por lo que
  hay (RN-INV-001/002)— y **no** aplica cuando la solicitud nombra su
  abastecedor: despachar desde donde no se pidió es lo que el que recibe
  no puede notar hasta contar la mercadería.
- **Estados**: `pendiente` → `aprobada` | `rechazada` | `cancelada`, y el
  despacho la lleva a `despachada` → `recibida`. Cancelar libera las
  reservas (RN-INV-010). `en_picking` **no existe y no va a existir**
  (descartado 2026-08-07): no gobierna ninguna regla y sería un estado que
  alguien tiene que marcar a mano.
- **`transferencia_item` va por SKU y lote**: el despacho reparte por FEFO
  y el destino recibe los mismos lotes que salieron (ADR-015).
- **Las diferencias se registran, no se corrigen**: no se despacha más de
  lo aprobado (RN-INV-001) ni se recibe más de lo enviado (RN-INV-002);
  menos sí en ambos casos. Al destino entra lo que de verdad llegó y la
  diferencia viaja en `inventory.transferencia_recibida`.
- **Transferencia lateral** sucursal↔sucursal: misma entidad con
  `solicitud_id` en NULL e ítems explícitos.

| Método | Ruta | Permiso |
|--------|------|---------|
| GET | `/reservas?almacen_id&sku_id` | `leer` |
| POST | `/reservas/{id}/liberar` | `liberar_reserva` |
| POST/GET | `/solicitudes` | `solicitar_insumos` / `leer` |
| GET | `/solicitudes/borrador?almacen_id=` | `solicitar_insumos` |
| POST/PATCH/DELETE | `/solicitudes/{id}/items[/{sku_id}]` | `solicitar_insumos` |
| POST | `/solicitudes/{id}/enviar` | `solicitar_insumos` |
| GET | `/solicitudes/resumen` | `leer_solicitudes_externas` |
| GET | `/solicitudes/{id}` | `leer` |
| POST | `/solicitudes/{id}/aprobar` \| `/rechazar` | `aprobar_solicitud` |
| POST | `/solicitudes/{id}/cancelar` | `solicitar_insumos` |
| POST/GET | `/transferencias` | `transferir` / `leer` |
| GET | `/transferencias/{id}` | `leer` |
| POST | `/transferencias/{id}/recibir` | `recepcion` |
| POST/GET | `/transferencias/{id}/guia` | `emitir_guia` / `leer` |
| GET | `/guias-remision?estado_emision=` | `leer` |

Solicitar y aprobar son permisos distintos y el aprobador no puede ser
quien pidió (RN-INV-006). `transferir` y `recepcion` ya estaban sembrados
desde el slice 1 sin uso: este slice los estrena.

Tests: `tests/test_transferencias.py` (23 casos). Migración `d8b35f1ca207`.

## Estado (slice 3 — conteo cíclico, 2026-08-01)

`conteo` + `conteo_item` según ADR-019. La periodicidad **la fija la
categoría** (`categoria.frecuencia_conteo`: diario / semanal / quincenal /
mensual / semestral / anual, RN-INV-007) — no hay un número universal.
NULL deja la categoría fuera del ciclo.

- **Programa derivado, sin tabla de calendario**: la próxima fecha de una
  categoría en un almacén es el último conteo **cerrado** que la cubrió
  más los días de su frecuencia; si nunca se contó, cuenta desde el alta
  de la categoría. Un conteo general (`categoria_id` NULL) pone al día a
  todas las categorías de ese almacén.
- **Snapshot al abrir**: `cantidad_sistema` se congela al abrir el conteo,
  no al cerrarlo. Un SKU contado que no estaba en el snapshot entra con
  sistema en 0 — es justo el sobrante que el conteo busca.
- **A ciegas por defecto** (RN-INV-005): el detalle omite
  `cantidad_sistema`/`diferencia` salvo permiso
  `inventory.ver_stock_esperado`. `almacenero` cuenta sin verlo.
- **Cerrar solicita, no corrige**: cada diferencia genera un `ajuste`
  `pendiente` con `ajuste.conteo_id`, que aprueba otro usuario
  (RN-INV-006). Los ítems no contados se ignoran: un conteo parcial no
  declara faltante lo que nadie miró. `dentro_margen` **lo calcula el
  servidor**, nunca el cliente: sale del parámetro `inventory/
  margen_error_ajuste` aprobado por Gerencia (ADR-014) y son dos
  tolerancias que conviven —**porcentaje** sobre la cantidad y **piso en
  dinero** sobre la diferencia valorizada al `costo_promedio`—, basta
  cumplir una (RN-INV-015). Sin parámetro vigente rige
  `INVENTORY_MARGEN_AJUSTE_PCT` (2 %, sin piso). Con sistema en 0 no hay
  base para el porcentaje, pero el piso sigue aplicando.
- **Lo no contado en su fecha se reporta a almacén y gerencia**
  (RN-INV-021): `inventory.conteo_vencido`. El día de vencimiento aún no
  es atraso.

| Método | Ruta | Permiso |
|--------|------|---------|
| PATCH | `/categorias/{id}` | `gestionar_catalogo` |
| GET | `/conteos/programa?almacen_id` | `leer` |
| POST | `/conteos/verificar-vencidos?almacen_id` | `contar` |
| POST | `/conteos` | `contar` |
| GET | `/conteos/{id}` | `contar` (+ `ver_stock_esperado` para el esperado) |
| POST | `/conteos/{id}/cantidades` | `contar` |
| POST | `/conteos/{id}/cerrar` | `contar` |
| POST | `/conteos/{id}/anular` | `contar` |

Cerrar un conteo crea los ajustes con `inventory.contar`, sin exigir
además `solicitar_ajuste`: cerrar el conteo **es** solicitar esos ajustes,
y ninguno mueve stock sin la firma de un aprobador distinto.

`PATCH /categorias/{id}` acepta `quitar_frecuencia: true` para sacar una
categoría del ciclo — mandar `frecuencia_conteo: null` significa "no la
toques", no "bórrala". Es el **único campo del módulo que se puede vaciar**
desde un PATCH; el resto se cambia por otro valor.

### Qué se corrige de un artículo (y qué no)

`PATCH /articulos/{id}` acepta `id_interno` desde el 2026-08-10, con la misma
unicidad del alta (reenviar el propio código no choca consigo mismo). Es el
código de cuatro caracteres que el almacenero lee en el estante: tecleado mal
se arrastra por toda la operación y hasta ahora era inmutable.

**`unidad_medida_id` no está en `ArticuloUpdate` y no va a estar.** El stock,
los movimientos y las recetas ya cargadas están expresados en la unidad
actual: cambiarla no convierte nada, **reinterpreta en silencio** todo lo que
ya existe — 10 pasa de 10 kilos a 10 gramos sin que se mueva una fila. Un
artículo con la unidad equivocada se archiva y se crea de nuevo.

**Anular** (2026-08-06) descarta un conteo abierto por error con motivo
obligatorio: no genera ajustes y no pone al día el calendario, porque el
programa solo mira los conteos `cerrado`. Antes la única salida era
cerrarlo vacío, y un conteo cerrado en cero afirma "se contó y no había
diferencias" —lo contrario de lo que pasó— además de correr la fecha de la
categoría.

Tests: `tests/test_conteos.py` (29 casos). Migraciones `c4e70a91d5b8` y
`c2f6a94b13de`.

## Estado (slice 2 — lote/FEFO, 2026-07-27)

`lote` (código, vencimiento, origen, condición de almacenamiento) y
`stock_lote` (saldo por lote y estado `disponible`/`bloqueado`/`agotado`)
implementados según ADR-015. El control es **opcional por artículo**
(`articulo.controla_lote`): solo los perecibles/trazables mueven stock por
lote.

- **FEFO al salir**: `application/stock.py::registrar_salida` reparte la
  cantidad entre los lotes con saldo, del vencimiento más próximo al más
  lejano (sin vencimiento va al final → FIFO por fecha de ingreso), y
  genera **un movimiento por lote tomado**. Un `lote_id` explícito es el
  override del lote sugerido y **exige `motivo_lote`** cuando no coincide
  con el que FEFO ya iba a tomar (RN-LOT-004).
- **Vencidos**: el picking bloquea el lote vencido que encuentra todavía
  disponible y publica `inventory.lote_vencido_detectado`;
  `POST /lotes/bloquear-vencidos` hace el mismo barrido a demanda, y
  desde 2026-08-06 lo dispara además un periódico diario (ver más abajo).
- **Ingresos**: la recepción de compra crea el lote con el código y
  vencimiento declarados por el proveedor (RN-VNC-002) y producción con
  `origen=produccion`. Un ingreso sin lote de un artículo que lo controla
  entra al lote del día — nada queda fuera de la trazabilidad.

| Método | Ruta | Permiso |
|--------|------|---------|
| POST | `/lotes` | `registrar_movimiento` |
| GET | `/lotes?almacen_id&sku_id&por_vencer_dias` | `leer` |
| POST | `/lotes/bloquear-vencidos` | `registrar_movimiento` |
| GET | `/lotes/{id}` | `leer` — el lote con su saldo por almacén (ADR-036) |

`POST /movimientos` devuelve ahora una **lista** de movimientos (una salida
FEFO puede repartirse entre varios lotes) y acepta `lote_id` + `motivo_lote`
opcionales. `GET /lotes` marca cada fila con `por_vencer`, calculado contra
`articulo.dias_alerta_vencimiento` (RN-VNC-004) o contra el
`por_vencer_dias` de la consulta, que manda si viene.

Tests: `tests/test_lotes.py` (14 casos). Migraciones `c9a2f4e18b60` y
`c2f6a94b13de`.

## Estado (slice 1 implementado 2026-07-25)

Operativo: catálogo (CRUD artículos/categorías/SKUs), stock por almacén y
ajuste con segregación de funciones. Capas `domain/rules.py`,
`infrastructure/` (modelos `stock`, `movimiento_inventario`, `ajuste` +
`repositories.py`), `application/` (`catalogo.py`, `stock.py`, `ajustes.py`),
`api/`. Migración `be914c92a94b`. Reusa auth/RBAC de `users`.

Endpoints `/api/v1/inventory`:

| Método | Ruta | Permiso |
|--------|------|---------|
| POST/GET | `/categorias` | `gestionar_catalogo` / `leer` |
| GET | `/categorias/{id}` | `leer` |
| GET | `/articulos/{id}` | `leer` |
| GET | `/skus/{id}` | `leer` — el SKU con su artículo y su saldo por almacén |
| GET | `/ajustes?almacen_id&estado` | `leer` — no existía: `ajuste_fuera_margen` reportaba un hecho que no se podía ir a mirar (ADR-036) |
| GET | `/ajustes/{id}` | `leer` — con artículo, almacén, solicitante y aprobador resueltos |
| GET | `/unidades-medida` | `leer` — catálogo global, sin filtro de tenant (`data-model.md` §3) |
| POST | `/unidades-medida` | `gestionar_catalogo` — CRUD antes diferido (ADR-014 Addendum b); requiere `categoria_udm_id` existente |
| PATCH | `/unidades-medida/{id}` | `gestionar_catalogo` — corrige `decimales` (RN-GER-010) sin recrear la unidad |
| GET/POST | `/categorias-udm` | `leer` / `gestionar_catalogo` |
| POST/GET/PATCH | `/articulos[/{id}]` | `gestionar_catalogo` / `leer` — el PATCH corrige `id_interno`, **nunca** `unidad_medida_id` (ver abajo). El GET acepta `?tipo=` (ej. `empaque`): filtra en la base porque la lista viene paginada y una pantalla que filtre lo recibido se queda sin opciones en cuanto el catálogo pasa de una página |
| POST | `/skus` | `gestionar_catalogo` |
| GET | `/stock` | `leer` |
| POST | `/movimientos` | `registrar_movimiento` |
| POST | `/ajustes` | `solicitar_ajuste` |
| POST | `/ajustes/{id}/aprobar` \| `/rechazar` | `aprobar_ajuste` |

Reglas ya aplicadas: stock solo cambia vía `movimiento_inventario`; salida no
deja stock negativo; ajuste `solicitar` ≠ `aprobar` y aprobador ≠ solicitante;
alerta `bajo_minimo` derivada en la consulta; evento
`inventory.ajuste_fuera_margen` al aprobar fuera de margen.

`application/stock.py::contar_bajo_minimo(session, empresa_id)` (nuevo
2026-07-26, ADR-012): cuenta filas bajo mínimo escopadas por empresa (vía
`Almacen.empresa_id` — mismo import de modelo permitido que ya usa
`application/listeners.py`), consumido por `core.dashboard_router` para el
dashboard gerencial.

**Guía de remisión** (2026-08-05, ADR-027): cuelga de `transferencia`
porque lo que declara es un traslado, y el traslado es un hecho de
inventario (RN-GDR-002: la emite el almacén). Las líneas **se derivan**
de `transferencia_item` agrupadas por SKU —RN-TRP-002 exige que lo
transportado coincida con lo declarado, así que no hay formulario de
ítems— y solo se teclea lo que el sistema no puede saber: chofer,
vehículo, peso bruto y fecha de inicio del viaje. Un traslado, una guía
(`transferencia_id` único) y correlativo por `(empresa, serie)`. El envío
a SUNAT es asíncrono (`POST /despatch/send` vía Celery): la guía impresa
es la que viaja y un rechazo se corrige y reemite, no detiene el camión.

**Diferido (deuda del módulo):** del slice de abastecimiento,
`reserva_stock` sigue con dos tipos sin productor (`produccion` y
`carrito`, que esperan a sus módulos) y la transferencia no lleva vehículo
ni tracking (`vehiculo` no existe). Del slice de lote: la reposición por
venta anulada entra al lote del día y no al lote del que salió. Ver
ROADMAP → Deuda técnica → Módulo inventory.

## Barridos periódicos (Celery beat, 2026-08-06)

Los dos endpoints de vencimiento ya no dependen de que alguien los llame:

| Tarea | Cuándo | Qué hace |
|---|---|---|
| `inventory.bloquear_lotes_vencidos` | 06:00 hora Perú | Bloquea todo lote vencido con saldo disponible |
| `inventory.reportar_conteos_vencidos` | 06:15 hora Perú | Publica `inventory.conteo_vencido` por categoría atrasada |

**Antes del turno y no a cualquier hora**: el vencimiento cambia al pasar
la medianoche del negocio (`src/shared/fechas.py`, no UTC), y bloquear el
lote a media mañana deja que la primera salida del día se lo lleve. Sin
tenant: un periódico no tiene empresa, y un lote vencido lo está para
todas. Que el conteo vencido se reporte **todos los días** hasta que se
haga es deliberado —es un recordatorio— a diferencia de
`stock_bajo_minimo`, que avisa al cruzar justamente para no repetirse.

## Sincronización con el hub de sucursal (implementado 2026-07-27)

`application/sincronizacion.py` declara qué replica este módulo hacia el
hub local (ADR-009 fase 2): unidades de medida, categorías, artículos,
SKU, recetas, el `stock` del almacén de esa sucursal y —desde el slice de
lote— `lote` y `stock_lote`. Sin stock local, la primera venta offline
fallaría al descontar insumos — el listener `sales.venta_confirmada` corre
también dentro del hub; sin los lotes, ese descuento no podría aplicar
FEFO y elegiría un lote distinto al que elige la nube.

`stock` y `stock_lote` son los recursos que el hub además escribe por su
cuenta. La
nube gana en el pull, y eso es correcto porque el ciclo **empuja antes de
jalar**: para cuando el hub lee el stock de la nube, la nube ya procesó
las ventas del corte.

`registrar_movimiento` acepta un `id` client-generado (mismo motivo que en
`sales`), aunque hoy el sync no empuja movimientos.

## Flujo

Solicitud (local) → aprobación + reserva (supervisor) → picking/packing
(central) → salida → transferencia en tránsito → recepción (local) → stock
actualizado.

El picking/packing es una etapa operativa del SOP, no un estado del ERP:
entre `aprobada` y `despachada` no cambia qué se puede hacer (ADR-020).

## Relaciones

- Escucha: `sales.venta_confirmada` (descuenta insumos según receta, **menos
  las restas de la línea**: el insumo que el cliente pidió quitar no se usó,
  así que descontarlo lo haría aparecer como faltante en el conteo del mes —
  RN-PRD-019, ADR-035),
  `sales.consumo_personal_registrado` (misma expansión de receta, pero con
  `tipo_movimiento=consumo_interno` y **valorizando** lo consumido —
  RN-COM-027, ADR-034), `purchases.compra_recibida` (suma stock central),
  `production.orden_completada` (consume insumos, produce subrecetas).
- Publica: `inventory.stock_consumido` (auditoría del descuento por venta/
  producción), `inventory.stock_bajo_minimo`, `inventory.transferencia_recibida`,
  `inventory.merma_registrada` (accounting recibe para su reporte de
  pérdidas), `inventory.devolucion_a_proveedor` (purchases gestiona
  reclamo/nota de crédito), `inventory.ajuste_fuera_margen` (accounting/
  administrador reciben alerta de auditoría),
  `inventory.lote_vencido_detectado` (notifica y dispara memorándum al
  responsable si el lote vencido seguía disponible),
  `inventory.conteo_vencido` (reporte a almacén y gerencia de la categoría
  que no se contó en su fecha, RN-INV-021),
  `inventory.consumo_personal_valorizado` (comida del personal ya
  descontada, con su monto al `costo_promedio` — accounting la asienta como
  gasto de alimentación de personal) y
  `inventory.consumo_personal_reversado` (el consumo se anuló: el insumo
  volvió y el asiento se reversa).
- Contrato público de lectura: `application/queries_publicas.py` — hoy
  `unidad_medida_para_magnitud` (nombre y `decimales` de una UdM, para que
  otro módulo exprese una cantidad con su unidad, RN-GER-010),
  `receta_resumen` (que `sales` valide la receta de un producto comercial),
  `insumos_de_receta` y `nombres_de_articulos` (las restas de `sales`: qué se
  le puede pedir "sin" a un plato **es** la lista de insumos de su receta, y
  el KDS necesita el nombre para imprimir "SIN CEBOLLA" — RN-COM-028,
  ADR-035) y
  `solicitudes_resumen_para_negociacion` (`GET /solicitudes/resumen`, permiso
  `leer_solicitudes_externas`: qué artículo pide más cada sucursal, para que
  `purchases` negocie volumen — ver `docs/architecture/events.md`) y
  `costo_unitario_de_recetas` (costo de **una unidad de rendimiento**, con
  merma, para que el reporte de margen del tablero no tenga que conocer el
  modelo de recetas) y `articulo_resumen` (identidad y **tipo** de un
  artículo, para que quien lo recibe valide que sirve: lo usa `sales` antes
  de guardar `producto_comercial.empaque_id`, que solo admite tipo `empaque`
  — RN-EMP-003). Mismo criterio que `sales.queries_publicas`: devuelve
  dicts, nunca el ORM, y nadie importa `inventory.infrastructure` desde
  afuera.

  `articulo_resumen` devuelve el tipo **crudo** y no un booleano
  `es_empaque`: qué tipo hace falta lo decide quien pregunta, que es el que
  conoce su propia regla. Un predicado por caso de uso convertiría el
  contrato en una lista de preguntas ajenas.

  `costo_unitario_de_recetas` reusa `recetas.costo_linea` en vez de
  recalcular con otro criterio —dos pantallas del ERP no pueden mostrar
  números distintos para lo mismo— y **omite** del resultado la receta sin
  insumos o sin rendimiento válido: nunca devuelve costo cero, que se leería
  como "gratis" en lugar de "desconocido".


## Merma y devolución (2026-08-06, ADR-028)

| Método | Ruta | Permiso |
|--------|------|---------|
| POST | `/mermas` | `solicitar_ajuste` |
| GET | `/mermas?almacen_id` | `leer` |
| POST | `/mermas/{id}/resolver` | `aprobar_ajuste` |
| POST | `/devoluciones` | `registrar_movimiento` |
| GET | `/devoluciones?almacen_id&origen` | `leer` |
| GET | `/devoluciones/{id}` | `leer` |
| POST | `/devoluciones/{id}/anular` | `registrar_movimiento` |
| POST | `/devoluciones/{id}/guia-remision` | `emitir_guia` |

Sin permisos nuevos: la merma reusa los del ajuste porque la segregación es
la misma —quien declara que algo no sirve no firma su baja— y un permiso
nuevo para la misma idea sería una segunda matriz que mantener.

**La recepción de transferencia admite parcial** desde el mismo día:
`{"parcial": true}` ingresa lo declarado y deja el resto **en tránsito**.
Se declara explícito y no se deduce de que falten ítems: deducirlo haría
que un olvido cierre la transferencia dando por perdido lo que todavía
viene en camino. El evento `inventory.transferencia_recibida` sale **una
sola vez**, al cerrar — si no, `accounting` asentaría el faltante de cada
entrega por separado.

Tests: `tests/test_merma_devolucion.py` (12 casos).

## Offline: el ciclo de abastecimiento en el hub (2026-08-07, ADR-009 fase 3)

Pedir, ver lo que viene y recibir son las tres cosas que el local hace con
el almacén, y las tres pasan cuando el internet no está — el camión no
espera. Lo que viaja:

| Recurso | Dirección | Por qué |
|---|---|---|
| `solicitud_insumos` + `solicitud_item` | ambas | El local pide offline y ve en qué estado va lo que pidió |
| `transferencia` + `transferencia_item` | ambas | Baja lo que **entra** a su almacén; sube el hecho de haberlo recibido |
| `reserva_stock` | baja | Sin ellas su `disponible` offline sería el físico entero |
| `conteo` + `conteo_item` | sube | Se cuenta offline y sube **cerrado** |
| `almacen` del abastecedor | baja | Sin la ficha del central no se le puede pedir nada |

**La guía de remisión no se emite offline, y es decisión tomada** (no
deuda). El correlativo es único por `(empresa, serie)`: dos hubs numerando
a la vez colisionarían con la guía **ya impresa y viajando en el camión**,
y el conflicto aparecería recién al sincronizar, cuando ya no hay nada que
corregir. Las dos salidas —una serie por almacén emisor, o un rango de
correlativos por hub— cuestan un trámite ante SUNAT o huecos de numeración
que hay que justificar, y hoy el único emisor es el almacén central, que
está en la nube. El despacho lateral offline se registra igual; su guía
sale al reconectar.

Tres decisiones que valen más que la tabla:

- **La recepción no es una fila que sube, es un hecho.** La transferencia la
  creó el central en la nube; el hub solo la recibe. Por eso reproducirla
  dos veces tiene que ser inocuo —y lo es— o un error ajeno trabaría el
  recurso para siempre.
- **El conteo sube cerrado, nunca a medias.** Uno abierto todavía se está
  contando: reproducirlo arriba generaría ajustes por ítems que nadie miró.
- **Cada módulo tiene su watermark.** Si `inventory` se traba con una
  recepción que la nube rechaza, las ventas siguen subiendo. Que un conteo
  bloquee el dinero sería exactamente al revés de lo que importa.