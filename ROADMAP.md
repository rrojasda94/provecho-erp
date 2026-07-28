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
| Core (app factory, settings, db, event bus) | ✅ 2026-07-04 | Endpoint `/health` operativo |
| Modelado de base de datos completo (SQLAlchemy + Alembic) | 🔶 en curso 2026-07-25 | Bloque transversal + organización (11) + slice Venta núcleo (11) + slice Cobro/Comprobante/Caja (8) + slice auth/RBAC (7) + slice inventory core (3) — 40 tablas en total. BD de desarrollo corre en **Supabase** (Postgres gestionado, solo BD — sin su Auth/RLS, ver `docs/engineering/devops.md`); Docker local sigue disponible como alternativa. Resto por slice vertical. |
| Módulo `users` (auth JWT + PIN + RBAC) | ✅ 2026-07-25 | Slice auth+CRUD implementado: 7 tablas RBAC (`rol`, `permiso`, `usuario_rol`, `rol_permiso`, `usuario_sucursal`, `refresh_token`, `audit_log`) + lockout en `usuario`. Login/refresh(rotativo+detección de reuso)/logout/me + CRUD admin de usuarios/roles/permisos/asignaciones. Argon2id, JWT, `require_permission` deny por defecto. `docs/security/authorization.md`. Restricciones JSONB por permiso: pendientes de aplicar (hoy solo chequeo por código). |
| Migraciones Alembic iniciales | 🔶 en curso 2026-07-25 | 6 migraciones aplicadas a la BD dev (head `be914c92a94b`): transversal+org, slice Venta, cobro/caja, cliente opcional, slice auth/RBAC, slice inventory core (stock/movimiento/ajuste). |
| Seeders (admin / PIN 123456, org base) | ✅ 2026-07-27 | `src/seeders/seed.py` (idempotente, prohibido en prod): matriz de roles/permisos semilla, `admin`/PIN `123456` y la **organización real** del grupo — empresa Majambo EIRL (RUC 20450311520, Jr. Ramón Castilla 248 - Tarapoto, zona `amazonia_ley27037`), marca Charlie's Pizzas **licenciada** a la empresa (`licencia_marca`), sucursales `CH1` (Jr. Ramón Castilla 248) y `CH2` (Jr. Lamas 299) activas y alquiladas (RN-IMP-004), almacén central `WH1` (`sucursal_id` NULL). Requirió `almacen.direccion` (migración `e5a1c93b7d40`): el central no cuelga de ninguna sucursal y no había dónde guardar su ubicación. Correr: `python -m src.seeders.seed`. Diferido: almacenes de sucursal de CH1/CH2 (no pedidos; su mín./máx. por SKU depende de datos de operación inexistentes) y CRUD de organización por API — hoy empresa/sucursal/almacén solo se crean por seeder. |
| Módulo `inventory` | 🔶 slice 1 ✅ 2026-07-25 | Catálogo (CRUD artículos/categorías/SKUs), stock por almacén (vía `movimiento_inventario` inmutable) y ajuste con segregación (`solicitar_ajuste` ≠ `aprobar_ajuste`, aprobador ≠ solicitante). Migración `be914c92a94b`. Diferido: lote/FEFO, reservas, conteo, transferencias, devolución, guía remisión, listeners de eventos. |
| Módulo `purchases` | 🔶 slice core ✅ 2026-07-25 | CRUD de proveedores (natural liga a `persona`, jurídico con RUC propio) y ciclo de OC tipo `insumo` (crear → emitir → recibir → anular), con idempotencia y umbral de aprobación configurable. `purchases.compra_recibida` → inventory suma stock y recalcula `costo_promedio`. Conformidad de comprobante (`purchases.dar_conformidad`) registra el `comprobante` recibido y dispara `purchases.comprobante_conforme` → cola de pago en `accounting`. Migración `4ff85f833b29` aplicada. Diferido: ver Deuda técnica. |
| Módulo `sales` (PDV) | 🔶 slices 1-3 ✅ 2026-07-27 | Venta con correlativo+idempotencia → `sales.venta_confirmada` → inventory descuenta por receta (+merma+empaque); cobro con pagos parciales → `pagada`; anulación pre-pago repone stock; CRUD productos/medios de pago. **KDS** (slice 2): pantallas configurables por sucursal y categorías (`kds_pantalla`, migración `7672566bf189`), avance por ítem en `venta_item.estado_preparacion` (fuente única → todas las pantallas ven el avance real), tipos preparación/despacho, comanda imprimible con contador de reimpresiones, evento `sales.pedido_listo`, rol `cocinero`. Kiosk/Central de Pedidos = clientes del mismo contrato, no módulos. **Cumplimiento de pedido** (slice 3, 2026-07-27): `PROC-OPE-002` definido como UN proceso (área Operaciones) y su etapa de entrega implementada — `POST /sales/ventas/{id}/entrega` con permiso propio `sales.entregar_pedido` y rol `despachador`, idempotente, publica `sales.venta_entregada` (disparador de la encuesta de marketing, RN-COM-007). Diferido: ver Deuda técnica. |
| Persona CRUD + lock optimista + matriz de aprobaciones + contrato público | ✅ 2026-07-25 | `POST/GET/PATCH /api/v1/personas` (sin Delete); `persona.version` con lock optimista (409 si desactualizada); `regla_aprobacion` (nuevo, `src/shared/`) reemplaza el umbral fijo de `purchases` por empresa, admin en `/api/v1/reglas-aprobacion`; primer contrato público de lectura cross-módulo (`sales.cliente` para marketing/comercial, `GET /api/v1/sales/clientes`). Migración `af8a246e2c25`. Ver detalle abajo. |
| Módulo `accounting` | 🔶 slice core+tesorería ✅ 2026-07-25 | Libro contable núcleo: plan de cuentas (`cuenta_contable`), periodo (`periodo_contable`, abrir/cerrar), asiento manual (`asiento`/`asiento_linea`, cuadre RN-CTB-001, anulación por asiento inverso RN-CTB-002) y mapeo configurable evento→cuentas (`regla_asiento`) que alimenta la generación automática para 4 eventos operativos ya publicados en código (`purchases.oc_emitida`, `purchases.compra_recibida`, `sales.venta_confirmada`, `purchases.comprobante_conforme`). **Pago a proveedor** (PROC-CTB-003, `movimiento_dinero`): cola idempotente por comprobante (RN-CTB-008) → ejecutar con umbral configurable + permiso (RN-CTB-005) → asiento automático. Migraciones `5402d99333fa`+`cbf904a9fc1b` aplicadas. Diferido: ver Deuda técnica. |
| Producción (fabricación) | 🔶 slice core ✅ 2026-07-25 | Orden de producción ad-hoc (crear → registrar consumo → completar con resultado de control de calidad) y costeo automático. Construido antes de tiempo a pedido del usuario — primera cocina real sigue planeada 2027. `receta.articulo_id` nuevo liga receta↔subreceta. Diferido: ver Deuda técnica. |
| Solicitudes / picking / transporte | ⬜ | Módulos futuros `requests`, `logistics` |
| Módulo `rrhh` | ✅ slice completo 2026-07-25 | Ciclo laboral completo: `trabajador` (con capa de aplicación que faltaba) + 12 entidades de §8b — `contrato_laboral` (borrador→firmado→finalizado), `postulante` (RN-PER-004), `socio`, `boleta_pago`/`liquidacion_bss` (idempotentes, RN-RRHH-001/003), `memorandum`/`amonestacion`/`acta`/`certificado_trabajo` (RN-RRHH-002/004/007), `solicitud_permiso` (RN-RRHH-005), `pacto_permanencia` (reembolso proporcional, RN-RRHH-006), `asistencia` (RN-RRHH-009, bloqueada para locación de servicios RN-PER-002). Migración `9e1b6a4c7d23`. Diferido: ver Deuda técnica. |
| RRHH: procesos y plantillas (reclutamiento, contratación, inducción) | ✅ 2026-07-19 | `docs/rrhh/`, 13 SOPs, 9 plantillas — ver detalle abajo. |
| Compras: procesos y plantillas (proveedores, cotización, OC, recepción, pago, caja chica, activos) | ✅ 2026-07-19 | `docs/compras/`, 11 SOPs, 6 plantillas — ver detalle abajo. Módulo backend `purchases` actualizado conforme al flujo |
| Comercial: procesos y plantillas (precio/margen, promociones, mercado, metas, desempeño, capacitación) | ✅ 2026-07-19 | `docs/comercial/`, 9 SOPs, 5 plantillas — ver detalle abajo. Módulo backend `sales` ajustado (margen, vigencia de promoción) |
| Almacén-Logística: procesos y plantillas (conteo, vencimientos/merma, transporte/transferencias) | ✅ 2026-07-19 | `docs/almacen-logistica/`, 8 SOPs, 6 plantillas — ver detalle abajo. Módulo backend `inventory` ajustado (lote, merma, ajuste solicitar/aprobar) |
| Producción: procesos y plantillas (cronograma, calidad/no conformidad, inocuidad, inventario de cocina, soporte a I+D+i) | ✅ 2026-07-20 | `docs/produccion/`, 4 SOPs, 5 plantillas — ver detalle abajo. Spec a futuro: primera cocina de producción planeada 2027, hoy sin operación real. Módulo backend `production` — slice core implementado 2026-07-25 |
| Gerencia: gobierno + matriz de aprobaciones + presupuesto anual | ✅ 2026-07-22 | `docs/gerencia/`, política + perfil + 3 plantillas + 1 SOP (definición de presupuesto anual, PROC-GER-001) — ver detalle abajo. Área de autoridad/estrategia/control; sin módulo backend (RBAC + documentos) |
| Marketing: procesos y plantillas (marca/naming, contenido, campañas, material en sucursal, agencias) | ✅ 2026-07-22 | `docs/marketing/`, 6 SOPs, 4 plantillas — ver detalle abajo. Módulo backend `marketing` nuevo (spec técnica); PROC-MKT-001 registrado. Resuelve el pendiente "módulo marketing README/contrato propio" |
| Contabilidad: procesos y plantillas | ✅ 2026-07-24 | `docs/contabilidad/` (política + marco legal + perfil contador/tesorero), 3 SOPs nuevos (pago a proveedor PROC-CTB-003, conciliación bancaria PROC-CTB-004, arqueo sorpresa PROC-CTB-005), 4 plantillas — ver detalle abajo. Área = tesorería + finanzas + registro + auditoría interna en un solo responsable, supervisada por Gerencia (RN-CTB-004..009; control en dos niveles: Contabilidad audita a las operativas, Gerencia audita a Contabilidad). Quedan propuestos PROC-CTB-006..013 |
| Mantenimiento, Sistemas/TI como áreas propias | ⬜ | Definidas como áreas del negocio (posible tercerización); documentación pendiente, desactivadas por ahora |
| Supervisión, CRM, tesorería, activos, proyectos, BI, reportes | ⬜ | Módulos futuros |
| Integración de facturación electrónica (**Factiliza**) | 🔶 boleta/factura ✅ 2026-07-26 | **Reemplaza a Nubefact** (decisión del usuario). Adaptador en `src/shared/integrations/factiliza/`; cola Celery + servicio `worker`; migración `b3d7f21ac094`. Emite boleta/factura con IGV desglosado y exoneración de Amazonía (RN-IMP-001). Diferido: nota de crédito, PDF/XML/CDR, guía de remisión — ver Deuda técnica → sales. |
| Integración Izipay | ⬜ | Proveedor decidido (ADR-003) |
| Integraciones Google / Meta | ⬜ | |
| Agentes IA para pedidos | ⬜ | |
| Notificaciones | ⬜ | Celery + canales por definir |
| Auditoría (audit_log) | ⬜ | Especificada en data-model |
| Endurecimiento de producción (rate limit, secretos, HTTPS, cabeceras) | 🔶 base ✅ 2026-07-26 | Rate limit por IP en login/refresh (Redis, fail-open), validación de config que aborta el arranque en `production` con valores de desarrollo, CORS + `TrustedHost` + cabeceras de seguridad + HSTS, `/docs` cerrado en producción, uvicorn `--proxy-headers`. Runbook de rotación de credenciales y custodia de `.env` en `docs/engineering/devops.md`. Pendiente: ver Deuda técnica → Seguridad. |
| App Android (15+) | ⬜ | **Decidido (ADR-013): PWA/responsive, no app nativa** — Next.js + Tailwind + Base UI es 100% web, sin base de código separada; debe hablar con el hub local de sucursal igual que web y PC, ver ADR-009 |
| Arquitectura frontend (Tailwind, Base UI, shell estilo Odoo) | ✅ spec 2026-07-27 | ADR-013: Tailwind sobre los tokens de marca existentes (`tailwind.config.ts` → `var(--color-*)`, sin hex mágico); Base UI (no Radix, no kit estilizado) para overlays/combobox/dialog; home de apps + sidebar por módulo estilo Odoo; grid y rutas filtrados por `permisos` de `GET /users/me` (ya existente, sin cambio de backend), guard real server-side en cada `layout.tsx` de módulo — el filtro del grid es solo UX. Sin librería de estado global (YAGNI). Playwright para e2e de flujos críticos, hoy en cero. `docs/prompts/frontend.md` actualizado con las reglas técnicas. Sin implementación de código todavía. |
| Modo offline del PDV — hub local de sucursal | ✅ fase 1 2026-07-26 · fase 2 2026-07-27 | ADR-009: hub local dedicado por sucursal (misma imagen del backend, Postgres propio), los 3 clientes (web/Android/PC) le hablan siempre al hub por LAN. **Fase 1**: `DEPLOYMENT_MODE=hub` + validación de config, detector de conectividad, `GET /health/sync`, `docker-compose.hub.yml`. **Fase 2 — motor de sync**: ciclo que **empuja y después jala** (`src/core/sync/motor.py`, proceso `python -m src.core.sync.runner`); `id` client-generado en `crear_venta`/`registrar_pago`/`registrar_movimiento` (el cambio previo que pedía la fase 1, sin migración); endpoints dedicados `GET /sync/pull` + `POST /sync/push` (permisos `sync.leer`/`sync.empujar`, rol `hub_sucursal`) porque los públicos no alcanzaban (no traen `pin_hash` ni los campos del catálogo, no son incrementales, y el push necesita conservar quién vendió y el número de orden); contrato declarativo por módulo (`application/sincronizacion.py`, 24 recursos) que el motor solo ensambla; tabla `sync_watermark` por recurso y dirección; `/health/sync` con avance y último error por recurso; alta de la cuenta de servicio con `python -m src.seeders.hub`. El hub NO empuja movimientos de inventario (el listener de la nube los regenera; duplicaría el consumo). 24 casos en `tests/test_sync_motor.py` sincronizando dos bases reales. Pendiente: ver Deuda técnica. |
| Backups automáticos | ✅ 2026-07-26 | `python -m src.backups.backup`: dump `pg_dump --format=custom` → verificación del archivo (firma + tablas críticas) → restauración probada contra base desechable → copia a S3 (opcional) → purga con retención de 30 días que nunca borra la copia más reciente. **Diario** (antes se declaraba mensual e incremental). Cron del host, no Celery beat. Runbook en `docs/engineering/devops.md#backups`. Pendiente: alerta ante fallo, ver Deuda técnica. |
| Dashboard gerencial mínimo | ✅ 2026-07-26 | `GET /api/v1/dashboard/resumen` (`src/core/dashboard_router.py`, permiso `dashboard.leer`): ventas del día (cantidad+total), stock bajo mínimo, cajas abiertas — agregador en `core`, nunca importa dominio de otro módulo (ADR-012). Requirió construir dos huecos que no existían: `sales` no tenía ningún listado de ventas, `accounting` tenía los modelos de caja (`apertura_caja`/`cierre_caja`/`arqueo`, migrados desde 2026-07-20) sin capa de aplicación. **Slice mínimo de caja** (`accounting.application.caja`): abrir/cerrar/arquear con **reconciliación real** (el cierre calcula `monto_esperado` desde los pagos en efectivo reales, vía contrato público de `sales`, no un número tipeado sin verificar). Primer frontend real: login por PIN + pantalla de dashboard en Next.js. Fuera de esta fase, a propósito: RN-POS-009..013 completas, relevo autenticado por PIN, máquina de estados de `custodia_efectivo` — ver Deuda técnica. |
| Protección de datos personales (Ley 29733) | 🔶 ARCO técnico ✅ 2026-07-26 | `docs/security/proteccion-datos-personales.md`: qué datos trata el ERP y dónde viven (casi todo en `persona`, fuente única — RN-GEN-007), derechos ARCO, plazos de conservación, medidas de seguridad ya vigentes (referenciadas, no reconstruidas), proceso de brecha. Cancelación implementada como **anonimización irreversible** de `persona`, no `DELETE` — `POST /api/v1/personas/{id}/anonimizar`, permiso dedicado `personas.anonimizar`, migración `dad43729501d` (RN-PER-007, ADR-011). Acceso/Rectificación ya existían (`GET`/`PATCH /personas/{id}`). Pendiente de **acción del usuario, no de código**: registro del banco de datos ante la ANPD, aviso de privacidad público, confirmar plazos de retención con el contador/abogado, jurisdicción de transferencia internacional. Pendiente técnico: ver Deuda técnica. |
| Contrato OpenAPI de la API | ✅ 2026-07-26 | `docs/architecture/openapi.json` exportado (`python -m src.core.openapi_export`) y verificado en CI — un endpoint que cambia sin regenerar el contrato falla el PR (ADR-010). `TAGS_METADATA` en `src/core/app.py` describe los 15 tags de la API; un tag nuevo sin descripción falla un test. De paso, corregidas dos afirmaciones falsas en `api-guidelines.md`: `idempotency_key` es campo del body, no header; las colecciones devuelven array plano, no `{items,total,page,page_size}` (nunca se implementó paginación). |
| CI/CD | 🔶 CI + entrega ✅ 2026-07-26 | `ci.yml` gana tres verificaciones que no existían: cabeza única de Alembic (una doble falla en el despliegue, no en el merge que la crea), construcción de la imagen **y arranque real del contenedor** contra `/health`, y `pip-audit` informativo. `release.yml` publica la imagen en GHCR en cada push a `main` (tags `v*` → versión exacta). `docker-compose.prod.yml` nuevo: el compose existente es solo desarrollo y desplegarlo publicaría esa configuración. Dockerfile con usuario sin privilegios y `HEALTHCHECK`. El **despliegue sigue manual** y documentado hasta que exista el VPS (ADR-008). |
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
  (umbral de OC, margen de contribución mínimo, frecuencia de conteo,
  margen de error de ajuste, monto de caja chica, plazo de envío de
  comprobantes, rangos salariales): decidido con el usuario que **no son
  valores fijos** — se configuran en `parametro_empresa` por empresa, los
  gestiona Gerencia, y un cambio puede sustentarse en un acta
  (`decision_gerencial`) cuando amerite (no obligatorio para un ajuste
  rutinario). Ver ADR-014, `data-model.md` §8c, RN-GER-008 y
  `docs/gerencia/politica-gerencia.md#parámetros-operativos-configurables`.
  Lo que queda abierto por cada uno de los puntos de abajo ya **no es el
  mecanismo** (resuelto) sino que **Gerencia cargue el valor real** —
  trabajo de configuración/negocio, no bloquea código:
  - ⬜ Umbral de aprobación de OC en soles (`purchases/oc_umbral`, ya vive
    en `regla_aprobacion` — solo falta que Gerencia lo configure por
    empresa; valor semilla S/2000 mientras tanto). ¿Umbral separado para
    activos?
  - ⬜ Margen de contribución mínimo objetivo (`comercial/margen_minimo`).
  - ⬜ Esquema de incentivo/comisión de metas de venta (Comercial + RRHH +
    Gerencia, nunca retroactivo) — el valor numérico va en
    `parametro_empresa`; el diseño del esquema en sí sigue siendo decisión
    de negocio a definir con esas tres áreas.
  - ⬜ Frecuencia de conteo cíclico y de conteo general de Almacén Central
    (`inventory/frecuencia_conteo_<categoria>`).
  - ⬜ Margen de error de ajuste de inventario
    (`inventory/margen_error_ajuste`).
  - ⬜ Monto del fondo de caja chica de compras
    (`purchases/monto_caja_chica`) — el mecanismo de reposición ante
    faltante sigue siendo decisión de proceso aparte, no solo de valor.
  - ⬜ Plazo interno de envío de comprobantes al contador
    (`contabilidad/plazo_envio_comprobante`).
  - ⬜ Rangos salariales de los 7 perfiles de puesto
    (`rrhh/rango_salarial_<perfil>`).
  Quedan **fuera** de este mecanismo por ser decisión de rol, no de valor
  (siguen abiertas tal cual):
  - ⬜ Aprobador suplente de OC en ausencia del administrador.
  - ⬜ Quién autoriza ajustes de inventario (admin vs. supervisor de
    logística — rol aún no existe formalmente).
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
- ⬜ Entidades de datos de Comercial-estrategia (metas de venta,
  evaluación de desempeño comercial, plan de capacitación, hallazgos de
  mercado) y de RRHH-proceso (convocatoria, entrevista/evaluación,
  inducción, evaluación de periodo de prueba) — SOPs y plantillas ya
  existen, falta llevarlas a `data-model.md`.
- ⬜ BPMN de las áreas nuevas (RRHH, Compras, Comercial-estrategia,
  Almacén-Logística): enfoque vigente es **primero SOP, luego BPMN** —
  los BPMN se agregan por área cuando sus SOPs estén estables, y en ese
  momento se registran los PROC en el registro maestro.
- ⬜ BPMN pendientes ya declarados: contingencias de personal faltante
  (RN-RRHH-011) y tardanza/falta del encargado (RN-RRHH-010).
- ✅ 2026-07-27 Catálogo de paletas de accesibilidad y niveles de tamaño de
  fuente — propuesta técnica definida (dos paletas: Provecho estándar y
  un modo alto contraste/daltonismo inspirado en Okabe-Ito que cubre
  protanopía+deuteranopía; 4 niveles de tamaño de fuente vía
  `--font-scale`). `docs/product/ui-ux.md#catálogo-de-paletas-y-tamaños-de-fuente-propuesta-técnica-2026-07-27`.
  Sujeta a ajuste si aparece validación real con usuarios daltónicos/baja
  visión. Sin implementar todavía.
- ✅ 2026-07-27 Grupo Majambo **no tiene tema propio** — Provecho es el
  único tema fuera de PDV/Kiosk (`docs/product/ui-ux.md`).
- ⬜ **Pendiente del usuario para desplegar el endurecimiento de producción**
  (2026-07-26, ver ROADMAP → Deuda técnica → Seguridad): no bloquea seguir
  desarrollando, solo hace falta al desplegar de verdad.
  1. Dominio real de producción → fijar `ALLOWED_HOSTS` y `CORS_ORIGINS` en
     el `.env` del servidor.
  2. Generar el `JWT_SECRET` real: `python -c "import secrets;
     print(secrets.token_urlsafe(48))"` — nunca el placeholder `change-me`.
  3. Cuando exista el VPS: Claude escribe el `nginx.conf` concreto (TLS,
     `proxy_pass`, `X-Forwarded-For`/`X-Forwarded-Proto`,
     `FORWARDED_ALLOW_IPS` con la IP real del proxy).

## Deuda técnica pendiente (backlog)

Registro vivo de deuda técnica declarada al cerrar cada slice — para que no
se olvide. Marcar ✅ al resolverse en el slice indicado.

### Transversal
- ⬜ **Contexto de tenant desde el JWT** (ADR-004): hoy varios endpoints
  reciben `empresa_id` en el body (ej. catálogo de inventory). Derivarlo de
  los claims + validar alcance en cada query. Afecta a todo módulo nuevo.
- ⬜ `users`: aplicar **restricciones JSONB** por permiso (hoy autoriza solo
  por código, no por condición monto/estado/horario).
- ⬜ `users`: auth de **`agente_ia` por token** (hoy exige PIN como humano).
- ⬜ **Theming multi-marca + accesibilidad** (frontend, spec en
  `docs/product/ui-ux.md`): resolver de tema por marca/sucursal para
  PDV/Kiosk, preferencias de accesibilidad (paleta daltonismo, tamaño de
  fuente) persistidas en el perfil de `usuario`. Catálogo de paletas y
  niveles ya definido (2026-07-27) — sin implementar.
- ⬜ **`parametro_empresa`** (ADR-014, `data-model.md` §8c, RN-GER-008):
  entidad transversal para valores operativos configurables por empresa
  (rango salarial, frecuencia de conteo, margen de error de ajuste, monto
  de caja chica, plazos internos) con `valor` JSONB y
  `decision_gerencial_id` opcional como sustento. Sin modelo ni migración
  todavía — candidato natural para el primer uso real: rango salarial de
  RRHH. Permiso nuevo `gerencia.gestionar_parametros_empresa`.
- ⬜ **`decision_gerencial`** (materializa el acta de decisión gerencial,
  RN-GER-002, `data-model.md` §8c): documentado desde el slice de Gerencia
  (2026-07-22) pero **sin modelo ni migración en código todavía** —
  `parametro_empresa.decision_gerencial_id` depende de que esta entidad
  exista primero.
- ✅ 2026-07-25 **Lock optimista en `persona`** (`VersionedMixin`,
  `src/core/model_base.py`): `PATCH /api/v1/personas/{id}` exige `version`
  vigente, 409 si está desactualizada. Aplicado solo a `persona` por
  ahora — extender a otras entidades compartidas si aparecen más choques
  reales de edición concurrente.
- ⬜ **Contrato de lectura `purchases` ↔ `inventory.solicitud_insumos`**
  ("qué usuarios/sucursales piden más productos"): bloqueado hasta que
  `solicitud_insumos` exista en código (deuda de `inventory`, ver abajo).
  El patrón de contrato público ya está establecido (`sales.cliente`, ver
  `docs/architecture/events.md`) — replicar cuando `solicitud_insumos`
  se implemente.

### Seguridad (tras el endurecimiento base de 2026-07-26)
- ⬜ **Rate limit global**, no solo en auth: el resto de la API sigue sin
  límite. Se resuelve mejor en nginx/Caddy (`limit_req`) que en la
  aplicación — decidir al configurar el servidor de producción.
- ⬜ **Ventana deslizante en el rate limit**: hoy es ventana fija; un pico
  justo en el borde deja pasar hasta el doble del límite. Solo vale la pena
  si aparece abuso real.
- ⬜ **Rate limit por usuario además de por IP**: una IP compartida (la
  sucursal entera sale por la misma) puede agotar el límite de todos.
  Evaluar cuando haya varias cajas por local.
- ⬜ **Content-Security-Policy**: falta definirla junto con el frontend
  (hoy solo hay cabeceras que no dependen del contenido).
- ⬜ **Escaneo de dependencias** (`pip-audit`/Dependabot) en CI.
- ⬜ **Verificación de firma en webhooks entrantes** (Izipay, Meta):
  documentada en `security.md`, sin implementar — llega con las
  integraciones.

### Dashboard y caja (tras la implementación de 2026-07-26 — ADR-012)
- ⬜ **Hallazgo real de la verificación en navegador**: `src/seeders/seed.py`
  no crea ninguna `Sucursal` ni asigna `admin` a una — `build_claims`
  deriva `empresa_id` desde las sucursales del usuario, así que en una
  instalación recién sembrada el dashboard (y cualquier otra pantalla que
  dependa de `empresa_id` del JWT) falla con "sin empresa asignada" hasta
  que alguien asigna una sucursal a mano. No es un bug de esta fase — ya
  existía — pero recién se hizo visible al construir la primera pantalla
  que de verdad depende de ese claim. Corregirlo en el seeder base (crear
  al menos una sucursal semilla y asignar `admin`) queda pendiente.
- ⬜ **Ciclo de caja completo**: RN-POS-009 a RN-POS-013 (verificación de
  series de POS, denominaciones obligatorias por billete/moneda), relevo
  autenticado por ambas partes con PIN propio (hoy solo se registra
  `relevo_encargado_id`, sin exigir su sesión), `custodia_efectivo` como
  máquina de estados real (cajero→supervisor→contabilidad).
- ⬜ **Enlace caja↔venta**: no bloquea cobrar sin caja abierta — deuda ya
  declarada en el slice de `sales`, sigue sin resolverse.
- ⬜ **`rechazar_pago` / reapertura de cierre**: si un cierre queda
  `con_irregularidad` no hay flujo de corrección, solo el registro.
- ⬜ **`GET /ventas` genérico** (listado paginado con filtros): el
  dashboard resuelve su propio agregado (`resumen_ventas_del_dia`); un
  listado general de ventas para otros usos queda pendiente.
- ⬜ **Caché/paginación del agregador**: cada llamada a
  `/dashboard/resumen` recalcula todo en vivo — aceptable al volumen de hoy,
  revisar si empieza a pesar.
- ⬜ **Más indicadores**: el dashboard de hoy es mínimo (3 tarjetas). Serie
  de ventas por hora, ranking de productos, alertas de KDS demorado, etc.
  quedan para iteraciones futuras.
- ⬜ **`empresa_id` seguirá viniendo por query param** en `/dashboard/resumen`
  hasta que se resuelva ADR-004 (tenant desde el JWT).

### Protección de datos personales (tras la implementación de 2026-07-26 — ADR-011)
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
- ⬜ **Paginación real** (`{items, total, page, page_size}`): ningún
  endpoint de listado la implementa hoy — se documentó honestamente en vez
  de fingir. Construir cuando una colección lo justifique por volumen
  (candidatas: histórico de ventas si se expone, `audit_log`).
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
- ⬜ **Job de despliegue**: hoy el despliegue es manual y documentado. Se
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
- ⬜ **Entorno de staging**: hoy se saltaría de CI a producción directo.
- ⬜ **Migraciones con vuelta atrás probada**: `alembic downgrade` existe por
  archivo pero nunca se ejercita; un despliegue fallido no tiene camino de
  regreso verificado.

### Observabilidad y salud (tras las implementaciones de 2026-07-26)
- ⬜ **Elegir proveedor y cargar `SENTRY_DSN`**: el código está listo pero
  sin DSN no reporta nada. Decidir Sentry SaaS (plan gratis) vs GlitchTip
  autoalojado en el mismo VPS — el código es el mismo para ambos (ADR-006).
- ⬜ **Contratar el monitor externo** y darle de alta las tres sondas
  (`/health` 1 min, `/health/ready` 5 min, `/health/backups` 1 h). Sin
  monitor, los endpoints no alertan a nadie: el ERP expone, el monitor avisa
  (ADR-007).
- ⬜ **Colector de logs**: hoy el JSON sale a stdout y queda en `docker logs`
  / journald. Falta enviarlo a algún lado consultable (Loki, o el propio
  Sentry para el flujo de errores).
- ⬜ **Métricas** (CPU, memoria, latencia, disponibilidad) y **trazas de
  rendimiento**: `SENTRY_TRACES_SAMPLE_RATE` está en 0. Subirlo cuando haya
  tráfico real que valga la pena perfilar.
- ✅ 2026-07-26 **Health check profundo**: `/health/ready` comprueba base de
  datos, Redis y profundidad de la cola; `/health/backups` comprueba
  frescura. Liveness quedó separado y sin dependencias a propósito.
- ⬜ **Salud del worker**: se infiere de la cola (si crece, el worker murió),
  no se pregunta directo. Suficiente por ahora; un `celery inspect ping` es
  caro para un endpoint que se sondea cada minuto.
- ⬜ **Handler de listener que revienta**: `EventBus.publish` corre los
  handlers en línea; si uno lanza, arrastra al publicador (una venta podría
  fallar por un listener contable). Evaluar aislar cada handler y reportar
  el fallo sin tumbar la operación.
- ⬜ **Flujo `auditoria` sin usuarios**: el `audit_log` va a base de datos
  pero no emite al log estructurado; el flujo está definido y vacío.

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
- ⬜ **Copia on-premise**: `security.md` declara redundancia on-premise +
  nube; hoy están el disco del servidor y S3 (ambos "nube" si el servidor es
  un VPS). Falta definir dónde vive la copia dentro de la empresa.
- ⬜ **Backup de archivos de S3** (`archivo`): solo se respalda Postgres.
  Cuando el módulo de archivos exista, sus objetos también necesitan copia.
- ⬜ **Cifrado del dump en reposo**: el archivo contiene datos personales de
  trabajadores y clientes (Ley 29733). Hoy va en claro al disco y al bucket.

### Módulo inventory (slices siguientes)
- ✅ 2026-07-25 **Listener `sales.venta_confirmada`** → consumo por receta
  (+merma % + empaque por modalidad) y `sales.venta_anulada` → reposición.
- ✅ 2026-07-25 **Listener `purchases.compra_recibida`** → suma stock en el
  almacén destino y recalcula `articulo.costo_promedio` (promedio
  ponderado solo contra el stock del almacén que recibe — deuda si
  `compra_directa` multi-almacén se vuelve frecuente, ver módulo purchases).
- ⬜ **Consumo omitido por configuración**: si falta almacén/SKU o el stock
  teórico no alcanza, el listener loguea y omite (la venta nunca se
  bloquea) — falta superficie de alerta/reporte de esas omisiones.
- ⬜ **`reserva_stock`**: disponible = físico − reservas activas
  (carrito / solicitud / producción / merma), RN-INV-009.
- ⬜ **Lote / FEFO**: `lote` + `stock_lote`; picking sugiere lote por
  `fecha_vencimiento`; bloqueo de vencidos + evento
  `inventory.lote_vencido_detectado`. **El lote lo genera tanto la recepción
  de compra como la producción**: un SKU producido recibe su lote al
  fabricarse — coordinar con el módulo `production`.
- ⬜ **Conteo cíclico**: `conteo` + `conteo_item`; la diferencia genera un
  `ajuste`.
- ⬜ **Transferencias + `solicitud_insumos`**: solicitud → aprobación →
  picking → en tránsito → recepción; incluye transferencia lateral
  sucursal↔sucursal.
- ⬜ **Devolución** (`devolucion`) + **`guia_remision`**.
- ⬜ **`stock_merma`** (subtipo reservado, no disponible) + reporte
  consolidado a `accounting`.
- ⬜ **Alerta `inventory.stock_bajo_minimo`** como evento (hoy solo flag
  `bajo_minimo` derivado en la consulta de stock).

### Módulo sales (slices siguientes)
- ⬜ **Precio server-side** (`lista_precio`/`precio`/`promocion`): hoy el
  PDV manda `precio_unitario` en el request. RN-COM: el precio lo fija el
  sistema por sucursal/canal.
- ✅ 2026-07-26 **Comprobante** (boleta/factura vía **Factiliza**) — venta
  `pagada` → `facturada`; series por `punto_venta`; correlativo por
  (empresa, serie); cola Celery con reintentos. Migración `b3d7f21ac094`.
- ⬜ **Nota de crédito** (anulación post-pago): endpoint `/note/send` de
  Factiliza ya relevado (requiere `afectado_Tipo_Doc`/`afectado_Num_Doc` +
  `motivo_Cod` del catálogo 09). Bloqueado por la decisión de flujo de
  anulación post-pago, no por la integración.
- ⬜ **Descarga de PDF / XML / CDR** del comprobante emitido
  (`/invoice/pdf|xml|cdr`): hoy se guarda el `hash` y la respuesta cruda,
  pero el cliente no puede bajarse su representación impresa.
- ⬜ **Guía de remisión electrónica** (`/despatch-*` de Factiliza) —
  se cruza con `guia_remision`, deuda de `inventory`.
- ⬜ **Comprobante sin correlativo reservado**: si Factiliza rechaza, el
  correlativo queda consumido por una fila `rechazado`. SUNAT admite
  huecos, pero conviene revisar si el negocio quiere reusarlo.
- ⬜ **Barrido de comprobantes pendientes**: `ComprobanteRepo.pendientes`
  ya existe pero nadie la llama — falta el periódico (Celery beat) que
  recoja los que quedaron sin encolar (ej. emitidos cuando aún no había
  `FACTILIZA_TOKEN`).
- ⬜ **Webhook de pasarela** (Izipay): hoy el pago nace `confirmado`
  (PDV presencial); pago online requiere estado `pendiente` + confirmación.
- ⬜ **Enlace con caja** (`apertura_caja`/`cierre_caja` de accounting):
  validar que el punto de venta tenga caja abierta al cobrar.
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
- ⬜ **KDS tiempo real**: hoy el frontend refresca por polling; push por
  WebSocket/Redis pub-sub (Redis reservado para pantallas/colas/sesiones).
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
- ⬜ **Lote/trazabilidad del producto terminado**: el ingreso a stock por
  `orden_completada` no genera `lote` (bloqueado por lote/FEFO, deuda de
  inventory) — sin eso no hay manipulador/envasador/variables de proceso
  trazables por lote (RN-PRD).
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
  `regla_aprobacion` (código `pago_umbral`, RN-CTB-005, `accounting.pago_aprobar`
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
- ⬜ **Convocatoria/perfil de puesto sin modelar**: RN-RRHH-013 (no publicar
  convocatoria sin perfil aprobado) es hoy proceso documental
  (`docs/rrhh/perfiles/`), no hay tabla `convocatoria` — `postulante` nace
  suelto, sin FK a una convocatoria.
- ⬜ **Uniforme/EPP (RN-RRHH-014/015)** y **parentesco/relaciones
  (RN-RRHH-016/017)**: sin modelo — hoy son controles manuales/SOP.
- ⬜ **`boleta_pago`/`liquidacion_bss` sin cálculo automático de PLAME**: la
  API recibe `ingresos`/`descuentos`/montos ya calculados (por el contador
  externo) — no hay motor de cálculo de renta 5ta/ONP/AFP/EsSalud en el ERP.

### Frontend (F2 — arquitectura y UX, documento 2026-07-27, actualizado tras ADR-013)

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

Ninguna de las 5 está implementada en código todavía — son decisiones de
arquitectura, no trabajo hecho.

Queda **una sola prioridad abierta**:

- ⬜ **F2.11 Tablas**: elegir librería (candidata: TanStack Table) y
  alcance v1 (orden/filtro/búsqueda/paginación) vs. v2 (columnas
  congelar/mover/ocultar, selección + acciones masivas, scroll virtual,
  totales). Es el componente más usado de todo el ERP y ninguna tabla está
  construida todavía — ADR-013 resuelve overlays/interacción, no grillas
  de datos.

Todo lo demás (theming multi-marca, accesibilidad — catálogo ya definido,
tiempo real de KDS, i18n, hardware, testing — Playwright ya decidido por
ADR-013, observabilidad, printing, productividad, multitarea) tiene
decisión tomada, está correctamente diferido, o depende de un módulo
backend que todavía no llega a pantalla — no bloquea empezar a diseñar.

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
