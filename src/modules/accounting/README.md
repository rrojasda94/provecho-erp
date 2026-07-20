# Módulo `accounting` — Contabilidad

## Objetivo

Registrar asientos contables generados por los eventos de los módulos
operativos (ventas, compras, inventario) y permitir asientos manuales
controlados. Base para tesorería y reportes financieros futuros.

## Entidades

`cuenta_contable` (plan de cuentas), `asiento`, `asiento_linea` (debe/haber),
`periodo_contable`. Detalle en `docs/architecture/data-model.md` §8 (se refina antes de implementar).

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
  `purchases.compra_recibida`, `inventory.*` (ajustes).
- Publica: `accounting.periodo_cerrado`.
