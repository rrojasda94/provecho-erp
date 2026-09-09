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

## Estado (slice core implementado 2026-09-09, ADR-098)

Operativo en `/api/v1/delivery`: alta y edición de repartidores propios,
tablero de despacho, ciclo completo de una ruta (crear con ruteo
heurístico → editar paradas → iniciar → entregar/fallar cada parada →
reintentar o cerrar la fallida → finalizar o cancelar), evidencia
fotográfica y la convergencia por evento con `sales` en los dos sentidos
(`delivery.entrega_registrada` marca la venta entregada;
`sales.venta_entregada`/`venta_anulada` cierran o cancelan la entrega).
Capas `domain/rules.py`, `application/` (`repartidores.py`, `rutas.py`,
`ruteo.py`, `entregas.py`, `tablero.py`, `parametros.py`, `listeners.py`),
`infrastructure/`, `api/`. Migración `69f4ca1d58f4` aplicada.

**Sin ruteo real todavía**: `application/ruteo.py` solo aplica la
heurística vecino-más-cercano (`optimizada_por` sale `heuristica` o
`manual`, nunca `google`) — la Routes API con `optimizeWaypointOrder`
llega en el próximo slice. **Sin GPS ni seguimiento público**: no existen
todavía `POST /rutas/{id}/posiciones` ni el enlace público de seguimiento
(`token_publico` queda sin generar). **Sin avisos**: no hay plantillas de
WhatsApp ni tareas de Celery — eso es un slice aparte. Ver
`docs/roadmap/deuda/modulo-delivery.md` y el orden de slices en
`docs/roadmap/historial/modulo-delivery.md`.

### Casos de uso

- **Alta de repartidor**: elegir un trabajador activo con cuenta propia
  (`rrhh.trabajadores_con_cuenta`) que aún no sea repartidor, y darle
  vehículo y sucursal.
- **Tablero de despacho**: ver los pedidos delivery ya listos sin asignar
  (`sales.ventas_listas_para_reparto`) y las rutas en curso con su última
  posición conocida (hoy siempre vacía — sin GPS todavía).
- **Crear una ruta**: elegir repartidor y uno o más pedidos; el servidor
  ordena las paradas con la heurística vecino-más-cercano y calcula
  distancia y ETA por parada. `PUT .../paradas` reemplaza el conjunto de
  una ruta que no salió todavía.
- **Iniciar / finalizar / cancelar una ruta**.
- **Entregar / fallar una parada**, con ubicación y foto opcional; un
  fallo pide motivo (y detalle si es "otro").
- **Reintentar o cerrar** una entrega fallida.
- Pendientes de slice: seguir el pedido por enlace público, y avisar al
  cliente por WhatsApp.

### Endpoints

| Método | Ruta | Permiso |
|--------|------|---------|
| GET | `/delivery/repartidores/candidatos` | `delivery.gestionar_repartidores` |
| POST | `/delivery/repartidores` | `delivery.gestionar_repartidores` |
| GET | `/delivery/repartidores` | `delivery.leer` o `delivery.despachar` |
| PATCH | `/delivery/repartidores/{id}` | `delivery.gestionar_repartidores` |
| GET | `/delivery/tablero` | `delivery.despachar` |
| POST | `/delivery/rutas` | `delivery.despachar` |
| GET | `/delivery/rutas` | `delivery.leer` |
| GET | `/delivery/rutas/{id}` | `delivery.leer` (o ruta propia) |
| PUT | `/delivery/rutas/{id}/paradas` | `delivery.despachar` |
| POST | `/delivery/rutas/{id}/iniciar\|finalizar` | `delivery.despachar` o repartidor dueño de la ruta |
| POST | `/delivery/rutas/{id}/cancelar` | `delivery.despachar` |
| GET | `/delivery/mi/rutas` | `delivery.repartir` |
| POST | `/delivery/entregas/{id}/entregar\|fallar` | `delivery.repartir` (propia) o `delivery.despachar` |
| POST | `/delivery/entregas/{id}/reintentar\|cerrar` | `delivery.despachar` |
| GET | `/delivery/entregas[/{id}/evidencia]` | `delivery.leer` |

Pendientes de slice: `POST /delivery/rutas/{id}/posiciones` y
`GET /delivery/publico/seguimiento/{token}`.

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

**Contratos públicos consumidos**: `sales.queries_publicas.venta_para_reparto`
y `ventas_listas_para_reparto`; `rrhh.queries_publicas.trabajadores_con_cuenta`
y `cuenta_de_trabajador`.

**Contratos públicos expuestos**: ninguno todavía — nada más consume de
`delivery` hoy.
