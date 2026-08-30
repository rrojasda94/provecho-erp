- **Un error de validación se leía en inglés y sin decir qué campo era**
  (2026-08-30). La API respondía los 422 con el formato crudo de FastAPI
  —`detail` como lista de `{loc, msg, type}`— y el frontend, que descarta
  `loc`, los mostraba concatenados: un formulario con tres campos mal
  cargados decía "Field required; Field required; Input should be..." tres
  veces lo mismo y ninguna nombraba un campo. Y como el cliente **no**
  replica `pattern`, `minimum` ni los enums a propósito, ese texto era el
  único mensaje de error para toda esa clase de fallos. Ahora `detail` es un
  texto en español que nombra cada campo ("Código: máximo 5 caracteres;
  Módulo: valor no válido: se espera 'compras' o 'rrhh'") y viaja además un
  `errores[]` con el que el diálogo de formulario marca y enfoca el primer
  input rechazado. La traducción va por `type` de Pydantic —un código
  estable— y no por el texto del mensaje; lo que no esté en la tabla cae al
  mensaje original, porque quedar en inglés es menos malo que perder el
  dato.
- **El parseo del error estaba duplicado byte por byte** en los dos clientes
  HTTP del frontend (`lib/api.ts` y `lib/cliente-api.ts`), y el helper
  `mensajeDe(e, porDefecto)` copiado en quince `actions.ts`. Todo eso vive
  ahora en `lib/errores.ts`. De paso deja de escribir "undefined; undefined"
  cuando un `detail` de lista viene sin `msg`.
