# Catálogo de eventos

Contrato de integración entre módulos. Los módulos se comunican SOLO por estos
eventos (bus interno `src/core/events.py`) o por contratos públicos — nunca
importando el dominio de otro módulo. Ver mapa:
[../diagrams/modules.md](../diagrams/modules.md).

## Convenciones

- Nombre: `<modulo>.<hecho_en_pasado>` (ej. `sales.venta_confirmada`).
- Un evento describe un hecho ya ocurrido; el emisor no sabe quién lo consume.
- El payload es un contrato estable: agregar campos sí, quitar/renombrar es
  cambio incompatible (nueva versión del evento).
- Idempotencia: los consumidores toleran recibir el mismo evento dos veces.

## Momento de despacho (ADR-016)

El evento se publica en medio del caso de uso, pero **no se entrega hasta
que commitea la sesión que lo publicó**. Si la transacción del emisor hace
rollback, el evento se descarta y ningún consumidor lo ve.

Consecuencias para quien emite y quien consume:

- Emitir es `event_bus.publish(nombre, payload, session=session)`. Sin
  `session=` el despacho es inmediato, y eso solo tiene sentido fuera de
  una transacción.
- El consumidor **puede leer de la base lo que el emisor escribió**: para
  cuando corre, esos datos ya están commiteados. El payload no necesita
  arrastrar todo por adelantado.
- Un handler que lanza una excepción no rompe al emisor ni impide que
  corran los demás: el bus lo loguea (`log.exception` → Sentry). Un
  consumidor que falla nunca cancela la operación de origen.
- La entrega es best-effort en proceso, no at-least-once: si el commit del
  *consumidor* falla, el del emisor ya ocurrió. La garantía completa
  requiere la tabla outbox descrita en ADR-016.

## Eventos vs. contratos públicos de lectura

El event bus (`src/core/events.py`) sirve para **notificar un hecho ya
ocurrido** de forma asíncrona (el emisor no sabe quién escucha). Para una
**consulta síncrona bajo demanda** ("dame los clientes de este grupo para
analizarlos") un evento no encaja — ahí el módulo dueño expone un **contrato
público de lectura**: un archivo `application/queries_publicas.py` con
funciones que devuelven DTOs (nunca el modelo ORM ni tipos de `domain`),
protegidas por su propio permiso RBAC. Otro módulo solo puede importar de
ese archivo — nunca de `domain`/`infrastructure` del módulo dueño
(CLAUDE.md: "nunca importar el dominio de otro módulo").

Mientras el módulo consumidor no exista todavía como código (ej.
`marketing`, hoy solo README), el contrato también se expone como endpoint
HTTP — así cualquier rol autorizado lo usa ya (análisis manual, integración
futura). Cuando el módulo consumidor exista, su capa de aplicación importa
la función directamente (llamada Python en proceso, sin HTTP).

| Contrato | Dueño | Consumidores | Función | Permiso |
|---|---|---|---|---|
| Lectura de clientes | `sales` | `marketing`/`comercial` (análisis, targeting de campañas) | `sales/application/queries_publicas.py::listar_clientes_para_analisis` (`GET /api/v1/sales/clientes`) | `sales.leer_clientes_externos` |
| Solicitudes por usuario | `inventory` (`solicitud_insumos`) | `purchases` (qué usuarios/sucursales piden más — insumo para negociar con proveedores) | **bloqueado** — `solicitud_insumos` aún no existe en código (deuda de `inventory`, ver ROADMAP) | — |

## Cadena de referencia (venta → contabilidad)

```
sales.venta_confirmada
   ↓ (inventory) reserva/consume insumos de la receta
inventory.stock_consumido
   ↓ (sales) emite comprobante
sales.comprobante_emitido
   ↓ (accounting) genera asiento
accounting.asiento_generado
```

## Eventos (v1)

| Evento | Emisor | Consumidores | Payload (clave) | Cuándo | Reglas |
|--------|--------|--------------|-----------------|--------|--------|
| `sales.venta_confirmada` | sales | inventory, accounting | venta_id, sucursal_id, items[], total | Al confirmar la venta | RN-COM-001, RN-PRD-002 |
| `sales.pago_registrado` | sales | accounting | venta_id, medio, monto, ref_externa | Al registrar pago | RN-COM-002 |
| `sales.comprobante_emitido` | sales | accounting | venta_id, tipo, serie_numero | Comprobante aceptado por SUNAT (Factiliza) | RN-COM-003 |
| `sales.venta_anulada` | sales | inventory, accounting | venta_id, motivo | Al anular | RN-GEN-002 |
| `sales.carrito_abandonado` | sales | — (analítica) | carrito_id, canal, paso, motivo (opcional) | Al abandonar sin confirmar | RN-COM-013 |
| `sales.pedido_listo` | sales (PROC-OPE-002) | — (pantalla de despacho, analítica de tiempos) | venta_id | Todos los ítems del pedido alcanzan `listo` | RN-CUP-005 |
| `sales.venta_entregada` | sales (PROC-OPE-002) | marketing* (habilita encuesta selectiva), accounting (habilita cobro al finalizar en mesa) | venta_id, sucursal_id, modalidad, cliente_id (opcional), repartidor_externo_plataforma (opcional), entregado_por | El pedido queda en manos del cliente | RN-CUP-005/006/007/009, RN-COM-007 |
| `marketing.encuesta_enviada` | marketing* | — (analítica de experiencia) | encuesta_id, venta_id, cliente_id, canal (`pos`\|`whatsapp`\|`link`) | Marketing selecciona una venta entregada y envía la encuesta — nunca automático para toda venta | RN-COM-007 |
| `inventory.stock_consumido` | inventory | — (auditoría) | almacen_id, articulo_id, cantidad, ref | Tras descontar por venta/producción | RN-INV-003 |
| `inventory.stock_bajo_minimo` | inventory | users (notifica), production* (dispara orden por necesidad) | almacen_id, articulo_id, actual, minimo | Al cruzar el mínimo | RN-PRD-007 |
| `inventory.transferencia_recibida` | inventory | accounting | transferencia_id, diferencias[] | Al recibir en local | RN-INV-002 |
| `inventory.merma_registrada` | inventory | accounting | almacen_id, sku_id, lote_id (opcional), cantidad, motivo | Al registrar merma/desperdicio | RN-INV-017 |
| `inventory.devolucion_a_proveedor` | inventory | purchases | devolucion_id, proveedor_id, items[], motivo | Al registrar devolución a proveedor (purchases gestiona reclamo/nota de crédito) | RN-INV-020 |
| `inventory.ajuste_fuera_margen` | inventory | accounting, users (alerta admin) | ajuste_id, almacen_id, sku_id, diferencia, margen | Ajuste excede el margen de error configurado | RN-INV-015 |
| `inventory.lote_vencido_detectado` | inventory | users (notifica), rrhh* (memorándum al responsable) | lote_id, almacen_id, sku_id, fecha_vencimiento, cantidad | Al hallar un lote vencido aún disponible en stock — lo publica tanto el picking FEFO al toparse con él como el barrido `POST /inventory/lotes/bloquear-vencidos` (ADR-015). Sin `responsable_id`: `almacen` no lo tiene modelado; el memorándum a RRHH queda bloqueado por eso | RN-VNC-001..003 |
| `purchases.oc_emitida` | purchases | accounting | oc_id, proveedor_id, empresa_id, total | Al emitir OC | RN-CMP-001 |
| `purchases.compra_recibida` | purchases | inventory, accounting | oc_id, almacen_id, items[] (articulo_id, cantidad, costo_unitario, lote_codigo, fecha_vencimiento) | Al recibir mercadería; los dos últimos campos solo los usa inventory si el artículo controla lote (RN-VNC-002) | RN-CMP-003 |
| `purchases.comprobante_conforme` | purchases | accounting | comprobante_id, orden_compra_id, proveedor_id, empresa_id, condicion_pago, sujeto_spot, porcentaje_deteccion, monto | Compras da conformidad al comprobante; accounting encola el pago (`movimiento_dinero` pendiente) | RN-CMP-005, RN-CMP-014 |
| `purchases.caja_chica_rendida` | purchases | accounting | rendicion_id, gasto_total, efectivo_restante, diferencia | Al cerrar la rendición semanal de caja chica | RN-CMP-017 |
| `purchases.evaluacion_proveedor_actualizada` | purchases | — (informativo) | proveedor_id, indicador_automatico | En cada recepción (cumplimiento, conformidad, variación de precio) | — |
| `production.orden_completada` | production* | inventory | orden_id, articulo_id, cantidad | Al terminar producción | RN-PRD-003 |
| `production.no_conformidad_detectada` | production* | users (alerta Comercial/Gerencia si reincidencia) | orden_id, resultado (`no_conforme_reprocesado`\|`no_conforme_desechado`), reporte_escalamiento_id | Al registrar control de calidad no conforme — un solo asiento contable posible por lote, y solo si `resultado=no_conforme_desechado`: ese caso también dispara `inventory.merma_registrada` (vía merma_cantidad/merma_motivo de la orden). `no_conforme_reprocesado` no genera merma ni asiento, solo el detalle de la corrección en el reporte de escalamiento | RN-PRD-013/014/015 |
| `production.equipo_frio_fuera_rango` | production* | users (alerta inmediata a Gerencia) | cocina_produccion_id, equipo_id, temperatura_c, rango_esperado | Checklist de turno detecta equipo de frío fuera de rango — bloquea nuevas órdenes en ese equipo (`checklist_inocuidad_turno.estado=bloqueado`) | RN-CDP-005 |
| `marketing.campana_lanzada` | marketing* | — (informativo/BI) | campana_id, marca_id, tipo, presupuesto | Al lanzar una campaña con brief aprobado | RN-MKT-003 |
| `marketing.lead_generado` | marketing* | sales (atribución lead→venta) | lead_id, campana_id, canal, cliente_id | Al registrar un lead de campaña; sales lo enlaza a la venta cuando Comercial cierra | RN-MKT-003 |
| `users.usuario_creado` | users | — | usuario_id, tipo | Al crear usuario | — |
| `users.sesion_iniciada` | users | — (auditoría) | usuario_id, ip | Login exitoso | — |
| `accounting.asiento_generado` | accounting | — (auditoría/BI) | asiento_id, evento_origen | Al generar asiento desde un evento operativo | — |
| `accounting.periodo_cerrado` | accounting | todos (bloquean escrituras del periodo) | periodo_id, fecha_cierre | Al cerrar un periodo contable | — |
| `accounting.apertura_caja_registrada` | accounting | users (alerta si hay diferencia) | apertura_caja_id, punto_venta_id, diferencia_reportada | Al aperturar caja | RN-POS-003, RN-MDP-002 |
| `accounting.cierre_caja_registrado` | accounting | — (auditoría/BI) | cierre_caja_id, apertura_caja_id, descuadre_monto | Al confirmar el cierre | PROC-CTB-001 |
| `accounting.cierre_caja_irregular` | accounting | users (notifica gerencia/RRHH) | cierre_caja_id, descuadre_monto, descuadre_atribucion | Cierre con descuadre/irregularidad detectada | RN-MDP-005 |
| `accounting.pago_ejecutado` | accounting | purchases (marca OC pagada — sin consumidor todavía), auditoría/BI | movimiento_dinero_id, comprobante_id, orden_compra_id, proveedor_id, monto, detraccion_monto, aprobado_por | Al ejecutar el pago a proveedor | RN-CMP-014, RN-CTB-005, RN-CTB-008 |
| `accounting.pago_requiere_aprobacion` | accounting | users (notifica gerencia — sin consumidor todavía) | movimiento_dinero_id, proveedor_id, monto, umbral | Pago sobre umbral en espera de aprobación de Gerencia | RN-CTB-005 |
| `accounting.arqueo_registrado` | accounting | users (notifica gerencia/RRHH si hay diferencia) | arqueo_id, punto, diferencia_monto, diferencia_atribucion | Al registrar un arqueo (sorpresa) | RN-CTB-007 |

`*` = módulo futuro. Reglas referenciadas en
[../domain/business-rules.md](../domain/business-rules.md).

> **Nota (2026-07-27)**: `sales.venta_entregada` y `marketing.encuesta_enviada`
> vuelven a la tabla al definirse `PROC-OPE-002` (Cumplimiento de pedido)
> como **un** proceso del área Operaciones. `venta_entregada` es del módulo
> `sales` porque el estado de cumplimiento vive en `venta_item` — el área
> dueña del proceso no obliga a crear un módulo de código nuevo. En la misma
> fecha se regulariza `sales.pedido_listo`, que el KDS publicaba desde
> 2026-07-25 sin fila en esta tabla.

> Al agregar un evento: definir aquí su fila ANTES de publicarlo o consumirlo.
