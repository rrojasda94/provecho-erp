# ADR-073 — La sesión se renueva sola, y el PDV lee su sucursal fresca

- **Estado:** aceptada
- **Fecha:** 2026-08-28
- **Contexto:** `frontend` (middleware, `app/pdv`), `users` (auth, alcance)
- **Relacionado:** ADR-004 (tenant), ADR-045 (bloqueo de pantalla), ADR-062
  (centro de labores ≠ alcance de datos), RN-POS-014

## Contexto

Dos síntomas del primer turno con usuarios nuevos, con la misma forma: **el
frontend tomaba una decisión con un dato congelado.**

### 1. "Se desconectan solos a los pocos minutos"

El access token dura 15 minutos y el refresh 7 días. `POST /auth/refresh`
existe desde el primer slice, con rotación y detección de reuso. Pero **el
frontend nunca lo llamaba**: la única lectura de la cookie de refresh en todo
`frontend/` era el logout. A los quince minutos exactos la cookie de acceso
caducaba y el turno entero caía a `/login`, en medio de un pedido, sin
explicación.

Se sumaba el bloqueo por inactividad de ADR-045, que a los cinco minutos tapa
la pantalla y por eso se reportó como "vence cada 5 minutos". Ese sí funciona
como se diseñó y no se toca; lo que estaba roto era lo de abajo.

### 2. "Reasigné la sucursal y el sistema seguía en la vieja"

El PDV resolvía su sucursal así:

```ts
const claims = decodificarClaims(token);
const sucursalId = claims?.sucursales?.[0];
```

Tres problemas en dos líneas:

- **Los claims son del token, y el token no se renovaba** (§1). Cambiar el
  alcance de una cuenta surtía efecto "cuando su sesión renueve", que sin
  refresh significaba *cuando vuelva a hacer login*.
- **`[0]` sobre una lista sin orden.** `UsuarioRepo.sucursal_ids` no tenía
  `ORDER BY`, así que el orden lo decidía Postgres. Un mesero asignado a CH1
  y CH2 operaba siempre contra la que saliera primera: **el pedido tomado en
  CH2 se creaba en CH1 y aparecía en las cuentas abiertas de CH1**. Ese es el
  segundo síntoma reportado, y es el mismo bug.
- **Sin selector.** Aun sabiendo cuál era el problema, no había forma de
  cambiar de local desde la pantalla.

El KDS ya había resuelto exactamente esto (sucursal por query string,
validada contra las propias, con selector); el PDV nunca recibió el
tratamiento.

## Decisión

### El middleware renueva la sesión

Un solo punto, y es el que ve **todo**: el render de un server component, el
proxy del navegador y cualquier route handler pasan por
`frontend/middleware.ts`.

Se descartaron las dos alternativas obvias:

- **En el proxy** (`app/api/proxy`): deja fuera el render del servidor, que
  es justo el camino que manda a `/login`.
- **Un latido en el navegador**: no cubre la pestaña que estuvo quieta media
  hora y vuelve con un clic — que es el caso real de una caja entre almuerzo
  y cena.

### Single-flight, o el arreglo cierra la sesión

`auth.refresh` **rota**: marca el token usado como revocado y trata un
segundo uso como señal de robo, revocando la sesión entera. Un PDV dispara
varias peticiones a la vez (carta, mesas, cuentas abiertas), así que sin
coordinación la primera renovación mataría la sesión que venía a salvar.

`refrescarSesion` guarda las renovaciones en vuelo en un `Map` de módulo, por
token: las llamadas concurrentes con el mismo refresh comparten una sola
rotación. El alcance es **un proceso de Next**, que hoy es todo (un droplet).
Con más de una instancia detrás de un balanceador esto vuelve a ser una
carrera; queda anotado en Deuda técnica.

### Se mira el `exp`, no solo la ausencia de la cookie

La cookie se planta con `maxAge` igual al plazo del token, así que el
navegador la borra al vencer — ese es el disparador barato. Pero no alcanza
solo con eso: son **dos relojes distintos**, el del navegador y el de la API,
y un desfase de segundos deja al token muerto con la cookie todavía puesta.
Esa ventana es exactamente el 401 que este ADR existe para cerrar. Además, si
`ACCESS_TOKEN_MINUTES` cambia del lado de la API sin que el frontend la siga,
el disparador por ausencia deja de dispararse nunca.

Por eso el middleware también decodifica el `exp` —sin verificar la firma, que
acá es correcto: no es una decisión de autorización, es "conviene renovar
antes de mandarlo"— y renueva con 60 segundos de margen.

**La cookie del request se reescribe, no se le agrega otra.** Con dos cookies
del mismo nombre en la cabecera el parser se queda con la primera, así que
dejar el token vencido delante haría que el nuevo viaje sin efecto.

### El PDV lee `/users/me` y elige su sucursal

- La sucursal sale de `obtenerSesion()`, que recalcula los claims contra la
  base **en cada render**, y no del JWT.
- Va por la URL (`?sucursal=<id>`), validada contra las del usuario: la
  tablet del local se queda con su enlace y la URL la escribe cualquiera.
- Con más de una sucursal asignada aparece un selector en el encabezado.
- El bloqueo "La sucursal no tiene puntos de venta" pasa a listar las otras
  sucursales del usuario como enlaces. Antes era un callejón sin salida
  aunque la caja que buscaba estuviera a un clic.

### `sucursal_ids` ordena y filtra

`ORDER BY Sucursal.nombre` y `deleted_at IS NULL`, igual que su hermano
`sucursales_de`. Esa lista **es** el claim `sucursales`, y hay pantallas que
toman la primera: sin orden, dos emisiones del mismo usuario podían diferir.
Y una sucursal borrada seguía viajando en el token, donde
`Tenant.exigir_sucursal` la dejaba pasar y el listado devolvía vacío en vez
de negar el acceso.

## Lo que NO se hizo

**Sincronizar `trabajador.sucursal_id` con `usuario_sucursal`.** Son dos cosas
distintas por decisión de ADR-062: dónde trabaja alguien (hecho laboral) y
qué datos alcanza (autorización). El usuario cambió una esperando la otra, y
la respuesta correcta es que la pantalla lo diga —RRHH → Trabajadores avisa
que el alcance se cambia en Usuarios → Cuentas—, no reintroducir la
duplicación que ADR-062 sacó a propósito.

## Consecuencias

- Sin migración.
- `frontend/lib/sesion-refresh.ts` es nuevo y pasa a ser el dueño de los
  nombres de cookie y de sus opciones; `lib/auth.ts` los reexporta. El
  middleware corre en Edge y no puede importar `lib/auth.ts`, que usa
  `Buffer`.
- El login deja de armar sus opciones de cookie a mano y usa las compartidas:
  dos juegos distintos dejarían dos cookies del mismo nombre y la sesión
  volvería a caducar aunque se esté renovando.
- Renovar re-emite `build_claims`, así que un cambio de alcance de datos
  ahora sí surte efecto en minutos sin volver a entrar. El aviso que la
  pantalla de Usuarios ya daba pasa a ser cierto.
- El bloqueo por inactividad suma `wheel` y `touchmove` a lo que cuenta como
  actividad: en una tablet, recorrer la carta con el dedo es operar el PDV, y
  sin ellos la pantalla se bloqueaba en la cara de quien la estaba usando.
