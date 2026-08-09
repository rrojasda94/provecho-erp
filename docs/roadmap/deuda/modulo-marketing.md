# Deuda técnica — Módulo marketing (slice core — deuda declarada)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-08-01 **Slice core**: `campana` (brief → aprobada → en_curso →
  cerrada, RN-MKT-003), `pieza_contenido` (RN-MKT-001/002),
  `lead` con atribución a la venta, `implementacion_material_sucursal`
  (RN-MKT-005) y `encuesta_satisfaccion` (RN-COM-007). Migración
  `e9c3b7412a68`, 17 endpoints, `tests/test_marketing.py`.
- ⬜ **`campana.aprobada_por` apunta a `usuario`, no a `decision_gerencial`**:
  RN-GER-007 exige acta de Gerencia cuando el gasto sale del presupuesto
  anual o supera el límite, pero ni `presupuesto_anual` ni
  `decision_gerencial` existen como tablas. Hoy la aprobación es un permiso
  (`marketing.campana_aprobar`, que el rol `marketing` NO tiene) sin control
  contra presupuesto. Se cierra junto con el slice de Gerencia.
- ⬜ **`campana.objetivo_comercial_id` diferido**: enlaza campaña de impulso
  de venta con la meta comercial; `objetivo_comercial`/`meta_venta` no
  existen todavía (deuda del área Comercial).
- ✅ 2026-08-08 **Slice encuesta / agencia / métricas** (migración
  `c1f80b6a2d34`, ADR-031 y ADR-030). Cierra cuatro de las deudas de abajo:
  - **Envío real de la encuesta, con guion por nodos.** `encuesta_plantilla`
    + `encuesta_pregunta` convierten el cuestionario en dato: cada pregunta
    declara a dónde sigue la conversación (`siguiente_codigo`) y por dónde se
    desvía según la respuesta (`saltos`), así un 2 de 5 pregunta **qué**
    falló y un 5 pregunta si nos recomendaría. `encuesta_satisfaccion` pasa a
    recordar en qué nodo está el cliente, y `encuesta_respuesta` guarda el
    detalle. Nuevo adaptador `src/shared/integrations/whatsapp/` (Cloud API
    de Meta) + webhook público con firma HMAC + enlace público con token.
    Saltos rotos y **ciclos** se rechazan al guardar la plantilla, no a mitad
    de conversación. **Expiración automática** por Celery beat cada hora.
  - **Calendario de contenido con adjuntos.** `GET /piezas/calendario`
    agrupa por día y cuenta el arte; los adjuntos cuelgan de `archivo`
    (`src/shared/`, polimórfico) en vez de un storage propio.
  - **Evaluación de agencia (RN-MKT-006).** `evaluacion_agencia` +
    `opcion_agencia` con criterios ponderados congelados **antes** de ver las
    propuestas, la opción interna obligada a competir, y dos permisos
    distintos para evaluar y decidir.
  - **Los eventos de marketing ya tienen consumidor: marketing.**
    `campana_metrica` acumula leads, conversiones, piezas y satisfacción; la
    satisfacción se acredita por la cadena lead → venta → encuesta.
  - Efecto colateral saneado: los tres `event_bus.publish` del módulo iban
    sin `session=`, o sea despachaban **antes** del commit (contra ADR-016);
    y `errors.py` dejó su jerarquía propia para heredar de
    `src/shared/errors.py`, lo que borró el `try/except … raise _http(e)`
    repetido en 17 endpoints.
- ⬜ **Frontend de lo nuevo**: el backend expone calendario con adjuntos,
  guion de encuesta, evaluación de agencia y métricas; `frontend/app/(app)/
  marketing/` sigue mostrando solo campañas y el listado plano de contenido.
- ⬜ **La plantilla de encuesta no se edita, se reemplaza**: hay
  `POST /encuestas/plantillas` y activación, no `PATCH`. Editar un guion con
  encuestas en curso obligaría a versionarlo (una conversación a mitad de
  camino apunta a nodos que podrían desaparecer); mientras tanto, se crea
  una plantilla nueva y se activa.
- ⬜ **El acuse de entrega de WhatsApp se ignora**: el webhook descarta los
  `statuses` (enviado/entregado/leído). Guardarlos permitiría distinguir "no
  contestó" de "nunca le llegó" mejor que `error_envio`.
