# Módulo `accounting` — Contabilidad

## Objetivo

Registrar asientos contables generados por los eventos de los módulos
operativos (ventas, compras, inventario) y permitir asientos manuales
controlados. Base para tesorería y reportes financieros futuros.

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
- Publica: `accounting.asiento_generado`, `accounting.periodo_cerrado`.
