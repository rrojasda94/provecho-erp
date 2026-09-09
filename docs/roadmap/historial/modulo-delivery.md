# Historial — Módulo `delivery`

Estado vigente: 🔶 En curso — slices 2 a 5 implementados (2026-09-09,
ADR-098): repartidores propios, el ciclo completo de una ruta (crear con
ruteo real contra Google o heurístico, editar paradas, iniciar, entregar
o fallar cada parada, reintentar o cerrar la fallida, finalizar o
cancelar), GPS del repartidor en ruta, el enlace público de seguimiento
con mapa en vivo, la PWA instalable del repartidor (`/reparto`) y el
tablero de despacho en el frontend del ERP (`/delivery`), con la
convergencia por evento hacia y desde `sales` en los dos sentidos. Falta
el aviso automático por WhatsApp (ver
`docs/roadmap/deuda/modulo-delivery.md`).

## Cronología

### 2026-09-09 — Especificación del reparto propio (ADR-098)

Se decidió separar el reparto propio de `sales` como módulo nuevo, tal
como preveía `docs/domain/workflows.md` desde 2026-07-27: *"Si el reparto a
domicilio llega a tener ruteo, flota propia y liquidación de repartidores,
se separa entonces como versión MAYOR."* La entidad `entrega` estaba
especificada como "pendiente de slice" en `data-model.md` desde la misma
fecha (ADR-053/054) y documentada como deuda en `docs/roadmap/deuda/
modulo-sales.md`: sin ella, una entrega fallida no se podía registrar.

Alcance acordado con el usuario (MVP completo, no incremental): entidad
`entrega` con trazabilidad de repartidor propio, `ruta_reparto` con varias
paradas optimizadas contra Google Routes (fallback heurístico si Google no
responde), GPS del repartidor durante la ruta, enlace público de
seguimiento con mapa en vivo, aviso automático al cliente por plantillas
de WhatsApp con fallback de enlace copiable, y entrega fallida con motivo
y evidencia fotográfica.

Decisión de integración (ADR-098): `delivery` nunca importa el dominio de
`sales` — avanza la venta a entregada publicando `delivery.entrega_registrada`,
que un listener nuevo de `sales` traduce a la misma
`cumplimiento.registrar_entrega` que ya usa el botón "Entregar" del KDS.
Lee la venta por dos contratos públicos nuevos de `sales`
(`venta_para_reparto`, `ventas_listas_para_reparto`), nunca por join
directo.

Documentación escrita en este slice: README del módulo, ADR-098,
`data-model.md` §6b, filas nuevas en `events.md` (4 eventos propios + 2
consumos de `sales` + 4 contratos públicos de lectura), RN-DLV-001 a 008
en `business-rules.md`, sección "Reparto propio" en `state-machines.md`,
nota de cierre en `workflows.md`, entradas de glosario, filas en
`ROADMAP.md` y `docs/product/modules.md`.

Slices de implementación planeados (ver `docs/roadmap/deuda/modulo-delivery.md`
para lo que queda deliberadamente fuera de cada uno): (2) backend core —
modelos, migración, repartidores/rutas/entregas, listeners con `sales`, 7
registros de activación; (3) ruteo real contra Google, GPS y el enlace
público de seguimiento; (4) PWA del repartidor; (5) tablero de despacho en
el ERP; (6) notificaciones por WhatsApp.

### 2026-09-09 — Slice core: repartidores, tablero y ciclo de ruta/entrega

Backend del slice 2 completo: cuatro tablas (`repartidor`, `ruta_reparto`,
`entrega`, `posicion_repartidor` — esta última sin uso todavía, reservada
para el GPS del slice siguiente), migración `69f4ca1d58f4` generada por
autogenerate y verificada con `alembic check` + ciclo `downgrade base` /
`upgrade head` contra Postgres real.

Los dos contratos de lectura de `sales` (`venta_para_reparto`,
`ventas_listas_para_reparto`) y de `rrhh` (`trabajadores_con_cuenta`,
`cuenta_de_trabajador`) quedaron implementados tal como los especificó
ADR-098. La convergencia por evento funciona en los dos sentidos:
`sales/application/listeners.py` ganó `session_factory` y un handler de
`delivery.entrega_registrada` que llama a la misma
`cumplimiento.registrar_entrega` del botón "Entregar" del KDS;
`delivery/application/listeners.py` escucha `sales.venta_entregada` (cierra
una entrega abierta si el KDS se adelantó) y `sales.venta_anulada`
(RN-DLV-006).

Decisión de implementación no anticipada en el ADR: el ruteo se apoya en
`Coordenada` de `shared/integrations/google` en vez de un tipo propio —
son el mismo punto (lat, lng), y así el slice de ruteo real no tiene que
traducir nada al conectar `computeRoutes`. También se prefirió mapear
"dirección sin anclar" y demás violaciones de RN-DLV a `ReglaNegocio`
(409), no a un 422 aparte: es el mismo criterio HTTP que ya usa el resto
del ERP para una regla de negocio (422 queda reservado para lo que
rechaza Pydantic antes de llegar al caso de uso).

Colisión de nombre resuelta antes de exportar el contrato: el schema
`EntregaOut` de `delivery` chocaba con el ya existente de `sales`
(la respuesta de `POST /sales/ventas/{id}/entrega`); se renombró a
`EntregaRepartoOut` en vez de dejar que FastAPI recalifique el de `sales`
con su ruta completa — mover el nombre de un contrato ya publicado es más
disruptivo que nombrar bien el nuevo.

Pruebas: `tests/test_delivery_rules.py` (18 casos, dominio puro) y
`tests/test_delivery.py` (23 casos de integración vía `TestClient`,
incluida la cadena completa iniciar → entregar → `sales.venta_entregada`,
y el camino inverso KDS → cierra la entrega de `delivery`). Suite completa
verde en SQLite (2453 pruebas), `ruff` limpio, `alembic check` sin
diferencias, contrato OpenAPI regenerado.

### 2026-09-09 — Slice 3: ruteo real, GPS y seguimiento público

`shared/integrations/google/rutas.py` ganó `ruta_optima()` contra
`computeRoutes` con `optimizeWaypointOrder`: pide el orden y la ruta
completa (con polilínea) saliendo del local y volviendo a él, misma
doctrina de clave-en-servidor que `distancia_km`. `application/ruteo.py`
la intenta primero cuando la ruta pide `optimizar=true` y hay más de una
parada; cualquier fallo (`RutasError`, sin clave) cae a la heurística
vecino-más-cercano sin romper la creación de la ruta —
`ruta.optimizada_por` queda registrando cuál de las dos se usó.

GPS: `POST /rutas/{id}/posiciones` (`application/posiciones.py`) acepta
un ping solo con la ruta `en_curso` y del repartidor dueño; guarda el
trazo (`posicion_repartidor`), actualiza `ruta.ultima_*` y recalcula por
haversine el ETA de la siguiente parada sin resolver — sin volver a
consultar a Google en cada ping (deuda declarada: re-cotización).

Seguimiento público: `application/seguimiento.py` + `api/publico_routers.py`
exponen `GET /delivery/publico/seguimiento/{token}` sin autenticación,
con el mismo criterio de token anónimo y 404 uniforme que
`marketing/api/publico_routers.py`. La respuesta (`SeguimientoOut`) es
deliberadamente mínima (RN-DLV-008): estado traducido a cuatro valores
públicos, ETA, primer nombre del repartidor, su última posición solo
mientras la entrega está `en_ruta`, destino y una línea de tiempo — nunca
monto, teléfono, dirección en texto ni las demás paradas de la salida
(no lleva polilínea). El token se genera al asignar la entrega a una ruta
y expira `delivery_seguimiento_vigencia_horas` después de resolverse.
Purga de posiciones y de evidencia por Celery beat
(`application/tasks.py`, `delivery_posiciones_retencion_dias` y
`delivery_evidencia_retencion_dias`).

Bug encontrado y corregido en el mismo cambio: comparar
`entrega.token_expira_at` (aware) contra `datetime.now(UTC)` revienta en
SQLite porque la columna vuelve sin zona tras el `commit` — mismo defecto
que ya resolvía `sales.domain.rules._sin_zona`; se replicó el mismo
parche en `seguimiento.py`.

Frontend: `app/(publico)/seguimiento/[token]/` (Server Component +
Server Action sin token, igual que `postular/[token]/`; sondeo cada 10 s
que se apaga solo al llegar a un estado final; mapa con dos marcadores
—repartidor y destino— usando `cargarMaps`/`useConfigMapas`, degradado a
solo texto sin clave de Google) y `lib/geo.ts` (Haversine que espeja
`shared/ubicacion.py::metros_entre`, y el decodificador de
`encodedPolyline` para cuando el tablero de despacho del slice 5 dibuje
la ruta).

Pruebas: `tests/test_google_rutas.py` (12 casos, `ruta_optima` con httpx
parcheado), `tests/test_delivery_seguimiento.py` (7 casos: claves exactas,
posición solo en `en_ruta`, 404 uniforme, `Cache-Control: no-store`),
casos nuevos en `tests/test_delivery.py` (ping GPS, fallback de Google) y
`tests/test_delivery_rules.py` (`eta_desde`), y `lib/geo.test.ts` en el
frontend. Suite completa verde en SQLite y contra Postgres real
(ADR-097), `ruff` y `eslint` limpios, `alembic check` sin diferencias,
contrato OpenAPI regenerado.

### 2026-09-09 — Slice 4: la PWA del repartidor

`GET /delivery/mi/rutas` cambió de forma: antes devolvía `RutaOut` sin
paradas (útil para el tablero, inútil para un repartidor que necesita
saber a qué puerta va y con quién habla). Ahora es una vista propia
(`application/mi_reparto.py`, `MiRutaOut`/`MiParadaOut`) que arma, para
cada ruta viva del repartidor, sus paradas ya resueltas contra la venta
(`sales.venta_para_reparto`) y el contacto del cliente
(`sales.venta_para_reparto` no traía nombre ni teléfono — se sumó
`contacto_de_cliente`, ya existente para la encuesta de `marketing`, y
un campo `total` nuevo en `venta_para_reparto` para el "monto a cobrar"
cuando la venta sigue `orden`, sin pagar). Es la única llamada que hace
la PWA: no le pide nada aparte a `sales` ni a `rrhh`.

Frontend nuevo: `app/reparto/` (pantalla completa fuera del shell, mismo
criterio ADR-013 que el PDV y el KDS) con `page.tsx` (sesión y permiso
`delivery.repartir` en el servidor), `reparto-cliente.tsx` (sondeo de
`mi/rutas` cada 15 s, pausado con la pestaña oculta), `ruta-cliente.tsx`
(iniciar/finalizar la ruta, lista de paradas con "Llamar"/"Navegar"/
"Entregado"/"No se pudo"), `parada-dialogo.tsx` (confirmar entrega o
registrar el motivo del fallo, con foto y ubicación opcionales),
`use-gps.ts` (`watchPosition` con el mismo throttle que exige el
servidor: un ping cada 10 s como mínimo, y solo si se movió 30 m) y
`use-wake-lock.ts` (pantalla encendida mientras la ruta está en curso,
se libera y se vuelve a pedir sola al volver de segundo plano).

Instalable: `public/reparto/manifest.webmanifest`, con dos íconos
PNG generados localmente (no hay diseño de marca para la PWA todavía —
un cuadrado con el color primario del ERP, deuda de diseño declarada)
y `metadata.manifest` en `page.tsx`. Sin service worker (ADR-013): offline
sigue como deuda declarada desde la especificación del módulo.

Reutilizado sin duplicar: `lib/camara.ts` ganó un parámetro
(`camara: "user" | "environment"`) para que `capturarFoto` sirva también
para la evidencia de una entrega —cámara trasera, la puerta y no la cara
de quien entrega— sin bifurcar el código que ya usaba `rrhh.marcacion`;
`lib/geo.ts::distanciaMetros` (slice 3) resuelve el throttle de
`use-gps.ts`; `RegionDeAviso` y el `<dialog>` nativo (mismo patrón que
`app/pdv/dialogos.tsx`) evitan reinventar el aviso pasajero y el diálogo
modal de una tercera pantalla táctil.

Se agregó `lib/modulos.ts`: ficha "Mi reparto" (`/reparto`, ícono `Bike`)
con permiso exacto `delivery.repartir` — no por prefijo `delivery.`, para
que un despachador con `delivery.despachar` no la vea también.

Pruebas: `tests/test_delivery.py` ganó dos casos de integración para
`mi/rutas` (paradas con venta y cliente resueltos, monto en `None` cuando
la venta ya se pagó). El flujo completo de la PWA (tablero → asignar →
iniciar desde el teléfono → entregar/fallar → enlace público) queda para
el Playwright `uso/delivery-reparto.spec.ts` de la especificación
original, que necesita el tablero del slice 5 para tener con qué crear
una ruta desde la UI — se escribe entonces. Suite completa verde en
SQLite, `ruff`/`eslint`/`tsc` limpios, `npm run build` sin advertencias
nuevas, contrato OpenAPI regenerado.

### 2026-09-09 — Slice 5: el tablero de despacho en el ERP

`app/(app)/delivery/` — a diferencia de la PWA y del enlace público, este
sí vive dentro del shell (ADR-013 reserva la pantalla completa para lo
que se opera de pie; despachar es trabajo de escritorio). Mismo patrón de
sondeo que el resto de pantallas operativas: `use-tablero.ts` copia el
criterio de `app/kds/use-cola.ts` (10 s, pausado con la pestaña oculta),
`tablero-cliente.tsx` arma "sin asignar" y "rutas vivas"
(`tarjeta-ruta.tsx` por ruta, con el mapa opcional de `mapa-rutas.tsx`),
`nueva-ruta-dialogo.tsx` crea la ruta eligiendo repartidor y pedidos con
`Dialog`/`sonner` (no `DialogoFormulario`+Server Action: un tablero en
vivo con mutaciones frecuentes encaja mejor con el patrón cliente que ya
usa `components/reportes/tablero.tsx`, no con el de un formulario CRUD
de una sola pantalla). `repartidores/` y `entregas/` son las otras dos
pantallas del submenú: alta/edición de repartidores y el historial
paginado (server-driven, mismo criterio que `app/(app)/auditoria/page.tsx`
— filtros y paginación por `searchParams`, no `TablaDatos`) con la
evidencia fotográfica en un diálogo.

Tres endpoints salieron insuficientes al construir la UI y se
enriquecieron en el mismo cambio, todos con el mismo criterio que ya
había fijado `mi/rutas` en el slice 4 (no forzar a la pantalla a resolver
nombres por su cuenta):

- `GET /delivery/tablero` devolvía `rutas: list[RutaOut]`, sin nombre de
  repartidor ni paradas — inútil para un despachador que necesita saber
  quién lleva qué. Ahora comparte la misma vista compuesta que
  `mi/rutas` (`mi_reparto.ruta_con_paradas`, renombrado de
  `_con_paradas` porque dejó de ser privado de un solo caso de uso), con
  `repartidor_nombre` sumado. Los esquemas se renombraron en el mismo
  cambio: `MiRutaOut`/`MiParadaOut` → `RutaConParadasOut`/
  `ParadaRepartoOut` — nombres que ya no tienen sentido "en primera
  persona" cuando el tablero de despacho los usa igual.
- `GET /delivery/repartidores` (y la respuesta de crear/editar) no traía
  el nombre del repartidor, solo `trabajador_id`/`usuario_id`: elegir
  repartidor en el diálogo de "nueva ruta" por UUID no es una opción.
  `repartidores.con_nombre` lo resuelve vía `rrhh.cuenta_de_trabajador`,
  igual que ya hacía el alta.
- `GET /delivery/entregas` (historial) tampoco traía número de orden,
  dirección ni nombre del cliente — `entregas.historial_enriquecido`
  reenvuelve la página de `paginar()` resolviendo cada fila contra
  `sales.venta_para_reparto`/`contacto_de_cliente` y el repartidor, mismo
  patrón. `EntregaRepartoOut` ganó los cuatro campos como opcionales
  (`None` por defecto): la respuesta inmediata de entregar/fallar/
  reintentar/cerrar no los resuelve, porque quien la recibe ya sabe a
  quién le acaba de pasar.

Bug de scanner encontrado al escribir `lib/delivery.ts`: las llamadas con
filtros opcionales armaban la query string con un helper
(`` `/delivery/tablero${query({...})}` ``) que no dejaba un `?` literal
en el código fuente. `lib/contrato.test.ts` corta la ruta escaneada en el
primer `?` del texto tal cual aparece en el archivo — sin uno literal,
capturaba la llamada a `query(...)` entera como si fuera la ruta y no
encontraba nada en el contrato. Se corrigió sacando el `?` del helper y
escribiéndolo en cada plantilla (`` `/delivery/tablero?${query(...)}` ``).

Test descubierto y esquivado, no arreglado: `lib/rutas.test.ts` asume que
cualquier `page.tsx` de módulo con un `redirect(` en el cuerpo es un stub
que solo redirige a `modulo.href` (el patrón de `catalogo`, `compras`,
`inventario`, `organizacion`, `rrhh`), y falla si ese `href` es la propia
raíz. El tablero de despacho vive en su propia raíz (`/delivery`) y tenía
un `redirect("/login")` legítimo para una sesión que vence entre dos
`apiFetch` — nada que ver con el patrón que el test vigila, pero
disparaba el mismo aviso. Se sacó ese `redirect` (la sesión vencida cae
en el mensaje genérico de error, y recargar la página ya pasa por
`obtenerSesion()`, que redirige sola) en vez de tocar un test compartido
por una excepción de un solo módulo.

Reutilizado sin duplicar: `ETIQUETA_ESTADO_ENTREGA` (antes triplicado
entre `app/reparto/ruta-cliente.tsx`, `tarjeta-ruta.tsx` y el historial,
cada uno con su propio texto) pasó a `lib/delivery.ts`, la misma fuente
que ya reexporta `apiDelivery`.

Pruebas: `tests/test_delivery.py` ganó tres casos (tablero con repartidor
y paradas resueltos, `listar_repartidores` con el nombre, historial de
entregas con venta y repartidor resueltos). Suite completa verde en
SQLite (2489 pruebas) y contra Postgres real (ADR-097), `ruff`/`eslint`/
`tsc` limpios, `npm run build` sin advertencias nuevas, contrato OpenAPI
regenerado.

### 2026-09-09 — Slice 6: notificaciones por WhatsApp

`application/notificaciones.py::despachar(session, entrega_id, hito)` —
mismo patrón que `marketing.application.envios.despachar` sobre el mismo
adaptador (`shared/integrations/whatsapp`), delivery es su segundo
consumidor: resuelve el teléfono vía `sales.contacto_de_cliente`, arma
los parámetros de la plantilla del hito (`en_camino`/`entregado`/
`fallida`) y manda `WhatsAppClient.enviar_plantilla`. Un
`WhatsAppRechazo` (4xx de Meta) se absorbe y queda en
`entrega.aviso_error` sin reintentar — reenviar el mismo payload da el
mismo rechazo; un fallo de transporte (`WhatsAppError`) propaga para que
la tarea reintente. `entrega.aviso_en_camino_at`/`aviso_resultado_at`/
`aviso_error` ya existían en el modelo desde la migración del slice 2:
se fijaron entonces, a propósito, para no deber una migración nueva acá.

`application/tasks.py` ganó `delivery.notificar_cliente` (bind,
`autoretry_for=(WhatsAppError,)`, backoff 60 s, 4 reintentos — copia
literal de `marketing.despachar_encuesta`) y `encolar_aviso(entrega_id,
hito)`: no hace nada sin WhatsApp configurado o en un hub de sucursal
(ADR-009, ahí no corre Celery y la mensajería sale siempre de la nube),
y si el broker no responde manda en línea antes que perder el aviso — el
llamador ya está fuera del request de nadie. `application/listeners.py`
se escucha a sí mismo por primera vez en `delivery` (mismo patrón que
`marketing.on_encuesta_enviada`): `ruta_iniciada` encola "en camino" por
cada parada, `entrega_registrada` encola "entregado",
`entrega_fallida` encola "fallida" — los tres después del commit
(ADR-016), y un fallo acá no puede deshacer lo que ya pasó, solo se
loguea.

In-app (`users.notificar_a`, sin envío, siempre en la bandeja): al
repartidor cuando `rutas.crear` le asigna una ruta, y a quien la creó
(`ruta.creada_por`) si una parada falla o si la venta de una entrega ya
`en_ruta` se anula (RN-DLV-006) — antes ese caso no avisaba a nadie, la
entrega simplemente se quedaba `en_ruta` sin que el despacho se enterara
de que la venta detrás ya no existía.

El tablero ganó el fallback que la spec pedía desde el slice 1:
`GET /delivery/tablero` ahora resuelve `enlace_seguimiento` por parada
(`mi_reparto._parada_de`, mismo enlace que recibe el cliente) y
`whatsapp_habilitado` a nivel de respuesta — `tarjeta-ruta.tsx` muestra,
en cada parada `en_ruta`, un botón "Copiar enlace" y, si hay teléfono,
"Enviar por WhatsApp" (`aviso-parada.tsx`, `wa.me` armado con
`enlaceWhatsApp` en `lib/delivery.ts`, mismo criterio de normalización
que `whatsapp.client.normalizar_telefono`) con una nota cuando el envío
automático no está configurado. El enlace siempre está — el aviso
automático es un atajo, nunca la única vía.

Pruebas: `tests/test_delivery_notificaciones.py` (nuevo, `ClienteWhatsAppFalso`
de `tests/test_marketing_encuestas.py`, `task_always_eager`): ruta
asignada notifica in-app al repartidor, cada hito manda su plantilla con
los parámetros esperados, sin teléfono deja `aviso_error="sin_telefono"`
sin reventar, un `WhatsAppRechazo` no reintenta y queda escrito, sin
WhatsApp configurado o en un hub no encola nada, entrega fallida avisa
por WhatsApp y notifica in-app a quien creó la ruta, y una venta anulada
con la entrega ya `en_ruta` notifica sin cancelarla. Bug encontrado y
corregido en el mismo cambio: la primera versión de
`despachar_notificacion` y `_enviar_en_linea` llamaban a
`notificaciones.despachar` sin `session.commit()` — el envío funcionaba
(la plantilla salía) pero `aviso_en_camino_at`/`aviso_error` nunca
quedaban en la fila porque la sesión de la tarea se cerraba sin guardar;
lo agarró el propio test de "sin teléfono" al releer la entrega con una
sesión nueva. Se corrigió con un `_despachar()` interno que comitea,
mismo patrón que ya usa `marketing.application.tasks`. Suite completa
verde en SQLite (2499 pruebas) y contra Postgres real (ADR-097),
`ruff`/`eslint`/`tsc` limpios, `npm run build` y `npm test` (499 casos)
sin advertencias nuevas, contrato OpenAPI regenerado.
