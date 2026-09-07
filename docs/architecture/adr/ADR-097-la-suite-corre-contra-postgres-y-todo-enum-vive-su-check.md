# ADR-097: La suite corre contra Postgres y todo `Enum` vive con su CHECK

## Estado

Aceptado (2026-09-06)

## Contexto

Los tests corren sobre SQLite en memoria (`create_engine("sqlite://")` +
`Base.metadata.create_all`), nunca contra el motor real de producción. SQLite
es laxo donde Postgres no lo es: no hace cumplir el largo de un `VARCHAR` y,
más grave, `Enum(..., native_enum=False)` — el tipo que usa todo el ERP para
sus columnas de vocabulario cerrado — no emite ningún `CHECK` por sí solo
desde SQLAlchemy 1.4 (`create_constraint` vale `False` por defecto). Sin ese
`CHECK`, un valor fuera del vocabulario entra sin ruido — la columna es un
`VARCHAR` pelado — y revienta recién en la **lectura**, con `LookupError` →
500 en cada consulta que cargue esa fila. No es un alta rechazada: es una
fila envenenada para todos hasta que alguien la corrija a mano en la base.

`persona.tipo_documento` (migración `c9f4a2e70b18`, 2026-08-30) ya mostró el
patrón real: el bug vivía en producción, invisible, porque la suite —que
corre sobre SQLite— nunca lo hubiera detectado tampoco sin el `CHECK`
explícito (SQLite sí hace cumplir un `CHECK`, una vez que existe). Quedaban
**113 columnas más** en el mismo estado, documentadas como deuda técnica
(`docs/roadmap/deuda/transversal.md`).

Cerrar esto pedía tres cosas encadenadas: que la suite pudiera correr contra
Postgres de verdad (para que un futuro bug de este tipo se note en CI, no en
producción), que ese run no fuera prohibitivamente más caro que el de
SQLite, y que las 113 columnas restantes tuvieran su `CHECK`.

## Decisión

### 1. La suite corre contra Postgres, aislada por schema

`tests/conftest.py::crear_engine_de_prueba` reemplaza el
`create_engine("sqlite://", ...)` que cada uno de los ~50 archivos de test
repetía. Por default sigue siendo SQLite en memoria — cero cambio de
comportamiento. Si la variable de entorno `TEST_DATABASE_URL` apunta a un
Postgres, cada test recibe su **propio schema** dentro de esa base:
`CREATE SCHEMA` + `execution_options(schema_translate_map={None: schema})`,
que hace que SQLAlchemy trate cualquier tabla sin schema explícito (todas
las del ERP) como si vivieran ahí. Mismo aislamiento que un SQLite
`:memory:` propio por test — ningún test ve las filas de otro — pero contra
el motor real. El schema se dropea al terminar el test.

La fixture `_engine_de_prueba` es el envoltorio de uso común; la función
`crear_engine_de_prueba(request)` de la que depende es pública y se llama
directo cuando un test necesita **más de una** base en el mismo caso (hoy
sólo `test_sync_motor.py`, que simula nube + hub).

Se agregó `idle_in_transaction_session_timeout=15s` y `lock_timeout=20s` al
conectar: corriendo esto de verdad contra un Postgres local se encontró una
sesión que quedó `idle in transaction` bloqueando el `DROP SCHEMA` del test
siguiente — más probablemente un artefacto de procesos de diagnóstico
matados a la fuerza (`SIGKILL`) durante el desarrollo de este cambio que un
leak real de la aplicación (`_override_get_db` cierra la sesión en su
`finally` en el único lugar donde el suite abre una), pero el límite queda
puesto de todas formas: sin él, cualquier sesión que no se cierre bien
cuelga el job de CI para siempre en vez de fallar con un error legible.

### 2. `create_app()` se comparte por sesión de pytest

Efecto lateral necesario del punto 1: sin esto, cada uno de los ~2200 tests
reconstruye las ~9 apps montadas (~200 ms de re-análisis de rutas de
FastAPI) — contra Postgres, ese costo se paga además por cada test que abre
su propio schema. `tests/conftest.py::_app_compartida` (session-scoped) hace
`create_app()` una sola vez por proceso de pytest; cada `env()` la recibe
como fixture y sólo pisa `app.dependency_overrides[get_db]` (y
`get_db_reportes]`), que es lo único que cualquier test muta del objeto —
verificado antes de aplicar el cambio.

**No** comparten esta fixture los dos archivos que necesitan una app
*fresca* por test: `test_security.py` (compara `app.docs_url`/`openapi_url`
antes y después de cambiar `settings.es_produccion`, que `create_app()` sólo
lee al construirse — un valor cacheado sería el trap encontrado al intentar
esto con `functools.lru_cache` sobre `create_app()` directamente, revertido)
y `test_observabilidad.py` (agrega una ruta ad-hoc al `app` para un caso de
prueba). Ambos siguen llamando `create_app()` directo.

### 3. Job `backend-postgres` en CI

Nuevo job en `.github/workflows/ci.yml`, con el mismo servicio de Postgres
16 que ya usa `migraciones`, corriendo `pytest` completo con
`TEST_DATABASE_URL` apuntando a él. **No** es uno de los seis jobs que el
ruleset de `main` exige — igual que `uso`, es deliberado: hacerlo requerido
es una decisión aparte, no un olvido de este cambio. Localmente, con fsync
por default (el modo seguro, no el que se usó para medir), crear el esquema
completo (~99 tablas) por test resulta caro en un Postgres de Docker Desktop
sobre Windows/WSL2 — la velocidad real en el runner de GitHub Actions
(Linux nativo, sin la capa de virtualización) es la que decide si esto
alcanza para ser obligatorio; si no alcanza, el paso (b) que la propia deuda
técnica ya dejaba anotado —esquema + seed una sola vez por worker y cada
test dentro de una transacción con `SAVEPOINT`— es el siguiente escalón, y
es deliberadamente **no** lo que este cambio hace.

### 4. Las 113 columnas restantes tienen su CHECK

Mismo patrón que `persona.tipo_documento`: un `CheckConstraint` explícito en
`__table_args__` (no `Enum(create_constraint=True)`, que queda ligado al
tipo — `_type_bound` — y `alembic check` lo ve como constraint sobrante en
cada corrida contra el modelo), con el mismo `name=` que el `Enum` que
respalda. 114 `CheckConstraint` nuevos en 65 tablas — la migración
`c4f3e14f5bce` sanea (`UPDATE ... SET col = NULL WHERE col NOT IN (...)`)
las columnas nullable antes de crear el `CHECK`; las `NOT NULL` no tienen a
dónde sanear un valor inválido sin inventar un dato, así que el
`CREATE CONSTRAINT` falla ruidoso si hay una fila sucia — preferible a
adivinar. Probada contra Postgres real: `upgrade head` → `downgrade` →
`upgrade head` → `alembic check` (sin diferencias) → verificación manual de
que el `CHECK` rechaza un valor fuera de vocabulario (`UPDATE cliente SET
tipo = 'invalido'` → `ck_cliente_tipo_cliente` lo rechaza).

Un caso no siguió el patrón mecánico: `ajuste.motivo` reusa el `Enum`
`MOTIVO_AJUSTE` **construido** en `movimiento_inventario.py` en vez de tener
el suyo propio — el `CHECK` de `ajuste` se agregó a mano, reusando el mismo
vocabulario, porque es otra tabla y necesita su propio constraint.

### 5. Guardia contra que la deuda vuelva a crecer

`tests/test_arquitectura.py::test_todo_enum_sin_tipo_nativo_tiene_su_check_constraint`
recorre cada archivo de modelos (`ast`, no import — no necesita una base) y
falla si aparece un `Enum(..., native_enum=False)` sin un `CheckConstraint`
con el mismo `name=` en el mismo archivo. No detecta el caso de
`ajuste.py`/`movimiento_inventario.py` (un `Enum` construido en un archivo y
reusado en otro): ese patrón es hoy único en todo el repo y se revisó a
mano; si reaparece, necesita el mismo cuidado.

## Consecuencias

- Ganancia real: un `Enum` sin `CHECK` que se agregue de acá en adelante lo
  frena el guard test en SQLite, sin necesidad de Postgres corriendo.
- Los `CHECK` de las 113 columnas se prueban de verdad en cualquier corrida
  del suite (SQLite los hace cumplir también) — antes ninguna corrida los
  ejercitaba.
- El costo de correr la suite contra Postgres localmente es hoy más alto
  que contra SQLite (crear el esquema completo por test, en vez de un
  archivo `:memory:`). Aceptado por ahora: el job de CI no es obligatorio,
  y el siguiente escalón (esquema + seed una vez por worker, transacción con
  `SAVEPOINT` por test) ya está anotado como el paso que sigue si esto
  molesta en la práctica.
- No hay `ALTER COLUMN` en la migración: ninguna de las 114 columnas
  necesitó ensancharse — sus valores ya cabían en el `VARCHAR` existente.

## Nota de coordinación

Esta rama (`chore/transversal-suite-contra-postgres`) se escribió en
paralelo con `fix/transversal-relojes-documento-y-cache` (T1, mergeada como
ADR-095), `fix/transversal-patch-vaciar-un-opcional` (T2, ADR-096) y el
bloque de `inventory` (ADR-090 a 094), sobre el mismo `main` que entonces
terminaba en 089. Renumerada a 097 al mergear.
