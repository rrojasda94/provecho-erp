- **La guía de remisión ya tiene pantalla** (2026-09-06, ADR-090). Cuatro
  endpoints con ADR (ADR-027) y catorce pruebas llevaban desde el
  2026-08-05 sin un solo llamador desde el frontend. Se emite con el botón
  «Guía» desde Traslados y desde Devoluciones (`origen=proveedor`), no
  desde una pantalla propia — RN-TRP-002 exige que lo transportado
  coincida con lo declarado, y un formulario aparte sería la forma de que
  no coincida. Al abrir pregunta si ya existe una y muestra su estado, o el
  formulario si no hay ninguna; lista `/inventario/guias-remision` de solo
  lectura para revisar lo ya emitido. Sumó `GET
  /devoluciones/{id}/guia-remision`, que faltaba, simétrico al de
  transferencia.
- **Descarga de PDF/XML/CDR de una guía aceptada**
  (`GET /guias-remision/{id}/descargar/{formato}`). `FactilizaClient.descargar`
  gana `recurso: "invoice" | "despatch"` en vez de duplicar el cliente —
  mismo verbo, mismo formato de respuesta, solo cambia el prefijo de la
  ruta. La anulación por comunicación de baja queda fuera de este cambio:
  su payload no se verificó contra el sandbox de QA de Factiliza y
  construirla a ciegas es el error que ADR-005 ya evitó una vez con la
  boleta.
- **`unidad_medida.codigo_sunat`** (migración `4466bd44b238`), editable
  desde Catálogo. Antes la guía traducía toda unidad con un diccionario de
  doce entradas y caía en `NIU` sin avisar — una "Doypack 2kg" salía mal
  en la GRE. La columna manda sobre el diccionario cuando está configurada;
  el diccionario sigue de valor de siembra y de fallback para lo que nadie
  configuró todavía.
