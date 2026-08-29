# ADR-076 — La promoción se aplica sola, y no toca el descuento manual

- **Estado:** aceptada
- **Fecha:** 2026-08-28
- **Contexto:** `sales` (`promocion`, `venta_promocion`, `total_a_cobrar`),
  `frontend` (PDV, Comercial → Promociones)
- **Relacionado:** RN-COM-017 (descuento manual), RN-PRM-001..008, ADR-061
  (cupón de la landing), ADR-018 (frontera explícita), ADR-023 (topes por
  permiso)

## Contexto

Tres cosas bajan el total de un pedido y el ERP solo tenía dos:

| | Quién decide | Quién firma |
|---|---|---|
| **Descuento manual** (RN-COM-017) | el cajero lo pide | un supervisor con su PIN |
| **Cupón** (ADR-061) | el cliente lo trae | nadie: el cupón *es* la autorización |
| **Promoción condicional** | **el pedido lo cumple** | nadie: no interviene una persona |

La tercera faltaba entera. Estaba anotada como deuda desde el slice del PDV,
con el ejemplo escrito —"segunda pizza a mitad de precio si pide dos del
mismo tamaño, en días vigentes, sobre el precio base de la más barata"— y con
la advertencia que este ADR toma como punto de partida.

Lo que existía y **no** es esto: `promocion_cupon` (ADR-061) hace una sola
cosa —un porcentaje, una vigencia y un interruptor— y emite un código por
cliente. Ahí hay algo que canjear; acá no.

## Decisión

### La frontera: nada de esto escribe en `venta.descuento_*`

Esos campos son el descuento manual: un acto humano con motivo y autorizador.
Si el motor escribiera ahí, el reporte de descuentos no podría distinguir lo
que regaló un supervisor de lo que aplicó una regla — y ese es el único dato
por el que ese reporte existe. Por eso las promociones aplicadas viven en
**`venta_promocion`**, tabla propia: un pedido puede activar más de una, y
aplanarlas en columnas obligaría a elegir cuál se guarda.

### Cuatro tipos, y la vigencia es de todos

Las cinco familias que el negocio pidió se reducen a cuatro tipos más una
vigencia común, porque "solo por día/hora" no es una condición sobre el
pedido:

| Tipo | Condición | Cubre |
|---|---|---|
| `nxm` | lleva N de un conjunto de productos/categorías | 2x1, 3x2 y **"la segunda a mitad de precio"** — el beneficio es un % sobre las unidades liberadas, no un booleano de "gratis" |
| `cantidad` | X unidades de un producto o categoría | "6 gaseosas → 15 % en las gaseosas" |
| `combo` | lleva **todos** estos productos | precio fijo del conjunto, o uno de ellos gratis |
| `monto_minimo` | total del pedido ≥ piso | % o monto; **con piso 0 es el precio de una franja horaria** |

Que `nxm` lleve porcentaje en vez de "gratis sí/no" es lo que evita un quinto
tipo para la promoción más común del rubro. Que `monto_minimo` acepte piso 0
es lo que evita un sexto para el martes de pizzas.

### Un solo `promocion` con `condicion`/`beneficio` en JSONB

Los cuatro tipos comparten vigencia, ámbito y resolución de solapes —que es
casi toda la entidad— y difieren en dos o tres números. Cuatro tablas serían
cuatro veces la misma fila con una columna distinta, cuatro migraciones cada
vez que aparezca un tipo, y un `UNION` para listarlas.

Mismo criterio que `venta_item.sin_articulo_ids`: un objeto que solo se lee
entero, junto con su fila. La forma la valida Pydantic al dar de alta y las
reglas que cruzan campos las valida el caso de uso (un `nxm` no puede liberar
tanto como exige llevar).

### La aritmética es pura y la vigencia entra por parámetro

`domain/promociones.py` no toca la base ni el reloj: `dia` y `hora` son
argumentos. Es lo que permite probar "el martes a las 20:00 con dos pizzas"
sin montar una venta ni mover el reloj del proceso, y es la mitad del módulo
que más se va a tocar cuando aparezca el quinto tipo.

La hora es la del **negocio** (`fechas.ahora()`), no la del contenedor: en
Docker el proceso corre en UTC, y un martes de pizzas hasta las 23:00 se
apagaría a las 18:00 hora Perú.

**La franja puede cruzar la medianoche.** Un happy hour de 22:00 a 02:00 es
un caso real, y compararlo como un rango simple lo dejaría siempre fuera.

### Cada unidad la consume una sola promoción

Se recorre por prioridad descendente y cada regla marca las unidades que usó.
Sin eso, un 2x1 y un "20 % en pizzas" se cobrarían los dos sobre la misma
pizza y el local regalaría más de lo que aprobó.

Se cuenta en **unidades y no en líneas**: "la segunda pizza" con una sola
línea de cantidad 2 tiene que activarse igual.

**Lo liberado es siempre lo más barato del conjunto.** Al revés, un 2x1 entre
una familiar y una personal regalaría la familiar, que no es lo que ninguna
carta del rubro promete.

Una promoción `acumulable` **ignora lo consumido y no consume nada**: se suma
encima, que es lo que la palabra dice. Las dos mitades importan — si mirara
lo consumido, el orden de prioridad decidiría si se aplica; y si consumiera,
un "10 % sobre todo el pedido" impediría que el 2x1 se activara después. Es
el único caso en que dos promociones tocan la misma unidad, y por eso el
default es `False`.

### El evento del aumento lleva lo que sube **la cuenta**, no la lista

`POST /ventas/{id}/items` publica `sales.venta_confirmada` con "lo confirmado
en esta operación" (ADR-043 §3), y hasta ahora eso era el precio de lista de
las líneas que entraron. Con una promoción de por medio dejan de ser lo
mismo: la segunda pizza de un 2x1 entra por S/ 40 y no le suma un sol al
total. Asentar los 40 dejaría los libros por encima de lo que la caja cobró.

Pasa a ser el **delta de `total_a_cobrar`** antes y después de la operación.
Sale exacto sin caso especial: incluye la promoción que se activó, la que se
cayó, y el reprorrateo del descuento manual.

El delta puede ser **negativo** —agregar una gaseosa que dispara un "20 %
desde S/ 50" baja el total más de lo que la línea suma— y se publica tal
cual. Taparlo con un cero dejaría los libros por encima de lo cobrado, que es
exactamente el error que este cálculo viene a evitar.

`inventory` no se entera: consume `items`, que sigue siendo el detalle de lo
que entró y es lo que hay que descontar del almacén — la promoción rebaja el
precio, no el consumo.

### Se recalcula entero en cada cambio del pedido

`recalcular_promociones` borra lo aplicado y lo evalúa de nuevo. Es
idempotente y destructivo a propósito: los cuatro caminos que cambian un
pedido —crear, agregar líneas, quitar líneas, mover— la llaman sin llevar la
cuenta de qué se activó antes. Una promoción que dejó de cumplirse porque el
cajero quitó una pizza desaparece sola, que es lo correcto; y el aumento que
completa el 2x1 lo activa, que es lo que una mesa que pide de a poco necesita
(RN-COM-029).

### La promoción baja **antes** que el descuento manual

`total_a_cobrar` resta primero las promociones y después el porcentaje que
firmó el supervisor. Al revés, un 20 % firmado sobre un pedido con 2x1
regalaría casi la mitad del ticket sin que nadie lo haya aprobado así. Por lo
mismo, el tope de `permiso.restricciones` (ADR-023) se mide contra la base ya
promocionada.

Entre cuentas, la promoción se **prorratea** igual que el descuento manual:
se activó sobre el pedido, no sobre la cuenta que toque cobrarse primero.

### El PDV no gana ningún botón

Las promociones se pintan en el ticket **con su nombre**, una línea por cada
una. El cajero no las pide ni las firma; lo único que tiene que poder hacer
es explicarlas. Si el nombre no alcanza, la promoción está mal nombrada —
pero callarla es peor: el cliente ve un total que no cuadra con la carta.

El alta vive en **Comercial → Promociones**, con
`sales.gestionar_promociones` (el mismo que ya cortaba una campaña de cupón).
Separado de `sales.aplicar_descuento` porque crear una regla que regala
margen todos los días no es lo mismo que firmar un descuento puntual.

## Alternativas descartadas

- **Reusar `venta.descuento_*`.** Es la que la deuda ya había descartado, y
  con razón: destruye la única distinción que el reporte de descuentos hace.
- **Una tabla por tipo de promoción.** Ver §"Un solo `promocion`".
- **Extender `promocion_cupon`.** Hace otra cosa: emite un código por cliente
  y lo apaga al canjearlo. Las dos van a convivir; unificarlas hoy sería
  especificar de más algo que el negocio no usa así.
- **Evaluar al cobrar y no en cada cambio.** El cajero le canta el total al
  cliente antes de cobrar: una promoción que aparece recién en el cobro es
  una discusión en el mostrador.
- **Un motor de reglas genérico** (expresiones configurables). Cuatro tipos
  con parámetros cubren lo que el negocio pidió y se pueden explicar en un
  formulario; un lenguaje de reglas se configura mal una vez y nadie sabe por
  qué el pedido salió a ese precio.

## Consecuencias

- **Migración** `c8e4f30b7a19`: `promocion` y `venta_promocion`, ninguna con
  backfill. Lo vendido hasta hoy no tenía promociones que aplicar.
- `sales.gestionar_promociones` amplía su alcance: ya no es solo cortar una
  campaña de cupón. No hay permiso nuevo ni rol que reasignar.
- Los extras **no participan**: son línea propia (RN-COM-021) pero no se
  piden solos, y dejarlos entrar haría que un 2x1 de pizzas regalara un queso
  extra.
- Un consumo de personal no promociona: ya vale cero (RN-COM-025).
- Terminar una promoción no reescribe ninguna venta: lo aplicado quedó
  congelado en `venta_promocion`, con el nombre que el cliente leyó
  (RN-PRM-005).
- Queda fuera —y anotado en deuda— el **motor de precios promocionales por
  lista** que `data-model.md` §6 describe para `promocion` (material
  promocional, guion de atención, capacitación). Esto es la mitad que baja el
  total; la otra mitad es una decisión del área comercial que nadie pidió
  todavía.
