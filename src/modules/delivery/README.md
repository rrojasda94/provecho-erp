# Módulo `delivery` — Reparto propio

## Objetivo

Llevar el pedido delivery desde que sale de cocina hasta la puerta del
cliente: asignar repartidores propios a una ruta con varias paradas,
calcular esa ruta y su ETA, registrar la entrega (o el fallo, con motivo y
evidencia), avisar al cliente por WhatsApp cuando el pedido sale y cuando
llega, y darle un enlace público donde vea el estado de su pedido y —
mientras el repartidor va en camino— su posición en el mapa.

No reemplaza nada de `sales`: la venta, su cotización de reparto por
kilómetro (ADR-054/068) y la dirección anclada al mapa (ADR-053/072) siguen
siendo de `sales`. `delivery` empieza donde `sales` marca el pedido `listo`
y termina donde `sales` lo marca `entregado` — pero ese último paso lo
dispara `delivery` por evento, nunca importando el dominio de `sales`
(ADR-098).

## Entidades

`repartidor` (trabajador propio con cuenta y vehículo), `ruta_reparto`
(una salida con una o más paradas, estado y posición en vivo), `entrega`
(una por venta, con su historial de intentos, resultado y evidencia),
`posicion_repartidor` (el trazo GPS de una ruta en curso). Detalle en
`docs/architecture/data-model.md` §6b.

## Estado (slice 5 implementado 2026-09-09, ADR-098)

Operativo en `/api/v1/delivery`: alta y edición de repartidores propios,
tablero de despacho, ciclo completo de una ruta (crear con ruteo real u
heurístico → editar paradas → iniciar → entregar/fallar cada parada →
reintentar o cerrar la fallida → finalizar o cancelar), evidencia
fotográfica, GPS del repartidor en ruta, seguimiento público con mapa, y
la convergencia por evento con `sales` en los dos sentidos
(`delivery.entrega_registrada` marca la venta entregada;
`sales.venta_entregada`/`venta_anulada` cierran o cancelan la entrega).
Capas `domain/rules.py`, `application/` (`repartidores.py`, `rutas.py`,
`ruteo.py`, `posiciones.py`, `entregas.py`, `seguimiento.py`, `tablero.py`,
`parametros.py`, `listeners.py`, `tasks.py`), `infrastructure/`,
`api/routers.py`, `api/publico_routers.py`. Migración `69f4ca1d58f4`
aplicada. Frontend: `app/(publico)/seguimiento/[token]/` (página pública
con mapa y línea de tiempo, sondeo cada 10 s) y `lib/geo.ts` (Haversine y
decodificador de polilínea).

`application/ruteo.py` intenta primero `computeRoutes` con
`optimizeWaypointOrder` (`shared/integrations/google/rutas.py::ruta_optima`)
cuando hay más de una parada, la creación pide optimizar y hay clave de
Google configurada; si Google no responde o no hay clave, cae a la
heurística vecino-más-cercano sin romper la operación (`optimizada_por`
registra cuál de las dos se usó). Cada ping GPS (`POST
/rutas/{id}/posiciones`) actualiza el trazo (`posicion_repartidor`), la
última posición de la ruta y el ETA heurístico de la siguiente parada sin
resolver. Los pings y las posiciones expuestas se purgan por Celery beat
(`delivery_posiciones_retencion_dias`, `delivery_evidencia_retencion_dias`).

`GET /delivery/mi/rutas` y `GET /delivery/tablero` no son un espejo de
`RutaOut`: las dos comparten una vista compuesta
(`application/mi_reparto.py::ruta_con_paradas`, esquema
`RutaConParadasOut`/`ParadaRepartoOut`) con cada parada ya resuelta contra
la venta (`sales.venta_para_reparto`) y el cliente
(`sales.contacto_de_cliente`) — dirección, nombre, teléfono y el monto a
cobrar si la venta sigue `orden` (sin pagar) — y, en el tablero, el
nombre del repartidor (`rrhh.cuenta_de_trabajador`). Ni la PWA ni el
tablero llaman a `sales` ni a `rrhh` por su cuenta. `GET
/delivery/repartidores` y `GET /delivery/entregas` (historial) resuelven
el mismo tipo de nombre por el mismo camino
(`repartidores.con_nombre`, `entregas.historial_enriquecido`).

Frontend: `app/reparto/` (pantalla completa fuera del shell, como el PDV
y el KDS — ADR-013) con `use-gps.ts` (GPS en vivo mientras la ruta está
en curso, con el mismo throttle 10 s/30 m que el backend acepta) y
`use-wake-lock.ts` (pantalla encendida durante la ruta). Instalable
(`public/reparto/manifest.webmanifest`), sin service worker: offline
queda declarado como deuda (ADR-013). `app/(app)/delivery/` es el
tablero de despacho, dentro del shell (ADR-013 reserva la pantalla
completa para lo que se opera de pie): tablero con sondeo cada 10 s
(`use-tablero.ts`, mismo criterio que `app/kds/use-cola.ts`), crear ruta,
cancelar una `planificada`, el mapa de cada ruta con su polilínea real
cuando se optimizó con Google (`mapa-rutas.tsx`), alta y edición de
repartidores, e historial de entregas paginado con la evidencia
fotográfica.

**Sin avisos todavía**: no hay plantillas de WhatsApp ni tareas de envío
— eso es un slice aparte. Ver `docs/roadmap/deuda/modulo-delivery.md` y
el orden de slices en `docs/roadmap/historial/modulo-delivery.md`.

### Casos de uso

- **Alta de repartidor**: elegir un trabajador activo con cuenta propia
  (`rrhh.trabajadores_con_cuenta`) que aún no sea repartidor, y darle
  vehículo y sucursal.
- **Tablero de despacho**: ver los pedidos delivery ya listos sin asignar
  (`sales.ventas_listas_para_reparto`) y las rutas en curso con su última
  posición conocida.
- **Crear una ruta**: elegir repartidor y uno o más pedidos; con
  `optimizar=true` el servidor pide el orden y la ruta a Google
  (`ruta_optima`) y cae a la heurística vecino-más-cercano si no hay
  clave o Google falla; calcula distancia y ETA por parada.
  `PUT .../paradas` reemplaza el conjunto de una ruta que no salió todavía.
- **Iniciar / finalizar / cancelar una ruta**.
- **Registrar un ping GPS** (`POST .../posiciones`) mientras la ruta está
  en curso: guarda el trazo y refresca el ETA de la próxima parada.
- **Entregar / fallar una parada**, con ubicación y foto opcional; un
  fallo pide motivo (y detalle si es "otro").
- **Reintentar o cerrar** una entrega fallida.
- **Seguir el pedido por el enlace público**: el cliente ve el estado, el
  ETA, el nombre del repartidor y su posición en vivo mientras está en
  camino — nunca monto, teléfono ni las demás paradas (RN-DLV-008).
- **La PWA del repartidor**: ver sus rutas vivas con cada parada (dirección,
  cliente, teléfono, monto a cobrar), iniciar la ruta, entregar o fallar
  cada parada con foto y ubicación, y finalizar — todo desde el teléfono,
  con GPS en vivo mientras reparte.
- **El tablero de despacho**: ver lo sin asignar y las rutas vivas con su
  repartidor, sus paradas y su mapa; crear una ruta eligiendo repartidor y
  pedidos; cancelar una que no salió todavía.
- **Repartidores y su historial**: alta, edición (vehículo, placa,
  teléfono, sucursal, activo) y el historial de entregas con filtros por
  estado, repartidor y fecha, con la foto de evidencia cuando la hay.
- Pendiente de slice: avisar al cliente por WhatsApp.

### Endpoints

| Método | Ruta | Permiso |
|--------|------|---------|
| GET | `/delivery/repartidores/candidatos` | `delivery.gestionar_repartidores` |
| POST | `/delivery/repartidores` | `delivery.gestionar_repartidores` |
| GET | `/delivery/repartidores` | `delivery.leer` o `delivery.despachar` — con el nombre resuelto |
| PATCH | `/delivery/repartidores/{id}` | `delivery.gestionar_repartidores` |
| GET | `/delivery/tablero` | `delivery.despachar` — con repartidor y paradas resueltos |
| POST | `/delivery/rutas` | `delivery.despachar` |
| GET | `/delivery/rutas` | `delivery.leer` |
| GET | `/delivery/rutas/{id}` | `delivery.leer` (o ruta propia) |
| PUT | `/delivery/rutas/{id}/paradas` | `delivery.despachar` |
| POST | `/delivery/rutas/{id}/iniciar\|finalizar` | `delivery.despachar` o repartidor dueño de la ruta |
| POST | `/delivery/rutas/{id}/cancelar` | `delivery.despachar` |
| POST | `/delivery/rutas/{id}/posiciones` | repartidor dueño de la ruta, `en_curso` |
| GET | `/delivery/mi/rutas` | `delivery.repartir` — con paradas ya resueltas |
| POST | `/delivery/entregas/{id}/entregar\|fallar` | `delivery.repartir` (propia) o `delivery.despachar` |
| POST | `/delivery/entregas/{id}/reintentar\|cerrar` | `delivery.despachar` |
| GET | `/delivery/entregas[/{id}/evidencia]` | `delivery.leer` — el historial trae venta y repartidor resueltos |
| GET | `/delivery/publico/seguimiento/{token}` | sin autenticación, token anónimo |

Ver `docs/architecture/events.md` para el detalle de payloads.

## Reglas

`docs/domain/business-rules.md#reparto-propio-módulo-delivery-adr-098`
(RN-DLV-001 a 008): una entrega por venta creada al asignar a una ruta,
toda parada con coordenadas ancladas, una entrega fallida nunca marca
entregado, reintentar reutiliza la misma fila, una ruta iniciada no se
cancela, la posición solo se acepta y se expone en ruta activa, y el
enlace público es una credencial anónima que expira. Hereda RN-CUP-005 a
010 (una entrega, motivo de fallo, quién entrega).

## Flujo

`docs/domain/state-machines.md#reparto-propio-módulo-delivery-adr-098`:
máquina de `entrega` (pendiente → asignada → en_ruta → entregada/fallida,
con reintento) y de `ruta_reparto` (planificada → en_curso → finalizada).

## Plantillas de WhatsApp (pendiente de slice)

Diseño acordado, sin construir: tres plantillas aprobadas en Meta, una por
hito (parámetros en este orden — el mismo orden que exige la plantilla
real):

- `pedido_en_camino` (`delivery.ruta_iniciada`): nombre del cliente,
  nombre del repartidor, minutos estimados, enlace de seguimiento.
- `pedido_entregado` (`delivery.entrega_registrada`): nombre del cliente,
  número de orden.
- `entrega_fallida` (`delivery.entrega_fallida`): nombre del cliente,
  motivo en lenguaje llano, contacto de la sucursal.

Sin WhatsApp configurado (`whatsapp.habilitado()` en falso) el tablero
mostrará un enlace de seguimiento para copiar y un botón `wa.me` — el
aviso automático es un atajo, nunca la única vía.

## Relaciones

**Escucha**: `sales.venta_entregada` (cierra una entrega abierta si la
venta se marcó entregada desde el KDS), `sales.venta_anulada` (cancela la
entrega si seguía `pendiente`/`asignada`).

**Publica**: `delivery.ruta_iniciada`, `delivery.entrega_registrada`
(consumido por `sales` para avanzar la venta a entregada, ADR-098),
`delivery.entrega_fallida`, `delivery.ruta_finalizada`. `ruta_finalizada`
no tiene consumidor todavía.

**Contratos públicos consumidos**: `sales.queries_publicas.venta_para_reparto`,
`ventas_listas_para_reparto` y `contacto_de_cliente`;
`rrhh.queries_publicas.trabajadores_con_cuenta` y `cuenta_de_trabajador`.

**Contratos públicos expuestos**: ninguno todavía — nada más consume de
`delivery` hoy.
