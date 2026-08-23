# ADR-056 — Líneas de receta condicionadas por variante, y con UdM propia

- Estado: aceptado
- Fecha: 2026-08-23
- Contexto: `inventory` (recetas), `sales` (venta)
- Relacionado: ADR-055 (atributos y variantes), ADR-023 (la receta hereda la
  unidad del insumo), ADR-035 (restas), RN-COM-037, RN-UDM-005, RN-UDM-001

## Contexto

ADR-055 hizo que la combinación deje de ser una fila de producto. Falta lo
otro, que es donde estaba el trabajo de verdad: **una receta que valga para
muchas combinaciones**.

En el archivo real de Charlie's, `Pizza MitadxMitad Familiar` es **una** lista
de materiales de 26 líneas. Cada línea lleva una columna
`bom_line_ids/bom_product_template_attribute_value_ids` que dice para qué
combinaciones cuenta:

```
Jamón picado | Mitad 1 F: Americana, Mitad 1 F: Hawaiana, Mitad 1 F: Rústica,
               Mitad 1 F: Mixta, Mitad 2 F: Americana, Mitad 2 F: Hawaiana,
               Mitad 2 F: Rústica, Mitad 2 F: Mixta | 0.025 | kg
```

Sin esa columna, esas 26 líneas son 361 recetas.

Hay un segundo hueco en el mismo archivo: `bom_line_ids/product_uom_id` toma
seis valores distintos —kg, Unidades, L, oz, Botella 1L, Botella 500mL— y no
siempre coincide con la unidad del artículo. `receta_item` **no tiene columna
de unidad**: ADR-023 la descartó explícitamente.

## Decisión

### 1. `receta_item.aplica_valores`: array de PTAV, NULL = siempre

JSONB nullable con ids de `producto_atributo_valor`. NULL o `[]` significa que
la línea aplica a toda combinación — que es el caso de **todas** las recetas
que existen hoy, y por eso la columna nace nullable: sin condición, el
comportamiento es exactamente el de antes, sin backfill.

Columna y no tabla, mismo criterio que `venta_item.sin_articulo_ids`
(ADR-035 §1): no tiene atributos propios y solo se lee entera junto con su
línea.

### 2. La regla de Odoo, literal: al menos un valor por cada atributo

`mrp.bom.line._skip_bom_line` → `mrp.bom._skip_for_no_variant`, verificado en
la rama `18.0`. Se agrupan los valores de la condición **por atributo**, y la
combinación elegida tiene que coincidir con **al menos uno de cada grupo**.
Entre grupos es Y; dentro de un grupo es O.

Vive en `inventory/domain/rules.aplica_a_variante`, pura y con prueba de
tabla. Es la única función de este cambio cuyo error mueve stock, así que no
comparte archivo con nada que tenga base de datos delante.

> **Consecuencia, y por qué el motor igual es el correcto.** Con esta regla,
> una línea que nombra las dos mitades solo aplica si las dos califican: media
> Americana + media Peperoni **no** descuenta el jamón. Es el comportamiento
> de Odoo, y por eso se implementa así — importar los datos de Charlie's y que
> descontaran distinto sería peor que el bug.
>
> Lo que quedó claro al cargar el archivo real es que **el dato estaba mal, no
> el motor**, y que además estaba muerto: si las dos mitades tienen que ser
> distintas (RN-COM-038), una condición que pide la misma en las dos nunca se
> cumple. La corrección es de datos y la aplica `scripts/odoo/`: cada línea
> simétrica se parte en **una por mitad, con la mitad del gramaje**. Se
> comporta igual que Odoo cuando Odoo acertaba —las dos mitades califican,
> gramaje entero— y correctamente cuando no. Ver la enmienda al pie.

### 3. Un valor huérfano forma su propio grupo

Si alguien borró el PTAV, la línea apunta a nada. Se exige el id exacto en vez
de dejar pasar la línea: la alternativa es descontar un insumo que quizá no
va, y eso descuadra el conteo del mes sin que nadie sepa por qué. La lectura
conservadora es la que hay que preferir cuando el error mueve stock.

### 4. `receta_item.unidad_medida_id` (nullable) **no** revierte ADR-023

Lo que ADR-023 descartó fue una unidad **libre**: *"la receta elegiría una
unidad distinta a la del artículo y habría dos verdades sobre la misma
cantidad"*. Eso sigue descartado.

Ésta es otra cosa: una unidad **de la misma categoría de UdM** que la del
artículo, que RN-UDM-001 admite desde siempre, y `unidad_medida.ratio` la
convierte sin ambigüedad. No hay dos verdades porque la conversión es exacta y
la unidad del artículo sigue siendo la que manda en el almacén.

Importa porque es como se compra y como se cocina: el aceite entra por litros
y la receta lleva 30 ml. Obligar a escribir "0.03" es exactamente el error de
tipeo que después aparece como faltante — el mismo argumento con el que
ADR-023 aceptó la aritmética tecleada.

NULL = la del artículo, que es el comportamiento de todo lo cargado.

### 5. Una sola cuenta para descontar y para costear

`domain/rules.consumo_de_linea` — merma más conversión — la usan
`listeners._consumos_de_items` y `recetas.costo_linea`. Estaban en dos lugares
escritas distinto. El día que una gane un paréntesis, el costo de un plato
deja de coincidir con lo que se descontó de la cámara y **ninguna de las dos
parece estar mal**.

### 6. El atributo de un valor se pide por el contrato público de `sales`

`sales.queries_publicas.atributo_de_valores(session, ids)`. Una consulta por
evento, ninguna cuando no hay líneas condicionadas.

Va por el contrato y no denormalizado dentro de `aplica_valores` porque la
condición nombra valores que el cliente **no** eligió —"aplica si la mitad es
Americana u Hawaiana"—, así que el dato no puede viajar en el evento de la
venta, que solo lleva lo elegido.

### 7. El orden de los tres filtros

En `_consumos_de_items`: primero la resta ("sin cebolla"), después la
condición, y recién entonces la conversión de unidad. Convertir algo que
después se descarta es trabajo tirado, y descartar después de convertir invita
a redondear dos veces.

## Alternativas descartadas

- **Una receta por combinación**, que es el modelo de hoy. 361 recetas que
  nadie puede mantener: cambiar los gramos de jamón serían 361 fichas.
- **Guardar el atributo dentro de `aplica_valores`** (`[{"v":…,"a":…}]`) para
  ahorrar la consulta. Es una segunda copia de algo único por construcción —un
  PTAV pertenece a una línea, y la línea a un atributo— y duplica el JSON.
- **O entre todos los valores de la condición**, sin agrupar por atributo.
  Es más simple de explicar y descontaría el jamón de las dos mitades por
  tener una sola americana. No es lo que hace Odoo ni lo que el archivo asume.
- **Dejar pasar la línea cuando el valor es huérfano.** Falla hacia descontar
  de más, que es el lado caro.
- **Recalcular la conversión desde el ratio en cada lectura de receta**, sin
  guardar la unidad. Haría que cambiar el ratio de una UdM moviera
  silenciosamente recetas ya aprobadas — mismo argumento con el que ADR-023
  descartó recalcular la cantidad desde la expresión.

## Consecuencias

- Migración `e2b7c40d91af` (la misma de ADR-055). `receta_item` gana
  `unidad_medida_id` (FK nullable), `aplica_valores` (JSONB nullable) y
  `orden`; `receta` gana `es_kit` y `ref_externa`.
- `receta.es_kit` es booleano y no un `tipo` de tres valores: Odoo tiene
  además `subcontract` y nadie lo pidió, y `recetas.TIPOS_RECETA` ya significa
  otra cosa (`subreceta` | `producto`, para filtrar el listado). Dos columnas
  llamadas "tipo de receta" con ejes distintos es cómo alguien filtra por una
  creyendo que filtra por la otra.
- `receta_item.orden` existe para que exportar dos veces dé el mismo archivo.
  Sin orden explícito, un diff contra el export anterior deja de servir.
- `_consumos_de_items` pasa a cargar las líneas **una vez por receta** en vez
  de una por ítem: dos platos de la misma pizza ya no la piden dos veces.
- `GET /inventory/recetas/{id}` devuelve la unidad **de la línea**, no la del
  artículo, cuando la línea eligió una. El editor tiene que mostrar la que se
  tecleó.
- `costo_linea` gana dos parámetros opcionales y `ratios_de_linea` los
  resuelve. Sin línea con unidad propia no hay consulta extra.
- El camino del descuento lee `unidad_medida.ratio` por primera vez.


## Enmienda (2026-08-23) — las dos mitades son distintas, y eso parte las líneas

El usuario corrigió una premisa al ver la primera carga: *"no puede haber
hawaiana + hawaiana. Puedes elegir 2 diferentes solamente. «sabor a» + «sabor
b» = «sabor b» + «sabor a»"*.

Cambia dos cosas.

### 1. La combinación de mitades iguales no existe, y el servidor la rechaza

Se usa `producto_exclusion` (ADR-055), que hasta ahora estaba creada y sin
usar. Una fila por sabor: `Mitad 1: Hawaiana` excluye `Mitad 2: Hawaiana`.

**Una sola fila, leída en los dos sentidos.** El par es simétrico; guardar el
espejo sería la misma verdad dos veces y la primera en desincronizarse.

Se valida en `_resolver_valores_variante`, al confirmar la venta, y no solo en
el PDV: el kiosko y la central de pedidos entran por el mismo endpoint, y una
regla que solo vive en una pantalla no es una regla — el mismo criterio con el
que ADR-023 §2 puso `_validar_grupos` en la venta.

### 2. Las 52 líneas condicionadas del archivo estaban muertas, y se parten

Verificado sobre el archivo real: **las 52 condiciones son simétricas**, el
mismo conjunto de sabores en las dos mitades. Con la regla nueva, una
condición que pide `Mitad 1 ∈ S` **y** `Mitad 2 ∈ S` con S de un solo sabor no
se cumple jamás; y con S de varios, deja de descontar en cuanto una mitad se
sale del conjunto.

Que sean simétricas dice cuál era la intención: **cada mitad aporta lo suyo**.
Así que cada línea se parte en dos, condicionada a una sola mitad y con la
mitad del gramaje:

```
antes:  Jamón | Mitad 1 ∈ {Ame,Haw,Rús,Mix} y Mitad 2 ∈ {Ame,Haw,Rús,Mix} | 0.025
después: Jamón | Mitad 1 ∈ {Ame,Haw,Rús,Mix} | (0.025)/2
         Jamón | Mitad 2 ∈ {Ame,Haw,Rús,Mix} | (0.025)/2
```

Igual que antes cuando las dos mitades calificaban (0.0125 × 2 = 0.025), y
correcto cuando solo califica una (0.0125, que antes era cero).

**La simetría `A+B == B+A` sale del modelo, no de ordenar nada al guardar.**
Con cada línea condicionada a una sola mitad, el total no depende de en qué
mitad se eligió cada sabor. No hace falta canonicalizar
`venta_item.valores_variante_ids` ni inventar una clave de combinación.

**La cantidad se escribe `(0.025)/2` y no `0.0125`.** El servidor evalúa la
operación y guarda las dos cosas (RN-COM-024), así que la planilla y la ficha
muestran de dónde salió el número. Es exactamente para lo que
`receta_item.expresion` existe.

**Las unidades pasan a 4 decimales**, el máximo que admite
`receta_item.cantidad` (`Numeric(12,4)`). Con 3, cada mitad de 0.025 redondea
a 0.013 y la pizza entera pasa a llevar 0.026 — un gramo de más por plato que
nadie pidió.

**Esto NO revierte la regla de §2.** El motor sigue siendo el de Odoo, y una
condición que nombra dos atributos sigue exigiendo los dos. Lo que cambió es
el **dato**, que es donde estaba el error.
