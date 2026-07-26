# Protección de datos personales (Ley 29733)

Base legal: Ley N° 29733 (Ley de Protección de Datos Personales) y su
reglamento D.S. 016-2024-JUS. Autoridad competente: Autoridad Nacional de
Protección de Datos Personales (ANPD, Ministerio de Justicia).

Este documento es la política técnica interna. El **aviso de privacidad**
público (el texto que ve un cliente/postulante/trabajador al entregar sus
datos) se deriva de acá pero es un documento aparte, de cara al titular —
pendiente de redactar, ver Pendientes.

## Qué datos personales trata el ERP y dónde viven

| Dato | Vive en | Titular | Base legal del tratamiento |
|------|---------|---------|------------------------------|
| Nombre, documento, fecha de nacimiento, domicilio, teléfono, email | `persona` (fuente única — RN-GEN-007) | Trabajador, cliente natural, usuario humano | Ejecución de contrato (laboral, de venta) o consentimiento |
| CV, puesto postulado | `postulante` → `archivo` (S3) | Postulante | Consentimiento previo, informado y expreso (RN-PER-004) |
| Remuneración, régimen previsional, cargo | `trabajador` | Trabajador | Obligación legal (planilla, PLAME) |
| Historial de acciones (login, cambios, pagos) | `audit_log` | Cualquier usuario autenticado | Interés legítimo — seguridad y trazabilidad |
| IP de acceso | `audit_log`, logs de aplicación | Cualquier usuario | Interés legítimo — seguridad |

`persona` es la única tabla con datos identificables "de fondo" —
`trabajador`/`cliente`/`usuario` la referencian por `persona_id` y no
duplican nombre/documento (RN-GEN-007). Esto simplifica el cumplimiento:
casi todo ARCO se resuelve tocando una sola entidad.

**Lo que el ERP NO almacena**: número de tarjeta, CVV o credenciales de
pago (las procesa Izipay directamente, `pago.pasarela` solo guarda la
referencia externa); contraseñas o PIN en texto plano (Argon2id,
`security.md`); historial médico o datos sensibles de salud.

## Derechos ARCO

| Derecho | Cómo se ejerce | Estado |
|---------|-----------------|--------|
| **Acceso** | `GET /api/v1/personas/{id}` | Implementado (slice de auth, 2026-07-25) |
| **Rectificación** | `PATCH /api/v1/personas/{id}` (lock optimista por `version`) | Implementado |
| **Cancelación** | `POST /api/v1/personas/{id}/anonimizar` — anonimización irreversible, no borrado físico | Implementado 2026-07-26 (ADR-011, RN-PER-007) |
| **Oposición** | — | Solo política: hoy no hay procesamiento de marketing automatizado al que oponerse. Se construye cuando exista. |

Los tres primeros exigen el permiso correspondiente (`users.gestionar` para
acceso/rectificación, `personas.anonimizar` — dedicado, más restrictivo —
para cancelación): el titular no accede directo a la API, ejerce su derecho
a través de quien administra el ERP (hoy, el administrador). Un titular
externo (cliente, postulante) solicita por el canal que corresponda
(atención al cliente, RRHH) y el administrador ejecuta la acción.

**Por qué cancelación es anonimización y no `DELETE`**: `persona` la
referencian `trabajador`/`cliente`/`usuario`; un borrado físico rompería
esas relaciones o dejaría planillas/comprobantes sin sustento, y ambos
tienen su propia obligación legal de retención (tributaria, laboral) que
prevalece mientras esté vigente. Ver
[ADR-011](../architecture/adr/ADR-011-derechos-arco-anonimizacion.md) para
el detalle y el checklist manual que debe verificarse antes de anonimizar.

## Plazos de conservación

- **Postulante no contratado**: sin plazo legal fijo en Perú (a diferencia
  del RGPD europeo) — se declara en el aviso de privacidad,
  `postulante.plazo_conservacion_declarado` ya lo modela (RN-PER-004).
- **Trabajador**: mientras dure el vínculo + el plazo de retención laboral/
  tributario tras el cese (planillas, boletas — referencia práctica: 5 años
  para efectos tributarios, confirmar con el contador externo según el
  tributo).
- **Cliente**: mientras haya comprobantes asociados bajo retención
  tributaria; sin comprobantes pendientes, se puede anonimizar a pedido.
- **Logs y `audit_log`**: sin plazo de purga automática todavía — deuda
  técnica (ver Pendientes).

## Medidas de seguridad ya vigentes

No se reconstruyen acá — se referencian, porque ya existen y cubren buena
parte de lo que la ley exige como "medidas de seguridad técnicas y
organizativas":

- **Cifrado en tránsito**: HTTPS obligatorio fuera de local, HSTS en
  producción (`security.md`).
- **Autenticación**: Argon2id para PIN, JWT + refresh rotativo,
  rate limit por IP en login (`security.md`, ADR sin número — slice de
  auth).
- **Control de acceso**: RBAC deny-por-defecto (`authorization.md`).
- **Redacción en logs y reporte de errores**: PIN, tokens, cabeceras
  sensibles nunca se escriben en un log ni se envían a Sentry
  (`send_default_pii=False`) — ADR-006.
- **Auditoría**: `audit_log` inmutable (quién, qué, cuándo, valor
  anterior/nuevo) en toda acción administrativa.
- **Backups**: diarios, con restauración probada, retención de 30 días —
  ADR-007. **Sin cifrar en reposo todavía** (deuda técnica declarada ahí:
  el dump contiene PII en claro).
- **Transferencia internacional**: la base de datos de desarrollo vive en
  Supabase (infraestructura gestionada, revisar región del proyecto);
  producción a definir. Ley 29733 exige que la transferencia
  transfronteriza de datos personales tenga garantías equivalentes — a
  confirmar la región/jurisdicción del proveedor elegido para producción.

## Brecha de seguridad — qué hacer

No hay automatismo (correcto: una alerta de brecha no puede depender de
que el propio sistema comprometido la reporte). Proceso manual mínimo ante
sospecha de acceso no autorizado a datos personales:

1. Confirmar el alcance: qué tabla(s), cuántos titulares, qué campos.
2. Rotar credenciales afectadas (`devops.md` → Rotación de credenciales).
3. Registrar el incidente (fecha, alcance, causa, remediación) — hoy sin
   plantilla propia, usar el mismo criterio que un acta de Gerencia.
4. **Notificar a la ANPD y a los titulares afectados** dentro del plazo que
   exige el reglamento (D.S. 016-2024-JUS) si la brecha compromete datos
   personales — plazo y forma exactos a confirmar con asesoría legal, no
   asumidos acá.

## Pendientes (acción del usuario, no de código)

Ninguno de estos lo puede "ejecutar" el ERP — son pasos administrativos/
legales del titular de la empresa:

- **Registrar el banco de datos personales ante la ANPD** (obligación
  formal bajo Ley 29733/D.S. 016-2024-JUS).
- **Designar responsable/encargado de protección de datos** (rol legal,
  hoy recae de facto en el administrador — confirmar si la ley exige
  designación formal según el volumen de datos tratado).
- **Redactar y publicar el aviso de privacidad** (versión de cara al
  titular de este documento — para clientes en el punto de venta,
  postulantes al aplicar, trabajadores al ingresar).
- **Confirmar plazos de retención exactos con el contador/abogado externo**
  (tributario, laboral) en vez de las referencias prácticas de esta página.
- **Confirmar jurisdicción/garantías de transferencia internacional** del
  proveedor de base de datos de producción.

## Deuda técnica (ver ROADMAP → Deuda técnica → Protección de datos)

- Anonimización no borra el `archivo` (CV en S3) de un `postulante`.
- Sin purga automática de `audit_log`/logs por antigüedad.
- Backups sin cifrar en reposo.
- Sin proceso ni plantilla formal de notificación de brecha.
- `usuario.email` (campo propio, no `persona.email`) no se toca al
  anonimizar la persona asociada.
