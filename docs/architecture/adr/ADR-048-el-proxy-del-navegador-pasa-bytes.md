# ADR-048 — El proxy del navegador pasa bytes, no texto

- **Estado:** aceptada
- **Fecha:** 2026-08-15
- **Contexto:** frontend (`app/api/proxy/[...ruta]/route.ts`), descargas y subidas
- **Relacionado:** ADR-004 (tenant y autorización en la API), ADR-013
  (arquitectura frontend), ADR-046 (carga masiva de recetas), ADR-047 (suite
  de uso)

## Contexto

El PDV llama a la API desde el navegador, y el token vive en una cookie
**httpOnly** que el JavaScript de la página no puede leer. El puente es una
ruta de Next (`/api/proxy/[...ruta]`) que adjunta el `Authorization` del lado
del servidor y reenvía. Existe desde el primer slice del PDV y hoy lo usan
~40 llamadas: la carta, el cobro, el KDS, los reportes.

Se escribió cuando todo lo que cruzaba era JSON, y quedó escrito **para**
JSON: el cuerpo de ida se leía con `await req.text()` y salía con un
`Content-Type: application/json` fijo; el de vuelta, igual. Mientras los dos
extremos hablaran JSON eso funciona y hasta parece prolijo.

ADR-046 metió por ahí lo primero que no es JSON:
`GET /inventory/recetas/plantilla` devuelve un `.xlsx` y
`POST /inventory/recetas/importar/validar` recibe un `multipart/form-data`.
Las dos direcciones se rompieron, y ninguna con un error:

- **La descarga.** Un `.xlsx` es un ZIP. `respuesta.text()` lo decodifica
  como UTF-8 y reemplaza cada byte inválido por U+FFFD: la corrupción es
  irreversible y ocurre **antes** de que nadie pueda notarla. Encima el
  `Content-Type` fijo y el `Content-Disposition` descartado hacían que el
  navegador guardara **`plantilla.json`**, que es como lo reportó el usuario.
- **La subida.** El `Content-Type` fijo pisa el que manda el navegador, y en
  `multipart/form-data` ese header lleva un `boundary` generado al vuelo. Sin
  boundary, el servidor busca una marca que el cuerpo no tiene. La fase 1 del
  importador nunca funcionó desde la pantalla; no se reportó porque nadie
  llegó a pasar de la descarga.

Nada lo detectó porque **nada probaba el camino real**:
`tests/test_recetas_variantes.py` ataca a FastAPI con `TestClient` y el proxy
queda fuera del recorrido. El backend estaba —y está— bien.

## Decisión

**El proxy es transparente en las dos direcciones. Lo único que agrega es el
`Authorization`.**

- **Ida:** se reenvía el `Content-Type` **entrante** cuando lo hay, y el
  cuerpo sin decodificar (`req.arrayBuffer()`). JSON sigue siendo JSON porque
  el cliente ya lo etiqueta así; `multipart` conserva su `boundary` porque el
  header viaja tal como lo escribió el navegador.
- **Vuelta:** el cuerpo se devuelve como stream (`respuesta.body`), sin pasar
  por texto, con el `Content-Type` y el `Content-Disposition` de la API.

Se conserva lo que ya hacía bien y no es negociable: el token nunca sale del
servidor, el cuerpo de error de la API vuelve **tal cual** (el cajero tiene
que leer "el pago excede el saldo de la cuenta", no un mensaje inventado
acá), y un 204/304 se responde sin cuerpo.

### Las cabeceras de vuelta son una lista blanca

Se copian `content-type` y `content-disposition`: las que le dicen al
navegador qué acaba de recibir y con qué nombre guardarlo. No se copia el
resto, y no por prudencia genérica — hay dos que hacen daño concreto:

- `content-encoding` y `content-length` describen una respuesta que `fetch`
  ya **descomprimió**. Reenviarlos le pide al navegador que gunzipee bytes
  planos, o que espere un largo que no es.
- `set-cookie` de la API terminaría en el navegador. La cookie de sesión la
  pone el login del lado de Next; nada de lo que la API mande tiene por qué
  cruzar.

Una lista negra habría que ampliarla cada vez que aparezca una cabecera
nueva con este problema, y el síntoma de olvidarse es silencioso.

### El cuerpo de ida se junta entero; el de vuelta se transmite

Encadenar `req.body` como stream exige `duplex: "half"`, que no está en el
tipo estándar de `RequestInit` y obliga a un cast. Lo que sube por acá son
formularios y planillas de catálogo —el importador tiene un tope de 5000
filas por hoja (ADR-046)—, no archivos de gigabytes. La vuelta sí va como
stream porque no cuesta nada: `Response` acepta el `ReadableStream` que
devuelve `fetch`.

## Alternativas descartadas

**Rutas dedicadas por descarga y por subida.** Un
`/api/descargas/plantilla-recetas` y un `/api/subidas/recetas` con su propio
manejo binario, dejando el proxy genérico como está para JSON.

Cuesta más y protege menos:

- Es **una ruta nueva por endpoint no-JSON**, escrita a mano, con su copia
  del rescate del token y del reenvío. Hoy serían dos; el PDF de la boleta,
  el XML/CDR de Factiliza, la exportación de reportes a CSV y el PDF de la
  guía de remisión están todos en el ROADMAP, y cada uno sumaría la suya.
- Cada copia es un lugar donde volver a olvidarse del `Content-Disposition`.
  El bug no fue "faltaba una ruta binaria", fue "el proxy reetiqueta lo que
  pasa": repartirlo en cinco rutas multiplica el lugar donde puede repetirse.
- Reintroduce la lista que el proxy evita a propósito. Su comentario de
  cabecera explica por qué no filtra rutas: la autorización real la hace la
  API (ADR-004) y una lista acá sería un segundo lugar donde olvidarse de
  actualizarla. Un juego de rutas dedicadas es exactamente esa lista, con
  otro nombre.
- Y el proxy genérico **seguiría roto** para todo lo que no se migre. Un
  endpoint que empiece a devolver un `Content-Disposition` —una exportación,
  un adjunto— volvería a llegar mal sin que nadie toque el proxy.

Lo único que se pierde al no tomar este camino es la posibilidad de poner
lógica propia por descarga (un nombre de archivo calculado en el cliente,
una cabecera de caché distinta). No hay ningún caso que la pida: el nombre lo
decide el que genera el archivo, que es la API.

**Detectar el tipo y decidir.** "Si `Content-Type` empieza con
`application/json`, texto; si no, bytes." Es la forma de tener dos caminos y
probar solo uno. Además falla en el borde que más importa: un error 500 con
`text/html`, o un JSON con `charset` raro. Pasar bytes siempre es un solo
camino.

## Consecuencias

- `app/api/proxy/[...ruta]/route.ts` deja de decodificar y de reetiquetar.
  Los ~40 llamados JSON existentes no cambian de comportamiento: el cliente
  ya mandaba `Content-Type: application/json` y la API ya lo devuelve.
- `frontend/lib/proxy.test.ts` (corre con `npm test`, milisegundos, sin
  servidores) fija el contrato: descarga byte por byte, `Content-Type` y
  `Content-Disposition` de la API, `boundary` intacto, JSON intacto, error
  literal, 204 sin cuerpo y 401 sin llamar a la API.
- `frontend/uso/importador-recetas.spec.ts` (ADR-047) recorre el camino real:
  descarga la plantilla, verifica la firma `PK\x03\x04`, **la abre con
  openpyxl** —la misma librería del backend—, la llena, la sube, resuelve un
  insumo desconocido en la revisión y confirma. Es el test que hubiera visto
  el bug: contra el proxy viejo falla con
  `Received: "plantilla.json"`, que es literalmente cómo lo reportó el
  usuario.
- El `<a href download>` sin valor de `importar-recetas.tsx` **no se toca**:
  con el `Content-Disposition` pasando derecho, el navegador guarda
  `plantilla-recetas.xlsx`. La prueba de uso lo afirma con
  `download.suggestedFilename()` en vez de darlo por hecho.
- `frontend/uso/planilla.ts` lee y escribe `.xlsx` con openpyxl a través del
  intérprete que ya resuelve `e2e/interprete.mjs`. Se importa con un
  `import()` dinámico porque Playwright compila las specs a CommonJS y un
  `.mjs` requerido desde ahí revienta en `import.meta`.
- Riesgo aceptado: el cuerpo de subida se junta en memoria. Con el tope de
  ADR-046 y lo que hoy se sube, no es un problema; el día que alguien suba
  un adjunto grande, la salida es `req.body` con `duplex: "half"` y este
  párrafo es el punto de partida.
