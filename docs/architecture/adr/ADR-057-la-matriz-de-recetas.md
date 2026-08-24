# ADR-057 — La matriz: el recetario como una hoja de cálculo

- Estado: aceptado
- Fecha: 2026-08-23
- Contexto: `inventory` (recetas)
- Relacionado: ADR-023 (aritmética tecleada), ADR-046 y ADR-052 (carga masiva
  y round-trip `.xlsx`), ADR-056 (líneas condicionadas), RN-COM-024

## Contexto

El editor de a una receta funciona. Lo que no escala es el trabajo real:

- Corregir el queso de las tres presentaciones de ocho pizzas son
  **veinticuatro fichas** abiertas de a una.
- Comparar dos recetas obliga a recordar la primera mientras se mira la
  segunda.
- La planilla resuelve las dos cosas y **no está en el ERP**: hay que
  exportar, abrir Excel, editar, volver a importar y revisar el diálogo de
  dos fases. Para tres gramajes, el ritual cuesta más que el cambio.

La carga masiva (ADR-046/052) existe para traer un recetario de afuera. Esto
es lo otro: el trabajo de todos los días sobre lo que ya está adentro.

## Decisión

### 1. Una grilla: insumos en las filas, recetas en las columnas

`/catalogo/recetas/matriz`, con `GET`/`PUT /inventory/recetas/matriz`.

**Sin librería de grid nueva.** `@tanstack/react-table` ya está en el
proyecto y ni siquiera hace falta acá: la grilla es una `<table>` con un
`<input>` por celda. Una dependencia de spreadsheet traería selección de
rangos, congelado de paneles y menús contextuales que nadie pidió.

Solo entran los insumos que **alguna** de esas recetas usa. Una grilla con
las cuatrocientas filas del catálogo es una grilla vacía.

### 2. La identidad de una celda es `(receta, insumo, condición)`

No un id de línea. Es lo que permite **pegar un rectángulo desde Excel**, que
no trae ids: el servidor resuelve solo si esa celda es un alta, una edición o
un borrado.

La condición entra en la clave porque desde ADR-056 el mismo insumo puede
estar dos veces en la misma receta si cada línea aplica a otra combinación.

### 3. Vaciar la celda borra la línea

En una grilla, vaciar la celda **es** la forma de decir "este insumo no va en
esta receta". Pedir un botón aparte sería inventar un gesto que nadie busca.

Vaciar una celda que ya estaba vacía no es un error: pegar un rectángulo con
huecos no puede reportar cuarenta problemas.

### 4. Se guarda por lote, y una celda mala no arrastra a las demás

El lienzo guarda en cada `onBlur` — una ida a la red por campo. En una grilla
eso sería una por tabulación. Acá se edita todo y se manda **solo lo que
cambió**: mandar la grilla entera reescribiría líneas que nadie tocó, con su
`updated_at` y su rastro de auditoría, y con dos personas en la pantalla la
última en guardar pisaría el trabajo de la otra aunque hubieran tocado celdas
distintas.

Cada celda entra en su propio `SAVEPOINT`, igual que cada receta en la carga
masiva (ADR-046). Pegar cuarenta celdas y perderlas todas porque una tenía un
insumo mal escrito es el modo de falla que hace que nadie vuelva a pegar nada.
La respuesta dice qué pasó con cada una en vez de cortar con un 409.

### 5. La celda muestra lo tecleado, no el resultado

Quien escribió `450/3` vuelve a ver la división. El número lo calcula el
servidor (RN-COM-024) y la vista previa aparece debajo mientras se escribe,
con los decimales de la unidad de esa línea.

**Después de guardar se relee del servidor** en vez de marcar las celdas como
limpias: el redondeo por UdM se decide allá, y una grilla que muestra lo que
el navegador creyó guardar es la que después no cuadra con la ficha.

### 6. Copiar también, no solo pegar

`copiar` vuelca la grilla en el mismo formato TSV que Excel entiende, y
`leerPegado` lo lee de vuelta. El round-trip está probado. Sin copiar, la
pantalla obliga a exportar el `.xlsx` para llevarse un rectángulo a otra
herramienta.

## Alternativas descartadas

- **Una librería de spreadsheet** (Handsontable, ag-Grid, Glide). Traen
  selección de rangos, fórmulas y menús que este caso no usa, y la mitad
  tienen licencia comercial para uso interno. La grilla real son cuarenta
  filas por veinte columnas.
- **Guardar en cada `onBlur`**, como el lienzo. Es lo que hace lento al
  lienzo, y en una grilla se multiplica por el número de celdas.
- **Mandar la grilla entera al guardar.** Más simple de escribir y reescribe
  lo que nadie tocó; ver §4.
- **Un id de celda en el payload.** Imposible de producir al pegar desde
  Excel, que es el gesto entero de esta pantalla.
- **Crecer la grilla al pegar** más filas de las que hay. Pegar cinco filas
  cuando quedan tres es un accidente común; inventar recetas sería peor que
  descartar.
- **Poner esto en la carga masiva.** Es el mismo dato por otro camino, sí,
  pero el ritual de exportar/importar cuesta más que el cambio cuando son
  tres gramajes. Las dos cosas conviven y no se pisan: la planilla trae
  recetario de afuera, la matriz corrige el de adentro.

## Consecuencias

- Endpoints nuevos `GET` y `PUT /inventory/recetas/matriz`. La ruta va
  declarada **antes** de `/recetas/{receta_id}`: FastAPI resuelve por orden y
  "matriz" entraría como un `receta_id` que no es UUID (mismo cuidado que
  `/recetas/plantilla`).
- `recetas.editar_item` acepta `unidad_medida_id`, y redondea con los
  decimales de **la unidad de la línea** y no con los del artículo: quien
  teclea gramos espera que 24.4 sea 24.
- Tope de 2000 celdas por guardado. Un rectángulo real no llega ni cerca; el
  límite está para que pegar una hoja entera por accidente no sea una
  transacción de diez minutos.
- `frontend/lib/matriz.ts` es puro y tiene 15 pruebas: el pegado y el diff se
  prueban sin montar un navegador.
- Queda pendiente: editar la **condición** de una celda desde la matriz.
  Desde el lienzo ya se edita (enmienda de ADR-056, 2026-08-24), que es donde
  los valores tienen nombre; en la grilla no, y hay un segundo problema
  debajo — la celda se busca sin la condición en la clave, así que una línea
  condicionada cae donde la grilla nunca mira. Anotado en Deuda técnica.
