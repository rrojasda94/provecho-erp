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

> **Consecuencia conocida y aceptada.** Con esta regla, media Americana +
> media Peperoni **no** descuenta el jamón: la condición exige que los dos
> grupos coincidan. Es el comportamiento de Odoo y el que el archivo de
> Charlie's ya asume, así que se implementa así y no "mejor" — importar sus
> datos y que descuenten distinto sería peor que el bug.
>
> La corrección es de **datos, no de motor**: una línea por mitad, a media
> cantidad, cada una condicionada a un solo atributo. `test_variantes_odoo.py`
> prueba las dos formas una al lado de la otra para que la diferencia sea
> visible. Anotado en Deuda técnica; se salda desde la planilla.

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
