# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added

- **Área Contabilidad** (2026-07-24): `docs/contabilidad/` (política de
  segregación de funciones/supervisión de Gerencia, marco legal tributario PE,
  perfil de contador/tesorero), 3 SOPs nuevos en
  `docs/diagrams/Procesos/Contabilidad/` (Tesorería: pago a proveedor
  PROC-CTB-003, conciliación bancaria PROC-CTB-004; Control: arqueo sorpresa
  PROC-CTB-005), 4 plantillas en `docs/templates/contabilidad/`. Reglas
  RN-CTB-004 a RN-CTB-009 (incluye auditoría interna: Contabilidad audita a las
  áreas operativas aguas arriba pero no a sí misma; su tesorería la audita
  Gerencia — modelo de control en dos niveles). Glosario: Tesorería, Finanzas,
  Flujo de caja, Conciliación bancaria, Arqueo, Auditoría interna, Orden de
  pago, Detracción, Activo No Corriente, Depreciación, Periodo contable.
  Nomenclatura: CAJ/TES/ACT confirmadas bajo Contabilidad. Eventos
  `accounting.pago_ejecutado`, `accounting.pago_requiere_aprobacion`,
  `accounting.arqueo_registrado`. Spec `src/modules/accounting/README.md`
  actualizada (tesorería/finanzas). Propuestos PROC-CTB-006..013 (reposición
  caja chica, flujo de caja, cierre de periodo, depósito, activo fijo, contador
  externo, auditoría de almacén, conciliación de facturas/comprobantes).
- **Área RRHH** (2026-07-19): `docs/rrhh/` (marco legal laboral REMYPE,
  perfiles de puesto), 13 SOPs en
  `docs/diagrams/Procesos/Recursos-Humanos/` (Reclutamiento, Contratación,
  Inducción), 9 plantillas en `docs/templates/rrhh/`. Reglas RN-RRHH-012 a
  RN-RRHH-014; RN-RRHH-005 corregida (15 días de vacaciones REMYPE).
- **Área Compras** (2026-07-19): `docs/compras/` (marco legal-tributario
  Amazonía/SPOT, perfil de encargado), 11 SOPs en
  `docs/diagrams/Procesos/Compras/` (Proveedores, Cotización-OC,
  Recepción-Pago, Caja-Chica, Activos-Equipamiento), 6 plantillas.
  Reglas RN-CMP-008 a RN-CMP-017. Spec `src/modules/purchases/README.md`
  actualizada (3 caminos de compra, caja chica, OC tipo activo, pago lo
  ejecuta accounting).
- **Área Comercial** (2026-07-19): `docs/comercial/` (política de
  precio/margen/promociones/metas, perfil de jefe comercial), 9 SOPs
  nuevos en `docs/diagrams/Procesos/Comercial/` (Estrategia-Mercado,
  Precios-Promociones, Metas-Desempeno), 5 plantillas. Reglas RN-CML-001
  a RN-CML-006; glosario: Margen de Contribución. Spec
  `src/modules/sales/README.md` actualizada (vigencia de promoción,
  margen de contribución, precio por nueva versión).
- **Área Almacén y Logística** (2026-07-19): `docs/almacen-logistica/`
  (política FEFO/FIFO, conteo/ajuste, perfiles de almacén y chofer),
  8 SOPs nuevos en `docs/diagrams/Procesos/Logistica-Almacen/`
  (Conteo-Auditoria, Vencimientos-Mermas, Transporte-Transferencias),
  6 plantillas. Spec `src/modules/inventory/README.md` actualizada
  (lote, merma, ajuste solicitar/aprobar, transferencia lateral).
- **Área Producción** (2026-07-20, spec a futuro — primera cocina de
  producción planeada 2027): `docs/produccion/` (política de cronograma,
  calidad/no conformidad, inocuidad, inventario de cocina, soporte a
  I+D+i; perfiles de jefe de cocina y cocinero), 4 SOPs nuevos en
  `docs/diagrams/Procesos/Produccion/` (Planificacion, Calidad-Inocuidad,
  Inventario-Cocina, Soporte-IDI), 5 plantillas en
  `docs/templates/produccion/`. Reglas RN-PRD-011 a RN-PRD-017; entidad
  `plan_produccion` nueva, `orden_produccion`/`reporte_escalamiento`
  ampliadas. Nuevo módulo `src/modules/production/README.md` (spec
  técnica, sin implementar) y evento
  `production.no_conformidad_detectada`.
- **Producción — costeo, desperdicio e inocuidad** (2026-07-20, mismo
  día): tabla de desperdicio por insumo/tipo/peso en `orden-produccion.md`;
  costeo real automático (insumos + mano de obra, RN-PRD-018); reporte de
  conteo de cocina pasa a autogenerado, el jefe de cocina solo visa;
  verificación de temperatura de equipos de frío con alerta automática a
  Gerencia (RN-CDP-005). Nuevas entidades `consumo_produccion_item` y
  `checklist_inocuidad_turno`; evento `production.equipo_frio_fuera_rango`.
- **Área Gerencia** (2026-07-22, versión ligera — autoridad/estrategia/
  control, sin módulo backend): `docs/gerencia/` (política de gobierno
  corporativo + matriz de aprobaciones como fuente única de umbrales,
  perfil de Gerente General), 2 plantillas en `docs/templates/gerencia/`
  (acta de decisión gerencial, evaluación de nuevo mercado/marca). Reglas
  RN-GER-001 a RN-GER-006; entidad transversal `decision_gerencial`
  (`data-model.md` §8c); glosario: Gerente General, Matriz de
  aprobaciones, Acta de decisión gerencial. Sin PROC ni evento ni módulo
  (la facultad de aprobar es RBAC, no una tabla).
- **Área Marketing** (2026-07-22): `docs/marketing/` (política de uso de
  marca/contenido/campañas, perfil de jefe de Marketing), 6 SOPs en
  `docs/diagrams/Procesos/Marketing/` (Marca-Contenido, Campanas,
  Proveedores-Agencias), 4 plantillas. Reglas RN-MKT-001 a RN-MKT-007;
  entidades `campana`, `pieza_contenido`, `lead`,
  `implementacion_material_sucursal` (`data-model.md` §8d); eventos
  `marketing.campana_lanzada`, `marketing.lead_generado`; PROC-MKT-001
  (Campaña de marketing, Borrador). Módulo `src/modules/marketing/README.md`
  (spec técnica). Glosario: Lead, Campaña, Naming, Jefe de Marketing.
  Frontera: Marketing atrae leads, Comercial cierra.
- **Presupuesto anual (Gerencia)** (2026-07-22): RN-GER-007, PROC-GER-001
  (reunión anual donde cada área presenta propuesta y Gerencia designa
  presupuesto + límite de gasto autónomo), SOP `definicion-presupuesto-anual.md`,
  plantilla `propuesta-presupuesto-anual.md`, fila en la matriz de
  aprobaciones. Ajuste Marketing: RN-MKT-001 (Marketing gestiona las
  marcas sin burocracia extra), RN-MKT-006 (agencias las evalúa Marketing
  y valida Gerencia, no pasan por Compras; el material sí).
- **Reglas de conducta laboral** (2026-07-22): RN-RRHH-015 (uniforme
  completo/limpio/presentable en jornada), RN-RRHH-016 (no contratar
  parientes de 1.er/2.º grado), RN-RRHH-017 (no relaciones sentimentales
  en el mismo centro ni con subordinación directa), RN-RRHH-018 (no usar
  conocimiento ni recursos de la empresa para terceros/beneficio personal).
- ADR-004: aislamiento de tenant por filtro de aplicación con
  `empresa_id` obligatorio + tests (RLS de Postgres como refuerzo futuro).
- Catálogo de eventos completado con los eventos ya declarados en las
  specs de módulos: `inventory.merma_registrada`,
  `inventory.devolucion_a_proveedor`, `inventory.ajuste_fuera_margen`,
  `inventory.lote_vencido_detectado` (nuevo — lote vencido hallado
  disponible notifica y dispara memorándum), `purchases.comprobante_conforme`,
  `purchases.caja_chica_rendida`, `purchases.evaluacion_proveedor_actualizada`,
  `users.sesion_iniciada`, `accounting.asiento_generado`,
  `accounting.periodo_cerrado` (`docs/architecture/events.md`).
- Modelo de datos: entidades `plantilla`, `flota`, `combo`/`combo_item`,
  `stock_lote` (stock por lote — hace implementable FEFO/FIFO),
  `ajuste`, `apertura_caja`, `cierre_caja`, `arqueo`,
  `reporte_escalamiento` (definición mínima, por validar), y bloque de
  Compras (`caja_chica_compras`, `caja_chica_movimiento`,
  `compra_directa`, `rendicion_caja_chica`, `evaluacion_proveedor`,
  `requerimiento_activo`); `articulo.tipo` gana `suministro` (consumo
  interno: limpieza, oficina) y queda declarado como enum extensible.
- Glosario: "Horario laboral" y "Horario de atención" (términos oficiales,
  reemplazan "horario de trabajo").
- Repositorio git inicializado (commit inicial con el estado
  pre-correcciones para trazabilidad).
- Modelado de BD — bloque transversal + organización (11 tablas):
  `persona`, `grupo`, `empresa`, `marca`, `licencia_marca`, `sucursal`,
  `almacen`, `categoria`, `categoria_udm`, `unidad_medida`, `archivo`.
  Modelos SQLAlchemy 2.0 tipados en
  `src/modules/{users,inventory}/infrastructure/models/` y
  `src/shared/models/`; mixins comunes (`UuidPkMixin`, `TimestampMixin`,
  `SoftDeleteMixin`, `JsonB`) en `src/core/model_base.py`; naming
  convention de constraints en `Base.metadata`; registro central
  `src/core/models_registry.py` cableado a Alembic; migración inicial
  Alembic validada contra Postgres 16 (ciclo upgrade/downgrade/upgrade);
  tests de esquema (`tests/test_models.py`).
- Puerto de Postgres en el host movido a **5433** (`docker-compose.yml`,
  `.env.example`) — el 5432 local lo ocupa la plataforma de Charlie's
  Pizzas; dentro de la red de compose sigue siendo `db:5432`.
- **BD de desarrollo movida a Supabase** (Postgres gestionado): la
  migración inicial (`a06c1d0a0913`) se aplicó contra el proyecto
  Supabase del usuario — 11 tablas + `alembic_version` verificadas.
  Motivo: visualización (Table Editor) y disponibilidad en línea de cara
  al despliegue futuro. Explícitamente **no** se activa Supabase
  Auth/RLS — sigue rigiendo `users` (JWT+PIN+Argon2id+RBAC) y el
  aislamiento de tenant por filtro de aplicación (ADR-004). Detalle y
  cómo alternar con el contenedor Docker local:
  `docs/engineering/devops.md`. Connection string solo en `.env`
  (gitignorado), plantilla sin secretos en `.env.example`.
- `reporte_escalamiento` definido con el negocio: cadena atención al
  cliente → supervisor (redacta solución) → comercial/gerencia; se
  almacena para mejora continua (`data-model.md` §6).
- **Slice Venta — núcleo de datos** (11 tablas nuevas, 22 en total):
  `usuario` (mínimo), `trabajador` (nuevo módulo `src/modules/rrhh/`),
  `articulo`/`sku`/`receta`/`receta_item` (base de productos, inventory),
  `cliente`/`punto_venta`/`producto_comercial`/`venta`/`venta_item`
  (nuevo módulo `src/modules/sales/`). Conecta venta con cliente y
  trabajador para habilitar historial de compras del cliente y ranking
  de ventas por trabajador — ambos probados en
  `tests/test_venta_slice.py`. Migración `08c7aa59dd6e` aplicada y
  verificada en Supabase (ciclo upgrade/downgrade/upgrade).
- **`venta.numero_orden`** (RN-COM-014, nueva): correlativo legible por
  sucursal y día (único junto a `sucursal_id`+`fecha_orden`) — lo que ve
  el personal en cocina/mostrador/KDS; distinto de `idempotency_key`
  (técnico) y del correlativo del comprobante (fiscal). Aplica tenga o
  no `cotizacion_id` la venta.
- **`cliente.usuario_id`** opcional (RN-COM-015, nueva): cuenta de
  autoservicio web — nunca requerida para comprar en sucursal o Central
  de Pedidos, esas ventas enrutan al mismo `cliente` sin login.
  Migración `90116965bfa8` aplicada y verificada en Supabase.
- **Slice Cobro y Comprobante (PROC-COM-002) + ciclo de caja
  (PROC-CTB-001/002)** — 8 tablas nuevas (30 en total): `medio_pago`
  (catálogo por empresa, decisión 2026-07-20), `pago` (RN-COM-016 —
  pago dividido confirmado real, suma de montos debe igualar
  `venta.total`), `comprobante` (nuevo módulo transversal en
  `src/shared/models/` — sirve a sales/purchases/accounting, correlativo
  único por empresa+serie, RN-CPP-007), `apertura_caja`,
  `custodia_efectivo`, `cierre_caja`, `arqueo` (nuevo módulo
  `src/modules/accounting/`, ciclo completo de caja). `punto_venta` gana
  `serie_boleta`/`serie_factura` (series SUNAT separadas por punto de
  venta, decisión 2026-07-20) — `comprobante.serie` las copia como
  snapshot inmutable al emitir. 3 tests nuevos
  (`tests/test_cobro_caja_slice.py`): pago dividido, unicidad de
  correlativo, cadena apertura→custodia→cierre. 13/13 tests pasan.
  Migración `8cde35e4f3f2` aplicada y verificada en Supabase (ciclo
  upgrade/downgrade/upgrade).

- Branding Provecho aplicado: paleta, tipografías (Anton Italic + Inter) y
  tokens CSS (`docs/product/ui-ux.md`).
- ADR-003: Izipay como pasarela de pago.
- `PROC-COM-002` Cobro y Emisión de Comprobante de Pago v1.0: narrativa +
  Mermaid en `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Comercial/PROC-COM-002-v1.0.bpmn` (detalle del
  paso "cobro" de `PROC-COM-001`, RN-COM-005).
- `PROC-CTB-002` Apertura de caja v1.0: narrativa + Mermaid en
  `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Contabilidad/PROC-CTB-002-v1.0.bpmn`. Nuevas
  reglas RN-POS-009 a RN-POS-013 y RN-MDP-006.
- `PROC-OPE-001` Apertura de sucursal v1.0: nueva área `OPE` (Operaciones)
  en `process-nomenclature.md`; narrativa + Mermaid en
  `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Operaciones/PROC-OPE-001-v1.0.bpmn` (checklist
  físico de apertura, recepción de pedido, limpieza, apertura de caja
  referenciada). Nuevas reglas RN-SUC-006 a RN-SUC-012, RN-PER-006 y
  RN-RRHH-009 a RN-RRHH-011. Glosario: agrega "Supervisor" (Actores) y
  "Alarma" (Recursos).
- SOPs de limpieza (14) y de lavado de menaje en
  `docs/diagrams/Procesos/Operaciones/Limpieza/`.
- SOPs de procesos comerciales/caja/apertura (9) derivados de los BPMN
  vigentes, en `Comercial/Ventas/`, `Comercial/Cobros/`,
  `Contabilidad/Caja/` y `Operaciones/Apertura-Sucursal/`.
- SOPs de `PROC-INV-001` (3): conteo de insumos y envío de requerimiento,
  picking y despacho en almacén central, recepción y devoluciones en
  local — nueva área `Logistica-Almacen` en
  `docs/diagrams/Procesos/`.

### Fixed

- `data-model.md` §6 `venta.estado`: seguía con el enum viejo de 8
  estados; corregido al enum vigente desde 2026-07-14
  (`orden|pagada|facturada|anulada`, RN-COM-005) — `state-machines.md`
  ya lo tenía correcto, quedaron desalineados.
- `data-model.md` §3 `articulo`: le faltaba `empresa_id` directo,
  rompiendo la convención de tenant (ADR-004) porque `categoria_id` es
  opcional.

### Changed

- `PROC-CMP-001` Compras v1.0 → v2.0: tres caminos de compra (informal/
  caja chica, preferente sin cotización comparativa, estándar/activo con
  RFQ) y ejecución del pago trasladada a Contabilidad (Compras solo
  sustenta el comprobante conforme). Registro maestro y `workflows.md`
  actualizados.
- Identidad de nombres unificada: **Provecho** = ERP, **Grupo Majambo** =
  grupo empresarial (corregido `docs/00_PROJECT.md`, aclarado en
  `CLAUDE.md`).
- Referencias de ADR normalizadas a 3 dígitos (`ADR-001`..`ADR-004`);
  ruta corregida en `CLAUDE.md` (`docs/architecture/adr/`).
- Entidad `contrato` reubicada como transversal (antes aparecía dentro de
  la sección de Inventario del data-model); referencia rota de
  `contrato_laboral` corregida.
- Specs de módulos sincronizadas con el catálogo de eventos (secciones
  Publica/Escucha de sales, inventory, purchases, accounting) y mapa
  `docs/diagrams/modules.md` regenerado.
- `docs/diagrams/README.md` actualizado a la convención real: SOPs
  primero y BPMN después, taxonomía `Procesos/<Área>/<Grupo>/`, versiones
  antiguas de BPMN se conservan para análisis.

- `PROC-INV-001` Abastecimiento de locales v0.1 → v0.2: detalla el conteo
  de fin de jornada en sucursal (balanzas, lector QR, ventana de 5 min
  fuera de refrigeración, alerta por margen de error RN-INV-015, cálculo
  de sugerido por punto de reorden RN-INV-013). Sigue en Borrador —
  picking/packing/transporte en almacén central aún sin este nivel de
  detalle.
- `PROC-CTB-001` Cierre de caja v1.0 → v1.1: agrega la bifurcación de
  custodia del fondo/caja chica (local en sucursal vs. traslado a
  oficinas de contabilidad, RN-MDP-006); RN-MDP-002 ampliada para cubrir
  la cadena de custodia en sentido inverso (apertura). Máquina de estados
  "Custodia de efectivo" actualizada en `docs/domain/state-machines.md`.
- Referencias a Mercadopago eliminadas (decisión: Izipay).
- Docs reorganizados por tema (`foundation/`, `domain/`, `architecture/`,
  `engineering/`, `security/`, `product/`) en vez de numeración plana;
  índice y orden de lectura en `docs/00_PROJECT.md`.
- Nuevos documentos de conocimiento: glosario (lenguaje ubicuo), filosofía del
  negocio, reglas de negocio (separadas del modelo de dominio), catálogo de
  eventos, máquinas de estado, autorización (RBAC, separada de seguridad).
- `AI_RULES` → `engineering/engineering-guide.md` (guía extensa; `/CLAUDE.md`
  la resume y apunta a ella).

### Removed

- Borradores duplicados de Venta: carpeta `docs/diagrams/Procesos/Ventas/`
  (BPMN/BPM de borrador — el vigente es
  `Comercial/PROC-COM-001-v1.0.bpmn`) y `docs/diagrams/Ventas.bpm`.
  `Cobro-PROC-COM-002-v1.0.bpmn.bpm` renombrado a
  `PROC-COM-002-v1.0.bpm` (archivo de proyecto Bizagi, doble extensión
  corregida).

## [0.1.0] - 2026-07-04

### Added

- Scaffold inicial: modular monolith (FastAPI + Next.js + PostgreSQL).
- Core: app factory, settings por entorno, sesión SQLAlchemy, event bus interno.
- Endpoint `/health` con tests.
- Especificaciones (contratos) de módulos: users, inventory, sales, purchases, accounting.
- Documentación: arquitectura, ADRs, modelo de negocio, modelo de datos v1.
- Docker Compose (api, web, postgres, redis), CI con GitHub Actions.
- Reglas de desarrollo en `CLAUDE.md`.
