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
  memorándums, amonestaciones, actas, permisos, pactos y asistencia solo
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
