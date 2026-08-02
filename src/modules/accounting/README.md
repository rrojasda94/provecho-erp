# Módulo `accounting` — Contabilidad

> Área de negocio documentada en [docs/contabilidad/](../../../docs/contabilidad/README.md).
> El área concentra hoy **tesorería, finanzas y registro contable** en un solo
> responsable, bajo supervisión de Gerencia (RN-CTB-004); este módulo es su
> soporte de software.

## Objetivo

Registrar asientos contables generados por los eventos de los módulos
operativos (ventas, compras, inventario), permitir asientos manuales
controlados y dar soporte a **tesorería** (ciclo de caja, pago a proveedor,
conciliación bancaria, arqueos) y a **finanzas** (flujo de caja, insumos de
presupuesto).

## Entidades

`cuenta_contable` (plan de cuentas), `asiento`, `asiento_linea` (debe/haber),
`periodo_contable`, `regla_asiento` (mapeo evento→cuentas),
`movimiento_dinero` (tesorería — pago a proveedor). Detalle en
`docs/architecture/data-model.md` §8.

**Estado de implementación (2026-07-25):** libro contable núcleo construido
— `cuenta_contable` (plan de cuentas), `periodo_contable` (abrir/cerrar),
`asiento`/`asiento_linea` (manual con permiso `accounting.asiento_manual`,
cuadre RN-CTB-001, anulación por asiento inverso RN-CTB-002) y
`regla_asiento` (mapeo configurable evento→cuentas que alimenta la
generación automática, `application/listeners.py`). Cubre hoy los 4 eventos
operativos que sus módulos de origen ya publican en código
(`purchases.oc_emitida`, `purchases.compra_recibida`,
`sales.venta_confirmada`, `purchases.comprobante_conforme`); el resto de
eventos listados abajo quedan pendientes de que esos módulos los publiquen
(deuda técnica, ver ROADMAP).

**Pago a proveedor (PROC-CTB-003, mismo día):** `movimiento_dinero`
(tesorería, genérico egreso/ingreso) — `purchases.comprobante_conforme`
encola un pago `pendiente` (`application/pagos.registrar_pago`, idempotente
por `comprobante_id`, RN-CTB-008); `application/pagos.ejecutar_pago` exige
permiso `accounting.pago_gestionar`, revisa el umbral configurable
(`parametro_empresa`, código `pago_umbral`, RN-CTB-005 — sobre el umbral
exige además `accounting.pago_aprobar`) y genera el asiento vía
`regla_asiento` (evento `accounting.pago_ejecutado`; sin mapeo configurado,
el pago igual se ejecuta y el asiento se omite). `rechazar_pago` cierra la
cola sin ejecutar. Detracción SPOT se calcula (`monto_detraccion`) pero el
asiento no la desglosa en cuenta propia — ver deuda técnica en ROADMAP.

Ciclo de caja (PROC-CTB-001/002) ya existía — `apertura_caja`,
`custodia_efectivo`, `cierre_caja`, `arqueo`
(`src/modules/accounting/infrastructure/models/`), dependencia del slice de
Cobro (PROC-COM-002), aún sin conectar al libro contable (no genera asiento
todavía). `comprobante` NO vive aquí — es transversal, está en
`src/shared/models/`.

## Casos de uso

- Mantener plan de cuentas.
- Generación automática de asientos desde eventos (venta, compra, ajuste de inventario).
- Asientos manuales con permiso `accounting.asiento_manual`.
- Cierre de periodo (bloquea modificaciones).
- Pago a proveedor: registrar (cola) → ejecutar (permiso + umbral) →
  asiento automático, o rechazar.

## Reglas

- Todo asiento cuadra: suma debe = suma haber. Validación en dominio.
- Asientos de periodo cerrado son inmutables.
- Ninguna eliminación física: reversión mediante asiento inverso.

## Flujo

Evento operativo → regla de mapeo contable → asiento generado → mayor/balances.

## Relaciones

- Escucha: `sales.venta_confirmada`, `sales.pago_registrado`,
  `sales.comprobante_emitido`, `purchases.oc_emitida` (provisiona),
  `purchases.compra_recibida`, `purchases.comprobante_conforme` (decide y
  ejecuta el pago según condición del proveedor),
  `purchases.caja_chica_rendida` (concilia y repone fondo),
  `inventory.transferencia_recibida`, `inventory.merma_registrada`
  (reporte de pérdidas), `inventory.ajuste_fuera_margen` (alerta de
  auditoría).
- Publica: `accounting.asiento_generado`, `accounting.periodo_cerrado`,
  `accounting.apertura_caja_registrada`, `accounting.cierre_caja_registrado`,
  `accounting.cierre_caja_irregular`, `accounting.pago_ejecutado`,
  `accounting.pago_requiere_aprobacion`, `accounting.arqueo_registrado`
  (ver [events.md](../../../docs/architecture/events.md)).

## Tesorería y finanzas (procesos del área)

Además del registro contable, el módulo soporta los procesos de tesorería/
finanzas documentados en el área:

- **Pago a proveedor** (PROC-CTB-003, implementado 2026-07-25): ejecuta el
  pago con comprobante conforme (RN-CMP-014), umbral de aprobación de
  Gerencia (RN-CTB-005), detracción SPOT (calculada, sin desglose contable
  propio aún) e idempotencia contra doble pago (RN-CTB-008).
- **Apertura/cierre de caja** (PROC-CTB-002/001, **slice mínimo**
  implementado 2026-07-26, ver ADR-012): `abrir_caja`/`cerrar_caja`/
  `registrar_arqueo` en `application/caja.py`. El cierre **reconcilia de
  verdad**: `monto_esperado = monto_apertura + efectivo cobrado desde la
  apertura`, este último vía el contrato público de `sales`
  (`total_efectivo_cobrado` — `accounting` no importa el dominio de
  `sales`). Permisos `accounting.caja_operar` (rol `cajero`, abre/cierra su
  propia caja) y `accounting.arqueo_registrar` (`supervisor`/`contador`).
  **Diferido a un slice dedicado** (no incluido): verificación de series de
  POS y denominaciones obligatorias (RN-POS-009..013), relevo autenticado
  por PIN propio de ambas partes (hoy solo se registra
  `relevo_encargado_id`), `custodia_efectivo` como máquina de estados real,
  enlace con `sales` para bloquear el cobro sin caja abierta.
- **Conciliación bancaria** (PROC-CTB-004): cuadra movimientos vs. extracto;
  visada por Gerencia, requisito de cierre de periodo (RN-CTB-006).
- **Flujo de caja** y **activo fijo/depreciación**: pendientes de slice
  dedicado (PROC-CTB-007/010, propuestos).

## Contrato API — caja (slice mínimo)

| Método | Ruta | Permiso |
|--------|------|---------|
| POST | `/accounting/cajas/apertura` | `accounting.caja_operar` |
| POST | `/accounting/cajas/apertura/{id}/cierre` | `accounting.caja_operar` |
| GET | `/accounting/cajas/abiertas?empresa_id=` | `accounting.leer` |
| POST | `/accounting/arqueos` | `accounting.arqueo_registrar` |
