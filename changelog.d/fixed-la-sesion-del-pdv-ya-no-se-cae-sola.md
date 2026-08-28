- **La sesión del PDV se caía a los quince minutos** (2026-08-28, ADR-073). El
  access token dura 15 min y el refresh 7 días, pero **el frontend nunca
  llamaba a `/auth/refresh`**: la única lectura de esa cookie en todo
  `frontend/` era el logout. El turno entero caía a `/login` en medio de un
  pedido. Ahora renueva el middleware, que es el único punto por el que pasan
  el render del servidor, el proxy del navegador y los route handlers.
  La renovación es **single-flight con ventana de gracia de 30 s**: la API
  rota el refresh y trata un segundo uso como robo revocando la sesión, así
  que sin coordinar el arreglo cerraba la caja que venía a salvar — se
  reprodujo antes de encontrarle la forma. El precio aceptado es que un
  refresh robado y reusado dentro de esos segundos, contra el mismo proceso,
  no dispara la revocación.
- **El PDV usaba la sucursal congelada del JWT** (2026-08-28, ADR-073).
  `claims.sucursales[0]` sobre una lista sin `ORDER BY`: quien tenía dos
  locales asignados operaba siempre contra el mismo, así que **el pedido
  tomado en CH2 se creaba en CH1 y aparecía en las cuentas abiertas de CH1**.
  Y como el token no se renovaba, reasignar la sucursal de una cuenta no valía
  hasta volver a entrar. Ahora sale de `/users/me` —recalculado en cada
  render—, va por `?sucursal=` validada contra las propias y hay selector con
  más de una, igual que el KDS. `UsuarioRepo.sucursal_ids` ordena por nombre y
  filtra las borradas: esa lista **es** el claim.
- **"La sucursal no tiene puntos de venta" era un callejón sin salida**
  (2026-08-28). El mensaje era terminal aunque la caja que el trabajador
  buscaba estuviera a un clic: ahora lista sus otras sucursales como enlaces.
