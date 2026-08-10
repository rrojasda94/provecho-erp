- **Un reporte ya no es una línea de texto: lleva al lugar donde se actúa**
  (2026-08-09, ADR-036). `reporte_emitido` guardaba `referencia_tipo` +
  `referencia_id` desde ADR-033 y **nadie los renderizaba**; el detalle
  `GET /reports/emitidos/{id}` existía y el frontend **nunca lo llamaba**. Ahora
  hay ficha de reporte (`/reportes/emitidos/[id]`) con quién lo provocó, de
  dónde viene, la foto de datos, a quién le llegó y por qué, y un botón al
  registro. El botón se esconde si el usuario no tiene el permiso del módulo
  dueño: ser destinatario no da acceso al dato (RN-REP-002).
- **Ocho endpoints `GET` que no existían.** Detalle de artículo, SKU, lote,
  categoría y ajuste en `inventory`; cierre de caja y pago a proveedor en
  `accounting`. Los ajustes de inventario **no tenían ni siquiera un listado**:
  se creaban y se aprobaban por API, y el reporte urgente de «ajuste fuera de
  margen» apuntaba a una pantalla que no existía. Ahora se aprueban y se
  rechazan desde `/inventario/ajustes`.
- **`src/core/destinos.py`**: el mapa `referencia_tipo` → endpoint + permiso.
  Vive en `core` porque lo leen `modules/reports` y `core/reportes`, que no
  pueden verse entre sí. `tests/test_destinos.py` verifica que **toda ruta del
  mapa esté montada de verdad** en la app: un rename de endpoint rompe el
  enlace en CI y no en producción (RN-REP-010).
- **Cada fila del tablero de consulta enlaza a su registro.** `Columna` gana
  `enlace` y las cuatro `queries_publicas` de las listas de problemas
  (`pedidos_demorados`, `consumos_omitidos`, `disponible_negativo`,
  `salidas_sin_lote`) proyectan el id que no proyectaban. Solo esas cuatro: el
  total de un martes no es un registro al que se pueda ir.
- **La campana navega al reporte** además de marcarlo leído. Antes decía que
  algo pasó y había que salir a buscarlo a mano.
