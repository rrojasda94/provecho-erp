# Deuda técnica — Módulo accounting (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-09-05 **El cobro entra al balance y la venta anulada sale de él**
  (sin migración): `sales.venta_pagada` y `sales.venta_anulada` no tenían
  suscriptor. El cobro cancela ahora la `1212` y mete la plata donde entró
  —`101` si fue efectivo, `1041` si fue tarjeta, billetera, transferencia o
  cheque— y una venta al crédito no asienta nada, porque la cuenta por cobrar
  sigue viva. La anulación entera reversa su asiento de ingreso.
  El asiento del cobro **no pasa por las plantillas ni por `regla_asiento`**:
  la cuenta del debe la decide el medio de pago, no el evento, y una venta se
  cobra con varios a la vez.
  Lo que deja abierto:
  - ⬜ **Quitar líneas de una orden deja el ingreso sobrevaluado.** La
    anulación parcial (`lineas_anuladas` con `venta_anulada: false`) no se
    asienta: reversar el asiento entero borraría el ingreso de las líneas que
    quedaron, y lo correcto es un asiento de ajuste por la diferencia. Hace
    falta que el payload traiga el importe de lo quitado, que hoy no trae.
  - ⬜ **El incremento de una orden ya confirmada no se asienta.** Agregar
    líneas republica `sales.venta_confirmada` con el mismo `venta_id`
    (`ventas.py`), y el dedupe por `(empresa, evento, referencia_origen)` lo
    descarta como si fuera un reenvío —`asientos.py`—, así que el ingreso
    queda corto por lo agregado. El comentario del publicador asume lo
    contrario. Las dos salidas: que la publicación lleve un identificador
    propio y el dedupe use ese (resuelve la clase entera, pero la reversión
    por origen pasa a tener que buscar todos los asientos de la venta), o un
    sufijo por número de confirmación en `referencia_origen`. Va en su rama.
  - ⬜ **El asiento se fecha con el día en que se procesa, no con el de la
    operación** (`listeners.py`, `fechas.hoy()`). Coinciden casi siempre —el
    listener corre justo después del commit— pero no cuando el evento llega
    tarde: el replay del hub offline o una venta de fin de mes procesada al
    día siguiente caen en el periodo equivocado, y el rango por defecto de
    Estados financieros (1° del mes → hoy) las esconde. Arreglarlo es que
    cada evento lleve la fecha de su operación.
  - ⬜ **De qué banco entró la plata no se sabe**: todo lo que no es efectivo
    va a `1041`. El ERP no modela cuentas bancarias (ver más abajo), así que
    hoy no hay nada más fino que elegir.

- ✅ 2026-09-05 **La contabilidad deja de vaciarse en silencio** (ADR-089,
  migración `b5e7d1a3c92f`): la empresa nace con su PCGE —`accounting` escucha
  `organizacion.empresa_creada`—, el periodo se abre al primer asiento del mes
  y la omisión queda en `asiento_omitido` con su motivo. Cierra la causa real
  de que el balance estuviera vacío: importar el plan de cuentas y abrir el
  mes eran dos cosas manuales que nadie sabía que había que hacer, y sin
  cualquiera de las dos **ningún** asiento automático del ERP entraba.
  Lo que deja abierto:
  - ⬜ **El efectivo que no nace en una caja de PDV no tiene dónde colgarse.**
    `movimiento_caja` y `custodia_efectivo` llevan `apertura_caja_id`, así que
    la plata que sale del banco para caja chica (o que entra por un préstamo o
    un premio) queda **sin responsable nominal**: nadie firma que la recibió,
    no se cuenta al cierre y no aparece en ningún arqueo. Es un hueco de
    modelo, no un endpoint que falte — el circuito que construyó ADR-025 está
    anclado al turno. Mientras tanto se registra con asiento manual, ver
    [`docs/contabilidad/operaciones-no-operativas.md`](../../contabilidad/operaciones-no-operativas.md).
  - ⬜ **`MovimientoDinero.tipo="ingreso"` es inalcanzable por API**: el enum
    lo admite, pero `PagoProveedorCreate` no expone `tipo` ni `concepto` y
    `registrar_pago` fija `"pago_proveedor"`. Un ingreso de tesorería no tiene
    cómo entrar a la cola.
  - ⬜ **RN-EMP-006 no tiene implementación**: «todo préstamo requiere estudio
    de viabilidad previo del área contable, aprobado por Gerencia». Hoy es una
    regla escrita que nada verifica, ni siquiera como recordatorio.
  - ⬜ **Los asientos perdidos no se reponen.** Este cambio arregla de acá en
    adelante; las ventas y consumos que ocurrieron mientras faltaban las
    cuentas y el periodo siguen sin asiento. Reprocesarlos es otro trabajo —
    hay que saber qué eventos hubo, no solo qué falta.

- ✅ 2026-08-30 **La cuenta contable se configura en la categoría y se hereda**
  (ADR-086, sin migración): las líneas de plantilla llevan rol, el asiento
  reparte el monto del evento por categoría y `articulo.tipo="servicio"` manda
  su parte a la 63x sin tocar existencias. `categoria.asiento_contable_config`
  deja de ser un campo de solo escritura.
  Lo que deja abierto:
  - ⬜ **`consumo_personal_valorizado` y `transferencia_recibida` no se
    reparten**: sus payloads llevan un `monto` agregado y ningún detalle, y
    sumárselo es cambiar el publicador dentro de `_mover`.
  - ⬜ **El rol `costo_venta` no existe todavía**: ningún evento asienta contra
    la 69 (ver más abajo, hace falta un consumo valorizado por venta), así que
    sería configuración muda. El día que ese evento exista, el rol se suma al
    catálogo y al formulario sin tocar el reparto.
  - ⬜ **La validación al guardar no comprueba «último nivel» al asentar**: si
    una cuenta gana hijas después de configurarse, el asiento se imputa igual
    en el rubro. `crear_asiento_automatico_multilinea` no hace esa comprobación
    (solo la hace el asiento manual); el filtro de lectura solo descarta lo que
    no existe o está inactivo.

- ✅ 2026-07-25 **Pago a proveedor (PROC-CTB-003)**: migración `cbf904a9fc1b`
  (`movimiento_dinero`). `purchases.comprobante_conforme` encola
  (`registrar_pago`, idempotente por `comprobante_id` RN-CTB-008);
  `ejecutar_pago` exige `accounting.pago_gestionar` + umbral vía
  `parametro_empresa` (código `pago_umbral`, RN-CTB-005, `accounting.pago_aprobar`
  sobre el umbral) y genera asiento vía `regla_asiento`
  (`accounting.pago_ejecutado`); `rechazar_pago` cierra sin ejecutar.
  Eventos `accounting.pago_ejecutado`/`pago_requiere_aprobacion` ya se
  publican, pero sin consumidor todavía (ver pendiente de `purchases`
  arriba y de `users`/alertas abajo).
- ⬜ **Resto de eventos → asiento automático**: `sales.pago_registrado` y
  `purchases.caja_chica_rendida` están documentados en `events.md` pero sus
  módulos de origen aún no los publican en código (en el caso de `sales`,
  el evento real ya publicado se llama `sales.venta_pagada`, no
  `sales.pago_registrado` — desalineación de nombre entre spec y código,
  revisar). `inventory.ajuste_fuera_margen` sí se publica pero `accounting`
  todavía no lo suscribe. Cuando existan/se suscriban, agregar su extractor
  de monto/empresa en `accounting/application/listeners.py`. Corregido
  2026-09-09: esta entrada incluía `sales.comprobante_emitido`,
  `inventory.transferencia_recibida` e `inventory.merma_registrada`, que
  **ya** se publican, se escuchan (`listeners.py:register()`) y asientan
  desde 2026-08-06/2026-08-31 — el doc no se había actualizado.
- ⬜ **Detracción SPOT sin cuenta propia**: `movimiento_dinero.monto_detraccion`
  se calcula (RN-IMP-003) pero el asiento de `pago_ejecutado` no la
  desglosa — el debe/haber usa el monto total, no separa la cuenta de
  detracciones del banco/caja. Requiere ampliar `regla_asiento` a N líneas
  (hoy es siempre 1 debe/1 haber).
- ⬜ **`accounting.pago_ejecutado`/`pago_requiere_aprobacion` sin
  consumidor real**: `events.md` documenta que `purchases` marca la OC
  pagada y que `users` alerta a Gerencia — ninguno de los dos escucha
  todavía.
- ⬜ **`rechazar_pago` no libera el comprobante**: el único
  `movimiento_dinero` por `comprobante_id` (unique) queda en `rechazado`
  para siempre; reintentar el pago del mismo comprobante requiere
  intervención manual (borrar/reabrir la fila) — evaluar si el negocio
  necesita un caso de uso de reapertura.
- ✅ 2026-07-26 **Arqueo backend (PROC-CTB-005)**: `application/caja.py::registrar_arqueo`
  + `POST /accounting/arqueos`, publica `accounting.arqueo_registrado`
  (slice mínimo, ver ADR-012 — sin visado de Gerencia ni plantilla propia).
- ⬜ **Conciliación bancaria (PROC-CTB-004)**: sin modelo ni caso de uso.
  RN-CTB-006 (cierre de periodo exige conciliación visada) no se valida
  todavía — `cerrar_periodo` hoy no lo comprueba. Bloquea implementar
  rigurosamente RN-CTB-006.
- ✅ 2026-07-26 **Ciclo de caja → eventos**: `apertura_caja`/`cierre_caja`/
  `arqueo` (PROC-CTB-001/002/005) ya tienen capa de aplicación
  (`accounting.application.caja`, ver ADR-012) y publican
  `accounting.apertura_caja_registrada`/`cierre_caja_registrado`/
  `cierre_caja_irregular`/`arqueo_registrado`. **No generan asiento
  contable todavía** (sin listener que consuma esos eventos hacia
  `regla_asiento`) — eso sigue pendiente. Tampoco incluye RN-POS-009..013
  completas ni la máquina de estados de `custodia_efectivo` — ver Deuda
  técnica → Dashboard y caja.
- ⬜ **Activo fijo/depreciación y flujo de caja** (PROC-CTB-007/010,
  propuestos): sin modelar, dependen de que exista el módulo de activos.
- ⬜ **`declaracion_itan`**: entidad documentada en data-model §8, sin
  slice propio (depende del ciclo tributario anual, RN-IMP-006).
- ✅ 2026-08-29 **`regla_asiento` de una sola línea debe/haber** (ADR-081):
  resuelto por otra vía. `regla_asiento` sigue siendo de 2 líneas y ahora es
  el **override**; sin regla, el evento cae en la plantilla del PCGE
  (`domain/plantillas.py`), que sí expresa N líneas con el IGV desagregado y
  el asiento de destino. Ampliar `regla_asiento` a N líneas dejó de ser
  necesario para el caso que la motivaba.
- ✅ 2026-08-29 **Plan contable oficial y estados financieros** (ADR-081):
  PCGE 2019 sembrable por empresa, asientos peruanos completos por plantilla,
  balance de comprobación, libro mayor, Estado de Situación Financiera y
  Estado de Resultados (por naturaleza). Sin migración.

- ✅ 2026-08-29 **El régimen de IGV se elige y admite excepción puntual** (ADR-081 enmendada, migración `dfb195b14433`): `shared/tributos.py` resuelve casilla de la operación → default de la empresa → zona tributaria, y el IGV se asienta con el comprobante (`sales.comprobante_emitido`, `purchases.comprobante_conforme`). Cierra también el pendiente de `sales.comprobante_emitido` sin consumidor.

Lo que ADR-081 dejó abierto:

- ⬜ **Una venta sin comprobante emitido no reconoce IGV**: es correcto —sin comprobante no hay venta— pero si la emisión a SUNAT falla, el débito fiscal queda pendiente hasta que se reemita, y nada lo señala hoy.
- ⬜ **`movimiento_dinero.monto` es el total de la OC sin IGV**: el pago a un proveedor gravado se encola por menos de lo que dice su factura. Anterior a ADR-081; ahora se nota más, porque el crédito fiscal sí queda asentado.
- ⬜ **La casilla de operación gravada es manual**: no se deduce del distrito del cliente ni del domicilio del proveedor. Automatizarlo exige definir qué distritos cuentan como zona exonerada.
- ⬜ **La conformidad de compras no tiene pantalla**: `gravado_igv` se manda por API. Mientras no exista la pantalla, el crédito fiscal de una compra gravada depende de que quien llame la API lo marque.
- ⬜ **La cuenta por cobrar de la venta (1212) no se cancela nunca**: el
  asiento de venta la carga y nada la abona, porque `sales.pago_registrado`
  no se publica (mismo pendiente de arriba). El balance cuadra —el activo
  está en «cuentas por cobrar» en vez de en «efectivo»— pero el ciclo de caja
  y el libro contable siguen sin tocarse. Es hoy el hueco más visible: se ve
  a simple vista en el Estado de Situación Financiera.
- ⬜ **El costo de ventas (69) no se genera solo**: hace falta un evento de
  consumo **valorizado** por venta. `inventory.stock_consumido` viaja sin
  monto, así que hoy el consumo se refleja por la vía del elemento 6
  (compras 60 contra variación de existencias 61), que es lo que el estado
  por naturaleza presenta. Sin 69 tampoco hay margen bruto.
- ⬜ **Estado de Resultados por función**: necesita los asientos de destino
  del PCGE (elemento 9 contra la 79), que ningún proceso genera. Presentarlo
  hoy daría un estado que no cuadra contra el mayor.
- ⬜ **Sin asiento de cierre anual**: no existe el traslado del resultado a
  resultados acumulados (elemento 89 contra la 59), así que el resultado del
  balance es acumulado desde el inicio del libro, en su línea propia del
  patrimonio. El ejercicio no se corta.
- ⬜ **Corte corriente/no corriente por rubro**: separar la porción corriente
  de un préstamo (rubro 45) exige la fecha de vencimiento de cada cuota, dato
  que `movimiento_dinero` no guarda. Mientras tanto la 45 va entera a no
  corriente y el contador externo reclasifica.
- ⬜ **Elementos 8 (parcial) y 0 del PCGE sin sembrar**: del 8 solo están
  `87` y `88`; faltan los saldos intermediarios de gestión (`80`-`85`) y la
  determinación del resultado (`89`). El elemento 0 (cuentas de orden) no
  está: sembrarlo pide agregar un tipo de cuenta nuevo al enum
  (`activo`/`pasivo`/`patrimonio`/`ingreso`/`gasto` no lo cubren), o sea
  migración.
- ⬜ **El PCGE no se siembra en el seeder**: se importa con un botón en Plan
  de cuentas. Sembrarlo automáticamente chocaría con los tests, que crean sus
  propias cuentas con códigos de rubro (`10`, `60`, `70`).
