# ADR-050 — El login también se teclea en el pinpad

- **Estado:** aceptada
- **Fecha:** 2026-08-15
- **Contexto:** `frontend/app/login`, `frontend/components/pinpad`, `users` (auth)
- **Relacionado:** **enmienda a ADR-045** (pinpad y bloqueo del PDV), RN-AUD-005,
  RN-POS-014, ADR-037 (sistema visual), ADR-041 (reseteo de PIN)

## Contexto

ADR-045 sacó el `<input type="password">` de los cuatro puntos del PDV que
piden un PIN, y cerró diciendo que **fuera del PDV no cambiaba nada**: "la
contraseña compartida es un problema del mostrador, no de una oficina donde
cada quien tiene su equipo".

Esa frase describía mal el mapa. El login **no es una pantalla de oficina**:
es la puerta por la que se entra a todas, incluido el PDV, y la que más veces
se cruza en una tablet de mostrador. `frontend/app/login/page.tsx` seguía
pidiendo el PIN en un `<input type="password" autocomplete="current-password">`
—el patrón exacto que ADR-045 eliminó, con la etiqueta que le pide al
navegador que lo guarde—. Con el PIN guardado en la tablet de la caja, el
turno siguiente entra con la cuenta del anterior y toda la auditoría de
RN-AUD-005 nombra a la persona equivocada. Haberlo sacado de los cuatro
diálogos y dejarlo en la puerta no protege nada: basta con entrar una vez.

Había además un segundo problema, más silencioso. El servidor distingue tres
negativas —401 credenciales, **423** cuenta bloqueada quince minutos tras
cinco intentos (`users/domain/rules.py`), **429** demasiados intentos desde
la IP, con `Retry-After`— y `actions.ts` devolvía `e.message` sin mirar el
status. Las tres llegaban a la pantalla como el mismo texto genérico, y quien
las recibe necesita cosas distintas: volver a teclear, esperar, o llamar a un
supervisor. Con un solo mensaje, las tres terminan en lo mismo: probar de
nuevo hasta bloquear la cuenta.

## Decisión

### El PIN del login se toca, no se escribe

Usuario en un campo de texto normal (es un identificador, no un secreto: que
el navegador lo recuerde es una ayuda). El PIN, en el mismo `Pinpad` del PDV,
**sin ningún campo de formulario** — ni siquiera uno oculto. El valor vive en
el estado de React y viaja en el `FormData` que arma el envío. Lo que un
gestor de contraseñas no ve no lo puede ofrecer.

**No hay lista de usuarios para elegir**, que era la alternativa cómoda: una
pantalla que enumera al personal le regala la mitad de la credencial a
cualquiera que pase por delante de la caja, y convierte el login en un
selector donde entrar como otro es un toque.

Al sexto dígito se envía solo (`onCompleto`). "Ingresar" sigue existiendo
para quien llegó por teclado.

### El pinpad sale de `app/pdv/`

Se muda a `frontend/components/pinpad/`, con su CSS a `globals.css`. No hay
nada del PDV en el componente —el propio ADR-045 lo dejó anotado: "si algún
día lo pide otra pantalla, se muda"—, y ese día es hoy.

Los colores se piden a los tokens `--pdv-*` **con respaldo** en los del back
office (`var(--pdv-rojo, var(--primary))`). Dentro de `.pdv` los `--pdv-*`
están definidos y el teclado se ve exactamente igual que antes; fuera, cae al
sistema visual de ADR-037 con su modo oscuro. Una sola regla para las dos
paletas, sin duplicar el bloque ni inventar tokens.

`frontend/app/pdv/pinpad.tsx` queda como **re-export de una línea**. Es
deliberado y temporal: hay otra rama trabajando sobre `app/pdv/dialogos.tsx`
(900 líneas) y cambiarle el `import` desde acá es un conflicto garantizado
sobre un archivo que no tenemos por qué tocar. El puente se borra con esos
dos imports, en la rama que los toque — anotado en
`docs/roadmap/deuda/frontend.md`.

### Cada negativa dice qué hacer

`loginAction` devuelve `{ error, motivo }` en vez de un texto suelto:

| Status | `motivo` | Qué se dice |
| --- | --- | --- |
| — (validación local) | `incompleto` | falta el usuario, o el PIN no tiene seis dígitos |
| 401 | `credenciales` | usuario o PIN incorrectos, **y** que a los 5 seguidos la cuenta se bloquea |
| 423 | `bloqueo` | bloqueada; vuelve en 15 minutos o pide un reseteo (ADR-041) |
| 429 | `limite` | demasiados intentos desde este equipo; cuánto esperar, leído del `Retry-After` |
| otro | `servidor` | el mensaje del servidor, tal cual |

El `motivo` viaja aparte del texto para que la pantalla distinga sin leer
copy, y para que una prueba lo afirme sin atarse a la redacción.

**El PIN incompleto se corta antes de llamar a la API.** Con un pinpad, un
"Ingresar" de más manda tres dígitos, y tres dígitos son un 401 que gasta uno
de los cinco intentos del lockout. Bloquear a alguien por un toque de más
sería nuestro, no suyo.

`ApiError` gana `reintentarEn`, leído del `Retry-After`. Es el único dato que
dice *cuánto*: sin él la pantalla solo puede escribir "más tarde".

## Detalles que no son arbitrarios

**El campo de usuario es controlado y la acción se despacha a mano**, nunca
por `<form action={...}>`. React 19 resetea los campos no controlados de un
formulario cuando su acción termina, **también cuando devolvió error**: con
el PIN mal tecleado se borraba además el usuario. Volver a escribirlo en cada
intento es exactamente la fricción que empuja a dejar la sesión de otro
abierta — el defecto que este ADR viene a cerrar. Es el mismo candado que el
back office ya puso en sus diálogos el 2026-08-10.

**No hay contador de intentos en el cliente.** Se dice la regla ("a los 5 la
cuenta se bloquea"), no cuántos quedan. El estado real vive en el servidor y
un contador local mentiría apenas alguien abra otra pestaña — y mentiría
tranquilizando, que es la peor dirección.

**El 429 no se puede probar de verdad en e2e.** `e2e/servidor-api.mjs` sube
`RATE_LIMIT_LOGIN_INTENTOS` a 100000 a propósito: toda la suite entra desde
`127.0.0.1` y con el límite real las últimas pruebas recibirían un 429 que no
tiene nada que ver con lo que están probando. Queda cubierto por lectura de
código y por el mismo mapeo que sí se ejercita en 401 y 423.

**El 423 sí se prueba de verdad**, y necesitó una cuenta de sacrificio en el
seeder (`bloqueo_e2e`): la prueba le agota los cinco intentos y la deja
inutilizable quince minutos. Hacerlo sobre el cajero o el encargado dejaría
sin sesión a las pruebas que corran después, en un orden que Playwright no
promete. El 401 de referencia se saca de un usuario **inexistente**, que
devuelve lo mismo por anti-enumeración y no le gasta intentos a nadie.

## Alternativas descartadas

**Un `<input type="hidden">` con el PIN.** Pasaría la aserción del DOM y
ningún gestor lo ofrecería para guardar. Se descarta igual: vuelve a haber un
campo en el formulario al que un autocompletado o un script puede escribir, y
la regla "el PIN no tiene campo" deja de poder verificarse mirando el DOM —
que es justo lo que la hace sostenible.

**Dejar el login como estaba y confiar en `autocomplete="off"`.** Los
gestores heurísticos lo ignoran desde hace años sobre campos
`type="password"`; es la misma razón por la que ADR-045 descartó `readOnly`.

**Migrar también `app/cambiar-pin/`** (tres `<input type="password">`: PIN
actual, nuevo y repetido). Es otro flujo y otra decisión de diseño —tres
pinpads en una pantalla, o uno con pasos— y mezclarla acá dejaba un cambio
imposible de revisar. Queda anotada como deuda.

## Consecuencias

- Sin migración. Sin cambios de backend.
- `frontend/app/pdv/pinpad.tsx` es un re-export mientras dure el puente.
- **El pinpad de la pantalla bloqueada del PDV se ve mejor que antes, y eso
  destapó un defecto**: `BloqueoPorInactividad` se monta como hermano de
  `<main className="pdv">` (`app/pdv/page.tsx`), no dentro, así que sus
  `var(--pdv-*)` **sin respaldo** eran inválidos al calcular y las reglas
  quedaban en `unset` — los puntos del PIN sin borde y el overlay con el
  fondo blanco del navegador. Con el respaldo del back office ahora sí se
  pintan. El overlay en sí (`.pdv-bloqueo`, que sigue sin respaldo) queda
  anotado como deuda: arreglarlo cambia cómo se ve una pantalla que este
  cambio no venía a tocar.
- `e2e/util.ts` teclea el PIN del login en el pinpad; **los 13 casos que ya
  existían siguen pasando por ahí** y ninguno tuvo que cambiar además del
  helper. Se suman 3: que no exista campo de contraseña en el DOM (con
  teclado físico y región viva verificados), que un PIN equivocado no borre
  el usuario, y que el 423 se distinga del 401.
- El login del back office deja de ser una excepción: **ningún PIN del ERP se
  escribe ya en un campo**, salvo el cambio de PIN, que queda en deuda.
