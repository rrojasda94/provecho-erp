# ADR-105 — El pedido web es un canal propio de `venta`, y "cobra por
adelantado" no excluye al repartidor

Fecha: 2026-09-17
Estado: aceptada

## Contexto

PR1 (ADR-101) dejó el sitio en solo lectura. PR2 (ADR-102) agregó cuentas.
Este PR3 agrega lo que falta para vender de verdad: carrito, checkout
(invitado o logueado), asignación automática de local para delivery,
estimado de espera, boleta o factura, y pago en efectivo o Izipay.

Dos cosas del modelo existente entraban en tensión con lo pedido:

1. **`venta.canal` no tenía `web`.** `sales.domain.rules.CANALES` era
   `{pdv, agente_ia, delivery}` — ningún pedido podía nacer con canal `web`
   todavía, aunque `Promocion.canales`/`PuntoVenta.canal` ya lo admitían
   desde antes (preparado, no conectado).
2. **RN-POS-005 dice que la autoatención cobra por adelantado.**
   `puntos_venta.py::_validar_canal` obliga a que todo `PuntoVenta` de canal
   `web` o `kiosko` tenga `politica_pago='adelantado'` — *"no hay quién
   persiga al cliente"*. Tomado literal, eso excluiría el pago contra
   entrega que el negocio pidió explícitamente (`majambo.md` §3.1.9: Yape,
   Plin, tarjeta y **efectivo** son medios de pago normales de Charlie's).

## Decisión

### 1. `venta.canal`/`lista_precio.canal` ganan `web`

`sales.domain.rules.CANALES = {pdv, agente_ia, delivery, web}`, con el
`CheckConstraint`/`Enum` de ambas tablas actualizado (migración
`3070159f64bd`). `storefront_canal` pasa de `delivery` (semilla temporal de
PR1, cuando `web` no existía) a `web` — una lista de precios general
(`canal=None`) sigue aplicando igual (`especificidad_lista`), así que el
cambio no rompe nada mientras no se cree una lista específica de otro
canal.

### 2. RN-POS-005 se lee por lo que protege, no por su letra: alguien cobra
   en el momento de la entrega, aunque no sea un cajero

La razón de ser de la regla es *"nadie persigue al cliente si se va sin
pagar"*. En un kiosko de autoservicio dentro del local eso es real: el
cliente puede levantarse e irse con la bandeja. En delivery o recojo web,
el repartidor o el mostrador **sí** verifican el pago antes de soltar el
pedido — la misma garantía que un cajero, con otra persona haciendo el
papel. Por eso:

- **Efectivo**: el pedido web crea la `Venta` en estado `orden` sin llamar
  a `registrar_pago` — se cobra al entregar/recoger, con el flujo normal de
  caja que ya existe (el repartidor o el mostrador lo cobran como cualquier
  delivery telefónico de hoy).
- **Izipay**: se cobra de inmediato contra la pasarela activa y
  `registrar_pago` se llama con `exigir_caja_abierta=False` — excepción
  explícita a ADR-025 §1, ya usada hasta ahora solo para el replay del hub
  (ADR-009). El dinero ya lo tiene la pasarela, no una caja física; exigir
  un turno abierto en el punto de venta `web` (que no tiene cajero delante)
  no protegería nada que Izipay no proteja ya.

`PuntoVenta(canal='web')` conserva `politica_pago='adelantado'` tal cual la
exige `_validar_canal` — no se tocó esa validación. Lo que cambia es que
"adelantado" para el pedido web se satisface con *Izipay pagado en el
checkout*, y el efectivo queda como una vía aparte que no pasa por
`registrar_pago` hasta la entrega, en vez de forzar todo pedido web a
pagarse antes de saber si va a haber cocina disponible para prepararlo.

### 3. El pedido nace en `storefront`, se confirma por evento (mismo
   patrón que ADR-102)

`storefront` no puede llamar a `sales.application.ventas.crear_venta`
directamente. El flujo:

1. `storefront.application.pedidos.confirmar()` valida el carrito, elige
   sucursal (recojo: la que pidió el cliente; delivery: automática, ver
   más abajo), fija precios contra la carta pública (nunca confía en lo que
   mandó el navegador, RN-PRC-003) y crea `storefront_pedido` +
   `storefront_pedido_item` en estado `pendiente`.
2. Publica `storefront.pedido_web_confirmado` **antes** del commit
   (`core/events.py`). `sales.application.listeners::
   on_pedido_web_confirmado` llama a `ventas.crear_venta(canal="web", ...)`
   y, si el medio es Izipay, a `registrar_pago(...)`.
3. Publica de vuelta `sales.pedido_web_procesado`
   (`{pedido_id, ok, venta_id?, numero_orden?, motivo?}`).
   `storefront.application.listeners::on_pedido_web_procesado` marca el
   pedido `confirmado` o `fallido`.

El bus es síncrono y en proceso: para cuando `confirmar()` retorna, la
cadena completa ya corrió y el pedido devuelto al checkout ya trae su
estado final — el cliente no necesita hacer polling en el caso normal.
**Esto es una desviación deliberada del plan original**, que sugería un
outbox real + reconciliación por Celery: ADR-016 ya había descartado esa
solución completa por cara y sin consumidor que la necesitara hoy, y este
PR sigue ese mismo criterio en vez de construir un outbox nuevo solo para
este flujo. El costo aceptado es el mismo de ADR-102: si el proceso muere
entre el paso 1 y el 2 (crash real, no una excepción de negocio), el
pedido queda `pendiente` para siempre y nadie lo reconcilia solo — ver
`docs/roadmap/deuda/modulo-storefront.md`.

### 4. Asignación automática de local y estimado de espera

`storefront/domain/asignacion.py` (puro): entre las sucursales activas de
la marca con un `PuntoVenta(canal=web)` que admita la modalidad pedida
(`sales.queries_publicas.puntos_venta_web_de_sucursales`, contrato nuevo),
se cotiza cada una contra el destino
(`sales.queries_publicas.cotizar_delivery_publico` — el mismo cálculo que
usa `crear_venta` internamente vía `tarifa_delivery`, expuesto de
antemano) y se descarta la que quede fuera del radio de delivery
(`DELIVERY_DISTANCIA_MAXIMA_KM`, ya existía). Entre las que quedan, gana la
más cercana **salvo que esté saturada** (`carga >= STOREFRONT_SATURACION_
PEDIDOS`, semilla 4) y otra dentro de radio no lo esté — la carga es el
conteo de `Venta.estado='orden'` de esa sucursal
(`sales.queries_publicas.carga_activa_por_sucursal`, contrato nuevo). El
ETA es `base + carga × minutos_por_pedido` (`STOREFRONT_ETA_*`), con 15
minutos de colchón en el máximo del rango — mismo orden de magnitud que los
30-45/45-55 min que Charlie's ya cotiza por teléfono.

> **Enmienda (2026-09-19)**: esa fórmula daba el mismo estimado para una
> botella de agua que para seis pizzas, y contaba como cola toda orden
> abierta sin límite de tiempo —en staging, pedidos de prueba nunca cerrados
> dejaron el estimado en 70-80 minutos—. Ahora el ETA sale de lo que se
> pide: `preparación + cola + viaje` (RN-WEB-011), con el tiempo de
> preparación cargado por producto en el ERP (`tiempo_preparacion_min`,
> RN-COM-045), la cola limitada a las últimas 3 horas y solo cuando hay algo
> que cocinar, y el viaje por km en delivery. `STOREFRONT_ETA_BASE_MINUTOS`
> pasa a ser el tiempo de un producto sin tiempo cargado. La cotización
> recibe el carrito (`items`) para poder calcularlo. Costo aceptado: el
> negocio tiene que cargar el tiempo de cada producto; mientras no lo haga,
> el estimado se comporta como antes (base estándar).

Recojo: el cliente elige el local (`majambo.md` §3.1: "recojo = el cliente
decide"), y solo se calcula el ETA, no la distancia ni el costo.

Los tres parámetros (`STOREFRONT_ETA_BASE_MINUTOS`, `_MINUTOS_POR_PEDIDO`,
`_SATURACION_PEDIDOS`) quedan en `.env` (semilla de `settings`), no en
`parametro_empresa` como sí vive `delivery_radio_km` — a diferencia de la
tarifa de delivery, que ya tiene meses de uso real que justifican el paso
de aprobación de Gerencia, esta es la primera versión del ETA/asignación y
someterla a ese flujo antes de ver un solo pedido real habría sido
prematuro. Se documenta como deuda si Gerencia pide poder tunearlos sin
desplegar.

### 5. Izipay: adaptador con interfaz real, pero solo el falso implementado

`src/shared/integrations/izipay/` define el `Protocol` `Pasarela`
(`crear_intento`, `verificar_webhook`), `IzipayFake` (aprueba cualquier
cobro de inmediato) e `IzipayReal` (esqueleto, lanza `NotImplementedError`
en ambos métodos). `izipay_habilitado()` decide cuál se usa según
`IZIPAY_API_KEY` esté configurada o no — mismo criterio que
`comprobantes.emision_habilitada()` para Factiliza. Sin una cuenta de
comercio real contra la cual probar el intercambio de la API de Izipay
(redirección, webhook, verificación de firma), completar `IzipayReal` a
ciegas sería código sin forma de verificarse; queda declarado como deuda
explícita, no como "ya funciona".

### 6. Extras y Mitad x Mitad quedan fuera de este slice

El carrito de PR3 es "un producto/tamaño (ya un `producto_comercial_id`
propio, por variante) + una cantidad". Extras (máx. 3) y Mitad x Mitad de
la carta de Charlie's (`brand-voice-guidelines.md`, `majambo.md` §3.1.8)
necesitarían un concepto de extra/combo que hoy no existe en `sales` —
construirlo a ciegas dentro de este PR, sin que el negocio lo valide,
habría sido inventar un modelo de datos nuevo sin encargo. Se documenta
como deuda con la forma del hueco (qué falta en `sales`, no cómo se
resuelve).

## Consecuencias

- `sales` gana tres funciones de lectura en su contrato público
  (`carga_activa_por_sucursal`, `puntos_venta_web_de_sucursales`,
  `cotizar_delivery_publico`) y un listener más
  (`on_pedido_web_confirmado`).
- `users` gana `usuario_servicio_storefront` en su contrato público — la
  única excepción de escritura en `queries_publicas.py`, que crea (una
  sola vez, get-or-create) el usuario `tipo=agente_ia` que autoría las
  ventas del sitio, porque `Venta.usuario_id` es NOT NULL y ningún cliente
  del sitio tiene cuenta de trabajador.
- Boleta/factura elegida en el checkout solo llega de forma confiable al
  comprobante cuando el pago es inmediato (Izipay): en efectivo, el
  cajero que cobra al entregar/recoger vuelve a pedir el documento, igual
  que en cualquier pedido telefónico de hoy — la preferencia capturada en
  `storefront_pedido` no se muestra todavía en ninguna pantalla del ERP.
- Sin Playwright de este flujo todavía (PR4).

## Alternativas descartadas

- **Exigir Izipay para todo pedido web, sin excepción.** Cumple RN-POS-005
  al pie de la letra, pero contradice el encargo explícito del negocio
  (efectivo es un medio de pago real y frecuente en Tarapoto) sin que haya
  evidencia de que el riesgo que la regla previene aplique a un repartidor
  que cobra en la puerta.
- **Outbox real + tarea de reconciliación por Celery**, como sugería el
  plan original. Mismo análisis costo/beneficio que ADR-016 ya hizo:
  correcto en el papel, más caro de construir y mantener que lo que un
  bus síncrono en proceso ya resuelve para el caso común, sin un segundo
  consumidor hoy que lo justifique.
