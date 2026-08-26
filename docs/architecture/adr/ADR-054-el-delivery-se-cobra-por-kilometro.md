# ADR-054 — El delivery se cobra por kilómetro, y el kilómetro lo mide el servidor

- **Estado:** aceptada
- **Fecha:** 2026-08-22
- **Contexto:** `sales` (venta, tarifa de delivery), `shared/integrations/google`
- **Relacionado:** ADR-005 (integraciones que prellenan), ADR-009 (hub
  offline), ADR-041 (cuota de un proveedor pago), ADR-053 (la dirección se
  elige en el mapa)
- **Superado en parte por ADR-068** (2026-08-25): la tarifa ya **no sale del
  `.env`** —la fija Gerencia en `parametro_empresa`, y `settings.delivery_*`
  queda solo como semilla— y el reparto **sí se suma al total de la venta**
  (RN-COM-041). Todo lo demás de esta ADR sigue vigente tal cual.

## Contexto

El reparto propio se cobraba a ojo o no se cobraba. Con las direcciones ya
ancladas en el mapa (ADR-053) se puede medir la distancia real y cobrarla, y
—más importante— **decidir cuándo no conviene repartir**: pasado cierto radio,
mandar a alguien media hora en moto sale más caro que derivar el pedido a una
plataforma externa (DAZ DAZ). Hay además distritos donde el negocio decidió no
repartir.

## Decisión

### El cálculo vive en el servidor

`shared/integrations/google/rutas.py` habla con la **Routes API**
(`computeRouteMatrix`, matriz de 1×1) usando una **segunda clave restringida
por IP**. `sales/application/tarifa_delivery.py` decide con lo que devuelve.

Son dos claves porque Google no admite restringir la misma por referente HTTP
y por IP a la vez, y son dos riesgos distintos: la del mapa se lee del código
de la página y sirve para dibujar; **esta define cuánta plata paga el
cliente**, y un número que viaja por el navegador es un número que se puede
editar.

De ahí sale un invariante verificable: **si aparece una llamada a
`routes.googleapis.com` en la pestaña de red del navegador, está mal hecho.**

Se usa `computeRouteMatrix` y no el endpoint de ruta completa porque la
respuesta trae los metros y nada más, sin la polilínea que acá no se dibuja.

### Distancia de manejo, no en línea recta

Un río en el medio son dos kilómetros de puente. La línea recta existe
únicamente como plan B.

### Nunca bloquea una venta

Si Google no contesta —caído, sin clave, sin cuota, o el hub de la sucursal
sin internet— se cae a **haversine × 1,3** y la cotización se marca
`aproximada`. El PDV lo muestra como "aprox." para que nadie discuta el monto
como si fuera una medición.

Cobrar de menos por un kilómetro es preferible a no poder tomar el pedido.
Mismo criterio que ADR-005, y es además lo único que funciona en el hub
offline (ADR-009).

`FACTOR_CALLE = 1.3` es una **perilla de calibración**, no una constante
universal: en Tarapoto las calles son regulares, en un cerro sería más. Se
ajusta comparando cotizaciones aproximadas contra las reales de Google.

### La zona restringida se resuelve por nombre de distrito

`DELIVERY_DISTRITOS_RESTRINGIDOS` es una lista separada por comas, comparada
sin tildes ni mayúsculas contra `ubicacion_distrito`, que ya viene con la
dirección.

Se descartó PostGIS con polígonos: es mucha máquina para una lista de cuatro
nombres, y traería una extensión de Postgres, un tipo de columna nuevo y una
pantalla para dibujar polígonos. Cuando el negocio necesite una zona que no
coincide con un distrito, ahí se paga ese costo (queda en la deuda del
ROADMAP).

**Se evalúa antes de medir**: la zona vetada no depende de la distancia, y
preguntarle a Google costaría una llamada por una respuesta que ya se sabe.

### La cotización se congela en la venta

`venta.distancia_entrega_km` y `venta.costo_entrega` se guardan al crear la
orden y **no se recalculan** al mirar el histórico. La tarifa por kilómetro
cambia y el pedido de ayer no puede cambiar de precio — mismo criterio por el
que la guía de remisión congela sus direcciones al emitirse.

El replay del hub (`sincronizacion.py`) **no vuelve a cotizar**: esa venta ya
se cobró con un precio, y recalcularlo cambiaría el monto a espaldas del
cliente.

### Caché por proceso, no en Redis

Cada pedido se cotiza dos veces —la que ve el cajero y la que congela la
orden—. Un `@lru_cache` sobre `distancia_km`, con las coordenadas redondeadas
a 5 decimales (~1 m), deja una sola llamada.

Sin TTL a propósito: la distancia entre dos puntos fijos no cambia. Y va sobre
`distancia_km` y no sobre la cotización completa para que **un fallo de Google
no quede cacheado** — `lru_cache` no guarda excepciones, así que la estimación
aproximada se recalcula cada vez y la medición real vuelve sola.

Se evaluó Redis con TTL: agrega un módulo de caché compartido y una superficie
de invalidación para ahorrar lo mismo que un diccionario.

### DAZ DAZ es una sugerencia, no una integración

Cuando la cotización dice `derivar_a_externo`, el PDV avisa ("13,4 km — más
lejos del radio propio: sugerir DAZ DAZ") y **el cajero decide**. Si acepta,
se marca el campo que ya existía: `venta.repartidor_externo_plataforma`
(`rappi|ubereats|pedidosya|…`), que suma el valor `dazdaz`. Cero tablas
nuevas.

### La cotización tiene cuota, como la consulta de documento

`POST /sales/ventas/cotizar-delivery` cuenta por usuario **y** por IP,
reusando `core.rate_limit.consumir`. Cada llamada gasta una medición de un
proveedor pago y un bucle mal escrito en el PDV se come el plan del mes. Dos
cuentas por lo mismo que en ADR-041: todas las cajas del local salen por la
misma IP, y limitar solo por ahí castiga al equipo por uno solo.

### Arranca apagado

`DELIVERY_TARIFA_BASE`, `DELIVERY_PRECIO_POR_KM` y
`DELIVERY_DISTANCIA_MAXIMA_KM` valen `0` de fábrica: el delivery se sigue
cobrando como antes hasta que el negocio defina la tarifa. Nada se enciende
solo.

> **ADR-068:** esos tres valores pasaron a ser la **semilla**. La tarifa que
> manda la fija Gerencia en `/gerencia/delivery` y vive en
> `parametro_empresa`. Sigue arrancando apagada, pero ya no hace falta
> redesplegar para encenderla — que es la razón por la que en tres meses
> nadie la encendió.

## Alternativas descartadas

- **Calcular en el navegador con la clave del mapa.** Menos código y ninguna
  clave nueva, pero el precio del reparto quedaría en manos del cliente.
- **Distance Matrix API (la clásica).** Hace lo mismo; Google la tiene marcada
  como legada.
- **Sumar el reparto al total de la venta.** Es lo que corresponde a futuro,
  pero exige una línea de venta (producto de servicio "Delivery") para que
  aparezca en el comprobante y en contabilidad. Queda en la deuda: por ahora
  el costo se calcula, se guarda y se muestra.
  **Resuelto por ADR-068 (2026-08-25)**, y sin la línea de venta: el flete
  entra al total desde su propia columna. Desde caja, «se calcula y no se
  cobra» se leía como que el PDV estaba roto.
- **Tarifa por sucursal o por marca.** Arranca global en `settings`. Cuando
  dos locales necesiten precios distintos, pasa a columnas de `sucursal`.
  Con ADR-068 pasó a ser **por empresa** (`parametro_empresa`); por sucursal
  sigue diferida.

## Consecuencias

- Una segunda clave de Google que rotar y vigilar
  (`docs/engineering/integraciones-google.md`).
- `venta` gana tres columnas más las cinco del ancla, y el contrato de sync
  las lleva.
- Con las claves vacías todo esto queda inerte: distancia aproximada, costo
  cero, nada que derivar.

## Addendum 2026-08-26 — el cobro se redondea al medio sol (RN-COM-042)

Base más precio por kilómetro produce el monto exacto, y el monto exacto es
incómodo: S/ 8.71, S/ 8.89. El repartidor no lleva monedas de un céntimo, el
cajero redondea de cabeza y a partir de ahí el ticket dice una cosa y la caja
tiene otra.

`costo_de` redondea ahora **por cercanía al múltiplo de S/ 0.50**
(`ROUND_HALF_UP` sobre medios soles, no el `ROUND_HALF_EVEN` que `decimal`
trae por defecto: el bancario es correcto pero impredecible para quien mira
un ticket, y sobre medio sol el empate caería a veces para arriba y a veces
para abajo sin que nadie entienda por qué).

Dos precisiones:

- Se redondea **el monto, no la distancia**. `distancia_entrega_km` sigue en
  dos decimales: es una medición, y redondearla al medio kilómetro cambiaría
  el cobro por un motivo que no tiene que ver con la plata.
- Se redondea **en las cuatro salidas**, no solo en la que mide. Las tres
  ramas «sin distancia» (sucursal sin anclar, dirección a mano, zona
  restringida) devolvían `tarifa.base` crudo, sin pasar siquiera por
  `quantize`: una base mal tecleada en Gerencia como `3.456` llegaba tal cual
  al ticket. Ahora las cuatro pasan por `costo_de`.

Consecuencia aceptada: una tarifa que dé menos de S/ 0.25 termina cobrando
cero. Es la tarifa la que está mal configurada, no el redondeo, y agregar un
piso mínimo sería una regla nueva para un caso que no existe.
