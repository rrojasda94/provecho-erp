# ADR-038 — Los grupos de opciones viajan por variante en la carta

- Estado: aceptado
- Fecha: 2026-08-12

## Contexto

No se podía vender una pizza. El cajero elegía "Pizza", elegía "Personal",
tocaba Guardar —la pantalla lo dejaba— y al enviar el pedido el servidor
respondía 409: `'Pizza Personal': 'Sabor' exige elegir 1, llegaron 0`. Sin
venta confirmada no hay comanda, así que tampoco llegaba nada al KDS ni se
podía cobrar.

La causa es una desalineación entre dónde vive el dato y dónde se lo leía.

ADR-023 dejó dicho que **la variante es el producto que se prepara**: tiene su
receta y su precio completo (RN-COM-022). ADR-035 §5 agregó que **el sabor es
un grupo obligatorio de una sola opción** (`minimo=1, maximo=1`), sin tipo de
grupo aparte. Las dos cosas juntas implican que los grupos cuelgan de la
**variante** — y así los crea el catálogo real (`pizzas_demo.py:285`
`crear_grupo_opcion(producto_id=variante.id, …)`).

Pero `GET /sales/carta` armaba `extras[]` una sola vez, del **padre**:

```python
grupos_por_id = {g.id: g for g in repo.grupos_de(producto.id)}   # el PADRE
for vinculo in repo.extras_de(producto.id):                      # el PADRE
```

El padre no tiene grupos —no se prepara, no se vende—, así que la carta
devolvía `extras: []` para la pizza. El PDV no dibujaba "Sabor", `queFalta()`
no tenía nada que exigir y habilitaba Guardar. La validación del servidor
(`_validar_grupos`, que sí consulta `grupos_de(variante.id)`) hacía su trabajo
correctamente y rechazaba. El resultado para el cajero era un error
**imposible de corregir desde la pantalla que lo produjo**.

Los tests no lo veían porque los dos casos de grupo usan "Pizza Simple", un
producto **sin** variantes: ahí el grupo vive en el propio producto y la carta
lo encontraba.

## Decisión

### 1. Cada variante lleva su propio `extras[]`

`VarianteDeCartaOut` gana `extras: list[ExtraDeCartaOut]`, con la misma forma
que el de nivel producto. El `extras[]` del producto se conserva y sigue
sirviendo a los productos simples.

**Por variante y no fusionado en el padre.** Fusionar era la alternativa
tentadora —una sola lista, un solo lugar de dónde leer— y es incorrecta por
dos razones independientes:

- **Los grupos difieren por tamaño de verdad.** "Peperoni Personal" y
  "Peperoni Familiar" son dos productos distintos con dos recetas distintas
  (otros gramos). Una lista fusionada tendría que elegir cuál de las dos
  mostrar antes de saber qué tamaño va a pedir el cliente.
- **El servidor no aceptaría lo fusionado.** `_armar_extras` rechaza con
  `ReglaNegocio` cualquier extra que no esté vinculado al producto exacto que
  se vende (`admite_extra(padre_prod.id, extra_id)`). Ofrecer los extras del
  padre sobre una variante sería volver a construir el mismo bug con otra
  forma: la pantalla ofreciendo algo que el servidor va a rechazar.

Es **aditivo**: un consumidor que ignore el campo se comporta como antes.

### 2. El PDV lee los extras del producto que se prepara

`extrasOfrecidos(item, variante)`: si el producto tiene presentaciones, los de
la variante elegida y nada más; si no tiene, los del producto. **Sin
fusionar**, por lo de arriba — la regla del cliente es exactamente la que
aplica el servidor.

Cambiar de tamaño **limpia los extras ya elegidos**: sus ids son de otra
variante y no significan nada bajo la nueva.

### 3. El sabor lleva precio de lista, y vale cero

Segundo bloqueo, independiente del anterior: `pizzas_demo` creaba las opciones
de sabor **sin precio**, y la carta descarta todo extra sin precio vigente en
el ámbito (mismo criterio que un producto sin precio). Aunque se arreglara §1,
los sabores no habrían aparecido.

Se les fija **precio 0**. El sabor no cobra aparte —la variante ya lleva el
precio completo (RN-COM-022)— pero "no cuesta nada" y "no tiene precio" son
cosas distintas: la primera es un precio, la segunda es una falta de dato, y
la carta hace bien en no ofrecer lo segundo.

Se evaluó exceptuar del filtro a los extras de grupos obligatorios (un sabor
obligatorio sin precio "obviamente" vale 0) y se descartó: sería una regla
implícita que solo se descubre leyendo el código, y dejaría pasar un extra
que quedó sin precio **por error** exactamente igual que uno que vale cero
a propósito.

## Alternativas descartadas

- **Fusionar los extras del padre y de la variante**: el servidor rechaza los
  del padre al vender la variante. Ver §1.
- **Que el PDV pida la ficha de cada variante** (`GET /productos/{id}`) al
  abrir el configurador: es la vuelta a la red que la carta existe para
  evitar, en el endpoint más caliente del PDV y en el momento en que el
  cajero está esperando.
- **Mover los grupos al padre y heredarlos**: rompe el caso real —los sabores
  de la Familiar no son los de la Personal— y contradice RN-COM-022.
- **Que `_validar_grupos` mire también los grupos del padre**: haría pasar la
  venta sin arreglar la pantalla. El cajero seguiría sin poder elegir sabor;
  simplemente el pedido saldría a cocina **sin** decir de qué es la pizza.

## Consecuencias

- `GET /sales/carta` gana `variantes[].extras[]`. Aditivo, sin migración.
- El hub offline **no necesita nada**: replica las tablas crudas
  (`producto_comercial`, `producto_opcion_grupo`, `producto_comercial_extra`)
  y arma la carta con este mismo `precios.py`. Un solo arreglo cubre los dos
  lados.
- La tarjeta del PDV cuenta los extras de la presentación más surtida y no la
  suma de todas: seis sabores en tres tamaños dirían "18 extras".
- `detalle_producto` (`catalogo.py`) **no cambia**: es por producto a
  propósito, y sus consumidores ya piden la ficha de cada variante por
  separado. Queda anotado en Deuda técnica que la pantalla de ficha
  (`/catalogo/productos/{id}`) muestra solo los grupos del padre, así que en
  un producto con presentaciones se ve vacía; el lugar de trabajo de esa
  estructura es el lienzo (ADR-035).
- Prueba nueva `test_la_carta_trae_los_grupos_de_cada_variante`: el caso con
  variantes que faltaba, de la carta hasta el 409 y el 201.
