# ADR-108 — Kardex gráfico en la ficha del artículo y próxima compra sugerida

Fecha: 2026-09-23
Estado: aceptada

## Contexto

Para decidir cuándo y a cuánto volver a comprar, quien compra necesitaba
ver tres cosas juntas: cómo se movió el precio, a qué ritmo entra y sale el
artículo, y cuándo se va a quedar corto. El kardex existente
(`GET /inventory/movimientos`) lista movimiento por movimiento y no tiene
costo; el precio histórico vive en las recepciones de `purchases`, y no había
endpoint que lo leyera. La ficha del artículo en Inventario era una tabla de
seis datos y en Compras no existía.

## Decisión

1. **Dos endpoints, uno por módulo dueño del dato**, compuestos en el
   frontend. Los módulos no se importan entre sí:
   - `GET /inventory/articulos/{id}/kardex?dias=180` — entradas y salidas por
     semana, saldo al cierre de cada semana (reconstruido hacia atrás desde el
     stock actual), stock y mínimo de toda la empresa, consumo diario y
     próxima compra sugerida. Los traslados internos no cuentan: en el total
     de la empresa se anulan.
   - `GET /purchases/articulos/{id}/historial-precios` — cada recepción con
     fecha, costo unitario, cantidad y proveedor. Del costo de la recepción, no
     de la OC: es lo que se pagó. Incluye compras directas (ADR-082).
2. **La predicción es lineal y vive en el dominio de inventario**
   (`rules.consumo_diario`, `rules.proxima_compra`, RN-INV-027): promedio de
   salidas de 90 días, mínimo 7 días de historia; fecha en que el stock toca
   el mínimo. La **frecuencia de compra** (promedio de días entre recepciones)
   la calcula la pantalla sobre el historial de precios, que es de compras.
3. **Una sola ficha** (`components/kardex/ficha-kardex.tsx`) en
   `/inventario/articulos/[id]` y `/compras/articulos/[id]`. A la primera se
   llega desde el nombre en la lista de artículos; a la segunda, desde cada
   línea de una OC. Sin `purchases.leer`, la ficha se dibuja sin el gráfico
   de precio.
4. **Tres gráficos y no uno con doble eje**: precio (soles), entradas/salidas
   (barras, misma unidad) y saldo con la línea de mínimo. Colores validados
   para daltonismo en claro y oscuro (`--kardex-entrada` + `--primary`), con
   leyenda y una vista de tabla.

## Alternativas descartadas

- **Guardar el costo en `movimiento_inventario`**: habría dado precio y
  cantidades en una consulta, pero es una migración sobre la tabla más grande
  del ERP para duplicar un dato que ya está en la recepción.
- **Modelo con estacionalidad o tendencia**: sin un año de historia real no
  hay con qué calibrarlo. Queda marcado (`ponytail:`) en `rules.proxima_compra`.

## Consecuencias

- La sugerencia no descuenta el plazo del proveedor: no existe ese dato por
  proveedor todavía (deuda en `docs/roadmap/deuda/modulo-inventory.md`).
- Las semanas previas al primer movimiento del período se recortan: un
  artículo nuevo se grafica desde que empezó a moverse.

## Enmienda 2026-09-23 — por almacén, por sede y como un todo

El kardex de la empresa entera no decía cómo estaba cada local. Se agrega el
**ámbito**:

- `GET /inventory/articulos/{id}/kardex` acepta `almacen_id` **o**
  `sucursal_id` (los dos juntos: 422). En la empresa los traslados internos
  se siguen excluyendo; en una sede o un almacén **cuentan**: lo que llega del
  central es su reposición y lo que manda, una salida. Con ámbito, la próxima
  compra se lee como **próxima reposición**.
- Una sede se valida contra la empresa del usuario, no contra sus sucursales
  asignadas: comparar sedes es mirar las demás
  (`exigir_sucursal_de_la_empresa`).
- `GET /inventory/articulos/{id}/kardex/por-almacen`: una fila por almacén que
  maneja el artículo con stock, mínimo, consumo diario, próxima reposición y
  reposiciones en 90 días, lo que se agota primero arriba. En la ficha es la
  tabla **«Cómo está cada sede»**, en rojo lo que está bajo el mínimo y en
  ámbar lo que se repone en una semana o menos.
- El precio sigue siendo de la empresa: un local abastecido por el central
  no compra. `historial-precios?almacen_id=` filtra las compras que entraron
  directo a un almacén, para la sede que sí compra por su cuenta.
- El ámbito vive en la URL (`?ambito=almacen:<id>` / `sucursal:<id>`), así que
  el enlace se comparte con quien maneja ese local.

