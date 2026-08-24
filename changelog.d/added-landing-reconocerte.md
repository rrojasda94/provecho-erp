- **Landing pública «Queremos RE-conocerte» y cupón de 10 %** (2026-08-24,
  ADR-059). Un QR en la mesa lleva a `/reconocerte`, donde un cliente de
  Charlie's deja DNI, cumpleaños, dirección y teléfono sin necesidad de
  cuenta, y recibe un cupón de un solo uso para su siguiente compra. La caja
  lo canjea con `POST /sales/ventas/{id}/cupon`, y ahí queda desactivado para
  siempre.
- **El cupón vive en `sales`, no en `marketing`.** Registrar al cliente y
  descontar la venta son dos escrituras dentro de `sales`, y un módulo solo
  entra a otro por `api.deps` o `queries_publicas` — ninguno de los dos sirve
  para escribir. Ponerlo en `marketing` habría exigido ampliar la lista de
  excepciones cruzadas de `tests/test_arquitectura.py`, que es justo la deuda
  que esa lista existe para no seguir acumulando. Marketing se entera por
  `sales.cliente_registrado_en_promocion` y crea su `lead`, igual que ya hace
  con `sales.venta_confirmada`.
- **El descuento reusa `venta.descuento_*` con un motivo nuevo, `cupon`.** El
  costo aceptado: esas columnas eran del descuento manual, y ahora comparten
  tabla con uno que nadie autorizó. Se paga porque la alternativa —un canal de
  descuento paralelo— obligaba a tocar `total_a_cobrar`, el prorrateo que
  SUNAT exige en el comprobante y las notas de crédito, que es la parte que
  maneja dinero y ya funciona. El motivo propio deja al reporte de descuentos
  separar el margen regalado a criterio del prometido en campaña, que era la
  auditabilidad que ADR-018 protege. **El motor de promociones condicionales
  sigue sin poder reusarlas**: ahí no interviene nadie.
- **El canje no pide PIN de supervisor**, a diferencia del descuento manual
  (RN-COM-017). El cupón ya era del cliente y el cupón es la autorización;
  pedir un supervisor por cada uno haría que la caja deje de canjearlos, que
  es la forma más segura de romper la promesa de la campaña.
- **La superficie pública escribe pero no borra, y solo lee un booleano.** No
  hay ningún `DELETE` —la baja de datos se atiende por `hola@majambo.com.pe`
  con la anonimización de ADR-011, nunca desde una página abierta a internet—,
  la consulta devuelve `{registrado: bool}` y nada más, y el `grupo_id` sale
  de la promoción activa y jamás del request. Lo único que la protege es el
  rate limit por IP, en tres niveles según lo que cuesta cada llamada: el más
  duro (5/hora) es el que convierte un DNI en un nombre, porque es el que
  permitiría enumerar documentos. Es el costo aceptado de que el cliente
  confirme su nombre en vez de teclearlo.
- **El código del cupón es el DNI** (lo pidió el negocio). El cliente no tiene
  nada que recordar ni guardar, y devolverlo en la respuesta no filtra nada
  porque es el número que él mismo acaba de escribir. A cambio, quien conozca
  un DNI ajeno podría intentar su cupón: se acota atándolo al cliente de la
  venta, no se elimina.
- **La empresa puede terminar la promoción en cualquier momento** con
  `POST /sales/promociones-cupon/{id}/termino` (`sales.gestionar_promociones`,
  del rol `supervisor`). Deja de emitir cupones nuevos y **no toca los ya
  entregados**: quien alcanzó a registrarse cumplió su parte del trato.
- **Los logotipos de `frontend/public/marcas/` son provisionales.** Están
  armados con tipografía y los colores de marca, no con los originales. Para
  poner los definitivos alcanza con reemplazar el archivo conservando el
  nombre — ningún componente cambia. Ver `frontend/public/marcas/README.md`.
- **El teléfono reconoce a un cliente, pero no reescribe su identidad.** Se
  le completa el documento solo a quien no tiene ninguno: sin ese candado,
  saber un teléfono ajeno alcanzaba para cambiarle el DNI a su dueño desde
  una página abierta a internet, y quedarse con su historial de compras. Un
  teléfono que ya es de alguien identificado se ignora y el registro entra
  como cliente nuevo — dos fichas con el mismo teléfono se limpian, una
  identidad pisada no. Apareció probando el flujo contra la API real; los
  tests no lo cubrían.
