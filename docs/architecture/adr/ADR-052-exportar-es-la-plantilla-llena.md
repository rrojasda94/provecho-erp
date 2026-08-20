# ADR-052 — Exportar es la plantilla llena, y la columna `ID` es la identidad

- **Estado:** aceptada
- **Fecha:** 2026-08-20
- **Contexto:** `inventory` (recetas, artículos), `sales` (clientes)
- **Relacionado:** ADR-046 (carga masiva de recetas), ADR-048 (el proxy pasa
  bytes), RN-COM-031, RN-INV-025, RN-PTS-007

## Contexto

ADR-046 dejó el recetario cargándose de golpe desde un `.xlsx`, en dos fases
con revisión en el medio. Quedaron tres huecos que se ven recién cuando alguien
usa el ERP con datos reales:

1. **El catálogo de artículos y el padrón de clientes se siguen tecleando de a
   uno.** Peor: cuando el importador de recetas encuentra un insumo que no
   existe, la única salida es ir a `/inventario/articulos`, crearlo a mano y
   volver a subir el archivo — porque no hay carga masiva de artículos.
2. **La plantilla baja vacía.** Sirve para la primera carga y para nada más.
   Corregir el rendimiento de treinta recetas ya cargadas exige abrir treinta
   fichas.
3. **Una receta que ya existe se omite** (`docs/roadmap/deuda/modulo-inventory.md:343`).
   La deuda quedó abierta a propósito: actualizar exige decidir qué pasa con
   los ingredientes que el archivo no menciona, y eso es decisión de negocio.

## Decisión

### Exportar es la plantilla con los datos adentro

`GET …/exportar` devuelve el mismo libro que `…/plantilla`, con las filas
llenas. Mismo formato, mismas hojas, mismas columnas: lo que baja se puede
editar y volver a subir sin traducir nada.

No son dos formatos porque no son dos cosas. La plantilla vacía sigue
existiendo para el caso en que todavía no hay nada que exportar — que es el
mismo argumento por el que ADR-046 le puso filas de ejemplo: sobre un catálogo
vacío, un archivo sin una sola fila obliga a adivinar si "Cantidad" son gramos
o kilos.

### La columna `ID`, y la regla que la explica

Cada libro abre con una columna `ID` que el export llena con el UUID y la
plantilla deja vacía. **Celda vacía = alta. Celda llena = actualización.**

La regla general de la que sale:

> **La clave de actualización tiene que ser un campo que la persona no está
> editando.**

De ahí, por entidad:

- **Recetas: solo por `ID`.** Su única clave natural es el nombre, y el nombre
  es justamente lo que alguien puede querer cambiar. Sin `ID`, renombrar y
  duplicar son indistinguibles. Consecuencia asumida: para actualizar recetas
  hay que partir de un export; una planilla tecleada a mano solo da de alta.
- **Artículos: por `ID`, o por `Código` (`id_interno`) si `ID` viene vacío.**
  El código es corto, estable, único y la gente ya lo usa.
- **Clientes: por `ID`, o por `Número de documento`.** Mismo criterio.

Un `ID` repetido dentro del mismo archivo marca las dos filas como problema:
copiar-pegar una fila es el accidente esperable, y silenciarlo escribiría dos
veces sobre el mismo registro.

### Qué se borra al actualizar lo decide una persona, receta por receta

Ésta es la decisión de negocio que `modulo-inventory.md:343` dejó abierta.

Cada receta de la revisión lleva `ingredientes_ausentes`, con dos valores:
`conservar` (por defecto) y `quitar`. La pantalla muestra el diff antes de
confirmar — qué se agrega, qué cambia y **cuántas líneas se quitarían** — y la
elección se hace por receta, no para todo el archivo.

El defecto es `conservar` porque el modo de falla asimétrico está claro: subir
una hoja parcial por error no puede vaciar una receta. Quien quiera el
comportamiento "el archivo *es* la receta" lo pide, viendo primero el número de
líneas que va a perder.

`ingredientes_ausentes` y `accion` viajan en el JSON de la fase 2, así que son
lo mismo que todo lo demás que vuelve de la pantalla: **el permiso que una
persona dio, no un hecho.** El servidor revalida antes de escribir, igual que
en ADR-046.

### La E/S de `.xlsx` va a `src/shared/planilla.py`; la lógica no

Tres entidades × (exportar + validar + importar) es donde nace el motor
genérico con descriptores de columnas y resolvers enchufables. No se construye.

Lo que de verdad se repite no tiene negocio adentro: abrir el libro y dar un
error legible si no es un `.xlsx`, mapear la cabecera, descartar filas vacías,
el tope de filas, celda → texto/decimal/booleano/fecha/uuid, y escribir bytes.
Son ~90 líneas y ya estaban escritas una vez.

Lo que no se repite no es duplicación, son tres significados distintos: qué
hojas, qué columnas, qué referencia hay que resolver, qué cuenta como "ya
existe" y qué puede cambiar una actualización. Un DSL que exprese las tres cosas
se lee peor que tres archivos planos, y cada regla nueva habría que poder
expresarla en el DSL antes de poder escribirla.

La regla de módulos ya hacía imposible el motor cruzado: `sales` no puede
importar de `inventory` (`tests/test_arquitectura.py`). `src/shared/` es el
único domicilio legal, y `test_shared_no_depende_de_ningun_modulo` garantiza
que solo pueda contener lo que no sabe de dominio — que es exactamente el corte
propuesto. La restricción arquitectónica y el corte correcto coinciden.

`planilla.py` **no importa FastAPI**: devuelve `bytes` y expone el MIME como una
cadena. El `Response` lo arma el router, que es quien sabe que existe HTTP.

### Se lee por nombre de cabecera, no por índice de columna

El parser de ADR-046 leía `_texto(fila, 0)`. Agregar `ID` a la izquierda habría
roto en silencio cualquier archivo ya llenado.

`cabecera()` normaliza (minúsculas, sin tildes) y `celda()` lee por nombre.
Efectos: agregar una columna no rompe los archivos viejos, reordenar columnas en
Excel no rompe nada, y una columna faltante da un error que **la nombra** en vez
de leer mal sin avisar.

### Las referencias que faltan las resuelve una persona, en pantalla

Unidad de medida, categoría e insumo desconocidos se resuelven en el diálogo:
elegir uno existente, **crearlo ahí mismo**, u omitir esa línea.

**Esto no revierte la alternativa que ADR-046 descartó.** Lo descartado era que
el *importador* creara solo los insumos que faltan: un "Queso mozarela" mal
tecleado se convertiría en un artículo duplicado que después hay que fusionar a
mano. Que una persona lo cree desde el diálogo, viendo el nombre que trajo el
archivo, es lo contrario de autocrear — es exactamente la revisión humana que
ADR-046 pedía, y que hasta hoy estaba a medio entregar.

## Alternativas descartadas

**Un motor de importación genérico.** Ver arriba: la duplicación real son 90
líneas sin negocio; lo demás son tres dominios distintos disfrazados de tres
tablas iguales.

**Exportar a CSV.** Mismo argumento que ADR-046 para la entrada: Excel en
configuración regional peruana separa con `;` y usa coma decimal, así que abrir
y volver a guardar corrompe los decimales **en silencio**. Un export que no se
puede reimportar sin romperse no es un round-trip.

**Que el archivo sea siempre autoritativo sobre la receta que nombra** (las
líneas ausentes se borran, sin preguntar). Es el modelo mental de una planilla y
es más predecible, pero convierte "subí el archivo equivocado" en pérdida de
datos sin acto explícito. Se ofrece como opción por receta, no como defecto.

**Actualizar por nombre.** Ver la regla: el nombre es lo que se edita.

**Que el importador de clientes consulte a Factiliza por fila**, como hace
`crear_cliente` de a uno. Una planilla de 300 clientes serían 300 llamadas
externas secuenciales dentro de un solo request, contra una cuota. La razón
social del archivo se toma tal cual; SUNAT manda cuando el cliente se edita de a
uno.

## Consecuencias

- `src/shared/planilla.py` es nuevo y lo usan `inventory` y `sales` sin
  conocerse entre sí.
- `plantilla()` de recetas pasa a ser `exportar()` con cero filas de datos: un
  solo generador de libro para los dos casos.
- La hoja `Ingredientes` **no lleva `ID`**: la identidad de una línea es
  `(receta, insumo)` y el dominio ya la hace única. Una columna con
  `receta_item.id` sería una segunda verdad que no sobrevive un copiar-pegar.
- `Cantidad` se exporta como `expresion or cantidad`: exportar `150` donde
  alguien escribió `450/3` perdería justo lo que RN-COM-024 existe para
  conservar.
- La `Unidad` de un artículo existente no se cambia por planilla —
  `catalogo.editar_articulo` la excluye a propósito—. Una fila cuya unidad
  difiera de la guardada **se reporta como problema visible**; ignorarla en
  silencio es el modo de falla que ADR-046 existe para evitar.
- Un cliente natural no se actualiza desde la planilla: nombre, teléfono y
  domicilio viven en `Persona` (RN-GEN-007) y `sales` no puede escribirla. Se
  reporta "se corrige en Personas", con enlace.
- Permiso nuevo `sales.gestionar_clientes`: hoy el único permiso de escritura
  sobre clientes es `sales.crear` ("Crear venta"), que lo tiene el cajero.
  Reescribir el padrón del grupo desde una planilla no es el mismo acto que
  registrar a alguien en el mostrador.
- Exportar exige permiso de **lectura**: devuelve los mismos datos que el
  listado, solo empaquetados.
- El export se baja con un `<a download>` contra el proxy del navegador, que ya
  pasa bytes y conserva `Content-Type` y `Content-Disposition` (ADR-048).
- Las respuestas de la fase de validación pasan a tener `response_model`: hasta
  ahora `validar_importacion_recetas` devolvía un dict crudo y `openapi.json` lo
  documentaba como `{}`, así que los tipos del frontend no los verificaba nadie.
