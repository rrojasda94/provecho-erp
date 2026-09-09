# Deuda técnica — Módulo assets (slice core — deuda declarada)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-09-09 **Slice core** (ADR-098): `activo`/`vehiculo`, kilometraje
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
  - ⬜ **`repuesto_compatibilidad`** y repuestos en la orden de
    mantenimiento: sin control de stock de repuestos todavía, `costo` de la
    orden alcanza para lo que se necesita hoy.
  - ⬜ **Alta automática del activo al recibir una OC tipo `activo`**:
    depende de `requerimiento_activo` en `purchases` (deuda declarada de
    ese módulo, aún rechazado en tiempo de ejecución). Cuando exista, un
    evento de `purchases` puede consumirse acá para no dar de alta el
    activo dos veces (una en el papeleo de compra, otra a mano en
    `assets`).
  - ⬜ **Depreciación en `accounting`**: `activo.valor_compra`/
    `vida_util_meses` quedan como insumo; el cálculo y el asiento siguen
    pendientes (deuda ya declarada de `accounting`, PROC-CTB-007/010).
  - ⬜ **`guia_remision.vehiculo_placa` sigue siendo texto libre**:
    reemplazarla por una FK a `assets.vehiculo` es deuda de `inventory`
    (ADR-027 §4 queda superado, no automáticamente migrado).
  - ⬜ **Adjuntos de `documento_vigencia` son solo metadata**: la subida
    binaria a S3 la hace el cliente directo contra el storage (mismo
    patrón que `marketing.application.adjuntos`); este módulo no tiene un
    endpoint de subida propio.
  - ⬜ **Canal de la alerta más allá de la campana**: deuda ya declarada de
    `reports` (ADR-033) — `assets` hereda el mismo límite que el resto del
    catálogo.
  - ⬜ **Frontend de `assets/tolerancia_consumo_pct`**: el parámetro se
    propone y aprueba por la misma pantalla de Gerencia que cualquier otro
    (`parametro_empresa`, ADR-014); no hay UI especial para este módulo.
