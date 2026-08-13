# ADR-044 — La cocina es una cadena de estaciones, no un solo paso

- **Estado:** aceptada
- **Fecha:** 2026-08-13
- **Contexto:** `sales` (KDS), `venta_item`, `kds_pantalla`
- **Relacionado:** RN-CUP-013, RN-CUP-002, RN-CUP-003, ADR-009 (sincronización)

## Contexto

Una pizzería no prepara un plato en un solo lugar. La masa se arma en un
sitio, se hornea en otro y se despacha en un tercero, y quien está en el
horno no necesita ver lo que todavía no llegó.

El KDS no podía expresar eso. `kds_pantalla.tipo` distinguía
`preparacion` de `despacho` y el ruteo era **solo por categoría**: la
pizza aparecía a la vez en armado y en horno, cualquiera de los dos podía
tacharla, y tacharla la dejaba `listo` sin haber pasado por el horno.
Despacho, además, veía la misma pantalla que una estación —el mismo
componente con otro filtro— así que mostraba ítems para tachar en vez de
decir qué falta y por quién se espera.

Lo que no alcanzaba: `venta_item.estado_preparacion` tiene cuatro estados
fijos (`pendiente`, `en_preparacion`, `listo`, `entregado`) y no puede
representar N estaciones. Agregar `en_horno` habría atado el dominio a la
cocina de una marca concreta.

## Decisión

Dos enteros y una función.

- **`kds_pantalla.orden`**: el eslabón de la estación en la cadena.
- **`venta_item.etapa_kds`**: el eslabón en el que va la línea.
- **`_estacion(cadena, producto, desde)`**: la primera estación de
  preparación activa con `orden >= desde` que atiende la categoría del
  producto.

Esa función resuelve las dos preguntas del KDS, y por eso es una sola:

- **Qué muestra una pantalla**: la línea está en esta estación si
  `_estacion(cadena, producto, item.etapa_kds)` cae en su `orden`.
- **A dónde va al tacharla**: `_estacion(cadena, producto, actual.orden + 1)`.
  Si devuelve `None`, no queda cadena por delante y la línea pasa a
  `listo`.

`estado_preparacion` **no cambia**: `pendiente`/`en_preparacion` mientras
recorre, `listo` al terminar la cadena, `entregado` por el endpoint de
entrega (RN-CUP-006). `sales.pedido_listo` se sigue publicando donde se
publicaba.

Consecuencias que salen gratis:

- **Una bebida se salta el horno sola.** El horno no atiende su categoría,
  así que la barra es su único eslabón y tacharla la deja lista. No hay
  configuración de excepciones.
- **Dos estaciones con el mismo `orden` son el mismo eslabón**, trabajando
  en paralelo con categorías distintas (horno y barra a la vez).
- **Todo lo ya configurado sigue igual.** Las columnas nacen en 0: una
  cocina de una estación es una cadena de un eslabón.

**Despacho sale del componente de cocina.** `despacho-cliente.tsx` muestra
una tarjeta por **pedido** con cuántas líneas van, en qué estación está
cada una y por quién se espera; no tacha ítems, porque marcar preparado es
un acto de la estación que preparó (RN-CUP-003).

Y **despacho deja de filtrar por categoría**. Podía configurarse con
`categoria_ids` y entonces mostraba media orden, lo que hace imposible el
control que le da sentido: verificar el pedido completo contra la comanda
antes de entregarlo (RN-CUP-004). El selector desaparece de su formulario —
un control que no hace nada es peor que ninguno.

## Por qué `>=` y no `==`

`_estacion` busca el primer eslabón **igual o posterior** al de la línea.
Con `==` exacto, desactivar el horno a media noche dejaría todo lo que
estaba en su eslabón sin ninguna pantalla que lo muestre: pedidos
invisibles en plena operación, que es la peor forma de fallar en cocina.
Con `>=`, la línea cae sola a la siguiente estación que la acepte.

Por el mismo motivo el siguiente eslabón se busca desde la estación
**actual** y no desde `etapa_kds + 1`: cuando el eslabón exacto ya no
existe, `etapa_kds` apunta más atrás que la estación real y sumarle uno
devolvería esa misma estación — la línea rebotaría ahí para siempre.

## Alternativas descartadas

**Un estado nuevo por estación** (`en_armado`, `en_horno`). Ata el enum del
dominio a la cocina de una marca: una sucursal con plancha necesitaría una
migración, y `transicion_preparacion_valida` tendría que conocer el orden
de las estaciones de cada local.

**Tabla de ruteo** (`categoria × estación → siguiente estación`). Expresa
lo mismo que `orden` con una tabla y dos joins más, y hace falta mantenerla
coherente: una fila que apunte a una estación borrada es un pedido perdido.
Con un entero no hay a qué apuntar mal.

**FK de `venta_item` a `kds_pantalla`.** La línea guardaría **quién** la
atiende en vez de **dónde va**. Desactivar una pantalla dejaría pedidos
apuntando a algo que ya no opera, y habría que decidir qué hacer con ellos
en una migración de datos en vez de que caigan solos al eslabón siguiente.

## Consecuencias

- Migración `b2e91f7c40aa`: dos columnas NOT NULL con default 0, sin
  backfill.
- **`orden` entra en la réplica del hub** (`RecursoSync` de
  `kds_pantalla`). Sin eso, durante un corte todas las estaciones del local
  caerían al mismo eslabón y el ruteo se rompería justo cuando no hay red.
  `venta_item.etapa_kds` **no** se sincroniza: el push replaya la venta
  como un `POST /ventas` nuevo y nunca llevó `estado_preparacion`, así que
  el avance de cocina ya era local por diseño.
- `ItemColaOut` gana `etapa_kds` y `estacion`; `PedidoColaOut` recupera
  `tipo` y `consumo_motivo`, que el `response_model` venía filtrando en
  silencio pese a que `cola_pantalla` los devolvía — la cocina no estaba
  viendo qué pedidos eran consumo de personal.
- La cola de una estación sigue mostrando lo que ya mandó al eslabón
  siguiente, con el destino a la vista. El pedido sale de esa cola cuando a
  la estación no le queda nada pendiente, no línea por línea.

## Enmienda (2026-08-13) — la unidad de cocina es el plato, no la fila

Al probarlo, una **Pizza Personal Peperoni** salía en la tarjeta como dos
ítems: `1 Pizza Personal` y `1 Peperoni`. El sabor es una fila propia de
`venta_item` colgada por `padre_venta_item_id` (ADR-023), y el KDS no
distinguía padres de hijos: no mencionaba esa columna en ninguna parte.

**Un extra no es una unidad de trabajo.** Nadie prepara un peperoni; se
prepara la pizza que lo lleva. Así que:

- el payload lo anida (`ItemColaOut.extras`) y la cola recorre solo padres;
- el ruteo mira la categoría **del plato**, no la del extra;
- marcar el plato marca sus extras, en el mismo estado y el mismo eslabón;
- la comanda lo imprime sangrado, como ya hacía con las restas.

Sigue siendo fila propia por lo que ADR-023 decidió —receta, precio,
anulación—, pero **el avance en cocina deja de ser suyo**. El comentario de
`venta_item.py` que lo justificaba con "su propio avance en cocina" quedó
corregido: esa parte era la equivocada.

Dos cosas que esto arregla de paso:

- **Un extra sin `categoria_id` colgaba el pedido.** Como ítem propio, una
  estación filtrada por categoría no lo atendía, así que se quedaba
  `pendiente` para siempre y `pedido_entregable` —que suma TODOS los
  ítems— nunca daba verdadero. Todos los extras de `pizzas_demo` están en
  ese caso.
- **Anular un plato con extras reventaba contra Postgres.**
  `fk_venta_item_padre` es `NO ACTION`, el PDV manda solo el id del padre, y
  borrarlo dejaba al hijo apuntándolo. SQLite no valida FKs, por eso la
  suite entera pasaba en verde; el fixture de `test_pdv_slice.py` ahora
  enciende `PRAGMA foreign_keys=ON` para que pruebe lo que la base real hace
  cumplir. Además la anulación no reponía el insumo del extra.
