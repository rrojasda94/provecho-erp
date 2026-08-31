# ADR-034 — El consumo de personal es un tipo de orden, no un descuento

- **Fecha:** 2026-08-09
- **Estado:** Aceptada
- **Contexto:** el grupo alimenta a su personal en fines de semana, feriados
  y días de alta actividad. Hoy eso no se registra en ninguna parte, y el
  costo de esa comida desaparece dentro del costo de ventas.

## Contexto

Lo que el negocio pide: que la comida del personal **se prepare y se
despache como cualquier pedido** —comanda, KDS, entrega— pero con **precio
cero**, sin emitir venta, y que **el costo sí se refleje** como alimentación
de personal, para poder regularizarlo.

Lo que el ERP tenía disponible antes de esta decisión:

1. **Descuento manual del 100% con motivo `cortesia` o `colaborador`**
   (RN-COM-017). Existe, está auditado y lo autoriza un supervisor.
2. **Merma** (`reserva_stock` tipo `merma`, ADR-028). Descuenta insumo y
   llega a contabilidad.

Ninguno sirve, y no por falta de campos:

- El descuento del 100% deja una **venta** de S/ 0.00. Esa venta publica
  `sales.venta_confirmada`, que `accounting` asienta como **ingreso** y
  `marketing` atribuye como venta de una campaña. Un plato regalado al
  personal no es ninguna de las dos cosas.
- Peor: esa venta **no se puede cerrar**. `registrar_pago` exige `monto > 0`
  y `pagos_cubren_total` exige igualdad exacta, así que la orden queda en
  `orden` para siempre — cuenta abierta en el PDV y en cada cierre de caja.
- Y al cobrarse, `_cerrar_cuenta` crea el comprobante sin preguntar: se
  emitiría una boleta de S/ 0.00 a SUNAT.
- La merma describe **pérdida** (vencido, dañado, robo). Un plato que el
  personal se comió no se perdió: se consumió con autorización. Además la
  merma es de insumo, y acá lo que se decide es preparar un producto de la
  carta.

## Decisión

### 1. `venta.tipo` — `venta` | `consumo_personal`

La orden se tipa en origen. Un `consumo_personal` nace con **todas sus
líneas en cero**: `crear_venta` no consulta lista de precios y **tampoco
acepta el precio que mande el cliente** (el PDV podría mandarlo; el replay
del hub también). El precio no se descuenta después — nunca existe.

Se agregan `consumo_motivo` (`fin_semana` | `feriado` | `alta_actividad` |
`capacitacion` | `otro`) y `consumo_autorizado_por`. El motivo es **enum
cerrado y no texto libre**: existe para agrupar el gasto por causa, y un
texto tecleado no agrupa.

**No se registra quién comió.** Es una decisión explícita del negocio: se
alimenta al turno, no a personas nominadas, y un beneficiario obligatorio
volvería el registro un trámite que el encargado va a saltarse.

### 2. Evento propio, no `sales.venta_confirmada`

`sales.consumo_personal_registrado` viaja con el mismo payload de ítems.
Publicar `venta_confirmada` habría sido más corto y habría metido un ingreso
de cero en el libro y un lead atribuido en marketing. El evento nuevo lo
consume solo `inventory`.

### 3. Estado terminal `cerrada`

La entrega (`POST /sales/ventas/{id}/entrega`) cierra el consumo. Es su
**único cierre posible**: nunca pasa por caja, y sin un estado terminal
quedaría abierto en la pestaña del PDV y en el arqueo. `registrar_pago` y
`aplicar_descuento` lo rechazan con 409 antes de tocar comprobantes.

### 4. `tipo_movimiento = consumo_interno`, valorizado por el emisor

El insumo sale con su propio tipo, no como `consumo_venta`: no tiene ingreso
detrás y su costo es gasto, no costo de ventas. Un reporte de consumos por
tipo de movimiento lo separa sin heurísticas.

`inventory` publica `inventory.consumo_personal_valorizado` con el **monto
al `costo_promedio`**, calculado sobre **las mismas líneas de consumo que
movieron el stock**. Es el mismo criterio de `inventory.merma_registrada`
(ADR-028): valoriza quien conoce el movimiento. Recalcularlo en `accounting`
—o desde `costo_unitario_de_recetas`, que divide por el rendimiento mientras
el listener de consumo no lo hace— daría dos números distintos para el mismo
plato.

`accounting` lo asienta por `regla_asiento`: debe gasto de alimentación de
personal, haber existencias. Sin regla configurada se omite y se loguea,
como todo el resto de la generación automática.

### 5. Anular reversa el gasto

`sales.venta_anulada` / `sales.lineas_anuladas` llevan ahora `tipo`.
Cuando es un consumo, `inventory` repone el insumo **y** publica
`inventory.consumo_personal_reversado`, con el que `accounting` anula el
asiento de ese origen (asiento inverso, RN-CTB-002). Sin ese segundo paso el
insumo volvía al almacén y el gasto quedaba inflado por comida que nadie
comió.

### 6. Lo firma un encargado, con PIN — y en cada cambio, no solo al alta

Permiso propio `sales.registrar_consumo_personal`, separado de
`sales.crear`, verificado por el token de elevación de `POST /auth/autorizar`
— mismo patrón que el descuento manual y el relevo de caja. Es comida
gratis: sin firma, cualquiera se sirve. Queda en `audit_log` con motivo,
autorizador y quién lo registró.

**Corrección del 2026-08-30.** La versión original pedía la firma una sola
vez, al crear la orden. Con la orden ya abierta, cualquiera con `sales.crear`
podía seguir sumándole platos por `POST /ventas/{id}/items` —el aumento de
RN-COM-029, pensado para la mesa que pide de a poco— y quitarle líneas dentro
de la ventana de corrección sin que nadie firmara. Es decir: la firma
autorizaba *ese* pedido, no el consumo, y el consumo podía crecer solo.

Ahora un consumo de personal exige el token de elevación en **cada** cambio
de sus líneas: `sales.registrar_consumo_personal` para sumar,
`sales.anular` para quitar, y ahí la ventana de corrección **no exime** —
existe para que el cajero arregle su propio tecleo, no para deshacer lo que
un encargado firmó.

Se deja **fuera** el borrador del PDV: mientras el pedido no salió a cocina
no hay inventario movido ni nada que un encargado haya autorizado todavía.
Pedir PIN por cada toque del catálogo convertiría armar una orden de personal
en un trámite, que es la forma segura de que el encargado deje de
registrarla.

**Las ventas normales no cambian**: agregar sigue sin firma de nadie y quitar
sigue firmándose solo pasada la ventana. La asimetría es el punto: en una
venta el producto se cobra, y acá se regala.

## Consecuencias

- El PDV gana un botón "Consumo de personal": el ticket muestra la franja,
  los montos en "—" y **el botón Cobrar desaparece** (no se deshabilita).
  En su lugar aparece **"Cerrar cuenta"** (2026-08-30), que registra la
  entrega. Que Cobrar desapareciera dejaba el ticket sin acción final: el
  único cierre posible vivía en la pantalla de despacho, así que el turno que
  no la abría terminaba con consumos abiertos en cada arqueo. El botón llama
  al **mismo** `POST /ventas/{id}/entrega` y no a un cierre propio —dos
  caminos para el mismo hecho darían dos rastros del mismo plato— y por eso
  hereda su exigencia: todos los ítems en `listo`. Consecuencia aceptada: una
  sucursal que no marca en el KDS sigue sin poder cerrar. Es el precio de no
  inventar un cierre que diga que salió comida que la cocina nunca reportó.
  El KDS muestra un distintivo y la comanda imprime `** CONSUMO PERSONAL **`
  con su motivo: la cocina prioriza distinto un pedido de cliente.
- `venta.estado` gana un quinto valor. Todo lector de estados —cierre de
  caja, tableros, reportes— sigue funcionando porque `cerrada` no aparece en
  ninguno de sus filtros; lo que no debe pasar es que alguien la cuente como
  venta al agregar un filtro nuevo. La excepción deliberada es la lista de
  **cuentas cerradas del PDV** (2026-08-30, antes rotulada "Cobrados"), que
  sí pide `estado=cerrada` además de `pagada`: la orden desaparecía de
  "Cuentas" al cerrarse y no reaparecía en ningún lado, así que el turno
  perdía el rastro de lo que se preparó sin cobrar. Va con su propia etiqueta
  y con "—" en la columna de plata, no con S/ 0.00 — el arqueo sigue sin
  sumarla.
- El gasto depende de que la empresa configure sus dos cuentas y la
  `regla_asiento`. El ERP **no siembra plan de cuentas** para nadie, así que
  esto es coherente con el resto, pero un consumo registrado sin regla no
  llega a contabilidad (queda en el log y en el movimiento de inventario).
- El **replay del hub** (ADR-009) transporta `tipo`, `consumo_motivo` y
  `consumo_autorizado_por` en `VentaSyncIn`. Sin eso, un consumo registrado
  durante un corte llegaba a la nube como venta de S/ 0.00 — el mismo
  criterio que ya se aplicaba al descuento manual: el encargado firmó en la
  sucursal y su PIN no se vuelve a pedir arriba.
- **Saldada el 2026-08-30:** `sales.consumo_personal_registrado` es una
  emisión del catálogo de reportes (ADR-033), dirigida a Gerencia y
  Contabilidad, con número de orden, motivo y autorizador — los dos últimos
  campos se agregaron al payload del evento para eso. Lo que sigue como deuda
  es el **acumulado** por sucursal/mes: hoy cada consumo avisa por su cuenta,
  y sumarlos es `GET /sales/ventas?tipo=consumo_personal` o los movimientos
  `consumo_interno`.

## Alternativas descartadas

- **Descuento del 100% con motivo `colaborador`.** Ver Contexto: declara un
  ingreso que no existe, emite comprobante y la orden no cierra nunca.
- **Registrarlo como merma de los insumos.** Describe pérdida, no consumo
  autorizado, y obligaría a que alguien tradujera a mano "una pizza" en su
  lista de insumos — que es exactamente lo que la receta ya sabe hacer.
- **Un canal o una modalidad nuevos** (`canal="interno"`). Serían la misma
  columna que decide precio y ruteo de listas de precios; un consumo de
  personal se pide en el mismo PDV y se lleva en mesa o para llevar como
  cualquier otro.
- **Módulo aparte.** Es una orden, un tipo de movimiento y una regla de
  asiento. Un módulo exigiría los siete registros de `module-guide` para no
  agregar ningún dominio propio.
- **Beneficiario obligatorio (FK a `usuario`/`trabajador`).** Decisión del
  negocio: se alimenta al turno. Puede agregarse después sin romper nada —
  una columna nullable más.
