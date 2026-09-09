# ADR-098: El reparto propio es un módulo y avanza la venta por eventos

## Estado

Aceptado (2026-09-09)

## Contexto

`sales` cubre el pedido delivery hasta que sale de cocina: cotiza el reparto
por kilómetro (ADR-054/068) y ancla la dirección al mapa (ADR-053/072), y
`cumplimiento.registrar_entrega` marca la venta entregada
(`sales.venta_entregada`). Lo que falta es enteramente operativo — quién
lleva el pedido, en qué salida, en qué orden, por dónde va, si llegó o
falló y por qué, con evidencia — y `docs/domain/workflows.md` ya lo
anticipaba: *"Si el reparto a domicilio llega a tener ruteo, flota propia y
liquidación de repartidores, se separa entonces como versión MAYOR"*
(línea 320 antes de este ADR).

La entidad `entrega` está especificada desde 2026-08 en
`docs/architecture/data-model.md` como "pendiente de slice" y documentada
como deuda en `docs/roadmap/deuda/modulo-sales.md`: *"Hoy una entrega
fallida no se puede registrar: solo se marca el pedido entregado o no se
marca nada."*

Construir ruteo, GPS de flota y un enlace público de seguimiento dentro de
`sales` metería en un módulo de ventas responsabilidades que no son venta:
posición de un repartidor, cálculo de rutas contra Google, retención de
datos de ubicación, notificación asíncrona por WhatsApp. `sales` seguiría
creciendo en una dirección que ya se declaró aparte.

`tests/test_arquitectura.py` exige que un módulo solo importe de otro su
`api.deps` o `application.queries_publicas`: ningún módulo puede llamar
directo al dominio de otro. Eso obliga a decidir *cómo* un módulo nuevo hace
avanzar una venta sin tocar `sales.domain` ni `sales.infrastructure`.

## Decisión

### 1. `delivery` es un módulo nuevo, no una rama de `sales`

Dueño de `repartidor`, `ruta_reparto`, `entrega` y `posicion_repartidor`.
Sigue la estructura estándar (`docs/engineering/module-guide.md`,
referencia `purchases`): `domain/`, `application/`, `infrastructure/`,
`api/`.

### 2. La venta se marca entregada por evento, nunca por import

`delivery` no importa `sales.application.cumplimiento`. Al registrar una
entrega, `delivery` publica `delivery.entrega_registrada`
(`{entrega_id, venta_id, sucursal_id, ruta_id, repartidor_id,
repartidor_usuario_id, fecha_entrega}`); un listener nuevo de `sales`
(`sales/application/listeners.py`, hoy sin `session_factory` porque solo
encolaba Celery) escucha ese evento y llama a
`cumplimiento.registrar_entrega(session, venta_id, entregado_por=...)` —
la misma función que ya usa el botón "Entregar" del KDS, ya idempotente
(RN-CUP-005).

El camino inverso también existe: `delivery` escucha `sales.venta_entregada`
para cerrar una `entrega` abierta si el despacho marcó la venta entregada
desde el KDS en vez de desde el tablero de reparto. Los dos caminos
convergen en el mismo estado sin que ninguno conozca el dominio del otro.

Costo aceptado: la entrega es best-effort en proceso (ADR-016) — si el
commit del listener de `sales` falla, el de `delivery` ya ocurrió y la
venta queda temporalmente sin marcar. Se documenta en `events.md`, mismo
trato que el resto de los eventos internos.

### 3. `delivery` lee la venta por contrato público, no por join directo

`sales/application/queries_publicas.py` gana `venta_para_reparto` y
`ventas_listas_para_reparto`: son la única superficie por la que `delivery`
sabe qué pedidos existen, su dirección/coordenadas, su cliente y si están
listos. `sales.pedido_listo` no se enriquece ni se consume — el tablero de
reparto resuelve "listos sin asignar" con una consulta activa, no con un
evento pasivo, así un pedido que cambia a delivery después de estar listo
también aparece.

### 4. Ruteo y notificación quedan detrás de los adaptadores existentes

El cálculo de ruta usa `src/shared/integrations/google/rutas.py`
(`ruta_optima`, nueva función junto a `distancia_km`), con la misma
doctrina de ADR-054: la clave que calcula la ruta no sale del servidor. El
aviso al cliente usa `src/shared/integrations/whatsapp` con el mismo patrón
de tarea Celery que `marketing` (plantilla, ventana de 24 h, reintento solo
en fallo de transporte).

## Consecuencias

- `sales` no crece con ruteo, GPS ni mensajería — sigue siendo el dueño de
  la venta y nada más.
- Quitar `delivery` completo (desregistrar sus 7 puntos de activación) deja
  a `sales` funcionando exactamente como hoy: el pedido llega a `listo` y se
  entrega manualmente desde el KDS, sin rastro de repartidor. Ningún dato de
  `sales` depende de que `delivery` exista.
- Todo dato de reparto (posición, ruta, motivo de fallo, evidencia) puede
  auditarse y purgarse con sus propias reglas de retención sin tocar el
  histórico de ventas.
- El costo es un salto de proceso más para cerrar una entrega (evento en
  vez de llamada directa) y dos contratos de lectura nuevos que `sales`
  debe mantener estables.
