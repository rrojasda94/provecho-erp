- El PATCH de las cinco entidades de organización (Grupo, Empresa, Marca,
  Sucursal, Almacén) ahora distingue "campo ausente" de "`null` explícito"
  (ADR-096), como ya hacía `editar_usuario` (ADR-070). Antes, un opcional
  puesto en `null` no se vaciaba — así que no se podía quitar el almacén
  abastecedor de un almacén, ni su respaldo, ni desactivar el
  `radio_marcaje_m` de una sucursal, aunque el selector del frontend ya
  ofrecía "Ninguno". Habilita vaciar `almacen_abastecedor_id`,
  `almacen_abastecedor_respaldo_id`, `direccion` y `sucursal_id` de almacén,
  `radio_marcaje_m`/`horario_atencion` de sucursal, `contacto`/
  `config_fiscal` de empresa, `skins` de marca y los cinco `ubicacion_*`.
- `MarcaOut` y `SucursalOut` exponen `skins`/`horario_atencion` en la
  lectura — eran escribibles desde el alta y no viajaban de vuelta.
- Corregidos dos bugs del mismo origen que el cambio expuso:
  `editar_almacen` derivaba sus validaciones con `campos.get(x) or actual`,
  que descartaba un `None` intencional igual que uno ausente; y
  `ubicacion.desanclar_si_cambio_el_texto` leía el texto crudo de la request
  en vez del ya aplicado a la entidad, desanclando por error ante un campo
  no-borrable en `null` explícito.
