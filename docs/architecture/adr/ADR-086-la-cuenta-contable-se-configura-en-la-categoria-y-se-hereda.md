# ADR-086 — La cuenta contable se configura en la categoría y se hereda

- **Estado:** aceptada
- **Fecha:** 2026-08-30
- **Contexto:** `accounting` (plantillas, asientos, listeners), `inventory`
  (categoría, artículo), `sales` (evento de venta)
- **Relacionado:** ADR-081 (el PCGE y los estados financieros), ADR-056
  (payload aditivo), ADR-019 (la categoría), RN-CTB-001

## Contexto

Reporte del turno: *«las categorías, productos, artículos y servicios no
tienen la posibilidad de asociar a un asiento contable. Si no se puede tener
eso claro, el balance y los estados contables van a resultar mal.»*

Es exacto. `domain/plantillas.py` escribe todo producto contra los mismos
códigos: **toda venta acredita `7011` y toda compra debita `6011` y `201`**,
sea una pizza, una cerveza o la factura de la luz. Las cuentas se eligen por
`(empresa_id, evento)` y nada más — la `regla_asiento` de la empresa o, sin
ella, la plantilla de fábrica. Como los estados financieros son pura
agregación sobre `asiento_linea`, lo que escriben las plantillas es
literalmente lo que muestra el balance.

Y había media solución construida sin terminar: `categoria.asiento_contable_config`
(JSONB) existe desde la primera migración, con el comentario «cuenta contable
por tipo de movimiento». Pero era **de solo escritura**: sin tipar, sin
validar, `CategoriaOut` no lo devolvía, ninguna pantalla lo escribía y
`grep asiento_contable_config src/modules/accounting` daba cero resultados.

## Decisión

### La categoría es el único lugar donde se configura

`articulo.categoria_id` y `producto_comercial.categoria_id` apuntan a la
**misma tabla**: es el único agrupador que comparten lo que se compra y lo que
se vende. Configurar ahí alcanza para categorías, artículos, productos y
servicios de una sola vez, y evita una segunda configuración del lado de
ventas que se desincronizaría de la primera.

No hay override por artículo. Configurar 400 artículos a mano no lo hace
nadie, y el día que un artículo puntual lo necesite, la salida es una
subcategoría — que además explica por qué es distinto.

### Se hereda por el árbol `padre_id`

Una categoría sin un rol configurado lo hereda de su madre, rol por rol; sin
ancestro que lo tenga, cae en el código de fábrica de la plantilla. «Gaseosas»
debajo de «Bebidas» no configura nada.

El resolutor vive en `inventory.application.queries_publicas`, no en
`accounting`: el árbol es de `inventory` —su guard de ciclos y su profundidad
máxima están en `application/catalogo.py`— y que contabilidad lo caminara
sería reimplementar la regla de otro módulo. Carga el árbol de la empresa en
una consulta y recorre en memoria, con tope de profundidad y conjunto de
visitados: la aplicación impide crear un ciclo, pero una fila tocada a mano no
puede colgar el asiento de una venta.

### El valor es el código del PCGE, no el id de la cuenta

- El fallback de la plantilla **ya es un código**; con id habría dos caminos
  de resolución para lo mismo.
- El PCGE se siembra por empresa: el `6011` es el mismo en todas y el que el
  contador reconoce; un id es de una fila. El hub **ya replica este campo**
  entre empresas del grupo (`inventory/application/sincronizacion.py`), donde
  un id ajeno sería basura.
- Es legible en un backup.

Costo aceptado: un código que no existe en el plan de esa empresa se detecta
al validar (escritura) y al resolver (lectura, con fallback y `log.warning`),
no por integridad referencial. Es JSONB: no hay FK posible con id tampoco.

### Las líneas de la plantilla llevan rol; las de contraparte no

`LineaPlantilla` gana `rol`. Solo las líneas con rol se reparten: `1212` (la
cuenta por cobrar es del cliente), `4212` (la deuda es del proveedor), `40111`
(el IGV es del fisco) y `1041` no dependen de qué se compró, y repartirlas no
significaría nada.

Los siete roles son exactamente los que hoy alimentan una línea: `compra`,
`existencia`, `variacion_existencia`, `servicio`, `ingreso`, `merma`,
`consumo_personal`.

### El asiento reparte, y el desglose es peso — nunca importe

`crear_asiento_desde_plantilla` acepta `desglose`
(`[{categoria_id, monto, es_servicio}]`) y prorratea cada línea con rol,
cuantizando al céntimo y dando **el residuo entero a la parte mayor**
(`reparto_proporcional`). Es el mismo principio con el que `desagregar`
calcula el IGV por diferencia: dos redondeos independientes se separan por un
céntimo y descuadran el asiento.

El asiento **siempre suma el monto del evento**, aunque el desglose venga
incompleto, con una categoría sin resolver o desactualizado. Esa es la
propiedad que impide que este parámetro sea una vía para descuadrar el mayor.
Dos categorías que resuelven al mismo código producen una línea, no dos.

Sin desglose útil, el asiento es el de antes **byte por byte**. Los casos de
`test_accounting_pcge.py` que afirman el asiento de fábrica siguen verdes sin
tocarse, y eso es lo que hace este cambio desplegable.

### `regla_asiento` ignora el desglose

La empresa que configuró un mapeo de dos líneas pidió dos líneas. Repartirlas
sería pisarle una decisión que tomó a propósito.

### La categoría la resuelve accounting; el importe viaja en el evento

La frontera es **quién puede saberlo**:

- El **importe por línea** viaja en `sales.venta_confirmada` (aditivo, la
  convención que ADR-056 y ADR-035 ya fijaron para ese payload) porque
  `accounting` **no puede recalcularlo**: sale de la lista de precios, de la
  promoción aplicada, del recargo de la variante y del descuento de línea.
  Contabilizar un número distinto al que se cobró sería peor que no repartir.
- La **categoría** la resuelve `accounting` por contrato público: es una
  clasificación, cambia poco, y quien la conoce es el módulo dueño de la
  tabla. Meterla en el payload obligaría a resolver la herencia en tres
  publicadores distintos.

Un asiento nunca se edita (`anular_asiento` crea el inverso, RN-CTB-002), así
que el argumento del *snapshot* es más débil de lo que parece: lo ya escrito
no cambia porque la categoría cambie mañana.

`purchases.compra_recibida` no cambió: su payload ya traía `articulo_id`,
`cantidad` y `costo_unitario`.

### Un servicio no entra a existencias

`articulo.tipo = "servicio"` (sin migración: el campo es `String(30)` con enum
extensible por diseño). Su parte del asiento usa el rol `servicio` —default
`6399`, «Otros»— y **no escribe el bloque de destino**. Cuadra sin trucos
porque `201`(debe) y `611`(haber) son un par del mismo importe: quitarlos
juntos no mueve la balanza. Una OC mixta asienta el destino solo por la parte
inventariable.

El discriminador es `articulo.tipo` y no el rol contable de su categoría: es
el mismo hecho que decide si la cosa **mueve stock**, e `inventory` tiene que
poder saberlo sin preguntarle nada a `accounting`. Con el rol como
discriminador, alguien que limpiara un campo del formulario de categorías
empezaría a crear movimientos de stock de un flete.

De paso se cierra una fuga: hasta hoy un artículo sin SKU escribía una
`incidencia_inventario` de tipo `sin_sku` **por ítem y por compra**, así que
cada factura de luz dejaba una falsa alarma que alguien tenía que revisar y
descartar. Un servicio se saltea sin incidencia, y `crear_sku` lo rechaza.

## Lo que NO se hizo

- **El rol `costo_venta`.** Ningún evento asienta todavía contra la 69 (falta
  un evento de consumo **valorizado** por venta, deuda ya anotada), así que
  sería configuración que no hace nada y que nadie podría notar hasta cerrar
  el mes.
- **Reparto de `inventory.consumo_personal_valorizado` y de
  `transferencia_recibida`.** Sus payloads llevan un `monto` agregado y ningún
  detalle; sumárselo es cambiar el publicador dentro de `_mover`, y no es lo
  que el reporte pide. Siguen con el código de fábrica.
- **Override por artículo o por producto.** Ver arriba.
- **`regla_asiento` por categoría.** La regla sigue siendo el override de dos
  líneas de la empresa y sigue ganando entera.
- **Tocar `_EXCEPCIONES_CRUZADAS` de `tests/test_arquitectura.py`.**
  `application.queries_publicas` ya es contrato público para cualquier par de
  módulos; esa lista solo puede encoger.

## Consecuencias

- **Sin migración.** `asiento_contable_config` y `padre_id` ya existían, y
  `articulo.tipo` es un enum extensible.
- **Una empresa que no configura nada se comporta exactamente como antes.**
- Un código mal tecleado no rompe la operación: se rechaza al guardar
  (`inventory.catalogo` consulta el contrato público de `accounting` — la
  cuenta existe en esta empresa, está activa y es de último nivel) y, si
  cambió después, cae al código de fábrica y se registra en el log.
- Recategorizar cambia los asientos futuros, no los pasados.
- `padre_id` sale por fin en `CategoriaOut` y se puede editar por la pantalla:
  `crear_categoria` ya lo aceptaba y **el router no se lo pasaba**, así que la
  jerarquía solo se podía armar tocando la base.
- Aparece un tipo de artículo `servicio` sin SKU ni stock. Un artículo que ya
  tenga SKU no se puede convertir en servicio sin borrar el SKU primero.
