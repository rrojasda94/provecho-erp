# Historial — Módulo `delivery`

Estado vigente: ⏳ Pendiente — solo especificación (ADR-098, 2026-09-09):
README, modelo de datos, eventos, reglas de negocio y máquinas de estado
escritos; sin código, sin migración, sin endpoints.

## Cronología

### 2026-09-09 — Especificación del reparto propio (ADR-098)

Se decidió separar el reparto propio de `sales` como módulo nuevo, tal
como preveía `docs/domain/workflows.md` desde 2026-07-27: *"Si el reparto a
domicilio llega a tener ruteo, flota propia y liquidación de repartidores,
se separa entonces como versión MAYOR."* La entidad `entrega` estaba
especificada como "pendiente de slice" en `data-model.md` desde la misma
fecha (ADR-053/054) y documentada como deuda en `docs/roadmap/deuda/
modulo-sales.md`: sin ella, una entrega fallida no se podía registrar.

Alcance acordado con el usuario (MVP completo, no incremental): entidad
`entrega` con trazabilidad de repartidor propio, `ruta_reparto` con varias
paradas optimizadas contra Google Routes (fallback heurístico si Google no
responde), GPS del repartidor durante la ruta, enlace público de
seguimiento con mapa en vivo, aviso automático al cliente por plantillas
de WhatsApp con fallback de enlace copiable, y entrega fallida con motivo
y evidencia fotográfica.

Decisión de integración (ADR-098): `delivery` nunca importa el dominio de
`sales` — avanza la venta a entregada publicando `delivery.entrega_registrada`,
que un listener nuevo de `sales` traduce a la misma
`cumplimiento.registrar_entrega` que ya usa el botón "Entregar" del KDS.
Lee la venta por dos contratos públicos nuevos de `sales`
(`venta_para_reparto`, `ventas_listas_para_reparto`), nunca por join
directo.

Documentación escrita en este slice: README del módulo, ADR-098,
`data-model.md` §6b, filas nuevas en `events.md` (4 eventos propios + 2
consumos de `sales` + 4 contratos públicos de lectura), RN-DLV-001 a 008
en `business-rules.md`, sección "Reparto propio" en `state-machines.md`,
nota de cierre en `workflows.md`, entradas de glosario, filas en
`ROADMAP.md` y `docs/product/modules.md`.

Slices de implementación planeados (ver `docs/roadmap/deuda/modulo-delivery.md`
para lo que queda deliberadamente fuera de cada uno): (2) backend core —
modelos, migración, repartidores/rutas/entregas, listeners con `sales`, 7
registros de activación; (3) ruteo real contra Google, GPS y el enlace
público de seguimiento; (4) PWA del repartidor; (5) tablero de despacho en
el ERP; (6) notificaciones por WhatsApp.
