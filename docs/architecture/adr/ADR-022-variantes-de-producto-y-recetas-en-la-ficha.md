# ADR-022 — Variantes de producto, grupos de opciones y recetas en la ficha

- Estado: aceptado
- Fecha: 2026-08-03

## Contexto

El catálogo comercial existente asume que un producto es una cosa con una
receta y un precio: `producto_comercial.receta_id` es NOT NULL y `precio`
cuelga del producto. La operación real de Charlie's Pizzas no se deja
describir así.

Una **Pizza Peperoni** se vende en tres tamaños —Personal, Mediana,
Familiar—. No son el mismo plato con recargo: cada tamaño lleva **otra
receta** (no es la misma masa escalada; cambian el bollo, los gramos de
queso y a veces el proceso) y **otro precio**. Además admite extras, y
algunos de esos extras deberían ser de elección obligatoria ("¿qué salsa?")
mientras que otros son opcionales ("¿doble queso?").

Tres problemas concretos:

**1. Dónde vive la variante.** Modelarla como atributo con recargo
("+S/ 20 si es familiar") obliga a construir precio, margen y costeo por
tamaño desde cero, y deja el margen de contribución —lo único que dice si
un tamaño conviene— fuera del alcance de las tablas que ya lo calculan.

**2. Qué hace obligatorio a un grupo de extras.** Un flag `obligatorio` y un
`minimo` conviven mal: son el mismo dato dicho dos veces, y dos datos que
dicen lo mismo terminan diciendo cosas distintas.

**3. Cómo se teclea una receta.** Pasar Personal a Familiar es aritmética de
servilleta: "1000 gramos entre 3 porciones", "180 por 1.5". Hacerlo con
calculadora fuera del sistema es exactamente donde entra el error de tipeo
que después aparece como faltante de inventario. Y una receta escrita a
mano es 15 líneas que nadie quiere volver a teclear para el tamaño
siguiente.

## Decisión

**1. La variante es un producto hijo (`producto_comercial.producto_padre_id`).**
Personal, Mediana y Familiar son tres filas de `producto_comercial` colgadas
de "Pizza Peperoni", cada una con su `receta_id` y su fila propia en
`precio` — **precio completo, no delta**. `receta_id` pasa a nullable: el
padre agrupa y no se vende (RN-COM-022).

Se eligió esto sobre atributos con recargo porque **todo lo que ya existe
sigue funcionando sin escribir una línea**: precio server-side por lista
(RN-PRC-003), descuento de insumos por `sales.venta_confirmada`, ruteo KDS,
`venta_item` con su precio congelado, margen de contribución por tamaño, y
la réplica al hub de sucursal. Es el mismo criterio con el que ADR-018
modeló los extras como productos comerciales, y por la misma razón.

El costo aceptado: padre e hijo son la misma tabla, así que las reglas
—"una variante no admite variantes", "el padre no puede tener receta ni
precio"— las hace cumplir la capa de aplicación, no la base. Están en
`sales/application/catalogo.py` y en `precios.fijar_precio`, con test.

**2. El grupo de opciones declara un mínimo, no un flag.**
`producto_opcion_grupo(nombre, minimo, maximo, orden)` +
`producto_comercial_extra.grupo_id`. `minimo >= 1` **es** ser obligatorio;
el toggle de la pantalla escribe 1 o 0. `maximo` limita opciones distintas
del grupo; el `maximo` que ya existía en `producto_comercial_extra` limita
unidades de un mismo extra (3 porciones de queso). Son dos topes distintos
y por eso son dos columnas.

La validación corre al confirmar la venta (`ventas._validar_grupos`), no
solo en el PDV: el kiosko y la central de pedidos entran por el mismo
endpoint, y una regla que solo vive en una pantalla no es una regla. Se
exceptúa el **replay del hub** (ADR-009): una venta que ya ocurrió y se
cobró durante un corte no se rechaza porque alguien volvió obligatorio un
grupo mientras tanto.

**3. La cantidad de receta acepta aritmética y guarda el resultado.**
`receta_item.expresion` conserva lo tecleado ("1000/3") y `cantidad` guarda
el resultado **redondeado a los decimales de la unidad de medida del
insumo** (RN-GER-010, RN-COM-024). La evaluación es del **servidor**
(`shared/aritmetica.py`, `ast` con lista blanca de nodos — nunca `eval`): si
el cliente mandara resultado y expresión por separado, nada garantizaría que
uno corresponda al otro. El frontend evalúa lo mismo solo para la vista
previa mientras se escribe.

Se guarda la expresión además del número, y no solo el número, porque
reeditar "1000/3" es rehacer la división a mano si no está; y no solo la
expresión, porque el descuento de stock y el costeo necesitan un número
estable que no dependa de reevaluar texto en cada venta.

Sobre eso, dos operaciones que evitan volver a teclear: **duplicar**
(clona la receta y sus líneas con sufijo "(copy)", sin destino asignado —
dos recetas produciendo el mismo artículo dejarían a `production` sin saber
cuál explotar) y **escalar por factor**, que redondea **cada línea con su
propia unidad**: 1.5 bollos de masa son 2 (la unidad no admite decimales)
mientras que el queso en gramos sí acepta el decimal.

**4. La receta se edita dentro de la ficha del producto.** Patrón Odoo: no
se sale a otra pantalla para decir de qué está hecha una pizza. El frontend
orquesta las dos APIs (`inventory` para la receta, `sales` para el producto);
no hay endpoint compuesto ni `sales` escribiendo tablas de `inventory`.
`inventory` estrena contrato público de lectura de receta
(`queries_publicas.receta_resumen`), que `sales` usa para validar que la
receta asignada existe.

> **Corregido el mismo día.** Al construir el módulo de recetas
> (`/catalogo/recetas`), el editor quedó incrustado en los dos lados y el
> usuario lo reportó de inmediato: "si ya creé la receta, ¿para qué la vuelvo
> a ver y editar en productos?". Tenía razón — lo mismo en dos pantallas hace
> pensar que son dos recetas distintas. **La ficha del producto ahora elige
> recetas, no las edita**: una tabla de presentaciones con un desplegable de
> las ya creadas y un enlace al módulo que sí las arma. Lo que sobrevive de
> esta decisión es lo importante: que asignar la receta no obligue a salir
> del producto, y que el frontend orqueste las dos APIs sin cruzar módulos en
> el backend.

**5. Los nombres se normalizan a formato título en el servidor.** El mismo
insumo escrito "queso mozzarella", "Queso Mozzarella" y "QUESO MOZZARELLA"
son tres filas distintas en un reporte. `shared/texto.a_titulo` aplica la
regla del español —conectores en minúscula salvo al inicio, siglas cortas
respetadas— y el frontend hace lo mismo al salir del campo. La normalización
del servidor es la que vale: la API tiene más clientes que esa pantalla.

## Alternativas descartadas

- **Atributos con recargo (tamaño como opción con `+monto`)**: uniforme en
  papel, pero deja precio, margen y reporte por tamaño fuera de las tablas
  que ya los resuelven, y obliga a modelar "qué receta corresponde a qué
  combinación de atributos" — que es justo lo que `producto_comercial` ya
  sabe hacer.
- **Columna `obligatorio` además de `minimo`**: dos fuentes para el mismo
  hecho.
- **Unidad de medida propia en `receta_item`**: la receta elegiría una
  unidad distinta a la del artículo y habría dos verdades sobre la misma
  cantidad; la del artículo es la que usa el descuento de stock. La receta
  hereda la unidad del insumo (RN-UDM-001).
- **`eval()` o una librería de expresiones para la aritmética**: `eval`
  ejecuta lo que sea que llegue por la API; una librería no se justifica
  para cuatro operadores. `ast` de la stdlib con lista blanca son 40 líneas.
- **Recalcular la cantidad desde la expresión en cada uso**: haría que el
  costo y el descuento dependieran de reparsear texto, y que cambiar el
  redondeo de una unidad moviera silenciosamente recetas ya aprobadas.

## Consecuencias

- Migración `b6d1e83f47ac`. Nada de lo ya cargado cambia de comportamiento:
  todo producto existente queda sin padre (simple) y todo extra sin grupo
  (opcional).
- `POST /sales/ventas` puede rechazar con 409 dos casos nuevos: vender el
  padre de un grupo de variantes y no cumplir el mínimo de un grupo.
- El contrato de `GET /sales/carta` gana `variantes[]` en cada ítem y cuatro
  campos de grupo en cada extra. Los ítems que son variantes ya no salen
  sueltos en la grilla.
- El hub replica `producto_opcion_grupo` y las columnas nuevas (29 recursos).
- Queda pendiente: reordenar variantes y grupos por arrastre (hoy se teclea
  `orden`), quitar un extra de un grupo y borrar un grupo — ver Deuda
  técnica en `ROADMAP.md`.
