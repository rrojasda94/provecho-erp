# ADR-091 — El catálogo se corrige por pantalla

- Estado: aceptado
- Fecha: 2026-09-06
- Contexto: `src/modules/inventory/application/catalogo.py`,
  `src/modules/inventory/api/{routers,schemas}.py`,
  `src/modules/inventory/infrastructure/models/articulo.py`,
  `src/modules/sales/infrastructure/models/producto_comercial.py`,
  migración `fab77826b2c9`
- Relacionado: ADR-046 (carga masiva en dos fases), ADR-052 (exportar es la
  plantilla llena), RN-GEN-005

## Contexto

Dos correcciones de catálogo que solo se podían hacer por SQL:

1. **Un SKU no se editaba.** `application/catalogo.py` tenía `crear_sku` y
   nada más. Un código de barras mal tecleado no tenía corrección posible
   desde el ERP; el importador (`importacion_articulos.py`) lo informaba
   como omitido y no lo tocaba, que es el modo de falla correcto para una
   planilla —tocarlo a medias sería peor que informarlo— pero no resolvía
   el caso de la pantalla de a uno.
2. **`id_interno` eran 4 caracteres compartidos por TODO el grupo.**
   `articulo.id_interno` y `producto_comercial.id_interno` son
   `UniqueConstraint` sin `empresa_id` a propósito (RN-COM-031, ADR-063):
   dos empresas del grupo no pueden compartir código porque hoy el
   catálogo del grupo se lee como uno solo. El problema no era la ausencia
   de `empresa_id` — era el largo: 4 caracteres alfanuméricos son ~1.6M
   combinaciones en teoría, pero el que se teclea a mano y se lee en el
   estante convive mal con más de un puñado de miles antes de sentirse
   agotado.

## Decisión

**`editar_sku` existe, con las mismas reglas de unicidad que `crear_sku`.**
`PATCH /inventory/skus/{id}` acepta `codigo`, `codigo_barras` y `activo`;
`articulo_id` no está —un SKU no cambia de artículo, eso es dar de alta uno
nuevo y archivar el viejo, mismo criterio que `unidad_medida_id` en
`ArticuloUpdate`—. El importador **no cambia**: sigue informando un código
repetido como omitido y no lo actualiza solo. Corregirlo sigue siendo la
pantalla de a uno, a propósito: una planilla que actualiza en silencio el
código de barras de un SKU que ya existe es el mismo riesgo que ADR-046 ya
evitó una vez con el nombre y la unidad de un artículo.

**`id_interno` pasa de 4 a 8 caracteres, y sigue único en todo el grupo, no
por empresa.** Se evaluaron las tres salidas y se descartaron dos:

- *Único por empresa* resolvía el agotamiento pero cambia lo que
  `id_interno` significa hoy —un identificador que cualquiera en el grupo
  puede escribir en una orden de compra o un traslado sin ambigüedad— y
  hoy opera una sola empresa: el problema que resolvería no existe
  todavía.
- *Único por empresa + 6 caracteres* es la migración más cara de las tres
  y la única que además cambia el significado del campo. Se paga doble por
  un problema que hoy es solo de espacio.
- **Ensanchar y seguir global** resuelve exactamente el problema medido
  —el espacio se agota, no que dos empresas necesiten el mismo código— sin
  tocar lo que la gente ya tiene memorizado: todo código de 4 caracteres
  existente sigue siendo válido, la migración es un `ALTER COLUMN` sin
  relleno de datos.

Aplica a los dos modelos que comparten el problema:
`inventory.articulo.id_interno` (validado también en el importador,
`LARGO_CODIGO`) y `sales.producto_comercial.id_interno` (el generador de
variantes, `variantes.py::_codigo_libre`, sigue produciendo códigos de 4
caracteres —1 letra + 3 dígitos base 36— porque ahí el espacio no está
agotado; ensanchar la columna no obliga a ensanchar lo que se genera).

RN-GEN-005 decía además que `id_interno` era **inmutable**, lo cual ya era
falso antes de este ADR: `editar_articulo` acepta `id_interno` desde
ADR-052 (2026-08-20). Se corrige la regla para que diga lo que el código
ya hace.

## Consecuencias

- Los códigos ya asignados de 4 caracteres no cambian; el ensanche es
  puramente aditivo.
- `test_importacion_articulos.py::test_un_codigo_mas_largo_que_la_columna_se_reporta_por_fila`
  se actualiza al nuevo largo — sigue probando lo mismo (SQLite no aplica
  el largo de un VARCHAR, Postgres sí).
- Si el grupo alguna vez abre una segunda empresa con catálogo propio y el
  código compartido se vuelve un problema real —no solo teórico—, la
  salida es *único por empresa*, no un tercer ensanche.
