# Deuda técnica — Protección de datos personales (tras la implementación de 2026-07-26 — ADR-011)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-08-01 **ARCO de postulante** (migración `b1d09e574c23`): los datos
  del candidato viven en `postulante`, no en `persona` —postular no mete a
  nadie en la fuente única de la empresa— así que
  `POST /personas/{id}/anonimizar` no lo alcanzaba. Ahora tiene los cuatro
  derechos: acceso (`GET /rrhh/postulantes/{id}`), rectificación (`PATCH`,
  409 sobre una ficha ya anonimizada), cancelación
  (`POST /rrhh/postulantes/{id}/anonimizar` — irreversible, reusa el permiso
  `personas.anonimizar` por ser la misma capacidad legal y el mismo
  custodio) y oposición (sigue siendo solo política, igual que en `persona`).
  Se anonimiza en vez de borrar aunque **nada referencie la fila**: el
  borrado se llevaría `motivo_descarte` y `canal_origen`, o sea la evidencia
  de por qué se descartó a alguien (Ley 26772) y la constancia de que la
  solicitud existió. Contratado → 409: sus datos ya están en `persona` bajo
  retención laboral y su ARCO se ejerce allá.
  **Purga por plazo**: `python -m src.modules.rrhh.purga` (cron del host,
  mismo criterio que backups) anonimiza lo vencido y nunca lo contratado; el
  plazo ahora se declara solo al crear la ficha
  (`RRHH_PLAZO_CONSERVACION_POSTULANTE_MESES`, 12 por defecto) porque un
  plazo NULL volvía la ficha inpurgable y el aviso de privacidad prometía
  algo que nadie aplicaba. Tests: `tests/test_rrhh_arco_postulante.py`.
- ⬜ **La purga no está dada de alta en ningún cron todavía** (ver
  *Cuando haya servidor*, punto 6): el comando
  existe y está probado, pero hasta que corra en el servidor el plazo sigue
  sin aplicarse en la práctica. Va junto con el cron de backups cuando exista
  el VPS.
- ⬜ **Borrado del `archivo` (CV) en `postulante`**: anonimizar la persona
  no toca el PDF en S3 — el módulo de archivos no tiene ni siquiera un
  flujo de borrado propio hoy.
- ⬜ **Purga de `audit_log`/logs por antigüedad**: sin retención automática
  todavía.
- ⬜ **Cifrado de backups en reposo**: el dump contiene PII en claro (ya
  declarado en la deuda de Backups, repetido acá por relevancia).
- ⬜ **Proceso y plantilla formal de notificación de brecha**: hoy es una
  lista de pasos en prosa, sin plantilla ni plazo confirmado con asesoría
  legal.
- ⬜ **`usuario.email` no se anonimiza** junto con `persona.email` — son
  campos independientes; si hace falta, es una acción aparte.
- ⬜ **Oposición** (cuarto derecho ARCO): sin contraparte técnica porque no
  existe procesamiento de marketing automatizado todavía. Construir cuando
  `marketing` tenga código real.
- ⬜ **Auto-servicio del titular**: hoy ARCO se ejerce a través del
  administrador (permiso `personas.anonimizar`/`users.gestionar`), no por
  un portal donde el propio titular pida su acceso/cancelación.
