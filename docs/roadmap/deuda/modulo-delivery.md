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

Declarada al construir el slice 4 (PWA del repartidor):

- ⬜ **Los íconos de `public/reparto/manifest.webmanifest` son un
  cuadrado de color, no diseño de marca.** Se generaron localmente (sin
  herramienta de diseño a mano en ese momento) solo para que el manifiesto
  tenga íconos válidos de 192/512 y la PWA sea instalable — cambiarlos por
  el ícono real de Provecho/Majambo es una tarea de diseño, no de código.

Declarada al construir el slice 5 (tablero de despacho):

- ⬜ **El tablero no reordena, agrega ni quita paradas de una ruta ya
  creada** (`PUT /delivery/rutas/{id}/paradas` existe y lo usa el backend
  al reintentar, pero no hay diálogo de "editar ruta" en
  `app/(app)/delivery/`). Hoy, para cambiar una ruta planificada, se
  cancela y se crea de nuevo.
- ⬜ **El despacho no puede forzar iniciar/finalizar una ruta desde el
  tablero**, aunque el permiso lo permite (`delivery.despachar` alcanza
  para `POST .../iniciar|finalizar`, no solo el repartidor dueño):
  `tarjeta-ruta.tsx` solo ofrece "Cancelar". Sirve para el caso normal
  —el repartidor inicia y finaliza desde la PWA— pero no para un
  teléfono sin batería o una ruta que hay que cerrar a mano.
- ⬜ **`tablero.rutas_vivas` y `entregas.historial_enriquecido` resuelven
  la venta y el repartidor de cada fila con una llamada aparte** (N+1):
  barato con pocas rutas vivas y una página de historial acotada
  (`page_size` máx. 100), pero una consulta agregada sería más liviana si
  el volumen crece. Mismo costo que ya aceptó `mi_reparto.ruta_con_paradas`
  en el slice 4.
- ⬜ **El mapa de una ruta (`mapa-rutas.tsx`) no dibuja el trazo del
  ruteo heurístico**, solo el de Google (`ruta.polyline`, que la
  heurística nunca calcula). Se ven los pines numerados igual, sin la
  línea entre ellos — una polilínea aproximada por distancia en línea
  recta sería confusa (no es la calle real) y se prefirió no dibujar
  nada antes que dibujar algo falso.
