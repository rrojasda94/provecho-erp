# ADR-101: El KDS despacha, el repartidor entrega

## Estado

Aceptado (2026-09-17)

## Contexto

ADR-098 (§2, "el camino inverso") hizo que `delivery` escuchara
`sales.venta_entregada` para cerrar sola la `entrega` abierta si el
despacho marcaba la venta entregada desde el botón del KDS en vez de
desde el tablero de reparto — pensado como una convergencia benigna entre
dos caminos al mismo resultado.

En uso real no lo es. `on_venta_entregada` cerraba la entrega **desde
cualquier estado** (`pendiente`, `asignada`, `en_ruta`), sin auditoría, sin
publicar `delivery.entrega_registrada` (así que el WhatsApp de "llegó tu
pedido" nunca salía) y sin que el repartidor hubiera hecho nada. Dos
síntomas reportados por el negocio son la misma causa:

1. Un pedido delivery que **todavía no tenía ruta** salía de "sin asignar"
   apenas alguien lo despachaba desde el KDS — `sales.pedido_entregado`
   (todos los ítems en `entregado`) es el mismo filtro que usaba
   `ventas_listas_para_reparto` para no mostrar lo ya resuelto, así que el
   pedido no volvía a poder rutearse.
2. Un pedido **con ruta ya asignada**, si alguien (mozo, cajero) lo
   despachaba desde el KDS mientras el repartidor seguía en la calle, veía
   su `entrega` saltar a `entregada` de golpe. La ruta seguía viva en el
   tablero (`RUTAS_VIVAS` no cambia), pero la parada ya no se podía
   resolver desde la PWA del repartidor — quedaba en un estado que no
   reflejaba la realidad.

Además, RN-DLV-001 exigía que una venta estuviera `lista` (todos los
ítems en `listo`) para entrar a una ruta. Eso significa que el despacho no
podía planificar la salida de un repartidor hasta que cocina terminara
—al revés de cómo trabaja un local real, donde se arma la ruta con lo que
ya se sabe que va a salir y se decide el orden mientras el último plato
sale del horno.

## Decisión

### 1. Rutear ya no exige que el pedido esté listo

`sales.ventas_listas_para_reparto` se renombra a `ventas_para_reparto` y
deja de filtrar por `pedido_entregable`: devuelve toda venta delivery
ruteable (sin plataforma externa, no anulada) con al menos un ítem no
entregado, y cada fila trae `lista: bool`
(`rules.pedido_entregable`, sin cambios). `delivery.rutas.crear` y
`editar_paradas` ya no exigen `lista` para **entrar** a una ruta —
RN-DLV-001 pasa a "toda parada necesita coordenadas ancladas", sin la
condición de estar lista.

Lo que sí sigue exigiendo `lista` es **salir**: `rutas.iniciar` recién
ahora valida que las paradas estén todas `lista`, y lo mismo vale para
sumar una parada nueva a una ruta `en_curso` (el repartidor ya salió, no
se le manda a esperar en la puerta de otro pedido a medio preparar).
RN-DLV-005 queda así: *una ruta se inicia solo con al menos una parada, un
repartidor activo y todas sus paradas `lista`*.

### 2. `delivery` deja de escuchar `sales.venta_entregada`

Se elimina `delivery.listeners.on_venta_entregada` y
`entregas.cerrar_por_venta_entregada`. Cerrar una `entrega` es, desde
ahora, **solo** cosa de `delivery`: el repartidor desde su PWA, o el
despacho en su nombre desde el tablero (mismo endpoint
`POST /delivery/entregas/{id}/entregar`, ya exigía `en_ruta` y ya
auditaba y publicaba el evento — no cambia).

El camino que sí sigue vivo es el declarado en ADR-098 §2 sin cambios: al
registrar una entrega, `delivery` publica `delivery.entrega_registrada` y
`sales.listeners` la escucha para llamar a
`cumplimiento.registrar_entrega` — la venta se marca entregada *desde*
delivery, nunca al revés.

Consecuencia directa: el botón "Entregar" del KDS para un pedido delivery
pasa a llamarse **"Despachar"**. Sigue llamando al mismo
`POST /sales/ventas/{id}/entrega` (`cumplimiento.registrar_entrega`, sin
tocar) — cierra la comanda de cocina, saca el pedido de la cola del KDS,
sigue siendo el camino para un cliente que recoge en el local — pero ya
**no** cierra ninguna entrega de reparto. Si el pedido tiene una ruta en
marcha, la ruta sigue viva y la parada solo la cierra el repartidor (o
despacho, desde `/delivery`) cuando de verdad se entregó.

### 3. Costo aceptado: dos estados pueden divergir un rato

Una venta delivery puede quedar `entregada` en `sales`
(`estado_preparacion` de todos sus ítems) mientras su `entrega` en
`delivery` sigue `en_ruta` — si alguien la despachó desde el KDS antes de
que el repartidor confirmara la entrega. No es un bug: es la misma
separación de autoridad que ya declaraba ADR-098 ("dos caminos que
convergen sin que ninguno conozca el dominio del otro"), aplicada en
sentido único. `delivery` sigue siendo la única fuente de verdad de si el
reparto en sí se completó; `sales` solo sabe si la comanda se cerró.

## Consecuencias

- Una ruta ya no desaparece ni se corrompe porque alguien tocó el botón
  equivocado en el KDS — el reparto se gestiona de punta a punta desde
  `delivery`, como pedía el negocio.
- El despacho puede armar y salir con una ruta mientras el último pedido
  sigue en cocina, y decide con qué sale de verdad recién al iniciar.
- Cierra parte de la deuda declarada en
  `docs/roadmap/deuda/modulo-delivery.md` (slice 5): editar paradas de una
  ruta ya creada, y cambiarle el repartidor, ahora tienen UI —
  `PUT /delivery/rutas/{id}/paradas` deja de ser un endpoint sin cliente.
- Nueva superficie de aviso: `GET /delivery/avisos` (toast/sonido en KDS y
  caja) y dos notificaciones de bandeja nuevas
  (`delivery.entrega_para_cobrar`, `delivery.ruta_finalizada`), resueltas
  por permiso (`users.usuarios_con_permiso`) y no por rol — así no hace
  falta que `delivery` conozca el catálogo de roles de `users`.
