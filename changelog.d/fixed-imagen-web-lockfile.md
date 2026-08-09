- **La imagen del frontend no arrancaba, y nadie se enteraba hasta
  reconstruirla** (2026-08-09). El `Dockerfile` de `frontend/` copiaba solo
  `package.json` —sin el lock— y resolvía los rangos de nuevo en cada build;
  después, el `COPY . .` metía el `node_modules` **del host** encima del que
  acababa de instalar, porque no había `.dockerignore`. Con el árbol local
  desactualizado (Next 15) sobre una instalación de Next 16, el contenedor
  moría al arrancar:

  ```
  ⚠ Mismatching @next/swc version, detected: 16.3.0 while Next.js is on 15.5.22
  [Error: Missing field `writeRoutesHashesManifest`]
  ```

  El contenedor parecía sano porque venía corriendo con una imagen vieja,
  anterior a la deriva: el fallo aparecía recién al reconstruir.
  Ahora `npm ci` sobre `package-lock.json` —las versiones exactas que probó
  el CI— y un `.dockerignore` que deja fuera `node_modules`, `.next` y el
  `.env`, que además se colaba en la imagen. De paso el contexto de build
  baja de cientos de MB a lo que ocupa el código.
