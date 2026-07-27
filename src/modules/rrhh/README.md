# Módulo `rrhh` — Recursos Humanos

## Objetivo

Gestionar el ciclo de vida laboral del trabajador: vínculo, contrato, cese,
nómina, documentos internos (memorándum, amonestación, boleta de pago,
certificado de trabajo) y demás procesos de `docs/rrhh/`.

## Estado de implementación (2026-07-25)

Slice completo: las 13 entidades de §8b implementadas con sus 4 capas
(domain/application/infrastructure/api). `trabajador` existía desde el slice
de ventas (solo el modelo, sin casos de uso) — este slice le agrega
`application/trabajadores.py` y completa el resto.

## Entidades

`trabajador`, `contrato_laboral`, `postulante`, `socio`, `boleta_pago`,
`liquidacion_bss`, `memorandum`, `amonestacion`, `acta`,
`certificado_trabajo`, `solicitud_permiso`, `pacto_permanencia`,
`asistencia`. Detalle en `docs/architecture/data-model.md` §8b.

`contrato_laboral` y `solicitud_permiso` se modelan directo en `rrhh` (no
como entidad transversal `contrato`/`solicitud` en `src/shared/`) — no había
precedente de esas entidades genéricas en código; mismo diferimiento que
`purchases` hizo con `cotizacion`. Ver ROADMAP si otro módulo necesita la
versión genérica.

## Casos de uso

- **`application/trabajadores.py`**: crear (valida RN-PER-002: locación de
  servicios nunca registra asistencia; RN-PER-001: subvención de
  practicante), actualizar, cesar, listar.
- **`application/contratos.py`**: crear (borrador) → firmar → finalizar
  (RN-RRHH-012, RN-CTR-004).
- **`application/postulantes.py`**: crear (exige `consentimiento_datos`,
  RN-PER-004), cambiar estado del proceso de selección.
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
RN-PER-001/002/004, RN-RRHH-002/003/005/006/009/012. El resto (RN-RRHH-007
visado de abogado, RN-RRHH-013 convocatoria sin perfil, RN-RRHH-014..018
uniforme/parentesco/relaciones/confidencialidad) queda como
documentación/proceso — no hay entidad propia en §8b para esas reglas
todavía (ver ROADMAP → Deuda técnica → Módulo rrhh).

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
- `trabajador.persona_id`/`postulante.persona_id`/`socio.persona_id` ligan
  con `users.persona` (party model, RN-GEN-007) — nombres/documento nunca
  se duplican aquí.
- `postulante.cv_archivo_id` liga con `shared.archivo`.
- Consumido por `sales` para el ranking de ventas por trabajador
  (`tests/test_venta_slice.py`).
