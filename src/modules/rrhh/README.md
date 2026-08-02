# Módulo `rrhh` — Recursos Humanos

## Objetivo

Gestionar el ciclo de vida laboral del trabajador: vínculo, contrato, cese,
nómina, documentos internos (memorándum, amonestación, boleta de pago,
certificado de trabajo) y demás procesos de `docs/rrhh/`.

## Estado de implementación

**2026-07-25** — slice del ciclo laboral: las 13 entidades de §8b con sus 4
capas (domain/application/infrastructure/api). `trabajador` existía desde el
slice de ventas (solo el modelo, sin casos de uso); ese slice le agregó
`application/trabajadores.py` y completó el resto.

**2026-08-01** — slice de contratación: `convocatoria` + el tablero que va de
la postulación recibida al fin del periodo de prueba.

## Entidades

`convocatoria`, `trabajador`, `contrato_laboral`, `postulante`, `socio`,
`boleta_pago`, `liquidacion_bss`, `memorandum`, `amonestacion`, `acta`,
`certificado_trabajo`, `solicitud_permiso`, `pacto_permanencia`,
`asistencia`. Detalle en `docs/architecture/data-model.md` §8b.

## Tablero de contratación

Los 13 pasos de `docs/rrhh/README.md` se manejan como **un solo tablero** por
convocatoria (`GET /rrhh/convocatorias/{id}/tablero`, columnas en orden):

```
recibido → preseleccionado → entrevistado → verificado → oferta_enviada
         → contratado → inducido → confirmado          (· descartado)
```

La ficha es el `postulante` y es el expediente de la búsqueda: no se cierra al
firmar el contrato sino al pasar el periodo de prueba. Se avanza de a una
columna (`POST /postulantes/{id}/avanzar`) — sin saltos ni retrocesos, porque
el historial del proceso es la defensa ante un reclamo de discriminación
(Ley 26772); descartar exige motivo escrito.

`contratado` no se alcanza avanzando: `POST /postulantes/{id}/contratar` crea
la `persona` y el `trabajador` en el mismo paso (o reusa la `persona` del
ex-trabajador recontratado). **El candidato no vive en `persona` mientras es
candidato**: el pool es gente ajena a la empresa y la mayoría nunca entra;
sus datos viven en su propia ficha con `respuestas` JSONB del formulario.

Contratar exige `rrhh.trabajador_gestionar`, no el permiso de postulante: ahí
nace la planilla. Publicar/cerrar una convocatoria exige
`rrhh.convocatoria_gestionar` (el administrador aprueba, el encargado pide).

## Formulario público de postulación

`POST /rrhh/postulaciones/{token}` — **sin JWT**. El token lo genera
`publicar_convocatoria` y desaparece al cerrarla: es lo único que autoriza a
escribir y solo puede crear un postulante de esa convocatoria. Protegido con
rate limit por IP (20/hora), campos acotados y consentimiento obligatorio
(RN-PER-004). La fecha de postulación la pone el servidor, no el cliente —
si no, se podría postular fuera de la fecha límite.

El formulario en sí es **Google Forms** (gratis, conocido por el candidato,
sin nada que hospedar); un Apps Script de ~12 líneas reenvía cada respuesta a
ese endpoint. El script y su configuración están en el SOP
[publicacion-convocatoria](../../../docs/diagrams/Procesos/Recursos-Humanos/Reclutamiento/publicacion-convocatoria.md).

## Datos personales del candidato (Ley 29733)

El candidato no está en `persona`, así que su ARCO no pasa por
`/personas/{id}`: tiene el suyo sobre la ficha — `GET`, `PATCH` y
`POST /rrhh/postulantes/{id}/anonimizar` (irreversible, permiso
`personas.anonimizar`). Se anonimiza en vez de borrar aunque nada referencie
la fila: el borrado se llevaría `motivo_descarte` y `canal_origen`, la
evidencia de por qué se descartó a alguien. Por eso **el motivo de descarte
se escribe como criterio, nunca con datos personales** — sobrevive a la
anonimización.

Cada ficha nace con `plazo_conservacion_declarado`
(`RRHH_PLAZO_CONSERVACION_POSTULANTE_MESES`, 12 por defecto) y
`python -m src.modules.rrhh.purga` anonimiza lo vencido desde el cron; nunca
al contratado, cuya retención es laboral. Detalle en
[proteccion-datos-personales.md](../../../docs/security/proteccion-datos-personales.md).

`contrato_laboral` y `solicitud_permiso` se modelan directo en `rrhh` (no
como entidad transversal `contrato`/`solicitud` en `src/shared/`) — no había
precedente de esas entidades genéricas en código; mismo diferimiento que
`purchases` hizo con `cotizacion`. Ver ROADMAP si otro módulo necesita la
versión genérica.

## Casos de uso

- **`application/convocatorias.py`**: crear (requisición aprobada, borrador) →
  publicar (RN-RRHH-013: exige `perfil_puesto`, genera el token público) →
  cerrar (retira el token); `tablero()` agrupa los postulantes por columna.
- **`application/postulantes.py`**: `recibir_postulacion` (formulario público
  por token), `crear_postulante` (referido o carga manual),
  `avanzar_postulante`, `descartar_postulante` (motivo obligatorio) y
  `contratar_postulante` (crea `persona` + `trabajador`).
- **`application/privacidad.py`**: derechos ARCO sobre `postulante` (Ley
  29733, ADR-011) — `anonimizar_postulante` (irreversible; 409 si ya se
  contrató: su ARCO se ejerce sobre `persona`) y
  `purgar_postulantes_vencidos`, que aplica el
  `plazo_conservacion_declarado`. El comando de cron es
  `python -m src.modules.rrhh.purga`.
- **`application/trabajadores.py`**: crear (valida RN-PER-002: locación de
  servicios nunca registra asistencia; RN-PER-001: subvención de
  practicante), actualizar, cesar, listar.
- **`application/contratos.py`**: crear (borrador) → firmar → finalizar
  (RN-RRHH-012, RN-CTR-004).
- **`application/socios.py`**: CRUD de participación societaria.
- **`application/nomina.py`**: `emitir_boleta_pago` y `liquidar_cese` —
  idempotentes por `idempotency_key` (dinero, CLAUDE.md), calculan
  `dentro_de_plazo` contra las 48h de RN-RRHH-002/003.
- **`application/disciplina.py`**: emitir memorándum, amonestación, acta,
  certificado de trabajo (RN-RRHH-002/004/007).
- **`application/permisos.py`**: `solicitud_permiso` crear → aprobar/
  rechazar (RN-RRHH-005, máquina de estados pendiente→aprobada/rechazada).
- **`application/capacitacion.py`**: `pacto_permanencia` — crear y calcular
  reembolso proporcional al tiempo de permanencia no cumplido (RN-RRHH-006).
- **`application/asistencia.py`**: marcar entrada/salida; bloqueado
  (`ReglaNegocio`) si `trabajador.registra_asistencia=false` (RN-PER-002).

Casos de uso base en `docs/rrhh/README.md` (flujo de 13 pasos de
incorporación) y SOPs en `docs/diagrams/Procesos/Recursos-Humanos/`.

## Reglas

RN-RRHH-*, RN-CTR-*, RN-PER-* en `docs/domain/business-rules.md`. Aplicadas
en código (`domain/rules.py` + validación en `application/`):
RN-PER-001/002/004, RN-RRHH-002/003/005/006/009/012/013. El resto (RN-RRHH-007
visado de abogado, RN-RRHH-014..018
uniforme/parentesco/relaciones/confidencialidad) queda como
documentación/proceso — no hay entidad propia en §8b para esas reglas
todavía (ver ROADMAP → Deuda técnica → Módulo rrhh). De RN-RRHH-013 se aplica
la mitad verificable por software (sin perfil no se publica); que el aviso no
tenga requisitos discriminatorios lo revisa una persona, con el SOP en mano.

## Eventos

Publicados, **sin listener cruzado todavía** (mismo estado en que nació
`trabajador` sin capa `application/`): `rrhh.trabajador_cesado`,
`rrhh.contrato_laboral_firmado`, `rrhh.boleta_pago_emitida`,
`rrhh.liquidacion_bss_pagada`, `rrhh.solicitud_permiso_aprobada`,
`rrhh.amonestacion_emitida`. Candidatos a futuro enganche: `accounting`
podría generar asiento al escuchar `boleta_pago_emitida`/
`liquidacion_bss_pagada`; `users` podría desactivar el `usuario` ligado al
escuchar `trabajador_cesado`. Ver ROADMAP.

## Relaciones

- `trabajador.usuario_id` (opcional) liga con `users.usuario` — un
  trabajador puede o no tener usuario de login.
- `trabajador.persona_id`/`socio.persona_id` ligan con `users.persona` (party
  model, RN-GEN-007) — nombres/documento nunca se duplican aquí.
- `postulante.persona_id`/`trabajador_id` son **nulos mientras es candidato** y
  se llenan al contratar; `postulante.convocatoria_id` es nulo si la
  postulación fue espontánea o por referido, fuera de una búsqueda abierta.
- `postulante.cv_archivo_id` liga con `shared.archivo`.
- `convocatoria.sucursal_id` (opcional) indica dónde se necesita cubrir.
- Consumido por `sales` para el ranking de ventas por trabajador
  (`tests/test_venta_slice.py`).
