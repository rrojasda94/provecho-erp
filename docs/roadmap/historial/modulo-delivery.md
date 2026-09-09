# Historial — Módulo `delivery`

Estado vigente: 🔶 En curso — slice core implementado (2026-09-09,
ADR-098): repartidores propios, tablero de despacho y el ciclo completo de
una ruta (crear con ruteo heurístico, editar paradas, iniciar, entregar o
fallar cada parada, reintentar o cerrar la fallida, finalizar o cancelar
la ruta), con la convergencia por evento hacia y desde `sales` en los dos
sentidos. Falta ruteo real contra Google Routes, GPS de flota, el enlace
público de seguimiento y el aviso automático por WhatsApp (ver
`docs/roadmap/deuda/modulo-delivery.md`).

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

### 2026-09-09 — Slice core: repartidores, tablero y ciclo de ruta/entrega

Backend del slice 2 completo: cuatro tablas (`repartidor`, `ruta_reparto`,
`entrega`, `posicion_repartidor` — esta última sin uso todavía, reservada
para el GPS del slice siguiente), migración `69f4ca1d58f4` generada por
autogenerate y verificada con `alembic check` + ciclo `downgrade base` /
`upgrade head` contra Postgres real.

Los dos contratos de lectura de `sales` (`venta_para_reparto`,
`ventas_listas_para_reparto`) y de `rrhh` (`trabajadores_con_cuenta`,
`cuenta_de_trabajador`) quedaron implementados tal como los especificó
ADR-098. La convergencia por evento funciona en los dos sentidos:
`sales/application/listeners.py` ganó `session_factory` y un handler de
`delivery.entrega_registrada` que llama a la misma
`cumplimiento.registrar_entrega` del botón "Entregar" del KDS;
`delivery/application/listeners.py` escucha `sales.venta_entregada` (cierra
una entrega abierta si el KDS se adelantó) y `sales.venta_anulada`
(RN-DLV-006).

Decisión de implementación no anticipada en el ADR: el ruteo se apoya en
`Coordenada` de `shared/integrations/google` en vez de un tipo propio —
son el mismo punto (lat, lng), y así el slice de ruteo real no tiene que
traducir nada al conectar `computeRoutes`. También se prefirió mapear
"dirección sin anclar" y demás violaciones de RN-DLV a `ReglaNegocio`
(409), no a un 422 aparte: es el mismo criterio HTTP que ya usa el resto
del ERP para una regla de negocio (422 queda reservado para lo que
rechaza Pydantic antes de llegar al caso de uso).

Colisión de nombre resuelta antes de exportar el contrato: el schema
`EntregaOut` de `delivery` chocaba con el ya existente de `sales`
(la respuesta de `POST /sales/ventas/{id}/entrega`); se renombró a
`EntregaRepartoOut` en vez de dejar que FastAPI recalifique el de `sales`
con su ruta completa — mover el nombre de un contrato ya publicado es más
disruptivo que nombrar bien el nuevo.

Pruebas: `tests/test_delivery_rules.py` (18 casos, dominio puro) y
`tests/test_delivery.py` (23 casos de integración vía `TestClient`,
incluida la cadena completa iniciar → entregar → `sales.venta_entregada`,
y el camino inverso KDS → cierra la entrega de `delivery`). Suite completa
verde en SQLite (2453 pruebas), `ruff` limpio, `alembic check` sin
diferencias, contrato OpenAPI regenerado.
