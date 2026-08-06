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

Mientras el módulo consumidor no exista todavía como código, el contrato
también se expone como endpoint HTTP — así cualquier rol autorizado lo usa
ya (análisis manual, integración futura). Cuando el módulo consumidor
existe, su capa de aplicación importa la función directamente (llamada
Python en proceso, sin HTTP) — es lo que hace `marketing` desde 2026-08-01.

| Contrato | Dueño | Consumidores | Función | Permiso |
|---|---|---|---|---|
| Lectura de clientes | `sales` | `marketing`/`comercial` (análisis, targeting de campañas) | `sales/application/queries_publicas.py::listar_clientes_para_analisis` (`GET /api/v1/sales/clientes`) | `sales.leer_clientes_externos` |
| Venta para encuesta | `sales` | `marketing` (decide a qué venta entregada encuestar, RN-COM-007) | `sales/application/queries_publicas.py::venta_para_encuesta` — devuelve sucursal, cliente y si el pedido ya se entregó | interno (llamada en proceso; el endpoint que lo usa exige `marketing.encuesta_gestionar`) |
| Solicitudes por artículo/sucursal | `inventory` (`solicitud_insumos`) | `purchases` (qué se pide más y desde dónde — insumo para negociar volumen con proveedores) | `inventory/application/queries_publicas.py::solicitudes_resumen_para_negociacion` (`GET /api/v1/inventory/solicitudes/resumen`) — suma `cantidad_solicitada` por artículo/sucursal, excluye canceladas | `inventory.leer_solicitudes_externas` |
| Compras por proveedor | `purchases` | `core/reportes` (tablero de gerencia) | `purchases/application/queries_publicas.py::compras_por_proveedor` — suma OC emitidas/recibidas por proveedor en un rango | `purchases.leer` (vía el catálogo de reportes) |
| Nombre y cargo del trabajador | `rrhh` | `core/reportes` (rotular el ranking de venta por quien atendió) | `rrhh/application/queries_publicas.py::nombres_por_usuario` — `usuario_id` → nombre y cargo. **Solo eso**: remuneración, contratos y sanciones no salen de `rrhh` por ningún contrato | `rrhh.leer` (vía el catálogo de reportes) |
| Costo unitario de receta | `inventory` | `core/reportes` (margen por producto) | `inventory/application/queries_publicas.py::costo_unitario_de_recetas` — costo de una unidad de rendimiento, con merma; una receta sin insumos **no** entra (nunca devuelve cero, que se leería como "gratis") | interno (llamada en proceso; el reporte que lo usa exige `sales.leer`) |
| Encargado de turno | `accounting` | `users` (a quién avisarle de algo que pasa en el local) | `accounting/application/queries_publicas.py::encargado_de_turno` — sale del `relevo_encargado_id` de la caja abierta (RN-MDP-002); `None` si no hay caja abierta | interno (llamada en proceso) |
| Puntos de venta de una sucursal | `sales` | `accounting` (encontrar la caja abierta del local) | `sales/application/queries_publicas.py::puntos_venta_de_sucursal` | interno |
| Estado de caja | `accounting` | `core/reportes` (tablero) | `accounting/application/queries_publicas.py::estado_de_caja` — cajas abiertas ahora, con horas sin cerrar y efectivo esperado | `accounting.leer` (vía el catálogo de reportes) |
| Pedidos demorados | `sales` (`alerta_pedido`) | `core/reportes` (tablero) | `sales/application/queries_publicas.py::pedidos_demorados` — lee la alerta guardada, no recalcula: el umbral queda congelado en la fila | `sales.leer` (vía el catálogo de reportes) |
| Serie/ranking de venta | `sales` | `core/reportes` | `sales/application/queries_publicas.py::ventas_por_dia`, `ventas_por_sucursal`, `ventas_por_hora`, `ventas_por_usuario`, `top_productos`, `vendido_por_producto` | `sales.leer` (vía el catálogo de reportes) |

## Cadena de referencia (venta → contabilidad)

```
sales.venta_confirmada
   ↓ (inventory) reserva/consume insumos de la receta
inventory.stock_consumido
   ↓ (sales) emite comprobante
sales.comprobante_emitido
sales.nota_credito_emitida
   ↓ (accounting) genera asiento
accounting.asiento_generado
```

## Eventos (v1)

| Evento | Emisor | Consumidores | Payload (clave) | Cuándo | Reglas |
|--------|--------|--------------|-----------------|--------|--------|
| `sales.venta_confirmada` | sales | inventory, accounting, marketing (atribución lead→venta) | venta_id, sucursal_id, cliente_id (opcional), items[], total | Al confirmar la venta. `cliente_id` se agregó 2026-08-01 para la atribución de marketing | RN-COM-001, RN-PRD-002, RN-MKT-003 |
| `sales.pago_registrado` | sales | accounting | venta_id, medio, monto, ref_externa | Al registrar pago | RN-COM-002 |
| `sales.comprobante_emitido` | sales | accounting | venta_id, tipo, serie_numero | Comprobante aceptado por SUNAT (Factiliza) | RN-COM-003 |
| `sales.nota_credito_emitida` | sales | inventory (repone stock **solo si quien acredita lo pidió**: sin reposición el evento viaja con `items` vacío), auditoría/BI | nota_credito_id, comprobante_id, venta_id, sucursal_id, motivo, total, repone_stock, emitido_por, items | Se acredita una venta ya cobrada, total o por ítem | RN-CPP-009 |
| `sales.venta_anulada` | sales | inventory, accounting | venta_id, motivo | Al anular | RN-GEN-002 |
| `sales.descuento_aplicado` | sales | accounting, gerencia (reporte de descuentos) | venta_id, sucursal_id, modo, valor, motivo, autorizado_por | Un supervisor autoriza un descuento manual sobre el total de una orden | RN-COM-017 |
| `sales.lineas_anuladas` | sales | inventory (repone stock), accounting | venta_id, sucursal_id, autorizado_por, motivo, items[] | Se quitan líneas de una orden YA enviada a cocina. Mismo payload que `venta_anulada` pero solo con lo quitado; inventory usa el mismo listener | RN-COM-020 |
| `accounting.movimiento_caja_registrado` | accounting | — (auditoría, arqueo) | movimiento_caja_id, apertura_caja_id, tipo, monto, motivo | Ingreso o retiro de efectivo del cajón durante el turno | RN-MDP-007 |
| `sales.pedido_demorado` | sales | **users** (crea `notificacion` para el encargado de turno del local), tablero de reportes vía `alerta_pedido` | venta_id, sucursal_id, minutos_umbral, minutos_transcurridos, estado, items_pendientes | El pedido sigue en cocina pasado el umbral (`parametro_empresa` `sales/minutos_alerta_pedido`, 15 min por defecto). Lo dispara la revisión agendada al confirmar la venta, o el barrido periódico si aquella se perdió | RN-CUP-005 |
| `sales.carrito_abandonado` | sales | — (analítica) | carrito_id, canal, paso, motivo (opcional) | Al abandonar sin confirmar | RN-COM-013 |
| `sales.pedido_listo` | sales (PROC-OPE-002) | — (pantalla de despacho, analítica de tiempos) | venta_id | Todos los ítems del pedido alcanzan `listo` | RN-CUP-005 |
| `sales.venta_entregada` | sales (PROC-OPE-002) | marketing (habilita encuesta selectiva), accounting (habilita cobro al finalizar en mesa) | venta_id, sucursal_id, modalidad, cliente_id (opcional), repartidor_externo_plataforma (opcional), entregado_por | El pedido queda en manos del cliente | RN-CUP-005/006/007/009, RN-COM-007 |
| `marketing.encuesta_enviada` | marketing | — (analítica de experiencia) | encuesta_id, venta_id, cliente_id, canal (`pos`\|`whatsapp`\|`link`) | Marketing selecciona una venta entregada y envía la encuesta — nunca automático para toda venta | RN-COM-007 |
| `inventory.stock_consumido` | inventory | — (auditoría) | almacen_id, articulo_id, cantidad, ref | Tras descontar por venta/producción | RN-INV-003 |
| `inventory.stock_bajo_minimo` | inventory | users (notifica), production* (dispara orden por necesidad) | almacen_id, articulo_id, actual, minimo | Al cruzar el mínimo | RN-PRD-007 |
| `inventory.transferencia_recibida` | inventory | accounting | transferencia_id, origen_almacen_id, destino_almacen_id, solicitud_id (nullable), diferencias[] (sku_id, lote_id, enviada, recibida) | Al recibir en destino (ADR-020). `diferencias` solo trae las líneas donde lo recibido no coincide con lo enviado — al destino entró lo que de verdad llegó. Sin consumidor todavía en `accounting` | RN-INV-002 |
| `inventory.merma_registrada` | inventory | accounting | almacen_id, sku_id, lote_id (opcional), cantidad, motivo | Al registrar merma/desperdicio | RN-INV-017 |
| `inventory.devolucion_a_proveedor` | inventory | purchases | devolucion_id, proveedor_id, items[], motivo | Al registrar devolución a proveedor (purchases gestiona reclamo/nota de crédito) | RN-INV-020 |
| `inventory.ajuste_fuera_margen` | inventory | accounting, users (alerta admin) | ajuste_id, almacen_id, sku_id, diferencia, margen | Ajuste excede el margen de error configurado | RN-INV-015 |
| `inventory.lote_vencido_detectado` | inventory | users (notifica), rrhh* (memorándum al responsable) | lote_id, almacen_id, sku_id, fecha_vencimiento, cantidad | Al hallar un lote vencido aún disponible en stock — lo publica tanto el picking FEFO al toparse con él como el barrido `POST /inventory/lotes/bloquear-vencidos` (ADR-015). Sin `responsable_id`: `almacen` no lo tiene modelado; el memorándum a RRHH queda bloqueado por eso | RN-VNC-001..003 |
| `inventory.guia_remision_emitida` | inventory | — (auditoría; `accounting` la resguarda, RN-GDR-003) | guia_remision_id, transferencia_id, serie, correlativo | Al emitir la guía de un traslado ya despachado. Sin consumidor todavía: contabilidad las resguarda leyendo `GET /inventory/guias-remision` | RN-GDR-001..003 |
| `inventory.guia_remision_emitida_sunat` | inventory | — (auditoría) | guia_remision_id, estado_emision, codigo_sunat | Cuando el proveedor devuelve el veredicto de SUNAT. Un rechazo **no detiene el traslado**: la guía impresa es la que viaja, y el dato se corrige y se reemite | RN-GDR-001 |
| `inventory.conteo_vencido` | inventory | users (reporte a almacén y gerencia) | almacen_id, categoria_id, categoria, frecuencia, fecha_programada, dias_atraso, dirigido_a (`["almacen","gerencia"]`) | Una categoría no se contó en la fecha que su frecuencia exigía — lo publica el barrido `POST /inventory/conteos/verificar-vencidos` (ADR-019). Sin consumidor todavía; hoy el reporte se lee en `GET /inventory/conteos/programa` | RN-INV-007, RN-INV-021 |
| `purchases.oc_emitida` | purchases | accounting | oc_id, proveedor_id, empresa_id, total | Al emitir OC | RN-CMP-001 |
| `purchases.compra_recibida` | purchases | inventory, accounting | oc_id, almacen_id, items[] (articulo_id, cantidad, costo_unitario, lote_codigo, fecha_vencimiento) | Al recibir mercadería; los dos últimos campos solo los usa inventory si el artículo controla lote (RN-VNC-002) | RN-CMP-003 |
| `purchases.comprobante_conforme` | purchases | accounting | comprobante_id, orden_compra_id, proveedor_id, empresa_id, condicion_pago, sujeto_spot, porcentaje_deteccion, monto | Compras da conformidad al comprobante; accounting encola el pago (`movimiento_dinero` pendiente) | RN-CMP-005, RN-CMP-014 |
| `purchases.caja_chica_rendida` | purchases | accounting | rendicion_id, gasto_total, efectivo_restante, diferencia | Al cerrar la rendición semanal de caja chica | RN-CMP-017 |
| `purchases.evaluacion_proveedor_actualizada` | purchases | — (informativo) | proveedor_id, indicador_automatico | En cada recepción (cumplimiento, conformidad, variación de precio) | — |
| `production.orden_completada` | production* | inventory | orden_id, articulo_id, cantidad | Al terminar producción | RN-PRD-003 |
| `production.no_conformidad_detectada` | production* | users (alerta Comercial/Gerencia si reincidencia) | orden_id, resultado (`no_conforme_reprocesado`\|`no_conforme_desechado`), reporte_escalamiento_id | Al registrar control de calidad no conforme — un solo asiento contable posible por lote, y solo si `resultado=no_conforme_desechado`: ese caso también dispara `inventory.merma_registrada` (vía merma_cantidad/merma_motivo de la orden). `no_conforme_reprocesado` no genera merma ni asiento, solo el detalle de la corrección en el reporte de escalamiento | RN-PRD-013/014/015 |
| `production.equipo_frio_fuera_rango` | production* | users (alerta inmediata a Gerencia) | cocina_produccion_id, equipo_id, temperatura_c, rango_esperado | Checklist de turno detecta equipo de frío fuera de rango — bloquea nuevas órdenes en ese equipo (`checklist_inocuidad_turno.estado=bloqueado`) | RN-CDP-005 |
| `marketing.campana_lanzada` | marketing | — (informativo/BI) | campana_id, marca_id, tipo, presupuesto | Al lanzar una campaña con brief aprobado | RN-MKT-003 |
| `marketing.lead_generado` | marketing | — (informativo/BI) | lead_id, campana_id, canal, cliente_id | Al registrar un lead en una campaña en curso. La atribución lead→venta la hace **marketing** escuchando `sales.venta_confirmada`, no `sales` escuchando este evento: el dueño del dato `lead.venta_id` es marketing (ADR-021) | RN-MKT-003 |
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
| `accounting.pos_averiado_reportado` | accounting | — (contabilidad manda el POS de emergencia; sin consumidor todavía) | pos_tarjeta_id, serie, sucursal_id, observacion | La apertura verifica un POS de tarjeta y lo encuentra fuera de servicio — **no bloquea abrir** | RN-POS-009/010/011 |
| `accounting.cierre_caja_reabierto` | accounting | — (auditoría/BI) | cierre_caja_id, apertura_caja_id, motivo, autorizado_por | Un cierre vuelve a `en_proceso` para recontar el cajón | RN-MDP-005 |
| `accounting.custodia_efectivo_entregada` | accounting | — (auditoría/BI) | custodia_efectivo_id, apertura_caja_id, estado, monto | El efectivo cambia de manos en la cadena de custodia (quien recibe firma con su PIN) | RN-MDP-002, RN-MDP-006 |

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
