# Historial — Módulo `production`

Estado vigente: 🔶 En curso — slice core de orden de producción implementado en código (2026-07-25) por adelanto a pedido del usuario, pero la primera cocina de producción real sigue planeada para 2027 y "producción sigue parqueada" en el plano de infraestructura (decisión 2026-08-05, que se refiere al *entorno* productivo, no al módulo).

## Cronología

### 2026-07-20 — Área Producción: cronograma, calidad, inocuidad e inventario de cocina

Documentación del área Producción a partir de la descripción de alcance
dada por el usuario: elaboración de subrecetas/procesamiento de insumos
por lotes, área metódica con foco fuerte en inocuidad y calidad (de ahí
depende gran parte de la calidad del producto final), responsable de la
cocina de producción y su mantenimiento, produce según cronograma +
necesidades de la empresa/almacén, da soporte a I+D+i/Comercial para
nuevo producto y mejora continua, e inventario propio similar al de
cocina de sucursal. Roles: cocinero, jefe de cocina.

Antes de modelar se resolvieron 2 decisiones reales con el usuario:

1. **Alcance temporal**: `domain-model.md` ya documentaba que la primera
   cocina de producción recién está planeada para 2027 — hoy la
   producción se hace en cocinas de sucursal. El usuario confirmó que
   esta sesión documenta **spec a futuro** (diseño/preparación), no un
   área operando hoy; la cocina de sucursal actual sigue bajo
   Operaciones/RRHH sin cambio.
2. **No conformidad de calidad**: se evalúa si el lote es corregible
   (reproceso) o no (desecho); en ambos casos se genera un
   `reporte_escalamiento` (reutiliza el patrón ya definido para
   atención al cliente); el desecho exige evidencia de destrucción
   (foto/video + testigo) para prevenir sustracción disfrazada de merma.
3. **Cronograma**: plan fijo por tipo de receta/proceso (evita
   contaminación cruzada) + ajuste por necesidad urgente de Almacén
   Central — no es puramente reactivo.

Incorporado:
- `docs/produccion/` (nuevo): `README.md` (mapa de responsabilidades),
  `politica-produccion.md` (cronograma, calidad/no conformidad, inocuidad
  referida a RN-CDP-*, inventario de cocina, soporte a I+D+i),
  `perfiles/` (jefe de cocina, cocinero de producción).
- `docs/diagrams/Procesos/Produccion/` (área nueva): 4 SOPs —
  `Planificacion/` (plan de producción, cronograma fijo + ajuste),
  `Calidad-Inocuidad/` (control de calidad y no conformidad, checklist de
  inocuidad de turno), `Inventario-Cocina/` (conteo cíclico de cocina de
  producción), `Soporte-IDI/` (soporte técnico a nuevo producto/mejora
  continua).
- `docs/templates/produccion/` — 5 plantillas: orden de producción,
  reporte de producción, ficha de no conformidad, checklist de inocuidad,
  reporte de conteo de cocina. Nuevo producto reutiliza la ficha ya
  existente de Comercial (no se duplica).
- `business-rules.md` — nueva sección "Producción — cronograma, calidad
  y cocina": RN-PRD-011 a RN-PRD-017 (plan de producción, agrupación por
  tipo de receta, control de calidad, no conformidad→escalamiento,
  evidencia de destrucción, inventario de cocina, viabilidad técnica
  antes de comprometer lanzamiento).
- `data-model.md` §7 — nueva entidad `plan_produccion`; `orden_produccion`
  ampliada con `plan_produccion_id` y `control_calidad_resultado`;
  `reporte_escalamiento` ampliado con origen `produccion` y motivo
  `no_conformidad_calidad` + `evidencia_id`.
- `workflows.md` — placeholder "Producción (si existe)" reemplazado por
  narrativa + Mermaid real; `PROC-PRD-001` v0.1→v1.0 (sigue Borrador:
  spec completa, sin operación real hasta 2027).
- `process-nomenclature.md` — registro maestro actualizado.
- `glossary.md` — término **Jefe de Cocina (Producción)** agregado a
  Actores.
- `events.md` — nuevo evento `production.no_conformidad_detectada`.
- **`src/modules/production/README.md`** (nuevo, spec técnica) — módulo
  backend `production` especificado conforme a este flujo.
- `00_PROJECT.md` — entrada `produccion/` y `templates/produccion/` en el
  mapa.

Pendiente (declarado, no bloquea): frecuencia exacta de cronograma y de
conteo cíclico de cocina (quedan `[[ COMPLETAR ]]`, a definir con
Gerencia/Contabilidad al diseñar la primera cocina de producción);
criterios técnicos de aceptación/rechazo de calidad por receta (a definir
con Producción/I+D+i cuando exista personal del área).

**Ajuste de costeo, desperdicio e inocuidad (mismo día, 2026-07-20):** el
usuario detalló 4 puntos que faltaban en la primera pasada:

1. El desperdicio de un insumo no es un número único: cada insumo puede
   tener más de un tipo de desperdicio (ej. tomate → pulpa aprovechable,
   más cáscara y semilla como desperdicio) y cada tipo tiene su propio
   peso real. `orden-produccion.md` pasa de un campo libre a una tabla
   insumo/tipo de desperdicio/peso.
2. El ERP debe calcular el **costo real** del producto aprovechable
   sumando el costo de insumos (el insumo completo comprado, no solo la
   parte aprovechable) más horas-hombre — nunca a mano.
3. Ningún documento de conteo se llena a mano: `reporte-conteo-cocina.md`
   pasa de plantilla rellenable a documento autogenerado por el ERP, el
   jefe de cocina solo visa — mismo principio que ya regía
   `reporte-produccion.md`, ahora explícito para evitar error humano de
   transcripción.
4. Parte de la inocuidad es revisar que los equipos de frío estén en
   rango de temperatura; fuera de rango, reporte automático a Gerencia
   (mismo criterio que la falla de frío en apertura de sucursal,
   RN-SUC-009).

Incorporado: RN-PRD-018 (costeo automático) y RN-CDP-005 (equipos de
frío) en `business-rules.md`; `receta_item.tipo_desperdicio`,
`consumo_produccion_item` y `checklist_inocuidad_turno` nuevas en
`data-model.md` §7; `orden_produccion` ampliada con costeo
(horas_hombre, costo_insumos, costo_mano_obra, costo_real_unitario);
evento `production.equipo_frio_fuera_rango` en `events.md`; plantillas
`orden-produccion.md` (tabla de desperdicio + costeo), `reporte-conteo-cocina.md`
(autogenerado) y `checklist-inocuidad.md` (tabla de equipos de frío)
reescritas; SOPs `plan-produccion-cronograma.md`,
`checklist-inocuidad-cocina.md` y `conteo-ciclico-cocina-produccion.md`
actualizados; perfiles de jefe de cocina y cocinero ajustados.

*(ROADMAP.md línea 34, mismo día)*: Producción: procesos y plantillas
(cronograma, calidad/no conformidad, inocuidad, inventario de cocina,
soporte a I+D+i) | ✅ 2026-07-20 | `docs/produccion/`, 4 SOPs, 5
plantillas — ver detalle abajo. Spec a futuro: primera cocina de
producción planeada 2027, hoy sin operación real. Módulo backend
`production` — slice core implementado 2026-07-25

### 2026-07-27 — Decisión de nomenclatura: "Producción" queda reservada a la cocina central

Del cierre del pendiente "Cumplimiento de pedido — PROC-OPE-002" (Área
Operaciones, cocina de sucursal): se decidió que Preparación y
Despacho/Entrega de sucursal son etapas internas de UN solo proceso, y
explícitamente **no** se llaman "Producción" para no chocar con el
módulo:

> (3) "Producción" ya nombra la cocina de producción central
> (`PROC-PRD-001`, primera cocina 2027) — reusarlo para la cocina de
> sucursal rompe la regla de que la sigla nombra un área real.

Registrado también en la sección de "Pendientes de decisión" resuelta
ese mismo día:

> ✅ 2026-07-27 Cumplimiento de pedido: **UN** proceso — `PROC-OPE-002`
> (área Operaciones), con Preparación y Despacho/Entrega como etapas
> internas, no dos procesos. Razones: un solo resultado (entra Orden de
> Pedido, sale pedido entregado) sin artefacto de traspaso; la máquina de
> estados ya implementada (`venta_item.estado_preparacion`) es una sola y
> las pantallas KDS `preparacion`/`despacho` son vistas de ella;
> "Producción" ya nombra la cocina de producción central
> (`PROC-PRD-001`, 2027) y reusarlo rompía la nomenclatura. Desbloquea
> `sales.venta_entregada` y `marketing.encuesta_enviada`; se separa como
> v2.0 si el reparto llega a [tener ruteo, flota y liquidación propios].

Referencia de secuencia de desarrollo (sección vieja "Orden sugerido de
desarrollo", sin fecha propia, previa a estas decisiones):

> 7. Producción, contabilidad, RRHH, resto de módulos.

### 2026-07-25 — Slice core del módulo `production` implementado en código

Fila de la tabla de Fundaciones (F0):

> Producción (fabricación) | 🔶 slice core ✅ 2026-07-25 | Orden de
> producción ad-hoc (crear → registrar consumo → completar con resultado
> de control de calidad) y costeo automático. Construido antes de tiempo
> a pedido del usuario — primera cocina real sigue planeada 2027.
> `receta.articulo_id` nuevo liga receta↔subreceta. Diferido: ver Deuda
> técnica.

## Estado vigente

**Estado vigente:** 🔶 En curso. El módulo `production` tiene un slice
core en código desde 2026-07-25 (orden de producción ad-hoc con consumo,
control de calidad y costeo automático; `receta.articulo_id` liga
receta↔subreceta — esto es la receta de **fabricación** de un artículo
producido, distinta de la "receta" de venta de `sales`), construido antes
de tiempo a pedido explícito del usuario. La documentación de área
(cronograma, calidad/no conformidad, inocuidad, inventario de cocina,
soporte a I+D+i) es **spec a futuro**: la primera cocina de producción
central real sigue planeada para 2027, y hoy la producción efectiva pasa
por las cocinas de sucursal (proceso `PROC-OPE-002`, deliberadamente NO
llamado "Producción" para no chocar con el nombre del módulo/área). La
decisión "Producción sigue parqueada" (2026-08-05) que aparece en
`ROADMAP.md` **no es sobre este módulo**: es sobre el entorno de
despliegue productivo (dominio real, backups on-premise, stack de
observabilidad) y se descartó de este historial por tratarse de un falso
positivo de la palabra "producción". Los pendientes de desarrollo del
módulo (8 ítems, 1 con severidad alta) viven en
`docs/roadmap/deuda/modulo-production.md`.

## Fuentes

- ROADMAP.md línea 27 (tabla F0): fila "Producción (fabricación)" — slice
  core ✅ 2026-07-25, orden de producción ad-hoc, costeo automático,
  `receta.articulo_id`.
- ROADMAP.md línea 34 (tabla F0): fila "Producción: procesos y
  plantillas" — ✅ 2026-07-20, `docs/produccion/`, 4 SOPs, 5 plantillas.
- ROADMAP.md líneas 452-457: "Pendientes de decisión" resuelta el
  2026-07-27 sobre Cumplimiento de pedido / nomenclatura de "Producción".
- ROADMAP.md líneas 600: índice de Deuda técnica — referencia a
  `docs/roadmap/deuda/modulo-production.md` (8 pendientes, 1 alto) —
  citada como puntero, no copiada.
- ROADMAP.md líneas 1108-1210: sección completa "Área Producción —
  cronograma, calidad, inocuidad e inventario de cocina (2026-07-20)" —
  contenido principal de este historial, transcrito verbatim.
- ROADMAP.md líneas 1351-1371 (dentro de "Cumplimiento de pedido —
  PROC-OPE-002 (2026-07-27)"): decisión y razones de por qué la cocina de
  sucursal no se llama "Producción".
- ROADMAP.md línea 1413: lista de "Orden sugerido de desarrollo" —
  referencia de secuencia, sin fecha propia.

Líneas revisadas y **descartadas** por no ser del módulo `production`
(solo contienen la palabra "producto"/"producción" en otro dominio):
líneas 10, 18, 21, 23, 45-49 (línea 47 es sobre endurecimiento del
*entorno* productivo, no del módulo), 68-373 (parches de PDV, promociones
y catálogo — todas usan "producto" en el sentido de artículo de venta o
"producción" como entorno de despliegue), 483-487 (Comercial/RRHH, palabra
"produce" sin relación), 563-572 (decisión "Producción sigue parqueada"
2026-08-05 es sobre infraestructura/despliegue, no sobre el módulo),
705-709 y 913-978 (documentación de Comercial que solo menciona a
Producción como área colaboradora, sin contenido propio del módulo),
1028-1034 (lista de entidades de catálogo comercial).
