- **Una orden de compra en borrador ahora se puede editar** (`PATCH
  /purchases/ordenes-compra/{id}`): antes de esto era inmutable desde el
  instante en que se creaba — corregir un precio o una cantidad tecleada mal
  exigía anular la OC entera y rehacerla. Reemplaza los ítems y recalcula el
  total, solo mientras `estado == "borrador"`; desde `emitida` sigue siendo
  inmutable, sin excepción, como ya era.
