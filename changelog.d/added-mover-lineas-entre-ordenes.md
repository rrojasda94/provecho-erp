- **Mover productos entre pedidos y cobrar solo lo seleccionado** (2026-08-27,
  RN-COM-043, ADR-070). El PDV ya tenía la selección múltiple (mantener
  presionado un producto) y el backend ya tenía el cobro dividido
  (`grupo_cobro`, ADR-018) — pero nada conectaba la una con el otro, y no
  existía forma de mover un producto cargado en la mesa equivocada. Un solo
  endpoint (`POST /ventas/{id}/mover-lineas`) resuelve ambos casos: reasigna
  líneas ya enviadas a otra orden, a una mesa libre, o a otra cuenta de la
  misma orden. Sin PIN de supervisor (el producto sigue existiendo en alguna
  orden abierta) y sin tocar inventario (el insumo no se movió del almacén).
  Costo aceptado: no genera asiento de reclasificación —origen y destino
  asientan contra las mismas cuentas, así que el efecto en el libro es cero—
  y no viaja todavía por el hub offline (mismo hueco que ya tenían
  `agregar_lineas`/`anular_lineas`).
