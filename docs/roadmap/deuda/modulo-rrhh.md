# Deuda técnica — Módulo rrhh (slice completo — deuda declarada)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-07-25 **Ciclo laboral completo**: `trabajador` (capa de aplicación
  que faltaba desde el slice de venta) + `contrato_laboral`, `postulante`,
  `socio`, `boleta_pago`, `liquidacion_bss`, `memorandum`, `amonestacion`,
  `acta`, `certificado_trabajo`, `solicitud_permiso`, `pacto_permanencia`,
  `asistencia`. Migración `9e1b6a4c7d23`.
- ⬜ **`contrato`/`solicitud` transversales**: `contrato_laboral` y
  `solicitud_permiso` se modelaron directo en `rrhh` (sin precedente de
  entidad genérica en código todavía) — mismo diferimiento que `purchases`
  hizo con `cotizacion`. Si otro módulo necesita `contrato`/`solicitud`
  genérico, extraer entidad transversal en `src/shared/` y migrar ambos.
- ⬜ **Eventos `rrhh.*` sin consumidor**: `trabajador_cesado`,
  `contrato_laboral_firmado`, `boleta_pago_emitida`, `liquidacion_bss_pagada`,
  `solicitud_permiso_aprobada`, `amonestacion_emitida` se publican pero
  nadie escucha todavía. Candidatos: `accounting` podría generar asiento al
  escuchar `boleta_pago_emitida`/`liquidacion_bss_pagada` (mismo patrón que
  `purchases.compra_recibida`); `users` podría desactivar el `usuario`
  ligado al escuchar `trabajador_cesado`.
- ⬜ **RN-RRHH-007 (visado de abogado) y RN-CTR-002 sin enforcement**: las
  cartas/actas se generan desde plantilla + datos del ERP, pero no hay
  entidad `plantilla` ni flag de "visado" — hoy es proceso manual fuera del
  ERP.
- ✅ 2026-08-01 **Convocatoria + tablero de contratación** (migración
  `a7f2c81e4b95`): `convocatoria` (borrador → publicada → cerrada) con
  RN-RRHH-013 aplicada en código —sin `perfil_puesto` no se publica—,
  formulario público de postulación por token (Google Forms + Apps Script,
  `POST /rrhh/postulaciones/{token}`, sin JWT, rate limit 20/h por IP),
  `postulante` con datos propios y `respuestas` JSONB (el candidato no entra
  a `persona` hasta contratar) y un solo tablero de 8 columnas + `descartado`
  para los 13 pasos de incorporación. Tests: `tests/test_rrhh_convocatoria.py`.
- ⬜ **Perfil de puesto sigue siendo documental**: `convocatoria.perfil_puesto`
  guarda el slug de `docs/rrhh/perfiles/`; no hay tabla `perfil_puesto` ni
  validación de que el slug exista. Vale la pena recién cuando los perfiles
  cambien seguido o los edite alguien que no toca el repo.
- ⬜ **Inducción sin checklist por paso**: los pasos 10-13 (inducción al grupo,
  uniforme, inducción al puesto, evaluación de prueba) son dos columnas del
  tablero (`inducido`, `confirmado`), no ítems con responsable y evidencia.
  Modelarlos aparte solo si la inducción empieza a fallar por pasos que nadie
  hizo.
- 🔶 **Pantallas de RRHH — contratación ✅ 2026-08-05, el resto no**:
  `/rrhh/contratacion` con las convocatorias (crear, publicar exigiendo
  perfil por RN-RRHH-013, cerrar) y **el tablero de las 8 etapas**: avance
  de a una columna, descarte con motivo obligatorio (Ley 26772) y
  contratación —que es donde nacen `persona` y `trabajador`—. Los
  descartados van plegados aparte: no son parte del flujo, pero esconderlos
  borraría la evidencia de por qué se descartó a alguien. La convocatoria
  seleccionada viaja en el query param para poder compartir la URL.
  Verificado en navegador de punta a punta: crear → publicar → dos
  postulaciones por el endpoint público → avanzar cuatro columnas →
  contratar (creó a Rosa Pinedo como Cocinera) → descartar con motivo.
  **Lo que sigue sin pantalla y por qué**: boletas, liquidaciones,
  memorándums, amonestaciones, actas, permisos y pactos solo
  tienen `POST` y `GET /{id}` en la API — **no hay endpoint de listado**,
  así que no se pueden dibujar sin agregarlos primero. El legajo del
  trabajador es el slice que los junta, y necesita backend antes que
  frontend.
- ✅ 2026-08-05 **Listados del legajo de RRHH**: `application/legajo.py` +
  `GET /trabajadores/{id}/legajo` (contratos, amonestaciones, memorándums,
  certificados, permisos y pactos en **una** lectura),
  `GET /solicitudes-permiso` (bandeja de aprobación paginada, la que
  envejece primero) y `GET /asistencia` con rango. Un endpoint y no ocho: el
  file personal es un documento, no ocho. **La nómina exige
  `rrhh.nomina_gestionar`** — restricción nueva: `rrhh.leer` lo tiene el
  supervisor, y que una boleta ya fuera legible por su id no es razón para
  volverla navegable; `nomina_visible` dice cuándo no viajó. 7 tests
  (`tests/test_rrhh_legajo.py`).
- ⬜ **Sin pantalla del legajo**: los endpoints están, el frontend cubre
  contratación y trabajadores. Es el siguiente paso natural.
- ⬜ **Sin listados generales de disciplina y nómina**: `memorandum`,
  `amonestacion`, `acta`, `boleta_pago` y `liquidacion_bss` se listan **por
  trabajador**, no de corrido. Una bandeja "todas las amonestaciones del
  mes" o "las boletas del periodo" necesitaría su propio endpoint; hoy no
  hay quién la pida.
- ✅ 2026-08-05 **El tablero pasó al frontend**: `/rrhh/contratacion`
  dibuja las columnas que `GET /convocatorias/{id}/tablero` ya devolvía.
- ⬜ **Uniforme/EPP (RN-RRHH-014/015)** y **parentesco/relaciones
  (RN-RRHH-016/017)**: sin modelo — hoy son controles manuales/SOP.
- ⬜ **`boleta_pago`/`liquidacion_bss` sin cálculo automático de PLAME**: la
  API recibe `ingresos`/`descuentos`/montos ya calculados (por el contador
  externo) — no hay motor de cálculo de renta 5ta/ONP/AFP/EsSalud en el ERP.
- 🔶 **El centro de labores ya lo consume la asistencia** (2026-08-24,
  ADR-064/065): el pad del local muestra a quienes tienen ahí su centro de
  labores y el aviso de salida sin marcar se atribuye a esa sucursal.
  Siguen sin consumirlo el **contrato laboral** (no lo imprime) y el
  **reemplazo entre sucursales** (RN-RRHH-011, sin modelo).
- ✅ 2026-08-24 **Turno de trabajo y pad de asistencia** (ADR-064, ADR-065,
  migración `c4d17b93e0af`): `turno_sucursal` es la primera entidad de
  **horario laboral** del ERP —el glosario lo nombraba desde el principio y
  nada lo modelaba—, y con ella `tardanza_min` pasa a ser algo que el
  servidor calcula en vez de un número que el cliente informaba. El pad
  (`frontend/app/asistencia/`) se abre con una cuenta de servicio por local y
  cada marcación la firma el PIN del trabajador, contra el mismo lockout del
  login. Barrido horario de salidas sin marcar → aviso al trabajador en su
  campana + `rrhh.salida_sin_marcar` al encargado y a RRHH. **Nunca genera
  horas extra** (RN-RRHH-022).
- ⬜ **Nadie tiene un turno asignado**: el turno de una marcación se **infiere**
  de la hora (`turnos.turno_vigente`). Alcanza para medir tardanza y
  vencimiento, y no alcanza para armar un rol de turnos ni para detectar
  **al que no vino** — sin turno asignado no hay ausencia que reportar, solo
  falta de fila. Es el siguiente paso si RRHH quiere el reporte de
  inasistencias.
- ⬜ **Marcar exige usuario con PIN**: quien no tiene cuenta no puede marcar
  en el pad (409 explícito). Su asistencia la registra RRHH a mano hasta que
  se le vincule una. Crear la cuenta al contratar cerraría el hueco del todo.
  - ✅ 2026-08-25 **la cuenta ya se podía asignar** desde la ficha del
    trabajador — `usuario_id` estaba en `TrabajadorCreate` pero no en
    `TrabajadorUpdate`, y ninguna pantalla lo ofrecía, así que desde la UI
    el campo era NULL para siempre y **nadie** podía marcar.
  - ✅ 2026-08-27 (ADR-070) **reemplazado**: ese mecanismo convivía con
    `usuario.persona_id` (Usuarios → "Persona vinculada") sin sincronizarse
    — vincular desde Usuarios no habilitaba el pad, que es el bug que se
    reportó. `trabajador.usuario_id` dejó de ser columna propia; se deriva
    de `usuario.persona_id`, que es ahora la única arista y se vincula
    únicamente desde Usuarios → Cuentas.
  - ✅ 2026-08-27 (ADR-070) **una cuenta por persona ya se valida en la
    base**: `uq_usuario_persona_viva`, índice único parcial en
    `usuario.persona_id` entre las cuentas vivas.
- ✅ 2026-08-27 (ADR-070) **ya se puede desvincular la persona de una
  cuenta**: `PATCH /users/{id}` pasó a `exclude_unset`, con `persona_id: null`
  explícito como el único campo que borra de verdad — mismo patrón que
  `BORRABLES` en `rrhh.trabajadores`.
- ✅ 2026-08-27 (ADR-070) **`crear_usuario` ya valida la persona**: 404 si no
  existe, 409 si ya tiene otra cuenta.
- ⬜ **Fijar un PIN concreto no tiene pantalla**: `POST /users/{id}/pin` existe
  y nadie lo llama; desde la UI solo se puede resetear al PIN por defecto.
- ⬜ **Los trabajadores que ya existían quedaron sin sucursal**: la migración
  `b6d29f10c47e` es aditiva y nullable, sin backfill — no hay dato del que
  deducir el local. Hay que asignárselos a mano desde RRHH → Trabajadores.
- ✅ 2026-08-28 (ADR-079) **Terminal enrolado y evidencia de marcaje**: el pad
  ya no marca solo con el PIN — exige un `terminal_marcaje` activo de la
  sucursal (RN-RRHH-023) y guarda foto/ubicación/IP de cada toque como
  observación, nunca como condición (RN-RRHH-024). Ver ROADMAP → Módulo
  `rrhh` para el detalle completo.
  - ⬜ **Ningún local tiene un terminal enrolado todavía**: es la migración
    operativa del cambio — hasta que un admin no autorice uno desde
    Organización/RRHH → Terminales, el pad de esa sucursal no marca (403
    en todo intento). No hay backfill posible: no hay tablet física de la
    que derivar el terminal.
  - ⬜ **`FORWARDED_ALLOW_IPS` en producción no incluye al contenedor `web`**:
    el proxy de Next ya reenvía `X-Forwarded-For`, pero la API solo confía
    en el salto si `FORWARDED_ALLOW_IPS` lo declara. Sin ese cambio de
    despliegue, `marcacion.ip` sigue siendo la IP de `web`, no la del local
    — un cambio de configuración, no de código, así que queda fuera de
    este slice.
  - ⬜ **El marcaje sigue sin ser offline**: ADR-009 deja RRHH fuera del
    alcance del hub de sucursal a propósito; un corte de internet bloquea
    el pad igual que antes de este cambio. Llevar `asistencia`/
    `terminal_marcaje`/`marcacion` al hub es un cambio propio si algún día
    pesa.
  - ⬜ **`radio_marcaje_m` no tiene valor sugerido**: cada sucursal lo deja
    en NULL (no evalúa distancia) hasta que alguien lo configure a mano
    desde Organización → Sucursales. No hay un valor por defecto razonable
    para todos los locales — depende de qué tan preciso es el GPS de cada
    tablet en ese punto exacto.
