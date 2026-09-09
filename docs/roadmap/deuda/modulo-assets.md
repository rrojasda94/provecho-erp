# Deuda técnica — Módulo assets (slice core — deuda declarada)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-09-09 **Slice core** (ADR-099): `activo`/`vehiculo`, kilometraje
  (`lectura_odometro`, odómetro monótono RN-VEH-005), combustible
  (`carga_combustible` ligada a un comprobante de `purchases`, rendimiento
  y detección de consumo anómalo RN-VEH-006/007), mantenimiento
  (`plan_mantenimiento` + `orden_mantenimiento`, aviso con anticipación
  configurable RN-MNT-005) y documentos con vencimiento
  (`documento_vigencia`, RN-DOC-001..004). Cinco emisiones nuevas en
  `reports` (`assets.mantenimiento_proximo/vencido`,
  `assets.documento_por_vencer/vencido`, `assets.consumo_anomalo`), área
  `compras` nueva en `AREAS_BASE`. Migración `30270ac890b1`.
  Lo que deja abierto:
  - ⬜ **`flota`** (agrupador de vehículos): sin reparto con varias unidades
    por categorizar, es un formulario que hoy nadie llenaría. Vuelve a la
    mesa si el grupo arma una flota real con más de un vehículo por tipo.
  - ✅ 2026-09-09 **`repuesto_compatibilidad`** y repuestos en la orden de
    mantenimiento: `repuesto_compatibilidad` (activo↔artículo `tipo=
    "repuesto"`) y `orden_mantenimiento_repuesto` (líneas de consumo,
    evento `inventory.movimiento_registrado` con origen
    `orden_mantenimiento`). No bloquea registrar un repuesto no listado.
  - ✅ 2026-09-09 **Alta automática del activo al recibir una OC tipo
    `activo`**: `purchases` construyó `requerimiento_activo` y
    `crear_orden_compra_activo`/`recibir_orden_compra_activo` (sin ítems de
    `inventory`, recepción total). `assets.application.listeners` (primer
    listener del módulo) consume `purchases.requerimiento_activo_recibido`
    y da de alta el activo. La doble aprobación de área/gerencia y las
    cotizaciones mínimas que `purchases` tenía especificadas siguen sin
    construirse (deuda de ese módulo, no de este); comprar un vehículo o
    varias unidades del mismo activo por esta vía también queda fuera.
  - ✅ 2026-09-09 **Depreciación en `accounting`**: `activo_depreciacion`
    (línea mensual por activo) + barrido Celery
    `accounting.correr_depreciacion_mensual` (PROC-CTB-010), asiento vía
    `crear_asiento_automatico` (idempotente por `activo_id:YYYY-MM`,
    respeta periodo cerrado). Consume `assets.queries_publicas.
    activos_depreciables` (contrato público, sin importar el dominio de
    `assets`).
  - ✅ 2026-09-09 **`guia_remision.vehiculo_placa` → `vehiculo_id`**:
    FK opcional a `assets.vehiculo` (`_resolver_placa` sigue aceptando
    texto libre para quien no registra el vehículo en `assets`). ADR-027
    §4 queda superado.
  - ✅ 2026-09-09 **Adjuntos de `documento_vigencia` con subida real a
    S3**: `src/shared/integrations/storage/s3.py` (mismo patrón lazy-import
    que `src/backups/backup.py`, ADR-007) genera URLs prefirmadas de subida
    y descarga; el registro de metadata sigue en `Archivo` (`shared`).
  - ✅ 2026-09-09 **Canal de alerta por email**: `reports` sumó `canal`
    (`campana`/`email`) a `regla_distribucion`/`entrega_reporte`
    (`src/shared/integrations/email/smtp.py`). Deuda ya cerrada del lado de
    `reports` (ADR-033); `assets` hereda el canal nuevo sin cambios propios.
  - ✅ 2026-09-09 **`assets/tolerancia_consumo_pct` sembrado y visible en
    Gerencia**: el parámetro no llegaba a proponerse (faltaba en
    `src/seeders/parametros.py`) y el módulo `assets` no estaba en el
    selector de `/gerencia/parametros` (`parametros-cliente.tsx`). Se
    corrigieron ambos gaps y se corrigió además `combustible.
    tolerancia_consumo` (leía `int(valor)` sobre un dict en vez de
    `valor["porcentaje"]`, mismo criterio que `sales.alertas.
    umbral_minutos`). Sigue sin una UI **dedicada** (tipo de input
    porcentaje con rango 0-100, label/descripción fijos por parámetro): es
    deuda transversal de ADR-014, igual para todos los módulos, no
    específica de `assets`.
