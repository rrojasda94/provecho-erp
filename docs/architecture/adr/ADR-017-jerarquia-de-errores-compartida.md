# ADR-017 — Una jerarquía de errores de aplicación y un solo mapeo a HTTP

- Estado: aceptado
- Fecha: 2026-08-01

## Contexto

Cada uno de los siete módulos declaraba su propia base (`SalesError`,
`InventoryError`, …) y sobre ella la misma tripleta: `NoEncontrado`,
`Conflicto`, `ReglaNegocio`. Cada uno de los ocho routers repetía el mismo
diccionario `_HTTP_STATUS` y la misma función `_http()`. Y cada endpoint
envolvía su caso de uso en un `try/except` cuyo cuerpo completo era
`raise _http(e) from e`: **86 repeticiones** del mismo gesto.

La duplicación ya había cobrado su precio. `sales` resolvía el mapeo por
`isinstance` —con un comentario explicando por qué: una subclase como
`PrecioNoDefinido(ReglaNegocio)` debe heredar el 409 de su base y no caer
al 400 genérico—. Los otros seis routers seguían usando
`_HTTP_STATUS.get(type(err), 400)`, la versión con el bug. La corrección se
hizo en una copia y las demás quedaron atrás; hoy no se manifiesta porque
`inventory` lista `StockInsuficiente` explícitamente, pero la próxima
subclase en cualquiera de esos seis módulos devuelve 400 en vez de 409.

El segundo costo es de omisión: un endpoint nuevo que se olvide del
`except` no devuelve 404, devuelve **500**.

## Decisión

**La jerarquía vive en `src/shared/errors.py`; el mapeo a HTTP, en un
handler global.**

```
AppError            → 400 (nada que herede de acá es un bug)
├── NoEncontrado    → 404
├── Conflicto       → 409
└── ReglaNegocio    → 409
```

Los módulos especializan cuando les aporta (`StockInsuficiente`,
`PrecioNoDefinido`) y no tocan el mapeo: el handler resuelve por
`isinstance`, así que la subclase hereda el estado de su base. Se eliminan
las siete bases por módulo, las ocho copias de `_http` y los 86
`try/except`.

**Un módulo con semántica HTTP propia registra su propio handler desde su
capa `api`.** Es el caso de `users`: 401 de credenciales, 423 de lockout,
422 de PIN mal formado. Starlette resuelve por el MRO de la excepción, así
que el handler específico gana y `core` no tiene que conocer los errores de
ningún módulo — solo llama a `registrar(app)` de cada uno.

`shared/errors.py` no importa FastAPI ni menciona códigos HTTP: `shared` no
sabe que existe una API.

## Alternativas descartadas

**Dejarlo como estaba.** Es la opción por defecto y no era irracional
mientras hubiera dos módulos. Con siete, la evidencia de que no escala ya
está en el repo: una corrección aplicada a una de ocho copias.

**Middleware en vez de exception handler.** Mismo efecto, pero el
middleware corre por fuera del ciclo de las dependencias con `yield`, y
justamente ahí es donde `get_db` hace el rollback. Con el handler, el
rollback de la sesión ya ocurrió cuando se construye la respuesta.

**Que el error lleve su propio `http_status` como atributo de clase.**
Elimina el diccionario, pero mete HTTP dentro de la capa de aplicación: el
mismo error tendría que saber qué código devolver aunque quien lo levante
sea un worker de Celery o el motor de sincronización.

## Consecuencias

- Tres endpoints conservan su `try/except`: los que **commitean en el
  camino de error** (persistir un intento de login fallido, la revocación
  de una cadena de refresh reutilizada, el intento contado de Factiliza).
  Ahí el `except` no traduce, decide sobre la transacción — el handler
  global no puede reemplazarlo. Quedan documentados como tales.
- Los routers pierden 251 líneas netas y el cuerpo de un endpoint pasa a
  ser: llamar al caso de uso, commitear, devolver.
- `except SalesError` en el replay del hub pasa a `except AppError`: algo
  más amplio, que es lo que ese punto quería decir (cualquier error de
  negocio esperado al reproducir un registro).

## Addendum (2026-08-30) — el 422 de validación entra al mismo sobre

La decisión de arriba cubre los errores **de dominio**. La validación de
entrada no es uno: la levanta FastAPI antes de que el endpoint corra, y
quedó fuera del handler global. El resultado era que el ERP tenía dos
formatos de error: `{"detail": str}` en todo lo propio y
`{"detail": [{loc, msg, type}]}` —con el `msg` en inglés— en los 422 de
Pydantic. El frontend descartaba `loc` y concatenaba los `msg`, así que un
formulario con tres campos mal cargados mostraba tres veces "Field
required" sin nombrar ninguno. Como el cliente **no** replica `pattern`,
`minimum` ni los enums a propósito, ese texto era el único mensaje de error
para toda esa clase de fallos.

`src/core/validacion.py` registra el handler de `RequestValidationError` y
devuelve el mismo sobre que el resto: `detail` como texto legible, más un
`errores[]` con `campo`/`etiqueta`/`mensaje` para que el formulario marque
el input culpable. `errores` va vacío en los 422 que no vienen de la
validación de entrada (`PinInvalido`, los `HTTPException(422)` de los
routers), así que el schema `ErrorValidacion` describe a los dos.

**Se traduce por `type` de Pydantic, no por el texto del `msg`**: el `type`
es un código estable y el `msg` es prosa que cambia entre versiones. Un
`type` que no esté en la tabla cae al `msg` original — quedar en inglés es
menos malo que perder el dato.

**No es i18n.** No hay catálogo de traducciones ni negociación de idioma:
la API habla español, igual que los mensajes de `AppError` que ya estaban
escritos en el código. Montar i18n para un solo idioma es infraestructura
que hay que mantener sin nadie del otro lado.

Las etiquetas (`unidad_medida_id` → "Unidad de medida") viven en
`src/shared/etiquetas.py` y son **por palabra**, no por campo: `codigo`,
`codigo_barras` y `numero_orden` se corrigen con tres entradas en vez de
una por cada campo de cada schema, que es lo que se desincroniza. Las
terminadas en `-ción`/`-sión` ni eso necesitan: hay una regla.

Costo aceptado: declarar el 422 propio a nivel de app hace que las 31
operaciones sin parámetros (de 464) documenten un 422 que nunca van a
devolver. Es sobre-declaración, y la alternativa era envolver
`app.openapi()` para reescribir el `$ref` operación por operación.
