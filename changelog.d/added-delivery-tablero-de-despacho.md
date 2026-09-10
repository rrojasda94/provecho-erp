- **El tablero de despacho de reparto propio vive en el ERP** (ADR-098,
  slice 5): en `/delivery` se ve lo sin asignar y las rutas vivas con su
  repartidor, sus paradas y un mapa con la polilínea real cuando la ruta
  se optimizó con Google; se crea una ruta eligiendo repartidor y
  pedidos, y se cancela una que no salió todavía. `/delivery/repartidores`
  da de alta y edita repartidores propios; `/delivery/entregas` es el
  historial paginado, con filtros y la foto de evidencia. `GET
  /delivery/tablero`, `GET /delivery/repartidores` y `GET
  /delivery/entregas` ahora resuelven venta, cliente y repartidor en la
  misma respuesta — ninguna de las tres pantallas llama a `sales` ni a
  `rrhh` por su cuenta, mismo criterio que ya fijó `GET /delivery/mi/rutas`
  en la PWA del repartidor. Costo aceptado: el tablero no reordena
  paradas de una ruta ya creada ni fuerza iniciar/finalizarla a mano —
  eso lo sigue haciendo el repartidor desde su teléfono
  (`docs/roadmap/deuda/modulo-delivery.md`).
