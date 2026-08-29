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
| Contacto del cliente | `sales` | `marketing` (a qué teléfono mandar la encuesta por WhatsApp, ADR-029) | `sales/application/queries_publicas.py::contacto_de_cliente` — nombre y teléfono, tomados de `persona` si es natural y de `cliente.contacto` si no. Devuelve `telefono` vacío si el cliente existe pero no hay a dónde escribirle: es una respuesta distinta de "no existe" y el llamador la trata distinto | interno (llamada en proceso; el endpoint que lo usa exige `marketing.encuesta_gestionar`) |
| Solicitudes por artículo/sucursal | `inventory` (`solicitud_insumos`) | `purchases` (qué se pide más y desde dónde — insumo para negociar volumen con proveedores) | `inventory/application/queries_publicas.py::solicitudes_resumen_para_negociacion` (`GET /api/v1/inventory/solicitudes/resumen`) — suma `cantidad_solicitada` por artículo/sucursal, excluye canceladas | `inventory.leer_solicitudes_externas` |
| Compras por proveedor | `purchases` | `core/reportes` (tablero de gerencia) | `purchases/application/queries_publicas.py::compras_por_proveedor` — suma OC emitidas/recibidas por proveedor en un rango | `purchases.leer` (vía el catálogo de reportes) |
| Nombre y cargo del trabajador | `rrhh` | `core/reportes` (rotular el ranking de venta por quien atendió) | `rrhh/application/queries_publicas.py::nombres_por_usuario` — `usuario_id` → nombre y cargo. **Solo eso**: remuneración, contratos y sanciones no salen de `rrhh` por ningún contrato. La cuenta se resuelve por persona (ADR-070): una persona recontratada puede matchear dos trabajadores, y gana el no cesado (o el de ingreso más reciente en empate) | `rrhh.leer` (vía el catálogo de reportes) |
| Costo unitario de receta | `inventory` | `core/reportes` (margen por producto) | `inventory/application/queries_publicas.py::costo_unitario_de_recetas` — costo de una unidad de rendimiento, con merma; una receta sin insumos **no** entra (nunca devuelve cero, que se leería como "gratis") | interno (llamada en proceso; el reporte que lo usa exige `sales.leer`) |
| Encargado de turno | `accounting` | `reports` (a quién avisarle de algo que pasa en el local — consumidor desde 2026-08-08, antes era `users`) | `accounting/application/queries_publicas.py::encargado_de_turno` — sale del `relevo_encargado_id` de la caja abierta (RN-MDP-002); `None` si no hay caja abierta **y también en toda apertura posterior a ADR-049**, donde el cajero abre solo y esa columna queda en NULL — el consumidor cae en su respaldo por rol, que pasó a ser el camino normal | interno (llamada en proceso) |
| Permisos de un usuario | `users` | `reports` (recortar el catálogo de emisiones a lo que el usuario puede ver) | `users/application/queries_publicas.py::permisos_de` — todos los códigos en una consulta, para **filtrar listas** (negar un acceso sigue siendo `require_permission`). Devuelve el comodín `*` tal cual: interpretarlo es de quien filtra | interno (llamada en proceso; el endpoint que lo usa exige `reports.leer`) |
| Puntos de venta de una sucursal | `sales` | `accounting` (encontrar la caja abierta del local) | `sales/application/queries_publicas.py::puntos_venta_de_sucursal` | interno |
| Estado de caja | `accounting` | `core/reportes` (tablero) | `accounting/application/queries_publicas.py::estado_de_caja` — cajas abiertas ahora, con horas sin cerrar y efectivo esperado | `accounting.leer` (vía el catálogo de reportes) |
| Pedidos demorados | `sales` (`alerta_pedido`) | `core/reportes` (tablero) | `sales/application/queries_publicas.py::pedidos_demorados` — lee la alerta guardada, no recalcula: el umbral queda congelado en la fila | `sales.leer` (vía el catálogo de reportes) |
| Serie/ranking de venta | `sales` | `core/reportes` | `sales/application/queries_publicas.py::ventas_por_dia`, `ventas_por_sucursal`, `ventas_por_hora`, `ventas_por_usuario`, `top_productos`, `vendido_por_producto`, `mesas_preferidas` (ADR-069 — ranking de mesa por sucursal, reusa `_ventas_en_rango` para no contradecir a los otros reportes del mismo rango) | `sales.leer` (vía el catálogo de reportes) |

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
| `sales.venta_confirmada` | sales | inventory, accounting, marketing (atribución lead→venta) | venta_id, sucursal_id, cliente_id (opcional), items[] (receta_id, cantidad, empaque_articulo_id, sin_articulo_ids), total | Al confirmar la venta. `cliente_id` se agregó 2026-08-01 para la atribución de marketing; `sin_articulo_ids` (restas de la línea) el 2026-08-09 — ausente = la línea no quitó nada | RN-COM-001, RN-PRD-002, RN-MKT-003 |
| `sales.consumo_personal_registrado` | sales | inventory (descuenta como `consumo_interno` y valoriza) | venta_id, sucursal_id, cliente_id (siempre null), items[], total (siempre "0"), tipo, consumo_motivo | Se confirma la comida del personal (RN-COM-025). **Evento propio y no `venta_confirmada`**: ese lo consumen `accounting` como ingreso y `marketing` como venta atribuible, y un consumo de personal no es ninguna de las dos | RN-COM-025/026/027, ADR-033 |
| `sales.pago_registrado` | sales | accounting | venta_id, medio, monto, ref_externa | Al registrar pago | RN-COM-002 |
| `sales.comprobante_emitido` | sales | **accounting** (asiento del débito fiscal desde 2026-08-29, ADR-080) | comprobante_id, venta_id, empresa_id, tipo, serie_numero, **total**, **gravado_igv** | Comprobante aceptado por SUNAT (Factiliza). `total` es el importe de **este** comprobante, no el de la venta entera: una cuenta dividida emite uno por grupo de cobro (RN-COM-018) y mandar el total en cada uno hacía que `accounting` reconociera el IGV una vez por comprobante sobre la venta completa. `gravado_igv` es la casilla del cobro (`null` = el régimen de la empresa) | RN-COM-003, RN-IMP-001 |
| `sales.nota_credito_emitida` | sales | inventory (repone stock **solo si quien acredita lo pidió**: sin reposición el evento viaja con `items` vacío), auditoría/BI | nota_credito_id, comprobante_id, venta_id, sucursal_id, motivo, total, repone_stock, emitido_por, items | Se acredita una venta ya cobrada, total o por ítem | RN-CPP-009 |
| `sales.venta_anulada` | sales | inventory, accounting, **reports** (acto de autoridad, RN-AUD-005) | venta_id, sucursal_id, usuario_id, items[] (receta_id, cantidad, sin_articulo_ids) | Al anular. Las restas viajan para que la reposición devuelva **solo lo que se consumió** (RN-PRD-019) | RN-GEN-002 |
| `sales.descuento_aplicado` | sales | accounting, **reports** (el «reporte de descuentos» a Gerencia, ya implementado) | venta_id, sucursal_id, modo, valor, motivo, autorizado_por | Un supervisor autoriza un descuento manual sobre el total de una orden | RN-COM-017 |
| `sales.cliente_registrado_en_promocion` | sales | marketing (lead de campaña) | promocion_id, promocion_nombre, cliente_id, cupon_id, ya_estaba_registrado | Un cliente se registra en la landing pública del QR y se le emite su cupón (ADR-061). Va `promocion_nombre` y no solo el id porque marketing empareja con SU campaña por nombre: no puede leer `promocion_cupon`, que es tabla de `sales` | RN-PRM-003, RN-MKT-003 |
| `sales.cupon_canjeado` | sales | — (hoy nadie; queda para el acumulado de campaña) | cupon_id, promocion_id, cliente_id, venta_id, monto | El cajero aplica un cupón a una venta y este queda desactivado para siempre | RN-PRM-004 |
| `sales.lineas_anuladas` | sales | inventory (repone stock), accounting, **reports** (acto de autoridad, RN-AUD-005) | venta_id, sucursal_id, autorizado_por, motivo, items[] | Se quitan líneas de una orden YA enviada a cocina. Mismo payload que `venta_anulada` pero solo con lo quitado; inventory usa el mismo listener | RN-COM-020 |
| `sales.lineas_movidas` | sales | **reports** (analítica; NO inventory, NO accounting) | movimiento_id, origen_venta_id, destino_venta_id, sucursal_id, grupos_origen[], grupo_destino, monto, usuario_id, items[] | Se reasignan líneas de una orden ya enviada a otra orden, a una mesa libre, o a otra cuenta de la misma orden ("mover productos" / "cobrar seleccionados" del PDV). El insumo no se movió del almacén ni volvió a él: por eso **no** lo consume `inventory`, a diferencia de `lineas_anuladas`. `accounting` tampoco: origen y destino asientan contra las mismas cuentas, así que reclasificar sería un asiento que se cancela solo — la desalineación de `referencia_origen` queda documentada como deuda (ADR-071) | RN-COM-043 |
| `accounting.movimiento_caja_registrado` | accounting | — (auditoría, arqueo) | movimiento_caja_id, apertura_caja_id, tipo, monto, motivo | Ingreso o retiro de efectivo del cajón durante el turno | RN-MDP-007 |
| `sales.pedido_demorado` | sales | **reports** (desde 2026-08-08; emite y distribuye — antes lo consumía `users` con la regla cableada), tablero de reportes vía `alerta_pedido` | venta_id, sucursal_id, minutos_umbral, minutos_transcurridos, estado, items_pendientes | El pedido sigue en cocina pasado el umbral (`parametro_empresa` `sales/minutos_alerta_pedido`, 15 min por defecto). Lo dispara la revisión agendada al confirmar la venta, o el barrido periódico si aquella se perdió | RN-CUP-005 |
| `sales.carrito_abandonado` | sales | — (analítica) | carrito_id, canal, paso, motivo (opcional) | Al abandonar sin confirmar | RN-COM-013 |
| `sales.pedido_listo` | sales (PROC-OPE-002) | — (pantalla de despacho, analítica de tiempos) | venta_id | Todos los ítems del pedido alcanzan `listo` | RN-CUP-005 |
| `sales.venta_entregada` | sales (PROC-OPE-002) | marketing (habilita encuesta selectiva), accounting (habilita cobro al finalizar en mesa) | venta_id, sucursal_id, modalidad, cliente_id (opcional), repartidor_externo_plataforma (opcional), entregado_por | El pedido queda en manos del cliente | RN-CUP-005/006/007/009, RN-COM-007 |
| `marketing.encuesta_enviada` | marketing | **marketing** (encola el envío real por WhatsApp y acumula en `campana_metrica`) | encuesta_id, venta_id, cliente_id, canal (`pos`\|`whatsapp`\|`link`) | Marketing selecciona una venta entregada y envía la encuesta — nunca automático para toda venta. Desde 2026-08-08 se publica con `session=` (ADR-016): el worker que manda el WhatsApp corre en otro proceso y solo puede leer filas ya commiteadas | RN-COM-007, ADR-029 |
| `marketing.encuesta_respondida` | marketing | **marketing** (acumula respuesta y puntaje en `campana_metrica`) | encuesta_id, venta_id, cliente_id, puntaje, canal | El cliente llegó al último nodo del guion (o contestó el puntaje suelto, en las encuestas anteriores al guion) | RN-COM-007, ADR-029 |
| `rrhh.salida_sin_marcar` | rrhh | **reports** (encargado del local + área RRHH) | trabajador_id, sucursal_id, trabajador, fecha, turno, hora_entrada, hora_limite | Un barrido horario encuentra una entrada sin salida pasada la `hora_limite_salida` del turno (ADR-064). Va **sin actor** a propósito, como `sales.pedido_demorado`: el hecho es «falta una marcación», no «alguien hizo algo mal». El recordatorio al propio trabajador **no** viaja por acá — va directo a su campana, porque abrir un reporte exige `rrhh.leer` (RN-REP-002) y él no lo tiene | RN-RRHH-021, RN-RRHH-022 |
| `inventory.stock_consumido` | inventory | — (auditoría) | almacen_id, articulo_id, cantidad, ref | Tras descontar por venta/producción | RN-INV-003 |
| `inventory.stock_bajo_minimo` | inventory | **reports** (desde 2026-08-08, antes `users`), production* (dispara orden por necesidad) | almacen_id, sku_id, cantidad, stock_minimo, **usuario_id** (2026-08-09, ADR-036: quién hizo el movimiento que cruzó el mínimo; nulo si no vino de una persona) | **Al cruzar** el mínimo, no cada vez que está por debajo: con el stock ya bajo, un evento por venta vuelve ruido la alerta. Reponer y volver a caer avisa de nuevo. `sku_id` y no `articulo_id` porque la fila de stock —y el mínimo— son por SKU | RN-PRD-007, RN-INV-008 |
| `inventory.transferencia_recibida` | inventory | **accounting** (asiento **solo si hubo faltante**) | transferencia_id, origen_almacen_id, destino_almacen_id, solicitud_id (nullable), diferencias[] (sku_id, lote_id, enviada, recibida), **monto_diferencia** | Al recibir en destino (ADR-020). `diferencias` solo trae las líneas donde lo recibido no coincide con lo enviado — al destino entró lo que de verdad llegó. El traslado entre almacenes de la misma empresa **no mueve resultado**; lo que sí es hecho contable es lo que salió y no llegó, así que sin faltante no hay asiento. `monto_diferencia` lo valoriza **el emisor** al `costo_promedio`: el costo es dato de `inventory` y hacerlo buscar por `accounting` sería importarle dominio ajeno | RN-INV-002 |
| `inventory.merma_registrada` | inventory | **accounting** (asiento por `regla_asiento`) | almacen_id, sku_id, lote_id (opcional), cantidad, motivo, **monto** | **Al desechar la merma, no al apartarla** (ADR-028): mientras la auditoría no decide, la mercadería puede volver al estante y asentar antes obligaría a reversar la mitad de los asientos. `monto` lo valoriza el emisor al `costo_promedio`; en 0 no se asienta nada | RN-INV-012, RN-INV-017 |
| `inventory.consumo_personal_valorizado` | inventory | **accounting** (asiento por `regla_asiento`: debe gasto de alimentación de personal / haber existencias) | venta_id, sucursal_id, empresa_id, motivo, **monto** | Tras descontar el insumo de un consumo de personal. Igual que la merma, **valoriza el emisor** al `costo_promedio`: es el único que conoce las líneas de consumo reales, y recalcularlo en contabilidad daría un número distinto al que movió el stock. En 0 no se asienta nada | RN-COM-027, ADR-034 |
| `inventory.consumo_personal_reversado` | inventory | **accounting** (anula el asiento de ese origen, asiento inverso RN-CTB-002) | venta_id, empresa_id | Se anuló un consumo de personal y el insumo volvió al almacén. Sin esto el gasto quedaría inflado por comida que nadie comió | RN-COM-027, RN-CTB-002 |
| `inventory.devolucion_a_proveedor` | inventory | purchases*, **reports** (RN-INV-020: `reporte_dirigido_a` por fin se enruta) | devolucion_id, almacen_id, referencia_id (proveedor), motivo, destino, reporte_dirigido_a, **registrado_por** (2026-08-09, ADR-036), items[] (sku_id, lote_id, cantidad) | Al registrar la devolución (ADR-028). La mercadería ya salió del almacén con el lote declarado. **Sin consumidor todavía**: el reclamo y la nota de crédito al proveedor son deuda de `purchases` | RN-INV-019/020 |
| `inventory.devolucion_de_cliente` | inventory | **reports** (RN-INV-020: dirige al área comercial) | devolucion_id, almacen_id, referencia_id (cliente), motivo, destino, reporte_dirigido_a, **registrado_por** (2026-08-09, ADR-036), items[] | Un cliente devolvió: la mercadería entró y `destino` ya decidió si volvió al estante (`reintegro`) o quedó apartada como merma (`desecho`/`auditoria`) | RN-INV-019/020 |
| `inventory.ajuste_fuera_margen` | inventory | accounting, **reports** (insumo de auditoría, RN-AUD-004) | ajuste_id, almacen_id, **aprobado_por**, **sku_id**, **cantidad**, **motivo** | Ajuste excede el margen de error configurado. Los cuatro últimos se agregaron el 2026-08-09 (ADR-036): esta fila documentaba `sku_id, diferencia, margen` que el código **nunca publicó**, y sin ellos el reporte decía «ajuste fuera de margen» sin decir de qué ni de cuánto. `aprobado_por` es el actor: el hecho reportado es que el ajuste se ejecutó, no que se pidió | RN-INV-015 |
| `inventory.lote_vencido_detectado` | inventory | **reports** (desde 2026-08-08, antes `users`), rrhh* (memorándum al responsable) | lote_id, almacen_id, sku_id, fecha_vencimiento, cantidad, **usuario_id** (2026-08-09, ADR-036: quién lo descubrió — el vencimiento no lo provoca nadie; nulo en el barrido de las 06:00) | Al hallar un lote vencido aún disponible en stock — lo publica el picking FEFO al toparse con él, el barrido `POST /inventory/lotes/bloquear-vencidos` y el periódico diario de las 06:00 (ADR-015). Sin `responsable_id`: `almacen` no lo tiene modelado, así que el aviso va **al rol** y el memorándum a RRHH sigue bloqueado — no por falta de aviso sino por falta de a quién dirigirlo | RN-VNC-001..003 |
| `inventory.guia_remision_emitida` | inventory | — (auditoría; `accounting` la resguarda, RN-GDR-003) | guia_remision_id, transferencia_id, serie, correlativo | Al emitir la guía de un traslado ya despachado. Sin consumidor todavía: contabilidad las resguarda leyendo `GET /inventory/guias-remision` | RN-GDR-001..003 |
| `inventory.guia_remision_emitida_sunat` | inventory | — (auditoría) | guia_remision_id, estado_emision, codigo_sunat | Cuando el proveedor devuelve el veredicto de SUNAT. Un rechazo **no detiene el traslado**: la guía impresa es la que viaja, y el dato se corrige y se reemite | RN-GDR-001 |
| `inventory.conteo_vencido` | inventory | **reports** (desde 2026-08-08, antes `users`; ahora `dirigido_a` sí tiene quien lo consuma) | almacen_id, categoria_id, categoria, frecuencia, fecha_programada, dias_atraso, dirigido_a (`["almacen","gerencia"]`), **usuario_id** (2026-08-09, ADR-036: quién pidió la verificación; nulo en el beat de las 06:15) | Una categoría no se contó en la fecha que su frecuencia exigía — lo publica el periódico diario de las 06:15 y el endpoint `POST /inventory/conteos/verificar-vencidos` (ADR-019). **Se repite cada día hasta que se cuente**: es un recordatorio, no la noticia de un hecho puntual | RN-INV-007, RN-INV-021 |
| `purchases.oc_emitida` | purchases | accounting | oc_id, proveedor_id, empresa_id, total | Al emitir OC | RN-CMP-001 |
| `purchases.compra_recibida` | purchases | inventory, accounting | oc_id, almacen_id, items[] (articulo_id, cantidad, costo_unitario, lote_codigo, fecha_vencimiento) | Al recibir mercadería; los dos últimos campos solo los usa inventory si el artículo controla lote (RN-VNC-002) | RN-CMP-003 |
| `purchases.comprobante_conforme` | purchases | accounting | comprobante_id, orden_compra_id, proveedor_id, empresa_id, condicion_pago, sujeto_spot, porcentaje_deteccion, monto, **gravado_igv** | Compras da conformidad al comprobante; accounting encola el pago (`movimiento_dinero` pendiente) **y asienta el crédito fiscal** (ADR-080): la recepción asentó la compra sin IGV porque el comprobante todavía no existía, y el crédito solo se toma con el comprobante válido y anotado. `gravado_igv` lo marca quien tiene la factura del proveedor delante | RN-CMP-005, RN-CMP-014, RN-IMP-001 |
| `purchases.caja_chica_rendida` | purchases | accounting | rendicion_id, gasto_total, efectivo_restante, diferencia | Al cerrar la rendición semanal de caja chica | RN-CMP-017 |
| `purchases.evaluacion_proveedor_actualizada` | purchases | — (informativo) | proveedor_id, indicador_automatico | En cada recepción (cumplimiento, conformidad, variación de precio) | — |
| `production.orden_completada` | production* | inventory | orden_id, articulo_id, cantidad | Al terminar producción | RN-PRD-003 |
| `production.no_conformidad_detectada` | production | reports (emite el reporte y lo distribuye) | orden_produccion_id, **almacen_id** (agregado 2026-08-08: de ahí sale la empresa y la sucursal del hecho), resultado (`no_conforme_reprocesado`\|`no_conforme_desechado`), **registrado_por** (2026-08-09, ADR-036: quién cerró la orden con el control de calidad en la mano). El escalamiento ya está modelado —`reporte_escalamiento`, ADR-036— y se abre **desde el reporte**, no desde este evento | Al registrar control de calidad no conforme — un solo asiento contable posible por lote, y solo si `resultado=no_conforme_desechado`: ese caso también dispara `inventory.merma_registrada` (vía merma_cantidad/merma_motivo de la orden). `no_conforme_reprocesado` no genera merma ni asiento, solo el detalle de la corrección en el reporte de escalamiento | RN-PRD-013/014/015 |
| `production.equipo_frio_fuera_rango` | production* | users (alerta inmediata a Gerencia) | cocina_produccion_id, equipo_id, temperatura_c, rango_esperado | Checklist de turno detecta equipo de frío fuera de rango — bloquea nuevas órdenes en ese equipo (`checklist_inocuidad_turno.estado=bloqueado`) | RN-CDP-005 |
| `marketing.campana_lanzada` | marketing | **marketing** (abre la fila de `campana_metrica` con la fecha de lanzamiento) | campana_id, marca_id, tipo, presupuesto | Al lanzar una campaña con brief aprobado | RN-MKT-003, ADR-030 |
| `marketing.lead_generado` | marketing | **marketing** (`campana_metrica.leads_generados`) | lead_id, campana_id, canal, cliente_id | Al registrar un lead en una campaña en curso. La atribución lead→venta la hace **marketing** escuchando `sales.venta_confirmada`, no `sales` escuchando este evento: el dueño del dato `lead.venta_id` es marketing (ADR-021) | RN-MKT-003 |
| `marketing.lead_atribuido` | marketing | **marketing** (`campana_metrica.leads_convertidos`) | lead_id, campana_id, venta_id, automatica | El lead apunta a la venta que cerró. Lo publican **las dos** vías, la manual (`POST /leads/{id}/atribucion`) y la automática (listener de `sales.venta_confirmada`, `automatica=true`): con dos caminos escribiendo el contador por separado, uno se olvida (ADR-030) | RN-MKT-003 |
| `marketing.pieza_publicada` | marketing | **marketing** (`campana_metrica.piezas_publicadas`, solo si la pieza cuelga de una campaña) | pieza_id, campana_id (nullable), marca_id, canal | Se publica una pieza pertinente y con uso de marca validado. `campana_id` nulo = contenido de marca siempre-verde, que no le suma a ninguna campaña | RN-MKT-001/002 |
| `marketing.agencia_decidida` | marketing | — (auditoría/BI; el contrato con la agencia se formaliza fuera del ERP hasta que exista `contrato`) | evaluacion_id, campana_id, opcion_id, tipo (`agencia`\|`interna`), costo, fuera_de_presupuesto | Gerencia firma con cuál se va la campaña. `fuera_de_presupuesto` viaja en el payload porque es lo que un tablero de control tiene que poder filtrar sin abrir la evaluación | RN-MKT-006, RN-GER-003 |
| `users.usuario_creado` | users | — | usuario_id, tipo | Al crear usuario | — |
| `users.sesion_iniciada` | users | — (auditoría) | usuario_id, ip | Login exitoso | — |
| `accounting.asiento_generado` | accounting | — (auditoría/BI) | asiento_id, evento_origen | Al generar asiento desde un evento operativo | — |
| `accounting.periodo_cerrado` | accounting | todos (bloquean escrituras del periodo) | periodo_id, fecha_cierre | Al cerrar un periodo contable | — |
| `accounting.apertura_caja_registrada` | accounting | users (alerta si hay diferencia) | apertura_caja_id, punto_venta_id, diferencia_reportada | Al aperturar caja | RN-POS-003, RN-MDP-008 |
| `accounting.cierre_caja_registrado` | accounting | — (auditoría/BI) | cierre_caja_id, apertura_caja_id, descuadre_monto | Al confirmar el cierre | PROC-CTB-001 |
| `accounting.cierre_caja_irregular` | accounting | reports (emite el reporte y lo distribuye) | cierre_caja_id, **sucursal_id** (agregado 2026-08-08: sin él `reports` no puede escopar el hecho — la caja cuelga del punto de venta, no de la sucursal), **cerrado_por** y **cajero_id** (2026-08-09, ADR-036: quien firma el relevo es el actor del cierre; de quién era la caja va aparte porque no tienen por qué ser la misma persona — **desde ADR-049 `cerrado_por` es el propio cajero**, porque el cierre ya no lo firma nadie más; el campo se mantiene para no reescribir `clave_actor` del catálogo), descuadre_monto, descuadre_tarjeta, descuadre_atribucion | Cierre con descuadre/irregularidad detectada | RN-MDP-005 |
| `accounting.pago_ejecutado` | accounting | purchases (marca OC pagada — sin consumidor todavía), auditoría/BI | movimiento_dinero_id, comprobante_id, orden_compra_id, proveedor_id, monto, detraccion_monto, aprobado_por | Al ejecutar el pago a proveedor | RN-CMP-014, RN-CTB-005, RN-CTB-008 |
| `accounting.pago_requiere_aprobacion` | accounting | reports (emite el reporte y lo distribuye) | movimiento_dinero_id, **empresa_id** (agregado 2026-08-08 para escopar por tenant: un pago es de la empresa, no de una sucursal), proveedor_id, monto, umbral, **solicitado_por** (2026-08-09, ADR-036: quien intentó ejecutarlo y no alcanzó el umbral — es a quien hay que volver una vez aprobado) | Pago sobre umbral en espera de aprobación de Gerencia | RN-CTB-005 |
| `accounting.arqueo_registrado` | accounting | users (notifica gerencia/RRHH si hay diferencia) | arqueo_id, punto, diferencia_monto, diferencia_atribucion | Al registrar un arqueo (sorpresa) | RN-CTB-007 |
| `accounting.pos_averiado_reportado` | accounting | — (contabilidad manda el POS de emergencia; sin consumidor todavía) | pos_tarjeta_id, serie, sucursal_id, observacion | La apertura verifica un POS de tarjeta y lo encuentra fuera de servicio — **no bloquea abrir** | RN-POS-009/010/011 |
| `accounting.cierre_caja_reabierto` | accounting | — (auditoría/BI) | cierre_caja_id, apertura_caja_id, motivo, autorizado_por | Un cierre vuelve a `en_proceso` para recontar el cajón | RN-MDP-005 |
| `accounting.custodia_efectivo_entregada` | accounting | — (auditoría/BI) | custodia_efectivo_id, apertura_caja_id, estado, monto | El efectivo cambia de manos en la cadena de custodia (quien recibe firma con su PIN). Desde ADR-049 el primer tramo (`en_caja → en_supervisor`, el encargado recibiendo lo que el cajero dejó al cerrar) también pasa por acá: antes se daba por ocurrido dentro del cierre | RN-MDP-002, RN-MDP-006, RN-MDP-008 |

`*` = módulo futuro. Reglas referenciadas en
[../domain/business-rules.md](../domain/business-rules.md).

| `reports.reporte_emitido` | reports | users (llena la bandeja: una fila de `notificacion` por destinatario) | reporte_emitido_id, codigo, titulo, cuerpo, nivel, sucursal_id, referencia_tipo, referencia_id, destinatarios[] | Cuando una emisión del catálogo resolvió al menos un destinatario. **No se publica si no hay destinatarios**: no habría nada que repartir (el hueco queda registrado del lado de `reports`) | RN-REP-001..008, ADR-033 |
| `reports.escalamiento_abierto` | reports | **reports** (el listener genérico lo emite y distribuye como cualquier otro hecho) | escalamiento_id, empresa_id, sucursal_id, reporte_emitido_id, origen, motivo, nivel_actual, descripcion, reportado_por | Alguien elevó un reporte porque no lo pudo resolver en su nivel. Ámbito **empresa** y no sucursal: un escalamiento puede nacer de un hecho sin local (un pago sobre umbral); el `sucursal_id` viaja igual para que `responsables_del_nivel` encuentre al encargado de turno. No hay recursión — emitir un reporte no abre un escalamiento | RN-CTP-004, RN-REP-011..014, ADR-036 |
| `reports.escalamiento_elevado` | reports | **reports** | escalamiento_id, empresa_id, sucursal_id, reporte_emitido_id, motivo, nivel_actual, nivel_anterior, elevado_por | El nivel anterior no pudo resolverlo y lo pasó al siguiente. `urgente`: ya se intentó una vez y sigue abierto | RN-CTP-004, RN-REP-012, ADR-036 |
| `reports.escalamiento_resuelto` | reports | **reports** (además al área Comercial: quien lo abrió tiene que enterarse de cómo terminó) | escalamiento_id, empresa_id, sucursal_id, reporte_emitido_id, nivel_actual, estado, resuelto_por | La cadena terminó. El histórico alimenta el SOP de mejora continua | RN-CTP-004, ADR-036 |

> **Nota (2026-07-27)**: `sales.venta_entregada` y `marketing.encuesta_enviada`
> vuelven a la tabla al definirse `PROC-OPE-002` (Cumplimiento de pedido)
> como **un** proceso del área Operaciones. `venta_entregada` es del módulo
> `sales` porque el estado de cumplimiento vive en `venta_item` — el área
> dueña del proceso no obliga a crear un módulo de código nuevo. En la misma
> fecha se regulariza `sales.pedido_listo`, que el KDS publicaba desde
> 2026-07-25 sin fila en esta tabla.

> **Nota (2026-08-08, ADR-033)**: los cuatro hechos que antes consumía
> `users` para llenar la bandeja (`sales.pedido_demorado`,
> `inventory.stock_bajo_minimo`, `inventory.lote_vencido_detectado`,
> `inventory.conteo_vencido`) los consume ahora `reports`, que decide a quién
> le llegan contra reglas administrables y publica `reports.reporte_emitido`.
> `users` consume ese único evento. El salto extra existe para que `reports`
> no escriba en la tabla `notificacion`, que sigue siendo de `users`: el
> usuario tiene una sola campana.

> Al agregar un evento: definir aquí su fila ANTES de publicarlo o consumirlo.
