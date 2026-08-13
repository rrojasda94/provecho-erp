# ADR-046 — Carga masiva de recetas: dos fases, sin tabla de staging

- **Estado:** aceptada
- **Fecha:** 2026-08-13
- **Contexto:** `inventory` (recetas)
- **Relacionado:** RN-COM-031, RN-COM-024 (aritmética tecleada), ADR-023

## Contexto

Un recetario de restaurante no se teclea plato por plato: ya existe en una
hoja de cálculo, con decenas de recetas y cientos de líneas. Cargarlo a mano
por la pantalla de a una es el trabajo que hace que el ERP no se adopte.

No había nada previo en el repo: ni dependencia para leer Excel, ni
`UploadFile`, ni `<input type="file">`, ni descarga de plantilla.

## Decisión

### `.xlsx`, no CSV

Excel en configuración regional peruana separa con `;` y usa coma decimal.
Abrir un CSV y volver a guardarlo convierte `0.5` en `0,5`, y el archivo se
corrompe **en silencio** — el peor modo de falla para una carga que el
usuario cree que salió bien. `openpyxl` lee el formato nativo y el problema
no existe.

### Dos fases con revisión en el medio

1. `POST /recetas/importar/validar` (multipart) → parsea y devuelve qué
   entra, qué no y por qué. **No guarda nada.**
2. La pantalla resuelve los insumos que el catálogo no reconoció —eligiendo
   uno existente, creándolo, u omitiendo esas filas—.
3. `POST /recetas/importar` con el JSON ya resuelto → **revalida todo** y
   commitea.

**Sin tabla de staging.** La alternativa era persistir el archivo parseado
con su propio ciclo de vida, su estado y su limpieza de importaciones
abandonadas. Con dos llamadas sin estado, una importación que alguien deja a
medias no deja nada que barrer.

**El servidor revalida en la segunda fase.** Lo que vuelve es un JSON que el
cliente pudo editar; confiar en que sigue siendo el archivo validado sería
dejar que un POST cree recetas con insumos de otra empresa.

### Se reusan `crear_receta` y `agregar_item`

El importador no inserta directo. Esas funciones son las que saben del
nombre único por empresa, de la unidad, de la merma y de la aritmética
tecleada (RN-COM-024) — un importador con su propia lógica sería un segundo
juego de reglas que se separa del primero a la primera corrección.

Efecto práctico: la cantidad acepta `450/3` en la hoja igual que en la
pantalla, y se redondea con los decimales de la unidad **del insumo**.

### Una receta que falla no arrastra a las demás

Cada receta entra en su propio `SAVEPOINT` (`session.begin_nested()`). Un
nombre repetido a mitad del archivo informa esa fila y sigue; sin savepoint,
o se cae la importación entera o la receta queda a medias —creada sin sus
ingredientes—, que es peor porque nadie lo nota.

## Alternativas descartadas

**Una sola fase que importa lo que puede.** Es lo que hace la mayoría de los
importadores, y es exactamente el modo de falla que hay que evitar: se
cargan 40 de 50 recetas, el mensaje dice "importación completada" y las 10
que faltan aparecen semanas después como platos que no se pueden vender.

**Tabla de staging.** Ver arriba: estado que hay que mantener y limpiar para
un flujo que dura dos minutos.

**Que el importador cree los insumos que faltan.** Un nombre mal escrito
—"Queso mozarela"— crearía un artículo duplicado que después hay que
fusionar a mano. Que lo decida una persona es la diferencia entre un error
de tipeo y un catálogo sucio.

## Consecuencias

- Dependencias nuevas: `openpyxl` y `python-multipart` (FastAPI lo necesita
  para `UploadFile`).
- `GET /inventory/recetas/plantilla` va declarada **antes** de
  `/recetas/{receta_id}`: FastAPI resuelve por orden y "plantilla" entraría
  como un `receta_id` que no es UUID.
- La plantilla lleva filas de ejemplo y una hoja de instrucciones. Una
  plantilla vacía obliga a adivinar si "Cantidad" son gramos o kilos.
- `contrato.test.ts` no sabía leer un cuerpo `multipart`: hacía
  `JSON.parse` de cualquier body y reventaba con «Unexpected token 'o'».
  Ahora lo distingue, lo cual habilita cualquier subida futura.
- Tope de 5000 filas por hoja: un recetario real no llega ni cerca, y el
  límite evita que un archivo corrupto tumbe el proceso.
