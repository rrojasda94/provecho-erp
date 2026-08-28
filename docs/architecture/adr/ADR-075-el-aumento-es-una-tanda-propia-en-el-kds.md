# ADR-075 — El aumento es una tanda propia en el KDS

- **Estado:** aceptada — **enmienda ADR-043 §1 y ADR-044**
- **Fecha:** 2026-08-28
- **Contexto:** `sales` (`venta_item.tanda`, KDS), `frontend/app/pdv`
- **Relacionado:** ADR-043 (la orden abierta sigue viva), ADR-044 (cadena de
  estaciones), RN-COM-029, RN-CUP-014

## Contexto

ADR-043 hizo posible que una mesa pida de a poco sin abrir una cuenta nueva.
Lo que no resolvió —y lo dejó anotado como deuda— es que **la cocina no
distingue lo que acaba de entrar**.

Dos cosas se juntaban:

1. **El PDV mandaba la línea al confirmar el diálogo del producto**, no al
   pulsar Enviar. El botón quedaba en "Enviado" e inerte desde el primer
   envío, así que no había ningún gesto de confirmación: tocar un producto
   sobre una mesa abierta ya era mandarlo a cocina.
2. **El KDS agrupa por venta.** El postre pedido a las 21:40 aparecía en la
   misma pastilla que la entrada de las 20:15, con el reloj de la pastilla
   corriendo desde que se abrió la mesa.

El resultado, tal como lo reportó el turno: no se podía "hacer un aumento" —
se podía marcar productos que salían de a uno, sin revisar, y que en cocina
se veían como si hubieran estado ahí desde el principio.

## Decisión

### Un entero en la línea: `venta_item.tanda`

En qué envío a cocina salió. 1 es el alta del pedido y cada
`POST /ventas/{id}/items` posterior suma uno. La tanda es **de la operación,
no de la línea**: todo lo que el trabajador confirmó de un envío sale junto,
en la misma comanda.

**Un entero de la venta y no un timestamp.** Dos líneas del mismo envío
tienen `created_at` parecidos pero no iguales, y agrupar por tiempo obliga a
elegir una tolerancia arbitraria que se rompe el día que el cajero tarde en
confirmar el diálogo del segundo producto. Es también lo que descarta la
propuesta que la deuda traía escrita ("mostrar la hora de la línea"): esa
resuelve *ver* la antigüedad, no *separar* la comanda.

**Los extras heredan la tanda de su plato.** No se preparan aparte
(RN-CUP-014), así que tampoco se anuncian aparte. El agrupado del KDS lo hace
por la tanda del padre y no por la de cada fila: si un dato viejo las tuviera
descoordinadas, el extra caería en un grupo donde su plato no está y —como la
tarjeta se arma recorriendo platos— desaparecería de la pantalla.

**Al mover líneas a otra orden se les da la tanda del destino** (ADR-071). La
del origen numeraba los envíos de otro pedido y chocaría con los de este; una
sola tanda para todo el lote, porque se movieron juntas.

### El PDV confirma con "Enviar aumento"

Marcar un producto sobre una orden abierta ya **no** llama al servidor: la
línea queda en el borrador, marcada como pendiente y rotulada "Sin enviar" en
el ticket. El botón vuelve a estar vivo como **"Enviar aumento (N)"** y manda
todo de una sola vez.

Es el mismo gesto que el primer envío —se marca, se revisa, se confirma—, que
es lo que el turno pedía: poder armar el aumento entero antes de mandarlo.

**Quitar sigue el mismo criterio.** Una línea pendiente se quita sin tocar el
servidor: nunca existió del otro lado, no repone nada y no necesita firma. Una
ya enviada sigue por `anular-lineas`, con la ventana de 5 minutos de ADR-043 —
y ahora **con motivo real**, tecleado por quien quita. El campo era
obligatorio en el contrato y el PDV mandaba `"Anulado desde PDV"` en las mil
anulaciones del año: el reporte de anulaciones lo leía y no decía nada.

Vale igual para mesa, para llevar y delivery: `agregar_lineas` y
`anular_lineas` nunca miraron la modalidad.

### Preparación agrupa por tanda; despacho, no

`cola_pantalla` emite una tarjeta por `(venta, tanda)` en las pantallas de
preparación, y una por pedido en las de despacho.

No es una inconsistencia: son dos preguntas distintas. La cocina prepara lo
que acaba de entrar y necesita ver cada envío con su propio reloj; el
despacho arma la bolsa contra el pedido completo (ADR-044, RN-CUP-004) y
partirlo en dos tarjetas sería la forma de entregar media orden.

Por eso `venta_id` deja de ser la clave de una tarjeta de cocina: lo es el par
`venta_id + tanda`.

### El reloj de la tanda arranca con la tanda

`creado_en` de una tarjeta de preparación es el `created_at` más viejo de su
tanda, no el de la venta. Si contara desde el pedido, una mesa abierta hace
dos horas que acaba de pedir un café saldría en rojo, y el semáforo dejaría
de significar algo el día que alguien se siente a comer sin apuro. Despacho
sigue contando desde el pedido, que es lo que el cliente está esperando.

### Y lo que la cocina lee, además de qué preparar

Dos notas, y son distintas:

- **`venta_item.nota`** — lo que el mesero dice de **ese plato**: "bien
  cocida", "sin sal". El diálogo del producto la pedía desde el primer PDV y
  el dato moría en el navegador: no había columna, `cuerpoLinea` no la
  mandaba, y al releer la orden se perdía. Era decorativa.
- **`venta.nota_cocina`** — cómo se sirve **el pedido**: "servir todo junto",
  "bebidas al final", "primero el pan al ajo". Es del pedido y no de una
  línea: colgarla de la primera la escondería dentro de un plato, y repetirla
  en todas sería pedirle al cocinero que las compare. Va **al pie** de la
  pastilla —primero se lee qué hay que preparar, después cómo sale— y en
  **todas las tandas**, porque es una instrucción del pedido y la tanda que
  no la llevara la ignoraría sin saberlo.

Las dos son texto libre, y eso es deliberado: lo estructurado ya existe y es
mejor —las restas descuentan inventario, los atributos cambian la receta—,
pero siempre queda un pedido del comensal que ninguna de las dos cosas
expresa. Lo que no puede pasar es que el campo exista en la pantalla y el
dato no llegue a la cocina.

La nota del pedido **se puede cambiar con la orden ya en cocina**
(`PUT /ventas/{id}/nota-cocina`, mismo permiso que crear y sin firma): así se
pide de verdad, a mitad del servicio. No toca el total, no mueve inventario y
no cambia qué se prepara — solo en qué orden sale.

## Alternativas descartadas

- **Mostrar la hora de cada línea en la misma tarjeta** (lo que proponía la
  deuda de ADR-043). Deja ver cuál llegó después, pero no separa la comanda:
  el cocinero sigue leyendo una tarjeta que mezcla lo que ya preparó con lo
  que acaba de entrar.
- **Una orden nueva por cada aumento.** Es el estado anterior a ADR-043 y su
  bug: la misma mesa termina con dos cuentas, que se cobran y se entregan por
  separado.
- **Agrupar por ventana de tiempo** (todo lo que entró en los últimos N
  segundos es una tanda). Una tolerancia arbitraria que falla justo cuando el
  cajero duda entre dos productos.

## Consecuencias

- **Migración** `a1c47e6b90d2`: `venta_item.tanda`, entero con
  `server_default='1'` y sin backfill. Todo lo vendido hasta hoy fue una sola
  tanda para efectos de la cola, que es exactamente como se venía mostrando.
- `PedidoColaOut` gana `tanda`, con default 1 — despacho y el historial la
  mandan así, porque ahí la unidad sigue siendo el pedido entero.
- Cierra la deuda 🔶 «El KDS no distingue una línea agregada de las
  originales» de `deuda/modulo-sales.md`.
- **Migración** `b5d21f8a0c36`: `venta_item.nota` y `venta.nota_cocina`,
  nullables y sin backfill.
- El evento no cambia: `agregar_lineas` sigue publicando
  `sales.venta_confirmada` con el delta (ADR-043 §3). La tanda es del KDS, no
  de contabilidad ni de inventario.
- El lote del hub lleva `tanda` y las dos notas: sin eso, el replay en la
  nube mostraría como un solo envío lo que en el local fueron tres, y la
  comanda reimpresa de una venta vieja no diría lo mismo que dijo la primera
  vez (ADR-009).
- ADR-043 §1 sigue valiendo en lo que decidió —agregar no exige la firma de
  nadie—; lo que esta enmienda cambia es **cuándo** se manda.
