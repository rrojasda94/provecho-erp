- **La imagen del frontend no traía `public/`** (2026-09-23). El modo
  `standalone` de Next no copia esa carpeta y el `Dockerfile` tampoco lo
  hacía: en staging daban 404 los manifests e íconos de las apps instalables
  (ADR-109, incluido el de Mi reparto desde ADR-098) y los logos de
  `marcas/`. Se copia en la etapa `runtime`.
