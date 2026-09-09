- **El repartidor propio tiene su PWA** (ADR-098, slice 4): en `/reparto`
  ve sus rutas vivas con cada parada ya resuelta (dirección, cliente,
  teléfono, monto a cobrar si la venta sigue sin pagar), inicia la ruta,
  llama o navega a cada parada, confirma la entrega o registra por qué no
  se pudo —con foto y ubicación opcionales— y finaliza cuando todo quedó
  resuelto. El GPS se manda solo mientras la ruta está en curso (throttle
  de 10 s/30 m) y la pantalla se mantiene encendida con la Wake Lock API.
  Instalable, sin service worker: offline queda como deuda ya declarada
  en la especificación del módulo. `GET /delivery/mi/rutas` cambió de
  forma para traer las paradas resueltas en la misma respuesta — la PWA
  no llama a `sales` ni a `rrhh` por su cuenta.
