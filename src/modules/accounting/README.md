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
`periodo_contable`. Detalle en `docs/architecture/data-model.md` §8 (se refina antes de implementar).

**Estado de implementación (2026-07-20):** módulo abierto parcialmente
con el ciclo de caja (PROC-CTB-001/002) — `apertura_caja`, `custodia_efectivo`,
`cierre_caja`, `arqueo` (`src/modules/accounting/infrastructure/models/`),
dependencia del slice de Cobro (PROC-COM-002). El resto de este README
(plan de cuentas, asiento, periodo_contable) sigue pendiente del slice
dedicado de Contabilidad. `comprobante` NO vive aquí — es transversal,
está en `src/shared/models/`.

## Casos de uso

- Mantener plan de cuentas.
- Generación automática de asientos desde eventos (venta, compra, ajuste de inventario).
- Asientos manuales con permiso `accounting.asiento_manual`.
- Cierre de periodo (bloquea modificaciones).

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

- **Pago a proveedor** (PROC-CTB-003): ejecuta el pago con comprobante conforme
  (RN-CMP-014), umbral de aprobación de Gerencia (RN-CTB-005), detracción SPOT
  e idempotencia contra doble pago (RN-CTB-008).
- **Conciliación bancaria** (PROC-CTB-004): cuadra movimientos vs. extracto;
  visada por Gerencia, requisito de cierre de periodo (RN-CTB-006).
- **Arqueo sorpresa** (PROC-CTB-005): control de Gerencia sobre el efectivo
  (RN-CTB-007).
- **Flujo de caja** y **activo fijo/depreciación**: pendientes de slice
  dedicado (PROC-CTB-007/010, propuestos).
