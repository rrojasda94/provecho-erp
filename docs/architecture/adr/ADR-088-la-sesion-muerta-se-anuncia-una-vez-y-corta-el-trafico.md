# ADR-088 — La sesión muerta se anuncia una vez y corta el tráfico del navegador

- Estado: aceptado
- Fecha: 2026-09-04
- Contexto: `frontend/lib/cliente-api.ts`, `frontend/lib/sesion-muerta.ts`,
  `frontend/components/sesion/aviso-sesion-expirada.tsx`,
  `frontend/app/layout.tsx`
- Relacionado: ADR-073 (la sesión se renueva sola), ADR-084 (la sesión muere
  con el navegador y a las ocho horas quietas), ADR-048 (el proxy del
  navegador pasa bytes), ADR-013 (arquitectura frontend),
  `docs/roadmap/auditoria-erp-2026-08-30.md` (hallazgo #10)

## Contexto

ADR-073 y ADR-084 resolvieron **cuánto vive** una sesión: el token de acceso
se rota solo en `middleware.ts` en cada request, el refresh dura ocho horas de
inactividad y muere con el navegador. Ninguno de los dos dijo **qué se ve
cuando la sesión ya no se puede renovar**, y la respuesta hasta hoy era: nada.

El efecto secundario de ADR-073 es lo que hace que valga la pena decidirlo
ahora. Antes de la renovación automática, un 401 en el navegador podía ser
cualquier cosa —un token de quince minutos que venció entre dos toques— y
tratarlo como "volvé a entrar" habría echado a la caja en medio de un pedido.
Hoy, un 401 que llega al navegador **ya pasó por el intento de refresco**: el
refresh está vencido, revocado o fue reusado. Es la señal más confiable de
sesión muerta que tiene el cliente.

Lo que hacía cada pantalla con ella, verificado en código (auditoría del
2026-08-30, hallazgo #10):

- **KDS** (`app/kds/use-cola.ts`): `setAviso(e.message)`, un cartel de cuatro
  segundos, y a los tres el `setInterval` vuelve a preguntar. La cola de
  cocina se queda congelada en el último dato bueno —nunca se limpia— y el
  cartel parpadea para siempre. Nadie en cocina lee eso como "la sesión
  murió"; lo lee como que el sistema anda lento.
- **Campana** (`components/shell/campana.tsx`): `catch { setError(true) }`,
  sin mirar el status. Muestra el último conteo conocido y las
  notificaciones dejan de llegar. Peor: al marcar una como leída, la quita de
  la lista optimista y el `recargar()` de rescate también da 401, así que el
  ítem desaparece y no vuelve.
- **Borradores del PDV** (`app/pdv/use-borradores-pdv.ts`): `catch {}` vacío,
  a propósito ("la persistencia es una red de seguridad, no un requisito"), y
  además borra su huella de guardado, así que **cada tecla** reintenta un PUT
  que falla. El cajero no ve absolutamente nada; se entera al recargar, con
  las pestañas vacías. Es pérdida de datos silenciosa.

Las tres son el mismo agujero en tres árboles de rutas distintos (`(app)`,
`/pdv`, `/kds`), y ninguna navegación de servidor lo tapa: ahí el redirect a
`/login` de `obtenerSesion()` ya funciona. El hueco es exclusivamente el
tráfico que sale del navegador en una página ya dibujada.

## Decisión

**Un 401 del navegador mata la sesión del lado del cliente: se anuncia una
sola vez con un diálogo modal y corta en seco las llamadas que vengan
después.**

### 1. La detección va en `lib/cliente-api.ts`, en un solo lugar

Por ahí salen **todas** las llamadas del navegador (ADR-048: el navegador
nunca habla con la API directo). Las tres funciones que salían a la red
—`pedir`, `pedirArchivo`, `subir`— repetían el mismo bloque de manejo de
error; ahora comparten `lanzar()`, que anota el 401 antes de tirar el
`ErrorApi`. Una sola línea cubre el KDS, la campana, los borradores del PDV,
las estaciones, el historial, el pad de asistencia, el editor de recetas, la
consulta de documento y el importador de planilla.

La alternativa —que cada pantalla mire `e.status === 401`— es la que produjo
tres comportamientos distintos para el mismo fallo, que es exactamente lo que
el módulo existía para evitar.

### 2. El estado vive en un módulo con una bandera, no en un contexto

`lib/sesion-muerta.ts`: `estaMuerta()`, `marcarMuerta()`, `suscribir()`. Sin
imports, como `lib/carga.ts` y `lib/errores.ts`, para que `node --test` lo
corra sin montar React ni Next.

Es un dato **de una sola vía** —una vez muerta no revive sin recargar—, así
que no necesita reconciliación ni provider. `marcarMuerta()` es idempotente:
el KDS pregunta cada 3 s y el PDV guarda cada 800 ms, de modo que la primera
sesión vencida dispara una andanada de 401 y un aviso por cada uno sería el
mismo cartel montándose sobre sí mismo.

### 3. Con la sesión muerta no se sale a la red

`abortarSiMuerta()` lanza el 401 sin llamar a `fetch`. Es lo que apaga el
bucle de refresco del KDS y el PUT por tecla del PDV, que si no seguirían
golpeando el proxy detrás del aviso hasta que alguien recargue.

### 4. El aviso es un `<dialog>` modal en el layout raíz

`components/sesion/aviso-sesion-expirada.tsx`, montado en `app/layout.tsx`,
que es el único ancestro común de `(app)`, `/pdv` y `/kds`.

Modal y no un banner por lo mismo que `pdv/bloqueo.tsx`: lo que hay detrás ya
no se puede operar, y un aviso esquivable en una tablet de cocina se esquiva.
`onCancel` prevenido —Escape no lo cierra—, un solo botón «Volver a entrar»
que va a `/login`. El diálogo nativo vive en el *top layer* del navegador, así
que tapa incluso un diálogo de formulario abierto sin pelear `z-index`.

## Consecuencias

- **Lo que ya no pasa**: la cola de cocina congelada con un cartel
  parpadeante; la campana mostrando un conteo viejo; el borrador del PDV que
  deja de guardarse y solo se descubre al recargar.
- **Lo que se pierde**: el trabajo sin guardar de la pantalla sigue
  perdiéndose — el aviso dice que la sesión murió, no rescata el formulario a
  medio llenar. Recuperar eso pide guardar el borrador en el navegador antes
  de reintentar, que es otra decisión y otro alcance.
- **Un 401 legítimo que no sea de sesión** (un endpoint que respondiera 401
  por otra razón) también dispararía el aviso. Hoy no existe: la API usa 403
  para "no te corresponde" y el 401 queda para "no sos nadie". Si algún día
  aparece, el discriminador tendría que ser un código en el cuerpo, no el
  status.
- **No cubre las Server Actions**, que corren en el servidor de Next y ya
  tienen su `redirect("/login")` en siete lugares. Son dos caminos distintos
  para el mismo hecho y conviene que sigan siéndolo: uno navega, el otro no
  puede.
- **Probado** en `frontend/lib/sesion-muerta.test.ts` (el aviso único, el
  corte en seco) y en `frontend/e2e/sesion.spec.ts`, borrando **las dos**
  cookies —hasta ahora la suite solo borraba la de acceso, o sea solo probaba
  el caso que ADR-073 sí salva.
