- **La plantilla de recetas se descargaba como un `.json` corrupto**
  (2026-08-15, ADR-048). El backend siempre armó un `.xlsx` de verdad; quien
  lo rompía era el proxy del navegador (`app/api/proxy/[...ruta]/route.ts`),
  que leía todo cuerpo con `text()` —un `.xlsx` es un ZIP y no sobrevive una
  decodificación UTF-8— y lo devolvía con `Content-Type: application/json`
  fijo, descartando el `Content-Disposition`. Sin nombre y con ese tipo, el
  navegador guardaba `plantilla.json`. Ahora el cuerpo viaja como stream y
  conservando el tipo y el nombre de archivo que manda la API.
- **La subida del recetario nunca llegó a funcionar desde la pantalla**
  (2026-08-15, ADR-048). El mismo proxy forzaba `Content-Type:
  application/json` en la ida, y en `multipart/form-data` ese header lleva un
  `boundary` que genera el navegador: pisarlo dejaba al servidor buscando una
  marca que el cuerpo no tenía. La fase 1 del importador (ADR-046) estaba
  rota desde que se escribió y nadie lo reportó porque nadie pudo pasar de la
  descarga. Ahora se reenvía el `Content-Type` entrante y el cuerpo sin
  decodificar.
- **Nada probaba el camino que recorre una persona.** Los tests del
  importador atacan a FastAPI con `TestClient` y el proxy queda fuera del
  recorrido, así que el endpoint podía estar perfecto y llegar roto al
  navegador. Se cierra con `frontend/lib/proxy.test.ts` (8 casos, sin
  levantar nada: binario byte por byte, `boundary` intacto, JSON intacto,
  error literal, 204 y 401) y con el recorrido
  `frontend/uso/importador-recetas.spec.ts` (ADR-047), que descarga la
  plantilla, verifica la firma `PK\x03\x04`, **la abre con openpyxl**, la
  llena, la sube, resuelve un insumo desconocido y la importa. Contra el
  proxy viejo falla con `Received: "plantilla.json"`.
- Costo aceptado: el cuerpo de subida se junta en memoria en vez de
  encadenarse como stream —`duplex: "half"` no está en el tipo estándar de
  `RequestInit`— y de la respuesta se copian solo `Content-Type` y
  `Content-Disposition`. Reenviar `content-encoding`/`content-length` de una
  respuesta que `fetch` ya descomprimió corrompe la descarga, y `set-cookie`
  de la API no tiene por qué cruzar al navegador.
