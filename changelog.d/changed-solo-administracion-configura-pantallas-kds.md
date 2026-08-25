- **Montar una pantalla de cocina pasa a ser acto de administración**
  (2026-08-24, ADR-065). `kds.configurar` sale del rol `supervisor`: dar de
  alta, renombrar o borrar una estación cambia por dónde pasa la comanda de
  **todos** los turnos, no solo del que está en el local esa tarde. Es alta de
  infraestructura, igual que el punto de venta (ADR-059). El supervisor
  conserva `kds.operar` y opera lo que ya está montado; la pantalla de
  estaciones ahora dice «pídele a un administrador».
- **Una pantalla KDS por fin se puede borrar** (2026-08-24). El modelo tenía
  `deleted_at` desde que nació y **ningún camino lo escribía**: una estación
  creada con un error de tipeo se quedaba para siempre. `DELETE
  /kds/pantallas/{id}` es baja lógica, exige `kds.configurar` y devuelve 409
  si la pantalla tiene cola —borrarla con pedidos encima dejaría esas líneas
  sin dónde tacharse—. `activo=false` sigue siendo otra cosa: apaga la
  estación y la deja volver. El `UNIQUE (sucursal_id, nombre)` pasa a ser
  parcial sobre las vivas, así el nombre de una borrada queda libre.
- **`GET /kds/pantallas` acepta `kds.operar` o `kds.configurar`**
  (2026-08-24). Un administrador que solo tuviera el permiso de configurar no
  podía **listar lo que administra** — el mismo patrón que ya usaba
  `GET /sales/puntos-venta`.
