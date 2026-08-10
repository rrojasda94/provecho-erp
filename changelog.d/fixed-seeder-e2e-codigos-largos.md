- **El seeder de e2e sembraba códigos que no caben en su columna**
  (2026-08-10). `articulo.id_interno` y `producto_comercial.id_interno` son
  `String(4)` y la siembra escribía `"E2E-H001"` y `"E2E-P001"`, de ocho.
  Entraban igual porque **SQLite no aplica el largo de un `VARCHAR`**; contra
  Postgres la siembra habría reventado. Salió a la luz al estrenar la edición
  de artículos: la pantalla no podía ni reenviar el código existente sin
  recibir un 422 de su propio valor. Ahora son `EH01` y `EP01`.
