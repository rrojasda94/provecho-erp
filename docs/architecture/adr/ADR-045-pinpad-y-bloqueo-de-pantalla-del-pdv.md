# ADR-045 — Pinpad y bloqueo de pantalla en el PDV

- **Estado:** aceptada — **enmendada por ADR-050** (el login también usa el
  pinpad; el componente se mudó a `components/pinpad/`)
- **Fecha:** 2026-08-13
- **Contexto:** `frontend/app/pdv`, `users` (auth)
- **Relacionado:** RN-POS-014, RN-AUD-005, ADR-013 (el PDV vive fuera del shell),
  ADR-050 (enmienda)

## Contexto

Dos problemas con la misma raíz: **la sesión del PDV termina siendo de
cualquiera**.

1. Los cuatro puntos del PDV que piden un PIN —apertura de caja, cierre,
   consumo de personal y autorización de supervisor— usaban un
   `<input type="password">`. El navegador ofrece guardarlo, y con el PIN
   guardado en la caja el turno siguiente entra con la cuenta del anterior.
   Toda la auditoría (RN-AUD-005: quién autorizó qué) pasa a nombrar a la
   persona equivocada.
2. Una caja desatendida queda operable. Quien pase puede cobrar, anular o
   registrar consumo de personal con la sesión de otro.

## Decisión

### Pinpad, y solo en el PDV

> **Enmendado el 2026-08-15 por ADR-050.** El "solo en el PDV" duró dos días:
> el login pedía el PIN en el mismo `<input type="password">` que esta
> decisión eliminó, y es la puerta por la que se entra al PDV. Hoy el
> componente vive en `frontend/components/pinpad/` y el login lo usa;
> `app/pdv/pinpad.tsx` es un re-export temporal. Todo lo demás de esta
> sección sigue vigente.

Un teclado numérico táctil (`app/pdv/pinpad.tsx`) **sin ningún `<input>`**.
El valor vive en el estado de React y lo que se ve son puntos. Esa es la
razón de existir del componente: un campo que el gestor de contraseñas no
ve no se puede guardar, y un PIN que no se guarda hay que saberlo.

Se acepta el teclado físico (hay cajas con uno): el objetivo es que el
**navegador** no lo capture, no incomodar a quien opera.

Fuera del PDV no cambia nada — el login del back office sigue con su campo
de siempre. Es una decisión explícita del encargo: la contraseña compartida
es un problema del mostrador, no de una oficina donde cada quien tiene su
equipo.

> **Este párrafo está revocado (ADR-050).** Describía mal el mapa: el login
> no es una pantalla de oficina, es la puerta por la que se entra al PDV
> desde la misma tablet. Sacar el campo de los cuatro diálogos y dejarlo en
> la puerta no protegía nada.

### Bloqueo por inactividad que NO cierra sesión

A los 5 minutos sin actividad se muestra un overlay que tapa todo. La
sesión sigue viva: la caja abierta, el borrador del pedido y las cookies
quedan intactos. Se desbloquea con el PIN del dueño de la sesión; "Cambiar
de usuario" sí hace logout real.

**Cerrar sesión a los cinco minutos habría sido peor que no hacer nada**:
el turno habría aprendido a dejar algo tocando la pantalla para no perder
el pedido a medio armar. Un control que estorba se elude, y elude también
lo que sí protegía.

### `POST /auth/verificar-pin`

Autenticado, cuerpo `{pin}`, 204 o 401. No emite tokens.

Se agrega porque **ninguno de los dos endpoints existentes dice "es la
misma persona"**:

- `POST /auth/login` rotaría la sesión — nuevo `sesion_id`, nuevos tokens —
  y con ella se perdería el borrador que el bloqueo existe para preservar.
- `POST /auth/autorizar` está para elevar a **otro** (RN-AUD-005): exige un
  código de permiso y emite un token acotado a una acción.

El usuario sale del token y no del cuerpo: pedirlo en el cuerpo dejaría
verificar el PIN de cualquiera.

## Detalles que no son arbitrarios

**El overlay es un `<dialog>` con `showModal()`**, no un `div` con
`z-index`. El PDV usa diálogos nativos, que se pintan en el *top layer* del
navegador: ningún `z-index` los tapa. Un overlay que no tape el diálogo de
cobro abierto no es un bloqueo.

Con una trampa que costó dos corridas de e2e encontrar: el `display` del
overlay va en `.pdv-bloqueo[open]`, **nunca en el selector base**. El
navegador oculta un `<dialog>` cerrado con `display: none`, y declarar
`display: grid` suelto lo pisa — el overlay quedaba pintado a pantalla
completa sobre el PDV desde el primer render, invisible al ojo porque el
fondo coincide y tragándose todos los clicks. El e2e del bloqueo lo detectó
en la aserción previa al adelanto del reloj; el del flujo de caja, como un
clic que nunca llegaba.

**El plazo se mide con un latido de 10 s contra una marca de tiempo**, no
con un `setTimeout` de cinco minutos. En una tablet con la pantalla apagada
el navegador estrangula los temporizadores largos y el bloqueo llegaría
tarde — que es exactamente cuando hace falta.

**El intento fallido cuenta contra el mismo lockout que el login** (5
intentos / 15 min, 423 Locked), y va detrás del mismo rate limit. Un
contador propio habría sido el camino cómodo para probar PINes sin agotar
los cinco del login.

## Alternativas descartadas

**`readOnly` en el `<input>`** (lo que se había previsto al planificar). Es
menos fiable: los gestores de contraseñas heurísticos siguen ofreciendo
guardar un campo `type="password"` aunque sea de solo lectura, y queda un
campo en el DOM al que un autocompletado puede escribir. Sin `input` no hay
nada que ofrecer.

**Bloquear con `login` y comparar el usuario devuelto.** Rota la sesión, y
además deja pasar el PIN de OTRO usuario válido: desbloquearía la pantalla
a nombre de alguien que no es el dueño de la sesión de abajo.

**Un temporizador en el servidor.** El servidor no sabe si alguien está
frente a la caja; solo ve requests, y un PDV con un pedido a medio armar no
hace ninguno. Además invalidar el token por inactividad es exactamente el
logout que se descartó.

## Consecuencias

- Sin migración.
- Los cuatro diálogos comparten `FirmaConPin` (usuario + pinpad): antes cada
  uno escribía su propio par de campos.
- Los e2e ya no llenan el PIN con `.fill()`; `tecleaPin()` toca los dígitos.
  El login del back office sigue usando `input[type="password"]` y no cambia
  — **hasta ADR-050**, que lo pasó al pinpad dos días después.
- El PDV pasa a pedir `/users/me` para saber el nombre de quien tiene la
  sesión: el JWT no lleva `username`, y la pantalla bloqueada tiene que
  decir de quién es la sesión que sigue abierta debajo.
