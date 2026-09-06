- **Ocho estados se comunicaban solo por color** (2026-09-05, hallazgo #17 de
  la auditoría del 2026-08-30). Quedaban píldoras escritas a mano —
  `bg-accent/30` para lo bueno, `bg-gray/20` para lo apagado — en productos,
  proveedores, artículos, sucursales, asientos, trabajadores, clientes y
  requerimientos. Para quien no distingue rojo de verde, las dos son la misma
  cápsula gris. Pasan a `Insignia`, que ata el ícono al tono para que no sea
  una prop que la pantalla número treinta y uno se olvide.
- **El aviso pasajero del KDS y del PDV no lo anunciaba nadie** (2026-09-05,
  mismo hallazgo). Las dos pantallas avisan con una píldora flotante que
  aparece y se va sola —«pedido listo», «no se pudo guardar»— y son justo las
  dos que se usan de pie y mirando otra cosa. Ahora la región vive siempre y
  lo que cambia es el mensaje de adentro: montar el `role="status"` **junto
  con** el texto no sirve, porque un lector de pantalla anuncia los cambios de
  una región viva, no su aparición — es la parte que se hace mal seguido.
  `role="status"` y no `alert`: son avisos de lo que pasó, no
  interrupciones, y `alert` corta lo que el lector esté leyendo.
