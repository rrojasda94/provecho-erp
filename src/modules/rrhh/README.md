# Módulo `rrhh` — Recursos Humanos

## Objetivo

Gestionar el ciclo de vida laboral del trabajador: vínculo, cargo, cese,
documentos internos (memorándum, amonestación, boleta de pago) y demás
procesos de `docs/rrhh/`.

## Estado de implementación (2026-07-20)

Módulo abierto **parcialmente** como dependencia del slice de datos de
Venta: se necesitaba `trabajador` para el ranking de ventas por
trabajador (`venta.usuario_id` → `trabajador.usuario_id`). Solo esa
entidad está modelada — el resto de este README describe el alcance
completo de §8b, pendiente del slice dedicado de RRHH.

## Entidades

`trabajador` (implementado — `src/modules/rrhh/infrastructure/models/`),
`postulante`, `socio`, `contrato_laboral`, `boleta_pago`, `memorandum`,
`amonestacion`, `acta`, `certificado_trabajo`, `liquidacion_bss`,
`solicitud_permiso`, `pacto_permanencia`, `asistencia` (pendientes).
Detalle en `docs/architecture/data-model.md` §8b.

## Casos de uso

Ver `docs/rrhh/README.md` (flujo de 13 pasos de incorporación) y los SOPs
en `docs/diagrams/Procesos/Recursos-Humanos/`. Sin casos de uso de API
implementados todavía — el módulo solo expone el modelo de datos mínimo.

## Reglas

RN-RRHH-* en `docs/domain/business-rules.md`. `registra_asistencia`
siempre `false` si `tipo_vinculo=locacion_servicios` (RN-PER-002) —
válida en el dominio, no a nivel de esquema.

## Relaciones

- `trabajador.usuario_id` (opcional) liga con `users.usuario` — un
  trabajador puede o no tener usuario de login.
- Consumido por `sales` para el ranking de ventas por trabajador
  (`tests/test_venta_slice.py`).
