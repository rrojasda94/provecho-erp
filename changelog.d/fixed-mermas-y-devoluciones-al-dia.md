- **La bandeja de mermas ya no ofrece resolver al que la registró**
  (2026-09-06). `MermaOut` no exponía `creado_por`, así que la pantalla no
  podía esconder los botones Desechar/Reintegrar y quien registró la merma
  se comía el 409 de RN-INV-019 al apretarlos. Suma `creado_por` y
  `liberado_por`, y un selector de almacén que el endpoint ya aceptaba y la
  pantalla nunca ofrecía.
- **La devolución se registra con varias líneas**. El formulario mandaba
  una sola aunque la API acepta varias desde el primer día — el caso real
  es rechazar un pedido completo, no un producto a la vez.
- **La ficha de devolución muestra nombres, no UUID**. Nuevo
  `users.nombres_de_usuarios` (mismo patrón que `inventory.nombres_de_articulos`,
  que ya usa el KDS), resuelve `registrado_por`/`anulado_por` en
  `GET /devoluciones/{id}`.
