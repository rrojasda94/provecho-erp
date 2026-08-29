- **Exportación del tablero de reportes** (ADR-082, Fase E). Cierra la
  deuda abierta "la exportación baja lo que se ve, no el dataset completo".
- **Imprimir el tablero**: botón nuevo junto a Guardar, `window.print()` +
  la variante `print:` de Tailwind — cero dependencias. Esconde toda la
  interfaz de edición (filtros, "+Agregar reporte", "Compartir con el
  rol", asa de arrastre, botones de exportar de cada tarjeta) y también la
  navegación del shell (sidebar, barra superior, pie de página): sin eso,
  imprimir un tablero imprimía la aplicación entera. El navegador ya
  ofrece "Guardar como PDF" en su propio diálogo.
- **XLSX del dataset completo, no las 500 filas de la tarjeta**:
  `POST /reportes/{codigo}/exportar` corre el mismo reporte, con el mismo
  permiso y el mismo rango que `/datos` (factorizado en `_reporte_y_filas`
  para no duplicar la doble puerta de RBAC ni la resolución de
  sucursal/marca), pero con el tope en 50 000 filas
  (`LIMITE_MAXIMO_EXPORTACION`) en vez de 500. Reusa
  `src/shared/planilla.py` (ya en el proyecto desde la carga masiva de
  recetas, ADR-052) para armar el `.xlsx`.
- **Los montos salen como número real, no como texto**: a diferencia del
  CSV por tarjeta (`aCsv`), acá `Decimal` se convierte a `float` antes de
  escribir la celda — una fórmula `=SUMA(...)` sobre la columna funciona
  sin que nadie la convierta a número primero.
- Verificado con 5 tests nuevos que leen el `.xlsx` de verdad con
  `openpyxl` (encabezado, tipo de cada celda, y que el tope real sea
  50 000 y no 500) — no solo el status code de la respuesta.
