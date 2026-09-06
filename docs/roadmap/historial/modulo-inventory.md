# Historial — Módulo `inventory`

Estado vigente: 🔶 En curso — catálogo, stock por almacén, lote/FEFO, conteo cíclico,
abastecimiento interno (solicitudes/reservas/transferencias), recetas y variantes,
abastecedor de respaldo, devoluciones, carga masiva/planillas .xlsx y requerimiento
de la jornada están implementados y operables de punta a punta (con pantallas);
queda deuda menor (guía de remisión offline, recorte de aprobado por SKU, encadenar
el borrador de requerimiento al cierre de un conteo cíclico) — ver
`docs/roadmap/deuda/modulo-inventory.md` (4 abiertos, 32 cerrados).

## Cronología

### 2026-07-04 — Especificaciones de módulos base

De la tabla F0 (fila "Especificaciones de módulos base"):

> Especificaciones de módulos base | ✅ 2026-07-04 | READMEs de users, inventory, sales, purchases, accounting |

### 2026-07-14 — Fase de procesos (tras el modelado de BD)

Del final del documento, plan de orden de desarrollo (`inventory` como paso 3 y 5):

> ### Fase de procesos (tras el modelado de BD)
>
> 1. `users`: auth (login PIN → JWT/refresh), RBAC, contexto de tenant, auditoría base.
> 2. Organización: grupo → empresa → marca → sucursal → almacén (vive en `users` o módulo `organization`).
> 3. `inventory`: artículos, stock por almacén, movimientos.
> 4. `purchases`: proveedores, OC, recepción → entrada a almacén central.
> 5. Solicitudes + transferencias central → local.
> 6. `sales`: PDV, recetas, descuento automático de insumos, pagos, Nubefact.
> 7. Producción, contabilidad, RRHH, resto de módulos.

**Estado vigente:** superado por los slices 1-9 del módulo `inventory` (ver entrada
2026-07-27 más abajo) y por el slice 4 (abastecimiento interno, ADR-020) para
"Solicitudes + transferencias central → local".

### 2026-07-14 — Modelado de BD — siguiente sesión (entidades de inventario)

De la sección "### Modelado de BD — siguiente sesión":

> Punto de partida: `docs/architecture/data-model.md` (fuente de verdad,
> ya ampliado con todo lo definido en esta sesión). Al modelar, revisar
> también `docs/domain/domain-model.md` y `docs/domain/business-rules.md`
> para constraints/checks a nivel de BD (ej. RN-GEN-001 stock inmutable,
> RN-INV-009 disponible=físico−reservado, RN-CPP-007 serie/correlativo
> único por empresa).
>
> Entidades transversales a modelar primero (de las que dependen casi
> todas las demás):
> - `persona` (party model — base de trabajador/cliente natural/usuario)
> - `categoria` (aplica a articulo Y activo)
> - `categoria_udm` + `unidad_medida` (con ratio de conversión)
> - `archivo` (vínculo polimórfico, soporta evidencia/reportes)
>
> Bloques de entidades nuevas de esta sesión, a incorporar al modelado:
> - **Productos/Inventario**: `sku`, `lote`, `reserva_stock`, `conteo`+
>   `conteo_item`, entidades ya existentes enriquecidas (`articulo` con
>   tipos `mercaderia`/`empaque`/`repuesto`, `stock` con fecha_apertura).
>
> Pendiente de decisión técnica antes de migrar: estrategia de tenant
> (RLS de Postgres vs. filtro a nivel de aplicación) — no definida aún en
> docs, definirla al iniciar esta fase.

**Estado vigente:** implementado en el slice 1 y siguientes del módulo
`inventory` (ver 2026-07-27 más abajo). La estrategia de tenant se resolvió
como filtro de aplicación (ADR-004, `empresa_id` obligatorio + tests).

### 2026-07-19 — Área Almacén y Logística: docs de proceso (tabla F0)

De la tabla F0 (fila "Almacén-Logística: procesos y plantillas"):

> Almacén-Logística: procesos y plantillas (conteo, vencimientos/merma, transporte/transferencias) | ✅ 2026-07-19 | `docs/almacen-logistica/`, 8 SOPs, 6 plantillas — ver detalle abajo. Módulo backend `inventory` ajustado (lote, merma, ajuste solicitar/aprobar) |

### 2026-07-19 — Área Almacén y Logística — conteo, vencimientos/merma, transporte (orden sugerido de desarrollo)

De la sección "### Área Almacén y Logística — conteo, vencimientos/merma, transporte (2026-07-19)":

> Documentación completa del área, complementando lo que ya existía
> (`Abastecimiento-Locales/`, 3 SOPs del ciclo sucursal↔central, y RN-ALM-*/
> RN-INV-* ya cubrían bastante del modelo). Se agregó lo que faltaba: conteo
> cíclico y ajuste con discrepancia investigada, control FEFO/FIFO explícito,
> gestión de vencimiento próximo, registro de merma/desperdicio, devolución a
> proveedor, y transporte/transferencias (incluye **transferencia lateral
> entre sucursales**, confirmada por el usuario como excepción real del
> negocio). Puesto dedicado: **encargado de Almacén Central**; transporte con
> **flota propia** (perfil de chofer/repartidor, kilometraje obligatorio
> RN-VEH-004).
>
> Incorporado:
> - `docs/almacen-logistica/` (nuevo): `README.md` (deja explícito qué NO
>   duplica — recepción de compra vive en Compras, ciclo de requerimiento ya
>   documentado), `politica-almacen-logistica.md` (FEFO/FIFO, conteo/ajuste,
>   punto de reorden — quién lo define [Producción+Contabilidad+Logística,
>   RN-INV-008] vs. quién compra [Compras], vencimiento/merma, devoluciones,
>   transferencia lateral, transporte), `perfiles/` (encargado de almacén
>   central, chofer/repartidor).
> - `docs/diagrams/Procesos/Logistica-Almacen/` — 8 SOPs nuevos en
>   `Conteo-Auditoria/` (conteo cíclico, ajuste por discrepancia),
>   `Vencimientos-Mermas/` (FEFO/FIFO, vencimiento próximo, merma/desperdicio)
>   y `Transporte-Transferencias/` (transferencia lateral, logística de
>   reparto, devolución a proveedor). Se suman a `Abastecimiento-Locales/`
>   ya existente.
> - `docs/templates/almacen-logistica/` — 6 plantillas: reporte de conteo
>   cíclico, ficha de ajuste, reporte de merma, guía de transferencia
>   lateral, guía de devolución a proveedor, hoja de ruta de reparto.
> - `src/modules/inventory/README.md` (spec técnica) — entidades `lote`,
>   `stock_merma`, `conteo`, `ajuste`, `devolucion`; casos de uso de FEFO/FIFO,
>   ajuste con permisos separados de solicitar/aprobar, transferencia lateral
>   (ya soportada por el modelo genérico origen/destino, sin cambio de
>   esquema); eventos nuevos `inventory.merma_registrada`,
>   `inventory.devolucion_a_proveedor`, `inventory.ajuste_fuera_margen`.
> - `00_PROJECT.md` — entrada `almacen-logistica/` en el mapa; tablas
>   actualizadas.
>
> No se generaron reglas de negocio nuevas — RN-ALM-001..007 y RN-INV-001..020
> ya cubrían el modelo; los SOPs las aplican en vez de duplicarlas.
>
> Pendiente (declarado, no bloquea): frecuencia exacta de conteo cíclico y
> margen de error de ajuste (quedan `[[ COMPLETAR ]]`, a definir con
> Contabilidad); quién autoriza ajustes (admin vs. supervisor de logística,
> rol aún no existe formalmente).

**Estado vigente:** la frecuencia de conteo cíclico se resolvió por categoría
(`categoria.frecuencia_conteo`, RN-INV-007, slice 3 — ver 2026-07-27) y el
margen de error de ajuste vía `INVENTORY_MARGEN_AJUSTE_PCT` (mismo slice),
con el piso en soles propuesto el 2026-08-05 (ver entrada de esa fecha). Quién
autoriza ajustes se decidió el 2026-08-05: el supervisor de turno (ver entrada
de esa fecha) — se descartó un rol "supervisor de logística" aparte.

### 2026-07-20 — Slice Venta — núcleo de datos (tablas base de inventory)

De la sección "### Slice Venta — núcleo de datos (2026-07-20)":

> Primer slice vertical de datos completo, a pedido del usuario: conectar
> venta con cliente y trabajador para habilitar **historial de compras del
> cliente** y **ranking de ventas por trabajador**. Ambas consultas ya
> funcionan y están probadas (`tests/test_venta_slice.py`).
>
> Antes de modelar se corrigieron 2 inconsistencias reales encontradas:
> `data-model.md` §6 `venta.estado` seguía listando el enum viejo de 8
> estados; `state-machines.md` ya lo había corregido a 4
> (`orden|pagada|facturada|anulada`) el 2026-07-14 — quedó desalineado.
> `articulo` no tenía `empresa_id` directo, rompiendo la convención de
> tenant (ADR-004) porque `categoria_id` es opcional. Ambas corregidas en
> `data-model.md` antes de generar el modelo.
>
> 11 tablas nuevas (22 en total con el bloque transversal):
> - `usuario` (alcance mínimo — sin rol/permiso/RBAC todavía, eso es el
>   slice de auth dedicado).
> - `trabajador` (RRHH — nuevo módulo `src/modules/rrhh/`, solo esta
>   entidad; el resto de §8b sigue pendiente del slice de RRHH).
> - `articulo`, `sku`, `receta`, `receta_item` (base de productos —
>   inventory), `cliente`, `punto_venta`, `producto_comercial`, `venta`,
>   `venta_item` (sales, módulo nuevo).
>
> Deliberadamente diferido (no bloquea historial/ranking, se agrega
> cuando se aborde PROC-COM-002 o el pricing): `modificador`,
> `variante_producto`, `combo`, `lista_precio`, `precio`, `promocion`,
> `medio_pago`, `pago`, `comprobante`, `carrito`, `central_pedidos`,
> `cuenta_puntos`.
>
> Migración `08c7aa59dd6e`, aplicada y verificada en Supabase (ciclo
> upgrade/downgrade/upgrade limpio, igual que el bloque anterior).

### 2026-07-20 — Revisión de consistencia y correcciones (stock_lote FEFO/FIFO, evento de lote vencido)

De la sección "### Revisión de consistencia y correcciones (2026-07-20)" (extracto
relevante a inventory; la sección completa toca varios módulos):

> Revisión completa del proyecto (SOPs, áreas, docs transversales, specs).
> Correcciones aplicadas en la misma sesión:
> [...]
> - Catálogo de eventos sincronizado con las specs (10 eventos agregados,
>   incl. `inventory.lote_vencido_detectado`); READMEs de módulos y mapa
>   `diagrams/modules.md` alineados.
> - Data-model: bloque Compras completo (caja chica, compra directa,
>   evaluación de proveedor, requerimiento de activo), `stock_lote`
>   (FEFO/FIFO implementable + bloqueo de vencidos con memorándum),
>   `ajuste`, `apertura_caja`/`cierre_caja`/`arqueo` (caja ya no es módulo
>   "futuro"), `flota`, `combo`, `plantilla`; `contrato` reubicado como
>   transversal; `articulo.tipo` + `suministro` (enum extensible).
> [...]

**Estado vigente:** `stock_lote`, FEFO y el bloqueo de lotes vencidos se
implementaron en el slice 2 de `inventory` (ADR-015, ver 2026-07-27 abajo),
que publica `inventory.lote_vencido_detectado`.

### 2026-07-27 — Módulo `inventory`: slices 1 a 9 (F0)

De la tabla F0 (fila "Módulo `inventory`", texto completo — cubre desde el slice 1
hasta el slice 9, con fechas internas desde 2026-07-27 hasta 2026-08-20):

> Módulo `inventory` | 🔶 slices 1-4 ✅ 2026-08-01 | **Slice 1**: catálogo (CRUD artículos/categorías/SKUs), stock por almacén (vía `movimiento_inventario` inmutable) y ajuste con segregación (`solicitar_ajuste` ≠ `aprobar_ajuste`, aprobador ≠ solicitante). Migración `be914c92a94b`. **Slice 2 — lote/FEFO** (2026-07-27, ADR-015): `lote` + `stock_lote`, control **opcional por artículo** (`articulo.controla_lote` — el queso sí, las servilletas no). La salida reparte por FEFO (vence antes, sale antes; sin vencimiento va al final → FIFO) y genera **un movimiento por lote tomado**, con `lote_id` explícito como override. El lote vencido se bloquea cuando el picking lo toca y publica `inventory.lote_vencido_detectado`; `POST /lotes/bloquear-vencidos` hace el barrido a demanda. La recepción de compra transporta el lote y vencimiento del proveedor (RN-VNC-002) y producción crea el suyo. Nada entra sin lote si el artículo lo controla: un ingreso sin lote cae en el lote del día. `POST /movimientos` pasa a devolver **lista** de movimientos. El hub replica `lote`/`stock_lote` (ADR-009). Migración `c9a2f4e18b60`. Tests: `tests/test_lotes.py`. **Slice 3 — conteo cíclico** (2026-08-01, ADR-019): `conteo` + `conteo_item` con la periodicidad configurada **en la categoría** (`categoria.frecuencia_conteo`, RN-INV-007) — no hay número universal. Calendario derivado del último conteo cerrado + frecuencia, sin tabla de programación; conteo general que pone al día a todas las categorías del almacén; stock esperado congelado al abrir; conteo **a ciegas** por defecto (`inventory.ver_stock_esperado`); el cierre genera un `ajuste` pendiente por diferencia (`ajuste.conteo_id`) sin mover stock, con margen `INVENTORY_MARGEN_AJUSTE_PCT`; `inventory.conteo_vencido` reporta a almacén y gerencia lo no contado en su fecha (RN-INV-021). Permisos nuevos `inventory.contar` y `inventory.ver_stock_esperado`. Migración `c4e70a91d5b8`. Tests: `tests/test_conteos.py`. **Slice 4 — abastecimiento interno** (2026-08-01, ADR-020): `reserva_stock` + `solicitud_insumos`/`solicitud_item` + `transferencia`/`transferencia_item`. El local pide, el supervisor aprueba **y reserva** el stock en el abastecedor, el central despacha (FEFO, un `transferencia_item` por lote) y el local recibe. `GET /stock` expone `cantidad`/`reservado`/`disponible` (RN-INV-009): reservar exige disponible, pero consumir nunca se bloquea por una reserva —una venta ya ocurrida no se niega— y por eso el disponible puede quedar negativo. Diferencias registradas, no corregidas: no se despacha más de lo aprobado ni se recibe más de lo enviado, menos sí (RN-INV-001/002). Cancelar libera reservas (RN-INV-010) y hay liberación manual (RN-INV-011). Transferencia lateral sucursal↔sucursal con la misma entidad. Migración `d8b35f1ca207`. Tests: `tests/test_transferencias.py`. **Slice 5 — recetas editables** (2026-08-03, ADR-023): CRUD de receta e ítems, duplicar con "(copy)", escalar por factor y **aritmética tecleada** en la cantidad ("1000/3"), evaluada en el servidor con `ast` y lista blanca —nunca `eval`— y redondeada a los decimales de la UdM del insumo (RN-COM-024); `receta_item.expresion` guarda lo tecleado para reeditarlo. `GET /inventory/unidades-medida` y contrato público `receta_resumen`. Migración `b6d1e83f47ac`. Tests: `tests/test_recetas_variantes.py`. **Slice 6 — abastecedor de respaldo** (2026-08-12, ADR-040, RN-INV-022, migración `a7c04e3b91d5`): `almacen.almacen_abastecedor_respaldo_id`. Con un solo abastecedor, dar de baja el central dejaba a la sucursal sin poder pedir y con un "almacén abastecedor no encontrado" que no decía qué hacer. `crear_solicitud` cae al respaldo **solo si el principal está dado de baja** —no por faltante, que tiene su propio camino— y **nunca** si el abastecedor vino explícito: despachar desde donde no se pidió es lo que el que recibe no puede notar hasta contar. La columna vive en `almacen` porque el que se abastece es el almacén, pero se elige desde el formulario de Sucursal. Dar de baja mira las dos columnas y el respaldo viaja al hub. **Slice 7 — devoluciones usables y carga masiva de recetas** (2026-08-13, ADR-046, RN-COM-030/031, sin migración): la API de devolución estaba completa desde el slice de merma y la pantalla era una tabla de **solo lectura** —registrar una devolución solo se podía llamando al endpoint a mano—; ahora hay formulario, botón de anular y ficha con qué se devolvió, a dónde fue y quién la registró o anuló. `registrar_devolucion` y `anular_devolucion` pasan a escribir en `audit_log`: mueven stock real y solo dejaban el evento, que responde otra pregunta. Suma `GET /inventory/skus` (no existía listado, así que ninguna pantalla podía ofrecer "qué se mueve") con el nombre del artículo, porque el código de un SKU no le dice nada a nadie. **Filtros del catálogo de recetas** por tipo y categoría, con el tipo **derivado** de si produce un artículo —sin columna nueva, que sería un segundo lugar donde puede estar mal— y viajando en la URL para filtrar en el servidor y poder compartir el enlace. **Carga masiva desde .xlsx**: plantilla con ejemplos e instrucciones, y una importación en **dos fases con revisión en el medio** —la primera dice qué entra y qué no sin guardar nada—, sin tabla de staging: una importación abandonada no deja nada que barrer. Un insumo que el catálogo no reconoce no cancela la carga (se elige o se omite **a la vista**) y una receta que no entra no arrastra a las demás (`SAVEPOINT` por receta). Reusa `crear_receta`/`agregar_item`, así que la cantidad acepta aritmética tecleada igual que en pantalla (RN-COM-024); el servidor revalida todo en la segunda fase porque lo que vuelve es un JSON que el cliente pudo editar. Dependencias nuevas: `openpyxl` y `python-multipart`. **2026-08-15 (ADR-048) — el importador no funcionaba desde el navegador**, y el backend no tenía nada que ver: el proxy de Next decodificaba todo cuerpo a texto y le fijaba `application/json`, así que la plantilla `.xlsx` se bajaba corrupta y llamada `plantilla.json`, y la subida de la fase 1 perdía el `boundary` del `multipart` antes de salir. Ahora el proxy pasa bytes en las dos direcciones y el recorrido completo queda cubierto por `frontend/uso/importador-recetas.spec.ts`. **Slice 9 — planillas de catálogo** (2026-08-20, ADR-052, RN-INV-025, sin migración): exportar pasa a ser **la plantilla con los datos adentro** — hasta ahora lo único que bajaba era una plantilla vacía de recetas, que sirve para la primera carga y para nada más. Las tres entidades del ERP (recetas, artículos y clientes) se bajan, se editan en Excel y se vuelven a subir. La identidad de una fila es la columna **`ID`** que escribe el export, o el **código interno** en artículos: el nombre no sirve de clave porque el nombre es justamente lo que se corrige. Se cierran las dos deudas que ADR-046 dejó abiertas — **el insumo que falta se crea desde el diálogo** (lo crea una persona, no el importador: ADR-046 descartó autocrear porque un nombre mal escrito ensucia el catálogo) y **la importación actualiza recetas existentes**, con los ingredientes ausentes conservándose salvo que se pida quitarlos receta por receta y viendo cuántas líneas se pierden. El catálogo de artículos suma sus cuatro endpoints con hojas `Artículos` y `SKUs`; la **unidad de un artículo existente no se cambia por planilla** y la fila se reporta en vez de reinterpretar en silencio el stock ya cargado. La E/S de `.xlsx` se extrae a `src/shared/planilla.py` (~150 líneas sin negocio adentro) y **no** se construyó un motor genérico: `sales` no puede importar de `inventory`, y qué hojas tiene cada libro son tres significados distintos. Se pasa a leer **por nombre de cabecera y no por posición**, que es lo que permitió agregar `ID` sin romper los archivos ya llenados. Las respuestas de validación pasan a tener `response_model` (devolvían un dict crudo y `openapi.json` las documentaba como `{}`). Tests: `tests/test_planilla.py`, `tests/test_importacion_articulos.py`, `frontend/uso/importador-articulos.spec.ts`. Diferido: guía remisión, `stock_merma`. | **Slice 8 — requerimiento de la jornada** (2026-08-19, ADR-051, RN-INV-023/024, migración `b5f27ac41e83`): responde lo que faltaba en `docs/domain/workflows.md` §Abastecimiento de locales — el conteo de fin de jornada ya describía un "borrador de solicitud de requerimiento" que nunca se construyó. `solicitud_insumos` gana el estado `borrador` (uno por almacén, no por usuario) y `solicitud_item` la columna `bajo_minimo_al_pedir`. `GET /solicitudes/borrador?almacen_id=` es get-or-create: arma la lista sola con lo que está bajo `stock_minimo` (cantidad para volver al mínimo) y, si ya existía, **suma** lo que cayó bajo mínimo desde la última vez sin tocar lo ya tecleado. `bajo_minimo_al_pedir` se **estampa al agregar el ítem y no se recalcula** —entre pedir y aprobar el stock se mueve, y recalcularla contaría otra historia—: es la respuesta a si el almacén distingue una urgencia real de un pedido por decisión del local, que sí. `POST/PATCH/DELETE /solicitudes/{id}/items[/{sku_id}]` editan el borrador con el permiso `solicitar_insumos` que ya existía; `POST /solicitudes/{id}/enviar` lo pasa a `pendiente` y **re-resuelve** el abastecedor (RN-INV-022 pudo cambiar mientras la lista estaba abierta). El borrador no aparece en `GET /solicitudes` salvo pidiendo `estado=borrador`, ni en `solicitudes_resumen_para_negociacion` (contrato hacia `purchases`), ni sube al hub offline (ADR-009): todavía no le pidió nada a nadie. Suma `GET /inventory/conteos` (faltaba: un conteo solo se podía pedir por su `id`) y `sucursal_id`/`marca_id` como filtros de `GET /solicitudes`, `GET /conteos` y `GET /conteos/programa`, resueltos por join a través del almacén sin columna nueva. **Pantallas nuevas**: `/inventario/solicitudes` (botón «Requerimiento de la jornada», tabla editable con badge Bajo mínimo / Pedido del local, aprobar/rechazar/cancelar) y `/inventario/conteos` (abrir, contar a ciegas, cerrar viendo los ajustes generados, anular con motivo) — el módulo no tenía ninguna de las dos hasta ahora, pese a que la API de solicitudes existía desde el slice 4. `tests/test_solicitudes_borrador.py` (10 casos) y recorrido de uso `frontend/uso/requerimientos.spec.ts`. Diferido: recortar el aprobado por SKU (`SolicitudAprobar.aprobadas` ya lo soporta la API) sin formulario todavía; encadenar el borrador al cierre de un conteo cíclico, que hoy son independientes.

**Estado vigente:** el diferido "guía remisión" del slice 9 se cerró el
2026-08-05 (ADR-027, ver entrada propia abajo). "`stock_merma`" y el resto
de diferidos de esta fila viven en `docs/roadmap/deuda/modulo-inventory.md`.
El diferido "recortar el aprobado por SKU" y "encadenar el borrador al
cierre de un conteo cíclico" del slice 8 siguen abiertos a la fecha de este
documento (2026-09-06).

### 2026-08-01 — Solicitudes / picking / transporte (F0, corrige plan obsoleto)

De la tabla F0 (fila "Solicitudes / picking / transporte"):

> Solicitudes / picking / transporte | 🔶 solicitudes y picking ✅ 2026-08-01 | **La fila estaba obsoleta** (verificado 2026-08-05): `requests` y `logistics` eran el plan de 2026-07-04 y el slice 4 de `inventory` (ADR-020) los dejó sin objeto. **Solicitudes** = `solicitud_insumos`/`solicitud_item` con su ciclo real (el local pide → el supervisor aprueba y reserva → el central despacha → el local recibe), más `reserva_stock`. **Picking** = el despacho reparte por FEFO y emite un `transferencia_item` por lote tomado. **Transferencias** sucursal↔sucursal con la misma entidad. Un módulo aparte habría necesitado el dominio de `inventory` (stock, lote, FEFO) para hacer exactamente eso, y CLAUDE.md prohíbe importarlo. La **guía de remisión** se cerró el 2026-08-05 (ADR-027) dentro de `inventory`, que era el argumento: es el comprobante del traslado, no un módulo. Queda sin dueño el transporte con ruteo/flota/liquidación propios, que hoy no existe como operación. |

### 2026-08-05 — Guía de remisión (ADR-027, dentro de `inventory`)

De la tabla F0 (fila "Integración de facturación electrónica (Factiliza)", extracto):

> [...] **Guía de remisión ✅ 2026-08-05** (ADR-027) — construida en `inventory`, no en `sales`: declara un traslado entre almacenes, no una venta. [...]

### 2026-08-05 — Pendiente de decisión: quién autoriza los ajustes de inventario

De "Pendientes de decisión (registro vivo)":

> - ✅ 2026-08-05 **Los ajustes de inventario los aprueba el supervisor**
>   de turno: está en el local, ve el faltante y decide en el momento. Ya
>   tenía `inventory.aprobar_ajuste`; queda confirmado y comentado. El
>   "supervisor de logística" como rol aparte se descarta: sería un rol
>   nuevo para una sola capacidad que el supervisor ya ejerce. La
>   segregación que importa —quien solicita no aprueba— vive en el dominio,
>   no en el rol.

Esto cierra el pendiente declarado en la sección de Almacén y Logística
(2026-07-19): "quién autoriza ajustes (admin vs. supervisor de logística,
rol aún no existe formalmente)".

### 2026-08-05 — Pendiente de decisión: mecanismo de parámetros configurables (incluye `inventory/margen_error_ajuste`)

De "Pendientes de decisión (registro vivo)" (extracto: intro del mecanismo,
general a varios módulos, más el punto propio de inventory):

> - ✅ 2026-07-27 **Mecanismo para los valores operativos configurables**
>   (umbral de OC, margen de contribución mínimo,
>   margen de error de ajuste, monto de caja chica, plazo de envío de
>   comprobantes, rangos salariales): decidido con el usuario que **no son
>   valores fijos** — se configuran en `parametro_empresa` por empresa, los
>   gestiona Gerencia, y un cambio puede sustentarse en un acta
>   (`decision_gerencial`) cuando amerite (no obligatorio para un ajuste
>   rutinario). Ver ADR-014, `data-model.md` §8c, RN-GER-008 y
>   `docs/gerencia/politica-gerencia.md#parámetros-operativos-configurables`.
>   **Ampliado 2026-08-02** (ADR-014 Addendum, RN-GER-009): cada parámetro
>   se configura **desde el módulo al que pertenece**, pero el cambio **no
>   surte efecto hasta que Gerencia lo aprueba** en su sección de
>   aprobaciones (aceptar / rechazar / modificar). Implementado: entidad,
>   migración `a71c9f4b2e60`, endpoints `/api/v1/parametros[/{id}/aprobar|
>   /rechazar]`, un permiso por módulo `<modulo>.proponer_parametro`.
>   Lo que queda abierto por cada uno de los puntos de abajo ya **no es el
>   mecanismo** (resuelto e implementado) sino que **el área proponga y
>   Gerencia apruebe el valor real** — trabajo de configuración/negocio, no
>   bloquea código:
>   **Propuestos 2026-08-05** con su sustento en
>   `docs/gerencia/propuesta-parametros-operativos.md` y cargados como
>   `estado='propuesto'` (`python -m src.seeders.parametros`, idempotente):
>   13 filas esperando en `/gerencia/parametros`. Cada propuesta declara de
>   dónde sale el número, **qué pasa si está mal** y cuándo revisarlo — un
>   parámetro mal puesto no rompe nada, distorsiona una decisión diaria
>   durante meses sin que nadie lo note.
>   - 🔶 `inventory/margen_error_ajuste` — propuesto 2 % **más piso de
>     S/ 20**: el porcentaje solo castiga a las categorías baratas y vuelve
>     ruido la alerta. El piso **exige código**, ver deuda de inventory.

### 2026-08-05 — BPMN de Abastecimiento de locales pasa a Vigente

De "Pendientes de decisión (registro vivo)" (extracto del bloque de BPMN de las
cuatro áreas nuevas):

> - ✅ 2026-08-05 BPMN de las cuatro áreas nuevas, con sus PROC registrados
>   en el maestro y su narrativa en `workflows.md` (el enfoque era *primero
>   SOP, luego BPMN*, y los SOPs ya estaban estables):
>   [...]
>   **PROC-INV-001 v0.2** Abastecimiento de locales, que además pasa de
>   Borrador a **Vigente**: el ciclo está implementado (ADR-020) y el traslado
>   ya emite guía (ADR-027).

### 2026-08-29 — Parche desplegables con búsqueda: catálogo de artículos con `?q=`

De "## Parche desplegables con búsqueda (versión a definir, 2026-08-29, en curso)"
(sección completa; el catálogo de `inventory` es el único endpoint que necesitó
búsqueda contra servidor):

> Nota de versión: al escribir esto se apuntó a "0.8.2", pero para cuando se
> integró con `main` esa versión ya la había cortado otra rama con contenido
> no relacionado (landing con dominio propio, marcaje de asistencia) y `main`
> ya iba en 0.9.0. El corte de versión de este parche queda pendiente — se
> hace al mergear, contra la versión real que tenga `main` en ese momento.
>
> Reportado desde el uso: crear una promoción pedía teclear los identificadores
> de los productos y categorías separados por coma. El campo era inusable —nadie
> se sabe un UUID— y fallaba en silencio: un id mal copiado creaba la promoción
> apuntando a un producto inexistente, que simplemente no se aplicaba nunca.
>
> Al revisarlo, el problema era más ancho: **114 `<select>` en 50 archivos y
> ninguno con búsqueda**. Y como `PAGE_SIZE_DEFECTO` es 50 y ningún `page.tsx`
> pide más, varios desplegables muestran solo la primera página del catálogo sin
> avisar que hay más — eso ya no es incomodidad, es un dato que falta.
>
> Se migran los **62** desplegables alimentados por la API. Los 52 restantes son
> enumerados escritos en el código —estados, tipos, modalidades, paginación— y
> siguen siendo `<select>` nativos: ponerle un buscador a tres opciones estorba.
>
> | Fase | Qué | Estado |
> |---|---|---|
> | 1 | `components/ui/combobox` (búsqueda, selección múltiple con fichas) sobre Base UI, con el filtrado en `lib/filtrar-opciones` | ✅ 2026-08-29 |
> | 1 | Promociones: productos, categorías y el producto gratis dejan de pedir ids a mano | ✅ 2026-08-29 |
> | 1 | `GET /inventory/articulos?q=` — el único catálogo que no entra completo en una página | ✅ 2026-08-29 |
> | 2 | Listas largas (artículos, recetas, cuentas contables, proveedores) + `page_size` explícito donde hoy se trunca | ✅ 2026-08-29 |
> | 2 | `?tipo=` repetible en artículos: "qué se produce" son subrecetas **y** mercadería | ✅ 2026-08-29 |
> | 3 | Listas acotadas (sucursales, almacenes, marcas, unidades de medida, roles, grupos, divisas, atributos) | ✅ 2026-08-29 |
> | 3 | Ayudante `elegirEnLista` en `e2e/util`: las pruebas dejan de hablar `selectOption` | ✅ 2026-08-29 |
>
> Quedan **52** `<select>` nativos y son todos de enumerados escritos en el
> código. No es deuda: un buscador sobre tres opciones estorba.
>
> Decisión: el filtrado ocurre **en el cliente**, sobre lo ya cargado. Solo los
> artículos buscan contra el servidor, porque son los únicos que no caben en el
> techo de 200 filas por página. Añadir `?q=` a los otros tres endpoints que se
> habían previsto resultó innecesario: SKUs y cuentas contables se devuelven sin
> paginar y proveedores entran de sobra.

### 2026-08-29 — Parche compras/inventario

De "## Parche compras/inventario (2026-08-29)" (sección completa):

> Reporte del usuario: no se podía crear un borrador de OC, el selector de
> artículos no mostraba todo el catálogo (se replicaba en compras), la OC era
> 100% inmutable incluso en borrador, y no había forma de registrar una compra
> a partir de solo una factura (sin OC previa). Investigación con 3 agentes
> Explore confirmó causa raíz de cada uno con evidencia de código; el
> descuento de stock por venta (que también se reportó como roto) resultó
> estar correctamente implementado y testeado — se le agregó visibilidad en
> vez de tocar la lógica.
>
> | # | Qué | Estado |
> |---|---|---|
> | 1 | Rol `comprador` sin `inventory.leer`: tumbaba la pantalla entera de nueva OC | ✅ 2026-08-29 |
> | 2 | Selector de artículos truncado a 50 (paginación sin `page_size`), en inventario, OC e importador de recetas | ✅ 2026-08-29 |
> | 3 | OC editable mientras está en `borrador` (`PATCH`); inmutable desde `emitida` como ya era | ✅ 2026-08-29 |
> | 4 | Compra directa sin OC previa, reutilizando `orden_compra` (ADR-081) | ✅ 2026-08-29 |
> | 5 | KPI de incidencias de inventario en el dashboard (el descuento de stock ya funcionaba y estaba testeado) | ✅ 2026-08-29 |
> | 6 | Alerta de stock bajo en el PDV, sin bloquear la venta (`GET /carta` → `stock_bajo`) | ✅ 2026-08-29 |
>
> Lo que **no** se hizo y quedó como deuda (`docs/roadmap/deuda/modulo-purchases.md`):
> la reconciliación completa estilo Odoo 18 entre compras/inventario/
> contabilidad (más allá de los eventos puntuales que ya existen) y la caja
> chica que la compra directa todavía no usa para pagar.

### 2026-08-30 — Parche 0.9.1: pantalla de stock/kardex y entrada de stock manual

De "## Parche 0.9.1 — tercer turno de prueba en staging (2026-08-30)" (filas
relevantes a inventory de esa tabla):

> | 1 | Pantalla de stock (`GET /inventory/stock` no lo consumía nadie) y kardex (`GET /inventory/movimientos`, nuevo) | ✅ 2026-08-30 |
> [...]
> | + | Entrada de stock manual: `/inventario/ajustes` solo aprobaba/rechazaba, sin forma de solicitar una — el formulario llama al mismo `POST /ajustes` que ya existía, y un artículo con lote puede declarar código y vencimiento al entrar | ✅ 2026-08-30 |

### 2026-09-04 — Inventario operable de punta a punta

De "## Inventario operable de punta a punta (2026-09-04)" (sección completa):

> Cuarto turno de prueba en staging: el módulo seguía inutilizable después de
> arreglar los artículos sin SKU. **Una sola causa, anterior a todo lo demás**:
> la fila de `stock` nacía sola con el primer movimiento, así que un almacén
> recién dado de alta era invisible y no había cómo arrancar. Y otra vez el
> patrón que se repite desde la 0.8.0 — endpoints entregados y probados, sin
> pantalla que los llame.
>
> | # | Qué | Estado |
> |---|---|---|
> | 1 | Un almacén declara qué artículos maneja (fila en cero) y con cuánto arranca (`carga_inicial`, sin segundo aprobador y solo sin historia previa) | ✅ 2026-09-04 |
> | 2 | El conteo ya tiene qué contar; el mensaje vacío deja de mentir ("no hay stock con esos filtros" cuando no había nada declarado) | ✅ 2026-09-04 |
> | 3 | Despacho de un requerimiento aprobado, con pantalla de picking y cantidad por línea | ✅ 2026-09-04 |
> | 4 | Pantalla de Traslados y recepción — lo despachado quedaba `en_transito` para siempre | ✅ 2026-09-04 |
> | 5 | `GET /solicitudes?almacen_abastecedor_id=`: la bandeja del que despacha, que no se podía preguntar | ✅ 2026-09-04 |
> | 6 | El seeder crea `almacen1` y `aprobador1`: sin dos usuarios el circuito no cierra ni para probarlo | ✅ 2026-09-04 |
> | + | El tipo de documento de una persona: «RUC» en el alta devolvía 500 y dejaba la fila ilegible (migración `c9f4a2e70b18`, vocabulario único en `src/shared/documento.py`) | ✅ 2026-08-30 |

### 2026-09-04 — Auditoría del 2026-08-30, Ola 2: transferencias y mermas

De "## Auditoría del 2026-08-30 — Ola 2 (2026-09-04)" (fila relevante a inventory
de la tabla de bloques):

> | `feat/inventario-transferencias-mermas` | #13 mermas y reservas sin pantalla; recepción parcial y traslado lateral sin entrada (el ciclo pedido lo cerró `fix/inventario-operable`) | ✅ 2026-09-04 — queda la guía de remisión, como deuda |

### 2026-09-05 — Auditoría del 2026-08-30, Ola 4: paginación server-side (`GET /inventory/lotes` gana tope)

De "## Auditoría del 2026-08-30 — Ola 4, calidad (2026-09-05)" (fila relevante a
inventory de la tabla de bloques):

> | `fix/paginacion-server-side` | #14 el recorte se avisa en las nueve pantallas que traían 200 filas y paginaban en el navegador; `GET /inventory/lotes` gana tope | ✅ 2026-09-05 |

## Fuentes

- Línea 12: fila F0 "Especificaciones de módulos base" (READMEs de inventory, entre otros).
- Líneas 705-706, 688-704, 727-729: sección "Modelado de BD — siguiente sesión" (entidades sku/lote/reserva_stock/conteo).
- Línea 33: fila F0 "Almacén-Logística: procesos y plantillas".
- Líneas 961-1006: sección "Área Almacén y Logística — conteo, vencimientos/merma, transporte (2026-07-19)".
- Líneas 1008-1040: sección "Slice Venta — núcleo de datos (2026-07-20)" (tablas base de inventory).
- Líneas 1092-1097: sección "Revisión de consistencia y correcciones (2026-07-20)" (stock_lote, evento inventory.lote_vencido_detectado).
- Línea 22: fila F0 "Módulo `inventory`" completa (slices 1 a 9, 2026-07-27 a 2026-08-20).
- Línea 28: fila F0 "Solicitudes / picking / transporte".
- Línea 41: fila F0 "Integración de facturación electrónica (Factiliza)" (extracto: guía de remisión ADR-027).
- Líneas 435-441: "Pendientes de decisión" — quién autoriza ajustes de inventario.
- Líneas 380-398, 414-416: "Pendientes de decisión" — mecanismo de parámetros configurables e `inventory/margen_error_ajuste`.
- Líneas 491-500: "Pendientes de decisión" — BPMN PROC-INV-001 a Vigente.
- Líneas 96-134: "Parche desplegables con búsqueda (2026-08-29)".
- Líneas 164-187: "Parche compras/inventario (2026-08-29)".
- Líneas 230-239: "Parche 0.9.1 — tercer turno de prueba en staging (2026-08-30)" (filas de stock/kardex y ajuste manual).
- Líneas 241-258: "Inventario operable de punta a punta (2026-09-04)".
- Líneas 260-280: "Auditoría del 2026-08-30 — Ola 2 (2026-09-04)" (fila feat/inventario-transferencias-mermas).
- Líneas 330-338: "Auditoría del 2026-08-30 — Ola 4, calidad (2026-09-05)" (fila fix/paginacion-server-side).
- Líneas 1405-1413: "Fase de procesos (tras el modelado de BD)" (plan inicial, pasos 3 y 5).

Rangos de línea leídos en `ROADMAP.md` para esta extracción: 1-1414 (archivo
completo, en tramos de lectura de 1 a ~135 líneas).
