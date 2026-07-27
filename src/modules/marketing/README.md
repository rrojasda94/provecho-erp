# Módulo `marketing` — Marca, contenido y campañas

**Estado (2026-07-22):** spec técnica, sin implementación. Resuelve el
pendiente "módulo `marketing`: README/contrato propio" del ROADMAP.
Documentado por dependencia: `sales` atribuye ventas a leads de campaña.

## Objetivo

Gestionar el crecimiento de marca: campañas con objetivo medible,
contenido pertinente a la marca, naming, material en sucursal, y la
atribución lead→venta en conjunto con `sales`/Comercial.

## Entidades

`campana` (tipo, objetivo, público, canal, presupuesto, KPI, estado,
aprobación gerencial si sobre umbral), `pieza_contenido` (calendario,
pertinencia y uso de marca validados), `lead` (canal, atribución a
`venta_id`), `implementacion_material_sucursal` (verificación en sitio).
`encuesta_satisfaccion` pertenece a este módulo (spec en
`docs/architecture/data-model.md` §6 y §8d). Su disparador es
`sales.venta_entregada`, que emite `PROC-OPE-002` (Cumplimiento de
pedido) desde 2026-07-27 — el hecho que faltaba para que la encuesta
pudiera construirse. Marketing elige a qué venta entregada enviarle
encuesta (selectiva, RN-COM-007) y al enviarla emite
`marketing.encuesta_enviada`.

`contrato` (transversal) y las compras de material/agencia (`purchases`)
no se duplican aquí — Marketing las usa.

## Casos de uso

- Crear campaña con brief; no pasa de `brief` a `aprobada` sin objetivo,
  público, presupuesto y KPI (RN-MKT-003); gasto fuera del presupuesto
  anual o sobre el límite genera una `decision_gerencial` (RN-GER-007/003).
- Planificar calendario de contenido; publicar solo piezas marcadas
  pertinentes y con uso de marca validado (RN-MKT-001/002).
- Definir/validar naming de producto o campaña (RN-MKT-007).
- Registrar leads de campaña y atribuirlos a la venta real cuando
  Comercial cierra (mide conversión, no solo alcance).
- Verificar la implementación de material en cada sucursal —producto
  nuevo y clásico— (RN-MKT-005).
- Evaluar propuesta de agencia vs. interna contra objetivo y presupuesto
  (RN-MKT-006) — Marketing evalúa, Gerencia valida; se formaliza por
  `contrato` y paga Contabilidad, la agencia (servicio) no pasa por
  `purchases`.

## Reglas

- Sin brief aprobado, la campaña no sale a canal (RN-MKT-003).
- Contenido no pertinente a la marca no se publica, aunque sea viral
  (RN-MKT-002).
- Marketing no modifica la identidad de la marca (reservado, RN-MAR-004);
  solo asegura su buen uso (RN-MKT-001).
- El **material** (bien) se adquiere vía `purchases`, no por fuera
  (RN-MKT-004); la **agencia** (servicio) la evalúa Marketing y la valida
  Gerencia, vía `contrato` + Contabilidad, no `purchases` (RN-MKT-006).
- Enviar material no cierra la tarea: se verifica la implementación en
  sucursal (RN-MKT-005).

## Flujo

Objetivo (con Comercial si es venta) → brief aprobado → (naming + uso de
marca validados) → material vía Compras + agencia evaluada → lanzamiento →
leads registrados → atribución lead→venta con `sales` → cierre y medición.

## Relaciones

- Escucha: `sales.venta_confirmada` (atribuye la venta a un `lead` cuando
  aplica).
- Publica: `marketing.campana_lanzada` (informativo/BI),
  `marketing.lead_generado` (consumido por `sales` para la atribución
  lead→venta).
- Coordina (no vía evento): `purchases` (material/agencia), `production`
  (disponibilidad de producto nuevo, RN-CML-005), `accounting`
  (presupuesto), Gerencia (aprobación sobre umbral).
