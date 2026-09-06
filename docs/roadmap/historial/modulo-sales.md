# Historial — Módulo `sales` (PDV, KDS, catálogo de venta)

Estado vigente: 🔶 En curso — PDV/KDS/catálogo de venta con múltiples slices y parches en producción/staging (cobro, mesas, cupones, cocina por estaciones, catálogo de atributos y variantes), con varias auditorías (Olas 1-4) cerrando huecos de superficie (endpoints sin pantalla, gates de permiso faltantes) y deuda declarada en `docs/roadmap/deuda/modulo-sales.md`.

## Cronología

### 2026-07-04 — F0, fundaciones (fila general)
> (ROADMAP.md líneas 5-12, tabla F0) — fila "Especificaciones de módulos base": "✅ 2026-07-04 | READMEs de users, inventory, sales, purchases, accounting".

### 2026-07-14/15 — Slice vertical en curso: Venta — PROC-COM-001
**Nomenclatura de procesos** (2026-07-15, `docs/domain/process-nomenclature.md`):
código de área es el área real de la empresa, no el módulo del ERP —
Venta pertenece a Comercial (`COM`), no a un área "Ventas" (`VNT`).
Renombrado en todo lo ya escrito: `RN-VNT-*`→`RN-COM-*`, `CU-VNT-*`→
`CU-COM-*`, proceso registrado como `PROC-COM-001` (v1.0, Vigente) en el
[registro maestro](docs/domain/process-nomenclature.md#registro-maestro).
El módulo de código sigue llamándose `sales` y los eventos siguen
`sales.venta_*` — el código de área NO reemplaza el nombre del módulo
técnico, son cosas distintas.

Primer proceso elegido para atravesar completo. Avance de esta sesión:

- **Mapa visual end-to-end** (FigJam, todos los procesos conectados,
  incluye Venta) — ver enlace en la conversación; ya tenía "Producción en
  sucursal" y "Marketing" como secciones separadas de "Comercial / Venta"
  — coincide con el recorte de alcance de abajo, no hizo falta tocarlo.
- **Procesos**: `docs/domain/workflows.md`.
- **Reglas**: `docs/domain/business-rules.md`.
- **Casos de uso** (F4, doc nuevo): `docs/domain/use-cases.md` —
  CU-COM-001 (mesa), CU-COM-002 (takeout/delivery).
- **Eventos**: `docs/architecture/events.md`.
- **Estados**: `docs/domain/state-machines.md`.
- **Datos**: `docs/architecture/data-model.md` §6 — entidad
  `encuesta_satisfaccion` (queda igual, es de un módulo futuro).

**Corrección de alcance (2026-07-14, mismo día, tras revisar contra un
BPMN de Bizagi que trajo el usuario)**: Venta termina en el envío del
pedido a cocina + el cobro (RN-COM-005). Preparación, emplatado/
empaquetado, despacho y entrega al cliente NO son Venta — se retiraron de
`workflows.md`/`business-rules.md`/`use-cases.md`/`state-machines.md`/
`events.md` y quedaron marcados "fuera de Venta, borrador sin confirmar"
en esos mismos archivos (no se borró contenido, se reetiquetó). Pendiente
del usuario: si eso es UN proceso ("Cumplimiento de pedido") o DOS
(Producción/Cocina + Despacho/Entrega) — dijo "defino después".
**Resuelto 2026-07-27**: UN proceso, `PROC-OPE-002` — ver la sección
"Cumplimiento de pedido — PROC-OPE-002" abajo.

**Relato detallado de los 3 canales (2026-07-14, mismo día)** — el usuario
narró la experiencia real de venta en Web, Central de Pedidos y Sucursal,
paso a paso, con puntos de abandono y su resolución. Incorporado:
- `use-cases.md` — CU-COM-001/002/003 reescritos por canal (antes eran
  por modalidad mesa/takeout-delivery, ahora son por canal real).
- `business-rules.md` — RN-COM-008 (datos obligatorios takeout/delivery),
  RN-COM-009 (confirmar pedido completo antes del precio), RN-COM-010/011/012
  (resolución de desistimiento por stock/precio/tiempo de espera),
  RN-COM-013 (registro de abandono para análisis de embudo).
- `events.md` — `sales.carrito_abandonado`.
- `workflows.md` — diagrama por canal, termina igual en "envío a cocina".
- **BPMN 2.0 para Bizagi** (generado, no a mano):
  `docs/diagrams/Procesos/Comercial/PROC-COM-001-v1.0.bpmn` — 5 lanes
  (Cliente, Web/Kiosko, Central de Pedidos, Atención al Cliente, Cocina),
  80 nodos, 96 flujos, arranca en 1 gateway de canal y converge en "Fin de
  Venta". Generado con script (no a mano) y validado estructuralmente
  (sin referencias colgantes, sin huérfanos, DI completo) — falta
  confirmar que Bizagi lo importe sin fricción, el usuario lo prueba.

Pendiente del slice Venta (señalado por el usuario, no modelado aún):
escalamiento de reclamos post-venta, monitoreo del pedido ya en curso,
manejo de errores técnicos/demoras del sistema. (Desistimiento durante la
toma del pedido SÍ quedó cubierto con RN-COM-010/011/012.) Módulo
`marketing` sigue sin README/contrato propio.

### 2026-07-20 — Modelado de BD — siguiente sesión (transversal, incluye bloque "Operación comercial")
*Nota: sección transversal a todo el ERP; se incluye aquí por el bloque "Operación comercial", que es de `sales`. Ver también historial de los demás módulos para el resto de bloques.*

Punto de partida: `docs/architecture/data-model.md` (fuente de verdad,
ya ampliado con todo lo definido en esta sesión). Al modelar, revisar
también `docs/domain/domain-model.md` y `docs/domain/business-rules.md`
para constraints/checks a nivel de BD (ej. RN-GEN-001 stock inmutable,
RN-INV-009 disponible=físico−reservado, RN-CPP-007 serie/correlativo
único por empresa).

Entidades transversales a modelar primero (de las que dependen casi
todas las demás):
- `persona` (party model — base de trabajador/cliente natural/usuario)
- `categoria` (aplica a articulo Y activo)
- `categoria_udm` + `unidad_medida` (con ratio de conversión)
- `archivo` (vínculo polimórfico, soporta evidencia/reportes)

Bloques de entidades nuevas de esta sesión, a incorporar al modelado:
- **Productos/Inventario**: `sku`, `lote`, `reserva_stock`, `conteo`+
  `conteo_item`, entidades ya existentes enriquecidas (`articulo` con
  tipos `mercaderia`/`empaque`/`repuesto`, `stock` con fecha_apertura).
- **Documentos**: `guia_remision`, `contrato`, `cotizacion`,
  `reporte_produccion`, `carta_disputa_pago`, `comprobante` (serie/
  correlativo por empresa/POS).
- **Movimientos**: `devolucion`, `auditoria` (proceso, distinto de
  `audit_log`).
- **Operación comercial**: `carrito`, `medio_pago`, `custodia_efectivo`,
  `promocion`, `cuenta_puntos`+`puntos_movimiento`, `programa_puntos_config`,
  `declaracion_itan`.
- **Recursos**: `vehiculo`, `equipamiento`, `repuesto_compatibilidad`,
  `orden_mantenimiento`.
- **RRHH** (`docs/architecture/data-model.md#8b`): `trabajador`,
  `contrato_laboral`, `boleta_pago`, `memorandum`, `amonestacion`, `acta`,
  `certificado_trabajo`, `liquidacion_bss`, `solicitud_permiso`,
  `pacto_permanencia`, `asistencia`, `postulante`, `socio`.
- **Máquinas de estado a implementar como constraints/transiciones**: ver
  `docs/domain/state-machines.md` (Venta con flujo orden→preparación→
  listo→entrega→pago/comprobante flexible→entregado→devolución; Custodia
  de efectivo cajero→supervisor→contabilidad).

Pendiente de decisión técnica antes de migrar: estrategia de tenant
(RLS de Postgres vs. filtro a nivel de aplicación) — no definida aún en
docs, definirla al iniciar esta fase.

### 2026-07-19 — Área Comercial — precio, margen, promociones, mercado y desempeño de venta
Documentación completa del área Comercial, a partir de un alcance amplio
dado por el usuario: no solo vender, sino mejorar procesos de venta, buscar
mercado/público nuevo, impulsar producto nuevo (coordina con
Producción/I+D+i), coordinar leads con Marketing, ofertas/promociones,
metas de venta, evaluación de desempeño del personal operativo, y
capacitación conjunta con RRHH/Marketing. Puesto dedicado: **jefe/encargado
comercial**. Decisión clave: la evaluación de desempeño de venta que hace
Comercial **alimenta** el proceso de RRHH pero no reemplaza su decisión de
continuidad laboral (periodo de prueba sigue siendo de RRHH). Metas de
venta: sin esquema de incentivo/comisión definido aún — se documentó el
criterio de cómo se aprobaría (Comercial + RRHH + Gerencia, nunca
retroactivo) sin inventar cifras.

Incorporado:
- `docs/comercial/` (nuevo): `README.md` (mapa de responsabilidades →
  SOPs), `politica-comercial.md` (margen de contribución, precios,
  ofertas/promociones, metas/incentivos, coordinación con áreas aún no
  documentadas), `perfiles/jefe-comercial.md`.
- `docs/diagrams/Procesos/Comercial/` — 9 SOPs nuevos en
  `Estrategia-Mercado/` (mejora continua de experiencia de cliente,
  investigación de mercado/público objetivo, coordinación de desarrollo de
  nuevo producto), `Precios-Promociones/` (evaluación de precio y margen,
  creación de oferta/promoción) y `Metas-Desempeno/` (coordinación de leads
  con Marketing, definición/seguimiento de metas, evaluación de desempeño
  comercial del personal, capacitación de venta). Se suman a `Ventas/` y
  `Cobros/` ya existentes.
- `docs/templates/comercial/` — 5 plantillas: ficha de precio/margen,
  brief de oferta/promoción, ficha de requerimiento de nuevo producto,
  reporte de desempeño comercial, plan de capacitación de venta.
- `business-rules.md` — nueva sección "Comercial — estrategia" con
  RN-CML-001 a RN-CML-006 (margen obligatorio antes de publicar precio,
  brief obligatorio de promoción, incentivo nunca retroactivo, evaluación
  de desempeño como insumo de RRHH sin reemplazar su decisión, producto
  nuevo no se compromete sin validar viabilidad, decisión de mercado
  requiere hallazgo documentado).
- `glossary.md` — término **Margen de Contribución** agregado (se usaba en
  varios lugares sin definición formal).
- `src/modules/sales/README.md` (spec técnica) — `lista_precio` con
  vigencia de promoción auto-restaurable, cálculo de margen de
  contribución expuesto a Comercial, cambio de precio siempre por nueva
  versión (nunca edición directa), igual que las OC de `purchases`.
- `00_PROJECT.md` — entrada `comercial/` en el mapa; tablas actualizadas.

Pendiente (declarado, no bloquea): margen de contribución mínimo objetivo
(queda `[[ COMPLETAR ]]`, a definir con contabilidad); esquema de
incentivo/comisión de metas de venta (queda como criterio a definir, sin
cifra); documentación propia de **Marketing** e **I+D+i/Producción** —
Comercial coordina con ambas pero solo documentó su propio lado del
proceso.

> (ROADMAP.md línea 32, fila F0 "Comercial: procesos y plantillas"): "✅ 2026-07-19 | `docs/comercial/`, 9 SOPs, 5 plantillas — ver detalle abajo. Módulo backend `sales` ajustado (margen, vigencia de promoción)".

### 2026-07-20 — Slice Venta — núcleo de datos
Primer slice vertical de datos completo, a pedido del usuario: conectar
venta con cliente y trabajador para habilitar **historial de compras del
cliente** y **ranking de ventas por trabajador**. Ambas consultas ya
funcionan y están probadas (`tests/test_venta_slice.py`).

Antes de modelar se corrigieron 2 inconsistencias reales encontradas:
`data-model.md` §6 `venta.estado` seguía listando el enum viejo de 8
estados; `state-machines.md` ya lo había corregido a 4
(`orden|pagada|facturada|anulada`) el 2026-07-14 — quedó desalineado.
`articulo` no tenía `empresa_id` directo, rompiendo la convención de
tenant (ADR-004) porque `categoria_id` es opcional. Ambas corregidas en
`data-model.md` antes de generar el modelo.

11 tablas nuevas (22 en total con el bloque transversal):
- `usuario` (alcance mínimo — sin rol/permiso/RBAC todavía, eso es el
  slice de auth dedicado).
- `trabajador` (RRHH — nuevo módulo `src/modules/rrhh/`, solo esta
  entidad; el resto de §8b sigue pendiente del slice de RRHH).
- `articulo`, `sku`, `receta`, `receta_item` (base de productos —
  inventory), `cliente`, `punto_venta`, `producto_comercial`, `venta`,
  `venta_item` (sales, módulo nuevo).

Deliberadamente diferido (no bloquea historial/ranking, se agrega
cuando se aborde PROC-COM-002 o el pricing): `modificador`,
`variante_producto`, `combo`, `lista_precio`, `precio`, `promocion`,
`medio_pago`, `pago`, `comprobante`, `carrito`, `central_pedidos`,
`cuenta_puntos`.

Migración `08c7aa59dd6e`, aplicada y verificada en Supabase (ciclo
upgrade/downgrade/upgrade limpio, igual que el bloque anterior).

### 2026-07-20 — Slice Cobro, Comprobante y Caja
*Nota: la parte de apertura/cierre/custodia de caja pertenece de fondo al módulo `accounting` — ver también `modulo-accounting.md`. Se conserva completa aquí porque el mismo slice, la misma migración y la misma sesión narrativa cubren el cobro del PDV y el ciclo de caja como una sola unidad indivisible en su momento.*

Segundo incremento del proceso Venta, a pedido del usuario: PROC-COM-002
(Cobro y Emisión de Comprobante) + el ciclo de caja completo
(PROC-CTB-001/002), que el cobro en efectivo necesita para cerrar su
cadena de custodia. Antes de modelar, alineamos 4 decisiones reales con
el usuario (no asumidas):

1. Alcance: caja completa (apertura/cierre/custodia) esta misma vuelta,
   no diferida.
2. Series de comprobante separadas por punto de venta (boleta ≠
   factura, típico SUNAT) — `punto_venta.serie_boleta`/`serie_factura`.
3. `medio_pago` es catálogo **por empresa**, no global del grupo.
4. Pago dividido (varios medios en una misma venta) es un caso real del
   negocio, no solo capacidad técnica — RN-COM-016 nueva.

Gaps reales encontrados y corregidos en `data-model.md` antes de
modelar: `pago` no tenía `monto` ni `idempotency_key` (imposible validar
pago dividido sin monto por fila); `medio_pago` no tenía `empresa_id`;
`punto_venta` no tenía dónde vivir la serie que `comprobante.serie`
dice heredar.

8 tablas nuevas (30 en total): `medio_pago`, `pago` (sales);
`comprobante` (nuevo módulo transversal `src/shared/models/` — sirve a
sales/purchases/accounting, ningún módulo lo posee en exclusiva);
`apertura_caja`, `custodia_efectivo`, `cierre_caja`, `arqueo` (nuevo
módulo `src/modules/accounting/`, solo el ciclo de caja — plan de
cuentas/asiento/periodo_contable siguen pendientes). 3 eventos nuevos en
`events.md`: `accounting.apertura_caja_registrada`,
`accounting.cierre_caja_registrado`, `accounting.cierre_caja_irregular`.

Deliberadamente diferido: `carta_disputa_pago` (RN-MDP-004, camino de
excepción — reclamo de doble cobro).

Migración `8cde35e4f3f2`, verificada en Supabase (ciclo upgrade/
downgrade/upgrade). 13/13 tests pasan (3 nuevos en
`tests/test_cobro_caja_slice.py`).

### 2026-07-22 — Ajuste vinculado desde Marketing/Gerencia (referencia)
*No se transcribe verbatim aquí por no ser contenido propio de `sales` — ver `docs/roadmap/historial/modulo-marketing.md` / `modulo-gerencia.md` para el detalle de "Ajustes de Marketing y Gerencia — feedback del usuario". Se anota el puntero porque toca RN-COM-007 (encuesta de satisfacción) que sí es contrato de `sales`.*

### 2026-07-25 — F0: Módulo `sales` (PDV) — slices 1-3
Venta con correlativo+idempotencia → `sales.venta_confirmada` → inventory descuenta por receta (+merma+empaque); cobro con pagos parciales → `pagada`; anulación pre-pago repone stock; CRUD productos/medios de pago. **KDS** (slice 2): pantallas configurables por sucursal y categorías (`kds_pantalla`, migración `7672566bf189`), avance por ítem en `venta_item.estado_preparacion` (fuente única → todas las pantallas ven el avance real), tipos preparación/despacho, comanda imprimible con contador de reimpresiones, evento `sales.pedido_listo`, rol `cocinero`; **pantalla KDS** en `frontend/app/kds/` (2026-08-03, tarjeta por pedido con tachado por ítem, polling 3 s). Kiosk/Central de Pedidos = clientes del mismo contrato, no módulos. **Cumplimiento de pedido** (slice 3, 2026-07-27): `PROC-OPE-002` definido como UN proceso (área Operaciones) y su etapa de entrega implementada — `POST /sales/ventas/{id}/entrega` con permiso propio `sales.entregar_pedido` y rol `despachador`, idempotente, publica `sales.venta_entregada` (disparador de la encuesta de marketing, RN-COM-007).

### 2026-07-27 — F0: Slice PDV (mesas, grupo de cobro, descuento manual)
**Slice PDV** (slice 4, 2026-07-28, ADR-018, migración `d7e3b8c14f52`): `mesa` tipada por sucursal + mapa de salón derivado; `grupo_cobro` para dividir la cuenta y emitir un comprobante por pagador (RN-COM-018); receptor tecleado en caja que decide boleta/factura sin cliente registrado (RN-CPP-003); descuento manual de orden con motivo y autorizador (RN-COM-017, permiso propio). Suma `POST /sales/clientes` y `GET /sales/ventas`.

### 2026-07-27 — Cumplimiento de pedido — PROC-OPE-002 (detalle completo)
Cierra el pendiente de decisión abierto el 2026-07-14: lo que ocurre
después de Venta es **un** proceso, no dos.

**Decisión y por qué.** `PROC-OPE-002 Cumplimiento de pedido` v1.0
Vigente, área **Operaciones** (cruza cocina de sucursal, atención al
cliente y reparto sin pertenecer a ninguna). Preparación y
Despacho/Entrega son etapas internas. Cuatro razones: (1) un solo
resultado — entra Orden de Pedido, sale pedido entregado — y ningún
artefacto de traspaso entre cocina y despacho; (2) el código ya lo modeló
como continuo: `venta_item.estado_preparacion` es UNA máquina de estados
y `kds_pantalla.tipo` (`preparacion`/`despacho`) es un filtro de vista
sobre ella, partirlo obligaba a partir la máquina y duplicar el contrato
del KDS; (3) "Producción" ya nombra la cocina de producción central
(`PROC-PRD-001`, primera cocina 2027) — reusarlo para la cocina de
sucursal rompe la regla de que la sigla nombra un área real; (4) mesa/
takeout/delivery son variantes de un mismo flujo, no procesos distintos.
No se pierde medición separada: `venta_item.updated_at` por transición ya
da tiempo de preparación y de despacho. Si el reparto llega a tener
ruteo, flota y liquidación propios, se separa entonces como v2.0.

**Especificación.** `process-nomenclature.md` (registro maestro + nota que
distingue `PRD` de la preparación en sucursal), `workflows.md` (sección
propia con gateway por modalidad; el borrador "fuera de Venta" se
reemplaza por un puntero), `use-cases.md` (CU-OPE-001/002/003 por
modalidad, con excepciones: cliente ausente, pedido no recogido, producto
rechazado), `business-rules.md` (**RN-CUP-001..012** nuevas; RN-COM-005
apunta al proceso; **RN-COM-007 reactivada** — la encuesta recupera su
disparador tras 13 días sin dueño), `state-machines.md` (la máquina pasa
de borrador a oficial, y se declara qué NO es estado: entrega fallida,
devolución y el pago al finalizar en mesa), `events.md` (filas de
`sales.venta_entregada` y `marketing.encuesta_enviada`), `data-model.md`
(entidad `entrega` especificada para el slice de delivery).

**Deriva corregida.** `sales.pedido_listo` se publicaba desde el slice KDS
(2026-07-25) sin fila en `events.md`, contra la propia regla del catálogo
("definir la fila ANTES de publicarlo"). Queda registrado.

**Código.** `sales/application/cumplimiento.py`: `registrar_entrega`
exige todos los ítems en `listo` (RN-CUP-005), es idempotente (repetirla
no reemite el evento) y publica `sales.venta_entregada` con modalidad,
cliente y plataforma de reparto. `POST /sales/ventas/{id}/entrega` con
permiso **propio** `sales.entregar_pedido` y rol nuevo `despachador`;
`cocinero` deliberadamente NO lo tiene (RN-CUP-006). En consecuencia el
bump del KDS ya **no** llega a `entregado`: devuelve 409 apuntando al
endpoint de entrega — antes cualquiera con `kds.operar` cerraba el pedido
ítem por ítem, lo que dejaba el permiso de entrega decorativo. Sin
migración: el enum ya tenía `entregado`.

**Fuera de esta fase, a propósito**: entidad `entrega` (trazabilidad del
repartidor y de la entrega fallida), plazo de espera de takeout
(RN-CUP-011) y BPMN del proceso — ver Deuda técnica → sales.

### 2026-08-03 — F0: Variantes y opciones (slice 5, ADR-023, migración `b6d1e83f47ac`)
Personal/Mediana/Familiar son productos hijos con receta y precio completo propios (RN-COM-022) — no un recargo sobre un precio base; el padre agrupa y no se vende. `producto_opcion_grupo` declara cuántos extras hay que elegir (RN-COM-023): `minimo >= 1` **es** ser obligatorio, sin flag aparte, y la regla se hace cumplir al confirmar la venta porque el kiosko entra por el mismo endpoint. Nombres normalizados a formato título en el servidor. Frontend: **Catálogo como módulo propio** (`/catalogo/productos`, no `/ventas`), con gate por permiso exacto `sales.gestionar_catalogo` — un cajero tiene `sales.crear` y con el filtro por prefijo veía y leía toda la carta; ahora el módulo no le aparece ni entrando por URL (enmienda a ADR-013). Ficha de producto que **elige** recetas ya creadas (el editor vive en Catálogo → Recetas; tenerlo en los dos lados hacía pensar que eran dos recetas distintas) y selector obligatorio de presentación + extras en el PDV.

### 2026-08-09 — F0: Consumo de personal (slice 6, ADR-034, migración `d5c81a7f3b62`)
La comida del staff en fines de semana, feriados y días de alta actividad es una orden de `tipo="consumo_personal"` con **todas sus líneas en cero** —ni lista de precios ni precio del cliente—, que se prepara y despacha como cualquier pedido pero **no se cobra ni emite comprobante** y cierra con la entrega (`estado="cerrada"`, su único cierre posible: nunca pasa por caja). **Cierre y trazabilidad en el turno** (2026-08-30): el ticket gana el botón **"Cerrar cuenta"** donde iría "Cobrar" —registra esa misma entrega, con la misma exigencia de tener todo `listo`—, la orden cerrada queda listada en la pestaña **"Cerradas"** del PDV (antes "Cobrados") sin monto y marcada como consumo, y `sales.consumo_personal_registrado` pasa a ser **emisión del catálogo de reportes** hacia Gerencia y Contabilidad. En la misma entrega, la firma del encargado deja de ser solo del alta: **cada aumento y cada línea quitada** de un consumo se firma, y ahí la ventana de corrección de 5 minutos no exime (las ventas normales no cambian). No se hizo con el descuento del 100% que ya existía porque esa venta declara un ingreso inexistente, la atribuye marketing y no se puede cerrar. La autoriza un encargado con PIN (`sales.registrar_consumo_personal`) y exige motivo de un enum cerrado. El costo sale de `inventory` como `consumo_interno`, valorizado al costo promedio, y `accounting` lo asienta como gasto de alimentación de personal; anularlo repone el insumo y reversa el asiento. Tests: `tests/test_consumo_personal.py`.

### 2026-08-09 — F0: Restas y lienzo de nodos (slice 7, ADR-035, migración `a4f1d0c8b573`)
Cierra el último tramo de RN-PRD-004 —tamaño → combinación → extras → **restas**—, el único que nunca se implementó. `venta_item.sin_articulo_ids` guarda qué insumos NO lleva la línea ("sin cebolla"): no cambia el precio, sí el consumo — `inventory` salta ese insumo y la reposición por anulación/nota de crédito devuelve solo lo consumido (RN-COM-028/RN-PRD-019). Lo quitable **es** la receta (`GET /productos/{id}/quitables`), sin tabla ni flag que mantener; pedir quitar lo que la receta no pone devuelve 409, salvo en el replay del hub. Cocina las ve en KDS y comanda (`SIN CEBOLLA`). Suma `DELETE /productos/{id}/extras/{extra_id}` y `DELETE /productos/{id}/grupos/{grupo_id}` (deuda de ADR-023). Frontend: **lienzo de nodos** a pantalla completa en `/catalogo/productos/{id}/nodos` — el árbol producto → tamaños → grupos → extras → restas → empaque → PLATO sobre un canvas oscuro con pan/zoom, minimapa y aristas curvas (`@xyflow/react`), editable en su estructura y con simulación en vivo de receta fusionada, costo y margen por combinación (la fusión se calcula en el cliente y no se guarda: lo que se descuenta sale del servidor). Vive fuera del shell del módulo, como PDV y KDS, así que hace su propio guard de permiso — con prueba e2e de que un cajero no entra ni por URL. La primera versión eran filas de `<div>` con líneas en CSS y la rechazó el usuario en el mismo día: el cambio de decisión está en la enmienda de ADR-035. Chips de "sin…" en el PDV, ticket y comanda. Tests: `tests/test_restas.py`.

### 2026-08-12 — F0: parches y correcciones varias del PDV/catálogo/KDS
**El PDV deja de pedir una caja ya abierta** (sin migración): `GET /accounting/cajas/abiertas` exigía `accounting.leer` —el permiso de todo el módulo contable, que el rol `cajero` no tiene ni le corresponde—, devolvía 403, y el PDV lo leía como "no hay caja": pedía la apertura y la apertura rebotaba por duplicada. Ahora acepta `sucursal_id` y con ese alcance basta `accounting.caja_operar`, validado contra el tenant (ADR-004) y no contra el parámetro; sin él sigue siendo la empresa entera con `accounting.leer`. La caja es del **punto de venta**, así que el turno que abrió un compañero vale para todo el local.

**La pizza se puede vender** (ADR-038, sin migración): `GET /carta` armaba los grupos de opciones leyendo el producto **padre**, pero cuelgan de la **variante** —que es la que se prepara (RN-COM-022/023)—, así que la carta devolvía `extras: []`, el PDV no dibujaba "Sabor", habilitaba Guardar sin elegirlo y el servidor rechazaba con 409 algo que la pantalla nunca ofreció; sin venta confirmada tampoco llegaba comanda al KDS. Ahora cada variante viaja con su `extras[]` (aditivo) y el PDV ofrece los de la presentación elegida, que son exactamente los que el servidor acepta. El hub no necesita nada: replica las tablas crudas y arma la carta con este mismo código.

**La orden enviada sigue viva** (ADR-043, RN-COM-029, sin migración): admite líneas nuevas (`POST /ventas/{id}/items`, mismo permiso que crear y sin firma de nadie — la mesa que pide de a poco no tiene por qué terminar con dos cuentas) y **quitar es gratis dentro de 5 minutos**; pasada la ventana lo firma un supervisor (RN-COM-020). Antes agregar era imposible y quitar exigía el PIN siempre, con lo que el control se ejecutaba veinte veces por turno y terminaba en la sesión del encargado abierta en la caja. La ventana de la orden se mide contra su **última** línea, y un lote necesita firma si **alguna** salió de ella. El agregado republica `sales.venta_confirmada` con **el incremento** y no con el acumulado: así inventory descuenta solo lo nuevo y accounting no asienta la venta dos veces. En el PDV, además, el "+" reusa el borrador vacío en vez de apilar pestañas y una pestaña sin líneas se descarta con su "×".

**La variante hereda del padre** (ADR-042, sin migración): el arreglo anterior servía para el catálogo del **seeder** —grupos en la variante— y dejaba roto el armado **a mano**, porque el lienzo cuelga "+ grupo" del nodo activo, que es el padre mientras el producto no tiene tamaños. Ahora una variante ofrece lo suyo **más lo del padre** (`grupos_efectivos`/`extras_efectivos`/`admite_extra_efectivo`, con el vínculo propio ganando sobre el heredado), y la venta acepta exactamente lo que la carta ofreció: dónde quedó colgado el grupo dejó de decidir nada.

**El cajero anula una orden enviada** con firma de supervisor: `sales.anular` es de supervisor y el botón del PDV devolvía 403 sin decir qué hacer, dejando el pedido en cocina. El endpoint entra con `sales.cobrar` **o** `sales.anular` —son roles disjuntos, exigir los dos dejaba afuera a los dos— y al que solo cobra le pide la elevación por PIN, igual que para quitar una línea (RN-COM-020).

**Pestaña de cuentas abiertas** en el PDV: estaba como nota al pie del mapa de mesas y filtraba fuera las de mesa, así que "¿qué falta cobrar?" no se podía responder de un vistazo.

**El lienzo se cablea de verdad** (tercera enmienda de ADR-035): `conectar()`/`desconectar()` estaban escritos, probados y enchufados, pero todos los `<Handle>` llevaban `isConnectable={false}` y react-flow no deja ni empezar el arrastre — era código inalcanzable. Además: una opción nueva se crea con su receta **desde el lienzo** (antes había que recorrer dos pantallas antes de poder colgarla), el grupo se retira desde su nodo (`BorrarGrupo` existía sin estar montado en ninguna parte) y un `<button disabled>` dejaba de tragarse los clicks de "receta" y "quitar".

### 2026-08-13 — F0: Cocina por estaciones, pinpad y comanda tabulada
**La cocina es una cadena de estaciones** (ADR-044, RN-CUP-013, migración `b2e91f7c40aa`): el KDS ruteaba **solo por categoría**, así que la pizza aparecía a la vez en armado y en horno, cualquiera podía tacharla y tacharla la dejaba `listo` sin haber pasado por el horno; despacho, además, era el mismo componente con otro filtro y ofrecía tachar ítems en vez de decir qué falta. Ahora cada estación tiene un paso (`kds_pantalla.orden`) y cada línea sabe en cuál va (`venta_item.etapa_kds`); todo lo resuelve una sola función —`_estacion(cadena, producto, desde)`— que dice **qué muestra una pantalla** y **a dónde va al tacharla**, porque cola y avance que discrepen dejarían líneas invisibles en cocina. Busca la primera estación con `orden >= desde` y no la exacta: desactivar el horno a media noche hace que su carga caiga al eslabón siguiente en vez de desaparecer. Una bebida se salta el horno sola —el horno no atiende su categoría— sin configurar excepciones, y `estado_preparacion` no cambia. `orden` viaja en la réplica del hub (sin él, durante un corte todas las estaciones caerían al mismo eslabón); `etapa_kds` no, porque el push replaya la venta como un `POST /ventas` nuevo y el avance de cocina ya era local por diseño. **Despacho pasa a pantalla propia**: tarjeta por pedido con cuántas líneas van, en qué estación está cada una y por quién se espera; solo entrega. De paso, la cola volvió a llevar `tipo` y `consumo_motivo` — el `response_model` los filtraba en silencio y el aviso de consumo de personal que la pantalla tenía escrito no se mostró nunca.

**Pinpad y bloqueo de pantalla del PDV** (ADR-045, RN-POS-014, sin migración): los cuatro sitios que piden PIN usaban un `<input type="password">`, el navegador ofrecía guardarlo y con el PIN guardado en la caja el turno siguiente entra con la cuenta del anterior —toda la auditoría de RN-AUD-005 nombrando a la persona equivocada—; ahora se teclean en un teclado numérico **sin campo de formulario**, que es lo que no se puede guardar. Y la pantalla se bloquea a los 5 minutos sin cerrar sesión: la caja abierta y el pedido a medio armar siguen donde estaban, porque un bloqueo que hiciera perder el pedido se eludiría dejando la pantalla tocada a propósito. Se reabre con `POST /auth/verificar-pin` —nuevo: `login` rotaría la sesión y `autorizar` está para elevar a otro (RN-AUD-005)—, detrás del mismo rate limit y contra el **mismo lockout** que el login. El overlay es un `<dialog>` con `showModal()` porque nada con `z-index` tapa el top layer, y el plazo se mide con un latido contra una marca de tiempo porque una tablet con la pantalla apagada estrangula los temporizadores largos. Fuera del PDV no cambia nada.

**El sabor dejó de contarse como un plato aparte** (RN-CUP-014, enmienda de ADR-044, sin migración): una *Pizza Personal Peperoni* salía en la tarjeta del KDS como dos ítems y en despacho contaba «2 de 2» por una sola pizza. El extra es fila propia de la venta —receta, precio y rastro al anularse— pero `kds.py` no mencionaba `padre_venta_item_id` en ninguna parte y aplanaba. Ahora viaja anidado y se muestra tabulado bajo su plato como ya se mostraban las restas, la comanda impresa lo sangra, el ruteo por estaciones mira la categoría **del plato**, y marcar el plato marca sus extras: sin esa cascada `pedido_entregable` —que suma todos los ítems— habría dejado el pedido sin poder entregarse jamás. De paso cierra dos agujeros que solo se ven en la base real: un extra **sin categoría** no lo atendía ninguna estación filtrada, así que se quedaba `pendiente` para siempre (el caso de todos los extras del seeder); y **anular un plato con extras** reventaba contra Postgres —`fk_venta_item_padre` es `NO ACTION` y el PDV manda solo el id del padre— además de no reponer el insumo del sabor. El fixture de `test_pdv_slice` pasa a encender `PRAGMA foreign_keys=ON`: SQLite las trae apagadas y por eso toda la suite pasaba en verde sobre un FK que producción sí hace cumplir.

### 2026-08-24 — F0: Cupón de promoción y landing pública (ADR-062, migración `a7c3e1f508b2`)
La campaña «Queremos RE-conocerte» — un QR en la mesa lleva a `/reconocerte`, el cliente deja DNI, cumpleaños, dirección y teléfono **sin cuenta**, y se lleva un cupón de 10 % de un solo uso que la caja canjea con `POST /sales/ventas/{id}/cupon`. Vive en `sales` y no en `marketing` porque sus dos operaciones son escrituras acá —crear o encontrar el `cliente`, descontar la `venta`— y un módulo solo entra a otro por `api.deps` o `queries_publicas`, que son de lectura: ponerlo allá exigía ampliar las excepciones cruzadas de `test_arquitectura`, que es la deuda que esa lista existe para no seguir acumulando. Marketing se entera por `sales.cliente_registrado_en_promocion` y crea su `lead`. Reusa `clientes.crear_cliente` entero, con su consulta a RENIEC y su fallback (RN-PTS-004), y reconoce por documento **o por teléfono** para no duplicar a la media base que se dio de alta en caja sin DNI. El descuento reusa `venta.descuento_*` con motivo nuevo `cupon` —un canal paralelo obligaba a tocar `total_a_cobrar`, el prorrateo SUNAT del comprobante y las notas de crédito— y el motivo propio es lo que deja al reporte separar el margen regalado a criterio del prometido en campaña; **el motor de promociones condicionales sigue sin poder reusarlas**. El canje **no pide PIN de supervisor** (a diferencia de RN-COM-017): el cupón ya era del cliente y es la autorización. La superficie pública **escribe pero no borra** —la baja va por `hola@majambo.com.pe` y la anonimización de ADR-011—, su consulta devuelve solo `{registrado: bool}`, y el `grupo_id` sale de la promoción activa y nunca del request. Lo único que la protege es el rate limit por IP, con el techo más duro (5/h) en el endpoint que convierte un DNI en un nombre, que es el que permitiría enumerar documentos. El código del cupón **es el DNI** (lo pidió el negocio): el cliente no guarda nada, y el costo —quien sepa un DNI ajeno puede intentarlo— se acota atándolo al cliente de la venta. Terminar la campaña es `POST /sales/promociones-cupon/{id}/termino` con `sales.gestionar_promociones`, y **no toca los cupones ya entregados**. Frontend: `frontend/app/(publico)/` — el primer grupo de rutas sin guard de sesión, con la voz de marca de Charlie's, el logo de Majambo en el pie y los términos completos. Los logotipos de `frontend/public/marcas/` son **provisionales**: reemplazar el archivo con el mismo nombre y listo. Sin pantalla de back-office ni QR generado por el ERP (decisión del usuario). Tests: `tests/test_cupones.py`.

### 2026-08-24 — F0: KDS pasa a administración (ADR-065, migración `c4d17b93e0af`)
**Montar una pantalla KDS pasa a ser acto de administración**: `kds.configurar` sale del rol `supervisor` —dar de alta, renombrar o borrar una estación cambia por dónde pasa la comanda de **todos** los turnos, no solo del que está en el local esa tarde, y eso es alta de infraestructura como el punto de venta (ADR-059)—; el supervisor conserva `kds.operar`. Aparece por fin `DELETE /kds/pantallas/{id}`: el modelo tenía `deleted_at` desde que nació y **ningún camino lo escribía**, así que una estación creada con un error de tipeo se quedaba para siempre. Es baja lógica y devuelve 409 si la pantalla tiene cola (borrarla con pedidos encima dejaría esas líneas sin dónde tacharse); `activo=false` sigue siendo el apagado temporal. El `UNIQUE (sucursal_id, nombre)` pasa a **parcial** sobre las vivas —con el plano, el nombre de una borrada quedaba tomado para siempre—. Y `GET /kds/pantallas` acepta `kds.operar` **o** `kds.configurar`: quien administra tenía que poder ver lo que administra. `punto_venta` **no** recibe DELETE: tiene series SUNAT y darlo de baja es identidad fiscal (anotado en Deuda técnica).

### 2026-08-25 — F0: El comprobante se imprime en la ticketera de 80 mm (ADR-067, sin migración)
Hasta hoy el ERP **no tenía modelo de boleta ni de factura** — lo único imprimible era el PDF de Factiliza, cuyo diseño decide el proveedor y que hay que bajar y abrir en un visor, o sea el diálogo que la caja no quiere ver. Ahora `GET /sales/comprobantes/{id}/ticket` arma la representación impresa: membrete de marca, ítems con precio, desglose de impuestos, total en letras y el **QR de la RS 097-2012** (`domain/qr_sunat.py`, nueve campos separados por `|`; el QR es dominio y no integración porque lo manda SUNAT, cambiar de proveedor no lo cambia). **No recalcula nada**: lee el mismo payload que se le manda a Factiliza, así que el papel y el XML no pueden discrepar en un céntimo de redondeo, y el papel es lo que el cliente se lleva. Sale **aunque SUNAT no haya contestado** —la emisión es asíncrona a propósito (RN-COM-003)— con la franja `PENDIENTE DE ENVÍO A SUNAT`. **Un solo ancho de papel**: todas las ticketeras del grupo son de 80 mm, pero la comanda salía a 32 columnas (58 mm) y la precuenta a 40 — tres documentos del mismo local con tres márgenes y un tercio del rollo en blanco en cocina; ahora las 48 columnas viven en `src/shared/impresion.py` y las comparten los tres, con el mismo membrete. Lo **configurable por marca** (logo y líneas del pie) va en `marca.skins["ticket"]`, la columna JSONB que ya existía para el branding del PDV: sin tabla ni migración. Razón social, RUC, domicilio fiscal y sucursal salen del padrón y **no se teclean por local** — un local que escribe su propio encabezado termina imprimiendo el RUC de la empresa equivocada, y eso en una boleta es un problema fiscal, no de diseño. Frontend: botón en PDV → Cobrados (comprobante) y en PDV → Cuentas (comanda, que suma al contador de reimpresiones y queda auditada), y pestaña nueva **Contabilidad → Comprobantes** con el registro de ventas, su importe, su estado ante SUNAT, reimpresión y descarga de PDF/XML. `GET /sales/comprobantes` acepta `sales.leer` **o** `accounting.leer`: el contador tiene que ver el documento fuente del asiento sin que haya que darle el módulo de ventas entero (mismo patrón que ADR-065 con las pantallas KDS). La impresión **sin diálogo** no es código sino la bandera `--kiosk-printing` del navegador, documentada en `docs/engineering/impresion-termica.md`; el agente ESC/POS —corte, cajón, campana— sigue en Deuda técnica, igual que la representación impresa de la nota de crédito. De paso cierra un bug que solo se ve con el QR encima: `_documento()` declaraba `fecha_Emision = now(UTC)`, así que un comprobante que se quedó en la cola y salía al día siguiente le declaraba a SUNAT una fecha que la venta nunca tuvo, y `now(UTC)` además corría el calendario (una venta de las 20:00 en Tarapoto es del día 25, en UTC ya es 26). Ahora es `created_at` leído en `America/Lima`. Una dependencia nueva: `segno` (Python puro, sin dependencias propias). Tests: `tests/test_ticket_impresion.py`.

### 2026-08-26 — F0: Cocina que se puede corregir
La pantalla de preparación pasa a **dos toques** —uno marca `en_preparacion`, el otro manda la línea a la estación siguiente—, porque uno solo encadenaba los dos pasos y el roce de un delantal contra la tablet despachaba un plato que nadie había empezado. **RN-CUP-002 enmendada**: deshacer existe, es de a un paso y tiene puerta propia (`POST /kds/items/{id}/retroceder`); `/avanzar` sigue siendo estrictamente hacia adelante. Suma **historial de entregas** (`GET /kds/pantallas/{id}/historial`, lo del día de negocio) y `POST /sales/ventas/{id}/deshacer-entrega` con el mismo permiso que entregar, para el toque sobre la tarjeta de al lado en despacho. **Semáforo de espera** (`application/kds_semaforo.py`, pantalla `/gerencia/kds`): la cocina no tenía **ninguna** noción de tiempo —un pedido de hace cuarenta minutos se veía igual que uno recién tomado— y ahora cada tarjeta lleva su reloj y cambia de color a los minutos que Gerencia apruebe; el reloj lo corre el navegador a partir de `creado_en`. Y **la sucursal del KDS ya no es `usuario.sucursales[0]`**: viaja en la URL como la estación, así que quien tiene dos locales asignados puede llegar al segundo, y una pantalla se puede mudar de sucursal con `PATCH` (409 con cola o con el nombre ocupado). **El reparto se cobra en múltiplos de S/ 0.50** (RN-COM-042), redondeando por cercanía: base más kilómetros daba S/ 8.71 y el repartidor no lleva monedas de un céntimo.

### 2026-08-27 — F0: Las mesas se configuran y tienen plano (ADR-069, migración `a1f9c3e7b204`)
ADR-018 había creado `mesa` pero solo el seeder podía darla de alta —`numero` lo mandaba el cliente, no había `PATCH`, y la única baja apagaba `activa` sin mirar si tenía historia—, así que una sucursal nueva se quedaba con el PDV diciendo "esta sucursal no tiene mesas configuradas todavía" sin salida. Ahora **el número lo asigna el sistema** (RN-MDC-004): `crear_mesa` calcula `max(activas) + 1`, nunca se edita, y **solo se retira la mesa de número más alto** (RN-MDC-006) — renumerar el resto reescribiría a qué mesa apuntó una venta ya cerrada, y dejar un hueco rompía el 1..n pedido. Una mesa sin ventas se borra de verdad; una con ventas queda `activa=False` conservando su número, que la próxima mesa creada reactiva en vez de insertar una fila. Ni editar ni retirar proceden con una orden abierta (RN-MDC-005), sin importar la fecha —el control original de ADR-018 solo miraba las órdenes de hoy. Suma `pos_x`/`pos_y`: la celda de un **plano en grilla de 12 columnas** (`rules.MESA_COLUMNAS`), no coordenadas en píxeles — el mapa del PDV y la pantalla nueva `/ventas/mesas` pintan la misma grilla vía `gridColumn`/`gridRow`. `DELETE /sales/mesas/{id}` reemplaza `POST /mesas/{id}/desactivar`, que no tenía llamadores en el frontend y era la única de las cuatro rutas sin `tenant.exigir_sucursal` —un supervisor podía tocar la mesa de otra empresa por id—; la nueva pasa por `scope.exigir_mesa`. Se quita `mesa.deleted_at`: `SoftDeleteMixin` no tenía ninguna escritura desde que la tabla existe, dos fuentes de verdad para el mismo borrado con el mismo riesgo que describe ADR-018 para `mesa.ocupada`. Suma al catálogo de reportes (ADR-024) **`mesas_preferidas`**: qué mesa pide más el cliente por sucursal, reusando `_ventas_en_rango` para no contradecir a los demás reportes del mismo rango. Frontend: `/ventas/mesas` (crear, editar zona/capacidad, arrastrar en el plano, retirar), copiado del patrón de `/organizacion/puntos-venta` pero con permiso `sales.gestionar_mesas` — configurar el salón no es identidad fiscal del local. Diferido: el plano es uno solo por sucursal y no separa por `zona`; `mesas.mapa()` sigue siendo N+1 sobre los ítems de cada venta abierta (ya lo era desde ADR-018). Tests: `tests/test_mesas.py`, `tests/test_pdv_slice.py`.

### 2026-08-27 — F0: Mover productos entre pedidos y cobrar seleccionados (RN-COM-043, ADR-071, sin migración)
La selección múltiple del PDV (mantener presionado un producto) y el `grupo_cobro` del cobro dividido (ADR-018) ya existían, pero nada los conectaba y no había forma de corregir un producto cargado en la mesa equivocada. `POST /ventas/{id}/mover-lineas` reasigna líneas ya enviadas a otra orden abierta, a una mesa libre, o a otra cuenta de la misma orden — un solo caso de uso para "mover productos" y "cobrar seleccionados". Sin PIN de supervisor (el producto sigue existiendo en alguna orden que se va a pagar o a anular) y sin publicar eventos de `inventory` (el insumo no se movió del almacén). `estado_preparacion`/`etapa_kds` viajan con la línea: lo ya cocinado no se recocina en la orden destino. No genera asiento de reclasificación —origen y destino asientan contra las mismas cuentas— ni viaja todavía por el hub offline (ver Deuda técnica).

### 2026-08-27 — Landing pública del QR con dominio propio (ADR-080)
`clientes.majambo.com.pe`, resolviendo el "Pendiente de decisión": el QR de la mesa apuntaba a `staging.majambo.com.pe/reconocerte` — un nombre que dice «staging» y cuya raíz es el ERP entero. El recorte va en el `Caddyfile` —no en `middleware.ts`, cuyo `matcher` excluye los prefetch y dejaría el guard esquivable con una cabecera— y solo deja pasar `/reconocerte*`, `/_next/static/*`, `/_next/image*`, `/marcas/*` y el favicon; el resto redirige 302 a la landing. Verificado con `caddy validate` + `caddy adapt` y un Caddy local contra el dev server: las dos trampas de sintaxis que caza ese paso (`redir` sin `*`, orden de los `handle`) producen configuraciones **válidas** que hacen otra cosa. **No es un control de seguridad** y **no es el padrón real**: `/login` sigue público en el otro dominio, y lo que se registre cae en la base desechable de staging. Nada de esto llega al droplet hasta que alguien copie el `Caddyfile` a mano — ver `staging.md` y `deuda/ci-cd.md`.

### 2026-08-22 — Google Maps: dirección anclada y delivery cobrado por kilómetro (ADR-053/054, ADR-068, ADR-072)
**Google Maps — la dirección se ancla y el delivery se cobra por kilómetro** (migraciones `c3d8b1f47a95` y `d41f6a2c98b7`). Una dirección era `String(255)` en seis lugares y nada más: nadie validaba que existiera, nadie podía navegar hacia ella, y **la dirección de delivery que el cajero tecleaba se perdía** — vivía solo en el borrador del navegador y `venta` no tenía columna que la recibiera. Ahora `UbicacionMixin` suma `place_id` + lat/lng + plus code + distrito a `sucursal`, `almacen`, `empresa`, `persona`, `proveedor` y `venta`, con un campo único (`components/direccion/campo-direccion.tsx`) que autocompleta con Places y deja arrastrar el pin. **Editar el texto a mano suelta el ancla** en las dos puntas (`shared/ubicacion.py` manda; el frontend solo acompaña): un texto que diga una calle con las coordenadas de otra manda el reparto al lugar equivocado. El mapa lo dibuja el navegador con clave restringida por dominio —los tokens de sesión de Places son lo que abarata la factura y no tienen versión server-side—, y por eso la CSP suma hosts de Google por primera vez. **Lo que define plata NO sale del servidor**: la distancia de reparto la mide la Routes API con una segunda clave restringida por IP, con cuota por usuario e IP como la consulta de documento, y el costo se **congela** en la venta. Pasado el radio o en distrito vetado se sugiere **DAZ DAZ** sobre el campo `repartidor_externo_plataforma` que ya existía — cero tablas nuevas. Google caído cae a haversine×1,3 marcado «aprox.» y el pedido se toma igual; sin claves el ERP se comporta exactamente como antes (lo verifica `frontend/uso/direccion.spec.ts`, que corre **sin** clave a propósito). Tests: `tests/test_ubicaciones.py`, `tests/test_tarifa_delivery.py`.

**2026-08-25 (ADR-068, RN-COM-040) — estaba construido y nadie podía usarlo.** Tres meses después de mergeado, la respuesta del negocio fue «eso no está disponible», y ninguna causa era de dominio: la tarifa vivía en el `.env` (así que cambiarla exigía redesplegar y los tres valores siguieron en `0`), el reparto **se calculaba y no se cobraba** —desde caja eso se lee como que el PDV está roto—, y sin claves de Google todo se degrada **en silencio**, que frente al cajero es correcto y frente a Gerencia es una pantalla que miente. Ahora los cuatro números son `parametro_empresa` del módulo `sales` y los fija Gerencia en **`/gerencia/delivery`**, con `settings.delivery_*` degradado a semilla: sigue arrancando apagado, pero encenderlo ya no es un despliegue. Pasa por la aprobación de ADR-014 como cualquier parámetro —acá se define cuánta plata paga el cliente—. `total_a_cobrar` suma `costo_entrega` **después** del descuento manual, un consumo de personal no lo paga y no se prorratea entre cuentas separadas; **sin línea de venta**: crear un producto de servicio «Delivery» para mover un número que ya tiene su columna no compra nada hoy. `GET /sales/delivery/configuracion` devuelve la tarifa **efectiva** (no la propuesta) más `activa` y `rutas_reales`, que es lo que hace que la pantalla avise cuál clave falta. **Sin migración**: `parametro_empresa` existe desde ADR-014. **Y la clave del mapa no llegaba al frontend fuera de desarrollo**: `docker-compose.staging.yml` y `docker-compose.prod.yml` no le declaraban ninguna `GOOGLE_MAPS_*` al servicio `web`, así que el `.env` del servidor podía tenerla y el proceso de Next no la veía — sin buscador, sin mapa y sin punto que medir. `.env.staging.example` además traía `GOOGLE_API_KEY=`, que no la lee nadie, y ninguna de las que sí se leen; `frontend/.env.example` no existía. Ese era el otro motivo real del «no está disponible». El PDV además cotiza **sin ancla**: sin clave de Maps ninguna dirección tiene punto, y callar la tarifa base le mostraba al cajero un total menor que el cobrado (esa llamada no toca a Google). Tests: `tests/test_tarifa_delivery.py` (+5), `tests/test_pdv_slice.py` (+4), `frontend/lib/reparto.test.ts`, `frontend/uso/delivery-gerencia.spec.ts` (poner la tarifa, aprobarla y cobrarla en el PDV). **Y el buscador nunca podía encenderse, con clave o sin ella**: el `<div>` que aloja el widget de Google solo se dibujaba si `conMapa` ya era `true`, pero el efecto que activa `conMapa` necesita que ese mismo `<div>` ya exista para engancharle el buscador — huevo y gallina, desde que se construyó ADR-053. Se detectó depurando staging: SDK en `200`, `window.google.maps` poblado en consola, y la pantalla seguía diciendo «no disponible». `campo-direccion.tsx` deja de condicionar ese `<div>` a `conMapa`.

**2026-08-27 (ADR-072) — y todavía no encendía: era una carrera en la carga del SDK.** Tercera vuelta sobre el mismo síntoma. `cargarMaps` resolvía en cuanto existía `window.google.maps`, pero ese objeto aparece **antes** de que el bootstrap de `loading=async` defina `importLibrary`, así que el llamador recibía un namespace a medio armar y moría con «maps.importLibrary is not a function» — dentro del `.catch()` mudo de `CampoDireccion`, o sea con el mismo aspecto que no tener clave. Ahora se espera a que `importLibrary` exista y se sondea en vez de escuchar `load` (un `<script>` ya cargado no vuelve a emitirlo, y reusarlo dejaba la promesa esperando para siempre en cada recarga en caliente). **La causa de que costara tres intentos no es técnica: el `catch` no decía nada**, así que cuatro fallas distintas —sin clave, clave restringida a otro dominio, SDK a medio cargar, huevo y gallina del `<div>`— se veían todas como un cuadro de texto pelado. Ahora escribe el motivo en consola. Es la lección de ADR-068 §3 en su forma más cara. Tests: `frontend/lib/google-maps.test.ts`. Diferido: tarifa por sucursal, zonas por polígono, el reparto como línea del comprobante.

### 2026-08-23 — Catálogo modelo Odoo (0.7.0, en curso)
Rama `feat/catalogo-odoo`, sobre v0.6.0. El catálogo pasa al modelo de
atributos y variantes de Odoo 18 porque el actual no soporta el carta real de
Charlie's: una `Pizza MitadxMitad Familiar` de 19 sabores por mitad son 361
productos con 361 recetas.

| Fase | Qué | Estado |
|---|---|---|
| F1 | Modelo, migración aditiva `e2b7c40d91af`, reglas puras | ✅ 2026-08-23 |
| F2 | Explosión de receta condicionada, venta, eventos, sync | ✅ 2026-08-23 |
| F3 | Conversor y cargador del catálogo de Odoo (`scripts/odoo/`) | ✅ 2026-08-23 |
| F4 | Matriz de recetas (ADR-057) | ✅ 2026-08-23 |
| F5 | Lienzo sobre el modelo de atributos (ADR-058) | ⛔ superada 2026-08-24 (ADR-063) |
| F6 | Seeder desde los `.xlsx` reales, corte 0.7.0 | ⏳ |
| F7 | La condición de una línea se lee y se edita en el lienzo | ⛔ superada 2026-08-24 (ADR-063) |
| F8 | Los atributos vuelven a la tabla: pantallas + generador de variantes (ADR-063) | ✅ 2026-08-24 |

**F5 y F7 quedaron sin efecto el mismo día que se cerraron**: el lienzo no
resultó un lugar de trabajo usable — el usuario seguía sin poder ver ni crear
atributos — y se reemplazó entero por `/catalogo/atributos` + la sección
«Atributos» de la ficha del producto + la columna «Condición» del editor de
receta. F8 cubre lo mismo que F5/F7 prometían, con tablas, y suma el
generador de combinaciones que F5 había dejado pendiente (`modo_variante =
'siempre'`; `'dinamica'` sigue sin construirse, ver deuda técnica).

**Vuelta atrás**: la migración de F1-F4 es solo aditiva, así que la imagen
0.6.0 corre contra ese esquema sin enterarse. F8 rompe esa promesa para
`producto_comercial.lienzo_pos` (migración `ce32c6610eb7`, la borra): volver
a una versión anterior a F8 exige `alembic downgrade` explícito, ya no basta
con `./scripts/desplegar.sh 0.6.0`.

### 2026-08-28 — Parche del PDV — hallazgos del turno de prueba (0.7.8)
Se probó el PDV en producción con dos usuarios nuevos de trabajadores en CH1
y CH2, y salieron doce cosas. Tres causas raíz explican la mitad: el frontend
nunca renovaba el token, el PDV leía su sucursal del JWT congelado, y el
borrador no existía fuera de la memoria del navegador.

| Tanda | Qué | Estado |
|---|---|---|
| 1 | Sesión que se renueva sola + sucursal fresca con selector (ADR-073) | ✅ 2026-08-28 |
| 1 | Borrador del PDV en el servidor (ADR-074) | ✅ 2026-08-28 |
| 1 | El aumento es una tanda propia en el KDS (ADR-075) | ✅ 2026-08-28 |
| 1 | La cuenta de mesa recuerda su número (`VentaOut.mesa_numero`) | ✅ 2026-08-28 |
| 1 | Apertura/cierre de caja sin texto montado; el PDV cabe en la ventana | ✅ 2026-08-28 |
| 1 | Bloqueo manual de la pantalla (RN-POS-014) | ✅ 2026-08-28 |
| 1 | Alta de cliente con solo DNI, y reuso si esa persona ya es cliente | ✅ 2026-08-28 |
| 2 | Pantalla de despacho como overlay dentro del PDV | ✅ 2026-08-28 (salida rotulada «Volver al PDV» el 2026-08-30: la × sin etiqueta no se leía como la vuelta) |
| 2 | Cupón y descuento manual en caja (backend ya existía, faltaba el PDV) | ✅ 2026-08-28 |
| 2 | Notas de cocina: por línea **y** una general del pedido, al pie de la pastilla del KDS | ✅ 2026-08-28 |
| 3 | Motor de promociones automáticas + su pantalla en el back office (ADR-076) | ✅ 2026-08-28 |

La tanda 3 es un slice, no un parche: el motor de promociones condicionales
no existe —lo que hay es `promocion_cupon` (ADR-061), que hace otra cosa— y
tiene que soportar N×M, X unidades de un producto o categoría, combo, monto
mínimo y vigencia por día/hora. **No puede escribir en `venta.descuento_*`**:
esos campos son el acto humano firmado, y mezclarlos haría imposible auditar
qué descuento fue manual y cuál automático.

### 2026-08-29 — Parche desplegables con búsqueda (versión a definir, en curso)
*Nota: patrón transversal de frontend (combobox de búsqueda para 62 `<select>` alimentados por API en toda la app), pero el disparador y buena parte del alcance son de `sales` (promociones). Ver también `modulo-inventory.md`/`modulo-purchases.md`/`modulo-accounting.md` para las listas de esos módulos que también se migraron.*

Nota de versión: al escribir esto se apuntó a "0.8.2", pero para cuando se
integró con `main` esa versión ya la había cortado otra rama con contenido
no relacionado (landing con dominio propio, marcaje de asistencia) y `main`
ya iba en 0.9.0. El corte de versión de este parche queda pendiente — se
hace al mergear, contra la versión real que tenga `main` en ese momento.

Reportado desde el uso: crear una promoción pedía teclear los identificadores
de los productos y categorías separados por coma. El campo era inusable —nadie
se sabe un UUID— y fallaba en silencio: un id mal copiado creaba la promoción
apuntando a un producto inexistente, que simplemente no se aplicaba nunca.

Al revisarlo, el problema era más ancho: **114 `<select>` en 50 archivos y
ninguno con búsqueda**. Y como `PAGE_SIZE_DEFECTO` es 50 y ningún `page.tsx`
pide más, varios desplegables muestran solo la primera página del catálogo sin
avisar que hay más — eso ya no es incomodidad, es un dato que falta.

Se migran los **62** desplegables alimentados por la API. Los 52 restantes son
enumerados escritos en el código —estados, tipos, modalidades, paginación— y
siguen siendo `<select>` nativos: ponerle un buscador a tres opciones estorba.

| Fase | Qué | Estado |
|---|---|---|
| 1 | `components/ui/combobox` (búsqueda, selección múltiple con fichas) sobre Base UI, con el filtrado en `lib/filtrar-opciones` | ✅ 2026-08-29 |
| 1 | Promociones: productos, categorías y el producto gratis dejan de pedir ids a mano | ✅ 2026-08-29 |
| 1 | `GET /inventory/articulos?q=` — el único catálogo que no entra completo en una página | ✅ 2026-08-29 |
| 2 | Listas largas (artículos, recetas, cuentas contables, proveedores) + `page_size` explícito donde hoy se trunca | ✅ 2026-08-29 |
| 2 | `?tipo=` repetible en artículos: "qué se produce" son subrecetas **y** mercadería | ✅ 2026-08-29 |
| 3 | Listas acotadas (sucursales, almacenes, marcas, unidades de medida, roles, grupos, divisas, atributos) | ✅ 2026-08-29 |
| 3 | Ayudante `elegirEnLista` en `e2e/util`: las pruebas dejan de hablar `selectOption` | ✅ 2026-08-29 |

Quedan **52** `<select>` nativos y son todos de enumerados escritos en el
código. No es deuda: un buscador sobre tres opciones estorba.

Decisión: el filtrado ocurre **en el cliente**, sobre lo ya cargado. Solo los
artículos buscan contra el servidor, porque son los únicos que no caben en el
techo de 200 filas por página. Añadir `?q=` a los otros tres endpoints que se
habían previsto resultó innecesario: SKUs y cuentas contables se devuelven sin
paginar y proveedores entran de sobra.

### 2026-08-28 — Parche 0.8.1 — segundo turno de prueba en staging
Con la 0.8.0 ya en staging, el turno reportó seis cosas. Cinco son agujeros
que abrió la propia 0.8.0 —las notas de cocina estiraron las tarjetas del
KDS, los cupones y descuentos metieron una diferencia entre el total del
navegador y el del servidor, el overlay de despacho dejó al KDS suelto sin
salida— y la sexta, el cobro que rechazaba el monto exacto, llevaba ahí
desde que existe el cobro.

| # | Qué | Estado |
|---|---|---|
| 1 | El pedido sale de la cola de cocina al entregarse, no al facturarse; y la categoría sin estación cae en la primera (ADR-078) | ✅ 2026-08-28 |
| 1 | El aumento se vuelve idempotente (`venta_item.idempotency_key`) | ✅ 2026-08-28 |
| 2 | La plata se cuantiza a centavos en `rules.a_centavos`, en dominio y frontend | ✅ 2026-08-28 |
| 2 | El saldo lo dice el servidor: `GET /ventas/{id}/saldo` | ✅ 2026-08-28 |
| 2 | El efectivo admite sobrepago y el vuelto se guarda (`pago.vuelto`, ADR-077) | ✅ 2026-08-28 |
| 3 | `GET /ventas/{id}/comprobantes`: uno por cuenta, imprimibles desde el PDV | ✅ 2026-08-28 |
| 4 | Salida del KDS en las cuatro pantallas (el overlay del PDV sigue con su ×) | ✅ 2026-08-28 |
| 5 | Techo a la tarjeta del KDS: solo scrollea la lista, el pie queda a la vista | ✅ 2026-08-28 |
| 6 | Despacho lee el estado de la línea, no la ausencia de estación; lo listo se agrupa arriba | ✅ 2026-08-28 |

Lo que **no** se hizo y se decidió no hacer: entrega parcial de líneas. La
unidad de despacho sigue siendo el pedido (ADR-044, RN-CUP-004) — la
trazabilidad que pedía el mozo se resuelve mostrando qué está listo, no
partiendo la bolsa. Y el comprobante sigue siendo por cuenta y no por pago:
un pago parcial no tiene líneas propias que declarar a SUNAT.

### 2026-08-29 — Parche compras/inventario (referencia parcial: visibilidad del descuento de stock)
*Nota: este parche es principalmente de `purchases`/`inventory` — ver `modulo-purchases.md`/`modulo-inventory.md` para el detalle completo. Se apunta aquí solo el ítem que toca ventas.*

Reporte del usuario: no se podía crear un borrador de OC, el selector de
artículos no mostraba todo el catálogo (se replicaba en compras), la OC era
100% inmutable incluso en borrador, y no había forma de registrar una compra
a partir de solo una factura (sin OC previa). Investigación con 3 agentes
Explore confirmó causa raíz de cada uno con evidencia de código; el
descuento de stock por venta (que también se reportó como roto) resultó
estar correctamente implementado y testeado — se le agregó visibilidad en
vez de tocar la lógica.

| # | Qué | Estado |
|---|---|---|
| 5 | KPI de incidencias de inventario en el dashboard (el descuento de stock ya funcionaba y estaba testeado) | ✅ 2026-08-29 |
| 6 | Alerta de stock bajo en el PDV, sin bloquear la venta (`GET /carta` → `stock_bajo`) | ✅ 2026-08-29 |

### 2026-08-30 — Auditoría del 2026-08-20 — Ola 1, lo que toca ventas
La auditoría de las cinco fases dejó 18 hallazgos priorizados. Esta tanda toma
los tres que caen sobre `/ventas` —la pantalla que verifica lo que se
facturó— y los cierra. El patrón común no es un error visible sino silencio:
un filtro que devuelve cero filas, un botón que termina en 403, una venta que
parece no tener líneas.

| # audit | Qué | Estado |
|---|---|---|
| 1 | El filtro de estados de la jornada ofrecía `entregada` (no existe) y escondía `facturada`; `estado` viajaba como `str` sin validar | ✅ 2026-08-30 |
| 3 | «Reintentar emisión», «Nota de crédito» y «Anular» gateados por permiso | ✅ 2026-09-04 — el resto de los botones-403 (pagos, asientos, trabajadores, artículos, devoluciones) se cerró en la Ola 2; la OC ya estaba gateada desde ADR-085 |
| 11 | El fallo al traer las líneas para la NC se distingue de una venta sin líneas | 🔶 parcial — `rechazarPagoAction` se cerró en la Ola 2; falta la carta del PDV |
| + | La alerta de pedido demorado nunca disparaba para un pedido sin cobrar: `ESTADOS_VIVOS` decía `confirmada`, que no es un valor de `estado_venta`, y omitía `orden` | ✅ 2026-08-30 |

La causa raíz de los tres primeros era la misma: los cinco valores de
`estado_venta` estaban escritos en cuatro lugares que no se importan entre sí.
Ahora hay **una** fuente, `sales.domain.rules.ESTADOS_VENTA`, de la que salen
el `Enum` de la columna, el `Literal` del query param y —con un test de
coherencia, extendiendo el patrón que la propia auditoría señalaba como
existente-pero-no-extendido (hallazgo 15)— el desplegable de la pantalla.

**Sigue abierto de la misma familia**, encontrado al hacer esto y sin tocar:
el PDV filtra su pestaña de cobrados por `estado="pagada"` a secas
(`use-datos-pdv.ts`), así que la venta se le cae de la lista en cuanto SUNAT
acepta y la mueve a `facturada` — mismo bug que ya se parcheó en el KDS
(0.8.1); `estado_emision="error"` es un valor de enum que `sales` nunca
escribe (sí `inventory`), y el botón «Reintentar emisión» se ofrece
justamente para `rechazado`/`error` —donde reintentar no sirve— y no para
`pendiente` con intentos acumulados, que es donde sí; y la reemisión del
comprobante corregido tras una NC de motivo 02/03 está documentada en tres
lugares y no existe.

### 2026-08-30 — Parche 0.9.1 — tercer turno de prueba en staging
Siete reportes. **Cinco no eran código faltante en el backend**: eran
superficies que nunca se construyeron sobre endpoints que ya existían y ya
tenían pruebas verdes — el patrón que se repite desde la 0.8.0 y que este
parche corta. Los otros dos sí eran decisiones pendientes: cuánto dura una
sesión y de dónde sale la cuenta contable de lo que se compra y se vende.

| # | Qué | Estado |
|---|---|---|
| 2 | El dashboard ofrece el pase al BI (existía el módulo, faltaba el enlace) | ✅ 2026-08-30 |
| 6 | El despacho embebido en el PDV vuelve con un botón rotulado, no con una × muda | ✅ 2026-08-30 |
| + | Recargar el PDV vuelve al pedido que se estaba armando, no a la primera pestaña (lo encontró la suite `uso`, que estaba roja en `main` por esto) | ✅ 2026-08-30 |

*(Los ítems 1, 3, 4/5 y 7 de este parche — pantalla de stock/kardex, expiración de sesión, ciclo de OC/factura de proveedor y cuenta contable heredada de categoría — son de `inventory`/`accounting`; ver esos historiales.)*

### 2026-09-04 — Auditoría del 2026-08-30 — Ola 2 (bloques que tocan sales)
La auditoría backend↔frontend del 2026-08-30 dejó 18 hallazgos repartidos en
cuatro olas: [`docs/roadmap/auditoria-erp-2026-08-30.md`](docs/roadmap/auditoria-erp-2026-08-30.md).
La Ola 0 (el inventario no se podía poblar) y las seis ramas de la Ola 1 ya
están en `main`. Ésta es la **Ola 2**: seis bloques, una rama y un PR cada uno.

Lo que une a los seis no es un error visible —es el patrón que la auditoría
vino a buscar—: un botón que promete 403, un formulario que se borra solo
cuando el servidor rechaza, un cuadre que dice «no cuadra» por un centavo que
no existe, una tablet de cocina que reintenta contra una sesión muerta para
siempre, y endpoints con ADR y pruebas que ninguna pantalla llama.

| Bloque | Hallazgos | Estado |
|---|---|---|
| `fix/sesion-expirada-cliente` | #10 la sesión muere y el cliente no se entera: bucle del KDS, campana muda, borradores del PDV que dejan de guardarse en silencio (ADR-088) | ✅ 2026-09-04 |

*(Los bloques `fix/contabilidad-pagos-rbac`, `fix/contabilidad-asientos-rbac`, `fix/rbac-botones-resto`, `fix/dialogos-migracion-sweep` y `feat/inventario-transferencias-mermas` son de `accounting`/`inventory`/frontend transversal; ver `modulo-accounting.md`/`modulo-inventory.md`. `fix/dialogos-migracion-sweep` — migración de 9 archivos/15 diálogos a `DialogoFormulario` — toca también pantallas de `sales` como cualquier otro módulo, sin contenido propio adicional que registrar aquí.)*

Tres correcciones al roadmap original, verificadas contra el código antes de
empezar: `fix/rbac-botones-resto` se achica porque
`compras/ordenes-compra/[id]` **ya está gateado** y es el modelo a copiar;
`gerencia/delivery` y `gerencia/kds` estaban en la lista del sweep sin tener
un solo `<dialog>`; y `feat/inventario-transferencias-mermas` está cumplido
solo en su tercio de transferencias.

### 2026-09-05 — La contabilidad que no registraba, y la Ola 3 (referencia)
*Nota: bloque principalmente de `accounting` — ver `modulo-accounting.md` para el detalle completo. Se apunta aquí porque el hallazgo original fue reportado desde el flujo de cobro del PDV ("las ventas cerradas no aparecían en el balance").*

Reportado operando en staging: **las ventas cerradas no aparecían en el
balance y la comida de personal no costaba nada**. La hipótesis era que
faltaba cablear algo, o que la facturación en pruebas solo reconoce
comprobantes oficiales.

No era eso, y vale escribirlo porque es el patrón que se repite: **el
cableado estaba completo y probado**. El asiento de la venta se genera al
confirmar la orden —del comprobante aceptado cuelga solo el IGV— y el de la
comida de personal existe desde ADR-034.

| Bloque | Qué | Estado |
|---|---|---|
| `fix/contabilidad-cobro-y-anulacion` | El cobro cancela la `1212` y mueve caja/bancos según con qué se cobró; la venta anulada revierte su ingreso | ✅ 2026-09-05 — el incremento de una orden ya confirmada y la fecha del asiento quedan como deuda, ver `deuda/modulo-accounting.md` |

### 2026-09-05 — Auditoría del 2026-08-30 — Ola 4, calidad (referencia parcial)
*Nota: bloques transversales de calidad (paginación server-side, deduplicación de tipos/tests, accesibilidad de insignias). Afectan pantallas de `sales` igual que las de los demás módulos, sin contenido narrativo propio adicional — ver `modulo-inventory.md`/`modulo-accounting.md` para el detalle completo si aplica.*

| Bloque | Qué | Estado |
|---|---|---|
| `fix/paginacion-server-side` | #14 el recorte se avisa en las nueve pantallas que traían 200 filas y paginaban en el navegador; `GET /inventory/lotes` gana tope | ✅ 2026-09-05 |
| `fix/contrato-tests-y-tipos-duplicados` | #15 una prueba parametrizada compara nueve listas de pantalla contra el enum del modelo —encontró una que ofrecía un valor que la API rechaza— y las formas `{id, nombre}` dejan de estar declaradas diecinueve veces | ✅ 2026-09-05 |
| `fix/accesibilidad-insignia-aria-live` | #17 ocho píldoras de estado escritas a mano pasan a `Insignia`, y el aviso pasajero del KDS y del PDV se anuncia también por voz | ✅ 2026-09-05 |

## Pendientes de decisión relacionados con `sales`

- ✅ 2026-07-27 **Cumplimiento de pedido**: **UN** proceso — `PROC-OPE-002`
  (área Operaciones), con Preparación y Despacho/Entrega como etapas
  internas, no dos procesos. Razones: un solo resultado (entra Orden de
  Pedido, sale pedido entregado) sin artefacto de traspaso; la máquina de
  estados ya implementada (`venta_item.estado_preparacion`) es una sola y
  las pantallas KDS `preparacion`/`despacho` son vistas de ella; "Producción"
  ya nombra la cocina de producción central (`PROC-PRD-001`, 2027) y
  reusarlo rompía la nomenclatura. Desbloquea `sales.venta_entregada` y
  `marketing.encuesta_enviada`; se separa como v2.0 si el reparto llega a
  tener ruteo/flota/liquidación propios.

- 🔶 (dentro del pendiente ampliado de "Mecanismo para los valores operativos configurables", ADR-014/ADR-014 Addendum) `sales/margen_minimo` — propuesto 60 %,
  desde food cost 32 % + empaque 3 % + comisión 4 %, y alcanzable porque
  Amazonía exonera el IGV.
- 🔶 `sales/incentivo_meta_pct` — propuesto bono **grupal por sucursal**,
  3 % del excedente sobre la meta, techo 0.5 RMV. Sigue necesitando la
  aprobación conjunta de Comercial + RRHH + Gerencia (política §3).

- ✅ 2026-08-05 Entidades de **Comercial-estrategia** llevadas a
  `data-model.md`, especificadas sin implementar: `meta_venta` +
  `meta_venta_seguimiento` y `hallazgo_mercado` en §6. Tres decisiones que
  valen más que las tablas: (a) la escala 1-4 es la misma en toda la
  organización para poder comparar a una persona consigo misma a lo largo
  del tiempo, con criterios en JSONB porque cada puesto pregunta lo suyo;
  (b) evaluación de desempeño y capacitación viven en `rrhh` aunque las
  ejecute Comercial — su artefacto termina en el file personal y `sales`
  no puede ser dueño de datos de `trabajador`; (c) el seguimiento de la
  meta es tabla, no columna. Falta el slice que las implemente.
- ✅ 2026-08-05 BPMN de área nueva registrado en el maestro:
  **PROC-COM-003** Definición y revisión de precio.

- ✅ 2026-08-27 **La landing pública del QR tiene dominio propio**
  (`clientes.majambo.com.pe`, ADR-080) — ver cronología arriba.

## Estado vigente

PDV, KDS y catálogo de venta (atributos/variantes, productos comerciales,
opciones/extras/restas, mesas, cupones, cocina por estaciones, ticket
impreso, delivery por kilómetro) están en producción/staging con múltiples
rondas de parches sobre hallazgos de uso real, más varias auditorías
(Olas 1-4) que cerraron huecos de gates de permiso y de "endpoint sin
pantalla". Persisten como deuda declarada (`docs/roadmap/deuda/modulo-sales.md`,
no reproducida aquí): el motor de promociones condicionales completo más
allá de N×M automáticas (ADR-076) y del cupón de un solo uso (ADR-061/062),
la entidad `entrega` con trazabilidad de repartidor, tarifa de delivery por
sucursal y zonas por polígono, el reparto como línea propia del comprobante,
el modo de variante `dinamica`, y el filtro de "Cobrados" del PDV que sigue
mirando `estado="pagada"` a secas (se cae de la lista al pasar a
`facturada`, mismo patrón ya corregido en el KDS).

## Fuentes

Rangos de línea de `ROADMAP.md` usados (estado del archivo al momento de
escribir este historial, antes de cualquier reorganización):

- Líneas 5-66 — tabla F0 (Estado — Fundaciones): fila 24 (`sales`, completa),
  fila 32 (Comercial: procesos y plantillas), fila 41 (Factiliza — nota sobre
  guía de remisión NO siendo de `sales`), fila 43 (Google Maps / delivery),
  fila 53 (Ciclo de caja — nota de frontera con `accounting`).
- Líneas 68-373 — bitácora de parches/auditorías agosto-septiembre 2026,
  prácticamente en su totalidad relacionada con PDV/ventas:
  - 68-95 Parche del PDV 0.7.8
  - 96-136 Parche desplegables con búsqueda (transversal, con foco en
    promociones de `sales`)
  - 137-163 Parche 0.8.1
  - 164-188 Parche compras/inventario (solo ítems 5 y 6, referencia parcial)
  - 189-220 Auditoría 2026-08-20 Ola 1 — lo que toca ventas
  - 222-240 Parche 0.9.1 (solo ítems 2, 6 y el "+" de recarga del PDV)
  - 260-288 Auditoría 2026-08-30 Ola 2 (solo `fix/sesion-expirada-cliente`,
    con nota sobre `fix/dialogos-migracion-sweep`)
  - 289-309 La contabilidad que no registraba (referencia, bloque
    `fix/contabilidad-cobro-y-anulacion`)
  - 330-342 Auditoría 2026-08-30 Ola 4 (referencia parcial, bloques
    transversales de calidad)
  - 343-373 Catálogo modelo Odoo (0.7.0)
- Líneas 375-573 — Pendientes de decisión: bloque de "Mecanismo para
  valores operativos configurables" (ítems `sales/margen_minimo` y
  `sales/incentivo_meta_pct`), "Cumplimiento de pedido: UN proceso",
  entidades de Comercial-estrategia (`meta_venta`, `hallazgo_mercado`),
  BPMN `PROC-COM-003`, y landing pública con dominio propio
  (`clientes.majambo.com.pe`).
- Líneas 574-605 — Deuda técnica: **no tocada**, por instrucción explícita.
- Líneas 606-1413 — Orden sugerido de desarrollo (julio 2026):
  - 606-687 Slice vertical Venta — PROC-COM-001
  - 688-730 Modelado de BD (transversal, bloque "Operación comercial")
  - 909-960 Área Comercial — precio, margen, promociones, mercado y
    desempeño de venta
  - 1008-1040 Slice Venta — núcleo de datos
  - 1041-1078 Slice Cobro, Comprobante y Caja (nota de frontera con
    `accounting` para la parte de caja)
  - 1351-1404 Cumplimiento de pedido — PROC-OPE-002 (detalle completo)
