# ADR-016 — Los eventos internos se despachan después del commit

- Estado: aceptado
- Fecha: 2026-08-01

## Contexto

El bus interno (`src/core/events.py`) era síncrono y despachaba en el acto:
`event_bus.publish(...)` llamaba a cada handler dentro del mismo `publish`.

Los casos de uso publican **en medio de su transacción**, no al final.
`ventas.crear_venta` hace `flush()`, publica `sales.venta_confirmada` y
devuelve; recién el router hace `session.commit()`. Los listeners, en
cambio, abren su **propia** sesión y commitean por separado
(`inventory.application.listeners.session_factory`).

Entre el `publish` y el `commit` del emisor hay una ventana real. El
`UNIQUE (sucursal_id, fecha_orden, numero_orden)` de `venta` es
precisamente un constraint que salta en el commit —el correlativo se
calcula con `max+1` y dos cajas simultáneas chocan, cosa que el propio
código documenta como el camino esperado de reintento—. En esa carrera, la
venta perdedora hacía rollback **después** de que inventory ya había
descontado y commiteado el consumo de insumos: stock descontado por una
venta que no existe. Lo mismo en el replay del hub
(`sales.application.sincronizacion._intentar` hace `rollback()` por ítem
rechazado) y en la tarea Celery del comprobante.

El efecto es silencioso: no rompe ningún test, no da error en runtime, y
aparece semanas después como una diferencia de inventario que el conteo
atribuye a merma.

## Decisión

**El evento se acumula en la sesión que lo publicó y se despacha cuando esa
sesión commitea.**

`publish(nombre, payload, session=...)` guarda el evento en `session.info`;
un listener de SQLAlchemy sobre `Session.after_commit` lo vacía, y
`after_soft_rollback` lo descarta. Sin `session=` el despacho es inmediato
—queda para lo que corre fuera de una transacción—.

Consecuencias buscadas, además de cerrar la ventana:

- El handler ahora **puede leer lo que publicó el emisor**. Antes, un
  listener con sesión propia no veía la venta todavía no commiteada; el
  payload tenía que arrastrar todo lo que el consumidor fuera a necesitar.
- Un handler que revienta ya no puede tumbar al emisor: post-commit no hay
  nada que deshacer, así que el bus lo loguea (`log.exception`, y de ahí a
  Sentry) y sigue con los demás. Es el criterio que `inventory` y
  `accounting` ya aplicaban a mano, ahora uniforme.

## Alternativas descartadas

**Tabla outbox + Celery.** Es la solución completa: el evento se escribe en
la misma transacción y un worker lo entrega con reintentos y garantía
at-least-once. También es la más cara —tabla, migración, worker, política
de reintentos y de venenosos, orden de entrega— y hoy no hay ningún
consumidor que la necesite: los dos listeners que existen corren en el
mismo proceso. Queda como el paso siguiente natural cuando un consumidor
tenga que vivir fuera del proceso; este cambio no lo estorba, lo prepara
(el punto de despacho ya es uno solo).

**Que el listener use la sesión del emisor.** Un solo commit, atomicidad
real. Descartada porque acopla el ciclo de vida de la transacción del
emisor a lo que haga cualquier consumidor: un fallo de inventario pasaría a
cancelar la venta, que es exactamente lo contrario de la regla vigente
("un fallo de inventario NUNCA rompe la venta").

**Mover el `publish` al router, después del commit.** Funciona y no
necesita nada nuevo, pero reparte la responsabilidad del evento entre el
caso de uso (que sabe qué pasó) y el router (que sabe cuándo commitear), y
hay que acordarse en cada endpoint — el mismo tipo de repetición que
ADR-017 saca de los routers.

## Consecuencias

- 33 llamadas a `publish` pasan a llevar `session=session`. El test de
  `core/events` fija que sin commit no se despacha y que el rollback
  descarta.
- La atomicidad sigue sin ser total: si el commit del *listener* falla, el
  del emisor ya ocurrió. La diferencia la sigue detectando el conteo. Lo
  que se cerró es la ventana inversa, que era la peligrosa.
- Un `publish` cuya sesión nunca commitea es un evento que se pierde en
  silencio. Es el comportamiento correcto (la operación tampoco ocurrió),
  pero conviene saberlo al depurar.
