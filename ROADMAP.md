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
| Modelado de base de datos completo (SQLAlchemy + Alembic) | 🔶 en curso 2026-07-25 | Bloque transversal + organización (11) + slice Venta núcleo (11) + slice Cobro/Comprobante/Caja (8) + slice auth/RBAC (7) + slice inventory core (3) — 40 tablas en total. BD de desarrollo corre en **Supabase** (Postgres gestionado, solo BD — sin su Auth/RLS, ver `docs/engineering/devops.md`); Docker local sigue disponible como alternativa. Resto por slice vertical. |
| Módulo `users` (auth JWT + PIN + RBAC) | ✅ 2026-07-25 | Slice auth+CRUD implementado: 7 tablas RBAC (`rol`, `permiso`, `usuario_rol`, `rol_permiso`, `usuario_sucursal`, `refresh_token`, `audit_log`) + lockout en `usuario`. Login/refresh(rotativo+detección de reuso)/logout/me + CRUD admin de usuarios/roles/permisos/asignaciones. Argon2id, JWT, `require_permission` deny por defecto. `docs/security/authorization.md`. Restricciones JSONB por permiso: aplicadas desde 2026-08-02 (ADR-022, ver Deuda técnica). |
| Migraciones Alembic | 🔶 al día 2026-08-05 | La BD dev de Supabase está en la cabeza del repo (`a4c8f21e6b09`, guía de remisión) y `python -m src.core.esquema` reporta **cero deriva**. Las primeras seis fueron transversal+org, slice Venta, cobro/caja, cliente opcional, slice auth/RBAC e inventory core; el detalle de cada slice posterior va en su fila. Tras aplicar una migración que suma permisos hay que correr `python -m src.seeders.seed` (idempotente): la migración crea tablas, no filas de RBAC. |
| Seeders (admin / PIN 123456, org base) | ✅ 2026-07-27 | `src/seeders/seed.py` (idempotente, prohibido en prod): matriz de roles/permisos semilla, `admin`/PIN `123456` y la **organización real** del grupo — empresa Majambo EIRL (RUC 20450311520, Jr. Ramón Castilla 248 - Tarapoto, zona `amazonia_ley27037`), marca Charlie's Pizzas **licenciada** a la empresa (`licencia_marca`), sucursales `CH1` (Jr. Ramón Castilla 248) y `CH2` (Jr. Lamas 299) activas y alquiladas (RN-IMP-004), almacén central `WH1` (`sucursal_id` NULL). Requirió `almacen.direccion` (migración `e5a1c93b7d40`): el central no cuelga de ninguna sucursal y no había dónde guardar su ubicación. Correr: `python -m src.seeders.seed`. Diferido: almacenes de sucursal de CH1/CH2 (no pedidos; su mín./máx. por SKU depende de datos de operación inexistentes) y CRUD de organización por API — hoy empresa/sucursal/almacén solo se crean por seeder. |
| Módulo `inventory` | 🔶 slices 1-4 ✅ 2026-08-01 | **Slice 1**: catálogo (CRUD artículos/categorías/SKUs), stock por almacén (vía `movimiento_inventario` inmutable) y ajuste con segregación (`solicitar_ajuste` ≠ `aprobar_ajuste`, aprobador ≠ solicitante). Migración `be914c92a94b`. **Slice 2 — lote/FEFO** (2026-07-27, ADR-015): `lote` + `stock_lote`, control **opcional por artículo** (`articulo.controla_lote` — el queso sí, las servilletas no). La salida reparte por FEFO (vence antes, sale antes; sin vencimiento va al final → FIFO) y genera **un movimiento por lote tomado**, con `lote_id` explícito como override. El lote vencido se bloquea cuando el picking lo toca y publica `inventory.lote_vencido_detectado`; `POST /lotes/bloquear-vencidos` hace el barrido a demanda. La recepción de compra transporta el lote y vencimiento del proveedor (RN-VNC-002) y producción crea el suyo. Nada entra sin lote si el artículo lo controla: un ingreso sin lote cae en el lote del día. `POST /movimientos` pasa a devolver **lista** de movimientos. El hub replica `lote`/`stock_lote` (ADR-009, 28 recursos). Migración `c9a2f4e18b60`. Tests: `tests/test_lotes.py`. **Slice 3 — conteo cíclico** (2026-08-01, ADR-019): `conteo` + `conteo_item` con la periodicidad configurada **en la categoría** (`categoria.frecuencia_conteo`, RN-INV-007) — no hay número universal. Calendario derivado del último conteo cerrado + frecuencia, sin tabla de programación; conteo general que pone al día a todas las categorías del almacén; stock esperado congelado al abrir; conteo **a ciegas** por defecto (`inventory.ver_stock_esperado`); el cierre genera un `ajuste` pendiente por diferencia (`ajuste.conteo_id`) sin mover stock, con margen `INVENTORY_MARGEN_AJUSTE_PCT`; `inventory.conteo_vencido` reporta a almacén y gerencia lo no contado en su fecha (RN-INV-021). Permisos nuevos `inventory.contar` y `inventory.ver_stock_esperado`. Migración `c4e70a91d5b8`. Tests: `tests/test_conteos.py`. **Slice 4 — abastecimiento interno** (2026-08-01, ADR-020): `reserva_stock` + `solicitud_insumos`/`solicitud_item` + `transferencia`/`transferencia_item`. El local pide, el supervisor aprueba **y reserva** el stock en el abastecedor, el central despacha (FEFO, un `transferencia_item` por lote) y el local recibe. `GET /stock` expone `cantidad`/`reservado`/`disponible` (RN-INV-009): reservar exige disponible, pero consumir nunca se bloquea por una reserva —una venta ya ocurrida no se niega— y por eso el disponible puede quedar negativo. Diferencias registradas, no corregidas: no se despacha más de lo aprobado ni se recibe más de lo enviado, menos sí (RN-INV-001/002). Cancelar libera reservas (RN-INV-010) y hay liberación manual (RN-INV-011). Transferencia lateral sucursal↔sucursal con la misma entidad. Migración `d8b35f1ca207`. Tests: `tests/test_transferencias.py`. **Slice 5 — recetas editables** (2026-08-03, ADR-023): CRUD de receta e ítems, duplicar con "(copy)", escalar por factor y **aritmética tecleada** en la cantidad ("1000/3"), evaluada en el servidor con `ast` y lista blanca —nunca `eval`— y redondeada a los decimales de la UdM del insumo (RN-COM-024); `receta_item.expresion` guarda lo tecleado para reeditarlo. `GET /inventory/unidades-medida` y contrato público `receta_resumen`. Migración `b6d1e83f47ac`. Tests: `tests/test_recetas_variantes.py`. Diferido: devolución, guía remisión, `stock_merma`. |
| Módulo `purchases` | 🔶 slice core ✅ 2026-07-25 | CRUD de proveedores (natural liga a `persona`, jurídico con RUC propio) y ciclo de OC tipo `insumo` (crear → emitir → recibir → anular), con idempotencia y umbral de aprobación configurable. `purchases.compra_recibida` → inventory suma stock y recalcula `costo_promedio`. Conformidad de comprobante (`purchases.dar_conformidad`) registra el `comprobante` recibido y dispara `purchases.comprobante_conforme` → cola de pago en `accounting`. Migración `4ff85f833b29` aplicada. Diferido: ver Deuda técnica. |
| Módulo `sales` (PDV) | 🔶 slices 1-3 ✅ 2026-07-27 | Venta con correlativo+idempotencia → `sales.venta_confirmada` → inventory descuenta por receta (+merma+empaque); cobro con pagos parciales → `pagada`; anulación pre-pago repone stock; CRUD productos/medios de pago. **KDS** (slice 2): pantallas configurables por sucursal y categorías (`kds_pantalla`, migración `7672566bf189`), avance por ítem en `venta_item.estado_preparacion` (fuente única → todas las pantallas ven el avance real), tipos preparación/despacho, comanda imprimible con contador de reimpresiones, evento `sales.pedido_listo`, rol `cocinero`. Kiosk/Central de Pedidos = clientes del mismo contrato, no módulos. **Cumplimiento de pedido** (slice 3, 2026-07-27): `PROC-OPE-002` definido como UN proceso (área Operaciones) y su etapa de entrega implementada — `POST /sales/ventas/{id}/entrega` con permiso propio `sales.entregar_pedido` y rol `despachador`, idempotente, publica `sales.venta_entregada` (disparador de la encuesta de marketing, RN-COM-007). **Slice PDV** (slice 4, 2026-07-28, ADR-018, migración `d7e3b8c14f52`): `mesa` tipada por sucursal + mapa de salón derivado; `grupo_cobro` para dividir la cuenta y emitir un comprobante por pagador (RN-COM-018); receptor tecleado en caja que decide boleta/factura sin cliente registrado (RN-CPP-003); descuento manual de orden con motivo y autorizador (RN-COM-017, permiso propio). Suma `POST /sales/clientes` y `GET /sales/ventas`. **Variantes y opciones** (slice 5, 2026-08-03, ADR-023, migración `b6d1e83f47ac`): Personal/Mediana/Familiar son productos hijos con receta y precio completo propios (RN-COM-022) — no un recargo sobre un precio base; el padre agrupa y no se vende. `producto_opcion_grupo` declara cuántos extras hay que elegir (RN-COM-023): `minimo >= 1` **es** ser obligatorio, sin flag aparte, y la regla se hace cumplir al confirmar la venta porque el kiosko entra por el mismo endpoint. Nombres normalizados a formato título en el servidor. Frontend: **Catálogo como módulo propio** (`/catalogo/productos`, no `/ventas`), con gate por permiso exacto `sales.gestionar_catalogo` — un cajero tiene `sales.crear` y con el filtro por prefijo veía y leía toda la carta; ahora el módulo no le aparece ni entrando por URL (enmienda a ADR-013). Ficha de producto que **elige** recetas ya creadas (el editor vive en Catálogo → Recetas; tenerlo en los dos lados hacía pensar que eran dos recetas distintas) y selector obligatorio de presentación + extras en el PDV. Diferido: ver Deuda técnica. |
| Módulo `sales` (PDV) | 🔶 slices 1-3 ✅ 2026-07-27 | Venta con correlativo+idempotencia → `sales.venta_confirmada` → inventory descuenta por receta (+merma+empaque); cobro con pagos parciales → `pagada`; anulación pre-pago repone stock; CRUD productos/medios de pago. **KDS** (slice 2): pantallas configurables por sucursal y categorías (`kds_pantalla`, migración `7672566bf189`), avance por ítem en `venta_item.estado_preparacion` (fuente única → todas las pantallas ven el avance real), tipos preparación/despacho, comanda imprimible con contador de reimpresiones, evento `sales.pedido_listo`, rol `cocinero`; **pantalla KDS** en `frontend/app/kds/` (2026-08-03, tarjeta por pedido con tachado por ítem, polling 3 s). Kiosk/Central de Pedidos = clientes del mismo contrato, no módulos. **Cumplimiento de pedido** (slice 3, 2026-07-27): `PROC-OPE-002` definido como UN proceso (área Operaciones) y su etapa de entrega implementada — `POST /sales/ventas/{id}/entrega` con permiso propio `sales.entregar_pedido` y rol `despachador`, idempotente, publica `sales.venta_entregada` (disparador de la encuesta de marketing, RN-COM-007). **Slice PDV** (slice 4, 2026-07-28, ADR-018, migración `d7e3b8c14f52`): `mesa` tipada por sucursal + mapa de salón derivado; `grupo_cobro` para dividir la cuenta y emitir un comprobante por pagador (RN-COM-018); receptor tecleado en caja que decide boleta/factura sin cliente registrado (RN-CPP-003); descuento manual de orden con motivo y autorizador (RN-COM-017, permiso propio). Suma `POST /sales/clientes` y `GET /sales/ventas`. Diferido: ver Deuda técnica. |
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
| Módulo `marketing` | 🔶 slice core ✅ 2026-08-01 | Primer código del módulo: `campana` con brief obligatorio (RN-MKT-003 — sin objetivo, público, presupuesto y KPI no se aprueba, y sin aprobación no sale a canal; quien redacta el brief no lo aprueba: `marketing.campana_aprobar` vive en `supervisor`, no en el rol `marketing`), `pieza_contenido` que solo se publica si es pertinente a la marca y su uso de marca está validado (RN-MKT-001/002), `lead` medido por conversión real y no por volumen, `implementacion_material_sucursal` (verificación en sitio, RN-MKT-005) y `encuesta_satisfaccion` (RN-COM-007), que la migración saca de §6 y le da dueño. La **atribución lead→venta** es automática solo cuando no hay ambigüedad —un único lead abierto del cliente en campaña en curso—; con dos o más queda manual, porque adivinar qué campaña convirtió falsea justo la métrica que la campaña existe para medir. Marketing lee el estado de entrega por el contrato público `sales::venta_para_encuesta`, nunca importando `Venta`. Migración `e9c3b7412a68`, 17 endpoints, 13 tests. Diferido: ver Deuda técnica. |
| Contabilidad: procesos y plantillas | ✅ 2026-07-24 | `docs/contabilidad/` (política + marco legal + perfil contador/tesorero), 3 SOPs nuevos (pago a proveedor PROC-CTB-003, conciliación bancaria PROC-CTB-004, arqueo sorpresa PROC-CTB-005), 4 plantillas — ver detalle abajo. Área = tesorería + finanzas + registro + auditoría interna en un solo responsable, supervisada por Gerencia (RN-CTB-004..009; control en dos niveles: Contabilidad audita a las operativas, Gerencia audita a Contabilidad). Quedan propuestos PROC-CTB-006..013 |
| Mantenimiento, Sistemas/TI como áreas propias | ⬜ | Definidas como áreas del negocio (posible tercerización); documentación pendiente, desactivadas por ahora |
| Supervisión, CRM, tesorería, activos, proyectos, BI/reportes | 🔶 revisada 2026-08-05 | **Cuatro de los siete ya no son futuros y dos no van a ser módulos.** **BI/reportes** ✅ 2026-08-04: `src/core/reportes/` (ADR-024) con catálogo cerrado de 10 reportes, tableros guardados por usuario y compartidos por rol, filtros y exportación a CSV. **Tesorería** ✅ 2026-07-25: vive **dentro de `accounting`** por decisión explícita del usuario —pago a proveedor, `movimiento_dinero`, caja y custodia— y separarla al salir de REMYPE es un pendiente de organización, no de código. **Supervisión** no es módulo: es el rol RBAC `supervisor` más la matriz de aprobaciones de Gerencia (`parametro_empresa` + `decision_gerencial`); un módulo "supervisión" sería un permiso disfrazado de dominio. **CRM** parcial: `sales.cliente` (con contrato público de lectura) y `marketing.lead`/`campana`/`encuesta_satisfaccion` con atribución lead→venta ya cubren captar y medir; falta historial de interacciones y segmentación, sin caso hasta que haya campañas reales corriendo. **Activos** ⬜ pero **ya tiene dueño**: se compran en `purchases` (OC tipo `activo` + `requerimiento_activo`, deuda declarada) y se deprecian en `accounting` (activo fijo/depreciación, PROC-CTB-007/010) — partirlos en un tercer módulo cortaría el ciclo de compra en dos. **Proyectos** ⬜ sin caso: el grupo no ejecuta obra ni proyectos facturables hoy. |
| Integración de facturación electrónica (**Factiliza**) | 🔶 boleta/factura ✅ 2026-07-26 | **Reemplaza a Nubefact** (decisión del usuario). Adaptador en `src/shared/integrations/factiliza/`; cola Celery + servicio `worker`; migración `b3d7f21ac094`. Emite boleta/factura con IGV desglosado y exoneración de Amazonía (RN-IMP-001). Nota de crédito, PDF/XML/CDR ✅ 2026-08-04. **Guía de remisión ✅ 2026-08-05** (ADR-027) — construida en `inventory`, no en `sales`: declara un traslado entre almacenes, no una venta. |
| Integración Izipay | ⬜ | Proveedor decidido (ADR-003) |
| Integraciones Google / Meta | ⬜ | |
| Agentes IA para pedidos | ⬜ | |
| Notificaciones | ⬜ | Celery + canales por definir |
| Auditoría (audit_log) | ⬜ | Especificada en data-model |
| Endurecimiento de producción (rate limit, secretos, HTTPS, cabeceras) | 🔶 base ✅ 2026-07-26 | Rate limit por IP en login/refresh (Redis, fail-open), validación de config que aborta el arranque en `production` con valores de desarrollo, CORS + `TrustedHost` + cabeceras de seguridad + HSTS, `/docs` cerrado en producción, uvicorn `--proxy-headers`. Runbook de rotación de credenciales y custodia de `.env` en `docs/engineering/devops.md`. Pendiente: ver Deuda técnica → Seguridad. |
| App Android (15+) | ⬜ | **Decidido (ADR-013): PWA/responsive, no app nativa** — Next.js + Tailwind + Base UI es 100% web, sin base de código separada; debe hablar con el hub local de sucursal igual que web y PC, ver ADR-009 |
| Arquitectura frontend (Tailwind, shadcn/ui, shell estilo Odoo) | ✅ spec 2026-07-27 | ADR-013 (revisado): Tailwind sobre los tokens de marca existentes (`tailwind.config.ts` → `var(--color-*)`, sin hex mágico); **shadcn/ui** (componentes copiados y editables, corre sobre Base UI, no Radix) para overlays/combobox/dialog y catálogo base — token set semántico + `--radius` único, mejor ajuste para editar color/forma por marca rápido que construir a mano; home de apps + sidebar por módulo estilo Odoo; grid y rutas filtrados por `permisos` de `GET /users/me` (ya existente, sin cambio de backend), guard real server-side en cada `layout.tsx` de módulo — el filtro del grid es solo UX. Sin librería de estado global (YAGNI). Playwright para e2e de flujos críticos: **2 casos del flujo del dinero en verde y en CI desde 2026-08-06**, ver Deuda técnica → Frontend. `docs/prompts/frontend.md` actualizado con las reglas técnicas. Sin implementación de código todavía. |
| Modo offline del PDV — hub local de sucursal | ✅ fase 1 2026-07-26 · fase 2 2026-07-27 | ADR-009: hub local dedicado por sucursal (misma imagen del backend, Postgres propio), los 3 clientes (web/Android/PC) le hablan siempre al hub por LAN. **Fase 1**: `DEPLOYMENT_MODE=hub` + validación de config, detector de conectividad, `GET /health/sync`, `docker-compose.hub.yml`. **Fase 2 — motor de sync**: ciclo que **empuja y después jala** (`src/core/sync/motor.py`, proceso `python -m src.core.sync.runner`); `id` client-generado en `crear_venta`/`registrar_pago`/`registrar_movimiento` (el cambio previo que pedía la fase 1, sin migración); endpoints dedicados `GET /sync/pull` + `POST /sync/push` (permisos `sync.leer`/`sync.empujar`, rol `hub_sucursal`) porque los públicos no alcanzaban (no traen `pin_hash` ni los campos del catálogo, no son incrementales, y el push necesita conservar quién vendió y el número de orden); contrato declarativo por módulo (`application/sincronizacion.py`, 28 recursos
tras sumar precios y lote/FEFO) que el motor solo ensambla; tabla `sync_watermark` por recurso y dirección; `/health/sync` con avance y último error por recurso; alta de la cuenta de servicio con `python -m src.seeders.hub`. El hub NO empuja movimientos de inventario (el listener de la nube los regenera; duplicaría el consumo). 24 casos en `tests/test_sync_motor.py` sincronizando dos bases reales. Pendiente: ver Deuda técnica. |
| Backups automáticos | ✅ 2026-07-26 | `python -m src.backups.backup`: dump `pg_dump --format=custom` → verificación del archivo (firma + tablas críticas) → restauración probada contra base desechable → copia a S3 (opcional) → purga con retención de 30 días que nunca borra la copia más reciente. **Diario** (antes se declaraba mensual e incremental). Cron del host, no Celery beat. Runbook en `docs/engineering/devops.md#backups`. Pendiente: alerta ante fallo, ver Deuda técnica. |
| Ciclo de caja completo | ✅ 2026-08-04 | ADR-025, migración `f3a1c62d90b4`. **No se cobra sin caja abierta** (contrato público `accounting.hay_caja_abierta`; el replay del hub es la única excepción); el monto de apertura y cierre **sale del conteo por denominación** (RN-POS-003/007) y la diferencia contra lo declarado se calcula sin bloquear la apertura (RN-POS-011); **cada relevo lo firma quien recibe con su PIN** (RN-MDP-002, permiso `accounting.caja_relevar`) y `custodia_efectivo` es máquina de estados real hasta `disponible`; **un cierre con faltante se reabre y se recuenta** dejando motivo y autorizador en `cierre_caja.correcciones` (RN-MDP-005), solo mientras el efectivo siga en el local. Nueva entidad `pos_tarjeta` (serie + código de comercio, RN-POS-010; emergencia = `sucursal_id` NULL, RN-POS-009) verificada al abrir. `tests/test_caja_ciclo.py` (17 casos). **Pantallas (2026-08-05)**: los diálogos del PDV se pusieron al día con este contrato —hablaban el anterior y devolvían 422 desde el día que se implementó— y contabilidad gana `/contabilidad/caja` con turnos cerrados, cadena de custodia firmada con PIN, reapertura e inventario de POS (`GET /accounting/cajas/turnos`). En el camino se cerró un agujero de integridad: `custodia` y `descuadre_atribucion` son enums y el schema los aceptaba como texto libre, dejando la fila ilegible al leerla. 24 casos. |
| Dashboard gerencial mínimo | ✅ 2026-07-26 | `GET /api/v1/dashboard/resumen` (`src/core/dashboard_router.py`, permiso `dashboard.leer`): ventas del día (cantidad+total), stock bajo mínimo, cajas abiertas — agregador en `core`, nunca importa dominio de otro módulo (ADR-012). Requirió construir dos huecos que no existían: `sales` no tenía ningún listado de ventas, `accounting` tenía los modelos de caja (`apertura_caja`/`cierre_caja`/`arqueo`, migrados desde 2026-07-20) sin capa de aplicación. **Slice mínimo de caja** (`accounting.application.caja`): abrir/cerrar/arquear con **reconciliación real** (el cierre calcula `monto_esperado` desde los pagos en efectivo reales, vía contrato público de `sales`, no un número tipeado sin verificar). Primer frontend real: login por PIN + pantalla de dashboard en Next.js. Fuera de esta fase, a propósito: RN-POS-009..013 completas, relevo autenticado por PIN, máquina de estados de `custodia_efectivo` — ver Deuda técnica. |
| Protección de datos personales (Ley 29733) | 🔶 ARCO técnico ✅ 2026-07-26 | `docs/security/proteccion-datos-personales.md`: qué datos trata el ERP y dónde viven (casi todo en `persona`, fuente única — RN-GEN-007; la excepción deliberada es `postulante`, ver 2026-08-01), derechos ARCO, plazos de conservación, medidas de seguridad ya vigentes (referenciadas, no reconstruidas), proceso de brecha. Cancelación implementada como **anonimización irreversible** de `persona`, no `DELETE` — `POST /api/v1/personas/{id}/anonimizar`, permiso dedicado `personas.anonimizar`, migración `dad43729501d` (RN-PER-007, ADR-011). Acceso/Rectificación ya existían (`GET`/`PATCH /personas/{id}`). Pendiente de **acción del usuario, no de código**: registro del banco de datos ante la ANPD, aviso de privacidad público, confirmar plazos de retención con el contador/abogado, jurisdicción de transferencia internacional. Pendiente técnico: ver Deuda técnica. |
| Contrato OpenAPI de la API | ✅ 2026-07-26 | `docs/architecture/openapi.json` exportado (`python -m src.core.openapi_export`) y verificado en CI — un endpoint que cambia sin regenerar el contrato falla el PR (ADR-010). `TAGS_METADATA` en `src/core/app.py` describe los 15 tags de la API; un tag nuevo sin descripción falla un test. De paso, corregidas dos afirmaciones falsas en `api-guidelines.md`: `idempotency_key` es campo del body, no header; las colecciones devuelven array plano, no `{items,total,page,page_size}` (nunca se implementó paginación). |
| CI/CD | 🔶 CI + entrega ✅ 2026-07-26 · e2e en CI 2026-08-06 | **Job `e2e`** (2026-08-06): el flujo del dinero de punta a punta sobre chromium, con `test-results/` como artefacto cuando falla — el único job que comprueba que cliente y servidor estén de acuerdo. `ci.yml` gana tres verificaciones que no existían: cabeza única de Alembic (una doble falla en el despliegue, no en el merge que la crea), construcción de la imagen **y arranque real del contenedor** contra `/health`, y `pip-audit` informativo. `release.yml` publica la imagen en GHCR en cada push a `main` (tags `v*` → versión exacta). `docker-compose.prod.yml` nuevo: el compose existente es solo desarrollo y desplegarlo publicaría esa configuración. Dockerfile con usuario sin privilegios y `HEALTHCHECK`. El **despliegue sigue manual** y documentado hasta que exista el VPS (ADR-008). |
| Chequeos de salud y alertas | ✅ 2026-07-26 | `src/core/health.py` + `health_router.py`: `/health` (liveness, sin dependencias), `/health/ready` (base de datos crítica → 503; Redis y cola degradan sin sacar de rotación) y `/health/backups` (503 pasadas 26 h — cubre el backup que nunca corrió, que no genera evento de error). El ERP expone estado; **un monitor externo alerta** (ADR-007): construir alertas dentro del servidor que se monitorea deja de avisar justo cuando ese servidor cae. Pendiente: contratar el monitor y dar de alta las sondas. |
| Observabilidad (métricas, trazas, logs centralizados) | 🔶 logs + errores ✅ 2026-07-26 | `src/core/logging_config.py`: JSON en producción, tres flujos (`app`/`seguridad`/`auditoria`) derivados del nombre del logger, `request_id` por request (respeta `X-Request-ID` entrante, sale en la cabecera y en el cuerpo del error 500), redacción de PIN/tokens/`Authorization`. `src/core/sentry.py`: reporte de errores en `api`, `worker` (señal `celeryd_init`) y `backups`; sirve para Sentry o GlitchTip autoalojado, no-op sin DSN. Pendiente: métricas, trazas y colector de logs — ver Deuda técnica. |
| UX: menús, buscadores, breadcrumbs, atajos, sidebars, dashboards | ⬜ | Definición pendiente con el usuario |
| UX: breadcrumb por ruta de usuario (no jerárquico) + tooltip de ayuda por campo de formulario | ✅ spec 2026-07-26 | `docs/product/ui-ux.md` — breadcrumb crece con la navegación (patrón Odoo), navegación jerárquica va por menús desplegables; todo campo de formulario lleva hover explicando término/formato. Solo especificado |
| UX: buscador contextual (nombre/insumo/exclusión, ranking por probabilidad) + dialog de venta sugerida (upsell) en carrito | ✅ spec 2026-07-26 | `docs/product/ui-ux.md` — buscador cruza `receta_item` para insumo/exclusión, lista ordenada por relevancia si no hay match único; al ir al carrito se sugieren productos de adición rápida, descartable. Solo especificado |
| Branding (paleta, tipografías, tokens CSS) | ✅ 2026-07-04 | Brandboard aplicado — `docs/product/ui-ux.md` |
| Skins multi-marca (PDV/Kiosk por marca vs **Provecho** en el resto — Majambo no tiene tema propio, decidido 2026-07-27), accesibilidad (2 paletas + 4 niveles de tamaño de fuente, catálogo definido 2026-07-27) y plataformas por módulo (táctil Android en PDV/Kiosk/KDS/Inventario, PC-first en el resto) | 🔶 spec 2026-07-27 | `docs/product/ui-ux.md` — solo especificado, falta implementar (resolver de tema por marca, preferencias de accesibilidad en perfil de usuario) |
| F2 — Arquitectura de frontend (documento maestro) | ✅ spec 2026-07-27 | `docs/product/frontend-architecture.md` — 31 secciones (tokens, componentes base/especializados, layout, navegación, estado, tablas, formularios, tiempo real, permisos visuales por rol, etc.) con estado por sección y los 6 puntos a cerrar antes de los diseños finales del alfa (layout general, componentes base, tablas, permisos visuales, arquitectura de carpetas, decisión de estado). Solo especificado — ver detalle en Deuda técnica → Frontend |

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
  (`data-model.md` §6).
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
- ⬜ **Cuando haya servidor** (parqueado 2026-08-05 por decisión del
  usuario). Nada de esto bloquea seguir desarrollando: son cosas que no se
  pueden hacer —ni probar de verdad— contra una máquina que todavía no
  existe. Estaban repartidas por seis secciones de este documento; acá
  quedan juntas para no descubrirlas de a una el día del despliegue.

  **Lo que solo puede hacer el usuario:**
  1. **Dominio real de producción** → fijar `ALLOWED_HOSTS` y
     `CORS_ORIGINS` en el `.env` del servidor. Sin esto, la validación de
     config aborta el arranque en `production`, que es a propósito.
  2. **Generar el `JWT_SECRET` real en el servidor**:
     `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Nunca
     el placeholder `change-me` — y nunca generado acá: un secreto que pasó
     por una conversación ya no es secreto.
  3. **Contratar el monitor externo** y dar de alta las tres sondas
     (`/health`, `/health/ready`, `/health/backups`). **Es lo único que no
     se puede resolver dentro del VPS** (ADR-007): un monitor que corre en
     la máquina que vigila deja de avisar justo cuando esa máquina cae.
  4. **Decidir dónde vive la copia on-premise** de los backups: hoy solo
     hay dump local + S3 opcional.

  **Lo que Claude escribe cuando exista la máquina** (no antes, porque sin
  la IP y el dominio reales serían plantillas que hay que reescribir):
  5. `nginx.conf` concreto: TLS, `proxy_pass`,
     `X-Forwarded-For`/`X-Forwarded-Proto` y `FORWARDED_ALLOW_IPS` con la IP
     real del proxy.
  6. **Cron del host** para las dos tareas que hoy existen y nadie ejecuta:
     `python -m src.backups.backup` (diario) y
     `python -m src.modules.rrhh.purga` (anonimiza postulantes vencidos —
     mientras no corra, el plazo de conservación que el aviso de privacidad
     promete no se aplica en la práctica).
  7. **Job de despliegue** en CI y **entorno de staging**: hoy se saltaría
     de CI a producción directo. Automatizar por SSH contra una máquina
     inexistente es escribir a ciegas (ADR-008).
  8. **Stack de observabilidad** (`docker-compose.observabilidad.yml`,
     GlitchTip + Loki/Alloy/Grafana) levantado en el mismo VPS.

## Deuda técnica pendiente (backlog)

Registro vivo de deuda técnica declarada al cerrar cada slice — para que no
se olvide. Marcar ✅ al resolverse en el slice indicado.

### Transversal
- **Un módulo se activa a mano en siete lugares** (2026-08-03). La estructura
  interna es replicable —los 8 módulos tienen la misma forma— pero no hay
  manifiesto por módulo ni autodescubrimiento: router y tag OpenAPI y
  `register()` de listeners en `src/core/app.py`, import en
  `models_registry.py`, migración, `PERMISOS`/`ROLES` en `src/seeders/seed.py`
  y entrada en `frontend/lib/modulos.ts`. Consecuencia: **borrar la carpeta de
  un módulo deja `core` sin compilar** — la promesa de "removible" es hoy del
  dominio, no del ensamblado. Mitigado, no resuelto:
  `docs/engineering/module-guide.md` documenta los siete pasos y
  `tests/test_arquitectura.py` exige tres de ellos (modelos en el registro,
  router montado, permisos de la API sembrados). Pendiente si algún día hay
  módulos opcionales de verdad: `MODULOS_ACTIVOS` en settings + carga por
  convención (`importlib`), que colapsa 1-4 en una línea; y `PERMISOS`
  declarados en el módulo en vez del seeder. No hacerlo antes de tener un
  caso real de módulo instalable/desinstalable — hoy los 8 están siempre
  encendidos.
- ✅ 2026-08-02 **`GET /personas` exigía `users.gestionar`, demasiado
  amplio para un lookup**: nuevo endpoint minimizado
  `GET /personas/buscar?q=` (permiso `personas.leer`, nuevo) que responde
  `PersonaBusquedaOut` — id/nombres/apellidos/numero_documento, nunca
  domicilio/teléfono/email/fecha de nacimiento — así que puede abrirse sin
  el permiso de administración completo. `personas.leer` sembrado en los
  roles `comprador` y `rrhh_admin`. `GET /personas` (ficha completa) sigue
  exigiendo `users.gestionar` sin cambios — el lookup es un recurso
  distinto, no un permiso más ancho sobre el mismo. RRHH/Trabajadores y
  Compras/Proveedores (natural) ya migraron a este endpoint.
- ✅ 2026-08-02 **CRUD de `unidad_medida`/`categoria_udm` (inventory) y
  `divisa` (gerencia)** — antes solo se editaban por seeder/migración
  (ADR-014 Addendum b). `POST/PATCH /inventory/unidades-medida[/{id}]`,
  `POST /inventory/categorias-udm` (permiso `inventory.gestionar_catalogo`)
  y `POST/PATCH /divisas[/{id}]` (permiso
  `gerencia.gestionar_parametros_empresa`, lectura abierta a cualquier
  autenticado — cualquier módulo que declare un monto necesita listar
  divisas válidas). `decimales` por unidad/divisa (RN-GER-010) ahora se
  corrige sin migración.
- ✅ 2026-08-02 **Cuatro endpoints de lectura que faltaban y bloqueaban
  pantallas de frontend**: `GET /api/v1/inventory/unidades-medida`
  (catálogo global, sin tenant — Inventario/Artículos lo necesita para el
  selector de `unidad_medida_id`), `GET /api/v1/purchases/ordenes-compra`
  (listado, no existía ni por error — solo había `GET .../{id}`),
  `GET /api/v1/almacenes` (nuevo en `users`, sin `require_permission` a
  propósito — catálogo de referencia, no dato sensible — pero sí escopado
  por tenant), `GET /api/v1/personas/buscar` (ver arriba).
- ✅ 2026-08-04 **Dos endpoints de lectura de RBAC que faltaban** y hacían
  inútil la pantalla de Usuarios: `GET /users/{id}/roles` —el token trae
  `roles` por nombre, sin id, así que desde la UI no había forma de
  desasignar— y `GET /roles/{id}/permisos`, porque asignar un rol sin poder
  ver qué habilita es exactamente el error que hay que evitar. Ambos con
  `users.gestionar`, sin permiso nuevo: son la misma administración que ya
  cubría crear y asignar.
- ✅ 2026-08-02 **Deriva de esquema del slice de contratación** (migración
  `e4a2f9c17b3d`): `postulante.estado` seguía en VARCHAR(10) con nueve
  estados de hasta 15 caracteres — `preseleccionado` fallaba en Postgres y
  pasaba en los tests porque SQLite ignora el largo. Además, `UNIQUE`
  duplicado en `convocatoria.token_publico`. Con esto el job `migraciones`
  de CI vuelve a verde: llevaba en rojo desde el 2026-08-01 y ningún PR
  podía pasar el check.
- ✅ **Contexto de tenant desde el JWT** (ADR-004): resuelto 2026-07-27 en
  `users`, `inventory`, `sales` y `kds`; completado 2026-08-01 en
  `purchases`, `production`, `accounting`, `rrhh` y el dashboard gerencial
  (`sync` ya lo derivaba de la cuenta de servicio). `src/core/tenant.py` +
  dependencia `get_tenant`; el `empresa_id`/`sucursal_id` sale de los
  claims, no del body, y un recurso ajeno responde 403 vía el handler de
  `FueraDeAlcance` del app factory. Tests en
  `tests/test_tenant_aislamiento.py`. Escape explícito documentado:
  superusuario (`*`) sin sucursal asignada puede indicar la empresa — sin
  eso el bootstrap del sistema sería imposible.
- ✅ 2026-08-01 `rrhh.postulante` **escopado por empresa**: se decidió con el
  usuario que la contratación es de la empresa, no del grupo (el grupo no
  tiene planilla). `postulante.empresa_id` obligatorio, heredado de la
  convocatoria cuando viene del formulario público.
- ✅ 2026-08-03 **Zona horaria del negocio** (`src/shared/fechas.py`,
  `settings.zona_horaria = "America/Lima"`). Se había anotado como "falla de
  los tests de conteos"; al revisarla resultó ser **de producción**: la
  aplicación derivaba "hoy" con `date.today()` —la zona del proceso, que en
  Docker es UTC— y la comparaba contra `created_at`/`cerrado_at`, que la base
  escribe en UTC. Pasadas las 19:00 hora Perú los dos relojes discrepaban un
  día y el calendario de conteo cíclico se corría entero. El mismo patrón
  estaba en otros 10 archivos —correlativo de venta por día, precio vigente,
  vencimiento de lotes, fecha de asiento contable, cierre de caja—, así que
  todos pasan por `fechas.hoy()`. Los 4 casos de `test_conteos` pasaron **sin
  tocar un solo test**, que es la prueba de que el error no estaba ahí.
  `tests/test_fechas_negocio.py` congela la regla, incluido un caso que falla
  si algún módulo vuelve a usar `date.today()`.
- ⬜ Los tests de `conteos` comparan contra `date.today()` local mientras
  `created_at` usa `CURRENT_TIMESTAMP` (UTC): corriendo después de las
  19:00 hora Perú fallan cuatro casos por un día de diferencia. Falla
  preexistente de zona horaria, no de la lógica de conteo.
- ✅ 2026-08-02 `users`: aplicar **restricciones JSONB** por permiso
  (ADR-022). `rules.ContextoPermiso`/`cumple_restricciones` (monto/estado/
  horario) + `UsuarioRepo.restricciones` + `check_permission(...,
  contexto=...)` (`api/deps.py`, retrocompatible — sin `contexto` se
  comporta igual que siempre; `require_permission` no cambia, no tiene
  acceso al body). Primer uso real: `sales.aplicar_descuento` acepta
  `monto_maximo` por rol, validado antes de aplicar el descuento. 15 tests
  nuevos (`tests/test_restricciones_permiso.py` + 3 casos HTTP en
  `test_sales.py`).
- ⬜ `users`: auth de **`agente_ia` por token** (hoy exige PIN como humano).
- ⬜ **Theming multi-marca + accesibilidad** (frontend, spec en
  `docs/product/ui-ux.md`): resolver de tema por marca/sucursal para
  PDV/Kiosk, preferencias de accesibilidad (paleta daltonismo, tamaño de
  fuente) persistidas en el perfil de `usuario`. Catálogo de paletas y
  niveles ya definido (2026-07-27) — sin implementar.
- ✅ 2026-08-02 **`parametro_empresa` con aprobación de Gerencia**
  (ADR-014 + Addendum, RN-GER-008/009): entidad transversal implementada
  (`src/shared/models/parametro_empresa.py`, migración `a71c9f4b2e60`).
  **El área propone desde su módulo, Gerencia acepta / rechaza / modifica**
  y recién ahí el valor llega al módulo. Lectura vía
  `src.shared.parametros.valor_vigente`. Permisos:
  `<modulo>.proponer_parametro` (uno por módulo) y
  `gerencia.gestionar_parametros_empresa`. Sigue sin existir un rol
  `gerente` explícito — hoy solo `admin` vía `*`. Falta que cada área
  proponga sus valores reales (ver "Pendientes de decisión") y el frontend
  de la bandeja.
- ✅ 2026-08-02 **`regla_aprobacion` retirada** (migración `b82d4c1f7a35`):
  sus umbrales vigentes se copiaron a `parametro_empresa` como
  `{"monto": ...}` ya aprobados; se borraron tabla, modelo, repo, los tres
  endpoints `/reglas-aprobacion` y el permiso
  `gerencia.gestionar_reglas_aprobacion`. `permiso_requerido` se descartó
  (era informativo). `umbral_vigente()` queda como envoltorio tipado
  (`Decimal`) sobre `parametro_empresa`. Una sola tabla de configuración
  por empresa, un solo flujo de aprobación.
- ✅ 2026-08-02 **RBAC por módulo al proponer parámetros**: un permiso por
  módulo (`<modulo>.proponer_parametro`, catálogo en
  `src/shared/parametros.py::MODULOS`) — Compras no propone parámetros de
  RRHH. `modulo` se valida como `Literal` en el schema (422 si es
  inventado) y `GET /parametros` sin filtro de `modulo` exige el permiso de
  Gerencia, porque los rangos salariales no son de lectura general.
- ✅ 2026-08-02 **`parametro_empresa.decision_gerencial_id` descartado**
  (previsto en ADR-014): el par propuesta/aprobación ya registra quién,
  qué, cuándo y con qué sustento (`motivo`) — la FK duplicaba ese rastro.
- ✅ 2026-08-02 **Toda magnitud lleva su unidad** (RN-GER-010, ADR-014
  Addendum b, migración `c93e5a7b1d42`): nueva entidad `divisa`
  (codigo/simbolo/**decimales**, sembrada con PEN), nueva columna
  `unidad_medida.decimales` (default 3) y `parametro_empresa.valor_display`
  con la magnitud formateada que lee Gerencia. `src/shared/magnitudes.py`
  valida y redondea con los decimales de la unidad (`ROUND_HALF_UP`, texto
  no float). Un monto sin `divisa` o una cantidad sin `unidad_medida_id`
  responden 422, al proponer y al modificar-y-aprobar.
- ✅ 2026-08-02 **CRUD de `divisa` y de `unidad_medida`** — resuelto el
  mismo día; ver la entrada de la sección *Transversal* de esta lista.
  `decimales` ya se corrige con un `PATCH`, sin migración.
  La frecuencia de conteo cíclico **salió de esta lista** (ADR-019,
  2026-08-01): es por categoría, no por empresa, y vive en
  `categoria.frecuencia_conteo`.
- ✅ 2026-08-03 **`decision_gerencial`** (acta de decisión gerencial,
  RN-GER-002, `data-model.md` §8c, migración `1805c0904c5c`): documentado
  desde el slice de Gerencia (2026-07-22), ahora con modelo en `shared`,
  repo, casos de uso y API — `POST/GET /api/v1/decisiones-gerenciales[/{id}]`,
  permisos nuevos `gerencia.decidir` y `gerencia.leer_decisiones` (el área
  ejecutora lee sin poder firmar, RN-GER-005; `leer_decisiones` sembrado en
  `supervisor`). `decidido_por_id` sale del token, no del cuerpo.
  `referencia_tipo`/`referencia_id` polimórficos sin FK: la decisión aplica
  a una OC escalada, una campaña sobre presupuesto o una sanción, y ningún
  módulo gana una FK hacia `shared`. `aprobado_con_condiciones` sin
  condiciones es 409 — un acta que no dice qué cumplir no sirve. 12 tests
  (`tests/test_decision_gerencial.py`). **Pendiente derivado:** ningún
  módulo la escribe todavía — `campana.aprobada_por` y la OC escalada
  siguen resolviendo por permiso, sin generar el acta (ver deuda de
  `marketing` más abajo).
- ✅ 2026-07-25 **Lock optimista en `persona`** (`VersionedMixin`,
  `src/core/model_base.py`): `PATCH /api/v1/personas/{id}` exige `version`
  vigente, 409 si está desactualizada. Aplicado solo a `persona` por
  ahora — extender a otras entidades compartidas si aparecen más choques
  reales de edición concurrente.
- ✅ 2026-08-04 **Contrato de lectura `purchases` ↔ `inventory.solicitud_insumos`**
  ("qué se pide más y desde dónde", insumo para negociar volumen con
  proveedores): mismo patrón de `sales.cliente`.
  `inventory/application/queries_publicas.py::solicitudes_resumen_para_negociacion`
  suma `cantidad_solicitada` por artículo y sucursal (`Almacen.sucursal_id`),
  excluye solicitudes `cancelada` —lo pedido cuenta como demanda real aunque
  no se haya aprobado ni despachado— y filtra por rango de fecha en zona de
  negocio (`fechas.zona()`, no UTC crudo). Expuesto en
  `GET /api/v1/inventory/solicitudes/resumen`, permiso nuevo
  `inventory.leer_solicitudes_externas` (sembrado en el rol `comprador`).
  `sucursal_id` sale `None` para almacenes sin sucursal (central,
  producción) — su demanda cuenta, solo no se atribuye a un local.

- ⬜ **La base de desarrollo está en la nube y eso hace lento todo**
  (medido 2026-08-05): `DATABASE_URL` apunta a Supabase y cada consulta
  cuesta **~130 ms de ida y vuelta** — `SELECT 1` tarda lo mismo que contar
  usuarios, así que es distancia, no trabajo de base. Todo request
  autenticado paga una consulta solo para resolver permisos, y una pantalla
  típica (4 llamadas × 3-6 consultas) se va a **2-3 segundos de puro viaje
  de red** antes de renderizar nada.
  El arreglo ya está escrito y comentado en `.env`: el Postgres local de
  `docker-compose` en el puerto 5433, que baja esos 130 ms a ~1. Queda como
  decisión del usuario porque implica correr las migraciones y el seeder
  contra esa base y trabajar con datos propios en vez de los compartidos.
  Supabase sigue siendo la correcta para verificar deriva de esquema y para
  lo que tenga que ver con datos reales.
  Mitigado en paralelo: `next dev --turbopack` (2026-08-05) saca la
  recompilación por ruta, que era el otro sumando.

### Seguridad (tras el endurecimiento base de 2026-07-26)
- ⬜ **El seeder no revoca** (encontrado 2026-08-05 al retirarle
  `purchases.aprobar` al rol `supervisor`): `ROLES` solo agrega los permisos
  que faltan, así que sacar uno del mapa no lo quita de ninguna base ya
  sembrada. Un permiso retirado por decisión de negocio sigue vigente en
  producción hasta que alguien lo borra a mano —que es lo que hubo que
  hacer acá—. Sincronizar en los dos sentidos es fácil; lo que hay que
  pensar antes es qué pasa con los permisos que un admin asignó a mano y no
  están en el mapa, porque una sincronización ingenua se los lleva puestos.
- ⬜ **Rate limit global**, no solo en auth: el resto de la API sigue sin
  límite. Se resuelve mejor en nginx/Caddy (`limit_req`) que en la
  aplicación — decidir al configurar el servidor de producción.
- ⬜ **Ventana deslizante en el rate limit**: hoy es ventana fija; un pico
  justo en el borde deja pasar hasta el doble del límite. Solo vale la pena
  si aparece abuso real.
- ⬜ **Rate limit por usuario además de por IP**: una IP compartida (la
  sucursal entera sale por la misma) puede agotar el límite de todos.
  Evaluar cuando haya varias cajas por local.
- ✅ 2026-08-04 **Content-Security-Policy**, en las dos puntas y con
  criterios distintos porque son dos cosas distintas:
  **API** (`src/core/app.py`) devuelve JSON y no tiene por qué cargar nada,
  así que va la más restrictiva posible —
  `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`
  — que además vuelve inerte cualquier respuesta que llegara a
  interpretarse como HTML. `/docs` queda exceptuado porque Swagger UI carga
  de un CDN; en producción no existe (`docs_url=None`), así que la
  excepción solo vive en desarrollo. **Frontend** (`frontend/middleware.ts`)
  usa **nonce por request** con `'strict-dynamic'`: Next inyecta scripts
  inline propios (hidratación, streaming RSC) y sin nonce habría que poner
  `'unsafe-inline'` en `script-src`, que es tanto como no tener CSP contra
  XSS. Concesión conocida y acotada: `style-src` sí lleva
  `'unsafe-inline'` (Next emite estilos críticos inline sin nonce) — el
  vector que importa, ejecución de script, queda cerrado igual.
  Verificado con `curl` contra ambos y sin violaciones en consola.
- ✅ 2026-08-04 **Escaneo de dependencias**: `.github/dependabot.yml` con
  los cuatro ecosistemas (pip, npm, github-actions, docker). Complementa a
  `pip-audit`, que solo *avisa* de una CVE publicada — Dependabot además
  abre el PR que la cierra. Agrupado por ecosistema para no recibir veinte
  PRs sueltos cada lunes; las de seguridad quedan fuera del grupo a
  propósito, para que lleguen solas y se vean. **Sigue pendiente**
  `pip-audit` bloqueante (hoy `|| true`) — ver la sección CI/CD.
- ⬜ **Verificación de firma en webhooks entrantes** (Izipay, Meta):
  documentada en `security.md`, sin implementar — llega con las
  integraciones.

### Dashboard y caja (tras la implementación de 2026-07-26 — ADR-012)
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
  (migración `d4e21b0c13d0`). 10 reportes en el catálogo.
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
- ⬜ **La exportación baja lo que se ve, no el dataset completo**: si
  contabilidad pide "todo el año en un archivo", 500 filas no alcanzan y
  ahí sí hace falta un endpoint que transmita en streaming — con su propio
  límite y probablemente asíncrono. No antes de que lo pidan.
- ✅ **`empresa_id` por query param en `/dashboard/resumen`** — **la entrada
  estaba obsoleta** (verificado 2026-08-05): ADR-004 se resolvió el
  2026-07-27 y el endpoint ya deriva la empresa del JWT vía
  `tenant.empresa(empresa_id)`. El query param sobrevive como el escape
  documentado del superusuario sin empresa asignada, igual que en el resto
  de la API — no como la vía normal.

### Protección de datos personales (tras la implementación de 2026-07-26 — ADR-011)
- ✅ 2026-08-01 **ARCO de postulante** (migración `b1d09e574c23`): los datos
  del candidato viven en `postulante`, no en `persona` —postular no mete a
  nadie en la fuente única de la empresa— así que
  `POST /personas/{id}/anonimizar` no lo alcanzaba. Ahora tiene los cuatro
  derechos: acceso (`GET /rrhh/postulantes/{id}`), rectificación (`PATCH`,
  409 sobre una ficha ya anonimizada), cancelación
  (`POST /rrhh/postulantes/{id}/anonimizar` — irreversible, reusa el permiso
  `personas.anonimizar` por ser la misma capacidad legal y el mismo
  custodio) y oposición (sigue siendo solo política, igual que en `persona`).
  Se anonimiza en vez de borrar aunque **nada referencie la fila**: el
  borrado se llevaría `motivo_descarte` y `canal_origen`, o sea la evidencia
  de por qué se descartó a alguien (Ley 26772) y la constancia de que la
  solicitud existió. Contratado → 409: sus datos ya están en `persona` bajo
  retención laboral y su ARCO se ejerce allá.
  **Purga por plazo**: `python -m src.modules.rrhh.purga` (cron del host,
  mismo criterio que backups) anonimiza lo vencido y nunca lo contratado; el
  plazo ahora se declara solo al crear la ficha
  (`RRHH_PLAZO_CONSERVACION_POSTULANTE_MESES`, 12 por defecto) porque un
  plazo NULL volvía la ficha inpurgable y el aviso de privacidad prometía
  algo que nadie aplicaba. Tests: `tests/test_rrhh_arco_postulante.py`.
- ⬜ **La purga no está dada de alta en ningún cron todavía** (ver
  *Cuando haya servidor*, punto 6): el comando
  existe y está probado, pero hasta que corra en el servidor el plazo sigue
  sin aplicarse en la práctica. Va junto con el cron de backups cuando exista
  el VPS.
- ⬜ **Borrado del `archivo` (CV) en `postulante`**: anonimizar la persona
  no toca el PDF en S3 — el módulo de archivos no tiene ni siquiera un
  flujo de borrado propio hoy.
- ⬜ **Purga de `audit_log`/logs por antigüedad**: sin retención automática
  todavía.
- ⬜ **Cifrado de backups en reposo**: el dump contiene PII en claro (ya
  declarado en la deuda de Backups, repetido acá por relevancia).
- ⬜ **Proceso y plantilla formal de notificación de brecha**: hoy es una
  lista de pasos en prosa, sin plantilla ni plazo confirmado con asesoría
  legal.
- ⬜ **`usuario.email` no se anonimiza** junto con `persona.email` — son
  campos independientes; si hace falta, es una acción aparte.
- ⬜ **Oposición** (cuarto derecho ARCO): sin contraparte técnica porque no
  existe procesamiento de marketing automatizado todavía. Construir cuando
  `marketing` tenga código real.
- ⬜ **Auto-servicio del titular**: hoy ARCO se ejerce a través del
  administrador (permiso `personas.anonimizar`/`users.gestionar`), no por
  un portal donde el propio titular pida su acceso/cancelación.

### Contrato de API (tras la implementación de 2026-07-26 — ADR-010)
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

### Modo offline del PDV (tras la fase 2 de 2026-07-27 — ADR-009)
- ✅ **Cambio previo a la fase 2** (2026-07-27): `crear_venta`,
  `registrar_pago` y `registrar_movimiento` aceptan `id` opcional
  client-generado; sin migración, como estaba previsto.
- ✅ **Motor de sync real** (2026-07-27): push→pull por ciclo, contrato
  declarativo por módulo, watermark por recurso, runner en su propio
  contenedor.
- ✅ **Cuenta de servicio por sucursal** (2026-07-27): rol `hub_sucursal`
  en el seeder y alta con `python -m src.seeders.hub`.
- ⬜ **Un ítem que la nube rechaza frena su recurso hasta que alguien lo
  mire**: es la política elegida (perder una venta en silencio es peor),
  pero hoy el único aviso es `ultimo_error` en `/health/sync`. Falta que el
  monitor externo alerte sobre eso, o una bandeja de ítems en conflicto.
- ⬜ **El borde del watermark se vuelve a bajar en cada ciclo**: el pull
  usa `campo_marca >= desde` para no perder nunca una fila escrita en el
  mismo instante que la marca, y `now()` en Postgres es el reloj de la
  transacción — así que un catálogo sembrado de una sola vez y nunca
  tocado viaja entero en cada ciclo. Con el tamaño de un catálogo de
  restaurante son cientos de KB por minuto; si el enlace de algún local lo
  siente, la salida es paginar por cursor compuesto `(marca, pk)`.
- ⬜ **Nada alerta si un hub deja de sincronizar**: `/health/sync` expone
  `ultimo_ok` por recurso, pero no hay nadie mirándolo. Mismo pendiente que
  la alerta de backups.
- ⬜ **`venta_item.estado_preparacion` no viaja a la nube**: el avance de
  KDS es local al local (y sus ítems no conservan `id` entre lados). Si
  alguna vez se quieren tiempos de cocina consolidados por grupo, hay que
  resolverlo aparte.
- ⬜ **`cliente` no se replica**: una venta offline es anónima o con datos
  escritos a mano; vender a cliente registrado exige estar en línea.
- ⬜ **`receta`/`receta_item` viajan sin filtro de tenant**: no tienen
  columna de empresa y acotarlas exigiría cruzar `producto_comercial`
  (dominio de `sales`) desde `inventory`. Aceptable mientras el grupo opere
  empresas que pueden verse entre sí; si eso cambia, `receta` necesita su
  columna de tenant antes que este sync.
- ⬜ **Descubrimiento del hub en la LAN** (mDNS `sucursal.local` o IP fija
  configurada por dispositivo): decisión de cliente, no resuelta en el
  backend.
- ⬜ **Redundancia del hub**: si el Raspberry Pi mismo se cae, la sucursal
  pierde el PDV entero — no hay hub de respaldo. Aceptado como riesgo por
  ahora (ADR-009); mitigación futura: imagen lista para flashear en un
  repuesto.
- ⬜ **Ningún frontend construido todavía**: web, Android y PC son proyectos
  aparte, ahora con contrato de arquitectura para construir contra él.
- ⬜ **Migraciones en cada hub**: un hub offline por días necesita
  `alembic upgrade head` local antes de sincronizar contra un esquema de
  nube ya migrado — mismo runbook que la nube (ADR-008), sin automatizar
  todavía por sucursal.

### CI/CD (tras la implementación de 2026-07-26)
- ⬜ **Job de despliegue** (ver *Cuando haya servidor*, punto 7): hoy el despliegue es manual y documentado. Se
  escribe cuando exista el VPS — automatizar por SSH contra una máquina que
  no existe da automatización no probada (ADR-008).
- ⬜ **Imagen de producción del frontend**: su `Dockerfile` sigue siendo de
  desarrollo (`npm run dev`), sin build de producción ni multi-stage. Por eso
  `release.yml` publica solo la imagen del backend.
- ⬜ **`pip-audit` bloqueante**: hoy es informativo (`|| true`) para que un
  aviso en una dependencia transitiva no frene un arreglo urgente en caja.
  Pasar a bloqueante cuando el equipo tenga rutina de revisión.
- ⬜ **Escaneo de la imagen** (Trivy/Grype) y firma del artefacto: el
  contenido de la imagen base no se audita todavía.
- ⬜ **Entorno de staging** (ver *Cuando haya servidor*, punto 7): hoy se saltaría de CI a producción directo.
- ⬜ **Migraciones con vuelta atrás probada**: `alembic downgrade` existe por
  archivo pero nunca se ejercita; un despliegue fallido no tiene camino de
  regreso verificado.

### Observabilidad y salud (tras las implementaciones de 2026-07-26)
- ✅ 2026-08-04 **GlitchTip autoalojado** (decisión del usuario sobre las
  dos que ADR-006 dejaba abiertas). Pesa que los datos no salgan del VPS: un
  reporte de error lleva rutas, parámetros y trazas, y aunque
  `_limpiar_evento` redacta PIN/tokens/cabeceras antes de enviar nada, lo
  que nunca sale de la máquina no hay que confiar en que esté bien
  redactado. Costo aceptado: un Postgres, un Redis y dos procesos más en el
  mismo VPS. Stack en `docker-compose.observabilidad.yml`, guía en
  `docs/engineering/observabilidad.md`.
  **Pendiente del usuario**: crear el proyecto en GlitchTip y pegar su DSN
  en `SENTRY_DSN` — sin ese paso el código sigue sin reportar nada.
- ✅ 2026-08-04 **Colector de logs: Loki + Alloy + Grafana** (decisión del
  usuario). El ERP ya emitía una línea de JSON por evento; lo que faltaba
  era que no muriera en `docker logs`. Alloy descubre los contenedores por
  el socket de Docker (montado **solo lectura**) y empuja a Loki; Grafana
  arranca con el datasource provisionado, porque sin él Loki es un agujero
  de solo escritura que nadie va a consultar por `curl` a las 2 a.m.
  `nivel`/`flujo`/`entorno` son etiquetas; `request_id` y `usuario_id`
  **no** —tienen tantos valores como requests y harían explotar el índice—
  y se filtran con LogQL, con el enlace ya armado en Grafana.
- ⬜ **Contratar el monitor externo** (ver *Cuando haya servidor*,
  punto 3) y darle de alta las tres sondas
  (`/health` 1 min, `/health/ready` 5 min, `/health/backups` 1 h). Sin
  monitor, los endpoints no alertan a nadie: el ERP expone, el monitor avisa
  (ADR-007). **Es lo único que no se puede resolver dentro del VPS**: un
  monitor que corre en la misma máquina no avisa cuando la máquina se cae.
- ⬜ **Métricas siguen faltando**: Loki guarda logs, no series temporales.
  Prometheus + node-exporter serían dos contenedores más; se difiere hasta
  que haya tráfico que justifique mirarlas.
- ⬜ **Métricas** (CPU, memoria, latencia, disponibilidad) y **trazas de
  rendimiento**: `SENTRY_TRACES_SAMPLE_RATE` está en 0. Subirlo cuando haya
  tráfico real que valga la pena perfilar.
- ✅ 2026-07-26 **Health check profundo**: `/health/ready` comprueba base de
  datos, Redis y profundidad de la cola; `/health/backups` comprueba
  frescura. Liveness quedó separado y sin dependencias a propósito.
- ✅ 2026-08-04 **Salud del worker**: ahora se pregunta, no se infiere.
  Una tarea de beat (`core.latido_worker`, cada minuto) escribe una clave en
  Redis con TTL de 3 min, y `/health/ready` la lee. Motivo del cambio: la
  cola solo delata al worker **cuando hay trabajo** — con cola vacía, un
  worker muerto y uno ocioso se ven idénticos, y en un restaurante la cola
  está vacía la mayor parte del día, justo cuando conviene enterarse
  temprano. Se usa TTL en vez de comparar timestamps para que la clave
  desaparezca sola y nadie tenga que decidir "cuán viejo es demasiado
  viejo". Degrada sin sacar de rotación: sin worker la caja sigue vendiendo,
  lo que se posterga es el comprobante y la alerta de cocina.
- ✅ **Handler de listener que revienta** — **la entrada estaba obsoleta**
  (verificado 2026-08-04): `EventBus._despachar` ya envuelve cada handler en
  `try/except` y registra con `log.exception`, así que un listener roto no
  arrastra al publicador ni impide que corran los demás. Se agregó el test
  que faltaba para congelarlo
  (`test_un_listener_que_revienta_no_arrastra_al_publicador`).
- ✅ 2026-08-04 **Flujo `auditoria` con contenido**: `AuditLogRepo.registrar`
  emite además al logger `provecho.auditoria`. No es duplicar por gusto: la
  tabla es el rastro legal (consultable, con su retención) y el log es lo
  que un colector externo puede vigilar en vivo — si alguien borrara la
  fila, la línea ya salió del proceso. **Solo metadatos**: `datos_antes`/
  `datos_despues` pueden traer PII (Ley 29733) y ese detalle se queda en la
  tabla.

### Backups (tras la implementación de 2026-07-26)
- ✅ 2026-07-26 **Alerta ante fallo**: el comando reporta a Sentry
  (`iniciar_sentry("backups")` + `reportar`) cuando falla, y
  `GET /health/backups` devuelve 503 cuando el último backup pasó las 26 h —
  que cubre el caso traicionero, el backup que **nunca corrió** y por eso no
  genera ningún evento de error. Falta solo dar de alta la sonda en el
  monitor externo (ver Observabilidad y salud).
- ⬜ **Restauración probada sin base desechable**: hoy `BACKUP_VERIFY_DATABASE_URL`
  es opcional y, si falta, solo se valida el archivo. Levantar la base de
  verificación en el servidor de producción para que la prueba real corra
  siempre (al menos semanal).
- ⬜ **Copia on-premise** (ver *Cuando haya servidor*, punto 4): `security.md` declara redundancia on-premise +
  nube; hoy están el disco del servidor y S3 (ambos "nube" si el servidor es
  un VPS). Falta definir dónde vive la copia dentro de la empresa.
- ⬜ **Backup de archivos de S3** (`archivo`): solo se respalda Postgres.
  Cuando el módulo de archivos exista, sus objetos también necesitan copia.
- ⬜ **Cifrado del dump en reposo**: el archivo contiene datos personales de
  trabajadores y clientes (Ley 29733). Hoy va en claro al disco y al bucket.

### Módulo inventory (slices siguientes)
- ✅ 2026-08-03 **Recetas editables** (ADR-023, migración `b6d1e83f47ac`):
  CRUD de receta e ítems, duplicar con "(copy)", escalar por factor y
  aritmética tecleada en la cantidad (`receta_item.expresion`), redondeada
  a los decimales de la UdM del insumo (RN-COM-024). `GET
  /inventory/unidades-medida` nuevo. Contrato público
  `queries_publicas.receta_resumen` — cierra la mitad `Receta` de la deuda
  "contrato público de inventory para `Articulo`/`Receta`" de la auditoría
  2026-08-01; `Articulo` sigue pendiente (`purchases` y `production` aún
  importan su ORM).
- ⬜ **Recetas sin tenant**: `receta` no tiene columna de empresa (por eso el
  hub la replica completa) y su CRUD no filtra por tenant. Con un solo
  grupo operando no se nota; con dos empresas que no deban verse entre sí,
  la columna va antes que cualquier otra cosa.
- ✅ 2026-07-25 **Listener `sales.venta_confirmada`** → consumo por receta
  (+merma % + empaque por modalidad) y `sales.venta_anulada` → reposición.
- ✅ 2026-07-25 **Listener `purchases.compra_recibida`** → suma stock en el
  almacén destino y recalcula `articulo.costo_promedio` (promedio
  ponderado solo contra el stock del almacén que recibe — deuda si
  `compra_directa` multi-almacén se vuelve frecuente, ver módulo purchases).
- ⬜ **Consumo omitido por configuración**: si falta almacén/SKU o el stock
  teórico no alcanza, el listener loguea y omite (la venta nunca se
  bloquea) — falta superficie de alerta/reporte de esas omisiones.
- ✅ 2026-08-01 **`reserva_stock` + `solicitud_insumos` + transferencias**
  (ADR-020, migración `d8b35f1ca207`): ciclo completo local pide →
  supervisor aprueba y reserva → central despacha → local recibe. La
  reserva es una promesa (no mueve `stock` ni genera movimiento) y
  `GET /stock` expone `cantidad`/`reservado`/`disponible` (RN-INV-009).
  Reservar bloquea, consumir no: una venta nunca se frena por una reserva.
  `transferencia_item` va por SKU **y lote** (el despacho reparte FEFO y el
  destino recibe los mismos lotes). Diferencias registradas, no corregidas
  (RN-INV-001/002). Transferencia lateral sucursal↔sucursal con la misma
  entidad. Permisos nuevos `solicitar_insumos`/`aprobar_solicitud`/
  `liberar_reserva`; estrena `transferir` y `recepcion`. 23 casos en
  `tests/test_transferencias.py`. Deuda que deja abierta:
  - ⬜ **Disponible negativo sin alerta**: es un estado alcanzable a
    propósito (promesa sin respaldo), pero hoy solo se ve consultando el
    stock. Falta que alguien lo mire.
  - ⬜ **Tipos de reserva sin productor**: `produccion` y `carrito` esperan
    a sus módulos; `merma` a `stock_merma` (RN-INV-012).
  - ⬜ **Transferencia sin vehículo ni tracking**: `vehiculo` no existe
    como entidad; quedó solo `transportista_id`. Faltan tracking GPS y
    tiempos de ruta/entrega que declara `data-model.md`.
  - ⬜ **Recepción de una sola pasada**: no hay recepción parcial que deje
    la transferencia en tránsito por el resto.
  - ⬜ **El ciclo no se replica al hub** (ADR-009): un local sin conexión
    no puede pedir ni recibir.
  - ⬜ **`inventory.transferencia_recibida` sin consumidor** en
    `accounting`.
  - ⬜ **Estado `en_picking` omitido** a propósito (no gobierna ninguna
    regla): si el negocio pide ver "el central ya empezó a armarlo",
    entra entonces.
- ✅ 2026-07-27 **Lote / FEFO** (ADR-015): `lote` + `stock_lote`, control
  opcional por artículo, reparto FEFO al registrar la salida, bloqueo de
  vencidos + `inventory.lote_vencido_detectado`, lote generado por
  recepción de compra y por producción. Deuda que deja abierta:
  - ⬜ **La reposición por venta anulada entra al lote del día**, no al
    lote del que salió: `sales.venta_anulada` no transporta los
    movimientos originales. Con volumen bajo la diferencia es contable,
    no física; si importa, el evento tiene que llevar el detalle.
  - ⬜ **Ventana de alerta de vencimiento por artículo**: hoy
    `por_vencer_dias` se pasa en cada consulta; el modelo de datos la
    quiere configurable por artículo.
  - ⬜ **`inventory.lote_vencido_detectado` sin consumidor y sin
    `responsable_id`**: `almacen` no tiene responsable modelado, así que
    el memorándum a RRHH (RN-VNC) no puede dirigirse a nadie.
  - ⬜ **Motivo del override de lote**: el README del módulo exige motivo
    al no tomar el lote sugerido; hoy el override es solo el `lote_id`
    explícito, sin motivo registrado.
  - ⬜ **`recepcion_item` no guarda el lote recibido**: el dato viaja en
    el evento hacia `inventory` pero el documento de recepción no lo
    conserva; si el listener falla, se pierde.
  - ⬜ **Salida sin lote que lo respalde**: si el total alcanza pero
    ningún lote cubre (stock previo al control de lote, o resto
    bloqueado), se registra un movimiento sin lote. Es deliberado
    (ADR-015) pero nadie revisa esos movimientos — falta reporte.
- ✅ 2026-08-01 **Conteo cíclico** (ADR-019, migración `c4e70a91d5b8`):
  `conteo` + `conteo_item`, con la periodicidad configurada **en la
  categoría** (`categoria.frecuencia_conteo`: diario/semanal/quincenal/
  mensual/semestral/anual, RN-INV-007) — no hay número universal. El
  calendario se deriva del último conteo cerrado más la frecuencia, sin
  tabla `programa_conteo`; un conteo general pone al día a todas las
  categorías del almacén. Stock esperado congelado al abrir, conteo a
  ciegas por defecto (permiso `inventory.ver_stock_esperado`), cierre que
  genera un `ajuste` pendiente por diferencia (`ajuste.conteo_id`) sin
  mover stock, y `inventory.conteo_vencido` a almacén y gerencia por lo
  que no se contó en su fecha (RN-INV-021). 22 casos en
  `tests/test_conteos.py`. Deuda que deja abierta:
  - ⬜ **Barrido de vencidos a demanda**: `POST /conteos/verificar-vencidos`
    no lo dispara nadie — el proyecto no tiene Celery beat, solo el worker
    de comprobantes. Mismo pendiente que `/lotes/bloquear-vencidos` y que
    `ComprobanteRepo.pendientes` (ver módulo sales).
  - ⬜ **`inventory.conteo_vencido` sin consumidor**: se publica, pero el
    "reporte a almacén y gerencia" hoy es leer
    `GET /conteos/programa`. Falta el adaptador de notificaciones — mismo
    bloqueo que `inventory.lote_vencido_detectado`.
  - ⬜ **Margen de error en `settings`**, no en `parametro_empresa`:
    `INVENTORY_MARGEN_AJUSTE_PCT` (2%) es global al deploy y debería ser
    por empresa (ADR-014). Mismo patrón provisional que
    `purchases_umbral_aprobacion_oc`.
  - ⬜ **El conteo no se replica al hub de sucursal** (ADR-009): contar sin
    conexión no está cubierto; el hub replica stock para vender, no para
    auditar el almacén.
  - ⬜ **`conteo` no tiene anulación expuesta**: el estado `anulado` existe
    en el modelo pero ningún endpoint lo usa, así que un conteo abierto
    por error bloquea la categoría hasta cerrarlo vacío.
  - ⬜ **Frecuencias en días fijos** (mensual = 30 días desde el último
    conteo, no el mismo día del mes). Si el negocio pide anclar al día del
    mes, cambia `rules.proxima_fecha_conteo` y nada más.
- ✅ 2026-08-05 **Guía de remisión** (ADR-027, migración `a4c8f21e6b09`,
  **aplicada a Supabase el 2026-08-05** junto con el seeder que suma
  `inventory.emitir_guia` al rol `almacenero`):
  `guia_remision` + `guia_remision_item` colgando de `transferencia`, porque
  lo que la guía declara es un traslado y el traslado es un hecho de
  inventario (RN-GDR-002). Las líneas **se derivan** de `transferencia_item`
  agrupadas por SKU —RN-TRP-002 exige que lo transportado coincida con lo
  declarado, y un formulario de ítems aparte es la forma de que no coincidan;
  el reparto FEFO por lote es control interno que SUNAT no declara. Se teclea
  solo lo que el sistema no puede saber: chofer, vehículo, peso bruto y fecha
  de inicio del viaje. Un traslado, una guía (`transferencia_id` único,
  emisión idempotente) y correlativo por `(empresa, serie)` calculado al
  emitir, no reservado antes —una guía reservada que no se emite deja un
  hueco en la numeración que también hay que justificar—. Envío a SUNAT
  asíncrono (`POST /despatch/send` vía Celery, `factiliza/guias.py` aparte
  del mapper de facturas porque una guía no tiene aritmética tributaria).
  Permiso nuevo `inventory.emitir_guia` en el rol `almacenero`. 14 tests
  (`tests/test_guia_remision.py`). **Sin entidad `vehiculo`**: sin flota, una
  tabla de vehículos sería un formulario que hay que llenar antes de emitir
  la primera guía.
- ⬜ **Devolución** (`devolucion`). Se cruza con la guía ya construida: una
  devolución al proveedor viaja con su propia guía de remisión.
- ⬜ **Guía de una venta con reparto**: hoy `guia_remision.transferencia_id`
  es obligatorio porque el único emisor es un traslado entre almacenes.
  Cuando exista reparto propio pasa a nullable — la migración es aditiva y
  el camino contrario no lo sería, por eso arranca estricta.
- ⬜ **Descarga de PDF/XML/CDR de la guía y anulación por comunicación de
  baja**: `FactilizaClient.descargar` apunta a `/invoice/...`; la guía
  necesita su ruta `/despatch/...`, y el payload de `/despatch/send` sigue
  **pendiente de verificación contra el sandbox real** de Factiliza — igual
  que estuvo la boleta antes de su primera emisión.
- ⬜ **`codigo_sunat` por unidad de medida**: hoy el mapper traduce con un
  diccionario de doce unidades y cae en `NIU` lo que no reconoce. El lugar
  correcto es una columna en `unidad_medida` editable desde Catálogo;
  mientras solo la guía lo necesite, una columna que alguien tiene que
  llenar a mano es más trabajo que el diccionario.
- ⬜ **La guía no se replica al hub**: la emite el almacén central, que
  está en la nube. Una sucursal offline que despache una transferencia
  lateral no puede emitir su guía hasta reconectar.
- ⬜ **Piso absoluto en el margen de ajuste** (deuda nueva 2026-08-05, de
  la propuesta de parámetros): `conteos.py` solo evalúa el porcentaje
  (`INVENTORY_MARGEN_AJUSTE_PCT`). Un 2 % sobre un conteo de S/ 30 en
  servilletas son 60 céntimos, así que cualquier diferencia real dispara
  `inventory.ajuste_fuera_margen` y la alerta se vuelve ruido que nadie
  mira — la peor falla posible en un control. El valor propuesto ya trae el
  piso (`{"porcentaje": 2, "piso": "20.00"}`); falta que el código lo lea.
- ⬜ **`stock_merma`** (subtipo reservado, no disponible) + reporte
  consolidado a `accounting`.
- ⬜ **Alerta `inventory.stock_bajo_minimo`** como evento (hoy solo flag
  `bajo_minimo` derivado en la consulta de stock).

### Módulo sales (slices siguientes)
- ✅ 2026-08-03 **Variantes y grupos de opciones** (ADR-023, migración
  `b6d1e83f47ac`): la variante es un `producto_comercial` hijo con receta y
  **precio completo** propios (RN-COM-022) — no un recargo sobre un precio
  base; el padre no se prepara, no admite precio y vender el padre es 409.
  `producto_opcion_grupo` con `minimo`/`maximo` decide qué grupo de extras
  obliga a elegir (RN-COM-023), validado al confirmar la venta y no solo en
  el PDV; el replay del hub se exceptúa. `GET /productos/{id}` (ficha
  completa) y `GET /marcas` nuevos; `GET /carta` devuelve `variantes[]` y el
  grupo de cada extra. Nombres normalizados a formato título en el servidor
  (`shared/texto.py`). Descartados por reemplazo: `modificador` y
  `variante_producto` del data-model.
- ✅ 2026-08-03 **Pantallas de artículos y de recetas**:
  `/inventario/articulos` (alta y edición de insumos, subrecetas, mercadería
  y empaques) y `/catalogo/recetas` (listado + ficha con "¿qué produce?").
  Cierran el hueco que hacía inusable el catálogo: no había forma de crear un
  insumo propio ni de ver una receta que no colgara de un producto. Con esto
  `/inventario` deja de ser un ícono que lleva a 404.
- ⬜ **7 íconos del home siguen llevando a 404** (`/produccion`, `/rrhh`,
  `/marketing`, `/gerencia`, `/usuarios`, `/contabilidad`, y el resto de
  `/inventario`): el grid lista los módulos que tienen **backend**, no los que
  tienen pantalla. O se construyen, o el grid deja de mostrar lo que no existe.
- ✅ 2026-08-03 **Catálogo separado del PDV en el frontend**: módulo propio
  (`/catalogo/productos`) con gate por permiso **exacto**
  `sales.gestionar_catalogo`, el mismo que la API exige para escribir. El
  filtro por prefijo del home (ADR-013) dejaba entrar a cualquiera con un
  permiso del área: un cajero leía el catálogo completo y recién al guardar
  chocaba con el 403. `puedeVerModulo()` resuelve prefijo vs permiso exacto
  en un solo lugar, usado por el grid y por el guard de `ModuloShell`.
- ⬜ **El backend del catálogo sigue en `sales`**: se evaluó mover
  `producto_comercial`/`precio` a un módulo `catalog` propio y se descartó —
  la autorización es por permiso, no por módulo, así que mover 5 tablas y sus
  FKs no habría ganado nada de seguridad. Revisar si algún día el catálogo
  necesita reglas de dominio que hoy no tiene.
- ⬜ **Ordenar y desarmar grupos de extras**: `orden` se teclea (ya editable
  en la ficha), pero no hay endpoint para quitar un extra de un grupo ni
  borrar un grupo. Alcanza para cargar el catálogo; molesta al mantenerlo.
- ✅ 2026-08-03 **Convertir un producto simple en uno con presentaciones**
  (`quitar_receta`) y **borrar presentaciones y recetas** con las dos
  negativas que importan: un producto ya vendido se descontinúa en vez de
  borrarse, y una receta en uso nombra al producto que la usa.
- ✅ 2026-07-28 **Slice PDV** (ADR-018, migración `d7e3b8c14f52`): cierra
  los cuatro huecos que destapó el diseño del punto de venta —
  `mesa` tipada por sucursal + `venta.mesa_id`/`comensales` con mapa de
  salón derivado (`GET /sales/mesas/mapa`, permiso `sales.gestionar_mesas`);
  `grupo_cobro` en `venta_item`/`pago`/`comprobante` para dividir la cuenta
  y emitir un comprobante por pagador (RN-COM-018);
  `comprobante.receptor_num_doc`/`receptor_nombre` para el DNI/RUC tecleado
  en caja, que decide boleta o factura sin exigir cliente registrado
  (RN-CPP-003); descuento manual de orden con motivo y autorizador
  (RN-COM-017, permiso `sales.aplicar_descuento` separado de
  `sales.cobrar`). Suma `POST /sales/clientes` (alta desde caja) y
  `GET /sales/ventas` (jornada por sucursal). Migración sin backfill y
  clave de idempotencia del grupo 1 intacta; 24 casos en
  `tests/test_pdv_slice.py`. **Pendiente derivado:**
  - ⬜ **Motor de promociones condicionales** por marca/sucursal — se
    activan solas si el pedido cumple reglas (ej. segunda pizza a mitad de
    precio si pide dos del mismo tamaño, en días vigentes, sobre el precio
    base de la más barata, sin incluir extras). Requiere entidad
    `promocion` con vigencia, condiciones de activación y base de cálculo.
    **No debe reutilizar `venta.descuento_*`**: esos campos son de un acto
    humano autorizado, con motivo y responsable; mezclarlos haría imposible
    auditar cuál descuento fue manual y cuál automático (ADR-018 →
    «Frontera explícita»).
  - ✅ 2026-08-02 **Alta de cliente/proveedor jurídico consulta Factiliza
    para el nombre/razón social** (`RENIEC`/`SUNAT` vía el mismo proveedor,
    ADR-005 ya lo dejaba previsto). `FactilizaClient.consultar_dni`/
    `consultar_ruc` (host propio, `FACTILIZA_CONSULTA_BASE_URL` —
    `api.factiliza.com`, **distinto** de `FACTILIZA_BASE_URL` que es solo
    emisión de comprobantes contra la QA `apife-qa.factiliza.com`; mismo
    token). `nombres_desde_dni`/`razon_social_desde_ruc`
    (`src/shared/integrations/factiliza/`) hacen fallback a lo tecleado si
    Factiliza no responde o no encuentra el documento — el alta nunca se
    bloquea por un proveedor externo caído. Cableado en
    `sales/application/clientes.py` (natural por DNI nuevo, jurídico por RUC
    nuevo) y `purchases/application/proveedores.py` (jurídico por RUC).
    Documento ya registrado en `persona` no vuelve a consultar. Probado con
    datos reales de QA: DNI 73632127 (Carlos Renato Rojas del Aguila) y RUC
    20610077782 (Servicios Rentaurant S.A.C., estado BAJA DE OFICIO — el
    consumo no valida `estado`/`condicion`, solo usa el nombre; bloquear por
    RUC no-HABIDO queda para cuando el negocio lo pida). 20 tests nuevos
    (`tests/test_factiliza_consulta.py` + casos en `test_pdv_slice.py`/
    `test_purchases.py`); `tests/conftest.py` nuevo, autouse que fuerza
    `factiliza_token=""` por test para que el suite nunca dependa de la red
    aunque el `.env` local tenga un token real.
  - ✅ 2026-07-28 **Cliente identificado por teléfono** (migración
    `e1c4a9d6b038`): `persona.numero_documento`/`tipo_documento` pasan a
    nullable, conservando el UNIQUE. Registrar a una persona natural exige
    teléfono, no DNI (RN-PTS-004); el documento se completa después
    (`PATCH /sales/clientes/{id}/documento`). RUC obligatorio solo para
    facturar a empresas. Sin documento o con `00000000` el cliente no
    cuenta como identificado y queda fuera de las promociones para
    clientes registrados (RN-PTS-005). Búsqueda por teléfono, documento o
    nombre (`GET /sales/clientes/buscar`, RN-PTS-006). Trabajador y usuario
    siguen exigiendo documento — validación en `users.application.admin`.
  - ⬜ **Reenvío del comprobante al cliente** (WhatsApp/correo) desde la
    pestaña de cobrados: falta el adaptador de notificaciones.
  - ⬜ `grupo_cobro` es un entero sin entidad detrás: nada impide un grupo 7
    sin grupos 1-6. Se valida en el caso de uso, no en el esquema.
  - ✅ 2026-07-28 **Frontend del PDV** en `frontend/app/pdv/`, contra los
    endpoints reales: apertura de caja con firma del encargado, catálogo con
    extras, ticket multi-borrador con selección por pulsación larga, mapa de
    mesas, cobrados del día y cobro con split de medios. Proxy
    `/api/proxy/[...ruta]` para que el token httpOnly no llegue al navegador.
    Verificado de punta a punta contra la API: venta con extras (94.00
    correcto), cobro dividido en dos cuentas con dos boletas y receptores
    distintos, y factura por RUC. **Pendiente de esta pantalla:** el botón
    "Más opciones" (descuento, anular líneas, precuenta, movimiento de
    efectivo) está cableado en backend pero no en la UI; y agregar productos
    a una orden ya enviada exige abrir una orden nueva — falta un endpoint
    que sume ítems a una `venta` existente.
- ✅ 2026-07-28 **Cierre del PDV para alfa** (ADR-018 §5-7, migraciones
  `f2a8c15e94d7` + `a3f0d29b6c81` + `b6d41e07af92`):
  - **Extras** (RN-COM-021): un extra es un `producto_comercial` con
    `es_extra=True` y receta propia; `producto_comercial_extra` define qué
    producto admite cuál y `venta_item.padre_venta_item_id` de qué línea
    cuelga. Hereda el grupo de cobro del padre y su consumo se multiplica
    por el plato. Reusa precio server-side, carta y descuento de inventario
    sin duplicar nada.
  - **Anular líneas enviadas** (RN-COM-020) y **precuenta** (RN-COM-019).
  - **Autorización de supervisor por PIN** (RN-AUD-005): cierra un hueco de
    seguridad — `autorizado_por` ya no viene del cuerpo del request.
  - **Movimiento de efectivo en caja** (RN-MDP-007) sumado al esperado del
    cierre.
  - **CI ejecuta las migraciones** contra Postgres real, ida y vuelta, más
    `alembic check`. Destapó y corrigió cuatro columnas `json` que debían
    ser `jsonb` y cinco índices/constraints declarados solo en la migración.
  - **Pendiente para después del alfa:** `variante_producto` (tamaños como
    variantes en vez de productos separados), mitad-y-mitad de pizza,
    `cuenta_puntos`/`puntos_movimiento` (canje real de puntos).
- ✅ 2026-07-27 **Precio server-side** (`lista_precio`/`precio`): el PDV
  ya no manda `precio_unitario` — `crear_venta` lo resuelve por
  marca+sucursal+canal+modalidad+fecha (RN-PRC-003/RN-MDC-003). Gana la
  lista promocional, luego la más específica, luego la de vigencia más
  reciente; al vencer la promoción el precio regular vuelve solo. Sin
  precio vigente la venta es 409 y el producto no sale en `GET /carta`.
  `precio` no tiene endpoint de edición: corregir = lista nueva
  (RN-PRC-005). Migración `d4b1f0a7c3e9` (cierra además la FK pendiente
  `medio_pago.lista_precio_credito_id`). El replay offline del hub
  conserva el precio cobrado (`VentaItemSyncIn`, ADR-009). Pendiente:
  `promocion` como entidad propia (material, guion, capacitación) y el
  cálculo de margen de contribución expuesto a Comercial (RN-CML-001).
- ✅ 2026-07-26 **Comprobante** (boleta/factura vía **Factiliza**) — venta
  `pagada` → `facturada`; series por `punto_venta`; correlativo por
  (empresa, serie); cola Celery con reintentos. Migración `b3d7f21ac094`.
- ✅ 2026-08-04 **Nota de crédito** (RN-CPP-009, migración `c2f7a91b4e08`,
  `sales/application/notas_credito.py`): total o **parcial por ítem**, con
  motivo del catálogo 09, contra un comprobante aceptado y una sola vez por
  documento. Serie propia por punto de venta (`serie_nc_boleta`/
  `serie_nc_factura`, nullable — sin ella no emite y lo dice, en vez de
  quemar un correlativo en la serie equivocada). Tres decisiones quedaron
  explícitas porque no tienen respuesta universal: **`repone_stock` lo
  declara quien acredita** (un plato devuelto en cocina rara vez devuelve el
  insumo, y corregir un RUC no toca inventario); **el motivo decide si la
  venta muere** —anulación y devolución la dan de baja, los de corrección de
  datos (02/03) no, solo liberan el comprobante para reemitir el corregido—;
  y **una nota rechazada por SUNAT no corrige nada**, queda registrada con
  su motivo. Las notas parciales sucesivas cuentan contra lo que queda por
  acreditar, no contra lo vendido. Permiso propio `sales.emitir_nota_credito`
  (supervisor). 14 tests.
- ✅ 2026-08-04 **Descarga de PDF / XML / CDR**
  (`GET /sales/comprobantes/{id}/descargar/{formato}`, permiso `sales.leer`):
  el PDF que se entrega al cliente y el **XML firmado** y el **CDR** que son
  el respaldo ante SUNAT. Se piden a Factiliza en el momento y **no se
  archivan**: su copia es la buena mientras el proveedor siga activo, y una
  nuestra podría quedar desincronizada sin ganar nada. Los bytes vuelven tal
  cual — reescribir un XML firmado lo invalida. Solo de un comprobante
  `aceptado`: antes no hay XML ni CDR que bajar.
- ✅ 2026-08-05 **Guía de remisión electrónica** (`/despatch/send`) — se
  construyó en **`inventory`**, no acá (ADR-027): lo que la guía declara es
  un traslado entre almacenes, no una venta, y `sales` no conoce almacenes.
  Que sea un documento de SUNAT no la vuelve de este módulo. Lo que sí es
  deuda de `sales` es la guía de una **venta con reparto a domicilio**, y
  espera a que exista reparto propio.
- ⬜ **Comprobante sin correlativo reservado**: si Factiliza rechaza, el
  correlativo queda consumido por una fila `rechazado`. SUNAT admite
  huecos, pero conviene revisar si el negocio quiere reusarlo.
- ⬜ **Barrido de comprobantes pendientes**: `ComprobanteRepo.pendientes`
  ya existe pero nadie la llama — falta el periódico (Celery beat) que
  recoja los que quedaron sin encolar (ej. emitidos cuando aún no había
  `FACTILIZA_TOKEN`).
- ⬜ **Webhook de pasarela** (Izipay): hoy el pago nace `confirmado`
  (PDV presencial); pago online requiere estado `pendiente` + confirmación.
- ✅ 2026-08-04 **Enlace con caja** (ADR-025): `registrar_pago` rechaza el
  cobro con 409 si el punto de venta no tiene turno abierto, preguntando
  por el contrato público `accounting.hay_caja_abierta`. Vale para todo
  medio de pago, no solo efectivo — el cierre cuadra también las tarjetas
  (RN-POS-004). Única excepción: el replay del push del hub.
- ⬜ **Consumo de subrecetas anidadas**: el listener expande un solo nivel
  de receta; una receta cuyo ítem es `subreceta` no explota recursivo aún.
- ⬜ Modificadores/variantes/combos, `central_pedidos` (pantalla y
  agregación), puntos/loyalty, kiosk UI. **UX definida** (2026-07-26,
  `docs/product/ui-ux.md`): seleccionar un producto comercial en PDV/Kiosk
  abre un dialog de personalización con sus modificadores admitidos
  (tamaño/combinación/extras/restas), que produce una `variante_producto`;
  orden fijo tamaño→combinación→extras→restas (RN-PRD-004). Falta definir
  si combo se configura en el mismo dialog o en uno propio, y el
  comportamiento en Kiosk (autoservicio) vs. PDV asistido.
- ⬜ **Buscador contextual de producto** (PDV/Kiosk/web): por nombre,
  por insumo/ingrediente (cruce `receta_item`) y por exclusión ("que no
  tenga X"); lista de resultados ordenada por relevancia cuando no hay
  match único. Ranking por **historial de uso/patrones detectados**
  (decidido 2026-07-26, no solo similitud de texto) — objetivo explícito:
  reducir fricción de búsqueda en versiones futuras a medida que aprende.
  UX especificada en `docs/product/ui-ux.md`, sin implementar — full-text
  search (`pg_trgm`/`tsvector`) como base, historial como señal encima.
- ⬜ **Dialog de venta sugerida (upsell) al ir al carrito**: productos
  complementarios de adición rápida, descartable sin bloquear el flujo.
  Criterio de sugerencia decidido (2026-07-26): complementos del producto
  elegido (ej. bebidas) + producto en promoción vigente. UX especificada
  en `docs/product/ui-ux.md`; falta definir cómo se configura la relación
  producto→complemento (fija vs. regla de venta cruzada).
- ⬜ **KDS tiempo real**: la pantalla (2026-08-03) refresca por polling
  cada 3 s; push por WebSocket/Redis pub-sub (Redis reservado para
  pantallas/colas/sesiones) sigue sin implementar.
- ⬜ **KDS sin reloj por pedido**: Odoo colorea la tarjeta al superar un
  umbral de espera; acá `GET /kds/pantallas/{id}/cola` no devuelve
  `fecha_orden`, así que no hay de dónde calcular el tiempo transcurrido.
  Va junto con "KDS tiempos" (abajo): agregar el timestamp al payload es
  el primer paso.
- ⬜ **KDS aviso de anulación**: si anulan un pedido ya en preparación, la
  tarjeta solo desaparece al refrescar — falta aviso explícito "ANULADO"
  (llega natural con el push de tiempo real).
- ⬜ **KDS impresión física**: la comanda sale como texto 32 cols; falta
  puente a impresora térmica (ESC/POS por red o agente local) y comanda
  automática al confirmar venta (hoy es bajo demanda).
- ⬜ **KDS tiempos**: alertas por pedido demorado (umbral por pantalla) y
  métricas de tiempo de preparación (base: `venta_item.updated_at`).
- 🔶 **Cumplimiento de pedido** (`PROC-OPE-002`, definido 2026-07-27):
  preparación + entrega implementadas (`POST /sales/ventas/{id}/entrega`
  → `sales.venta_entregada`). Falta la **rama delivery con trazabilidad**:
  entidad `entrega` especificada en `data-model.md` §6 (repartidor propio
  vs. plataforma externa, hora de salida, resultado `entregado`/`fallido`
  con motivo — RN-CUP-007/008, evidencia). Hoy una entrega fallida no se
  puede registrar: solo se marca el pedido entregado o no se marca nada.
- ⬜ **Plazo de espera de takeout no recogido** (RN-CUP-011): la regla
  existe, el plazo por sucursal no está configurado ni modelado.

### Módulo purchases (slices siguientes)
- ✅ 2026-07-25 **Migración Alembic** `4ff85f833b29` (proveedor,
  orden_compra, orden_compra_item, recepcion_compra, recepcion_item)
  aplicada a la BD dev (Supabase).
- ✅ 2026-07-25 **Conformidad de comprobante** (`application/comprobantes.py`,
  permiso `purchases.dar_conformidad`): crea el `comprobante` recibido
  (transversal, `shared`), lo liga a la última `recepcion_compra` de la OC
  y publica `purchases.comprobante_conforme` — `accounting` encola el pago
  (ver slice pago a proveedor abajo).
- ⬜ **`cotizacion`**: hoy toda OC tipo `insumo` emite sin cotización
  comparativa (el camino "simplificado" de proveedor preferente es el
  único implementado). Falta el flujo normal (proveedor regular) con
  cotización de respaldo.
- ⬜ **OC tipo `activo` + `requerimiento_activo`**: doble aprobación
  (área + gerencia) y mínimo 2 cotizaciones vinculadas antes de emitir.
  Hoy el tipo está rechazado explícitamente en la capa de aplicación.
- ⬜ **`compra_directa` + caja chica** (`caja_chica_compras`,
  `caja_chica_movimiento`, `rendicion_caja_chica`): compra sin OC a
  proveedor informal, con comprobante obligatorio y rendición semanal
  conciliada por `accounting`.
- ⬜ **`evaluacion_proveedor`** automática (cumplimiento de plazo,
  conformidad, variación de precio) recalculada en cada recepción.
- ⬜ **`orden_compra` no queda marcada como pagada**: `accounting.pago_ejecutado`
  se publica pero `purchases` no lo escucha; `orden_compra.estado` no tiene
  un valor para "pagada" todavía (RN-CMP-014 vive hoy solo del lado de
  `accounting`).
- ⬜ **Listener `inventory.devolucion_a_proveedor`**: gestionar reclamo/
  nota de crédito con el proveedor (bloqueado por `devolucion` en
  inventory, ver arriba).

### Módulo production (slices siguientes)
- ✅ 2026-07-25 **Migración Alembic** `f78501175fba` (orden_produccion,
  consumo_produccion_item, receta.articulo_id) aplicada a la BD dev
  (Supabase).
- ⬜ **`plan_produccion`** (cronograma fijo por tipo de receta/turno,
  evita contaminación cruzada): hoy toda orden se crea ad-hoc, sin plan.
- ⬜ **`checklist_inocuidad_turno`**: bioseguridad, superficies, equipos
  de frío (JSONB), indicio de plaga — bloquea la cocina si algo falla
  (RN-CDP-005), igual criterio que falla de frío en apertura de sucursal.
- ⬜ **`reporte_produccion`** consolidado automático al cierre de jornada
  (RN-DOC-010), visado por el jefe de cocina, no redactado a mano.
- ⬜ **`reporte_escalamiento` real**: hoy `production.no_conformidad_detectada`
  se publica pero nadie lo consume — falta la entidad (vive en `shared`)
  y quién la genera/resuelve.
- ⬜ **Merma → `accounting`**: `no_conforme_desechado` registra
  `merma_cantidad`/`merma_motivo` en la orden pero no dispara
  `inventory.merma_registrada` (bloqueado por `stock_merma`, deuda de
  inventory) — sin ese evento, el asiento contable de la merma no llega.
  Mismo bloqueo para el costeo por lote (ver siguiente punto).
  Reproceso (`no_conforme_reprocesado`) correctamente no genera merma ni
  asiento (RN-PRD — solo detalle en el reporte de escalamiento).
- 🔶 **Lote/trazabilidad del producto terminado**: desde 2026-07-27
  (ADR-015) el ingreso por `orden_completada` **sí** genera `lote`
  (`origen=produccion`, referencia a la orden) cuando el artículo controla
  lote. Falta la trazabilidad fina de fabricación —manipulador, envasador,
  línea, variables de proceso, QR (RN-PRD, RN-LOT-002/003)—: son campos
  del slice de `production`, que además debe mandar la fecha de
  vencimiento (hoy el lote producido nace sin ella, RN-VNC-001).
- ⬜ **Subrecetas anidadas**: una orden que consume otra subreceta (con su
  propia orden de producción) no está resuelta — hoy `registrar_consumo`
  espera insumos ya disponibles en stock.
- ⬜ **Conteo cíclico del almacén de producción**: mismo esquema que
  `inventory` en Almacén Central (bloqueado por conteo, deuda de
  inventory).
- ⬜ **Segregación quien crea vs. quien completa la orden**: hoy
  `production.crear`/`production.completar` son permisos distintos pero
  nada impide que el mismo usuario tenga ambos y haga las dos acciones
  (a diferencia de `inventory.ajuste`, que sí exige aprobador≠solicitante) —
  evaluar si el negocio lo requiere para producción.

### Módulo accounting (slices siguientes)
- ✅ 2026-07-25 **Pago a proveedor (PROC-CTB-003)**: migración `cbf904a9fc1b`
  (`movimiento_dinero`). `purchases.comprobante_conforme` encola
  (`registrar_pago`, idempotente por `comprobante_id` RN-CTB-008);
  `ejecutar_pago` exige `accounting.pago_gestionar` + umbral vía
  `parametro_empresa` (código `pago_umbral`, RN-CTB-005, `accounting.pago_aprobar`
  sobre el umbral) y genera asiento vía `regla_asiento`
  (`accounting.pago_ejecutado`); `rechazar_pago` cierra sin ejecutar.
  Eventos `accounting.pago_ejecutado`/`pago_requiere_aprobacion` ya se
  publican, pero sin consumidor todavía (ver pendiente de `purchases`
  arriba y de `users`/alertas abajo).
- ⬜ **Resto de eventos → asiento automático**: `sales.pago_registrado`,
  `sales.comprobante_emitido`, `purchases.caja_chica_rendida`,
  `inventory.transferencia_recibida`, `inventory.merma_registrada`,
  `inventory.ajuste_fuera_margen` están documentados en `events.md` pero
  sus módulos de origen aún no los publican en código (o, en el caso de
  `sales`, el evento real ya publicado se llama `sales.venta_pagada`, no
  `sales.pago_registrado` — desalineación de nombre entre spec y código,
  revisar). Cuando existan, agregar su extractor de monto/empresa en
  `accounting/application/listeners.py`.
- ⬜ **Detracción SPOT sin cuenta propia**: `movimiento_dinero.monto_detraccion`
  se calcula (RN-IMP-003) pero el asiento de `pago_ejecutado` no la
  desglosa — el debe/haber usa el monto total, no separa la cuenta de
  detracciones del banco/caja. Requiere ampliar `regla_asiento` a N líneas
  (hoy es siempre 1 debe/1 haber).
- ⬜ **`accounting.pago_ejecutado`/`pago_requiere_aprobacion` sin
  consumidor real**: `events.md` documenta que `purchases` marca la OC
  pagada y que `users` alerta a Gerencia — ninguno de los dos escucha
  todavía.
- ⬜ **`rechazar_pago` no libera el comprobante**: el único
  `movimiento_dinero` por `comprobante_id` (unique) queda en `rechazado`
  para siempre; reintentar el pago del mismo comprobante requiere
  intervención manual (borrar/reabrir la fila) — evaluar si el negocio
  necesita un caso de uso de reapertura.
- ✅ 2026-07-26 **Arqueo backend (PROC-CTB-005)**: `application/caja.py::registrar_arqueo`
  + `POST /accounting/arqueos`, publica `accounting.arqueo_registrado`
  (slice mínimo, ver ADR-012 — sin visado de Gerencia ni plantilla propia).
- ⬜ **Conciliación bancaria (PROC-CTB-004)**: sin modelo ni caso de uso.
  RN-CTB-006 (cierre de periodo exige conciliación visada) no se valida
  todavía — `cerrar_periodo` hoy no lo comprueba. Bloquea implementar
  rigurosamente RN-CTB-006.
- ✅ 2026-07-26 **Ciclo de caja → eventos**: `apertura_caja`/`cierre_caja`/
  `arqueo` (PROC-CTB-001/002/005) ya tienen capa de aplicación
  (`accounting.application.caja`, ver ADR-012) y publican
  `accounting.apertura_caja_registrada`/`cierre_caja_registrado`/
  `cierre_caja_irregular`/`arqueo_registrado`. **No generan asiento
  contable todavía** (sin listener que consuma esos eventos hacia
  `regla_asiento`) — eso sigue pendiente. Tampoco incluye RN-POS-009..013
  completas ni la máquina de estados de `custodia_efectivo` — ver Deuda
  técnica → Dashboard y caja.
- ⬜ **Activo fijo/depreciación y flujo de caja** (PROC-CTB-007/010,
  propuestos): sin modelar, dependen de que exista el módulo de activos.
- ⬜ **`declaracion_itan`**: entidad documentada en data-model §8, sin
  slice propio (depende del ciclo tributario anual, RN-IMP-006).
- ⬜ **`regla_asiento` de una sola línea debe/haber**: el mapeo actual
  genera exactamente 2 líneas por evento (una cuenta debe, una haber) —
  suficiente para provisión/recepción/venta simples; un asiento con más de
  2 líneas (ej. IGV desglosado) requiere asiento manual o ampliar el mapeo.

### Módulo rrhh (slice completo — deuda declarada)
- ✅ 2026-07-25 **Ciclo laboral completo**: `trabajador` (capa de aplicación
  que faltaba desde el slice de venta) + `contrato_laboral`, `postulante`,
  `socio`, `boleta_pago`, `liquidacion_bss`, `memorandum`, `amonestacion`,
  `acta`, `certificado_trabajo`, `solicitud_permiso`, `pacto_permanencia`,
  `asistencia`. Migración `9e1b6a4c7d23`.
- ⬜ **`contrato`/`solicitud` transversales**: `contrato_laboral` y
  `solicitud_permiso` se modelaron directo en `rrhh` (sin precedente de
  entidad genérica en código todavía) — mismo diferimiento que `purchases`
  hizo con `cotizacion`. Si otro módulo necesita `contrato`/`solicitud`
  genérico, extraer entidad transversal en `src/shared/` y migrar ambos.
- ⬜ **Eventos `rrhh.*` sin consumidor**: `trabajador_cesado`,
  `contrato_laboral_firmado`, `boleta_pago_emitida`, `liquidacion_bss_pagada`,
  `solicitud_permiso_aprobada`, `amonestacion_emitida` se publican pero
  nadie escucha todavía. Candidatos: `accounting` podría generar asiento al
  escuchar `boleta_pago_emitida`/`liquidacion_bss_pagada` (mismo patrón que
  `purchases.compra_recibida`); `users` podría desactivar el `usuario`
  ligado al escuchar `trabajador_cesado`.
- ⬜ **RN-RRHH-007 (visado de abogado) y RN-CTR-002 sin enforcement**: las
  cartas/actas se generan desde plantilla + datos del ERP, pero no hay
  entidad `plantilla` ni flag de "visado" — hoy es proceso manual fuera del
  ERP.
- ✅ 2026-08-01 **Convocatoria + tablero de contratación** (migración
  `a7f2c81e4b95`): `convocatoria` (borrador → publicada → cerrada) con
  RN-RRHH-013 aplicada en código —sin `perfil_puesto` no se publica—,
  formulario público de postulación por token (Google Forms + Apps Script,
  `POST /rrhh/postulaciones/{token}`, sin JWT, rate limit 20/h por IP),
  `postulante` con datos propios y `respuestas` JSONB (el candidato no entra
  a `persona` hasta contratar) y un solo tablero de 8 columnas + `descartado`
  para los 13 pasos de incorporación. Tests: `tests/test_rrhh_convocatoria.py`.
- ⬜ **Perfil de puesto sigue siendo documental**: `convocatoria.perfil_puesto`
  guarda el slug de `docs/rrhh/perfiles/`; no hay tabla `perfil_puesto` ni
  validación de que el slug exista. Vale la pena recién cuando los perfiles
  cambien seguido o los edite alguien que no toca el repo.
- ⬜ **Inducción sin checklist por paso**: los pasos 10-13 (inducción al grupo,
  uniforme, inducción al puesto, evaluación de prueba) son dos columnas del
  tablero (`inducido`, `confirmado`), no ítems con responsable y evidencia.
  Modelarlos aparte solo si la inducción empieza a fallar por pasos que nadie
  hizo.
- 🔶 **Pantallas de RRHH — contratación ✅ 2026-08-05, el resto no**:
  `/rrhh/contratacion` con las convocatorias (crear, publicar exigiendo
  perfil por RN-RRHH-013, cerrar) y **el tablero de las 8 etapas**: avance
  de a una columna, descarte con motivo obligatorio (Ley 26772) y
  contratación —que es donde nacen `persona` y `trabajador`—. Los
  descartados van plegados aparte: no son parte del flujo, pero esconderlos
  borraría la evidencia de por qué se descartó a alguien. La convocatoria
  seleccionada viaja en el query param para poder compartir la URL.
  Verificado en navegador de punta a punta: crear → publicar → dos
  postulaciones por el endpoint público → avanzar cuatro columnas →
  contratar (creó a Rosa Pinedo como Cocinera) → descartar con motivo.
  **Lo que sigue sin pantalla y por qué**: boletas, liquidaciones,
  memorándums, amonestaciones, actas, permisos, pactos y asistencia solo
  tienen `POST` y `GET /{id}` en la API — **no hay endpoint de listado**,
  así que no se pueden dibujar sin agregarlos primero. El legajo del
  trabajador es el slice que los junta, y necesita backend antes que
  frontend.
- ✅ 2026-08-05 **Listados del legajo de RRHH**: `application/legajo.py` +
  `GET /trabajadores/{id}/legajo` (contratos, amonestaciones, memorándums,
  certificados, permisos y pactos en **una** lectura),
  `GET /solicitudes-permiso` (bandeja de aprobación paginada, la que
  envejece primero) y `GET /asistencia` con rango. Un endpoint y no ocho: el
  file personal es un documento, no ocho. **La nómina exige
  `rrhh.nomina_gestionar`** — restricción nueva: `rrhh.leer` lo tiene el
  supervisor, y que una boleta ya fuera legible por su id no es razón para
  volverla navegable; `nomina_visible` dice cuándo no viajó. 7 tests
  (`tests/test_rrhh_legajo.py`).
- ⬜ **Sin pantalla del legajo**: los endpoints están, el frontend cubre
  contratación y trabajadores. Es el siguiente paso natural.
- ⬜ **Sin listados generales de disciplina y nómina**: `memorandum`,
  `amonestacion`, `acta`, `boleta_pago` y `liquidacion_bss` se listan **por
  trabajador**, no de corrido. Una bandeja "todas las amonestaciones del
  mes" o "las boletas del periodo" necesitaría su propio endpoint; hoy no
  hay quién la pida.
- ✅ 2026-08-05 **El tablero pasó al frontend**: `/rrhh/contratacion`
  dibuja las columnas que `GET /convocatorias/{id}/tablero` ya devolvía.
- ⬜ **Uniforme/EPP (RN-RRHH-014/015)** y **parentesco/relaciones
  (RN-RRHH-016/017)**: sin modelo — hoy son controles manuales/SOP.
- ⬜ **`boleta_pago`/`liquidacion_bss` sin cálculo automático de PLAME**: la
  API recibe `ingresos`/`descuentos`/montos ya calculados (por el contador
  externo) — no hay motor de cálculo de renta 5ta/ONP/AFP/EsSalud en el ERP.

### Módulo marketing (slice core — deuda declarada)
- ✅ 2026-08-01 **Slice core**: `campana` (brief → aprobada → en_curso →
  cerrada, RN-MKT-003), `pieza_contenido` (RN-MKT-001/002),
  `lead` con atribución a la venta, `implementacion_material_sucursal`
  (RN-MKT-005) y `encuesta_satisfaccion` (RN-COM-007). Migración
  `e9c3b7412a68`, 17 endpoints, `tests/test_marketing.py`.
- ⬜ **`campana.aprobada_por` apunta a `usuario`, no a `decision_gerencial`**:
  RN-GER-007 exige acta de Gerencia cuando el gasto sale del presupuesto
  anual o supera el límite, pero ni `presupuesto_anual` ni
  `decision_gerencial` existen como tablas. Hoy la aprobación es un permiso
  (`marketing.campana_aprobar`, que el rol `marketing` NO tiene) sin control
  contra presupuesto. Se cierra junto con el slice de Gerencia.
- ⬜ **`campana.objetivo_comercial_id` diferido**: enlaza campaña de impulso
  de venta con la meta comercial; `objetivo_comercial`/`meta_venta` no
  existen todavía (deuda del área Comercial).
- ⬜ **Contenido sin archivo adjunto ni calendario visual**: `pieza_contenido`
  guarda título/canal/fecha y métricas, no el arte. Cuando haga falta,
  colgar de `archivo` (`src/shared/`, ya existe) en vez de crear storage
  propio.
- ⬜ **`marketing.campana_lanzada` y `marketing.lead_generado` sin
  consumidor**: se publican pero nadie escucha (candidato natural: BI).
- ⬜ **Encuesta sin envío real ni expiración automática**: `POST /encuestas`
  crea la fila y publica el evento; mandar el WhatsApp/link es trabajo de un
  adaptador en `src/shared/integrations/` que todavía no existe, y
  `expirar_encuesta` es un endpoint manual, no un barrido programado.
- ⬜ **Evaluación de agencia (RN-MKT-006) sin modelo**: la decisión
  agencia-vs-interna se documenta fuera del ERP; formalizarla exige
  `contrato` transversal (misma deuda que `rrhh`).

### Frontend (F2 — arquitectura y UX, documento 2026-07-27, actualizado tras ADR-013)

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
- ⬜ **Login y PDV siguen sin migrar a shadcn**: el login conserva sus
  clases `.login-*` en `@layer components` y el PDV su CSS propio. Funcionan;
  se migran cuando se los toque, no antes.
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
  mismo día (ver Deuda técnica → Transversal) — sigue sin pantalla propia,
  se gestiona por API.
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
  Deuda que deja: son **dos** casos sobre una sola pantalla. El resto del
  ERP sigue sin prueba de pantalla, y el job tarda ~4 min porque levanta
  Next en modo desarrollo.
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
