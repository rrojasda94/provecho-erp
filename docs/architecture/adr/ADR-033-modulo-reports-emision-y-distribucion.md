# ADR-033 — Módulo `reports`: emisión y distribución, con el catálogo cerrado

- Estado: aceptado
- Fecha: 2026-08-08

## Contexto

El ERP publica **52 eventos** desde ocho módulos. Antes de este cambio,
**cuatro** llegaban a una persona (`sales.pedido_demorado`,
`inventory.stock_bajo_minimo`, `inventory.lote_vencido_detectado`,
`inventory.conteo_vencido`), por código cableado en
`users/application/listeners.py`. A quién le llegaban lo decidían dos
funciones fijas de `users/application/notificaciones.py`, cuyo propio
docstring declaraba el hueco:

> **El punto de configuración futuro está en `destinatarios_de_sucursal`.**
> Hoy la regla es fija —encargado de turno, con supervisores como respaldo—
> porque una tabla de preferencias sin nadie que la administre es un
> formulario más y el mismo resultado.

Consecuencias medibles:

- **No había forma de ver el mapa.** Nadie podía responder «¿a quién le llega
  un descuadre de caja?» sin leer Python.
- **No había forma de cambiarlo sin un deploy.**
- **Las reglas de negocio que exigen reportes dirigidos estaban sin
  implementar**: RN-CTP-004 (escalamiento → supervisor), RN-INV-020
  (devolución → almacén o comercial), RN-INV-021 (conteo vencido → almacén y
  gerencia), RN-PRD-009 (cambio de receta → reporte).
- **El ERP ya publicaba el destino y nadie lo consumía**:
  `inventory.conteo_vencido` manda `dirigido_a: ["almacen", "gerencia"]` y
  `devolucion.reporte_dirigido_a` guarda `almacen`|`comercial`. Eran cadenas
  sin nadie del otro lado.
- `ROADMAP.md` tenía `| Notificaciones | ⬜ | Celery + canales por definir |`.

## Decisión

**Un módulo `reports` que es dueño de la emisión y la distribución**, con la
misma disciplina de catálogo cerrado que ADR-024 aplicó a la consulta.

### Por qué es un módulo, si ADR-024 dijo que no

ADR-024 descartó un módulo `reportes` con este argumento textual:

> el motor no tiene dominio propio, solo ensambla `queries_publicas` ajenas.

**Era cierto para el motor de consulta y es falso para la distribución.** Son
dos cosas distintas y conviene decirlo de una vez:

| | `src/core/reportes/` (ADR-024) | `src/modules/reports/` (este ADR) |
|---|---|---|
| Disparo | El usuario pide (**pull**) | Pasa un hecho (**push**) |
| Estado propio | Ninguno (salvo el tablero, que es preferencia) | Áreas, reglas, emisiones, entregas |
| Reglas propias | Ninguna: compone contratos ajenos | Resolución de destinatarios, precedencia, no-retroactividad |
| Resultado | Una tabla calculada al momento | Una fila guardada y repartida |

La distribución tiene estado y reglas, así que paga los siete registros de
alta de `module-guide.md`. ADR-024 **no se revierte**: su motor sigue donde
está y su razonamiento sigue siendo correcto para lo que decidía.

Los nombres conviven a un carácter de distancia y por eso se dicen acá:
`reportes` (español) es el motor de consulta; `reports` (inglés, como todos
los módulos) es emisión y distribución.

### El catálogo de emisiones es cerrado, y en código

`domain/catalogo.py` declara las trece emisiones: código, permiso del módulo
dueño, whitelist de campos, plantilla de título, nivel, ámbito y áreas
sugeridas. **No es una tabla.** Mismo motivo que ADR-024, trasladado de la
lectura a la escritura: si el conjunto de emisiones fuera administrable por
API, quien puede crear reglas podría hacerse enviar cualquier cosa que pase
por el bus, y el RBAC dejaría de aplicar en cuanto el cliente escribe la
definición.

Lo que **sí** es administrable es a quién llega cada emisión. Esa es
exactamente la línea: *la regla configura destinatarios, nunca datos.*

`codigo` **es** el nombre del evento. Tener dos identificadores para el mismo
hecho solo agrega una tabla de traducción que se desincroniza; si un día un
evento tuviera que producir dos reportes distintos, son dos reglas sobre la
misma emisión.

### Las seis entidades

`area` + `area_miembro` (roles y/o personas, opcionalmente acotadas a una
sucursal) · `regla_distribucion` + `regla_destinatario` (el gobierno) ·
`reporte_emitido` + `entrega_reporte` (el rastro). Detalle en
`docs/architecture/data-model.md` §16.

**El área no es un rol.** Un rol dice qué puede hacer alguien; un área dice de
qué se tiene que enterar. Se parecen tanto que la tentación es fusionarlos, y
no coinciden: `gerencia`, `comercial` y `almacen` no son roles del RBAC, y un
área se compone de varios roles más personas puntuales. Se compone
principalmente **por rol** porque así se administra solo — alguien cambia de
puesto y gana o pierde los reportes sin que nadie actualice una lista, y quien
cesa deja de recibirlos al perder el rol (mismo criterio que el addendum de
ADR-024 para compartir tableros).

### La cadena de entrega, y por qué tiene dos saltos

```
evento del módulo → reports.listeners → ReporteEmitido + EntregaReporte
                                      → publica reports.reporte_emitido
                                      → users.listeners → Notificacion
```

`reports` **no importa `notificacion`**: publica y `users` la llena. El salto
extra compra que el usuario siga teniendo **una sola campana** y que `users`
siga siendo dueño de su bandeja. Ambos saltos son post-commit (ADR-016) y
cada listener abre su propia sesión.

Por lo mismo, **`entrega_reporte` no lleva `leida_at`**: el estado de lectura
ya vive en `notificacion.leida_at`, que es la bandeja que el usuario abre.
Duplicarlo daría dos verdades sobre el mismo hecho y se separarían en la
primera entrega que falle a medias. La entrega registra la *distribución* —a
quién le tocó y **por qué**—, que es el dato de gobierno que no existía en
ningún lado.

### Decisiones menores, con su motivo

- **La regla de la sucursal le gana a la general** (RN-REP-008). Si aplicaran
  las dos, quien esté en ambas recibiría el mismo hecho dos veces. Se
  implementa con **dos índices únicos parciales** y no con un
  `UniqueConstraint` de tres columnas: en SQL los NULL son distintos entre sí,
  así que la constraint simple dejaría convivir dos reglas generales.
- **Las entregas no son retroactivas** (RN-REP-004). `reporte_emitido.regla_id`
  y `entrega_reporte.motivo` se congelan al emitir. Cambiar la distribución
  mañana no puede reescribir a quién le llegó ayer — mismo criterio que
  `pedidos_demorados` guardando el umbral vigente al alertar.
- **Una emisión sin destinatarios se persiste igual** (RN-REP-005), con cero
  entregas, y sale como **hueco** en la matriz. Antes era un `log.warning` que
  nadie leía. Un aviso que no llegó a nadie es información de gestión, no un
  no-evento.
- **La matriz muestra huecos y fugas, no solo lo configurado.** Una matriz que
  solo lista reglas se ve completa siempre; lo que el administrador necesita
  ver es lo que falta. *Fuga* = regla activa que hoy no resuelve a nadie.
- **El alcance no cuenta los resolutores dinámicos.** Quién está de turno
  depende del momento; estimarlo sería inventar un número que cambia solo.
- **`reports.leer_matriz` es un permiso aparte de `reports.leer`.** El mapa
  revela la estructura organizacional —quién responde por qué local, quién
  compone Gerencia— y eso es más de lo que necesita quien viene a leer sus
  reportes. **`reports.administrar` queda solo en `admin`**, por lo mismo que
  `purchases.aprobar`: cambiar a quién le llega un descuadre es una decisión
  de gobierno, no de turno.
- **No hay `POST /emitidos`.** El reporte lo emite el evento, no un cliente —
  mismo criterio que ADR-031 para `audit_log`: un endpoint de escritura le
  permitiría al reportado dictar lo que dice su reporte.
- **El gobierno se audita con `shared.auditoria`, no con un historial propio**
  (RN-REP-007). «Ver si hay modificaciones en los flujos» se responde con
  `GET /api/v1/auditoria?entidad=regla_distribucion`. Un segundo historial en
  paralelo sería una tabla más que mantener y otra que se desincroniza.
- **Tres payloads ganaron un campo** (aditivo, permitido por `events.md`):
  `accounting.cierre_caja_irregular` += `sucursal_id`,
  `accounting.pago_requiere_aprobacion` += `empresa_id`,
  `production.no_conformidad_detectada` += `almacen_id`. Sin ellos el hecho no
  se puede atribuir a un tenant y el reporte no se puede escopar.

### Seguridad

1. **Catálogo cerrado**: ningún identificador de tabla o columna llega del
   cliente. `codigo_emision` se valida contra el catálogo al guardar.
2. **Doble puerta de lectura** (RN-REP-002): ser destinatario (o tener
   `reports.leer_todo`) **y** tener el permiso que la emisión declara, que es
   el de su módulo dueño. Estar en la lista de distribución no otorga acceso
   al dato — un cocinero puede recibir el aviso de que hubo un descuadre y no
   ver el detalle de la caja.
3. **Whitelist de campos** (RN-REP-003): `reporte_emitido.datos` solo guarda
   lo que la emisión declara. Un payload que traiga de más no se filtra al
   cliente por olvido de nadie.
4. **Tenant en toda consulta**; áreas, reglas y destinatarios dentro de la
   propia empresa (RN-REP-006). Un reporte que no se pudo atribuir a una
   empresa solo lo ve el superusuario, igual que las filas sin tenant de
   `audit_log`.
5. **Un reporte ajeno responde 404, no 403**: la respuesta no confirma su
   existencia.
6. **`datos` puede traer PII** (Ley 29733) y por eso no sale al logger —
   mismo criterio que `audit_log.datos_antes/despues`.

## Consecuencias

- `users/application/listeners.py` pasa de cuatro handlers a uno.
  `notificaciones.py` pierde la decisión de destinatarios y queda como lo que
  su docstring siempre dijo que era: bandeja.
- `users.application.queries_publicas` gana `permisos_de(session, usuario_id)`
  — contrato público para filtrar listas por permiso (lo usa el catálogo de
  emisiones, como `core/reportes` usa el suyo).
- El seeder crea seis áreas y una regla general por emisión, con la
  distribución que estaba cableada. **Sin eso el módulo arrancaría con trece
  huecos**: los hechos ocurrirían y no le llegarían a nadie.
- `reports` se vuelve pieza caliente: cada evento del catálogo pasa por su
  listener. El bus ya aísla fallas (`try/except` por handler, ADR-016) y la
  entrega sigue siendo best-effort, igual que antes.
- **Efecto colateral**: sembrar 12 filas más de `rol_permiso` (97 → 109) cruzó
  el umbral de paginación del sync y destapó un bug latente en
  `core/sync/serializacion.marca_de`, que devolvía marcas *naive* mientras el
  resto del motor trabaja en UTC *aware*. El camino de pull multi-página nunca
  se había ejercitado. Corregido en el mismo cambio.
- **Deuda declarada**: `reporte_escalamiento` (RN-CTP-004) sigue sin modelar —
  la cadena supervisor → comercial → gerencia necesita estado y acciones
  propias, no solo distribución. Tampoco están: adjuntar un reporte del
  catálogo de `core/reportes` a una emisión, canales de transporte más allá de
  la bandeja (el campo `canal` ya está), y digest en vez de una entrega por
  hecho.

## Alternativas descartadas

- **Dejarlo en `users`, agregando una tabla de preferencias.** Es lo que el
  docstring anticipaba, y no alcanza: la distribución tiene seis entidades y
  reglas propias. Metida en `users`, ese módulo pasa a ser dueño de la
  autenticación, la organización, el RBAC **y** el gobierno de la información.
- **Absorber `core/reportes` dentro del módulo.** Un solo lugar llamado
  Reportes es tentador, pero contradice ADR-024 por escrito sin ganar nada: el
  motor de consulta sigue sin tener dominio propio. Se mantienen separados y
  el ADR nombra la diferencia para que nadie los confunda.
- **Área = rol del RBAC.** Cero tablas nuevas y se administra solo, pero
  fuerza a que cada área sea un rol, y `almacen`/`gerencia`/`comercial` no lo
  son. Habría que inventar roles sin permisos solo para poder dirigirles un
  reporte.
- **Área = el `trabajador.area` de rrhh** (texto libre). Sin tablas nuevas,
  pero un typo deja un reporte sin destinatario y nadie se entera — el modo de
  fallar más caro que tiene este módulo.
- **Catálogo de emisiones en tabla.** Máxima flexibilidad y la peor superficie:
  quien administra reglas podría hacerse enviar cualquier payload del bus.
- **Que `reports` escriba `notificacion` directo.** Un salto menos, a cambio de
  que un módulo escriba en la tabla de otro. Se prefirió el evento, que es el
  mecanismo que la arquitectura ya prescribe.
- **`leida_at` en `entrega_reporte`.** Dos verdades sobre lo mismo.

## Referencias

- ADR-024 (catálogo cerrado de reportes de consulta), ADR-031 (`audit_log`
  transversal), ADR-016 (eventos post-commit), ADR-004 (tenant desde el JWT),
  ADR-022 (restricciones de permiso), ADR-026 (paginación).
- `src/modules/reports/README.md`, `docs/architecture/events.md`,
  `docs/architecture/data-model.md` §16.
- Reglas: `RN-REP-001` … `RN-REP-008` en `docs/domain/business-rules.md`.
- Tests: `tests/test_reports.py` (no confundir con `tests/test_reportes.py`).
