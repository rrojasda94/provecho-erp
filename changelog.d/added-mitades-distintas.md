- **Las dos mitades de una mitad-y-mitad tienen que ser distintas**
  (RN-COM-038, enmienda de ADR-056).

  Media hawaiana y media hawaiana no es una mitad-y-mitad: es una hawaiana
  entera, que ya se vende como su propio producto con su receta y su precio.
  `producto_exclusion` —creada en ADR-055 y hasta ahora sin usar— declara el
  par imposible, y `POST /sales/ventas` lo rechaza con 409. Se valida al
  confirmar la venta y no solo en el PDV: el kiosko y la central de pedidos
  entran por el mismo endpoint.

  La exclusión se guarda **una vez** y vale en los dos sentidos: el par es
  simétrico y guardar el espejo sería la misma verdad dos veces.

- **Las líneas condicionadas a las dos mitades se parten en una por mitad.**

  Con la regla de arriba, una condición que pide el mismo sabor en las dos
  mitades no se cumple nunca, y una que pide un conjunto en las dos deja de
  descontar en cuanto una mitad se sale. Las 52 líneas del archivo de
  Charlie's resultaron ser **todas simétricas** —el mismo conjunto de sabores
  en las dos mitades—, que es lo que dice cuál era la intención: cada mitad
  aporta lo suyo.

  `scripts/odoo/convertir_catalogo.py` las parte, con la mitad del gramaje y
  escrito como operación (`(0.025)/2`) para que la planilla muestre de dónde
  salió el número (RN-COM-024). Se comporta igual que Odoo cuando Odoo
  acertaba y correctamente cuando no.

  **`A + B` y `B + A` consumen lo mismo por construcción**: con cada línea
  condicionada a una sola mitad, el total no depende de en qué mitad se
  eligió cada sabor. No hace falta canonicalizar nada al guardar.

- Las unidades de medida de la carga pasan a **4 decimales**, el máximo que
  admite `receta_item.cantidad`. Con 3, media línea de 0.025 kg redondea a
  0.013 y la pizza entera lleva un gramo de más que nadie pidió.
