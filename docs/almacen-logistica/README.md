# Área Almacén y Logística — Grupo Majambo

Responsable del stock exacto (Almacén Central y su relación con los
almacenes de sucursal) y del movimiento físico de insumos entre
ubicaciones: recepción interna, conteo, control de vencimiento, mermas,
devoluciones y transporte. La ejecuta un **encargado de almacén** dedicado.

No duplica lo que ya vive en otras áreas:

- **Recepción de compra a proveedor** (Almacén Central recibe de un
  proveedor externo) → [Compras/Recepcion-Pago](../diagrams/Procesos/Compras/Recepcion-Pago/).
- **Ciclo de requerimiento sucursal↔central** (conteo de fin de jornada,
  picking/despacho, recepción en sucursal) → ya documentado en
  [Abastecimiento-Locales](../diagrams/Procesos/Logistica-Almacen/Abastecimiento-Locales/).

Este README y sus SOPs cubren lo que faltaba: conteo/auditoría del propio
Almacén Central, control de vencimiento y merma, devolución a proveedor, y
transporte/transferencias entre ubicaciones.

## Flujo por responsabilidad

| Responsabilidad | Dónde vive |
|---|---|
| Recepción de compra externa | [Compras/Recepcion-Pago](../diagrams/Procesos/Compras/Recepcion-Pago/) (ya documentado) |
| Requerimiento sucursal ↔ central | [Abastecimiento-Locales](../diagrams/Procesos/Logistica-Almacen/Abastecimiento-Locales/) (ya documentado) |
| Conteo cíclico y ajuste de discrepancia en Almacén Central | [Conteo-Auditoria/](../diagrams/Procesos/Logistica-Almacen/Conteo-Auditoria/) |
| Control FEFO/FIFO, vencimiento próximo, registro de merma/desperdicio | [Vencimientos-Mermas/](../diagrams/Procesos/Logistica-Almacen/Vencimientos-Mermas/) |
| Transferencia lateral entre sucursales, transporte/reparto, devolución a proveedor | [Transporte-Transferencias/](../diagrams/Procesos/Logistica-Almacen/Transporte-Transferencias/) |

## Documentos del área

| Documento | Contenido |
|---|---|
| [politica-almacen-logistica.md](politica-almacen-logistica.md) | FEFO/FIFO, conteo/ajuste, punto de reorden (quién lo define vs. quién compra), devoluciones, transporte/flota |
| [perfiles/](perfiles/) | Encargado de almacén central, chofer/repartidor |
| [../templates/almacen-logistica/](../templates/almacen-logistica/) | Reporte de conteo, ficha de ajuste, reporte de merma, guía de transferencia/devolución, hoja de ruta |

## Principios del área

- **Ningún insumo sale del almacén sin guía** (RN-ALM-001) — transferencia
  lateral incluida, no solo despacho a central.
- **Movimiento de inventario sigue FEFO/FIFO** (RN-ALM-007) — lo más
  antiguo o próximo a vencer sale primero, sin excepción por comodidad de
  acomodo.
- **Todo ajuste exige motivo y permiso `inventory.ajustar`** (RN-INV-004);
  solicitar y autorizar son permisos distintos (RN-INV-006).
- **El punto de reorden lo determinan Producción, Contabilidad y
  Logística** (RN-INV-008); Compras lo ejecuta (compra), no lo define solo.
- **Vehículo propio se asigna a un responsable con kilometraje registrado**
  (RN-VEH-002/004) — no es de "quien lo necesite ese día" sin control.
- **Transferencia lateral entre sucursales es excepción documentada**, no
  la vía normal de abastecimiento — el flujo normal sigue siendo
  sucursal↔central.
