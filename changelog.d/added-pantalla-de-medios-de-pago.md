- **Catálogo → Medios de pago** (`/catalogo/medios-pago`): la pantalla que
  faltaba para dar de alta con qué se cobra. Hasta ahora el backend tenía
  `POST /sales/medios-pago` desde el primer slice y el frontend solo los
  leía, así que un local que empezaba a cobrar con otra billetera dependía
  de quien tuviera acceso a la API. Alta con tipo (el vocabulario de
  `rules.TIPOS_MEDIO_PAGO`), dirección y comisión; edición en línea de
  nombre, tipo, comisión y activo, con el mismo gate
  `sales.gestionar_catalogo` que el resto del catálogo. Suma
  `PATCH /sales/medios-pago/{id}`; el `GET` acepta `direccion` e
  `incluir_inactivos`.
- **No hay borrar, hay apagar.** Un medio que ya cobró no se puede quitar
  sin dejar cobros huérfanos: `activo=false` lo saca del PDV y lo deja en
  pie en el histórico, igual que descontinuar un producto. La pantalla los
  sigue mostrando (`incluir_inactivos=true`) porque quien apagó tiene que
  poder reactivar, y avisa cuando no queda ninguno activo de cobro: sin eso
  el PDV no puede cerrar una venta, y hasta ahora eso se descubría recién
  en la caja.
- **El PDV pide `direccion=cobro`.** Con lo que se le paga a un proveedor no
  se le cobra a un comensal, y sin el filtro el primer medio de dirección
  `pago` habría salido como pastilla en la pantalla del cajero. El
  vocabulario de `tipo` y `direccion` pasa a validarse en el borde
  (`Literal` en el esquema): antes un valor inventado llegaba hasta el
  flush y reventaba contra el CHECK de la columna.
