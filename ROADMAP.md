# Bitácora de construcción — Provecho ERP

Registro de lo construido y lo pendiente. Actualizar en cada cambio relevante.

## Estado — F0 (Fundaciones)

| Área | Estado | Notas |
|------|--------|-------|
| Scaffold del proyecto | ✅ 2026-07-04 | Estructura, Docker, CI, docs, reglas |
| Reestructura de docs por temas (foundation/domain/architecture/engineering/security/product) | ✅ 2026-07-04 | Índice en `docs/00_PROJECT.md` |
| Docs de conocimiento (glosario, filosofía, reglas, eventos, máquinas de estado, autorización) | ✅ 2026-07-04 | Base para desarrollo asistido por IA |
| Especificaciones de módulos base | ✅ 2026-07-04 | READMEs de users, inventory, sales, purchases, accounting |
| Modelo de datos (v1, documento) | ✅ 2026-07-04 | `docs/architecture/data-model.md` |
| Modelo de datos ampliado (bloques Inventario, Documentos, Movimientos, Operación comercial, Recursos, Información, RRHH, Actores) | ✅ 2026-07-14 | `docs/architecture/data-model.md` — ~50 entidades nuevas/enriquecidas; ver detalle abajo |
| Core (app factory, settings, db, event bus) | ✅ 2026-07-04 | Endpoint `/health` operativo. **Bus revisado 2026-08-01 (ADR-016)**: el evento se despacha recién al commitear la sesión que lo publicó — antes se entregaba en medio de la transacción y un rollback dejaba stock descontado por una venta inexistente. |
| Auditoría arquitectónica | ✅ 2026-08-01 | `docs/architecture/audit-2026-08-01.md`. Veredicto: arquitectura sana y proporcionada, sin sobreingeniería; separación de capas al 100 % y dominio puro. Aplicado: eventos post-commit (ADR-016), jerarquía de errores unificada (ADR-017, −251 líneas en routers), contrato público `users.tiene_permiso`, y `tests/test_arquitectura.py` (98 casos) que congela los límites. Descartado con justificación: dividir `rules.py` (120 líneas el mayor), dividir `repositories.py` (ya son 9-13 clases pequeñas por archivo), eventos tipados (sin type checker en CI el beneficio es solo documental) y separar eventos sync/async (lo asíncrono real ya vive en Celery). Diferido: `Empresa`/`Sucursal`/`Almacen`/`Persona` de `users` a `shared/models` (37 archivos; conviene junto al CRUD de organización), contrato público de `inventory` para `Articulo`/`Receta`, y `core/dashboard_router` a un módulo propio. |
| Modelado de base de datos completo (SQLAlchemy + Alembic) | 🔶 en curso 2026-07-25 | Bloque transversal + organización (11) + slice Venta núcleo (11) + slice Cobro/Comprobante/Caja (8) + slice auth/RBAC (7) + slice inventory core (3) — 40 tablas en total. BD de desarrollo corre en el **Postgres del `docker-compose`** (host `localhost:5433`) desde 2026-08-08, por latencia; Supabase queda como alternativa documentada en `docs/engineering/devops.md`. Resto por slice vertical. |
| Módulo `users` (auth JWT + PIN + RBAC) | ✅ 2026-07-25 | Slice auth+CRUD implementado: 7 tablas RBAC (`rol`, `permiso`, `usuario_rol`, `rol_permiso`, `usuario_sucursal`, `refresh_token`, `audit_log`) + lockout en `usuario`. Login/refresh(rotativo+detección de reuso)/logout/me + CRUD admin de usuarios/roles/permisos/asignaciones. Argon2id, JWT, `require_permission` deny por defecto. `docs/security/authorization.md`. Restricciones JSONB por permiso: aplicadas desde 2026-08-02 (ADR-022, ver Deuda técnica). **Token de API para agentes** (2026-08-08, ADR-032, migración `b3f7d21a9c04`): una cuenta `tipo=agente_ia` se autentica con `token_agente` (256 bits, solo el SHA-256 se persiste, revocable de a uno) en vez de PIN — un PIN de 6 dígitos son 20 bits en un `.env` y su lockout apaga integraciones. `get_claims` distingue por el prefijo `prv_` y arma **los mismos claims**: el RBAC no cambia. **CRUD de organización por API** (2026-08-08, permiso propio `organizacion.gestionar`): grupo, empresa, marca, licencia de marca, sucursal y almacén; sin cambios de esquema. **Reseteo de PIN y consulta de documento** (2026-08-12, ADR-041, migración `a7c04e3b91d5`): un PIN olvidado no se recuperaba —Argon2id— y el frontend documentaba un autoservicio que no existía. `users.resetear_pin` (permiso propio, a `rrhh_admin`) devuelve la cuenta al PIN por defecto y **la bloquea**: `get_current_user` lee `usuario.debe_cambiar_pin` de la base —no de un claim, que se congela al emitir— y responde 403 a todo salvo verse, cambiarlo y salir; se revocan sus sesiones y se limpia el lockout. Suma `POST /users/me/pin` (sin permiso, con PIN actual). Y `GET /consulta/{dni,ruc}/{n}` en `core` expone al fin el cliente de Factiliza que existía sin consumidor: botón "Buscar" en Personas y Proveedores que prellena sin decidir, permiso propio `consulta.documento` porque cada consulta gasta cuota y trae datos de quien todavía no es nadie en el sistema. **La consulta, visible y con cuota** (2026-08-15): el botón faltaba en Ventas → Clientes —la pantalla que promete que «SUNAT manda sobre la razón social tecleada»— y ningún punto de montaje miraba el permiso, así que un `contador` lo veía y se comía un 403; el gate vive ahora dentro del componente y `permisos` es prop obligatoria. Cierra además la deuda del rate limit: `GET /consulta/{dni,ruc}/{n}` cuenta **por usuario y por IP** (20 y 60 por minuto, configurables) reusando `core/rate_limit.py` —fail-open incluido—, porque en un local todas las cajas salen por la misma dirección y limitar solo por IP castiga al equipo entero por uno. **La consulta llega a caja** (2026-08-22, addendum de ADR-041): faltaba el punto donde más se teclea un documento —el PDV—, el único de los cuatro y justo aquel por el que el `cajero` tiene el permiso. Quedó en sus **dos** momentos: el alta de cliente y el receptor del comprobante. En caja hay un solo campo para los dos documentos, así que el modo `auto` deja que el largo decida el padrón (8 → RENIEC, 11 → SUNAT, la misma regla que ya elegía boleta o factura, RN-CPP-003, aislada en `frontend/lib/documento.ts` con su prueba); un largo intermedio no se consulta, porque una consulta a ciegas gasta cuota para volver con un "no encontrado" que no significa nada. Montarlo obligó a una segunda forma del mismo botón: `BuscarDocumento` escribe en el DOM del `<form>` y el PDV lleva estado de React, así que `ConsultaDocumento` recibe el número y devuelve la respuesta cruda por `onDatos` — se descartó rehacer el diálogo de cobro como formulario no controlado. El campo de documento del alta acepta ahora los dos largos: con 11 el cliente nace jurídico, que es lo que `crear_cliente` ya hacía y la pantalla no dejaba pedir. **Y RRHH, donde más pesa**: `contratar_postulante` creaba la `persona` con lo que el candidato escribió de sí mismo en el formulario **público** —sin sesión ni permiso—, y con ese nombre se firma el contrato y se declara a SUNAT; `sales` y `purchases` ya pasaban el documento por `nombres_desde_dni` y RRHH no. Ahora el servidor lo aplica aunque nadie apriete el botón, y el diálogo de contratar suma nombres/apellidos editables para poder verlo antes (precedencia RENIEC > lo revisado > lo declarado; con carné o pasaporte no se consulta). De paso, un **401 del proveedor se llamaba "respuesta ilegible"** —solo el 404 vacío y el 5xx se trataban aparte, así que el 401 moría en el parseo de JSON— y mandaba a buscar un error de formato donde lo que hay que revisar es la credencial. |
| Migraciones Alembic | 🔶 cabeza `d5c81a7f3b62` (2026-08-09, consumo de personal, encadenada detrás de `b3f7d21a9c04`) | **Aplicada en la BD dev el 2026-08-09** (`alembic upgrade head` + `downgrade` probados contra el Postgres local; el permiso nuevo `sales.registrar_consumo_personal` lo siembra el seeder). Nota para futuras migraciones de enums: los `Enum(native_enum=False)` del proyecto **no crean CHECK** en Postgres (default de SQLAlchemy 2.0), son `VARCHAR` — agregar un valor que entre en el largo declarado no toca el esquema. Con una migración sin aplicar, `python -m src.core.esquema` reporta deriva a propósito. Dos ramas que salen del mismo commit crean **dos cabezas**, y `alembic upgrade head` falla en el despliegue, no en el merge que las causó: lo atrapan `test_el_repo_tiene_una_sola_cabeza` y el job `backend`, y se arregla repuntando el `down_revision` de la que llega segunda. Ojo: la base es **una sola para todos los worktrees**, así que otra rama en curso puede dejarla en una revisión que la tuya todavía no conoce — es el mismo comportamiento que había con Supabase, no lo trajo la mudanza. Las primeras seis fueron transversal+org, slice Venta, cobro/caja, cliente opcional, slice auth/RBAC e inventory core; el detalle de cada slice posterior va en su fila. Tras aplicar una migración que suma permisos hay que correr `python -m src.seeders.seed` (idempotente): la migración crea tablas, no filas de RBAC. |
| Seeders (admin / PIN 123456, org base) | ✅ 2026-07-27 | `src/seeders/seed.py` (idempotente, prohibido en prod): matriz de roles/permisos semilla, `admin`/PIN `123456` y la **organización real** del grupo — empresa Majambo EIRL (RUC 20450311520, Jr. Ramón Castilla 248 - Tarapoto, zona `amazonia_ley27037`), marca Charlie's Pizzas **licenciada** a la empresa (`licencia_marca`), sucursales `CH1` (Jr. Ramón Castilla 248) y `CH2` (Jr. Lamas 299) activas y alquiladas (RN-IMP-004), almacén central `WH1` (`sucursal_id` NULL). Requirió `almacen.direccion` (migración `e5a1c93b7d40`): el central no cuelga de ninguna sucursal y no había dónde guardar su ubicación. Correr: `python -m src.seeders.seed`. **CRUD de organización por API: ✅ 2026-08-08** — el seeder deja de ser la única vía para crear empresa/marca/sucursal/almacén. Diferido: almacenes de sucursal de CH1/CH2 (no pedidos; su mín./máx. por SKU depende de datos de operación inexistentes). |
| Módulo `inventory` | 🔶 slices 1-4 ✅ 2026-08-01 | **Slice 1**: catálogo (CRUD artículos/categorías/SKUs), stock por almacén (vía `movimiento_inventario` inmutable) y ajuste con segregación (`solicitar_ajuste` ≠ `aprobar_ajuste`, aprobador ≠ solicitante). Migración `be914c92a94b`. **Slice 2 — lote/FEFO** (2026-07-27, ADR-015): `lote` + `stock_lote`, control **opcional por artículo** (`articulo.controla_lote` — el queso sí, las servilletas no). La salida reparte por FEFO (vence antes, sale antes; sin vencimiento va al final → FIFO) y genera **un movimiento por lote tomado**, con `lote_id` explícito como override. El lote vencido se bloquea cuando el picking lo toca y publica `inventory.lote_vencido_detectado`; `POST /lotes/bloquear-vencidos` hace el barrido a demanda. La recepción de compra transporta el lote y vencimiento del proveedor (RN-VNC-002) y producción crea el suyo. Nada entra sin lote si el artículo lo controla: un ingreso sin lote cae en el lote del día. `POST /movimientos` pasa a devolver **lista** de movimientos. El hub replica `lote`/`stock_lote` (ADR-009). Migración `c9a2f4e18b60`. Tests: `tests/test_lotes.py`. **Slice 3 — conteo cíclico** (2026-08-01, ADR-019): `conteo` + `conteo_item` con la periodicidad configurada **en la categoría** (`categoria.frecuencia_conteo`, RN-INV-007) — no hay número universal. Calendario derivado del último conteo cerrado + frecuencia, sin tabla de programación; conteo general que pone al día a todas las categorías del almacén; stock esperado congelado al abrir; conteo **a ciegas** por defecto (`inventory.ver_stock_esperado`); el cierre genera un `ajuste` pendiente por diferencia (`ajuste.conteo_id`) sin mover stock, con margen `INVENTORY_MARGEN_AJUSTE_PCT`; `inventory.conteo_vencido` reporta a almacén y gerencia lo no contado en su fecha (RN-INV-021). Permisos nuevos `inventory.contar` y `inventory.ver_stock_esperado`. Migración `c4e70a91d5b8`. Tests: `tests/test_conteos.py`. **Slice 4 — abastecimiento interno** (2026-08-01, ADR-020): `reserva_stock` + `solicitud_insumos`/`solicitud_item` + `transferencia`/`transferencia_item`. El local pide, el supervisor aprueba **y reserva** el stock en el abastecedor, el central despacha (FEFO, un `transferencia_item` por lote) y el local recibe. `GET /stock` expone `cantidad`/`reservado`/`disponible` (RN-INV-009): reservar exige disponible, pero consumir nunca se bloquea por una reserva —una venta ya ocurrida no se niega— y por eso el disponible puede quedar negativo. Diferencias registradas, no corregidas: no se despacha más de lo aprobado ni se recibe más de lo enviado, menos sí (RN-INV-001/002). Cancelar libera reservas (RN-INV-010) y hay liberación manual (RN-INV-011). Transferencia lateral sucursal↔sucursal con la misma entidad. Migración `d8b35f1ca207`. Tests: `tests/test_transferencias.py`. **Slice 5 — recetas editables** (2026-08-03, ADR-023): CRUD de receta e ítems, duplicar con "(copy)", escalar por factor y **aritmética tecleada** en la cantidad ("1000/3"), evaluada en el servidor con `ast` y lista blanca —nunca `eval`— y redondeada a los decimales de la UdM del insumo (RN-COM-024); `receta_item.expresion` guarda lo tecleado para reeditarlo. `GET /inventory/unidades-medida` y contrato público `receta_resumen`. Migración `b6d1e83f47ac`. Tests: `tests/test_recetas_variantes.py`. **Slice 6 — abastecedor de respaldo** (2026-08-12, ADR-040, RN-INV-022, migración `a7c04e3b91d5`): `almacen.almacen_abastecedor_respaldo_id`. Con un solo abastecedor, dar de baja el central dejaba a la sucursal sin poder pedir y con un "almacén abastecedor no encontrado" que no decía qué hacer. `crear_solicitud` cae al respaldo **solo si el principal está dado de baja** —no por faltante, que tiene su propio camino— y **nunca** si el abastecedor vino explícito: despachar desde donde no se pidió es lo que el que recibe no puede notar hasta contar. La columna vive en `almacen` porque el que se abastece es el almacén, pero se elige desde el formulario de Sucursal. Dar de baja mira las dos columnas y el respaldo viaja al hub. **Slice 7 — devoluciones usables y carga masiva de recetas** (2026-08-13, ADR-046, RN-COM-030/031, sin migración): la API de devolución estaba completa desde el slice de merma y la pantalla era una tabla de **solo lectura** —registrar una devolución solo se podía llamando al endpoint a mano—; ahora hay formulario, botón de anular y ficha con qué se devolvió, a dónde fue y quién la registró o anuló. `registrar_devolucion` y `anular_devolucion` pasan a escribir en `audit_log`: mueven stock real y solo dejaban el evento, que responde otra pregunta. Suma `GET /inventory/skus` (no existía listado, así que ninguna pantalla podía ofrecer "qué se mueve") con el nombre del artículo, porque el código de un SKU no le dice nada a nadie. **Filtros del catálogo de recetas** por tipo y categoría, con el tipo **derivado** de si produce un artículo —sin columna nueva, que sería un segundo lugar donde puede estar mal— y viajando en la URL para filtrar en el servidor y poder compartir el enlace. **Carga masiva desde .xlsx**: plantilla con ejemplos e instrucciones, y una importación en **dos fases con revisión en el medio** —la primera dice qué entra y qué no sin guardar nada—, sin tabla de staging: una importación abandonada no deja nada que barrer. Un insumo que el catálogo no reconoce no cancela la carga (se elige o se omite **a la vista**) y una receta que no entra no arrastra a las demás (`SAVEPOINT` por receta). Reusa `crear_receta`/`agregar_item`, así que la cantidad acepta aritmética tecleada igual que en pantalla (RN-COM-024); el servidor revalida todo en la segunda fase porque lo que vuelve es un JSON que el cliente pudo editar. Dependencias nuevas: `openpyxl` y `python-multipart`. **2026-08-15 (ADR-048) — el importador no funcionaba desde el navegador**, y el backend no tenía nada que ver: el proxy de Next decodificaba todo cuerpo a texto y le fijaba `application/json`, así que la plantilla `.xlsx` se bajaba corrupta y llamada `plantilla.json`, y la subida de la fase 1 perdía el `boundary` del `multipart` antes de salir. Ahora el proxy pasa bytes en las dos direcciones y el recorrido completo queda cubierto por `frontend/uso/importador-recetas.spec.ts`. **Slice 9 — planillas de catálogo** (2026-08-20, ADR-052, RN-INV-025, sin migración): exportar pasa a ser **la plantilla con los datos adentro** — hasta ahora lo único que bajaba era una plantilla vacía de recetas, que sirve para la primera carga y para nada más. Las tres entidades del ERP (recetas, artículos y clientes) se bajan, se editan en Excel y se vuelven a subir. La identidad de una fila es la columna **`ID`** que escribe el export, o el **código interno** en artículos: el nombre no sirve de clave porque el nombre es justamente lo que se corrige. Se cierran las dos deudas que ADR-046 dejó abiertas — **el insumo que falta se crea desde el diálogo** (lo crea una persona, no el importador: ADR-046 descartó autocrear porque un nombre mal escrito ensucia el catálogo) y **la importación actualiza recetas existentes**, con los ingredientes ausentes conservándose salvo que se pida quitarlos receta por receta y viendo cuántas líneas se pierden. El catálogo de artículos suma sus cuatro endpoints con hojas `Artículos` y `SKUs`; la **unidad de un artículo existente no se cambia por planilla** y la fila se reporta en vez de reinterpretar en silencio el stock ya cargado. La E/S de `.xlsx` se extrae a `src/shared/planilla.py` (~150 líneas sin negocio adentro) y **no** se construyó un motor genérico: `sales` no puede importar de `inventory`, y qué hojas tiene cada libro son tres significados distintos. Se pasa a leer **por nombre de cabecera y no por posición**, que es lo que permitió agregar `ID` sin romper los archivos ya llenados. Las respuestas de validación pasan a tener `response_model` (devolvían un dict crudo y `openapi.json` las documentaba como `{}`). Tests: `tests/test_planilla.py`, `tests/test_importacion_articulos.py`, `frontend/uso/importador-articulos.spec.ts`. Diferido: guía remisión, `stock_merma`. | **Slice 8 — requerimiento de la jornada** (2026-08-19, ADR-051, RN-INV-023/024, migración `b5f27ac41e83`): responde lo que faltaba en `docs/domain/workflows.md` §Abastecimiento de locales — el conteo de fin de jornada ya describía un "borrador de solicitud de requerimiento" que nunca se construyó. `solicitud_insumos` gana el estado `borrador` (uno por almacén, no por usuario) y `solicitud_item` la columna `bajo_minimo_al_pedir`. `GET /solicitudes/borrador?almacen_id=` es get-or-create: arma la lista sola con lo que está bajo `stock_minimo` (cantidad para volver al mínimo) y, si ya existía, **suma** lo que cayó bajo mínimo desde la última vez sin tocar lo ya tecleado. `bajo_minimo_al_pedir` se **estampa al agregar el ítem y no se recalcula** —entre pedir y aprobar el stock se mueve, y recalcularla contaría otra historia—: es la respuesta a si el almacén distingue una urgencia real de un pedido por decisión del local, que sí. `POST/PATCH/DELETE /solicitudes/{id}/items[/{sku_id}]` editan el borrador con el permiso `solicitar_insumos` que ya existía; `POST /solicitudes/{id}/enviar` lo pasa a `pendiente` y **re-resuelve** el abastecedor (RN-INV-022 pudo cambiar mientras la lista estaba abierta). El borrador no aparece en `GET /solicitudes` salvo pidiendo `estado=borrador`, ni en `solicitudes_resumen_para_negociacion` (contrato hacia `purchases`), ni sube al hub offline (ADR-009): todavía no le pidió nada a nadie. Suma `GET /inventory/conteos` (faltaba: un conteo solo se podía pedir por su `id`) y `sucursal_id`/`marca_id` como filtros de `GET /solicitudes`, `GET /conteos` y `GET /conteos/programa`, resueltos por join a través del almacén sin columna nueva. **Pantallas nuevas**: `/inventario/solicitudes` (botón «Requerimiento de la jornada», tabla editable con badge Bajo mínimo / Pedido del local, aprobar/rechazar/cancelar) y `/inventario/conteos` (abrir, contar a ciegas, cerrar viendo los ajustes generados, anular con motivo) — el módulo no tenía ninguna de las dos hasta ahora, pese a que la API de solicitudes existía desde el slice 4. `tests/test_solicitudes_borrador.py` (10 casos) y recorrido de uso `frontend/uso/requerimientos.spec.ts`. Diferido: recortar el aprobado por SKU (`SolicitudAprobar.aprobadas` ya lo soporta la API) sin formulario todavía; encadenar el borrador al cierre de un conteo cíclico, que hoy son independientes.
| Módulo `purchases` | 🔶 slice core ✅ 2026-07-25 | CRUD de proveedores (natural liga a `persona`, jurídico con RUC propio) y ciclo de OC tipo `insumo` (crear → emitir → recibir → anular), con idempotencia y umbral de aprobación configurable. `purchases.compra_recibida` → inventory suma stock y recalcula `costo_promedio`. Conformidad de comprobante (`purchases.dar_conformidad`) registra el `comprobante` recibido y dispara `purchases.comprobante_conforme` → cola de pago en `accounting`. Migración `4ff85f833b29` aplicada. Diferido: ver Deuda técnica. |
| Módulo `sales` (PDV) | 🔶 slices 1-3 ✅ 2026-07-27 | Venta con correlativo+idempotencia → `sales.venta_confirmada` → inventory descuenta por receta (+merma+empaque); cobro con pagos parciales → `pagada`; anulación pre-pago repone stock; CRUD productos/medios de pago. **KDS** (slice 2): pantallas configurables por sucursal y categorías (`kds_pantalla`, migración `7672566bf189`), avance por ítem en `venta_item.estado_preparacion` (fuente única → todas las pantallas ven el avance real), tipos preparación/despacho, comanda imprimible con contador de reimpresiones, evento `sales.pedido_listo`, rol `cocinero`; **pantalla KDS** en `frontend/app/kds/` (2026-08-03, tarjeta por pedido con tachado por ítem, polling 3 s). Kiosk/Central de Pedidos = clientes del mismo contrato, no módulos. **Cumplimiento de pedido** (slice 3, 2026-07-27): `PROC-OPE-002` definido como UN proceso (área Operaciones) y su etapa de entrega implementada — `POST /sales/ventas/{id}/entrega` con permiso propio `sales.entregar_pedido` y rol `despachador`, idempotente, publica `sales.venta_entregada` (disparador de la encuesta de marketing, RN-COM-007). **Slice PDV** (slice 4, 2026-07-28, ADR-018, migración `d7e3b8c14f52`): `mesa` tipada por sucursal + mapa de salón derivado; `grupo_cobro` para dividir la cuenta y emitir un comprobante por pagador (RN-COM-018); receptor tecleado en caja que decide boleta/factura sin cliente registrado (RN-CPP-003); descuento manual de orden con motivo y autorizador (RN-COM-017, permiso propio). Suma `POST /sales/clientes` y `GET /sales/ventas`. **Variantes y opciones** (slice 5, 2026-08-03, ADR-023, migración `b6d1e83f47ac`): Personal/Mediana/Familiar son productos hijos con receta y precio completo propios (RN-COM-022) — no un recargo sobre un precio base; el padre agrupa y no se vende. `producto_opcion_grupo` declara cuántos extras hay que elegir (RN-COM-023): `minimo >= 1` **es** ser obligatorio, sin flag aparte, y la regla se hace cumplir al confirmar la venta porque el kiosko entra por el mismo endpoint. Nombres normalizados a formato título en el servidor. Frontend: **Catálogo como módulo propio** (`/catalogo/productos`, no `/ventas`), con gate por permiso exacto `sales.gestionar_catalogo` — un cajero tiene `sales.crear` y con el filtro por prefijo veía y leía toda la carta; ahora el módulo no le aparece ni entrando por URL (enmienda a ADR-013). Ficha de producto que **elige** recetas ya creadas (el editor vive en Catálogo → Recetas; tenerlo en los dos lados hacía pensar que eran dos recetas distintas) y selector obligatorio de presentación + extras en el PDV. **Consumo de personal** (slice 6, 2026-08-09, ADR-034, migración `d5c81a7f3b62`): la comida del staff en fines de semana, feriados y días de alta actividad es una orden de `tipo="consumo_personal"` con **todas sus líneas en cero** —ni lista de precios ni precio del cliente—, que se prepara y despacha como cualquier pedido pero **no se cobra ni emite comprobante** y cierra con la entrega (`estado="cerrada"`, su único cierre posible: nunca pasa por caja). No se hizo con el descuento del 100% que ya existía porque esa venta declara un ingreso inexistente, la atribuye marketing y no se puede cerrar. La autoriza un encargado con PIN (`sales.registrar_consumo_personal`) y exige motivo de un enum cerrado. El costo sale de `inventory` como `consumo_interno`, valorizado al costo promedio, y `accounting` lo asienta como gasto de alimentación de personal; anularlo repone el insumo y reversa el asiento. Tests: `tests/test_consumo_personal.py`. **Restas y lienzo de nodos** (slice 7, 2026-08-09, ADR-035, migración `a4f1d0c8b573`): cierra el último tramo de RN-PRD-004 —tamaño → combinación → extras → **restas**—, el único que nunca se implementó. `venta_item.sin_articulo_ids` guarda qué insumos NO lleva la línea ("sin cebolla"): no cambia el precio, sí el consumo — `inventory` salta ese insumo y la reposición por anulación/nota de crédito devuelve solo lo consumido (RN-COM-028/RN-PRD-019). Lo quitable **es** la receta (`GET /productos/{id}/quitables`), sin tabla ni flag que mantener; pedir quitar lo que la receta no pone devuelve 409, salvo en el replay del hub. Cocina las ve en KDS y comanda (`SIN CEBOLLA`). Suma `DELETE /productos/{id}/extras/{extra_id}` y `DELETE /productos/{id}/grupos/{grupo_id}` (deuda de ADR-023). Frontend: **lienzo de nodos** a pantalla completa en `/catalogo/productos/{id}/nodos` — el árbol producto → tamaños → grupos → extras → restas → empaque → PLATO sobre un canvas oscuro con pan/zoom, minimapa y aristas curvas (`@xyflow/react`), editable en su estructura y con simulación en vivo de receta fusionada, costo y margen por combinación (la fusión se calcula en el cliente y no se guarda: lo que se descuenta sale del servidor). Vive fuera del shell del módulo, como PDV y KDS, así que hace su propio guard de permiso — con prueba e2e de que un cajero no entra ni por URL. La primera versión eran filas de `<div>` con líneas en CSS y la rechazó el usuario en el mismo día: el cambio de decisión está en la enmienda de ADR-035. Chips de "sin…" en el PDV, ticket y comanda. Tests: `tests/test_restas.py`. **El PDV deja de pedir una caja ya abierta** (2026-08-12, sin migración): `GET /accounting/cajas/abiertas` exigía `accounting.leer` —el permiso de todo el módulo contable, que el rol `cajero` no tiene ni le corresponde—, devolvía 403, y el PDV lo leía como "no hay caja": pedía la apertura y la apertura rebotaba por duplicada. Ahora acepta `sucursal_id` y con ese alcance basta `accounting.caja_operar`, validado contra el tenant (ADR-004) y no contra el parámetro; sin él sigue siendo la empresa entera con `accounting.leer`. La caja es del **punto de venta**, así que el turno que abrió un compañero vale para todo el local. **La pizza se puede vender** (2026-08-12, ADR-038, sin migración): `GET /carta` armaba los grupos de opciones leyendo el producto **padre**, pero cuelgan de la **variante** —que es la que se prepara (RN-COM-022/023)—, así que la carta devolvía `extras: []`, el PDV no dibujaba "Sabor", habilitaba Guardar sin elegirlo y el servidor rechazaba con 409 algo que la pantalla nunca ofreció; sin venta confirmada tampoco llegaba comanda al KDS. Ahora cada variante viaja con su `extras[]` (aditivo) y el PDV ofrece los de la presentación elegida, que son exactamente los que el servidor acepta. El hub no necesita nada: replica las tablas crudas y arma la carta con este mismo código. **La orden enviada sigue viva** (2026-08-12, ADR-043, RN-COM-029, sin migración): admite líneas nuevas (`POST /ventas/{id}/items`, mismo permiso que crear y sin firma de nadie — la mesa que pide de a poco no tiene por qué terminar con dos cuentas) y **quitar es gratis dentro de 5 minutos**; pasada la ventana lo firma un supervisor (RN-COM-020). Antes agregar era imposible y quitar exigía el PIN siempre, con lo que el control se ejecutaba veinte veces por turno y terminaba en la sesión del encargado abierta en la caja. La ventana de la orden se mide contra su **última** línea, y un lote necesita firma si **alguna** salió de ella. El agregado republica `sales.venta_confirmada` con **el incremento** y no con el acumulado: así inventory descuenta solo lo nuevo y accounting no asienta la venta dos veces. En el PDV, además, el "+" reusa el borrador vacío en vez de apilar pestañas y una pestaña sin líneas se descarta con su "×". **La variante hereda del padre** (2026-08-12, ADR-042, sin migración): el arreglo anterior servía para el catálogo del **seeder** —grupos en la variante— y dejaba roto el armado **a mano**, porque el lienzo cuelga "+ grupo" del nodo activo, que es el padre mientras el producto no tiene tamaños. Ahora una variante ofrece lo suyo **más lo del padre** (`grupos_efectivos`/`extras_efectivos`/`admite_extra_efectivo`, con el vínculo propio ganando sobre el heredado), y la venta acepta exactamente lo que la carta ofreció: dónde quedó colgado el grupo dejó de decidir nada. **El cajero anula una orden enviada** con firma de supervisor: `sales.anular` es de supervisor y el botón del PDV devolvía 403 sin decir qué hacer, dejando el pedido en cocina. El endpoint entra con `sales.cobrar` **o** `sales.anular` —son roles disjuntos, exigir los dos dejaba afuera a los dos— y al que solo cobra le pide la elevación por PIN, igual que para quitar una línea (RN-COM-020). **Pestaña de cuentas abiertas** en el PDV: estaba como nota al pie del mapa de mesas y filtraba fuera las de mesa, así que "¿qué falta cobrar?" no se podía responder de un vistazo. **El lienzo se cablea de verdad** (tercera enmienda de ADR-035): `conectar()`/`desconectar()` estaban escritos, probados y enchufados, pero todos los `<Handle>` llevaban `isConnectable={false}` y react-flow no deja ni empezar el arrastre — era código inalcanzable. Además: una opción nueva se crea con su receta **desde el lienzo** (antes había que recorrer dos pantallas antes de poder colgarla), el grupo se retira desde su nodo (`BorrarGrupo` existía sin estar montado en ninguna parte) y un `<button disabled>` dejaba de tragarse los clicks de "receta" y "quitar". **La cocina es una cadena de estaciones** (2026-08-13, ADR-044, RN-CUP-013, migración `b2e91f7c40aa`): el KDS ruteaba **solo por categoría**, así que la pizza aparecía a la vez en armado y en horno, cualquiera podía tacharla y tacharla la dejaba `listo` sin haber pasado por el horno; despacho, además, era el mismo componente con otro filtro y ofrecía tachar ítems en vez de decir qué falta. Ahora cada estación tiene un paso (`kds_pantalla.orden`) y cada línea sabe en cuál va (`venta_item.etapa_kds`); todo lo resuelve una sola función —`_estacion(cadena, producto, desde)`— que dice **qué muestra una pantalla** y **a dónde va al tacharla**, porque cola y avance que discrepen dejarían líneas invisibles en cocina. Busca la primera estación con `orden >= desde` y no la exacta: desactivar el horno a media noche hace que su carga caiga al eslabón siguiente en vez de desaparecer. Una bebida se salta el horno sola —el horno no atiende su categoría— sin configurar excepciones, y `estado_preparacion` no cambia. `orden` viaja en la réplica del hub (sin él, durante un corte todas las estaciones caerían al mismo eslabón); `etapa_kds` no, porque el push replaya la venta como un `POST /ventas` nuevo y el avance de cocina ya era local por diseño. **Despacho pasa a pantalla propia**: tarjeta por pedido con cuántas líneas van, en qué estación está cada una y por quién se espera; solo entrega. De paso, la cola volvió a llevar `tipo` y `consumo_motivo` — el `response_model` los filtraba en silencio y el aviso de consumo de personal que la pantalla tenía escrito no se mostró nunca. **Pinpad y bloqueo de pantalla del PDV** (2026-08-13, ADR-045, RN-POS-014, sin migración): los cuatro sitios que piden PIN usaban un `<input type="password">`, el navegador ofrecía guardarlo y con el PIN guardado en la caja el turno siguiente entra con la cuenta del anterior —toda la auditoría de RN-AUD-005 nombrando a la persona equivocada—; ahora se teclean en un teclado numérico **sin campo de formulario**, que es lo que no se puede guardar. Y la pantalla se bloquea a los 5 minutos sin cerrar sesión: la caja abierta y el pedido a medio armar siguen donde estaban, porque un bloqueo que hiciera perder el pedido se eludiría dejando la pantalla tocada a propósito. Se reabre con `POST /auth/verificar-pin` —nuevo: `login` rotaría la sesión y `autorizar` está para elevar a otro (RN-AUD-005)—, detrás del mismo rate limit y contra el **mismo lockout** que el login. El overlay es un `<dialog>` con `showModal()` porque nada con `z-index` tapa el top layer, y el plazo se mide con un latido contra una marca de tiempo porque una tablet con la pantalla apagada estrangula los temporizadores largos. Fuera del PDV no cambia nada. **El sabor dejó de contarse como un plato aparte** (2026-08-13, RN-CUP-014, enmienda de ADR-044, sin migración): una *Pizza Personal Peperoni* salía en la tarjeta del KDS como dos ítems y en despacho contaba «2 de 2» por una sola pizza. El extra es fila propia de la venta —receta, precio y rastro al anularse— pero `kds.py` no mencionaba `padre_venta_item_id` en ninguna parte y aplanaba. Ahora viaja anidado y se muestra tabulado bajo su plato como ya se mostraban las restas, la comanda impresa lo sangra, el ruteo por estaciones mira la categoría **del plato**, y marcar el plato marca sus extras: sin esa cascada `pedido_entregable` —que suma todos los ítems— habría dejado el pedido sin poder entregarse jamás. De paso cierra dos agujeros que solo se ven en la base real: un extra **sin categoría** no lo atendía ninguna estación filtrada, así que se quedaba `pendiente` para siempre (el caso de todos los extras del seeder); y **anular un plato con extras** reventaba contra Postgres —`fk_venta_item_padre` es `NO ACTION` y el PDV manda solo el id del padre— además de no reponer el insumo del sabor. El fixture de `test_pdv_slice` pasa a encender `PRAGMA foreign_keys=ON`: SQLite las trae apagadas y por eso toda la suite pasaba en verde sobre un FK que producción sí hace cumplir. Diferido: ver Deuda técnica. |
| Persona CRUD + lock optimista + matriz de aprobaciones + contrato público | ✅ 2026-07-25 | `POST/GET/PATCH /api/v1/personas` (sin Delete); `persona.version` con lock optimista (409 si desactualizada); `regla_aprobacion` (nuevo, `src/shared/`) reemplaza el umbral fijo de `purchases` por empresa, admin en `/api/v1/reglas-aprobacion`; primer contrato público de lectura cross-módulo (`sales.cliente` para marketing/comercial, `GET /api/v1/sales/clientes`). Migración `af8a246e2c25`. Ver detalle abajo. |
| Módulo `accounting` | 🔶 slice core+tesorería ✅ 2026-07-25 | Libro contable núcleo: plan de cuentas (`cuenta_contable`), periodo (`periodo_contable`, abrir/cerrar), asiento manual (`asiento`/`asiento_linea`, cuadre RN-CTB-001, anulación por asiento inverso RN-CTB-002) y mapeo configurable evento→cuentas (`regla_asiento`) que alimenta la generación automática para 4 eventos operativos ya publicados en código (`purchases.oc_emitida`, `purchases.compra_recibida`, `sales.venta_confirmada`, `purchases.comprobante_conforme`). **Pago a proveedor** (PROC-CTB-003, `movimiento_dinero`): cola idempotente por comprobante (RN-CTB-008) → ejecutar con umbral configurable + permiso (RN-CTB-005) → asiento automático. Migraciones `5402d99333fa`+`cbf904a9fc1b` aplicadas. Diferido: ver Deuda técnica. |
| Producción (fabricación) | 🔶 slice core ✅ 2026-07-25 | Orden de producción ad-hoc (crear → registrar consumo → completar con resultado de control de calidad) y costeo automático. Construido antes de tiempo a pedido del usuario — primera cocina real sigue planeada 2027. `receta.articulo_id` nuevo liga receta↔subreceta. Diferido: ver Deuda técnica. |
| Solicitudes / picking / transporte | 🔶 solicitudes y picking ✅ 2026-08-01 | **La fila estaba obsoleta** (verificado 2026-08-05): `requests` y `logistics` eran el plan de 2026-07-04 y el slice 4 de `inventory` (ADR-020) los dejó sin objeto. **Solicitudes** = `solicitud_insumos`/`solicitud_item` con su ciclo real (el local pide → el supervisor aprueba y reserva → el central despacha → el local recibe), más `reserva_stock`. **Picking** = el despacho reparte por FEFO y emite un `transferencia_item` por lote tomado. **Transferencias** sucursal↔sucursal con la misma entidad. Un módulo aparte habría necesitado el dominio de `inventory` (stock, lote, FEFO) para hacer exactamente eso, y CLAUDE.md prohíbe importarlo. La **guía de remisión** se cerró el 2026-08-05 (ADR-027) dentro de `inventory`, que era el argumento: es el comprobante del traslado, no un módulo. Queda sin dueño el transporte con ruteo/flota/liquidación propios, que hoy no existe como operación. |
| Módulo `rrhh` | ✅ ciclo laboral 2026-07-25 · contratación 2026-08-01 | Ciclo laboral completo: `trabajador` (con capa de aplicación que faltaba) + 12 entidades de §8b — `contrato_laboral` (borrador→firmado→finalizado), `postulante` (RN-PER-004), `socio`, `boleta_pago`/`liquidacion_bss` (idempotentes, RN-RRHH-001/003), `memorandum`/`amonestacion`/`acta`/`certificado_trabajo` (RN-RRHH-002/004/007), `solicitud_permiso` (RN-RRHH-005), `pacto_permanencia` (reembolso proporcional, RN-RRHH-006), `asistencia` (RN-RRHH-009, bloqueada para locación de servicios RN-PER-002). Migración `9e1b6a4c7d23`. **Slice contratación** (2026-08-01, migración `a7f2c81e4b95`): `convocatoria` como expediente de la búsqueda (borrador→publicada→cerrada) con RN-RRHH-013 aplicada en código —sin perfil de puesto no se publica—; formulario público de postulación por token (`POST /rrhh/postulaciones/{token}`, sin JWT, rate limit 20/h por IP, consentimiento obligatorio RN-PER-004, fecha puesta por el servidor) que se llena con **Google Forms + un Apps Script de 12 líneas**, no con un formulario propio ni la API de Google; `postulante` con datos propios y `respuestas` JSONB — **el candidato no entra a `persona` mientras es candidato**, `persona`+`trabajador` nacen al contratar (o se reusa la persona del recontratado, RN-GEN-007); y **un solo tablero** para los 13 pasos de incorporación (`recibido`→`preseleccionado`→`entrevistado`→`verificado`→`oferta_enviada`→`contratado`→`inducido`→`confirmado`, más `descartado`), avance de a una columna y descarte con motivo obligatorio porque el historial es la defensa ante un reclamo (Ley 26772). `postulante` gana `empresa_id` y cierra la excepción de tenant del mismo día. Permiso nuevo `rrhh.convocatoria_gestionar`. Tests: `tests/test_rrhh_convocatoria.py`. Diferido: ver Deuda técnica. |
| RRHH: procesos y plantillas (reclutamiento, contratación, inducción) | ✅ 2026-07-19 | `docs/rrhh/`, 13 SOPs, 9 plantillas — ver detalle abajo. |
| Compras: procesos y plantillas (proveedores, cotización, OC, recepción, pago, caja chica, activos) | ✅ 2026-07-19 | `docs/compras/`, 11 SOPs, 6 plantillas — ver detalle abajo. Módulo backend `purchases` actualizado conforme al flujo |
| Comercial: procesos y plantillas (precio/margen, promociones, mercado, metas, desempeño, capacitación) | ✅ 2026-07-19 | `docs/comercial/`, 9 SOPs, 5 plantillas — ver detalle abajo. Módulo backend `sales` ajustado (margen, vigencia de promoción) |
| Almacén-Logística: procesos y plantillas (conteo, vencimientos/merma, transporte/transferencias) | ✅ 2026-07-19 | `docs/almacen-logistica/`, 8 SOPs, 6 plantillas — ver detalle abajo. Módulo backend `inventory` ajustado (lote, merma, ajuste solicitar/aprobar) |
| Producción: procesos y plantillas (cronograma, calidad/no conformidad, inocuidad, inventario de cocina, soporte a I+D+i) | ✅ 2026-07-20 | `docs/produccion/`, 4 SOPs, 5 plantillas — ver detalle abajo. Spec a futuro: primera cocina de producción planeada 2027, hoy sin operación real. Módulo backend `production` — slice core implementado 2026-07-25 |
| Gerencia: gobierno + matriz de aprobaciones + presupuesto anual | ✅ 2026-07-22 | `docs/gerencia/`, política + perfil + 3 plantillas + 1 SOP (definición de presupuesto anual, PROC-GER-001) — ver detalle abajo. Área de autoridad/estrategia/control; sin módulo backend (RBAC + documentos) |
| Marketing: procesos y plantillas (marca/naming, contenido, campañas, material en sucursal, agencias) | ✅ 2026-07-22 | `docs/marketing/`, 6 SOPs, 4 plantillas — ver detalle abajo. PROC-MKT-001 registrado. Resuelve el pendiente "módulo marketing README/contrato propio" |
| Módulo `marketing` | 🔶 slices 1-2 ✅ 2026-08-08 | Primer código del módulo: `campana` con brief obligatorio (RN-MKT-003 — sin objetivo, público, presupuesto y KPI no se aprueba, y sin aprobación no sale a canal; quien redacta el brief no lo aprueba: `marketing.campana_aprobar` vive en `supervisor`, no en el rol `marketing`), `pieza_contenido` que solo se publica si es pertinente a la marca y su uso de marca está validado (RN-MKT-001/002), `lead` medido por conversión real y no por volumen, `implementacion_material_sucursal` (verificación en sitio, RN-MKT-005) y `encuesta_satisfaccion` (RN-COM-007), que la migración saca de §6 y le da dueño. La **atribución lead→venta** es automática solo cuando no hay ambigüedad —un único lead abierto del cliente en campaña en curso—; con dos o más queda manual, porque adivinar qué campaña convirtió falsea justo la métrica que la campaña existe para medir. Marketing lee el estado de entrega por el contrato público `sales::venta_para_encuesta`, nunca importando `Venta`. Migración `e9c3b7412a68`, 17 endpoints, 13 tests. **Slice 2** (2026-08-08, ADR-031/030, migración `c1f80b6a2d34`): la encuesta **sale de verdad** y deja de ser un formulario — el guion vive en `encuesta_plantilla`/`encuesta_pregunta` como un grafo de nodos donde cada respuesta elige la siguiente pregunta (un 2 de 5 pregunta qué falló, un 5 pregunta si nos recomendaría), y `encuesta_satisfaccion` recuerda en qué nodo está el cliente porque en WhatsApp no hay formulario, hay mensajes de a uno. Adaptador nuevo `src/shared/integrations/whatsapp/` (Cloud API de Meta), webhook público con firma HMAC, enlace público con token, y expiración automática por barrido horario. El primer mensaje del cliente **no** se cuenta como respuesta: solo abre la ventana de 24 h que Meta exige. Suma calendario de contenido con adjuntos (`GET /piezas/calendario`, arte colgado de `archivo`), evaluación agencia-vs-interna con criterios ponderados congelados antes de ver las propuestas y permisos separados para evaluar y decidir (RN-MKT-006), y `campana_metrica` — que convierte en consumidores reales a los eventos que el módulo publicaba al vacío. Diferido: ver Deuda técnica. |
| Contabilidad: procesos y plantillas | ✅ 2026-07-24 | `docs/contabilidad/` (política + marco legal + perfil contador/tesorero), 3 SOPs nuevos (pago a proveedor PROC-CTB-003, conciliación bancaria PROC-CTB-004, arqueo sorpresa PROC-CTB-005), 4 plantillas — ver detalle abajo. Área = tesorería + finanzas + registro + auditoría interna en un solo responsable, supervisada por Gerencia (RN-CTB-004..009; control en dos niveles: Contabilidad audita a las operativas, Gerencia audita a Contabilidad). Quedan propuestos PROC-CTB-006..013 |
| Mantenimiento, Sistemas/TI como áreas propias | ⬜ | Definidas como áreas del negocio (posible tercerización); documentación pendiente, desactivadas por ahora |
| Supervisión, CRM, tesorería, activos, proyectos, BI/reportes | 🔶 revisada 2026-08-05 | **Cuatro de los siete ya no son futuros y dos no van a ser módulos.** **BI/reportes** ✅ 2026-08-04: `src/core/reportes/` (ADR-024) con catálogo cerrado de 13 reportes, tableros guardados por usuario y compartidos por rol, filtros y exportación a CSV. **Desde 2026-08-08 hay una segunda mitad**, y son cosas distintas: `core/reportes` es la **consulta** (el usuario pide, se calcula) y el módulo `reports` (ADR-033) es la **emisión y distribución** (pasa un hecho, se genera, se guarda y se reparte). ADR-024 descartó un módulo porque el *motor de consulta* no tiene dominio propio; la distribución sí lo tiene —áreas, reglas, emisiones, entregas— así que paga sus siete registros de alta. **Tesorería** ✅ 2026-07-25: vive **dentro de `accounting`** por decisión explícita del usuario —pago a proveedor, `movimiento_dinero`, caja y custodia— y separarla al salir de REMYPE es un pendiente de organización, no de código. **Supervisión** no es módulo: es el rol RBAC `supervisor` más la matriz de aprobaciones de Gerencia (`parametro_empresa` + `decision_gerencial`); un módulo "supervisión" sería un permiso disfrazado de dominio. **CRM** parcial: `sales.cliente` (con contrato público de lectura) y `marketing.lead`/`campana`/`encuesta_satisfaccion` con atribución lead→venta ya cubren captar y medir; falta historial de interacciones y segmentación, sin caso hasta que haya campañas reales corriendo. **Activos** ⬜ pero **ya tiene dueño**: se compran en `purchases` (OC tipo `activo` + `requerimiento_activo`, deuda declarada) y se deprecian en `accounting` (activo fijo/depreciación, PROC-CTB-007/010) — partirlos en un tercer módulo cortaría el ciclo de compra en dos. **Proyectos** ⬜ sin caso: el grupo no ejecuta obra ni proyectos facturables hoy. |
| Integración de facturación electrónica (**Factiliza**) | 🔶 boleta/factura ✅ 2026-07-26 | **Reemplaza a Nubefact** (decisión del usuario). Adaptador en `src/shared/integrations/factiliza/`; cola Celery + servicio `worker`; migración `b3d7f21ac094`. Emite boleta/factura con IGV desglosado y exoneración de Amazonía (RN-IMP-001). Nota de crédito, PDF/XML/CDR ✅ 2026-08-04. **Guía de remisión ✅ 2026-08-05** (ADR-027) — construida en `inventory`, no en `sales`: declara un traslado entre almacenes, no una venta. |
| Integración Izipay | ⬜ | Proveedor decidido (ADR-003) |
| Integraciones Google / Meta | 🔶 Maps ✅ 2026-08-22 | **Google Maps — la dirección se ancla y el delivery se cobra por kilómetro** (ADR-053, ADR-054; migraciones `c3d8b1f47a95` y `d41f6a2c98b7`). Una dirección era `String(255)` en seis lugares y nada más: nadie validaba que existiera, nadie podía navegar hacia ella, y **la dirección de delivery que el cajero tecleaba se perdía** — vivía solo en el borrador del navegador y `venta` no tenía columna que la recibiera. Ahora `UbicacionMixin` suma `place_id` + lat/lng + plus code + distrito a `sucursal`, `almacen`, `empresa`, `persona`, `proveedor` y `venta`, con un campo único (`components/direccion/campo-direccion.tsx`) que autocompleta con Places y deja arrastrar el pin. **Editar el texto a mano suelta el ancla** en las dos puntas (`shared/ubicacion.py` manda; el frontend solo acompaña): un texto que diga una calle con las coordenadas de otra manda el reparto al lugar equivocado. El mapa lo dibuja el navegador con clave restringida por dominio —los tokens de sesión de Places son lo que abarata la factura y no tienen versión server-side—, y por eso la CSP suma hosts de Google por primera vez. **Lo que define plata NO sale del servidor**: la distancia de reparto la mide la Routes API con una segunda clave restringida por IP, con cuota por usuario e IP como la consulta de documento, y el costo se **congela** en la venta. Pasado el radio o en distrito vetado se sugiere **DAZ DAZ** sobre el campo `repartidor_externo_plataforma` que ya existía — cero tablas nuevas. Google caído cae a haversine×1,3 marcado «aprox.» y el pedido se toma igual; sin claves el ERP se comporta exactamente como antes (lo verifica `frontend/uso/direccion.spec.ts`, que corre **sin** clave a propósito). Paso a paso de la consola en [`docs/engineering/integraciones-google.md`](docs/engineering/integraciones-google.md). Tests: `tests/test_ubicaciones.py`, `tests/test_tarifa_delivery.py`. Diferido: cobrar el reparto como línea de venta (hoy se calcula, se guarda y se muestra), tarifa por sucursal, zonas por polígono. Meta sigue ⬜. |
| Agentes IA para pedidos | ⬜ | |
| Notificaciones | ✅ 2026-08-08 | **Resueltas como distribución, no como transporte** (ADR-033). El problema real no era el canal: era que de 52 eventos publicados solo 4 llegaban a alguien, cableados en `users/application/listeners.py`, y no había forma de ver ni cambiar quién recibía qué sin un deploy. El módulo `reports` lo vuelve administrable: catálogo cerrado de 13 emisiones, áreas, reglas por (empresa, emisión, sucursal) y una matriz que marca **huecos** (el hecho ocurre y no se entera nadie) y **fugas** (regla que no llega a nadie). El transporte sigue siendo la bandeja in-app existente; correo y WhatsApp son un slice aparte (el campo `canal` ya está en el modelo). Migración `9a1c4e7b2d30`. |
| Auditoría (audit_log) | ✅ 2026-08-08 | Transversal (ADR-031): `src/shared/auditoria.py` es el único escritor, `GET /api/v1/auditoria` (permiso `auditoria.leer`) el lector. Cinco módulos nuevos dejan rastro; `empresa_id` + índices en migración `b3d9f1c2a077`. Pendiente la purga por antigüedad (ver Deuda técnica → Protección de datos) |
| Endurecimiento de producción (rate limit, secretos, HTTPS, cabeceras) | 🔶 base ✅ 2026-07-26 | Rate limit por IP en login/refresh (Redis, fail-open), validación de config que aborta el arranque en `production` con valores de desarrollo, CORS + `TrustedHost` + cabeceras de seguridad + HSTS, `/docs` cerrado en producción, uvicorn `--proxy-headers`. Runbook de rotación de credenciales y custodia de `.env` en `docs/engineering/devops.md`. Pendiente: ver Deuda técnica → Seguridad. |
| App Android (15+) | ⬜ | **Decidido (ADR-013): PWA/responsive, no app nativa** — Next.js + Tailwind + Base UI es 100% web, sin base de código separada; debe hablar con el hub local de sucursal igual que web y PC, ver ADR-009 |
| Arquitectura frontend (Tailwind, shadcn/ui, shell estilo Odoo) | ✅ spec 2026-07-27 | ADR-013 (revisado): Tailwind sobre los tokens de marca existentes (`tailwind.config.ts` → `var(--color-*)`, sin hex mágico); **shadcn/ui** (componentes copiados y editables, corre sobre Base UI, no Radix) para overlays/combobox/dialog y catálogo base — token set semántico + `--radius` único, mejor ajuste para editar color/forma por marca rápido que construir a mano; home de apps + sidebar por módulo estilo Odoo; grid y rutas filtrados por `permisos` de `GET /users/me` (ya existente, sin cambio de backend), guard real server-side en cada `layout.tsx` de módulo — el filtro del grid es solo UX. Sin librería de estado global (YAGNI). Playwright para e2e de flujos críticos: **13 casos en verde y en CI desde 2026-08-06** (flujo del dinero, sesión, gate de módulo por permiso, lienzo de nodos y bloqueo de pantalla), ver Deuda técnica → Frontend. **2026-08-15 (ADR-047)**: se le suma una **suite de uso** aparte (`frontend/uso/`, `npm run test:uso`) para recorridos completos con captura en cada hito — el techo de tres casos de `e2e` sigue vigente porque `e2e` bloquea todo merge, y `uso` deliberadamente no lo hace. `docs/prompts/frontend.md` actualizado con las reglas técnicas. Sin implementación de código todavía. **2026-08-10 — el ERP ya corrige, no solo crea**: botón "Editar" en la fila de seis pantallas existentes y ocho rutas nuevas (Usuarios → Personas, Ventas → Clientes, Inventario → Categorías y Unidades de medida, y el módulo **Organización** con empresas/marcas/sucursales/almacenes). El backend ya tenía `PATCH` para casi todo: lo que faltaba era la pantalla. Molde único en `components/formulario/dialogo-formulario.tsx` (antes copiado en siete pantallas) que además arregla que **React 19 reseteaba el formulario al fallar la acción**, borrando lo tecleado. Personas lleva bloqueo optimista por `version` — con eso la rectificación de la Ley 29733 deja de ejercerse por `curl`. **2026-08-15 (ADR-048) — el proxy del navegador pasa bytes, no texto**: `app/api/proxy/[...ruta]/route.ts` leía todo cuerpo con `text()` y le fijaba `Content-Type: application/json` en las dos direcciones. Estaba escrito para un mundo de puro JSON y rompía en silencio lo primero que no lo fuera: la plantilla `.xlsx` del recetario se bajaba corrupta y con nombre `plantilla.json`, y toda subida `multipart` perdía su `boundary`. Ahora reenvía el `Content-Type` entrante, devuelve el cuerpo como stream y conserva `Content-Disposition`; se descartó la alternativa de rutas dedicadas por descarga (una copia por endpoint binario, y el proxy genérico seguiría roto para el resto). Lo fijan `frontend/lib/proxy.test.ts` (8 casos) y el recorrido de uso del importador. Ver Deuda técnica → Frontend. **2026-08-15 (ADR-050) — el login se teclea en el pinpad**: seguía pidiendo el PIN en un `<input type="password" autocomplete="current-password">`, o sea el patrón que ADR-045 había eliminado dos días antes dentro del PDV, en la pantalla que más veces se cruza y desde la misma tablet de la caja — sacarlo de los cuatro diálogos y dejarlo en la puerta no protegía nada. Ahora el usuario se teclea y el PIN se toca, **sin campo de formulario ni oculto**; el pinpad salió de `app/pdv/` a `components/pinpad/` (CSS a `globals.css`, con los tokens `--pdv-*` como preferencia y los del back office como respaldo, así una sola regla sirve a las dos paletas) y `app/pdv/pinpad.tsx` queda como re-export temporal para no chocar con la rama que trabaja `dialogos.tsx`. El login además **distingue las tres negativas** (401 / 423 con sus 15 minutos / 429 con su `Retry-After`), corta un PIN incompleto antes de gastar un intento del lockout, y deja de borrar el usuario tecleado al fallar. Deuda que deja: el puente del re-export y `app/cambiar-pin/`, el último PIN que se escribe en un campo. **2026-08-10 — el ERP ya corrige, no solo crea**: botón "Editar" en la fila de seis pantallas existentes y ocho rutas nuevas (Usuarios → Personas, Ventas → Clientes, Inventario → Categorías y Unidades de medida, y el módulo **Organización** con empresas/marcas/sucursales/almacenes). El backend ya tenía `PATCH` para casi todo: lo que faltaba era la pantalla. Molde único en `components/formulario/dialogo-formulario.tsx` (antes copiado en siete pantallas) que además arregla que **React 19 reseteaba el formulario al fallar la acción**, borrando lo tecleado. Personas lleva bloqueo optimista por `version` — con eso la rectificación de la Ley 29733 deja de ejercerse por `curl`. Ver Deuda técnica → Frontend. **2026-08-18 — los diálogos se centran y el PDV cabe en una tablet**: los diecisiete diálogos del ERP se abrían pegados a la esquina superior izquierda por dos causas encimadas —el preflight de Tailwind pisa con `margin: 0` el `margin: auto` con el que el navegador centra un `<dialog>` modal, y el `animation-fill-mode: both` de `.revelar` deja computado un `transform` identidad, que convierte al contenedor en bloque contenedor de todo `position: fixed`, top layer incluido—; se arregla con `dialog:modal { margin: auto; overflow: auto }` global y `backwards` en las animaciones de entrada. El PDV escondía el ticket entero (`display: none`) por debajo de 60rem, o sea en toda tablet en vertical y todo teléfono: pedido, totales, «Enviar» y «Cobrar» dejaban de existir. Ahora carta y ticket comparten celda y se alternan con un botón que solo aparece en ese ancho. Con eso van la barra del PDV que recortaba «Cuentas» y «Cobrados» a 390 px, el conteo por denominaciones que se desbordaba llevándose «Abrir caja», las barras superiores de PDV y KDS con la altura clavada, y la pantalla de bloqueo pintada con el blanco del navegador (deuda de ADR-050, cerrada). Lo fija `frontend/uso/responsive.spec.ts`, que recorre home, inventario, KDS con dos estaciones y PDV con caja abierta en 390×844, 820×1180 y 1440×900 afirmando dos cosas: que ningún control quede fuera de un contenedor que lo recorta y que todo modal quede centrado. |
| Modo offline del PDV — hub local de sucursal | ✅ fase 1 2026-07-26 · fase 2 2026-07-27 · fase 3 2026-08-07 | ADR-009: hub local dedicado por sucursal (misma imagen del backend, Postgres propio), los 3 clientes (web/Android/PC) le hablan siempre al hub por LAN. **Fase 1**: `DEPLOYMENT_MODE=hub` + validación de config, detector de conectividad, `GET /health/sync`, `docker-compose.hub.yml`. **Fase 2 — motor de sync**: ciclo que **empuja y después jala** (`src/core/sync/motor.py`, proceso `python -m src.core.sync.runner`); `id` client-generado en `crear_venta`/`registrar_pago`/`registrar_movimiento` (el cambio previo que pedía la fase 1, sin migración); endpoints dedicados `GET /sync/pull` + `POST /sync/push` (permisos `sync.leer`/`sync.empujar`, rol `hub_sucursal`) porque los públicos no alcanzaban (no traen `pin_hash` ni los campos del catálogo, no son incrementales, y el push necesita conservar quién vendió y el número de orden); contrato declarativo por módulo (`application/sincronizacion.py`, 35 recursos
tras sumar precios y lote/FEFO) que el motor solo ensambla; tabla `sync_watermark` por recurso y dirección; `/health/sync` con avance y último error por recurso; alta de la cuenta de servicio con `python -m src.seeders.hub`. El hub NO empuja movimientos de inventario (el listener de la nube los regenera; duplicaría el consumo). 33 casos en `tests/test_sync_motor.py` sincronizando dos bases reales. **Fase 3 (2026-08-07)**: el ciclo de abastecimiento offline — el local pide, ve lo que viene y recibe, y cuenta su almacén. El motor deja de estar cableado a `sales`: hay un registro `MODULOS_PUSH` y **cada módulo lleva su propio watermark**, así un conteo trabado no frena el dinero. La guía de remisión **no se emite offline** y eso es decisión tomada, no deuda (ADR-009). Pendiente: ver Deuda técnica. |
| Backups automáticos | ✅ 2026-07-26 | `python -m src.backups.backup`: dump `pg_dump --format=custom` → verificación del archivo (firma + tablas críticas) → restauración probada contra base desechable → copia a S3 (opcional) → purga con retención de 30 días que nunca borra la copia más reciente. **Diario** (antes se declaraba mensual e incremental). Cron del host, no Celery beat. Runbook en `docs/engineering/devops.md#backups`. Pendiente: alerta ante fallo, ver Deuda técnica. |
| Ciclo de caja completo | ✅ 2026-08-04 | ADR-025, migración `f3a1c62d90b4`. **No se cobra sin caja abierta** (contrato público `accounting.hay_caja_abierta`; el replay del hub es la única excepción); el monto de apertura y cierre **sale del conteo por denominación** (RN-POS-003/007) y la diferencia contra lo declarado se calcula sin bloquear la apertura (RN-POS-011); **cada relevo lo firma quien recibe con su PIN** (RN-MDP-002, permiso `accounting.caja_relevar`) y `custodia_efectivo` es máquina de estados real hasta `disponible`; **un cierre con faltante se reabre y se recuenta** dejando motivo y autorizador en `cierre_caja.correcciones` (RN-MDP-005), solo mientras el efectivo siga en el local. Nueva entidad `pos_tarjeta` (serie + código de comercio, RN-POS-010; emergencia = `sucursal_id` NULL, RN-POS-009) verificada al abrir. `tests/test_caja_ciclo.py` (17 casos). **Pantallas (2026-08-05)**: los diálogos del PDV se pusieron al día con este contrato —hablaban el anterior y devolvían 422 desde el día que se implementó— y contabilidad gana `/contabilidad/caja` con turnos cerrados, cadena de custodia firmada con PIN, reapertura e inventario de POS (`GET /accounting/cajas/turnos`). En el camino se cerró un agujero de integridad: `custodia` y `descuadre_atribucion` son enums y el schema los aceptaba como texto libre, dejando la fila ilegible al leerla. 24 casos. **Enmendado el 2026-08-15 (ADR-049, RN-MDP-008, migración `c8b41f60d2a7`)**: la firma con PIN salió de la apertura y del cierre —**el cajero opera su turno solo**, le basta `accounting.caja_operar`— y quedó donde la plata cambia de manos. Al cerrar, el efectivo nace `en_caja` a nombre del cajero y el encargado firma la recepción después (`en_caja → en_supervisor`), un estado que existía en el enum desde el primer día y que el sistema no escribía nunca. El motivo es de operación, no de modelo: exigir que un encargado viniera a firmar cada apertura se pagaba dejando su sesión abierta en la caja todo el turno, que es lo contrario de lo que la firma buscaba probar. `relevo_encargado_id` queda NULLABLE y `encargado_de_turno` se apaga en la práctica (ver Deuda técnica → Dashboard y caja). Recorrido de uso nuevo: `frontend/uso/caja-custodia.spec.ts`. |
| Dashboard gerencial mínimo | ✅ 2026-07-26 | `GET /api/v1/dashboard/resumen` (`src/core/dashboard_router.py`, permiso `dashboard.leer`): ventas del día (cantidad+total), stock bajo mínimo, cajas abiertas — agregador en `core`, nunca importa dominio de otro módulo (ADR-012). Requirió construir dos huecos que no existían: `sales` no tenía ningún listado de ventas, `accounting` tenía los modelos de caja (`apertura_caja`/`cierre_caja`/`arqueo`, migrados desde 2026-07-20) sin capa de aplicación. **Slice mínimo de caja** (`accounting.application.caja`): abrir/cerrar/arquear con **reconciliación real** (el cierre calcula `monto_esperado` desde los pagos en efectivo reales, vía contrato público de `sales`, no un número tipeado sin verificar). Primer frontend real: login por PIN + pantalla de dashboard en Next.js. Fuera de esta fase, a propósito: RN-POS-009..013 completas, relevo autenticado por PIN, máquina de estados de `custodia_efectivo` — ver Deuda técnica. |
| Protección de datos personales (Ley 29733) | 🔶 ARCO técnico ✅ 2026-07-26 | `docs/security/proteccion-datos-personales.md`: qué datos trata el ERP y dónde viven (casi todo en `persona`, fuente única — RN-GEN-007; la excepción deliberada es `postulante`, ver 2026-08-01), derechos ARCO, plazos de conservación, medidas de seguridad ya vigentes (referenciadas, no reconstruidas), proceso de brecha. Cancelación implementada como **anonimización irreversible** de `persona`, no `DELETE` — `POST /api/v1/personas/{id}/anonimizar`, permiso dedicado `personas.anonimizar`, migración `dad43729501d` (RN-PER-007, ADR-011). Acceso/Rectificación ya existían (`GET`/`PATCH /personas/{id}`). Pendiente de **acción del usuario, no de código**: registro del banco de datos ante la ANPD, aviso de privacidad público, confirmar plazos de retención con el contador/abogado, jurisdicción de transferencia internacional. Pendiente técnico: ver Deuda técnica. |
| Contrato OpenAPI de la API | ✅ 2026-07-26 | `docs/architecture/openapi.json` exportado (`python -m src.core.openapi_export`) y verificado en CI — un endpoint que cambia sin regenerar el contrato falla el PR (ADR-010). `TAGS_METADATA` en `src/core/app.py` describe los 15 tags de la API; un tag nuevo sin descripción falla un test. De paso, corregidas dos afirmaciones falsas en `api-guidelines.md`: `idempotency_key` es campo del body, no header; las colecciones devuelven array plano, no `{items,total,page,page_size}` (nunca se implementó paginación). |
| CI/CD | 🔶 CI + entrega ✅ 2026-07-26 · e2e en CI 2026-08-06 | **Job `e2e`** (2026-08-06): el flujo del dinero de punta a punta sobre chromium, con `test-results/` como artefacto cuando falla — el único job que comprueba que cliente y servidor estén de acuerdo. `ci.yml` gana tres verificaciones que no existían: cabeza única de Alembic (una doble falla en el despliegue, no en el merge que la crea), construcción de la imagen **y arranque real del contenedor** contra `/health`, y `pip-audit` informativo. `release.yml` publica la imagen en GHCR en cada push a `main` (tags `v*` → versión exacta). `docker-compose.prod.yml` nuevo: el compose existente es solo desarrollo y desplegarlo publicaría esa configuración. Dockerfile con usuario sin privilegios y `HEALTHCHECK`. El **despliegue sigue manual** y documentado hasta que exista el VPS (ADR-008). **Job `uso`** (2026-08-15, ADR-047): recorridos completos con captura, artefacto **siempre** (no solo al fallar). Queda **fuera de los seis checks requeridos** por el ruleset y con `continue-on-error` — un recorrido lento no puede bloquear un arreglo de caja; agregarlo al ruleset sería cambiar esa decisión, no corregir un olvido. **Arnés de paralelo** (2026-08-15): `E2E_PUERTO_WEB` (el par de `E2E_PUERTO_API`, que existía solo) y resolución automática del `.venv` desde un worktree, para que dos agentes puedan correr Playwright a la vez — esquema de slots en `docs/engineering/trabajo-en-paralelo.md`. |
| Paquete de demo portable | ✅ 2026-08-09 | `python scripts/empaquetar_demo.py` → `ZIP_<versión>/provecho-demo-<versión>.zip`: el ERP entero en la PC de quien prueba, sin internet ni servidor, con doble clic en `INICIAR.bat` (`admin` / PIN `123456`). Nace de que no hay VPS todavía y esperar a tenerlo era esperar para poner el sistema frente a la gente que lo va a usar. `docker-compose.demo.yml` **no publica nada en internet** —secretos versionados a propósito— y no tiene `build:` porque en esa PC no hay código fuente; su servicio `init` migra y siembra en cada arranque, que es lo que convierte cuatro comandos de consola en un solo `up`. Trajo dos cosas que faltaban por su cuenta: la **imagen de producción del frontend** (etapa `runner` con `output: "standalone"`, ~250 MB contra ~1.5 GB del `npm run dev` que era la única que existía) y `COOKIE_SECURE`, sin el cual la sesión moría en silencio al entrar desde la tablet del local por http. Vigilado por `tests/test_repo_coherencia.py` (imágenes del compose == imágenes que el ZIP exporta, y el Node de la imagen == el del CI). De paso destapó que la **versión declarada llevaba tres releases congelada**: `cortar_version.py` cortaba el CHANGELOG pero nunca tocaba `pyproject.toml` ni `frontend/package.json`, que seguían en `0.1.0` con el repo en `v0.4.0` — la versión vivía solo en el tag de git. Ahora el script las escribe y un test las vigila; el ZIP además lleva `VERSION.txt` con el commit exacto. Límites conocidos: un solo usuario, reset manual, y Docker Desktop como requisito duro. Ver `docs/engineering/devops.md#paquete-de-demo-portable`. |
| Chequeos de salud y alertas | ✅ 2026-07-26 | `src/core/health.py` + `health_router.py`: `/health` (liveness, sin dependencias), `/health/ready` (base de datos crítica → 503; Redis y cola degradan sin sacar de rotación) y `/health/backups` (503 pasadas 26 h — cubre el backup que nunca corrió, que no genera evento de error). El ERP expone estado; **un monitor externo alerta** (ADR-007): construir alertas dentro del servidor que se monitorea deja de avisar justo cuando ese servidor cae. Pendiente: contratar el monitor y dar de alta las sondas. |
| Observabilidad (métricas, trazas, logs centralizados) | 🔶 logs + errores ✅ 2026-07-26 | `src/core/logging_config.py`: JSON en producción, tres flujos (`app`/`seguridad`/`auditoria`) derivados del nombre del logger, `request_id` por request (respeta `X-Request-ID` entrante, sale en la cabecera y en el cuerpo del error 500), redacción de PIN/tokens/`Authorization`. `src/core/sentry.py`: reporte de errores en `api`, `worker` (señal `celeryd_init`) y `backups`; sirve para Sentry o GlitchTip autoalojado, no-op sin DSN. Pendiente: métricas, trazas y colector de logs — ver Deuda técnica. |
| UX: menús, buscadores, breadcrumbs, atajos, sidebars, dashboards | 🔶 2026-08-12 | **Paleta de comandos** (`Ctrl+K`, `components/shell/paleta-comandos.tsx`) sobre Base UI Autocomplete — sin `cmdk`: motor de fuzzy search para ~50 entradas estáticas y arrastra Radix, que ADR-013 descartó. Los destinos salen de `lib/navegacion.ts`, se arman en servidor y llegan filtrados por permiso; cada resultado es un `<Link>` real (Enter, clic central y «abrir en pestaña nueva» funcionan solos). Sidebar con ítem activo y submenú registrado en un solo archivo. Atajo `/` para el buscador de la tabla. Pendiente: breadcrumb por ruta recorrida, atajos por acción dentro de una pantalla, dashboards configurables |
| UX: breadcrumb por ruta de usuario (no jerárquico) + tooltip de ayuda por campo de formulario | ✅ spec 2026-07-26 | `docs/product/ui-ux.md` — breadcrumb crece con la navegación (patrón Odoo), navegación jerárquica va por menús desplegables; todo campo de formulario lleva hover explicando término/formato. Solo especificado |
| UX: buscador contextual (nombre/insumo/exclusión, ranking por probabilidad) + dialog de venta sugerida (upsell) en carrito | ✅ spec 2026-07-26 | `docs/product/ui-ux.md` — buscador cruza `receta_item` para insumo/exclusión, lista ordenada por relevancia si no hay match único; al ir al carrito se sugieren productos de adición rápida, descartable. Solo especificado |
| Branding (paleta, tipografías, tokens CSS) | ✅ 2026-07-04 | Brandboard aplicado — `docs/product/ui-ux.md` |
| Skins multi-marca (PDV/Kiosk por marca vs **Provecho** en el resto — Majambo no tiene tema propio, decidido 2026-07-27), accesibilidad (2 paletas + 4 niveles de tamaño de fuente, catálogo definido 2026-07-27) y plataformas por módulo (táctil Android en PDV/Kiosk/KDS/Inventario, PC-first en el resto) | 🔶 accesibilidad ✅ 2026-08-12 | **Accesibilidad implementada (ADR-037)**: paleta de alto contraste (Okabe-Ito, cubre el par rojo-verde), escala de letra en cuatro niveles y modo oscuro, las tres en el perfil del usuario y no en el dispositivo — en un local la misma tablet la usan tres turnos. Se resuelven en el servidor (`class="dark"`, `data-escala`, `data-paleta` en `<html>`): `next-themes` exigiría un script inline que la CSP con nonce tendría que autorizar. Paleta y tema se combinan. `Insignia` ata el ícono al tono, que es lo que hace cumplible «ningún estado solo por color». Pendiente: resolver de tema por marca para PDV/Kiosk |
| F2 — Arquitectura de frontend (documento maestro) | ✅ spec 2026-07-27 | `docs/product/frontend-architecture.md` — 31 secciones (tokens, componentes base/especializados, layout, navegación, estado, tablas, formularios, tiempo real, permisos visuales por rol, etc.) con estado por sección y los 6 puntos a cerrar antes de los diseños finales del alfa (layout general, componentes base, tablas, permisos visuales, arquitectura de carpetas, decisión de estado). Solo especificado — ver detalle en Deuda técnica → Frontend |

## Catálogo modelo Odoo (0.7.0, en curso desde 2026-08-23)

Rama `feat/catalogo-odoo`, sobre v0.6.0. El catálogo pasa al modelo de
atributos y variantes de Odoo 18 porque el actual no soporta el carta real de
Charlie's: una `Pizza MitadxMitad Familiar` de 19 sabores por mitad son 361
productos con 361 recetas.

| Fase | Qué | Estado |
|---|---|---|
| F1 | Modelo, migración aditiva `e2b7c40d91af`, reglas puras | ✅ 2026-08-23 |
| F2 | Explosión de receta condicionada, venta, eventos, sync | ✅ 2026-08-23 |
| F3 | Conversor y cargador del catálogo de Odoo (`scripts/odoo/`) | ✅ 2026-08-23 |
| F4 | Matriz de recetas (ADR-057) | ✅ 2026-08-23 |
| F5 | Lienzo sobre el modelo de atributos (ADR-058) | ✅ 2026-08-23 |
| F6 | Seeder desde los `.xlsx` reales, corte 0.7.0 | ⏳ |

**Vuelta atrás**: la migración es solo aditiva, así que la imagen 0.6.0 corre
contra este esquema sin enterarse. Volver a operar es
`./scripts/desplegar.sh 0.6.0`; el `alembic downgrade` solo hace falta si
además se quiere el esquema idéntico, y borra lo cargado con el modelo nuevo.

## Pendientes de decisión (registro vivo)

Marcar aquí cuando cada uno se resuelva (y actualizar el doc que lo
contiene, buscando su `[[ COMPLETAR ]]`):

- ✅ 2026-07-27 **Mecanismo para los valores operativos configurables**
  (umbral de OC, margen de contribución mínimo,
  margen de error de ajuste, monto de caja chica, plazo de envío de
  comprobantes, rangos salariales): decidido con el usuario que **no son
  valores fijos** — se configuran en `parametro_empresa` por empresa, los
  gestiona Gerencia, y un cambio puede sustentarse en un acta
  (`decision_gerencial`) cuando amerite (no obligatorio para un ajuste
  rutinario). Ver ADR-014, `data-model.md` §8c, RN-GER-008 y
  `docs/gerencia/politica-gerencia.md#parámetros-operativos-configurables`.
  **Ampliado 2026-08-02** (ADR-014 Addendum, RN-GER-009): cada parámetro
  se configura **desde el módulo al que pertenece**, pero el cambio **no
  surte efecto hasta que Gerencia lo aprueba** en su sección de
  aprobaciones (aceptar / rechazar / modificar). Implementado: entidad,
  migración `a71c9f4b2e60`, endpoints `/api/v1/parametros[/{id}/aprobar|
  /rechazar]`, un permiso por módulo `<modulo>.proponer_parametro`.
  Lo que queda abierto por cada uno de los puntos de abajo ya **no es el
  mecanismo** (resuelto e implementado) sino que **el área proponga y
  Gerencia apruebe el valor real** — trabajo de configuración/negocio, no
  bloquea código:
  **Propuestos 2026-08-05** con su sustento en
  `docs/gerencia/propuesta-parametros-operativos.md` y cargados como
  `estado='propuesto'` (`python -m src.seeders.parametros`, idempotente):
  13 filas esperando en `/gerencia/parametros`. Cada propuesta declara de
  dónde sale el número, **qué pasa si está mal** y cuándo revisarlo — un
  parámetro mal puesto no rompe nada, distorsiona una decisión diaria
  durante meses sin que nadie lo note.
  - 🔶 `purchases/oc_umbral` — propuesto S/ 2,000 (confirma el semilla).
    **El de menor base**: no hay histórico de OC contra el cual calibrarlo.
    Sigue abierto si hace falta un umbral separado para activos.
  - 🔶 `sales/margen_minimo` — propuesto 60 %, desde food cost 32 % +
    empaque 3 % + comisión 4 %, y alcanzable porque Amazonía exonera el IGV.
  - 🔶 `sales/incentivo_meta_pct` — propuesto bono **grupal por sucursal**,
    3 % del excedente sobre la meta, techo 0.5 RMV. Sigue necesitando la
    aprobación conjunta de Comercial + RRHH + Gerencia (política §3).
  - 🔶 `inventory/margen_error_ajuste` — propuesto 2 % **más piso de
    S/ 20**: el porcentaje solo castiga a las categorías baratas y vuelve
    ruido la alerta. El piso **exige código**, ver deuda de inventory.
  - 🔶 `purchases/monto_caja_chica` — propuesto S/ 500 con reposición al
    bajar de S/ 150.
  - 🔶 `accounting/plazo_envio_comprobante` — propuesto 5 días hábiles
    desde el cierre. Es plazo **interno**: el vencimiento real de SUNAT
    depende del último dígito del RUC.
  - 🔶 `rrhh/rango_salarial_<perfil>` × 7 — propuestos como **múltiplo de
    RMV** (1.00–2.80 según perfil), no en soles. Dos cosas antes de
    aprobar: **confirmar la RMV vigente** (el marco legal la registra en
    S/ 1,130 con nota de verificar) y contrastar contra avisos reales de
    Tarapoto — la propuesta tiene la estructura de responsabilidad, no el
    mercado local.
  Quedan **fuera** de este mecanismo por ser decisión de rol, no de valor
  (resueltas 2026-08-05 con el usuario):
  - ✅ 2026-08-05 **El suplente de OC es otro administrador**, no el
    encargado de turno: una OC sobre el umbral es una decisión de plata.
    Consecuencia en código: se **retiró** `purchases.aprobar` del rol
    `supervisor`, que lo tenía desde el slice inicial y contradecía esta
    decisión. Revocado también en la BD dev — el seeder solo agrega.
  - ✅ 2026-08-05 **Los ajustes de inventario los aprueba el supervisor**
    de turno: está en el local, ve el faltante y decide en el momento. Ya
    tenía `inventory.aprobar_ajuste`; queda confirmado y comentado. El
    "supervisor de logística" como rol aparte se descarta: sería un rol
    nuevo para una sola capacidad que el supervisor ya ejerce. La
    segregación que importa —quien solicita no aprueba— vive en el dominio,
    no en el rol.
- ✅ 2026-07-20 `reporte_escalamiento`: definido con el usuario — cadena
  atención al cliente → supervisor (redacta solución) → comercial/gerencia
  (acciones reportadas); se almacena para mejora continua
  (`data-model.md` §6). **Implementado el 2026-08-09** (ADR-036) en
  `src/modules/reports/`, no en `shared`: ancla al `reporte_emitido` y no a la
  venta, y el escalón se resuelve con áreas + encargado de turno porque el ERP
  no tiene jerarquía organizacional.
- ✅ 2026-07-27 Cumplimiento de pedido: **UN** proceso — `PROC-OPE-002`
  (área Operaciones), con Preparación y Despacho/Entrega como etapas
  internas, no dos procesos. Razones: un solo resultado (entra Orden de
  Pedido, sale pedido entregado) sin artefacto de traspaso; la máquina de
  estados ya implementada (`venta_item.estado_preparacion`) es una sola y
  las pantallas KDS `preparacion`/`despacho` son vistas de ella; "Producción"
  ya nombra la cocina de producción central (`PROC-PRD-001`, 2027) y
  reusarlo rompía la nomenclatura. Desbloquea `sales.venta_entregada` y
  `marketing.encuesta_enviada`; se separa como v2.0 si el reparto llega a
  tener ruteo/flota/liquidación propios.
- ✅ 2026-07-22 Módulo `marketing`: README/contrato propio —
  `src/modules/marketing/README.md` + área documentada en `docs/marketing/`.
- ✅ 2026-07-24 Área Contabilidad documentada — `docs/contabilidad/`
  (tesorería + finanzas + registro en un responsable, supervisada por
  Gerencia); resuelve el pendiente "Contabilidad: procesos y plantillas" y
  confirma CAJ/TES/ACT bajo Contabilidad. Incluye auditoría interna en dos
  niveles (RN-CTB-009): Contabilidad audita a Compras/Almacén/cajas de
  sucursal; Gerencia audita a Contabilidad. Propuestos PROC-CTB-006..013.
  Pendientes de este mismo pendiente: separar tesorería/registro al salir de
  REMYPE, y llevar entidades contables (asiento, plan de cuentas, activo
  fijo, conciliación) a `data-model.md` en su slice.
- ⬜ Tratamiento de contratos vigentes al salir de REMYPE (~jul 2027).
- ✅ 2026-08-05 Entidades de **Comercial-estrategia** y **RRHH-proceso**
  llevadas a `data-model.md`. `convocatoria` y `postulante` ya estaban
  desde el slice de contratación (2026-08-01) — la entrada las seguía
  listando como pendientes. Especificadas ahora, sin implementar:
  `meta_venta` + `meta_venta_seguimiento` y `hallazgo_mercado` en §6;
  `entrevista`, `plan_induccion` + `plan_induccion_item`,
  `evaluacion_periodo_prueba`, `evaluacion_desempeno` y `capacitacion` +
  `capacitacion_asistente` en §8b.
  Tres decisiones que valen más que las tablas: (a) **la escala 1-4 es la
  misma en toda la organización** —entrevista, periodo de prueba, desempeño
  comercial— para poder comparar a una persona consigo misma a lo largo del
  tiempo, y los criterios van en JSONB porque cada puesto pregunta lo suyo;
  (b) **evaluación de desempeño y capacitación viven en `rrhh` aunque las
  ejecute Comercial**: su artefacto termina en el file personal y `sales`
  no puede ser dueño de datos de `trabajador` — Comercial produce, RRHH
  custodia, y `evaluador_id` deja visible que el evaluador fue de otra
  área; (c) **el seguimiento de la meta es tabla, no columna**: guardar
  solo el cumplimiento final convierte la meta en un número que se mira
  cuando ya no hay nada que hacer, que es justo lo que el SOP quiere
  evitar. Falta el slice que las implemente.
- ✅ 2026-08-05 BPMN de las cuatro áreas nuevas, con sus PROC registrados
  en el maestro y su narrativa en `workflows.md` (el enfoque era *primero
  SOP, luego BPMN*, y los SOPs ya estaban estables):
  **PROC-RRH-001** Incorporación de personal ·
  **PROC-CMP-001 v2.0** Compras (los tres caminos: informal con caja chica,
  preferente sin cotización, estándar/activo con RFQ) ·
  **PROC-COM-003** Definición y revisión de precio ·
  **PROC-INV-001 v0.2** Abastecimiento de locales, que además pasa de
  Borrador a **Vigente**: el ciclo está implementado (ADR-020) y el traslado
  ya emite guía (ADR-027).
- ✅ 2026-08-05 BPMN de las dos contingencias:
  **PROC-RRH-002** personal faltante en la apertura (RN-RRHH-011 — el local
  **abre igual**, el pago extra del reemplazo se le descuenta al faltante
  salvo constancia médica) y **PROC-RRH-003** tardanza o falta del encargado
  (RN-RRHH-010 — hasta 30 min es memorándum y *no es sanción*, más de 30 min
  o falta es amonestación). Ninguna de las dos tiene soporte en código
  todavía: son proceso, no pantalla.
- ✅ 2026-07-27 Catálogo de paletas de accesibilidad y niveles de tamaño de
  fuente — propuesta técnica definida (dos paletas: Provecho estándar y
  un modo alto contraste/daltonismo inspirado en Okabe-Ito que cubre
  protanopía+deuteranopía; 4 niveles de tamaño de fuente vía
  `--font-scale`). `docs/product/ui-ux.md#catálogo-de-paletas-y-tamaños-de-fuente-propuesta-técnica-2026-07-27`.
  Sujeta a ajuste si aparece validación real con usuarios daltónicos/baja
  visión. Sin implementar todavía.
- ✅ 2026-07-27 Grupo Majambo **no tiene tema propio** — Provecho es el
  único tema fuera de PDV/Kiosk (`docs/product/ui-ux.md`).
- ✅ 2026-08-23 **Droplet de staging levantado** (DigitalOcean, ver
  [`docs/engineering/staging.md`](docs/engineering/staging.md) para IP,
  dominios y bitácora — nunca secretos ahí). Usuario `app` sin root/password
  por SSH, firewall, Docker, DNS de `staging.majambo.com.pe` y
  `api-staging.majambo.com.pe` ya resueltos. Escrito en el repo:
  `docker-compose.staging.yml`, `Caddyfile` (TLS automático, elegido sobre
  nginx+certbot para no mantener renovación a mano), `.env.staging.example`,
  `scripts/desplegar.sh` y `release.yml` publicando también la imagen del
  frontend (`ghcr.io/rrojasda94/provecho-erp-web`) — antes solo publicaba el
  backend, staging no habría tenido pantallas.
- ⬜ **Falta para terminar el primer despliegue de staging:**
  1. `.env` real en el servidor (`JWT_SECRET`/`POSTGRES_PASSWORD` generados
     ahí, nunca en una conversación — un secreto que la pasó deja de serlo).
  2. `docker login ghcr.io` con el token de lectura ya generado.
  3. Primer `docker compose -f docker-compose.staging.yml up -d` y
     verificación de `/health/ready`.
  4. Cron de backup diario (`python -m src.backups.backup`) y purga semanal
     de postulantes (`python -m src.modules.rrhh.purga`) dados de alta en
     el droplet.
  5. Monitor externo (healthchecks.io/UptimeRobot) contra `/health`,
     `/health/ready`, `/health/backups` — es lo único que no se puede
     resolver dentro del VPS (ADR-007).
- ⬜ **Producción sigue parqueada** (decisión 2026-08-05): dominio real,
  decidir dónde vive la copia on-premise de los backups, y stack de
  observabilidad (`docker-compose.observabilidad.yml`) — todo eso se retoma
  cuando exista la máquina de producción, staging no la reemplaza.

## Deuda técnica pendiente (backlog)

Registro vivo de deuda técnica declarada al cerrar cada slice — para que no
se olvide. Marcar ✅ al resolverse en el slice indicado.

Vive en [`docs/roadmap/deuda/`](docs/roadmap/deuda/), **un archivo por área**.
Estaba todo acá —2.000 líneas en una sola sección— y era donde caían casi
todos los conflictos de merge: dos ramas de módulos distintos chocaban por
compartir archivo, no por contradecirse. Las referencias en prosa del tipo
«ver ROADMAP → Deuda técnica → Frontend» siguen valiendo: el área es el
nombre del archivo.

| Área | Archivo | ⬜ abiertos | ✅ cerrados |
| --- | --- | --- | --- |
| Transversal | [`transversal.md`](docs/roadmap/deuda/transversal.md) | 5 | 22 |
| Seguridad (tras el endurecimiento base de 2026-07-26) | [`seguridad.md`](docs/roadmap/deuda/seguridad.md) | 8 | 3 |
| Dashboard y caja (tras la implementación de 2026-07-26 — ADR-012) | [`dashboard-y-caja.md`](docs/roadmap/deuda/dashboard-y-caja.md) | 6 | 17 |
| Protección de datos personales (tras la implementación de 2026-07-26 — ADR-011) | [`proteccion-de-datos-personales.md`](docs/roadmap/deuda/proteccion-de-datos-personales.md) | 8 | 1 |
| Contrato de API (tras la implementación de 2026-07-26 — ADR-010) | [`contrato-de-api.md`](docs/roadmap/deuda/contrato-de-api.md) | 6 | 1 |
| Modo offline del PDV (tras la fase 2 de 2026-07-27 — ADR-009) | [`modo-offline-del-pdv.md`](docs/roadmap/deuda/modo-offline-del-pdv.md) | 10 | 3 |
| CI/CD (tras la implementación de 2026-07-26) | [`ci-cd.md`](docs/roadmap/deuda/ci-cd.md) | 7 | 4 |
| Observabilidad y salud (tras las implementaciones de 2026-07-26) | [`observabilidad-y-salud.md`](docs/roadmap/deuda/observabilidad-y-salud.md) | 3 | 6 |
| Backups (tras la implementación de 2026-07-26) | [`backups.md`](docs/roadmap/deuda/backups.md) | 4 | 1 |
| Módulo inventory (slices siguientes) | [`modulo-inventory.md`](docs/roadmap/deuda/modulo-inventory.md) | 4 | 32 |
| Módulo sales (slices siguientes) | [`modulo-sales.md`](docs/roadmap/deuda/modulo-sales.md) | 44 | 26 |
| Módulo purchases (slices siguientes) | [`modulo-purchases.md`](docs/roadmap/deuda/modulo-purchases.md) | 6 | 2 |
| Módulo production (slices siguientes) | [`modulo-production.md`](docs/roadmap/deuda/modulo-production.md) | 8 | 1 |
| Módulo accounting (slices siguientes) | [`modulo-accounting.md`](docs/roadmap/deuda/modulo-accounting.md) | 8 | 3 |
| Módulo rrhh (slice completo — deuda declarada) | [`modulo-rrhh.md`](docs/roadmap/deuda/modulo-rrhh.md) | 9 | 4 |
| Módulo marketing (slice core — deuda declarada) | [`modulo-marketing.md`](docs/roadmap/deuda/modulo-marketing.md) | 5 | 2 |
| Frontend (F2 — arquitectura y UX, documento 2026-07-27, actualizado tras ADR-013) | [`frontend.md`](docs/roadmap/deuda/frontend.md) | 11 | 24 |

## Orden sugerido de desarrollo

**Decisión del usuario (2026-07-14: "modelar toda la BD antes de
procesos") queda revertida (2026-07-14, sesión posterior).** Nuevo
enfoque: **slices verticales por proceso de negocio**, no fases
horizontales para todo el negocio. Un proceso a la vez (ej. "Compra de
insumos") atraviesa junto: procesos → reglas → casos de uso → eventos →
modelo de datos de ese proceso — antes de pasar al siguiente proceso.
Motivo: reglas (`business-rules.md`, 713 líneas) y modelo de datos
(`data-model.md`, 500 líneas) ya avanzaron adelantados y por separado del
resto — señal de que las fases se solapan naturalmente; evita también
rehacer entidades/reglas si aparece un caso raro tarde en un proceso ya
"cerrado" en otra fase.

El detalle de entidades ya relevado en la sesión de modelado de BD
(abajo) sigue siendo insumo válido — se incorpora al slice del proceso
correspondiente en vez de migrarse todo de una sola vez.

### Slice vertical en curso: Venta — PROC-COM-001 (2026-07-14/15)

**Nomenclatura de procesos** (2026-07-15, `docs/domain/process-nomenclature.md`):
código de área es el área real de la empresa, no el módulo del ERP —
Venta pertenece a Comercial (`COM`), no a un área "Ventas" (`VNT`).
Renombrado en todo lo ya escrito: `RN-VNT-*`→`RN-COM-*`, `CU-VNT-*`→
`CU-COM-*`, proceso registrado como `PROC-COM-001` (v1.0, Vigente) en el
[registro maestro](docs/domain/process-nomenclature.md#registro-maestro).
El módulo de código sigue llamándose `sales` y los eventos siguen
`sales.venta_*` — el código de área NO reemplaza el nombre del módulo
técnico, son cosas distintas.

Primer proceso elegido para atravesar completo. Avance de esta sesión:

- **Mapa visual end-to-end** (FigJam, todos los procesos conectados,
  incluye Venta) — ver enlace en la conversación; ya tenía "Producción en
  sucursal" y "Marketing" como secciones separadas de "Comercial / Venta"
  — coincide con el recorte de alcance de abajo, no hizo falta tocarlo.
- **Procesos**: `docs/domain/workflows.md`.
- **Reglas**: `docs/domain/business-rules.md`.
- **Casos de uso** (F4, doc nuevo): `docs/domain/use-cases.md` —
  CU-COM-001 (mesa), CU-COM-002 (takeout/delivery).
- **Eventos**: `docs/architecture/events.md`.
- **Estados**: `docs/domain/state-machines.md`.
- **Datos**: `docs/architecture/data-model.md` §6 — entidad
  `encuesta_satisfaccion` (queda igual, es de un módulo futuro).

**Corrección de alcance (2026-07-14, mismo día, tras revisar contra un
BPMN de Bizagi que trajo el usuario)**: Venta termina en el envío del
pedido a cocina + el cobro (RN-COM-005). Preparación, emplatado/
empaquetado, despacho y entrega al cliente NO son Venta — se retiraron de
`workflows.md`/`business-rules.md`/`use-cases.md`/`state-machines.md`/
`events.md` y quedaron marcados "fuera de Venta, borrador sin confirmar"
en esos mismos archivos (no se borró contenido, se reetiquetó). Pendiente
del usuario: si eso es UN proceso ("Cumplimiento de pedido") o DOS
(Producción/Cocina + Despacho/Entrega) — dijo "defino después".
**Resuelto 2026-07-27**: UN proceso, `PROC-OPE-002` — ver la sección
"Cumplimiento de pedido — PROC-OPE-002" abajo.

**Relato detallado de los 3 canales (2026-07-14, mismo día)** — el usuario
narró la experiencia real de venta en Web, Central de Pedidos y Sucursal,
paso a paso, con puntos de abandono y su resolución. Incorporado:
- `use-cases.md` — CU-COM-001/002/003 reescritos por canal (antes eran
  por modalidad mesa/takeout-delivery, ahora son por canal real).
- `business-rules.md` — RN-COM-008 (datos obligatorios takeout/delivery),
  RN-COM-009 (confirmar pedido completo antes del precio), RN-COM-010/011/012
  (resolución de desistimiento por stock/precio/tiempo de espera),
  RN-COM-013 (registro de abandono para análisis de embudo).
- `events.md` — `sales.carrito_abandonado`.
- `workflows.md` — diagrama por canal, termina igual en "envío a cocina".
- **BPMN 2.0 para Bizagi** (generado, no a mano):
  `docs/diagrams/Procesos/Comercial/PROC-COM-001-v1.0.bpmn` — 5 lanes
  (Cliente, Web/Kiosko, Central de Pedidos, Atención al Cliente, Cocina),
  80 nodos, 96 flujos, arranca en 1 gateway de canal y converge en "Fin de
  Venta". Generado con script (no a mano) y validado estructuralmente
  (sin referencias colgantes, sin huérfanos, DI completo) — falta
  confirmar que Bizagi lo importe sin fricción, el usuario lo prueba.

Pendiente del slice Venta (señalado por el usuario, no modelado aún):
escalamiento de reclamos post-venta, monitoreo del pedido ya en curso,
manejo de errores técnicos/demoras del sistema. (Desistimiento durante la
toma del pedido SÍ quedó cubierto con RN-COM-010/011/012.) Módulo
`marketing` sigue sin README/contrato propio.

### Modelado de BD — siguiente sesión

Punto de partida: `docs/architecture/data-model.md` (fuente de verdad,
ya ampliado con todo lo definido en esta sesión). Al modelar, revisar
también `docs/domain/domain-model.md` y `docs/domain/business-rules.md`
para constraints/checks a nivel de BD (ej. RN-GEN-001 stock inmutable,
RN-INV-009 disponible=físico−reservado, RN-CPP-007 serie/correlativo
único por empresa).

Entidades transversales a modelar primero (de las que dependen casi
todas las demás):
- `persona` (party model — base de trabajador/cliente natural/usuario)
- `categoria` (aplica a articulo Y activo)
- `categoria_udm` + `unidad_medida` (con ratio de conversión)
- `archivo` (vínculo polimórfico, soporta evidencia/reportes)

Bloques de entidades nuevas de esta sesión, a incorporar al modelado:
- **Productos/Inventario**: `sku`, `lote`, `reserva_stock`, `conteo`+
  `conteo_item`, entidades ya existentes enriquecidas (`articulo` con
  tipos `mercaderia`/`empaque`/`repuesto`, `stock` con fecha_apertura).
- **Documentos**: `guia_remision`, `contrato`, `cotizacion`,
  `reporte_produccion`, `carta_disputa_pago`, `comprobante` (serie/
  correlativo por empresa/POS).
- **Movimientos**: `devolucion`, `auditoria` (proceso, distinto de
  `audit_log`).
- **Operación comercial**: `carrito`, `medio_pago`, `custodia_efectivo`,
  `promocion`, `cuenta_puntos`+`puntos_movimiento`, `programa_puntos_config`,
  `declaracion_itan`.
- **Recursos**: `vehiculo`, `equipamiento`, `repuesto_compatibilidad`,
  `orden_mantenimiento`.
- **RRHH** (`docs/architecture/data-model.md#8b`): `trabajador`,
  `contrato_laboral`, `boleta_pago`, `memorandum`, `amonestacion`, `acta`,
  `certificado_trabajo`, `liquidacion_bss`, `solicitud_permiso`,
  `pacto_permanencia`, `asistencia`, `postulante`, `socio`.
- **Máquinas de estado a implementar como constraints/transiciones**: ver
  `docs/domain/state-machines.md` (Venta con flujo orden→preparación→
  listo→entrega→pago/comprobante flexible→entregado→devolución; Custodia
  de efectivo cajero→supervisor→contabilidad).

Pendiente de decisión técnica antes de migrar: estrategia de tenant
(RLS de Postgres vs. filtro a nivel de aplicación) — no definida aún en
docs, definirla al iniciar esta fase.

### Apertura y Cierre de Caja — PROC-CTB-002 / PROC-CTB-001 (2026-07-16)

`PROC-CTB-002` Apertura de caja documentado (v1.0, Vigente), cerrando el
placeholder pendiente de `workflows.md`. Requirió también actualizar
`PROC-CTB-001` Cierre de caja (v1.0 → v1.1) para resolver una
inconsistencia real: el cierre asumía que el efectivo siempre termina en
contabilidad, pero la custodia puede quedarse en la sucursal (caja fuerte)
según seguridad del local y monto — ver RN-MDP-006.

Incorporado:
- `business-rules.md` — RN-POS-009 (POS de emergencia por grupo de
  sucursales), RN-POS-010 (inventario de POS con serie/código de
  comercio), RN-POS-011 (apertura no se bloquea por faltante/POS
  averiado), RN-POS-012 (encargado prevé sencillo), RN-POS-013 (dedicación
  exclusiva del encargado durante conteo/apertura), RN-MDP-002 ampliada
  (cadena de custodia inversa en apertura), RN-MDP-006 (custodia local vs.
  traslado a oficinas).
- `state-machines.md` — Custodia de efectivo: ciclo completo
  `en_caja → en_supervisor → (en_contabilidad → disponible | directo) →
  en_caja`, en vez de un `[*]` genérico.
- `workflows.md` — narrativa + Mermaid de Apertura de caja; Cierre de caja
  actualizado con la bifurcación de custodia.
- `process-nomenclature.md` — registro maestro actualizado.
- **BPMN 2.0 para Bizagi**: `PROC-CTB-002-v1.0.bpmn` (nuevo) y
  `PROC-CTB-001-v1.1.bpmn` (reemplaza v1.0), en
  `docs/diagrams/Procesos/Contabilidad/`.

### Apertura de Sucursal — PROC-OPE-001 (2026-07-16)

`PROC-OPE-001` Apertura de sucursal documentado (v1.0, Vigente). Primer
proceso del área nueva `OPE` (Operaciones), creada porque el proceso cruza
seguridad física, higiene/inocuidad, recepción de mercadería y RRHH sin
tener una sola área de negocio dueña. Resolvió una contradicción real
planteada en la descripción original: el aire acondicionado no puede
encenderse en paralelo a la limpieza (el polvo levantado acelera su
deterioro) — la apertura de caja (que enciende AC, pantallas, extractores)
pasa a ser secuencial, después de terminada la limpieza, no paralela a
ella.

Incorporado:
- `business-rules.md` — RN-SUC-006 a RN-SUC-012 (checklist de apertura de
  5 minutos no bloqueante, AC apagado durante limpieza, plaga/baños no
  bloquea pero exige desinfección + reporte a Mantenimiento, triage de
  falla de frío, tanque de gas de repuesto obligatorio + sanción por falta
  de aviso, contingencias de luz/agua, doble custodio de llave), RN-PER-006
  (jerarquía Supervisor sobre Encargado de tienda), RN-RRHH-009 a
  RN-RRHH-011 (no marcar entrada no se paga, memorándum vs. carta de
  amonestación por tardanza/falta del encargado según impacto en la
  apertura, compensación de personal faltante).
- `glossary.md` — "Supervisor" (Actores, con alcance RBAC de marca vs. el
  Encargado de tienda de una sola sucursal) y "Alarma" (Recursos, tipo
  Equipamiento).
- `workflows.md` — narrativa + Mermaid de Apertura de sucursal; referencia
  a PROC-CTB-002 (apertura de caja) y a los pasos 6-9 de PROC-INV-001
  (recepción de pedido) en vez de duplicarlos.
- `process-nomenclature.md` — área `OPE` agregada a la tabla; registro
  maestro actualizado.
- **BPMN 2.0 para Bizagi**: `PROC-OPE-001-v1.0.bpmn` (nuevo), en
  `docs/diagrams/Procesos/Operaciones/`. 3 carriles (Encargado/Supervisor,
  Atención al Cliente, Cocina), 59 nodos, 67 flujos — checklist de
  apertura con gateways de excepción para agua/luz/plaga-higiene/frío/gas
  inline; apertura de caja y recepción de pedido representadas como tareas
  que remiten a sus procesos ya documentados.

Pendiente (declarado, no bloquea): diagrama BPMN de las contingencias de
personal faltante (RN-RRHH-011) y de tardanza/falta del encargado o
supervisor (RN-RRHH-010) — la regla de negocio ya existe, el diagrama se
detalla en otra sesión.

### Área RRHH — reclutamiento, contratación e inducción (2026-07-19)

Documentación completa del área de Recursos Humanos: reclutamiento de
personal operativo, selección, elección de modalidad de contrato,
firma/alta, inducción y entrega de uniforme. Empresa acreditada como
**microempresa en REMYPE** (D.S. 013-2013-PRODUCE); saldrá del régimen
aprox. julio 2027 — documentación deja el punto de cambio marcado.

Incorporado:
- `docs/rrhh/` (nuevo): `README.md` (mapa del área, flujo de 13 pasos de
  incorporación), `marco-legal-laboral.md` (régimen microempresa vs.
  general, las 6 modalidades de contrato del grupo, obligaciones legales al
  contratar, plan de salida de REMYPE), `perfiles/` (cocina, atención al
  cliente/mozo-cajero — no existe puesto de cajero separado —, limpieza y
  apoyo, + plantilla para nuevos perfiles).
- `docs/diagrams/Procesos/Recursos-Humanos/` (área nueva en la taxonomía de
  SOPs): 13 SOPs en `Reclutamiento/` (requisición y perfil, convocatoria,
  filtrado, entrevista, verificación de referencias, selección y oferta),
  `Contratacion/` (elección de modalidad, firma y alta en T-Registro,
  apertura de file personal) e `Induccion/` (inducción grupo/empresa/marca,
  inducción al puesto, entrega de uniforme, evaluación de periodo de
  prueba).
- `docs/templates/rrhh/` — 9 plantillas nuevas: 3 contratos (indeterminado,
  sujeto a modalidad, tiempo parcial — con cláusulas de régimen
  microempresa), convocatoria, ficha de entrevista, carta de oferta, ficha
  de datos del trabajador, checklist de alta, acta de entrega de uniforme.
- `business-rules.md` — RN-RRHH-005 corregida (15 días de vacaciones bajo
  REMYPE, no 30); RN-RRHH-012 a RN-RRHH-014 (sin alta en T-Registro no hay
  primer turno, sin perfil ni requisitos discriminatorios no hay
  convocatoria, uniforme como condición de trabajo con acta y registro en
  ERP).
- `00_PROJECT.md` — entrada `rrhh/` en el mapa de documentación; tabla de
  `templates/` y `diagrams/` actualizadas.

Pendiente (declarado, no bloquea): módulo `rrhh` del ERP en sí (spec en
`data-model.md` §8b) — esta sesión documentó proceso y plantillas, no
implementó backend. Definir con contador/abogado el tratamiento de
contratos vigentes al momento de salir de REMYPE.

### Área Compras — proveedores, cotización, OC, recepción y pago (2026-07-19)

Documentación completa del área de Compras: alta/evaluación de
proveedores, cotización (RFQ), emisión y aprobación de OC, recepción en
Almacén Central, conformidad de comprobante y pago. Compra centralizada:
ninguna sucursal compra directo a proveedor externo. Puesto dedicado de
**encargado de compras** (a diferencia de RRHH, no lo ejecuta el
administrador). Pago mixto según proveedor (contado o crédito pactado por
ficha).

Incorporado:
- `docs/compras/` (nuevo): `README.md` (flujo de 7 pasos),
  `marco-legal-compras.md` (régimen Amazonía/Ley 27037 — IGV exonerado
  dentro de zona, comprobantes, detracciones SPOT, plazos de pago,
  centralización), `perfiles/encargado-compras.md`.
- `docs/diagrams/Procesos/Compras/` (área nueva): `Proveedores/` (alta y
  evaluación, evaluación periódica), `Cotizacion-OC/` (solicitud de
  cotización, emisión de OC, aprobación sobre umbral), `Recepcion-Pago/`
  (recepción en Almacén Central, conformidad de comprobante, pago a
  proveedor). 8 SOPs (con el ajuste posterior de caja chica y activos:
  11 en total).
- `docs/templates/compras/` — 4 plantillas: ficha de proveedor, solicitud
  de cotización (RFQ), orden de compra, evaluación de proveedor.
- `business-rules.md` — RN-CMP-008 a RN-CMP-010 (bloqueo de OC sobre
  umbral y prohibición de fraccionamiento, RUC verificado antes del alta
  de proveedor, compra siempre centralizada en Almacén Central).
- `00_PROJECT.md` — entrada `compras/` en el mapa; tablas de `templates/` y
  `diagrams/` actualizadas.

Pendiente (declarado, no bloquea): definir el monto exacto del umbral de
aprobación de OC (queda `[[ COMPLETAR ]]` en el marco legal, la plantilla
de OC y el SOP de aprobación) y el plazo interno de envío de comprobantes
al contador.

**Segundo ajuste — sanción por faltante de caja chica (2026-07-19):** si la
rendición de caja chica queda con faltante no sustentado, Contabilidad
reporta a RRHH (identifica responsable y monto); tras derecho a descargo
(mismo principio que RN-RRHH-004), RRHH emite memorándum (plantilla ya
existente `templates/rrhh/memorandum.md`) y aplica descuento por planilla
del monto faltante; reincidencia (2+) puede escalar a amonestación.
Incorporado: `rendicion-caja-chica.md` (pasos 8-9 nuevos), RN-CMP-017,
`marco-legal-compras.md §7` actualizado.

**Ajuste de flujo real (2026-07-19, mismo día):** el usuario corrigió el
diseño inicial tras revisar. Cambios: (1) proveedores informales
(mercado/supermercado) compran sin OC, sustentados con boleta/factura y
pagados con **caja chica de compras** (fondo fijo, rendición semanal a
Contabilidad); (2) con proveedor "preferente" recurrente, la OC se emite
**sin cotización comparativa** (sustento = requerimiento de almacén +
factura) — la comparación de precio vive en la evaluación periódica, no en
cada compra; (3) el encargado de compras también busca y negocia
**activos/equipamiento**, siempre con cotización comparativa y validación
de especificación/precio por el **área solicitante + gerencia** antes de
la OC; (4) **Contabilidad ejecuta el pago**, no Compras — Compras solo
sustenta el comprobante conforme; (5) la **evaluación de proveedor es
automática en el ERP** a partir de recepciones, con revisión humana solo
sobre alertas.

Incorporado en el ajuste: `docs/compras/perfiles/encargado-compras.md`,
`README.md` y `marco-legal-compras.md` reescritos (3 caminos de compra,
caja chica, activos); 2 SOPs nuevos en `Caja-Chica/` (compra a proveedor
informal, rendición semanal) y 1 en `Activos-Equipamiento/` (búsqueda y
negociación); SOPs de cotización/OC/pago/evaluación corregidos; 2
plantillas nuevas (rendición de caja chica, ficha de requerimiento de
activo); RN-CMP-011 a RN-CMP-016 nuevas; **spec técnica
`src/modules/purchases/README.md` actualizada** para que el módulo real
del ERP se construya conforme a este flujo (camino simplificado, compra
directa, caja chica, OC tipo activo con doble validación, evento de
comprobante conforme a `accounting` en vez de que `purchases` pague).

### Área Comercial — precio, margen, promociones, mercado y desempeño de venta (2026-07-19)

Documentación completa del área Comercial, a partir de un alcance amplio
dado por el usuario: no solo vender, sino mejorar procesos de venta, buscar
mercado/público nuevo, impulsar producto nuevo (coordina con
Producción/I+D+i), coordinar leads con Marketing, ofertas/promociones,
metas de venta, evaluación de desempeño del personal operativo, y
capacitación conjunta con RRHH/Marketing. Puesto dedicado: **jefe/encargado
comercial**. Decisión clave: la evaluación de desempeño de venta que hace
Comercial **alimenta** el proceso de RRHH pero no reemplaza su decisión de
continuidad laboral (periodo de prueba sigue siendo de RRHH). Metas de
venta: sin esquema de incentivo/comisión definido aún — se documentó el
criterio de cómo se aprobaría (Comercial + RRHH + Gerencia, nunca
retroactivo) sin inventar cifras.

Incorporado:
- `docs/comercial/` (nuevo): `README.md` (mapa de responsabilidades →
  SOPs), `politica-comercial.md` (margen de contribución, precios,
  ofertas/promociones, metas/incentivos, coordinación con áreas aún no
  documentadas), `perfiles/jefe-comercial.md`.
- `docs/diagrams/Procesos/Comercial/` — 9 SOPs nuevos en
  `Estrategia-Mercado/` (mejora continua de experiencia de cliente,
  investigación de mercado/público objetivo, coordinación de desarrollo de
  nuevo producto), `Precios-Promociones/` (evaluación de precio y margen,
  creación de oferta/promoción) y `Metas-Desempeno/` (coordinación de leads
  con Marketing, definición/seguimiento de metas, evaluación de desempeño
  comercial del personal, capacitación de venta). Se suman a `Ventas/` y
  `Cobros/` ya existentes.
- `docs/templates/comercial/` — 5 plantillas: ficha de precio/margen,
  brief de oferta/promoción, ficha de requerimiento de nuevo producto,
  reporte de desempeño comercial, plan de capacitación de venta.
- `business-rules.md` — nueva sección "Comercial — estrategia" con
  RN-CML-001 a RN-CML-006 (margen obligatorio antes de publicar precio,
  brief obligatorio de promoción, incentivo nunca retroactivo, evaluación
  de desempeño como insumo de RRHH sin reemplazar su decisión, producto
  nuevo no se compromete sin validar viabilidad, decisión de mercado
  requiere hallazgo documentado).
- `glossary.md` — término **Margen de Contribución** agregado (se usaba en
  varios lugares sin definición formal).
- `src/modules/sales/README.md` (spec técnica) — `lista_precio` con
  vigencia de promoción auto-restaurable, cálculo de margen de
  contribución expuesto a Comercial, cambio de precio siempre por nueva
  versión (nunca edición directa), igual que las OC de `purchases`.
- `00_PROJECT.md` — entrada `comercial/` en el mapa; tablas actualizadas.

Pendiente (declarado, no bloquea): margen de contribución mínimo objetivo
(queda `[[ COMPLETAR ]]`, a definir con contabilidad); esquema de
incentivo/comisión de metas de venta (queda como criterio a definir, sin
cifra); documentación propia de **Marketing** e **I+D+i/Producción** —
Comercial coordina con ambas pero solo documentó su propio lado del
proceso.

### Área Almacén y Logística — conteo, vencimientos/merma, transporte (2026-07-19)

Documentación completa del área, complementando lo que ya existía
(`Abastecimiento-Locales/`, 3 SOPs del ciclo sucursal↔central, y RN-ALM-*/
RN-INV-* ya cubrían bastante del modelo). Se agregó lo que faltaba: conteo
cíclico y ajuste con discrepancia investigada, control FEFO/FIFO explícito,
gestión de vencimiento próximo, registro de merma/desperdicio, devolución a
proveedor, y transporte/transferencias (incluye **transferencia lateral
entre sucursales**, confirmada por el usuario como excepción real del
negocio). Puesto dedicado: **encargado de Almacén Central**; transporte con
**flota propia** (perfil de chofer/repartidor, kilometraje obligatorio
RN-VEH-004).

Incorporado:
- `docs/almacen-logistica/` (nuevo): `README.md` (deja explícito qué NO
  duplica — recepción de compra vive en Compras, ciclo de requerimiento ya
  documentado), `politica-almacen-logistica.md` (FEFO/FIFO, conteo/ajuste,
  punto de reorden — quién lo define [Producción+Contabilidad+Logística,
  RN-INV-008] vs. quién compra [Compras], vencimiento/merma, devoluciones,
  transferencia lateral, transporte), `perfiles/` (encargado de almacén
  central, chofer/repartidor).
- `docs/diagrams/Procesos/Logistica-Almacen/` — 8 SOPs nuevos en
  `Conteo-Auditoria/` (conteo cíclico, ajuste por discrepancia),
  `Vencimientos-Mermas/` (FEFO/FIFO, vencimiento próximo, merma/desperdicio)
  y `Transporte-Transferencias/` (transferencia lateral, logística de
  reparto, devolución a proveedor). Se suman a `Abastecimiento-Locales/`
  ya existente.
- `docs/templates/almacen-logistica/` — 6 plantillas: reporte de conteo
  cíclico, ficha de ajuste, reporte de merma, guía de transferencia
  lateral, guía de devolución a proveedor, hoja de ruta de reparto.
- `src/modules/inventory/README.md` (spec técnica) — entidades `lote`,
  `stock_merma`, `conteo`, `ajuste`, `devolucion`; casos de uso de FEFO/FIFO,
  ajuste con permisos separados de solicitar/aprobar, transferencia lateral
  (ya soportada por el modelo genérico origen/destino, sin cambio de
  esquema); eventos nuevos `inventory.merma_registrada`,
  `inventory.devolucion_a_proveedor`, `inventory.ajuste_fuera_margen`.
- `00_PROJECT.md` — entrada `almacen-logistica/` en el mapa; tablas
  actualizadas.

No se generaron reglas de negocio nuevas — RN-ALM-001..007 y RN-INV-001..020
ya cubrían el modelo; los SOPs las aplican en vez de duplicarlas.

Pendiente (declarado, no bloquea): frecuencia exacta de conteo cíclico y
margen de error de ajuste (quedan `[[ COMPLETAR ]]`, a definir con
Contabilidad); quién autoriza ajustes (admin vs. supervisor de logística,
rol aún no existe formalmente).

### Slice Venta — núcleo de datos (2026-07-20)

Primer slice vertical de datos completo, a pedido del usuario: conectar
venta con cliente y trabajador para habilitar **historial de compras del
cliente** y **ranking de ventas por trabajador**. Ambas consultas ya
funcionan y están probadas (`tests/test_venta_slice.py`).

Antes de modelar se corrigieron 2 inconsistencias reales encontradas:
`data-model.md` §6 `venta.estado` seguía listando el enum viejo de 8
estados; `state-machines.md` ya lo había corregido a 4
(`orden|pagada|facturada|anulada`) el 2026-07-14 — quedó desalineado.
`articulo` no tenía `empresa_id` directo, rompiendo la convención de
tenant (ADR-004) porque `categoria_id` es opcional. Ambas corregidas en
`data-model.md` antes de generar el modelo.

11 tablas nuevas (22 en total con el bloque transversal):
- `usuario` (alcance mínimo — sin rol/permiso/RBAC todavía, eso es el
  slice de auth dedicado).
- `trabajador` (RRHH — nuevo módulo `src/modules/rrhh/`, solo esta
  entidad; el resto de §8b sigue pendiente del slice de RRHH).
- `articulo`, `sku`, `receta`, `receta_item` (base de productos —
  inventory), `cliente`, `punto_venta`, `producto_comercial`, `venta`,
  `venta_item` (sales, módulo nuevo).

Deliberadamente diferido (no bloquea historial/ranking, se agrega
cuando se aborde PROC-COM-002 o el pricing): `modificador`,
`variante_producto`, `combo`, `lista_precio`, `precio`, `promocion`,
`medio_pago`, `pago`, `comprobante`, `carrito`, `central_pedidos`,
`cuenta_puntos`.

Migración `08c7aa59dd6e`, aplicada y verificada en Supabase (ciclo
upgrade/downgrade/upgrade limpio, igual que el bloque anterior).

### Slice Cobro, Comprobante y Caja (2026-07-20)

Segundo incremento del proceso Venta, a pedido del usuario: PROC-COM-002
(Cobro y Emisión de Comprobante) + el ciclo de caja completo
(PROC-CTB-001/002), que el cobro en efectivo necesita para cerrar su
cadena de custodia. Antes de modelar, alineamos 4 decisiones reales con
el usuario (no asumidas):

1. Alcance: caja completa (apertura/cierre/custodia) esta misma vuelta,
   no diferida.
2. Series de comprobante separadas por punto de venta (boleta ≠
   factura, típico SUNAT) — `punto_venta.serie_boleta`/`serie_factura`.
3. `medio_pago` es catálogo **por empresa**, no global del grupo.
4. Pago dividido (varios medios en una misma venta) es un caso real del
   negocio, no solo capacidad técnica — RN-COM-016 nueva.

Gaps reales encontrados y corregidos en `data-model.md` antes de
modelar: `pago` no tenía `monto` ni `idempotency_key` (imposible validar
pago dividido sin monto por fila); `medio_pago` no tenía `empresa_id`;
`punto_venta` no tenía dónde vivir la serie que `comprobante.serie`
dice heredar.

8 tablas nuevas (30 en total): `medio_pago`, `pago` (sales);
`comprobante` (nuevo módulo transversal `src/shared/models/` — sirve a
sales/purchases/accounting, ningún módulo lo posee en exclusiva);
`apertura_caja`, `custodia_efectivo`, `cierre_caja`, `arqueo` (nuevo
módulo `src/modules/accounting/`, solo el ciclo de caja — plan de
cuentas/asiento/periodo_contable siguen pendientes). 3 eventos nuevos en
`events.md`: `accounting.apertura_caja_registrada`,
`accounting.cierre_caja_registrado`, `accounting.cierre_caja_irregular`.

Deliberadamente diferido: `carta_disputa_pago` (RN-MDP-004, camino de
excepción — reclamo de doble cobro).

Migración `8cde35e4f3f2`, verificada en Supabase (ciclo upgrade/
downgrade/upgrade). 13/13 tests pasan (3 nuevos en
`tests/test_cobro_caja_slice.py`).

### Revisión de consistencia y correcciones (2026-07-20)

Revisión completa del proyecto (SOPs, áreas, docs transversales, specs).
Correcciones aplicadas en la misma sesión:

- **git init** con commit inicial del estado previo (trazabilidad).
- Identidad: Provecho = ERP, Grupo Majambo = grupo (00_PROJECT, CLAUDE).
- ADRs normalizados a 3 dígitos; ruta corregida en CLAUDE.md; **ADR-004**
  nuevo: tenant por filtro de aplicación (`empresa_id` obligatorio +
  tests; RLS como refuerzo futuro).
- Glosario: **Horario laboral** vs **Horario de atención** definidos;
  "horario de trabajo" reemplazado; `sucursal.horario_atencion` en
  data-model.
- Catálogo de eventos sincronizado con las specs (10 eventos agregados,
  incl. `inventory.lote_vencido_detectado`); READMEs de módulos y mapa
  `diagrams/modules.md` alineados.
- Data-model: bloque Compras completo (caja chica, compra directa,
  evaluación de proveedor, requerimiento de activo), `stock_lote`
  (FEFO/FIFO implementable + bloqueo de vencidos con memorándum),
  `ajuste`, `apertura_caja`/`cierre_caja`/`arqueo` (caja ya no es módulo
  "futuro"), `flota`, `combo`, `plantilla`; `contrato` reubicado como
  transversal; `articulo.tipo` + `suministro` (enum extensible).
- `PROC-CMP-001` v1.0 → v2.0 (3 caminos de compra, pago en Contabilidad).
- Limpieza: borradores `Procesos/Ventas/` y `diagrams/Ventas.bpm`
  eliminados; doble extensión `.bpmn.bpm` corregida; `diagrams/README.md`
  reescrito (SOP primero → BPMN después; versiones antiguas se conservan).
- CHANGELOG puesto al día (todo el trabajo del 2026-07-19 + esta sesión).
- Skill `sop-creator` endurecida para no dejar cabos sueltos (ver skill).

### Área Producción — cronograma, calidad, inocuidad e inventario de cocina (2026-07-20)

Documentación del área Producción a partir de la descripción de alcance
dada por el usuario: elaboración de subrecetas/procesamiento de insumos
por lotes, área metódica con foco fuerte en inocuidad y calidad (de ahí
depende gran parte de la calidad del producto final), responsable de la
cocina de producción y su mantenimiento, produce según cronograma +
necesidades de la empresa/almacén, da soporte a I+D+i/Comercial para
nuevo producto y mejora continua, e inventario propio similar al de
cocina de sucursal. Roles: cocinero, jefe de cocina.

Antes de modelar se resolvieron 2 decisiones reales con el usuario:

1. **Alcance temporal**: `domain-model.md` ya documentaba que la primera
   cocina de producción recién está planeada para 2027 — hoy la
   producción se hace en cocinas de sucursal. El usuario confirmó que
   esta sesión documenta **spec a futuro** (diseño/preparación), no un
   área operando hoy; la cocina de sucursal actual sigue bajo
   Operaciones/RRHH sin cambio.
2. **No conformidad de calidad**: se evalúa si el lote es corregible
   (reproceso) o no (desecho); en ambos casos se genera un
   `reporte_escalamiento` (reutiliza el patrón ya definido para
   atención al cliente); el desecho exige evidencia de destrucción
   (foto/video + testigo) para prevenir sustracción disfrazada de merma.
3. **Cronograma**: plan fijo por tipo de receta/proceso (evita
   contaminación cruzada) + ajuste por necesidad urgente de Almacén
   Central — no es puramente reactivo.

Incorporado:
- `docs/produccion/` (nuevo): `README.md` (mapa de responsabilidades),
  `politica-produccion.md` (cronograma, calidad/no conformidad, inocuidad
  referida a RN-CDP-*, inventario de cocina, soporte a I+D+i),
  `perfiles/` (jefe de cocina, cocinero de producción).
- `docs/diagrams/Procesos/Produccion/` (área nueva): 4 SOPs —
  `Planificacion/` (plan de producción, cronograma fijo + ajuste),
  `Calidad-Inocuidad/` (control de calidad y no conformidad, checklist de
  inocuidad de turno), `Inventario-Cocina/` (conteo cíclico de cocina de
  producción), `Soporte-IDI/` (soporte técnico a nuevo producto/mejora
  continua).
- `docs/templates/produccion/` — 5 plantillas: orden de producción,
  reporte de producción, ficha de no conformidad, checklist de inocuidad,
  reporte de conteo de cocina. Nuevo producto reutiliza la ficha ya
  existente de Comercial (no se duplica).
- `business-rules.md` — nueva sección "Producción — cronograma, calidad
  y cocina": RN-PRD-011 a RN-PRD-017 (plan de producción, agrupación por
  tipo de receta, control de calidad, no conformidad→escalamiento,
  evidencia de destrucción, inventario de cocina, viabilidad técnica
  antes de comprometer lanzamiento).
- `data-model.md` §7 — nueva entidad `plan_produccion`; `orden_produccion`
  ampliada con `plan_produccion_id` y `control_calidad_resultado`;
  `reporte_escalamiento` ampliado con origen `produccion` y motivo
  `no_conformidad_calidad` + `evidencia_id`.
- `workflows.md` — placeholder "Producción (si existe)" reemplazado por
  narrativa + Mermaid real; `PROC-PRD-001` v0.1→v1.0 (sigue Borrador:
  spec completa, sin operación real hasta 2027).
- `process-nomenclature.md` — registro maestro actualizado.
- `glossary.md` — término **Jefe de Cocina (Producción)** agregado a
  Actores.
- `events.md` — nuevo evento `production.no_conformidad_detectada`.
- **`src/modules/production/README.md`** (nuevo, spec técnica) — módulo
  backend `production` especificado conforme a este flujo.
- `00_PROJECT.md` — entrada `produccion/` y `templates/produccion/` en el
  mapa.

Pendiente (declarado, no bloquea): frecuencia exacta de cronograma y de
conteo cíclico de cocina (quedan `[[ COMPLETAR ]]`, a definir con
Gerencia/Contabilidad al diseñar la primera cocina de producción);
criterios técnicos de aceptación/rechazo de calidad por receta (a definir
con Producción/I+D+i cuando exista personal del área).

**Ajuste de costeo, desperdicio e inocuidad (mismo día, 2026-07-20):** el
usuario detalló 4 puntos que faltaban en la primera pasada:

1. El desperdicio de un insumo no es un número único: cada insumo puede
   tener más de un tipo de desperdicio (ej. tomate → pulpa aprovechable,
   más cáscara y semilla como desperdicio) y cada tipo tiene su propio
   peso real. `orden-produccion.md` pasa de un campo libre a una tabla
   insumo/tipo de desperdicio/peso.
2. El ERP debe calcular el **costo real** del producto aprovechable
   sumando el costo de insumos (el insumo completo comprado, no solo la
   parte aprovechable) más horas-hombre — nunca a mano.
3. Ningún documento de conteo se llena a mano: `reporte-conteo-cocina.md`
   pasa de plantilla rellenable a documento autogenerado por el ERP, el
   jefe de cocina solo visa — mismo principio que ya regía
   `reporte-produccion.md`, ahora explícito para evitar error humano de
   transcripción.
4. Parte de la inocuidad es revisar que los equipos de frío estén en
   rango de temperatura; fuera de rango, reporte automático a Gerencia
   (mismo criterio que la falla de frío en apertura de sucursal,
   RN-SUC-009).

Incorporado: RN-PRD-018 (costeo automático) y RN-CDP-005 (equipos de
frío) en `business-rules.md`; `receta_item.tipo_desperdicio`,
`consumo_produccion_item` y `checklist_inocuidad_turno` nuevas en
`data-model.md` §7; `orden_produccion` ampliada con costeo
(horas_hombre, costo_insumos, costo_mano_obra, costo_real_unitario);
evento `production.equipo_frio_fuera_rango` en `events.md`; plantillas
`orden-produccion.md` (tabla de desperdicio + costeo), `reporte-conteo-cocina.md`
(autogenerado) y `checklist-inocuidad.md` (tabla de equipos de frío)
reescritas; SOPs `plan-produccion-cronograma.md`,
`checklist-inocuidad-cocina.md` y `conteo-ciclico-cocina-produccion.md`
actualizados; perfiles de jefe de cocina y cocinero ajustados.

### Área Gerencia — gobierno y matriz de aprobaciones (2026-07-22)

Documentación del área Gerencia a partir de la descripción del usuario:
parte estratégica y de autoridad, guía a nuevos mercados/marcas, último
visado cuando las áreas necesitan aprobar propuestas, y vela por que
empresa y trabajadores cumplan. Gerencia ya aparecía en ~57 archivos como
"aprobador final" pero sin dueño ni matriz propia — esta sesión lo
formaliza.

3 decisiones con el usuario antes de escribir:

1. **Actor**: Gerente General **delegado por los socios** — se respeta la
   línea del glosario (Gerencia/Directivo = trabajador con facultades
   delegadas; Socio = dueño). Decisiones reservadas a socios (PI, marca,
   alta/baja de empresa) quedan fuera del alcance del gerente.
2. **Control/disciplina**: Gerencia **decide/ordena, RRHH ejecuta** con
   el debido proceso ya documentado (RN-RRHH-004) — Gerencia no aplica la
   sanción por sí misma.
3. **Alcance ligero** (elección del usuario): **matriz de aprobaciones +
   política de gobierno**, sin SOPs estratégicos paso a paso. La
   estrategia se registra por decisión (acta), no por procedimiento fijo.

Consecuencia de diseño: **sin módulo backend** `gerencia` — la facultad
de aprobar es un permiso RBAC, no una tabla; Gerencia es autoridad +
documentos. Único artefacto de datos: `decision_gerencial` (transversal,
`shared`).

Incorporado:
- `docs/gerencia/` (nuevo): `README.md` (qué hace / qué no duplica),
  `politica-gerencia.md` (gobierno corporativo, **matriz de aprobaciones**
  como fuente única de umbrales, dirección estratégica, supervisión y
  control), `perfiles/gerente-general.md`.
- `docs/templates/gerencia/` — 2 plantillas: acta de decisión gerencial,
  ficha de evaluación de nuevo mercado/marca.
- `business-rules.md` — nueva sección "Gerencia — dirección y gobierno":
  RN-GER-001 a RN-GER-006 (facultades delegadas, decisión siempre
  documentada, matriz de aprobaciones como fuente única, abstención por
  conflicto de interés, decide→ejecuta el área competente, entrada a
  nuevo mercado con estudio previo).
- `data-model.md` §8c (nueva) — entidad transversal `decision_gerencial`;
  la matriz de aprobaciones queda como política/config, no tabla.
- `glossary.md` — **Gerente General**, **Matriz de aprobaciones**, **Acta
  de decisión gerencial** agregados.
- `00_PROJECT.md` — entrada `gerencia/` y `templates/gerencia/` en el mapa.

No genera PROC (no hay SOPs de proceso), ni evento, ni módulo — coherente
con el alcance ligero elegido.

Pendiente (declarado, no bloquea): umbral exacto de OC y de escalamiento
de lanzamientos a Gerencia (quedan `[[ COMPLETAR ]]` en la matriz, se
resuelven con los mismos pendientes de Compras/Comercial ya listados);
rango salarial del Gerente General (con los socios).

### Reglas de conducta laboral (2026-07-22)

A pedido del usuario, 4 reglas de conducta agregadas a `business-rules.md`
(sección RRHH): **RN-RRHH-015** (uniforme completo, limpio y presentable
toda la jornada), **RN-RRHH-016** (no contratar parientes de 1.er/2.º
grado — conflicto de interés/trato preferente, RN-GRP-001; parentesco
sobreviniente se declara y puede exigir reubicación), **RN-RRHH-017** (no
relaciones sentimentales en el mismo centro laboral ni con subordinación
directa; se declara y reubica para eliminar el conflicto), **RN-RRHH-018**
(no usar conocimiento ni recursos de la empresa para terceros o beneficio
personal — extiende confidencialidad RN-EMP-002/RN-GRP-004 y conflicto de
interés RN-GER-004 al personal operativo, falta grave).

### Área Marketing — marca, contenido, campañas y material (2026-07-22)

Documentación completa del área Marketing a partir del alcance dado por el
usuario. Frontera clave confirmada: **Marketing atrae el lead, Comercial
cierra la venta e investiga la oportunidad**. Marketing = crecimiento,
notoriedad, marca, contenido; Comercial = conversión y exploración de
mercado. Puesto dedicado: **jefe/encargado de Marketing**.

Distinción respetada: `MKT` (Marketing, ejecución) ≠ `MRC` (Manejo de
marca, identidad del holding) — Marketing asegura el **buen uso** de la
marca, no modifica su identidad (reservado, RN-MAR-004). Consecuencia de
diseño: Marketing sí tiene módulo backend (a diferencia de Gerencia),
porque maneja entidades propias (campaña, contenido, lead, material).

Incorporado:
- `docs/marketing/` (nuevo): `README.md` (frontera con Comercial y qué NO
  hace), `politica-marketing.md` (uso de marca, pertinencia sobre
  viralidad, brief/aprobación de campañas, material vía Compras, agencias),
  `perfiles/jefe-marketing.md`.
- `docs/diagrams/Procesos/Marketing/` (área nueva) — 6 SOPs:
  `Marca-Contenido/` (uso de marca + naming, plan de contenido y redes),
  `Campanas/` (lanzamiento de producto, medios y eventos),
  `Proveedores-Agencias/` (material promocional e implementación en
  sucursal, evaluación de propuesta de agencia/interna).
- `docs/templates/marketing/` — 4 plantillas: brief de campaña, calendario
  de contenido, evaluación de propuesta de agencia, checklist de material
  en sucursal.
- `business-rules.md` — nueva sección "Marketing": RN-MKT-001 a RN-MKT-007
  (uso de marca sin modificarla, pertinencia sobre viralidad, brief +
  handoff de leads con Comercial, material vía Compras, verificación en
  sucursal, evaluación de agencia con matriz de aprobaciones, naming).
- `data-model.md` §8d (nueva) — entidades `campana`, `pieza_contenido`,
  `lead`, `implementacion_material_sucursal`; `encuesta_satisfaccion`
  reasignada a este módulo.
- `events.md` — `marketing.campana_lanzada`, `marketing.lead_generado`
  (consumido por `sales` para atribución lead→venta).
- `workflows.md` + `process-nomenclature.md` — **PROC-MKT-001** (Campaña
  de marketing) v1.0 Borrador con narrativa + Mermaid.
- `glossary.md` — **Lead**, **Campaña**, **Naming**, **Jefe de Marketing**.
- **`src/modules/marketing/README.md`** (nuevo, spec técnica) — resuelve
  el pendiente de "módulo marketing README/contrato propio".
- `00_PROJECT.md` — entradas `marketing/` y `templates/marketing/`.

Pendiente (declarado, no bloquea): periodicidad del calendario de
contenido.

### Ajustes de Marketing y Gerencia — feedback del usuario (2026-07-22)

Tras revisar el primer borrador de Marketing, el usuario corrigió 3 cosas:

1. **Marketing gestiona las marcas sin burocracia extra** — RN-MKT-001
   reescrita: Marketing es dueño operativo de las marcas (uso,
   consistencia, contenido, naming); solo lo reservado a socios
   (modificación estructural de identidad, venta de PI — RN-MAR-004,
   RN-GRP-006) lo excede. Se eliminó la capa de "elevar a Manejo de marca"
   para el trabajo cotidiano.
2. **Agencias las evalúa Marketing, Gerencia valida** — RN-MKT-006
   reescrita: la agencia es un servicio; Marketing la evalúa por su
   conocimiento, Gerencia valida, se formaliza por contrato y paga
   Contabilidad — **no pasa por Compras**. El **material** (bien) sí sigue
   vía Compras (RN-MKT-004). Ajustados el SOP de evaluación de agencia, la
   plantilla, el SOP de medios/eventos, el módulo backend y `data-model`.
3. **Presupuesto anual — nuevo proceso en Gerencia** — el usuario pidió un
   mecanismo para definir presupuestos: reunión anual donde cada área
   presenta propuesta y Gerencia designa presupuesto + límite de gasto
   autónomo por área (bajo el límite, el área ejecuta sin aprobación
   puntual; sobre él o fuera de presupuesto, aprueba Gerencia). Nuevo
   **RN-GER-007**, **PROC-GER-001** (workflows + registro), SOP
   `definicion-presupuesto-anual.md`, plantilla `propuesta-presupuesto-anual.md`,
   y fila en la matriz de aprobaciones. Reemplaza el `[[ COMPLETAR ]]` de
   "umbral de presupuesto de campaña" por el marco de presupuesto anual
   (los montos/límites por área siguen `[[ COMPLETAR ]]`, se fijan en la
   reunión).

### Cumplimiento de pedido — PROC-OPE-002 (2026-07-27)

Cierra el pendiente de decisión abierto el 2026-07-14: lo que ocurre
después de Venta es **un** proceso, no dos.

**Decisión y por qué.** `PROC-OPE-002 Cumplimiento de pedido` v1.0
Vigente, área **Operaciones** (cruza cocina de sucursal, atención al
cliente y reparto sin pertenecer a ninguna). Preparación y
Despacho/Entrega son etapas internas. Cuatro razones: (1) un solo
resultado — entra Orden de Pedido, sale pedido entregado — y ningún
artefacto de traspaso entre cocina y despacho; (2) el código ya lo modeló
como continuo: `venta_item.estado_preparacion` es UNA máquina de estados
y `kds_pantalla.tipo` (`preparacion`/`despacho`) es un filtro de vista
sobre ella, partirlo obligaba a partir la máquina y duplicar el contrato
del KDS; (3) "Producción" ya nombra la cocina de producción central
(`PROC-PRD-001`, primera cocina 2027) — reusarlo para la cocina de
sucursal rompe la regla de que la sigla nombra un área real; (4) mesa/
takeout/delivery son variantes de un mismo flujo, no procesos distintos.
No se pierde medición separada: `venta_item.updated_at` por transición ya
da tiempo de preparación y de despacho. Si el reparto llega a tener
ruteo, flota y liquidación propios, se separa entonces como v2.0.

**Especificación.** `process-nomenclature.md` (registro maestro + nota que
distingue `PRD` de la preparación en sucursal), `workflows.md` (sección
propia con gateway por modalidad; el borrador "fuera de Venta" se
reemplaza por un puntero), `use-cases.md` (CU-OPE-001/002/003 por
modalidad, con excepciones: cliente ausente, pedido no recogido, producto
rechazado), `business-rules.md` (**RN-CUP-001..012** nuevas; RN-COM-005
apunta al proceso; **RN-COM-007 reactivada** — la encuesta recupera su
disparador tras 13 días sin dueño), `state-machines.md` (la máquina pasa
de borrador a oficial, y se declara qué NO es estado: entrega fallida,
devolución y el pago al finalizar en mesa), `events.md` (filas de
`sales.venta_entregada` y `marketing.encuesta_enviada`), `data-model.md`
(entidad `entrega` especificada para el slice de delivery).

**Deriva corregida.** `sales.pedido_listo` se publicaba desde el slice KDS
(2026-07-25) sin fila en `events.md`, contra la propia regla del catálogo
("definir la fila ANTES de publicarlo"). Queda registrado.

**Código.** `sales/application/cumplimiento.py`: `registrar_entrega`
exige todos los ítems en `listo` (RN-CUP-005), es idempotente (repetirla
no reemite el evento) y publica `sales.venta_entregada` con modalidad,
cliente y plataforma de reparto. `POST /sales/ventas/{id}/entrega` con
permiso **propio** `sales.entregar_pedido` y rol nuevo `despachador`;
`cocinero` deliberadamente NO lo tiene (RN-CUP-006). En consecuencia el
bump del KDS ya **no** llega a `entregado`: devuelve 409 apuntando al
endpoint de entrega — antes cualquiera con `kds.operar` cerraba el pedido
ítem por ítem, lo que dejaba el permiso de entrega decorativo. Sin
migración: el enum ya tenía `entregado`.

**Fuera de esta fase, a propósito**: entidad `entrega` (trazabilidad del
repartidor y de la entrega fallida), plazo de espera de takeout
(RN-CUP-011) y BPMN del proceso — ver Deuda técnica → sales.

### Fase de procesos (tras el modelado de BD)

1. `users`: auth (login PIN → JWT/refresh), RBAC, contexto de tenant, auditoría base.
2. Organización: grupo → empresa → marca → sucursal → almacén (vive en `users` o módulo `organization`).
3. `inventory`: artículos, stock por almacén, movimientos.
4. `purchases`: proveedores, OC, recepción → entrada a almacén central.
5. Solicitudes + transferencias central → local.
6. `sales`: PDV, recetas, descuento automático de insumos, pagos, Nubefact.
7. Producción, contabilidad, RRHH, resto de módulos.
