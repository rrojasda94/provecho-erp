# ADR-035 — Restas ("sin X") y lienzo de nodos de receta

- Estado: aceptado
- Fecha: 2026-08-08

## Contexto

`RN-PRD-004` dice desde el principio que el sistema aplica los modificadores
de un producto comercial **siempre en el orden tamaño → combinación → extras
→ restas**. Tres de esos cuatro tramos ya existían y no como una capa nueva,
sino repartidos en el modelo que ADR-018 y ADR-023 dejaron armado:

| Tramo | Cómo está modelado | Desde |
|---|---|---|
| Tamaño | variante = producto hijo (`producto_padre_id`), receta y precio propios | ADR-023 |
| Combinación (sabor) | opción de un grupo con `minimo=1, maximo=1`, con receta propia | ADR-018 + ADR-023 |
| Extras | `producto_comercial_extra` + `producto_opcion_grupo` | ADR-018 |
| **Restas** | — | **nada** |

Y el empaque, que no es un modificador pero sí sale del mismo plato, vive en
`producto_comercial.empaque_id` + `modalidades_empaque` (RN-EMP-003).

Dos huecos, uno de dominio y otro de operación:

**1. Las restas nunca se implementaron.** "Sin cebolla" se escribía en la
nota libre a cocina (`venta_item` no la guarda tipada; el PDV la mandaba
dentro del texto). El plato salía bien, pero **el inventario descontaba la
cebolla igual**. La cebolla que se quedó en la cámara aparece como faltante
en el conteo del mes, y nadie puede explicar por qué. Cuanto más se usa la
nota, peor cuadra el conteo.

**2. El árbol completo no se ve en ninguna pantalla.** La ficha del producto
muestra presentaciones y grupos en tablas separadas, y cada receta vive en
otro módulo. Para responder "¿cuánto me cuesta una Familiar de peperoni con
extra queso y sin cebolla, y qué margen deja?" hay que abrir cinco pantallas
y sumar a mano. Eso —no la falta de un modelo— era lo que hacía sentir que
las recetas no eran componibles.

## Decisión

### 1. La resta es una columna de la línea, no una tabla ni una entidad

`venta_item.sin_articulo_ids` (JSONB, nullable): array de `articulo.id`.

- **Array de ids y no una tabla**: no tiene atributos propios. Es un
  conjunto que solo se lee entero y junto con su línea. Una tabla sería
  vacía de datos y llena de joins. Cuando haga falta reportar "qué se quita
  más" —que hoy nadie pidió— la tabla se justifica; hoy no.
- **`articulo_id` y no `receta_item_id`**: la línea de receta se edita y se
  borra, el artículo no. Guardando la línea, una receta corregida mañana
  dejaría restas históricas apuntando a nada y la comanda reimpresa de una
  venta vieja diría "sin —".
- **NULL y no `[]` cuando no se quitó nada**: "no quitó nada" es la ausencia
  del dato. Es además lo que vale para todo lo vendido antes de la
  migración, sin backfill.

### 2. Lo quitable **es** la receta. No hay nada que configurar

No se agrega `receta_item.quitable` ni una tabla de quitables por producto.
`GET /sales/productos/{id}/quitables` devuelve los insumos de la receta del
producto, y el servidor rechaza al vender cualquier `articulo_id` que la
receta no ponga.

Se evaluó el flag —"que Producción decida que no se puede pedir pizza sin
masa"— y se descartó por ahora: sería una segunda fuente de la misma verdad,
y el caso que evita ("sin masa") es absurdo pero inocuo, porque la resta no
cambia el precio y cocina ve el pedido antes de prepararlo. Si aparece un
caso real donde quitar un insumo arruina el plato de forma cara, el flag es
una columna y un checkbox. Queda anotado en Deuda técnica.

**Endpoint aparte y no un campo de `GET /carta`**: la carta se pide entera al
abrir el PDV, y meter esto ahí haría una consulta de receta por producto para
un dato que el cajero mira en una línea a la vez. Se pide al abrir el
configurador de esa línea, y depende de la variante elegida — una Familiar y
una Personal no llevan lo mismo.

### 3. La resta no cambia el precio; sí el consumo

Quitar cebolla no abarata la pizza (el costo de la cebolla en el plato es
marginal y el precio se fija por lista, RN-PRC-003). Pero **sí** tiene que
mover inventario: `inventory.listeners._consumos_de_items` salta el insumo
quitado, y la reposición por anulación / nota de crédito devuelve
exactamente lo mismo que se consumió — reponer lo que nunca salió dejaría
stock de más.

Se descartó permitir descuento por resta: obligaría a modelar precio
negativo por opción y a tocar el cálculo server-side de precio y de margen,
para un caso que la operación no pidió.

### 4. El lienzo de nodos: se recorre y se edita la estructura, no las recetas

Pantalla nueva `/catalogo/productos/{id}/nodos`. Dibuja el árbol por filas
—producto → tamaño → grupos → extras → restas → empaque— y al tocar los
nodos arma un plato: un panel recalcula en vivo la **receta fusionada**, el
costo y el margen de esa combinación exacta.

- **Desde el lienzo se edita la estructura** (agregar tamaño, abrir grupo,
  colgar una opción, quitar un extra, borrar un grupo, elegir empaque), pero
  **no las cantidades de cada receta**: eso sigue en Catálogo → Recetas, con
  un enlace desde cada nodo. Es la corrección que ADR-023 §4 ya registró —
  el editor de receta en dos pantallas hace pensar que son dos recetas
  distintas, y el usuario lo reportó el mismo día.
- **La fusión se calcula en el cliente** (`frontend/lib/nodos.ts`) y **no se
  guarda**. Es un simulador: lo que se descuenta de verdad lo calcula el
  servidor al confirmar la venta, con Decimal. Por eso el cliente puede usar
  punto flotante sin consecuencias — el número se muestra y se descarta.
- **El precio del simulador se teclea.** El precio que cobra el PDV sale de
  la lista vigente de la sucursal (RN-PRC-003), que depende de sucursal,
  canal y modalidad; pedirla acá sería traer contexto de punto de venta a una
  pantalla de catálogo. Tecleado sirve además para lo que la pantalla quiere
  responder: "¿qué margen me deja si lo pongo a S/ 45?".
- **El frontend orquesta las dos APIs** (`sales` para la ficha, `inventory`
  para cada receta), sin endpoint compuesto ni `sales` leyendo tablas de
  `inventory` — mismo criterio de ADR-023 §4. Las recetas se piden **cuando
  el nodo entra al plato**, no todas al abrir: una pizza de 3 tamaños × 8
  sabores son 27 recetas y se muestran una a la vez.
- **Los conectores son CSS, no SVG medido en JS.** El árbol es por filas, así
  que dos líneas absolutas por fila dicen lo mismo que un cálculo de
  coordenadas, y siguen funcionando al cambiar el ancho.
- **Solo se despliega el subárbol del tamaño activo.** Dibujar los grupos de
  los tres tamaños a la vez es una maraña que no se lee; el tamaño activo se
  resalta y su subárbol se despliega debajo.

### 5. No hay "tipo de grupo" para el sabor

Se evaluó agregar `producto_opcion_grupo.tipo = combinacion|extra` para que
el lienzo distinguiera el tramo "combinación" de RN-PRD-004. Se descartó:
**un grupo de sabores ya es un grupo obligatorio de una sola opción**
(`minimo=1, maximo=1`), y la diferencia entre combinación y extra no cambia
ninguna aritmética —los dos aportan receta que se suma—. La columna solo
serviría para pintar distinto, y sería una tercera forma de decir algo que
`minimo`/`maximo` ya dicen. El botón "+ grupo" del lienzo nace marcado como
obligatorio y de una sola opción, que es la forma de crear un grupo de
sabores sin explicarle a nadie qué es un mínimo.

## Alternativas descartadas

- **Tabla `venta_item_resta`**: sin atributos propios, se lee siempre entera
  con su línea. Joins a cambio de nada.
- **`receta_item.quitable`**: segunda fuente de la misma verdad; el caso que
  evita es inocuo hoy (ver §2).
- **Restas con descuento de precio**: obliga a precio negativo por opción y a
  tocar el cálculo server-side de precio y margen. Nadie lo pidió.
- **`quitables` dentro de `GET /carta`**: una consulta de receta por producto
  en el endpoint más caliente del PDV, para un dato que se mira de a uno.
- **Guardar la receta fusionada**: sería un cuarto lugar donde vive la misma
  información (receta, línea de venta, evento de consumo) y el primero en
  quedar desactualizado.
- **Librería de canvas de nodos (react-flow y similares)**: una dependencia
  nueva para un árbol de seis filas fijas. El layout no es libre — lo dicta
  RN-PRD-004 — así que no hay nada que arrastrar ni que enrutar.

## Consecuencias

- Migración `a4f1d0c8b573`. Nada de lo ya vendido cambia de comportamiento:
  toda línea existente queda con `sin_articulo_ids = NULL`, y el listener de
  inventario trata la ausencia del campo igual que antes.
- `POST /sales/ventas` puede rechazar con 409 un caso nuevo: pedir "sin X"
  de un artículo que la receta del producto no usa. Se exceptúa el **replay
  del hub** (ADR-009): esa venta ya se preparó y se cobró, y la receta pudo
  cambiar durante el corte.
- El contrato gana tres operaciones: `GET /sales/productos/{id}/quitables`,
  `DELETE /sales/productos/{id}/extras/{extra_id}` y
  `DELETE /sales/productos/{id}/grupos/{grupo_id}`. Las dos últimas cierran
  la deuda que ADR-023 dejó anotada.
- `sales.venta_confirmada`, `sales.venta_anulada`, `sales.lineas_anuladas` y
  `sales.nota_credito_emitida` llevan `sin_articulo_ids` en cada ítem. Es
  aditivo: un consumidor que lo ignore se comporta como antes.
- El KDS y la comanda impresa muestran las restas (`SIN CEBOLLA`, sangrada y
  en mayúsculas). `sales` las nombra a través del contrato público de
  `inventory` (`nombres_de_articulos`), sin tocar su ORM.
- La réplica al hub incluye las restas en cada línea: sin ellas, el replay en
  la nube descontaría insumos que la sucursal nunca usó.
- Borrar un grupo **suelta** sus extras en vez de borrarlos: el extra es un
  producto comercial con su receta y su precio, y existe con o sin grupo.
- Queda pendiente: reordenar nodos por arrastre (hoy se teclea `orden`) y el
  flag `quitable` si aparece el caso que lo justifique — ver Deuda técnica en
  `ROADMAP.md`.
