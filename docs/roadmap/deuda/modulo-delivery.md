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

- ✅ **El tablero no reordena, agrega ni quita paradas de una ruta ya
  creada.** Cerrada 2026-09-17 (ADR-101): `ruta-dialogo.tsx` edita una
  ruta `planificada` o `en_curso` (agregar/quitar paradas no resueltas,
  cambiar repartidor) desde el propio tablero.
- ✅ **El despacho no puede forzar iniciar/finalizar una ruta desde el
  tablero.** Cerrada 2026-09-17 (ADR-101): `tarjeta-ruta.tsx` ofrece
  Iniciar (deshabilitado si alguna parada sigue en cocina), Finalizar y
  "Marcar entregada" por parada, además de Cancelar.
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

Declarada al construir el slice 6 (notificaciones por WhatsApp):

- ⬜ **El "contacto de la sucursal" de la plantilla `entrega_fallida` es
  solo su nombre, nunca un teléfono.** `Sucursal` no tiene columna de
  teléfono ni existe un contrato público que la resuelva — cuando exista,
  la plantilla puede pasar a un contacto real en vez de "el local".
- ⬜ **El ETA que viaja en la plantilla `pedido_en_camino` es el mismo
  heurístico de `entrega.eta_at`** (deuda ya declarada arriba: "no se
  recotiza contra Google en ruta"), redondeado a minutos enteros contra el
  momento del envío — no se vuelve a recalcular si el aviso se reintenta
  varios minutos después.
- ⬜ **Un rechazo de Meta (`aviso_error`) no tiene pantalla propia.** Queda
  en la fila de la entrega y se ve en el historial (`GET
  /delivery/entregas`), pero nada resalta "este aviso falló" en el
  tablero — el despachador tiene el enlace copiable como red de
  seguridad, pero no una alerta activa.

Declarada al construir ADR-101 ("el KDS despacha, el repartidor entrega"):

- ⬜ **La encuesta de satisfacción de `marketing` puede salir antes de que
  el pedido llegue de verdad.** Se dispara con `sales.venta_entregada`
  (ADR-021), que ahora puede publicarse al despachar desde el KDS —antes
  de que el repartidor confirme la entrega en la puerta— para un pedido
  delivery. No es un bug nuevo (la encuesta siempre escuchó ese evento):
  es que ADR-101 hizo más frecuente que "despachado" y "entregado de
  verdad" sean momentos distintos para delivery. Mover el trigger de la
  encuesta a `delivery.entrega_registrada` para modalidad delivery
  específicamente exigiría que `marketing` conociera `delivery`, o un
  contrato de lectura nuevo — no se resolvió acá.
- ⬜ **Replanificar lo pendiente de una ruta `en_curso` no modela una
  eventual vuelta al local.** `_origen_de_ruta` parte de la última
  posición del repartidor (o de la sucursal si todavía no pingueó);
  correcto para agregar una parada en el camino, pero si el despacho
  agrega un pedido que en la práctica exige pasar antes por el local
  (recoger algo, por ejemplo), el ETA no lo refleja — asume que el
  repartidor va directo.
- ⬜ **Una entrega `fallida` sigue sin acción en el tablero.**
  `POST /entregas/{id}/reintentar` y `.../cerrar` existen desde el slice
  6 pero ninguna pantalla los llama (ni el historial, ni la tarjeta de
  ruta) — con rutas ahora más fáciles de dejar `finalizada` con paradas
  fallidas, la ausencia de esta UI pesa más que antes.
