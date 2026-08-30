- **Registrar una recepción era imposible si el costo de la OC tenía más de
  dos decimales** (2026-08-30). `orden_compra_item.cantidad` y
  `costo_unitario` son `Numeric(12, 4)` —el costo de un insumo a granel se
  lleva a cuatro decimales— pero los campos del formulario declaraban
  `step="0.01"`. Con eso, el diálogo de recepción se abría precargado con el
  costo de la propia orden (`0.0040`) y el navegador se negaba a enviarlo:
  «the two nearest valid values are 0 and 0.01», en un globo nativo que
  desaparece solo y no deja rastro. El botón «Registrar» no hacía nada y no
  había nada que leer. Los cuatro campos —cantidad y costo, en la recepción,
  en la compra directa y en el alta de OC— pasan a declarar la precisión que
  la columna guarda.
