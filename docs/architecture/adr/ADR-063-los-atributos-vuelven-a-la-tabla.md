# ADR-063 — Los atributos vuelven a la tabla

- Estado: aceptado
- Fecha: 2026-08-24
- Contexto: `sales` (catálogo comercial), frontend
- Relacionado: ADR-035 (lienzo de nodos), ADR-055 (atributos y variantes),
  ADR-056 (recetas condicionadas), ADR-057 (la matriz), ADR-058 (el lienzo
  sobre el modelo de atributos, superado por este), RN-COM-036/037/038

## Contexto

El modelo de atributos de Odoo entró completo en ADR-055 y ADR-056: existen
`atributo`, `atributo_valor`, `producto_atributo_linea`,
`producto_atributo_valor` (PTAV), `producto_variante_valor`,
`producto_exclusion`, y `receta_item.aplica_valores` ya condiciona una línea
a uno o varios valores. La API entera existe desde ese momento.

La única pantalla que la usaba era el lienzo (ADR-058), y el usuario reportó
lo mismo que ya se había reportado tres veces sobre el modelo anterior
(ADR-035 §5, ADR-038, ADR-042): *"no puedo ver ni crear los atributos"*. Los
siete métodos de `catalogoApi` para atributos no los llamaba ninguna
pantalla — solo `contrato.test.ts` los ejercitaba.

ADR-058 había descartado explícitamente una pantalla aparte: *"lo mismo en
dos pantallas hace pensar que son dos cosas distintas. El lienzo es el lugar
de trabajo del catálogo."* Esa objeción vale mientras las dos pantallas
compiten. Al borrar el lienzo entero deja de haber dos pantallas — vuelve a
haber una, y es otra.

Faltaba además la única pieza que ADR-055 §3 había dejado sin construir: el
generador que materializa las combinaciones de un atributo en modo `siempre`.

## Decisión

### 1. El lienzo se borra entero, no se retira gradualmente

`frontend/app/(lienzo)/` (9 archivos, 2.995 líneas), `frontend/lib/lienzo.ts`
(833), `frontend/lib/nodos.ts` (253), sus tres suites de test, y
`@xyflow/react` de `package.json`. No queda como vista de solo lectura: una
pantalla que ya no se puede editar pero sigue linkeada es la que alguien abre
por costumbre y reporta como rota.

Se borra **después** de que las pantallas nuevas cubren lo mismo, en el mismo
cambio — no en dos PRs separados, porque un estado intermedio sin ninguna de
las dos formas de editar atributos es peor que cualquiera de las dos.

### 2. Dos pantallas, estilo Odoo 18: catálogo global + oferta por producto

`/catalogo/atributos` — tabla de atributos (nombre, modo de variante, cómo se
muestra, orden) con sus valores expandibles. Es donde se declara el
vocabulario una vez: "Tamaño" con Personal/Mediana/Familiar lo declara quien
arma el primer producto y lo reusan los siguientes cuarenta.

Sección «Atributos» en la ficha del producto — qué atributos ofrece **este**
producto, con qué valores y qué sobreprecio (PTAV), sus exclusiones
declaradas, y el botón que genera variantes. La separación es la misma que ya
regía en la API desde ADR-055: el atributo es del catálogo, la oferta es del
producto.

### 3. El generador de variantes, acotado a `modo_variante = 'siempre'`

`POST /sales/productos/{id}/variantes` (`src/modules/sales/application/
variantes.py`). Toma los atributos `siempre` del producto, arma el producto
cartesiano de sus valores activos, descarta lo que `producto_exclusion`
prohíbe (RN-COM-038) y lo que ya existe, y crea una fila hija por
combinación nueva.

**Es idempotente**: correrlo dos veces crea cero la segunda. Nunca borra ni
desactiva una variante existente — bajar un atributo de `siempre` a `nunca`
deja de generar, no deshace lo generado (mismo criterio que
`editar_atributo` ya prometía desde ADR-055).

`modo_variante = 'dinamica'` (materializar en la primera venta) queda **fuera
de este cambio** a propósito: tocar el camino de la venta es exactamente el
riesgo que había que evitar para poder decir "esto no afecta al PDV". Queda
en deuda técnica.

**`id_interno` es `String(4)` único en todo el grupo**, no por empresa. El
generador acuña códigos con el mismo formato que
`scripts/odoo/convertir_catalogo.py::codigo()` — una letra de familia y tres
dígitos en base 36 — pero consciente de colisiones: carga los códigos
existentes y toma el primero libre, en vez de asumir un índice determinista
como hace el importador de una sola pasada.

Una variante nace **sin receta** — no hay ninguna de dónde copiarla, el padre
no puede tener una propia (RN-COM-022) — y se reporta si quedó **sin precio**
en ninguna lista: `GET /carta` descarta en silencio lo que no sabe cobrar, así
que sin ese aviso alguien genera una docena de combinaciones y no ve ninguna
en el PDV sin saber por qué.

### 4. La condición de una línea de receta se edita en el editor de receta

Columna «Condición» en `components/catalogo/receta-editor.tsx`, con
casillas agrupadas por atributo dentro de un `<details>` — mismo criterio que
ADR-057 §1: HTML plano en vez de una librería nueva para un selector
múltiple. El editor pide `GET /sales/recetas/{id}/atributos` una vez al
montar; lista vacía = ningún producto usa esta receta, y la columna no se
dibuja — más honesto que ofrecer una condición sin nombres, que es
exactamente el hueco que ADR-058 había dejado anotado.

Ese endpoint resuelve el camino inverso receta → producto → atributos, con
herencia del padre (ADR-042), y vive en `sales` porque
`producto_comercial.receta_id` es una columna de `sales`.

**Se corrige de paso un bug que existía antes del lienzo y sobrevivía en el
editor de receta**: el filtro de insumos ya usados comparaba solo por
`articulo_id`, así que era imposible poner el mismo insumo en dos líneas con
condición distinta — exactamente el caso de la pizza mitad-y-mitad, el motivo
por el que existe ADR-056. Ahora filtra por `(insumo, condición)`, la misma
identidad que usa el 409 del servidor y la celda de la matriz.

### 5. `producto_comercial.lienzo_pos` se borra, con migración

Columna cosmética que nada más lee. Migración `ce32c6610eb7`, encadenada
detrás de `b6d29f10c47e`. `downgrade` la reagrega nullable — se pierden las
posiciones guardadas, aceptable porque son puramente visuales.

**Rompe la promesa de ADR-055 §6** de que la imagen anterior corre contra
este esquema sin enterarse: volver a una versión que todavía dibuja el
lienzo exige `alembic downgrade` explícito, ya no basta con
`./scripts/desplegar.sh 0.6.0`.

### 6. Se borra el interruptor que nunca se implementó

ADR-055 §6 documentó `parametro_empresa` → `sales` / `catalogo.modelo_odoo`
como el interruptor entre el modelo viejo y el nuevo, con default `False`.
**Nunca se leyó en ningún lugar del código** — grep confirma cero lecturas de
`parametro_empresa` en `src/modules/sales/`, solo tres comentarios que lo
mencionaban. Se borra la afirmación de ADR-055, del README de `sales` y de
los dos docstrings que la repetían, en vez de construir un interruptor que
nadie pidió ni usó.

## Alternativas descartadas

- **Dejar el lienzo como vista de solo lectura.** Una pantalla que muestra
  pero no deja actuar es la que alguien abre por costumbre y reporta como
  rota — y mantener su código vivo solo para leer es el mismo costo de
  mantenimiento con la mitad del valor.
- **Borrar el lienzo primero, construir las tablas después.** Deja al ERP sin
  ninguna forma de editar atributos durante el intervalo — peor que
  cualquiera de las dos pantallas.
- **Materializar también el modo `dinamica` en este cambio.** Exige tocar
  `ventas._resolver_valores_variante`, que es precisamente el camino que
  había que dejar intacto para poder decir "esto no afecta al PDV".
- **Arreglar la matriz para que muestre las líneas condicionadas.** Sigue sin
  entrar: la matriz busca la celda sin la condición en la clave (ADR-057), y
  arreglarlo es un cambio de otra forma, no de esta.

## Consecuencias

- Nueva migración `ce32c6610eb7`: borra `producto_comercial.lienzo_pos`.
- Nuevos endpoints en `sales`: `PATCH /atributos/{a}/valores/{v}`,
  `DELETE /atributos/{a}`, `DELETE /productos/{p}/atributos/{a}`,
  `POST /productos/{p}/variantes`, `GET /recetas/{r}/atributos`.
- `PATCH /atributos/valores/{ptav_id}` gana `activo` opcional: es lo que
  permite reofrecer un valor retirado por error, que antes era de ida.
- `src/modules/sales/application/variantes.py` (nuevo): el generador.
- RN-COM-039 (nueva, `docs/domain/business-rules.md`): qué materializa el
  generador, qué exclusiones respeta, por qué es idempotente.
- Frontend: `/catalogo/atributos` (nueva ruta), sección «Atributos» +
  «Combinaciones que no existen» en la ficha del producto, columna
  «Condición» en el editor de receta. `frontend/lib/navegacion.ts` gana la
  entrada, que alimenta sola a la paleta de comandos.
- Deuda técnica: `modo_variante = 'dinamica'`, la matriz sin líneas
  condicionadas, crear un atributo nuevo desde dentro de la ficha del
  producto (hoy hay que ir a Catálogo → Atributos primero).
