# ADR-011 — Derechos ARCO sobre `persona`: anonimización, no borrado físico

- Estado: aceptado
- Fecha: 2026-07-26

## Contexto

Ley 29733 (Protección de Datos Personales, Perú) y su reglamento
D.S. 016-2024-JUS exigen que el titular de datos personales pueda ejercer
derechos **ARCO**: Acceso, Rectificación, Cancelación, Oposición. El ERP ya
tenía Acceso y Rectificación de facto (`GET`/`PATCH /api/v1/personas/{id}`,
slice de auth de 2026-07-25). Cancelación no existía.

`persona` es la fuente única de datos de personas naturales (party model,
RN-GEN-007): `trabajador`, `cliente` (natural) y `usuario` (humano) la
referencian por `persona_id`. Un `DELETE` real de `persona` rompería esas
FK, o dejaría planillas (`boleta_pago`), comprobantes (`comprobante`) y
auditoría sin sustento — y en varios casos la ley de protección de datos
choca con otra obligación legal de **retener** (tributaria, laboral), que
prevalece mientras esté vigente.

## Decisión

**Cancelación se implementa como anonimización irreversible**, no
`DELETE`: `POST /api/v1/personas/{id}/anonimizar` (permiso dedicado
`personas.anonimizar`, distinto de `users.gestionar`) sobrescribe
`nombres`, `apellidos`, `numero_documento`, `fecha_nacimiento`,
`domicilio`, `telefono`, `email` con valores no identificables y marca
`persona.anonimizado_at`. La fila y sus relaciones (`trabajador_id`,
`cliente_id`, etc.) permanecen intactas — solo el dato identificable
desaparece.

`numero_documento` es `UNIQUE`: no puede quedar en blanco ni repetirse
entre personas ya ancladas, así que se reemplaza por un valor derivado del
propio `id` (`ANON` + 15 caracteres hex), no por un texto fijo.

**El sistema NO verifica automáticamente** si hay una obligación de
retención vigente en otro módulo (`trabajador.estado=activo`, comprobante
bajo retención tributaria, litigio) antes de anonimizar. Dos razones:
`users` es el módulo más foundational del ERP —`rrhh`, `sales`, `purchases`
importan `Persona`/`Empresa`/`Usuario` directo de él— así que `users`
consultando hacia `rrhh` invertiría esa dirección de dependencia
establecida en todo el código (CLAUDE.md: nunca importar el dominio de otro
módulo). Y muchas obligaciones de retención reales (litigio, acuerdo
informal) no son modelables en una columna de todos modos. Se documenta un
checklist manual en vez de un bloqueo automático:

**Antes de anonimizar, verificar:**
- [ ] `trabajador` ligado, si existe: `estado != activo` (RN-PER-007).
- [ ] Sin comprobantes/documentos tributarios bajo plazo de retención SUNAT
  (Ley del IR: 5 años; Código Tributario puede exigir más).
- [ ] Sin litigio o reclamo abierto que dependa de estos datos.
- [ ] Si la persona fue `postulante`: su ficha de postulante y su
  `cv_archivo_id` (S3) **no** se tocan con este endpoint — ver Consecuencias.

**Auditoría sin re-almacenar la PII**: `audit_log.datos_despues` registra
`{"campos_anonimizados": [...], "motivo": ...}` — deliberadamente **nunca**
el valor real que se borró. Guardar el nombre/documento eliminado en el
propio audit_log dejaría esa PII accesible para siempre, vaciando de
sentido la anonimización.

**Rectificación bloqueada post-anonimización**: `PATCH /personas/{id}`
sobre una persona ya anonimizada devuelve 409 — no hay dato real que
rectificar.

## Consecuencias

- Acceso (RN-PER "leer"), Rectificación (`PATCH`) y ahora Cancelación
  (`POST .../anonimizar`) cubren ARCO salvo **Oposición**, que hoy es una
  cláusula de política (`docs/security/proteccion-datos-personales.md`) sin
  contraparte técnica porque no existe todavía procesamiento de marketing
  automatizado al que oponerse.
- **`postulante` tiene su propio endpoint** (desde 2026-08-01): sus datos no
  viven en `persona` —postular no debe meter a nadie en la fuente única de la
  empresa— así que anonimizar la persona no limpia la ficha del candidato.
  `POST /rrhh/postulantes/{id}/anonimizar` aplica la misma decisión de este
  ADR (anonimizar, no borrar) por una razón distinta: allá el borrado rompía
  FK, acá nada referencia la fila pero se llevaría la evidencia del descarte
  (Ley 26772) y la constancia de la solicitud. Reusa el permiso
  `personas.anonimizar`: misma capacidad legal, mismo custodio, otra tabla.
  Se suma una purga por plazo de conservación
  (`python -m src.modules.rrhh.purga`), que `persona` no tiene ni necesita —
  sus datos están bajo retención tributaria/laboral, no bajo un plazo
  declarado en el aviso de privacidad.
- **`archivo` (CV de `postulante`, S3) no se borra** con este endpoint — el
  módulo de archivos no tiene ni siquiera un flujo de borrado propio hoy.
  El PDF del CV sigue en S3. Deuda técnica declarada, no resuelta acá.
- `usuario.email` (campo propio, fallback de `agente_ia`) no se toca por
  este endpoint — solo `persona.email`. Si el usuario asociado necesita
  también anonimizarse, es una acción separada, no incluida hoy.
- La anonimización es **irreversible por diseño**: no hay "deshacer". Un
  segundo intento sobre la misma persona da 409.
- Permiso dedicado (`personas.anonimizar`) en vez de reusar
  `users.gestionar`: alguien con CRUD normal de personas no puede disparar
  una acción irreversible sin que se le otorgue explícitamente.

## Alternativas descartadas

- **`DELETE` físico de `persona`** — descartado: rompe FK activas
  (`trabajador`, `cliente`, `usuario`) y borraría el sustento de planillas y
  comprobantes ya emitidos, que otra ley obliga a retener.
- **Soft-delete (`deleted_at`) como "cancelación"** — descartado: el dato
  identificable seguiría en la fila, solo oculto de las consultas normales.
  No satisface el derecho de cancelación, que exige que el dato deje de
  existir de forma identificable, no que se archive.
- **Bloqueo automático cross-módulo** (`users` consultando `rrhh` antes de
  anonimizar) — descartado: invertiría la dirección de dependencia que todo
  el código ya asume (`rrhh`/`sales`/`purchases` importan de `users`, nunca
  al revés). Se documenta como checklist manual en su lugar.
- **Guardar el valor anterior en `audit_log.datos_antes`** (patrón que usan
  otras acciones auditadas) — descartado específicamente para esta acción:
  haría que el propio mecanismo de auditoría preservara para siempre el
  dato que la ley exige borrar.
