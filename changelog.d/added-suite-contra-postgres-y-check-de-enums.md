- La suite de tests puede correr contra Postgres, no sólo SQLite (ADR-097):
  `TEST_DATABASE_URL` hace que cada test reciba su propio schema en un
  Postgres real, con el mismo aislamiento que el SQLite en memoria de
  siempre. Nuevo job `backend-postgres` en CI (no forma parte de los seis
  obligatorios).
- `create_app()` se comparte por sesión de pytest en vez de reconstruirse en
  cada uno de los ~50 archivos de test que la llamaban — quitaba ~200 ms por
  test de puro re-análisis de rutas de FastAPI.
- 114 columnas `Enum(native_enum=False)` en 65 tablas ganan su
  `CheckConstraint` (antes sólo `persona.tipo_documento` lo tenía): un valor
  fuera del vocabulario ahora se **rechaza al escribir**, en vez de guardarse
  sin ruido y reventar con `LookupError` → 500 en cada lectura posterior de
  esa fila. Nuevo test guardián que impide que la lista vuelva a crecer sin
  su CHECK.
