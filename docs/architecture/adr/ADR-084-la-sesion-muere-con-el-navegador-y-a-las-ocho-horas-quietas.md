# ADR-084 — La sesión muere con el navegador y a las ocho horas quietas

- **Estado:** aceptada
- **Fecha:** 2026-08-30
- **Contexto:** `frontend` (cookies, middleware), `users` (auth)
- **Relacionado:** ADR-073 (la sesión se renueva sola), ADR-045 (bloqueo de
  pantalla), ADR-079 (el terminal de marcaje), RN-POS-014

## Contexto

Reporte del turno de prueba, textual: *«He apagado la PC y entrado nuevamente
al staging y mi sesión seguía abierta. Eso no puede pasar.»*

Y no era un bug: era lo que el código pedía. `opcionesCookie(maxAge)` plantaba
las dos cookies con `Max-Age` —900 s el acceso, 604 800 s el refresh—. Una
cookie con `Max-Age` es **persistente**: el navegador la escribe en disco y no
la borra al cerrarse. Al volver, el middleware de ADR-073 veía el acceso
vencido, rotaba el refresh contra `POST /auth/refresh` y replantaba las dos
con el plazo completo.

Del lado del servidor tampoco había nada que lo frenara. `refresh_token` tiene
`expira_en`, pero **cada rotación inserta una fila nueva** con
`expira_en = ahora + 7 días`: mientras la sesión se use, su vencimiento se
corre solo. Y el `maxAge` de la cookie hacía que "usarla" no requiriera a
nadie — bastaba abrir el navegador. El resultado es una sesión que en la
práctica no caduca nunca, en una PC que puede ser la del mostrador.

El bloqueo de pantalla del PDV (ADR-045) no cubre esto y no pretendía
hacerlo: tapa la pantalla a los cinco minutos y **no cierra la sesión**, a
propósito, porque un bloqueo que hiciera perder el pedido a medio armar se
eludiría dejando la pantalla tocada.

## Decisión

### Dos mitades, porque ninguna alcanza sola

**1. Las cookies pasan a ser de sesión.** `opcionesCookie()` deja de recibir y
de poner `maxAge`. Sin `Max-Age` ni `Expires`, el navegador las borra al
cerrarse: cerrar el sistema vuelve a significar cerrar la sesión, que es lo
que cualquiera espera.

**2. La API corta por inactividad a las 8 horas.** `auth.refresh` mide contra
el `created_at` de la fila que le llega y, si pasó el plazo, revoca la
**cadena entera** (`revocar_sesion`) y devuelve 401.

La primera sola no alcanza porque **«restaurar pestañas» devuelve las cookies
de sesión intactas**. Es la configuración por defecto de Chrome en Windows
después de un apagón sucio, que es exactamente el caso reportado. La segunda
sola tampoco: dejaría el refresh en el disco de un equipo compartido durante
siete días, disponible para cualquiera que abra el navegador dentro de la
ventana de inactividad.

### Por qué se reusa `created_at` y no una columna nueva

No hace falta un `ultimo_uso_en`: la rotación **ya** inserta una fila por cada
renovación, así que el `created_at` del token que llega **es** la hora de la
última actividad de esa sesión. El middleware renueva con un minuto de margen
sobre los quince del access token, o sea que ese dato nunca se atrasa más de
catorce minutos. Una columna nueva sería una migración para guardar algo que
la tabla ya dice.

### Por qué ocho horas

Dos era la alternativa obvia y es la equivocada. Una caja entre almuerzo y
cena puede quedarse media tarde sin que nadie la toque, y hacerla volver a
entrar ahí **es el problema que ADR-073 vino a arreglar** —«se desconectan
solos a los pocos minutos»—; reintroducirlo con otro número sería deshacer ese
trabajo. Ocho horas entra un turno completo y no entra una noche, que es la
frontera que el reporte describe. El plazo vive en
`REFRESH_INACTIVIDAD_HORAS`, no en una constante: `0` lo apaga para un
despliegue que necesite una sesión que no caduque por quietud (un tablero
colgado en la pared), sin tocar código.

### El corte se registra como `info`, no como `error`

`log_seguridad` ya usa `error` para el reuso de un refresh token, que es señal
fuerte de robo. Vencer por inactividad es lo esperado y pasa cada mañana:
mezclarlos enterraría la alerta que sí importa bajo el ruido de la rutina.

## Lo que NO se hizo

- **Tope absoluto de sesión.** Alguien que usa el ERP todos los días mantiene
  su cadena viva indefinidamente. Cortarla cada N días obligaría a mirar el
  primer token de la cadena (`sesion_id`) y sumaría un login sorpresa a mitad
  de turno; el corte por inactividad ya cubre lo que el reporte pedía.
- **Cerrar sesión desde el navegador al cerrar la ventana.** `beforeunload` no
  se dispara de forma confiable —y menos en un apagón, que es el caso—, así
  que sería una promesa que a veces no se cumple. El corte del servidor no
  depende de que el cliente colabore.
- **Purgar las filas de `refresh_token` vencidas.** La tabla crece con una
  fila por renovación y nadie la limpia. Es anterior a este cambio y no lo
  empeora; va a Deuda técnica.

## Consecuencias

- Sin migración: `created_at` ya existía (`TimestampMixin`).
- **El pad de asistencia pide login después de apagar la tablet.** Corre bajo
  la sesión de una cuenta de servicio y llama a `obtenerSesion()`, así que un
  local que apaga la tablet en la noche entra a la mañana con seis dígitos. El
  **enrolamiento del dispositivo no se pierde**: `COOKIE_TERMINAL` es de un
  año y no se toca (ADR-079) — lo que caduca es la sesión de la persona, no la
  identidad del equipo. Si molesta, la salida es una marca por cuenta
  («sesión persistente»), no aflojarle el plazo a todos; queda anotado.
- `MINUTOS_ACCESS`, `DIAS_REFRESH`, `MAX_AGE_ACCESS` y `MAX_AGE_REFRESH`
  desaparecen del frontend. Existían solo para calcular el `maxAge`, y eran
  una copia a mano de dos valores de la API que había que acordarse de
  sincronizar.
- La renovación silenciosa de ADR-073 sigue funcionando, pero ahora con **un
  solo disparador**: el `exp` del JWT. El otro —que el navegador borrara la
  cookie de acceso al vencer— ya no ocurre. Ese camino existía desde ADR-073
  para cubrir el desfase entre el reloj del navegador y el de la API, y pasa a
  ser el único.
