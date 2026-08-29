# ADR-079 — El marcaje se ancla al dispositivo, no a la red

- Estado: aceptado
- Fecha: 2026-08-28
- Contexto: `rrhh` (pad de asistencia), `users` (sucursal, PIN)
- Relacionado: ADR-053 (la dirección se elige en el mapa — datos personales de
  ubicación), ADR-065 (el pad de asistencia y quién configura las pantallas),
  ADR-070 (la cuenta se liga al trabajador por la persona), RN-RRHH-020/022,
  `docs/security/authorization.md`

## Contexto

ADR-065 resolvió *quién* puede marcar (el PIN del propio trabajador, contra el
lockout del login) y desde *qué cuenta* se abre el pad (una cuenta de servicio
por sucursal). No resolvió *dónde*. Dos huecos concretos:

1. **La sesión de la cuenta de servicio es exportable.** Con el mismo token,
   `/asistencia` funciona igual de bien desde cualquier navegador — el celular
   de un supervisor que quiere marcar entrada sin haber llegado, por ejemplo.
2. **El PIN se presta.** Un compañero teclea por el que llegó tarde y la
   tardanza no se reporta. Nadie mira quién estaba frente a la pantalla al
   momento de marcar.

Tres formas de "atar el marcaje al local" se evaluaron y dos se descartaron:

- **Lista de IPs públicas por sucursal.** Barato, sin frontend nuevo — pero la
  IP de un ISP residencial o de una PYME cambia sin aviso, y un bloqueo por IP
  dejaría al local entero sin poder marcar un martes cualquiera porque el
  proveedor rotó la dirección. Sirve como observación, nunca como candado.
- **Geocerca GPS pura (sin dispositivo enrolado).** La sucursal ya tiene
  lat/lng (`UbicacionMixin`), pero el GPS de una tablet fija bajo techo se
  equivoca por decenas de metros, exige HTTPS y permiso del navegador, y se
  falsea con cualquier app de ubicación falsa. Débil como candado; sirve como
  observación.
- **Reconocimiento facial.** Cierra el hueco 2 mejor que una foto simple, pero
  el costo de un proveedor biométrico y el riesgo de tratar datos biométricos
  (categoría sensible bajo Ley 29733) son desproporcionados frente a guardar
  una foto que un humano revisa si algo no cuadra.

## Decisión

Tres capas, dos que bloquean y dos que solo observan (la ubicación es una de
las dos que observan):

### 1. Terminal enrolado — bloquea (RN-RRHH-023)

`terminal_marcaje` es el dispositivo autorizado a marcar por una sucursal.
Nace inactivo con un código de 6 dígitos vigente 30 minutos
(`POST /rrhh/terminales`, `rrhh.terminal_gestionar` — alta de infraestructura
del local, igual criterio que `kds.configurar` frente a `kds.operar`). La
tablet lo teclea una sola vez en la pantalla de activación del pad
(`POST /asistencia/terminal/enrolar`, con la cuenta de servicio) y recibe un
secreto propio, que de ahí en más manda en el header `X-Terminal` de cada
marcación.

Del lado del servidor solo se guarda `sha256(secreto)` — SHA-256 y no
Argon2id, a propósito: el secreto son 128 bits que genera el servidor, no una
contraseña humana que haga falta proteger de un diccionario. Mismo criterio
que `TokenAgente` (`src/modules/users/infrastructure/models/token_agente.py`).

`POST /asistencia/terminal/marcar` resuelve el terminal por su secreto y
exige que sea de la misma sucursal que el trabajador (mismo principio que
`pad_asistencia.sucursal_de`): sin terminal activo de esa sucursal, **403**,
aunque el PIN sea correcto. Revocar (`DELETE /rrhh/terminales/{id}`) es
borrado lógico: sin fila viva no hay secreto que resuelva, y la siguiente
marcación desde esa tablet cae al 403 en el acto — sirve para una tablet
perdida o dada de baja.

El secreto viaja en una cookie **httpOnly** que pone un Server Action de
Next.js (`asistencia/actions.ts`), no en `localStorage`: el JavaScript de la
página nunca lo ve, igual criterio que el token de sesión.

### 2. Evidencia por marcación — observa, nunca bloquea (RN-RRHH-024)

Cada toque del pad escribe una fila `marcacion` (colgada de la `asistencia`
del día, que sigue siendo la fila-resumen): quién firmó, desde qué terminal
(`NULL` = corrección de back-office), con qué IP, a qué distancia de la
sucursal y con qué foto.

- **Foto**: cámara frontal al momento de marcar, JPEG de 320px al 60%
  (~40 KB). Vive en la fila (`LargeBinary`, `deferred`) y no en S3: hoy no
  existe ninguna ruta de subida al storage para RRHH y el volumen es chico.
  Se purga a los `rrhh_marcaje_foto_retencion_dias` (90 por defecto,
  tarea diaria) — se borra el binario, la fila y el resto de la evidencia
  quedan.
- **Ubicación**: `navigator.geolocation` del navegador. La distancia a la
  sucursal (`shared.ubicacion.metros_entre`, haversine) se calcula si la
  sucursal declaró `radio_marcaje_m`; si no lo declaró, no se evalúa. La
  anomalía **no se guarda como columna** — se deriva comparando en el
  momento de leer, así que corregir el radio de un local reclasifica su
  histórico entero en vez de dejarlo congelado con un criterio viejo.
- **IP**: `X-Forwarded-For` que Caddy pone en la request al llegar a Next, que
  el proxy de Next (`app/api/proxy/[...ruta]/route.ts`) ahora reenvía a la
  API. Antes de este cambio **no se reenviaba**: la API veía siempre la IP
  del contenedor `web`, nunca la del local — una evidencia falsa es peor que
  ninguna. El `FORWARDED_ALLOW_IPS` de la API tiene que confiar en este salto
  (la IP/host de `web`), no solo en el de Caddy.

Ninguno de los tres es obligatorio ni bloquea: sin permiso de cámara, sin GPS
o sin proxy de por medio, el marcaje se registra igual con esos campos en
`NULL`. Bloquear por evidencia ausente convertiría un permiso de navegador
denegado en "no puedes fichar hoy".

### 3. Radio de marcaje por sucursal, no global

`sucursal.radio_marcaje_m` (nullable, sin valor por defecto): cada local
decide si evalúa distancia y con qué margen. Un local sin GPS confiable (mala
señal, tablet siempre en el mismo rincón sin vista al cielo) simplemente no lo
configura y el pad sigue funcionando exactamente igual que antes de este ADR.

## Consecuencias

- El pad deja de marcar hasta que alguien enrole un terminal para cada
  sucursal — es la migración operativa de este cambio: sin eso, `X-Terminal`
  nunca llega y todo marcaje da 403. Cada sucursal necesita su alta desde
  Organización/RRHH → Terminales antes de que el local vuelva a fichar.
- Un supervisor con la sesión de la cuenta de servicio en su celular ya no
  puede marcar por nadie: sin el secreto del terminal (que vive en la cookie
  de esa tablet), el 403 llega antes de pedir el PIN.
- La foto y la ubicación de un trabajador son datos personales (mismo
  criterio que ADR-053 para las coordenadas de una persona). El fin es
  control de asistencia, la retención es de `rrhh_marcaje_foto_retencion_dias`
  días, y corresponde informarlo en el Reglamento Interno de Trabajo —eso es
  del negocio, no del código.
- `FORWARDED_ALLOW_IPS` en producción tiene que incluir la IP/host del
  contenedor `web` además de la de Caddy: es un cambio de configuración de
  despliegue, no de código, y sin él la IP que queda en `marcacion.ip` sigue
  siendo la del contenedor.
