# ADR-077 — El sobrepago en efectivo se acepta y el vuelto se guarda

- **Estado:** aceptada — **enmienda RN-COM-016**
- **Fecha:** 2026-08-28
- **Contexto:** `sales` (`pago.vuelto`, `rules.pagos_cubren_total`,
  `ventas.registrar_pago`), `frontend/lib/cobro.ts`
- **Relacionado:** ADR-018 (cobro dividido), ADR-025 (ciclo de caja),
  RN-COM-016, RN-COM-018, RN-MDP-002

## Contexto

El turno de prueba de la 0.8.0 lo reportó así: «pese a que pongo monto
exacto, arroja error indicando que la cantidad supera al monto a pagar».

Eran dos problemas distintos que se veían como uno.

**El primero no era una regla, era un redondeo.** La aritmética del diálogo
de cobro se hace en el `number` de JavaScript, donde 33.30 − 10 deja
23.299999999999997. Ese número viajaba al servidor como string, tal cual. El
pago entraba —no excedía el saldo— pero la suma de los pagos nunca llegaba al
total, así que la cuenta no se cerraba: **la venta quedaba en `orden` y sin
comprobante**, cobrada de hecho y sin cobrar para el sistema. En el otro
sentido, un `pagado < total` por una millonésima dejaba el botón "Confirmar
pago" muerto con "Restante S/ 0.00" en pantalla.

Del lado del servidor pasaba lo simétrico: `total_venta` sumaba
`cantidad × precio` sin cuantizar, y `cantidad` y `precio_unitario` guardan
dos decimales cada uno. 1.5 × 12.35 da 18.525. El saldo real de la cuenta era
18.525 mientras la pantalla —que lee `venta.total`, ya truncado por
`Numeric(10,2)`— decía 18.53. Pagar el monto exacto que el cajero tenía
delante se rechazaba por excederlo; pagar 18.52 dejaba medio centavo
imposible de cancelar.

**El segundo sí era una regla.** `pagos_cubren_total` documentaba «no se
admite sobrepago» y comparaba por igualdad exacta. En una caja eso significa
que el cajero no puede aceptar un billete de 50 por una cuenta de 33.30: para
cobrar tiene que teclear el saldo de memoria, al centavo, con el cliente
esperando. El vuelto sí se mostraba, pero solo en el navegador: se calculaba
en `calcularCobro` y moría ahí.

## Decisión

### El dinero se cuantiza a centavos, en los dos lados

`rules.a_centavos()` es el único lugar donde se redondea plata, y todo total
que alguien vaya a cobrar, mostrar o comparar pasa por ahí: `total_venta`,
`total_a_cobrar` y las dos comparaciones de `pagos_cubren_total`. En el
frontend, `aCentavos()` en `lib/cobro.ts` y `.toFixed(2)` al mandar el monto.

**`ROUND_HALF_UP` y no el bancario que `quantize` trae por defecto.** Es como
redondea `numeric` en Postgres, que es quien guarda `venta.total`; con el
bancario, 18.525 daría 18.52 en el cálculo y 18.53 en la columna, que es
exactamente la discrepancia que esto viene a cerrar.

`PagoCreate.monto` declara `decimal_places=2`: un monto con cola de decimales
deja de ser algo que el contrato acepte y calle.

### El saldo lo dice el servidor

`GET /sales/ventas/{id}/saldo` devuelve, por cuenta, total, pagado y saldo.
El diálogo de cobro lo usa en vez de sumar el borrador.

El total del navegador no puede saber el flete de una orden reabierta ni el
prorrateo del descuento entre cuentas, y cualquiera de las dos diferencias
terminaba en un cobro rechazado con el "monto exacto" en pantalla. **El
número que valida el pago tiene que ser el mismo que lo propone.** Si la
consulta falla se cobra igual con el total del borrador: quedarse sin poder
cobrar por un dato de apoyo sería peor que la diferencia que ese dato evita.

### El efectivo admite sobrepago; los demás medios, no

`registrar_pago` acepta `monto > saldo` cuando `medio_pago.tipo` está en
`MEDIOS_CON_VUELTO` —hoy, `efectivo`—. Lo aplicado a la cuenta es el saldo
y la diferencia se guarda en **`pago.vuelto`**.

**`monto` sigue siendo lo que entra a la cuenta y no lo que entregó el
cliente.** Es lo que contabilidad asienta y lo que el cierre de caja espera
encontrar; meter ahí los 50 de un billete por una cuenta de 40 pondría en los
libros diez soles que salieron del cajón esa misma noche.

**Y no vale para tarjeta ni billetera.** Ahí no hay cajón que devuelva: un
monto de más es un error de tecleo, y aceptarlo dejaría la tarjeta cobrada
por encima de lo consumido con un arqueo que ya no puede cuadrar. El error
ahora lo dice: «el pago excede el saldo de la cuenta y este medio no da
vuelto».

Por eso `pagos_cubren_total` pasa a ser `>=` y no `==`. No es que se acepte
cobrar de más: lo aplicado nunca excede el saldo. Es que la igualdad exacta
sobre Decimales sin cuantizar dejaba cuentas pagadas al centavo sin cerrarse.

## Alternativas descartadas

- **Solo arreglar el redondeo y dejar prohibido el sobrepago.** Cierra el bug
  reportado pero deja al cajero tecleando el saldo exacto de memoria, que es
  la mitad de la queja y la que se repite en cada turno.
- **Aceptar sobrepago en cualquier medio.** Un sobrepago con tarjeta no tiene
  vuelto posible: la única forma de "devolverlo" es una nota de crédito al
  día siguiente. Aceptarlo en silencio convierte un error de tecleo en un
  problema contable.
- **Guardar lo entregado en `monto` y derivar lo aplicado.** Obligaría a
  todos los consumidores de `pago.monto` —cierre de caja, contabilidad,
  reportes, el replay del hub— a saber restar el vuelto. Uno que se olvide
  descuadra los libros, y son cinco.
- **Redondear solo en el frontend.** Deja al servidor comparando 18.525
  contra 18.53: el cajero ve el monto exacto y el cobro lo rechaza igual.

## Consecuencias

- **Migración** `d4b7e91c2f80`: `pago.vuelto`, `Numeric(10,2)` con
  `server_default='0'` y sin backfill — los pagos viejos no tuvieron vuelto.
- `PagoOut` gana `vuelto`; `VentaItemOut` gana `descuento`, que faltaba y
  hacía que reabrir una orden reconstruyera un total a precio de lista.
- El arqueo puede, por primera vez, explicar por qué el cajón tiene menos
  billetes que la suma de los cobros.
- La propina sigue siendo un movimiento de caja aparte y no un campo del
  pago: no es plata de la venta y no va en el comprobante.
- RN-COM-016 queda enmendada: la suma de los pagos **cubre** el total, no lo
  iguala.
