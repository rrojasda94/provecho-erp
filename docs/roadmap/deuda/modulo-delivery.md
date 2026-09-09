# Deuda técnica — Módulo delivery (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

Declarada de entrada (2026-09-09, ADR-098), antes de escribir el primer
slice de código — costos aceptados explícitamente al fijar el alcance del
MVP, para que no se descubran a mitad de una auditoría:

- ⬜ **La PWA del repartidor no funciona offline.** Instalable
  (`manifest.webmanifest`) pero sin service worker: sin señal, no carga
  la ruta ni encola los pings de posición o la confirmación de entrega.
  ADR-013 ya decidió PWA/responsive y no app nativa; un service worker con
  cola de reintento es la siguiente pieza cuando la cobertura en zona de
  reparto lo justifique.
- ⬜ **El ETA no se recotiza contra Google en ruta**, solo con
  haversine/velocidad media desde el último ping. Barato y suficiente para
  la parada siguiente; re-consultar `computeRouteMatrix` cada pocos
  minutos daría un ETA más fino a costo de una llamada paga por ping.
- ⬜ **La evidencia de entrega vive en la fila** (`entrega.evidencia_foto`,
  `LargeBinary` deferred, base64 acotado, purga por Celery beat), mismo
  tratamiento que `rrhh.marcacion.foto`. No hay ruta de subida a S3 real
  en el proyecto (`Archivo` solo guarda metadatos, el cliente pone la
  URL) — migrar cuando exista.
- ⬜ **Sin liquidación de repartidores.** `delivery.ruta_finalizada` se
  publica con distancia y duración pero hoy nadie lo consume; pago por
  entrega, comisión o planilla del repartidor queda fuera de este slice.
- ⬜ **Zonas de reparto siguen sin polígono** (mismo ítem que
  `docs/roadmap/deuda/modulo-sales.md`: `zona_servicio` con geocerca real
  está especificada en `data-model.md` §1b y no implementada). `delivery`
  rutea por coordenada punto a punto, no por zona.
- ⬜ **Sin push en tiempo real.** Tablero de despacho, PWA del repartidor y
  enlace público de seguimiento son todos polling (10-15 s), mismo criterio
  que el KDS (`docs/roadmap/deuda/modulo-sales.md`: "KDS tiempo real").
  Cuando se resuelva el push para uno, conviene resolverlo para los tres a
  la vez — es la misma infraestructura (Redis pub-sub/WebSocket).
- ⬜ **Un repartidor propio no puede llevar la ruta de otra sucursal en el
  mismo turno.** El scope de `delivery.repartir` es por ruta propia, no
  hay reparto cruzado entre locales cercanos. No es un caso pedido hoy.
