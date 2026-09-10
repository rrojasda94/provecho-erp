- **El reparto propio calcula rutas de verdad y el cliente las sigue en un
  mapa** (ADR-098, slice 3): crear una ruta con `optimizar=true` ahora le
  pide el orden y la ruta —con polilínea— a Google Routes
  (`computeRoutes` + `optimizeWaypointOrder`), y cae sola a la heurística
  vecino-más-cercano si no hay clave o Google falla, sin romper la
  creación. El repartidor manda su posición en ruta
  (`POST /rutas/{id}/posiciones`), que actualiza el trazo GPS y el ETA de
  la siguiente parada. El cliente ve todo eso por un enlace público sin
  cuenta (`GET /delivery/publico/seguimiento/{token}`): estado, ETA,
  primer nombre del repartidor, su posición mientras está en camino y una
  línea de tiempo — nunca monto, teléfono, dirección en texto ni las
  demás paradas de la salida (RN-DLV-008). Token anónimo con expiración a
  las pocas horas de resolverse la entrega, 404 uniforme para inexistente
  o vencido, purga de posiciones y evidencia por Celery beat. Costo
  aceptado: el ETA en ruta no se recotiza contra Google (solo la parada
  siguiente, por haversine); la PWA del repartidor y el tablero del ERP
  quedan para los próximos slices (`docs/roadmap/deuda/modulo-delivery.md`).
