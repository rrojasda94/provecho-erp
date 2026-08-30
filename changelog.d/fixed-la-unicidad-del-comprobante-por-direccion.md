- **La factura de un proveedor bloqueaba nuestra propia serie** (2026-08-30,
  ADR-085, migración `0a056863874b`). `comprobante` es transversal —emitidos y
  recibidos en la misma tabla— pero su unicidad era una sola,
  `(empresa_id, serie, correlativo)`, sin distinguir `direccion`. Con eso: la
  F001-1 de un proveedor impedía emitir la nuestra; dos proveedores no podían
  coincidir en un número (el segundo moría con un 500); y
  `siguiente_correlativo` tomaba el máximo de la serie **sin filtrar
  dirección**, así que registrar una compra F001-1200 hacía que el siguiente
  comprobante propio saliera con el 1201 — un salto de numeración ante SUNAT
  provocado por el papel de un tercero. Ahora son dos índices únicos
  parciales: el emitido es único por empresa, el recibido por emisor.
- **La factura del proveedor no se podía representar.** Se guardaban tipo,
  serie, correlativo y sustento, y nada más: la fecha del papel —la que manda
  en el Registro de Compras— no tenía dónde ir, y el importe se tomaba
  implícitamente de `orden_compra.total`, que es la base valorizada de lo
  recibido y no lo que la factura declara. `comprobante` suma `emisor_num_doc`,
  `fecha_emision` y `total`. Lo ya registrado no se rellena con el total de la
  OC: sería un número que parece venir del papel sin venir de él.
- **Un tipo de comprobante inválido devolvía 500 en vez de 422.** `tipo` y
  `sustento` eran `str` libres contra columnas `Enum` con CHECK, así que el
  valor malo moría en el `flush` sin decir qué campo estaba mal — el mismo
  defecto que `ProveedorUpdate` ya había corregido con `Literal`.
