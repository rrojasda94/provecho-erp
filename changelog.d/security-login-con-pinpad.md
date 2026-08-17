- **El login se teclea en el pinpad, no en un campo de contraseña**
  (2026-08-15, ADR-050, enmienda a ADR-045). `frontend/app/login/page.tsx`
  pedía el PIN en un `<input type="password" autocomplete="current-password">`
  — el patrón exacto que ADR-045 había eliminado dos días antes dentro del
  PDV, en la pantalla que más veces se cruza y desde la misma tablet de la
  caja. El navegador ofrece guardarlo, y con el PIN guardado el turno
  siguiente entra con la cuenta del anterior: toda la auditoría de RN-AUD-005
  nombrando a la persona equivocada. Sacar el campo de los cuatro diálogos del
  PDV y dejarlo en la puerta no protegía nada — basta con entrar una vez.
  Ahora el usuario se teclea (es un identificador, no un secreto) y el PIN se
  toca en un teclado numérico **sin campo de formulario, ni oculto**: el valor
  vive en el estado de React y viaja en el `FormData` del envío. Al sexto
  dígito entra solo. Se descartó la lista de usuarios para elegir: enumerar al
  personal le regala la mitad de la credencial a cualquiera que pase frente a
  la caja.
- **El pinpad dejó de ser del PDV.** Se mudó de `app/pdv/pinpad.tsx` a
  `frontend/components/pinpad/` y su CSS de `pdv.css` a `globals.css`, con
  cada color pedido al token `--pdv-*` **con respaldo** en el del back office
  (`var(--pdv-rojo, var(--primary))`): dentro del PDV se ve exactamente igual
  que antes y fuera cae al sistema visual de ADR-037, modo oscuro incluido,
  sin duplicar el bloque. `app/pdv/pinpad.tsx` queda como re-export de una
  línea a propósito, para no chocar con la rama que trabaja sobre
  `dialogos.tsx`; el puente y `app/cambiar-pin/` quedan anotados como deuda.
- **El login dejó de tratar igual a las tres negativas del servidor.**
  `actions.ts` devolvía `e.message` sin mirar el status, así que "PIN
  equivocado" (401), "cuenta bloqueada quince minutos" (423) y "demasiados
  intentos desde esta IP" (429) llegaban con el mismo texto genérico — y las
  tres terminaban en lo mismo: probar de nuevo hasta bloquear la cuenta. Ahora
  cada una dice qué hacer y cuánto esperar (el 429 lee el `Retry-After`, para
  lo cual `ApiError` lo expone), y un PIN de menos de seis dígitos se corta
  **antes** de llamar a la API: con un pinpad, un "Ingresar" de más gastaría
  uno de los cinco intentos del lockout. Sin contador de intentos en el
  cliente — el estado real vive en el servidor.
- **El usuario tecleado ya no se borra al errar el PIN.** React 19 resetea los
  campos no controlados de un `<form action>` cuando la acción termina,
  también cuando devolvió error; volver a escribir el usuario en cada intento
  es justo la fricción que empuja a dejar la sesión de otro abierta. Mismo
  candado que el back office puso en sus diálogos el 2026-08-10.
- **Tres casos e2e nuevos** (13 → 16, `frontend/e2e/sesion.spec.ts`): que en
  el DOM del login no exista ningún `input` de tipo password ni con
  `autocomplete` de contraseña —se afirma el DOM y no un comportamiento,
  porque un `type="password"` agregado sin querer dejaría todo lo demás en
  verde—, con teclado físico y región viva verificados; que un PIN equivocado
  no borre el usuario; y que una cuenta bloqueada avise distinto que un PIN
  equivocado, agotando de verdad los cinco intentos sobre una cuenta de
  sacrificio del seeder (`bloqueo_e2e`). El 429 no se prueba: la suite sube el
  rate limit a propósito para poder entrar muchas veces desde la misma IP.
