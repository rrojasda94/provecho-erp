# Módulo `reports` — Emisión y distribución de reportes

## Objetivo

Que el ERP sepa **qué reporta, a quién se lo manda y por qué** — y que eso se
administre sin tocar código.

El ERP publica hoy 52 eventos. Antes de este módulo, cuatro llegaban a una
persona por código cableado en `users/application/listeners.py`, y los
destinatarios los decidían dos funciones fijas. No había forma de ver el mapa
completo ni de cambiarlo sin desplegar. Varias reglas de negocio
(RN-CTP-004, RN-INV-020, RN-INV-021, RN-PRD-009) exigen por escrito que un
hecho «genere un reporte dirigido a» un área, y ninguna estaba implementada:
`inventory.conteo_vencido` ya publicaba `dirigido_a: ["almacen","gerencia"]`
y `devolucion.reporte_dirigido_a` ya guardaba `almacen|comercial`, sin que
nadie los consumiera.

**No confundir con `src/core/reportes/`** (ADR-024), que es el motor de
**consulta**: el usuario pide un reporte y se calcula ahora. Este módulo es
el de **emisión y distribución**: pasa un hecho, se genera el reporte, se
guarda y se entrega. Ver ADR-033.

## Entidades

`area` (Almacén, Gerencia, Comercial, Cocina, Caja…), `area_miembro`
(rol o usuario, opcionalmente acotado a una sucursal), `regla_distribucion`
(qué emisión se distribuye, en qué ámbito), `regla_destinatario` (a qué área,
rol, usuario o resolutor dinámico), `reporte_emitido` (la instancia guardada,
con su foto de datos) y `entrega_reporte` (a quién le tocó y **por qué**).
Detalle en `docs/architecture/data-model.md` §16.

El **catálogo de emisiones** (`domain/catalogo.py`) es una lista cerrada en
código, no una tabla: la regla configura *a quién* llega un reporte, nunca
*qué datos* lee. Mismo criterio de ADR-024.

## Estado (slice core implementado 2026-08-08)

Operativo en `/api/v1/reports`. Migración `9a1c4e7b2d30`.

| Método | Ruta | Permiso |
|--------|------|---------|
| GET | `/emisiones` | `reports.leer` — el catálogo, recortado a lo que el usuario puede ver |
| GET | `/matriz` | `reports.leer_matriz` — el mapa: por emisión, sus reglas, destinatarios, huecos y fugas |
| GET/POST | `/areas` | `reports.leer_matriz` / `reports.administrar` |
| PATCH/DELETE | `/areas/{id}` | `reports.administrar` |
| GET/POST | `/areas/{id}/miembros` | `reports.leer_matriz` / `reports.administrar` |
| DELETE | `/areas/{id}/miembros/{miembro_id}` | `reports.administrar` |
| GET/POST | `/reglas` | `reports.leer_matriz` / `reports.administrar` |
| PATCH/DELETE | `/reglas/{id}` | `reports.administrar` |
| GET | `/emitidos` | `reports.leer_todo` — los de la empresa, paginado |
| GET | `/emitidos/{id}` | doble puerta: destinatario (o `reports.leer_todo`) **y** el permiso que declara la emisión |
| GET | `/mios` | `reports.leer` — lo que me fue entregado |

**No hay `POST /emitidos`.** El reporte lo emite el evento, no un cliente —
mismo criterio que ADR-031 para `audit_log`: un endpoint de escritura le
permitiría al reportado dictar lo que dice su reporte.

Emisiones cableadas en este slice (13): los cuatro avisos que existían
migrados desde `users` (`sales.pedido_demorado`,
`inventory.stock_bajo_minimo`, `inventory.lote_vencido_detectado`,
`inventory.conteo_vencido`) más `inventory.devolucion_a_proveedor`,
`inventory.devolucion_de_cliente` (RN-INV-020), `inventory.ajuste_fuera_margen`,
`sales.descuento_aplicado`, `sales.venta_anulada`, `sales.lineas_anuladas`
(actos de autoridad, RN-AUD-005), `accounting.cierre_caja_irregular`,
`accounting.pago_requiere_aprobacion` y
`production.no_conformidad_detectada` (RN-PRD-015).

Deuda del slice: `reporte_escalamiento` (RN-CTP-004, diseñado en
`data-model.md` §6 y todavía sin modelar — la cadena supervisor → comercial
→ gerencia necesita estado y acciones propias, no solo distribución);
adjuntar un reporte del catálogo de `core/reportes` a una emisión
(«al cerrar caja, manda la foto de `estado_caja` a Gerencia»); canales de
transporte más allá de la bandeja (correo, WhatsApp — el campo `canal` ya
está en el modelo); y digest/resumen en vez de una entrega por hecho.

## Casos de uso

- **Ver el catálogo de emisiones**: qué hechos del ERP producen un reporte.
- **Ver la matriz de distribución**: por emisión, a qué áreas y usuarios
  llega en cada sucursal. Marca los **huecos** (emisión sin regla activa: el
  hecho ocurre y no se entera nadie) y las **fugas** (regla cuyos
  destinatarios no resuelven a ningún usuario).
- **Administrar áreas** y su composición (roles y/o usuarios puntuales,
  opcionalmente acotados a una sucursal).
- **Administrar reglas**: qué emisión, en qué sucursal (o todas), con qué
  nivel, hacia qué destinatarios.
- **Emitir** (automático, por evento): resolver destinatarios, guardar el
  reporte con su foto de datos y registrar una entrega por destinatario.
- **Leer**: mis reportes, y —con permiso— los de la empresa.

## Reglas

- `RN-REP-001` — El catálogo de emisiones es cerrado. Una regla solo puede
  referirse a un `codigo_emision` existente; el cliente nunca aporta tablas,
  columnas ni filtros que compongan una consulta.
- `RN-REP-002` — Leer un reporte emitido exige **las dos** puertas: ser
  destinatario (o tener `reports.leer_todo`) **y** tener el permiso que la
  emisión declara, que es el de su módulo dueño. Estar en la lista de
  distribución no otorga acceso al dato.
- `RN-REP-003` — Solo se persisten los campos que la emisión declara en
  `campos`. Un payload que traiga de más no se filtra al cliente por olvido.
- `RN-REP-004` — Las entregas no son retroactivas: `reporte_emitido.regla_id`
  y `entrega_reporte.motivo` quedan congelados al emitir. Cambiar la regla
  mañana no reescribe a quién le llegó ayer.
- `RN-REP-005` — Una emisión sin destinatarios **se persiste igual**, con
  cero entregas, y aparece como hueco en la matriz. Un aviso que no llegó a
  nadie es información de gestión, no un no-evento.
- `RN-REP-006` — Un área, una regla y sus destinatarios pertenecen a una
  empresa. Un rol o usuario destinatario debe pertenecer a la empresa de la
  regla.
- `RN-REP-007` — Toda alta, cambio o baja de área, miembro, regla o
  destinatario deja rastro en `audit_log` (ADR-031). El gobierno de la
  distribución es auditable por definición.
- `RN-REP-008` — Una regla por `(empresa, emisión, sucursal)`. La regla con
  `sucursal_id` nula es la de la empresa entera y **solo aplica donde no hay
  una específica** — si no, un mismo hecho entregaría dos veces.

## Flujo

```
evento del módulo  →  reports.listeners  →  ReporteEmitido + EntregaReporte
                                         →  publica reports.reporte_emitido
                                         →  users.listeners  →  Notificacion
```

Dos saltos, ambos post-commit (ADR-016). `users` sigue siendo dueño de la
bandeja: el usuario tiene una sola campana, no dos.

## Relaciones

- **Escucha**: los 13 eventos del catálogo (`domain/catalogo.py`), de
  `sales`, `inventory`, `accounting` y `production`.
- **Publica**: `reports.reporte_emitido` — `users` lo consume para llenar la
  bandeja. Payload: `reporte_emitido_id`, `codigo`, `titulo`, `cuerpo`,
  `nivel`, `sucursal_id`, `referencia_tipo`, `referencia_id`,
  `destinatarios` (lista de `usuario_id`).
- **Consume el contrato público de**: `accounting.queries_publicas.encargado_de_turno`
  (quién está a cargo del local ahora) — el resolutor dinámico que se mudó
  desde `users/application/notificaciones.py`.
- Lee `users.infrastructure.models` (`Rol`, `UsuarioRol`, `UsuarioSucursal`,
  `Sucursal`, `Almacen`) para resolver destinatarios — organización
  transversal, excepción `"*"` de `tests/test_arquitectura.py`.
