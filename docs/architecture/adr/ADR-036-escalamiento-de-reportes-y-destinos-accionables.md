# ADR-036 — Escalamiento de un reporte y destinos accionables

- Estado: aceptado
- Fecha: 2026-08-09

## Contexto

ADR-033 puso el módulo `reports` en pie: los hechos del ERP se emiten, se
distribuyen y se guardan. Lo que quedó fue un reporte que **cuenta y no sirve
para nada más**. Concretamente, y verificado sobre el código de la rama
anterior:

- `reporte_emitido` guardaba `referencia_tipo` + `referencia_id` desde el
  primer día, el schema los mandaba al cliente (`frontend/lib/reports.ts`) y
  **ningún componente los renderizaba**. Cero enlaces en todo el módulo.
- `GET /reports/emitidos/{id}` devolvía `datos` y `entregas`, y **el frontend
  nunca lo llamaba**. No existía la ruta `/reportes/emitidos/[id]`.
- No había **quién**: `reporte_emitido` no tenía columna de actor, y solo 5 de
  ~50 eventos del bus llevaban `usuario_id`. «Ajuste de inventario fuera de
  margen» no decía a quién preguntarle.
- No había **dónde exacto**: `emision._ubicar()` resolvía el `almacen_id` para
  elegir destinatarios y lo descartaba al persistir.
- No había **a quién elevar**: `reporte_escalamiento` estaba especificado en
  `data-model.md` §6 y exigido por RN-CTP-004 y RN-PRD-014, y ADR-033 lo
  declaró deuda. El ERP tampoco tiene jerarquía organizacional donde leerlo.
- De los nueve `referencia_tipo` del catálogo, **ocho endpoints de detalle no
  existían** (los ajustes de inventario no tenían ni siquiera un listado) y
  siete pantallas tampoco.
- El tablero de consulta (ADR-024) tenía el mismo problema: `consumos_omitidos`,
  `disponible_negativo`, `salidas_sin_lote` y `pedidos_demorados` son listas de
  problemas cuyas filas no llevaban a ninguna parte — las cuatro
  `queries_publicas` ni siquiera proyectaban el id de la entidad.

## Decisión

**El reporte deja de ser una línea de texto: dice quién y dónde, lleva al
lugar donde se actúa, y se puede elevar dejando rastro.**

### 1. El reporte dice quién lo provocó y en qué almacén

`reporte_emitido` gana `actor_id` y `almacen_id`, ambas nullable y sin
backfill. `Emision` gana `clave_actor`: qué campo del payload es el actor.

`clave_actor` vacío significa **el hecho lo detecta el sistema** y el actor
queda nulo: la API lo muestra como «Sistema» (RN-REP-009). El caso testigo es
`sales.pedido_demorado`, que nace de un barrido de Celery.

**Alternativa descartada: usar `venta.usuario_id` (el mozo) como actor de
`pedido_demorado`.** El actor de un reporte es quien provocó el hecho, y el
hecho es «el pedido siguió en cocina pasado el umbral», no «alguien tomó el
pedido». Poner ahí al mozo convierte un aviso de proceso en una acusación, y
encima contra quien no tiene la culpa. El responsable operativo ya es el
**destinatario** (`encargado_de_turno`), que es donde corresponde.

**Sin backfill, a propósito.** Un reporte de agosto no puede decir quién lo
provocó porque el dato nunca se guardó. Dirá «Sistema». Inventarle un actor a
una fila vieja sería peor que dejarla sin él.

### 2. Un mapa de destinos en `src/core/destinos.py`

`referencia_tipo` → `(ruta del endpoint, permiso del módulo dueño, etiqueta)`.

**Vive en `core` porque lo leen dos consumidores que no pueden verse entre
sí**: `modules/reports/api` (para el reporte emitido) y `core/reportes` (para
las filas del tablero). Ponerlo en `reports/domain` lo dejaría fuera del
alcance de `core/reportes`, y ponerlo en `shared` lo dejaría fuera del alcance
de `reports.domain` — las dos barreras están congeladas en
`tests/test_arquitectura.py`. `core` es la única capa que los dos pueden leer.

El permiso es el **del módulo dueño**, igual que en el catálogo de emisiones:
ser destinatario no da acceso al dato (RN-REP-002), así que el cliente esconde
el botón que llevaría a un 403. La única excepción es `escalamiento`, cuya
entidad es de `reports`.

**Rutas de API, no de pantalla.** El backend no conoce el router de Next.js; la
traducción a ruta de UI vive en `frontend/lib/destinos.ts`. El permiso **no** se
duplica: viaja en `GET /reports/emisiones` y el cliente lo consulta.

`tests/test_destinos.py` congela dos cosas: que todo `referencia_tipo` del
catálogo tenga entrada, y que **toda ruta corresponda a un endpoint realmente
montado** en `create_app()`. Un rename de endpoint rompe el enlace en CI y no
en producción (RN-REP-010).

### 3. Ocho endpoints nuevos para cerrar el 9/9

`GET` de detalle para `articulo`, `sku`, `lote`, `categoria` y `ajuste` (más el
listado de ajustes, que no existía) en `inventory`; `cierres/{id}` y
`pagos-proveedor/{id}` en `accounting`. Todos con el permiso del módulo dueño y
el `exigir_*` de su `application/scope.py`. `exigir_sku` es nuevo y hereda el
tenant de su artículo, igual que `exigir_lote`.

### 4. `reporte_escalamiento` vive en `reports`, no en `shared`

`data-model.md` §6 decía `shared`. **Se contradice a propósito**, y esta es la
parte del ADR que más importa registrar.

El criterio de `shared` es «sin dueño de módulo»: `decision_gerencial` está ahí
porque la escriben purchases, marketing y rrhh y ninguno la posee.
`reporte_escalamiento` tiene **un solo escritor y un solo lector**. Esa línea de
`data-model.md` se escribió el 2026-07-20, cuatro meses antes de que el módulo
existiera.

Además la lógica **no puede** vivir en `shared`: abrir y elevar necesitan
`Area`, `AreaMiembro`, `destinatarios.*` y `emision.emitir()`, y
`test_shared_no_depende_de_ningun_modulo` lo prohíbe. Poner el modelo en
`shared` y el caso de uso en `reports` parte una entidad en dos capas sin ganar
un solo consumidor.

**Alternativa descartada: dejarla en `shared` con `origen_tipo`/`origen_id`
polimórficos** (patrón de `decision_gerencial`). Pierde la integridad
referencial contra el reporte —que es justo el historial que se quiere
consultar— y la lógica sigue viviendo en `reports` igual.

### 5. El escalamiento ancla al reporte, no a la venta

El spec hablaba de `venta_id | carrito_id | orden_produccion_id`. **No se
modelan como columnas.** Son exactamente lo que `referencia_tipo` +
`referencia_id` ya guardan, para los nueve tipos y no para tres; `carrito` ni
siquiera existe como tabla (`sales/infrastructure/models/__init__.py` lo declara
diferido); y anclar a la venta perdería la foto `datos`, el `nivel`, el
`actor_id` y la doble puerta de RN-REP-002.

`origen` sí se guarda —es el eje del SOP de mejora continua del área
Comercial— pero se **deriva** del reporte al abrir, en `domain/escalamiento.py`.
Pedírselo a quien eleva es hacerle repetir un dato que el ERP ya tiene, con la
chance de que lo repita mal.

La FK es `ondelete="RESTRICT"`, deliberadamente distinta del `CASCADE` de
`entrega_reporte`: el reporte es la evidencia de la cadena.

### 6. A quién elevar, sin jerarquía organizacional

El ERP no tiene `supervisor_id`, ni `jefe_id`, ni nivel de rol. El escalón se
resuelve con lo que sí existe (`catalogo.DESTINO_POR_NIVEL`):

| `nivel_actual` | Destinatario |
|---|---|
| `supervisor` | dinámico `encargado_de_turno` (respaldo: roles `supervisor`/`admin`) |
| `comercial` | área `comercial` |
| `gerencia` | área `gerencia` |

`supervisor → encargado_de_turno` es RN-CTP-004 al pie de la letra («un
supervisor **o encargado de sucursal**»).

**Riesgo aceptado y visible: el seeder pone el rol `supervisor` dentro del área
Comercial**, así que elevar de supervisor a comercial puede caer en la misma
persona. Es la organización real de hoy, no un bug del código. El diseño lo
**muestra** —`POST …/elevar` devuelve `destinatarios`, y vacío se dibuja como
«no llegó a nadie»— en vez de bloquear la elevación y esconderlo.

El resolutor `responsables_del_nivel` recibe el nivel por un kwarg `contexto`
nuevo de `destinatarios.resolver()`, que `emitir()` alimenta con **la proyección
ya recortada por la whitelist**: un resolutor dinámico nunca ve más de lo que la
emisión declaró, así la garantía de RN-REP-003 se extiende sola.

### 7. Tres emisiones nuevas, con ámbito `empresa`

`reports.escalamiento_abierto`, `_elevado` y `_resuelto`. Se publican al bus y
el listener genérico las recoge sin una línea de código nueva; el seeder les
crea su regla porque itera el catálogo. No hay recursión: emitir un reporte no
abre un escalamiento.

Ámbito `empresa` y no `sucursal` porque un escalamiento puede nacer de un hecho
sin local (un pago sobre umbral). El `sucursal_id` viaja igual en `campos` y de
ahí lo lee el resolutor para encontrar al encargado de turno.

Son las únicas emisiones cuyo permiso empieza con `reports.` — y con razón: el
hecho **es** de reports. No es una segunda matriz de permisos.

### 8. `Columna.enlace` en el tablero de consulta

`core/reportes/catalogo.Columna` gana `enlace` y `TIPOS_COLUMNA` gana `"id"`.
El id se declara **como una columna más**, así pasa por el mismo whitelist de
`ejecutar()` sin excepciones que después haya que recordar. La columna
`tipo="id"` no se dibuja: es el ancla del enlace de la fila.

**Solo los cuatro reportes de problemas**, a propósito: `pedidos_demorados`,
`consumos_omitidos`, `disponible_negativo` y `salidas_sin_lote`. Cada fila suya
es un registro sobre el que hay que actuar. Los agregados (`ventas_por_dia`,
`compras_por_proveedor`) no tienen a qué apuntar: el total de un martes no es un
registro. No es una omisión.

## Consecuencias

- Un reporte se abre y dice qué pasó, quién lo provocó, dónde, con qué datos, a
  quién le llegó y por qué, y lleva de un click al lugar donde se resuelve.
- La campana **navega** al reporte además de marcarlo leído. Antes decía que
  algo pasó y había que salir a buscarlo a mano.
- Los ajustes de inventario tienen pantalla por primera vez: se aprueban y se
  rechazan desde ahí.
- RN-CTP-004 y RN-PRD-014 dejan de ser deuda.
- **Los reportes anteriores a esta rama dicen «Sistema»** aunque los haya
  provocado alguien. Es el costo de no inventar el dato.
- **Solo se puede escalar lo que el catálogo cerrado emite.** Los motivos
  `queja`, `error_sistema` y `desistimiento_no_resuelto` de RN-CTP-004 se pueden
  elegir, pero nadie publica hoy «un cliente se quejó»: haría falta una emisión
  `sales.queja_registrada` con endpoint de alta, que contradice el «no hay
  `POST /emitidos`» de ADR-033. Queda como deuda declarada, con el problema
  nombrado, en `docs/roadmap/deuda/modulo-sales.md`.
- **Los índices parciales y los CHECK solo se validan de verdad contra
  Postgres.** El suite corre sobre SQLite; el criterio de aceptación es
  `alembic check` limpio en el job `migraciones` del CI.

## Alternativas descartadas

Además de las tres ya argumentadas arriba (tabla en `shared`, `venta_id` como
columna, el mozo como actor de `pedido_demorado`):

- **Cruzar `audit_log` para resolver el actor en vez de ampliar payloads.** No
  hace falta tocar eventos, pero `audit_log` solo registra actos de autoridad y
  de plata: la mayoría de los hechos reportados no están ahí, y el cruce por
  `(entidad, entidad_id)` sería una heurística que falla en silencio.
- **Una tabla `accion_reporte` genérica en vez de la cadena de niveles.** Más
  simple, pero no contesta «a quién elevar», que es la mitad del pedido, y deja
  RN-CTP-004 sin implementar igual.
- **Filtrar la lista destino al registro del reporte en vez de subirlo al
  tope.** El contexto de alrededor —qué más hay pendiente en ese almacén, en esa
  caja— suele ser parte de la decisión.

## Referencias

- ADR-033 (módulo `reports`), ADR-024 (catálogo cerrado de consulta),
  ADR-031 (`audit_log`), ADR-016 (eventos post-commit), ADR-004 (tenant)
- RN-CTP-004, RN-PRD-014/015, RN-REP-001..014
- `docs/architecture/data-model.md` §6 y §16
