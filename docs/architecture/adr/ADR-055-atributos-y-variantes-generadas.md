# ADR-055 — Atributos y variantes generadas (modelo Odoo), con interruptor

- Estado: aceptado
- Fecha: 2026-08-23
- Contexto: `sales` (catálogo comercial)
- Relacionado: ADR-023 (la variante es un producto hijo), ADR-035 (restas y
  lienzo), ADR-038 y ADR-042 (dónde vive el grupo de opciones), ADR-056
  (recetas condicionadas), RN-COM-036, RN-COM-022

## Contexto

Tres correcciones sobre el mismo modelo en once días —ADR-035 §5, ADR-038,
ADR-042— y el usuario volvió a reportar lo mismo: *"la forma actual no está
funcionando"*. Las tres eran correctas y ninguna tocaba la causa.

El modelo dice que **la combinación vendible es una fila de producto**
(`producto_comercial` con `producto_padre_id`, ADR-023) y que **el sabor es un
grupo obligatorio de una sola opción** (`producto_opcion_grupo` con
`minimo=1, maximo=1`, ADR-035 §5). Las dos decisiones fueron buenas para el
problema que había —tres tamaños con receta y precio propios— y no escalan al
que hay.

Los números salen del catálogo real de Charlie's, exportado de Odoo:

| Hecho | En el modelo actual |
|---|---|
| `Pizza MitadxMitad Familiar`: atributos `Mitad 1 F` (19 valores) x `Mitad 2 F` (19) | **361 filas de producto con 361 recetas**, por tamaño |
| 429 plantillas de producto, 195 recetas, 526 líneas | se teclean de a una |
| 7 atributos, uno de ellos "Quitar ingrediente" con 12 valores | no existe la noción de atributo |

361 recetas no es un problema de pantalla ni de rendimiento: es que **nadie
las puede mantener**. Cambiar los gramos de jamón obliga a abrir 361 fichas.

Odoo resuelve esto separando dos cosas que acá son una: la **plantilla** (qué
se ofrece) de la **variante** (qué se vendió). El puente son
`product.attribute` / `product.attribute.value` /
`product.template.attribute.line` / `product.template.attribute.value`.

## Decisión

### 1. Entran las cuatro tablas de Odoo, con sus nombres traducidos

| Provecho | Odoo | Qué es |
|---|---|---|
| `atributo` | `product.attribute` | La dimensión: "Tamaño", "Mitad 1" |
| `atributo_valor` | `product.attribute.value` | "Familiar", "Hawaiana" |
| `producto_atributo_linea` | `product.template.attribute.line` | Qué atributo ofrece un producto |
| `producto_atributo_valor` (**PTAV**) | `product.template.attribute.value` | Ese valor **en ese producto** |

**El PTAV es la pieza central** y no una indirección de más. "Familiar" como
idea es una sola, pero "Familiar en la Pizza Peperoni" tiene un sobreprecio
propio y puede estar retirado en un producto y vigente en otro. Apuntar al
valor global obligaría a guardar `precio_extra` en una tabla puente idéntica a
ésta con otro nombre. Es además a lo que apuntan las dos cosas que importan:
la variante materializada y la línea de receta condicionada (ADR-056).

Se agregan dos más: `producto_variante_valor` (qué combinación **es** una
fila hija) y `producto_exclusion` (combinaciones que no existen —
`product.template.attribute.exclusion`).

`producto_exclusion` no entra por completitud: el catálogo real la necesita el
primer día. En una pizza **mitad y mitad las dos mitades tienen que ser
distintas** (RN-COM-038) — media hawaiana y media hawaiana no es una
mitad-y-mitad, es una hawaiana entera, que ya se vende como su propio producto
con su receta y su precio. Sin la exclusión el PDV deja armar una combinación
que no existe y la venta la acepta.

### 2. La variante generada **sigue siendo** `producto_comercial`

No es una concesión al modelo viejo: es lo que hace que precio server-side
(RN-PRC-003), margen por variante, ruteo del KDS, `venta_item.precio_unitario`
congelado, `GET /carta` y la réplica al hub **sigan funcionando sin escribir
una línea**. Es el mismo criterio con el que ADR-023 eligió el producto hijo
sobre el atributo con recargo, y con el que ADR-018 modeló los extras como
productos comerciales.

Lo que cambia es **quién** crea esas filas —el generador, no una persona— y
qué llevan colgado: los PTAV que las identifican.

### 3. Los tres modos de `create_variant`, y por qué hacen falta los tres

`atributo.modo_variante`:

| Modo | Odoo | Materializa | Para qué |
|---|---|---|---|
| `siempre` | `always` | todas las combinaciones al vincular | Tamaño: cada uno tiene receta y precio propios |
| `dinamica` | `dynamic` | la fila, la primera vez que se vende | atributos anchos donde pocas combinaciones se piden |
| `nunca` | `no_variant` | nada | Mitad 1 / Mitad 2 / "sin cebolla": no cambian el producto, cambian lo que se consume |

Con un solo modo no alcanza, y la elección es lo que decide si el catálogo se
sostiene: `Mitad 1 F` x `Mitad 2 F` en `siempre` son las 361 filas del
problema; en `nunca` son cero filas y una receta de 26 líneas.

El export de Charlie's marca los siete atributos como "Instantáneamente"
(`siempre`). **Se importa tal cual y se avisa**: el importador reporta cuántas
variantes generaría cada atributo antes de generarlas, y la pantalla ofrece
pasarlo a `nunca`. Reinterpretarlo en silencio sería decidir por el usuario
algo que cambia su catálogo.

### 4. `precio_extra` se suma, no reemplaza

`producto_atributo_valor.precio_extra` se agrega al precio que resuelve la
lista vigente (RN-PRC-003). La lista sigue mandando sobre el precio base por
sucursal, canal y modalidad — que es lo que ADR-023 protegió al descartar el
"atributo con recargo", y sigue en pie: acá el recargo es **además** del
precio de lista, no en lugar de él.

### 5. Una variante hereda los valores de su padre

Misma regla que `grupos_efectivos` / `extras_efectivos` (ADR-042) y por la
misma razón, que ya costó dos correcciones: quien arma un producto a mano
cuelga el atributo del **padre** —cuando lo crea todavía no hay variantes— y
el importador lo cuelga donde diga la planilla. **Mientras el lugar importe,
siempre hay una mitad de los catálogos rota.**

### 6. La migración es solo aditiva

Ninguna columna existente cambia de tipo ni de nulabilidad, y todo lo nuevo
nace NULL o con default. La consecuencia práctica es la que importa: **la
imagen 0.6.0 corre contra este esquema sin enterarse**, así que volver atrás
es `./scripts/desplegar.sh 0.6.0` y no hace falta downgrade para volver a
operar.

Esta promesa deja de valer a partir de ADR-063 (2026-08-24): la migración que
borra `producto_comercial.lienzo_pos` sí exige `alembic downgrade` explícito
para volver a una versión anterior. Sigue valiendo para todo lo demás de este
ADR y de ADR-056.

> **Nota (2026-08-24)**: este ADR documentó acá un interruptor
> `parametro_empresa` → `sales` / `catalogo.modelo_odoo` que nunca se llegó a
> leer en ningún lugar del código — ni la carta, ni el PDV, ni la validación
> de grupos lo consultaban. Se retira la afirmación en vez de construir un
> interruptor que nadie usó (ver ADR-063 §6).

## Alternativas descartadas

- **Reemplazar `producto_comercial` por plantilla + variante separadas.** Es
  el modelo de Odoo puro y rompería las siete FK que otros módulos tienen
  contra el catálogo, más precio, margen, KDS, carta y réplica. El costo es
  todo el ERP; la ganancia, un diagrama más prolijo.
- **Un módulo `catalog` aparte.** Ya se había evaluado y descartado
  (`docs/roadmap/deuda/modulo-sales.md`): mover cinco tablas y sus FK no gana
  nada, porque la autorización es por permiso y no por módulo.
- **Solo el modo `nunca`.** Alcanza para pizzas y no para tamaños, que
  necesitan precio y receta por combinación. Además obligaría a reinterpretar
  el archivo de Odoo al importarlo.
- **Solo el modo `siempre`, fiel al export.** Son exactamente las 361 filas
  que hacen inmanejable el catálogo de hoy.
- **Guardar el atributo dentro del PTAV** (denormalizado) para no consultar.
  Ver ADR-056: se resuelve por el contrato público de `sales`, que ya existe.
- **Migrar los datos actuales al modelo nuevo automáticamente.** El camino es
  exportar, revisar en Excel e importar — que es justo lo que ADR-057
  construye. Un backfill silencioso sobre 429 productos es el modo de falla
  que ADR-046 existe para evitar.

## Consecuencias

- Migración `e2b7c40d91af`, aditiva. Seis tablas nuevas y columnas nullable
  en `producto_comercial` (`ref_externa`, `lienzo_pos`) y `venta_item`
  (`valores_variante_ids`).
- `venta_item.valores_variante_ids` (JSONB, nullable) guarda los PTAV
  elegidos. Misma forma y mismas razones que `sin_articulo_ids` (ADR-035 §1):
  columna y no tabla, NULL y no `[]` para lo vendido antes de la migración.
- `POST /sales/ventas` puede rechazar con 409 dos casos nuevos: elegir un
  valor que el producto —o su padre— no ofrece, y elegir una combinación
  que `producto_exclusion` declara imposible (RN-COM-038). Se exceptúa el
  replay del hub (ADR-009), igual que las restas.
- Los cinco eventos de venta llevan `valores_variante_ids` en cada ítem. Es
  **aditivo**: un consumidor que lo ignore se comporta como antes.
- `producto_comercial.lienzo_pos` cierra la deuda que ADR-035 §5 dejó abierta.
  El argumento de entonces —"cualquier cambio de estructura recoloca todo"—
  deja de valer cuando el árbol lo dicta el atributo y no la topología fija.
- `sales` estrena contrato público `atributo_de_valores`, que consume
  `inventory` (ver ADR-056).
- Queda pendiente: el generador de combinaciones para `siempre`/`dinamica`, la
  pantalla de matriz y el lienzo sobre el modelo nuevo — ver `ROADMAP.md`.
