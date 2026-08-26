# ADR-066 — Los atributos llegan al PDV

- Estado: aceptado
- Fecha: 2026-08-25
- Contexto: `sales` (carta, venta, KDS, sincronización offline), frontend (PDV)
- Relacionado: ADR-023/035/038/042 (grupos de extras), ADR-055 (atributos y
  variantes), ADR-056 (recetas condicionadas), ADR-063 (los atributos vuelven
  a la tabla; **este ADR supera su §3**), ADR-009 (modo offline),
  RN-COM-036/037/038/039, **RN-COM-040** (nueva)

## Contexto

Probando staging, el usuario reportó que la pizza MitadXMitad no ofrecía
elegir sabores: el configurador del PDV mostraba únicamente la lista de
«Sin…» y ninguna opción. El diagnóstico dio algo peor que un problema de
pantalla.

**Conviven dos generaciones del modelo de opciones y el PDV solo conoce la
vieja.**

- **Mecanismo A** (ADR-023/035/038/042): `producto_opcion_grupo` +
  `producto_comercial_extra` + un `producto_comercial` con `es_extra=True`
  por opción. Es lo único que lee `GET /carta` (`precios._extras_de`).
- **Mecanismo B** (ADR-055/056/063): `atributo` → `atributo_valor` →
  `producto_atributo_linea` → `producto_atributo_valor` (PTAV) →
  `producto_exclusion`. Es donde MitadXMitad guarda sus sabores.

`precios.py` no importaba ni una tabla del mecanismo B. La cadena completa:
`variantes[].extras = []` → `agruparExtras([]) = []` → el bloque no se dibuja
y **tampoco avisa** → `queFalta` no exige nada → «Guardar» habilitado → la
pizza se cobra **sin sabores** → ninguna línea condicionada de la receta se
activa → **no se descuenta ningún insumo**. El faltante aparece recién en el
conteo del mes, cuando ya nadie puede atarlo a esa venta.

Lo que sí se veía —el «Sin…»— viene de otro endpoint (`quitables_de`), que no
depende de ninguna de las dos generaciones. De ahí que fuera lo único en
pantalla, y de ahí que el síntoma pareciera «sobran restas» en vez de «faltan
sabores».

Los conteos en la base de staging fijaron el alcance real:

| Dato | Valor |
|---|---|
| `producto_opcion_grupo` (mecanismo A) | **0 filas** |
| Productos con atributos | solo MitadXMitad Familiar y Mediana |
| `producto_atributo_valor` con `precio_extra ≠ 0` | **0** de 68 |
| Exclusiones cargadas | 34 |
| Líneas de receta condicionadas | 467 |

O sea: en el catálogo real **ningún** producto tenía opciones que el PDV
supiera mostrar, y la máquina de ADR-056 estaba cargada y sin usar.

ADR-063 dejó el PDV fuera a propósito (§3: *«tocar el camino de la venta es
exactamente el riesgo que había que evitar»*). Esa decisión fue correcta para
su alcance —construir las pantallas de catálogo sin arriesgar el cobro— y es
la que este ADR supera, porque el costo de no tocarlo resultó ser una venta
que no descuenta.

## Decisión

**1. La carta gana `atributos` y `exclusiones`, aditivos.**
`CartaItemOut` y `VarianteDeCartaOut` ganan los dos campos con default `[]`.
No se traducen los PTAV a `ExtraDeCartaOut`: un extra es un
`producto_comercial` que nace como línea cobrada y viaja por
`producto_comercial_id`; un PTAV no es un producto y viaja por
`valores_variante_ids`. Son dos caminos distintos en `ventas.py`, y
disfrazar uno de otro obligaría igual a un discriminador en el DTO — más el
stepper de cantidad de `FilaExtra`, que no significa nada en un «elige
exactamente uno».

**2. Una sola función alimenta la carta y el validador.**
`catalogo.atributos_ofrecidos(session, productos)` la consumen `precios.carta`
y `ventas._validar_atributos`. Es la decisión estructural del cambio: con el
filtro escrito dos veces, la pantalla dejaría de ofrecer lo que el servidor
exige y el producto quedaría **invendible** — el peor desenlace posible acá,
y el único que no se nota hasta el mostrador. Mismo criterio que
`admite_extra_efectivo`, compartido por carta y venta desde ADR-042.

Resuelve **por lote**: la carta recorre el catálogo entero y `_extras_de` ya
es N+1; sumarle cuatro consultas por variante convertiría abrir el PDV en
cientos de idas a la base.

**3. Se ofrece todo lo que no es `siempre`.**
Filtro: la línea cuelga del producto **o de su padre** (herencia de ADR-042,
la misma de `valores_ofrecidos`), PTAV activo, `atributo_valor` activo, y
`modo_variante != 'siempre'`. Los `siempre` ya se materializaron como
variantes y volver a preguntarlos sería pedir dos veces la misma elección.
`dinamica` **sí** se pregunta: hoy se comporta como `nunca` (deuda de
ADR-063) y `valores_ofrecidos` no filtra por modo, así que excluirla dejaría
un atributo que el servidor acepta y la pantalla nunca ofrece.

**4. RN-COM-040: ofrecido es obligatorio.**
No se agregan `minimo`/`maximo` a `producto_atributo_linea`. Multi-valor por
atributo no tiene consumidor —la condición agrupa por atributo y
`producto_variante_valor` es un valor por atributo— y cero elegidos es
justamente el bug. La regla se hace cumplir al confirmar la venta, con
excepción del replay del hub.

`if not pedidos: return None` en `_resolver_valores_variante` **no se toca**:
ahí NULL = «no eligió» es correcto para las ventas anteriores a la migración.
El agujero se cierra un nivel arriba, en `_armar_lineas`.

**5. Las exclusiones viajan como ayuda de pantalla.**
El servidor ya rechaza (`combinacion_excluida`), pero al confirmar el pedido
entero: el cajero se enteraba de que no podía repetir sabor cuando ya no
estaba mirando la pizza. La pastilla excluida se dibuja **apagada, no
oculta** — una opción que desaparece se reporta como «falta el sabor»,
mientras que una apagada dice por qué no se puede.

**6. `precio_extra` empieza a cobrarse.**
Estaba documentado como sumando en cuatro lugares y **nada lo sumaba**: una
columna editable desde la ficha que no cobraba. Se suma en el servidor
(`precios.recargo_de_valores`), antes de fijar el precio de la línea. El
replay con precio provisto no se recotiza (ADR-009), así que no se cobra dos
veces. Se verificó contra la base real que hoy no hay ningún valor con
recargo distinto de cero: activarlo no mueve ningún precio existente.

**7. Offline entra en el mismo cambio, no después.**
`sales.sincronizacion` replica las cinco tablas de atributos y
`inventory.sincronizacion` agrega `aplica_valores` a `receta_item` —replicaba
`expresion` pero no la condición, que es lo que decide si el insumo sale del
almacén—. Sin esto, RN-COM-040 haría que el hub **rechace toda venta de
MitadXMitad durante un corte**: exactamente el caso que el modo offline
existe para evitar.

**8. Cocina sigue sabiendo qué prepara.**
`kds._valores_por_item` espeja `_restas_por_item`, y la comanda imprime una
línea por valor, antes de extras y restas —dicen *qué es* el plato, no qué se
le agregó—. Sin esto la comanda de una MitadXMitad dejaba de decir qué
mitades lleva, que es lo único que el pizzero necesita de ese plato: antes lo
decía porque el sabor era un extra.

## Consecuencias

- El PDV pide un sabor por mitad y no deja guardar sin ellos. La pizza
  MitadXMitad pasa a descontar lo que corresponde.
- La sección «Sin…» arranca **colapsada** (`<details>` nativo, mismo patrón
  que la ficha de reporte): con veinte insumos empujaba fuera de la vista
  justo lo que el cajero viene a elegir.
- **Reabrir una línea ya enviada pierde los valores**: `VentaItemOut` no
  devuelve `valores_variante_ids`. Con RN-COM-040 eso ahora es un 409
  explícito al reenviarla —falla ruidosa— en vez de una venta que se cobra
  sin descontar. Queda anotado como deuda.
- Las dos generaciones **siguen conviviendo**. Migrar el mecanismo A al B es
  otro cambio, con migración de datos y de recetas; acá no se toca el seeder
  demo ni se desactiva nada.
- `modo_variante='dinamica'` sigue sin materializar: ahora se **pregunta**
  como `nunca`, que es lo que el servidor ya aceptaba.

## Alternativas descartadas

- **Traducir los PTAV a extras** para reusar la UI existente. Más barato en
  la pantalla y mentiroso en el contrato: el `producto_comercial_id` sería un
  PTAV, que `_armar_item` resolvería como producto y devolvería 404. Hay que
  poner un discriminador igual, y encima queda escondido dónde importa: al
  mandar la venta.
- **Extender ADR-063** en vez de escribir este. Ese ADR decidió
  explícitamente lo contrario; reescribirlo para que diga lo inverso borra el
  rastro de por qué se hizo así primero.
- **Validar solo en el PDV.** El kiosko y la central de pedidos entran por el
  mismo endpoint, y una regla que vive en una pantalla no es una regla.
