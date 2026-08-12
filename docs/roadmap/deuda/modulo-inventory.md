# Deuda técnica — Módulo inventory (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-08-12 **Abastecedor de respaldo** (ADR-040, RN-INV-022,
  migración `a7c04e3b91d5`): dar de baja el central dejaba a la sucursal sin
  poder pedir nada.
- ⬜ **No se puede vaciar un abastecedor ya elegido** (2026-08-12): los
  `PATCH` de organización tratan `null` como "no tocar" (convención de
  `users/api/schemas.py`), así que elegir "Ninguno" en el selector no lo
  limpia — solo lo deja como estaba. Es previo a este cambio y ahora tiene un
  campo más. Se arregla con un centinela explícito en el `Update`, que es un
  cambio de contrato para las cinco entidades de organización.

- ✅ 2026-08-03 **Recetas editables** (ADR-023, migración `b6d1e83f47ac`):
  CRUD de receta e ítems, duplicar con "(copy)", escalar por factor y
  aritmética tecleada en la cantidad (`receta_item.expresion`), redondeada
  a los decimales de la UdM del insumo (RN-COM-024). `GET
  /inventory/unidades-medida` nuevo. Contrato público
  `queries_publicas.receta_resumen` — cierra la mitad `Receta` de la deuda
  "contrato público de inventory para `Articulo`/`Receta`" de la auditoría
  2026-08-01; `Articulo` sigue pendiente (`purchases` y `production` aún
  importan su ORM).
- ✅ 2026-08-06 **Recetas con tenant** (`receta.empresa_id`, migración
  `d5b81e0c37a4`). Era la última entidad del catálogo sin columna de
  empresa: el CRUD listaba las de todas y el hub las replicaba completas.
  Ahora el listado filtra, cada ruta por id pasa por `exigir_receta`, el
  **nombre es único por empresa y no por grupo** —dos empresas del grupo
  pueden vender la misma pizza con recetas distintas— y un ítem no puede
  tomar un artículo ajeno: eso devuelve **404 y no 403**, porque para esa
  empresa el artículo no existe. `receta_item` no lleva columna propia, se
  acota por su receta.
  La salida que ADR-009 anticipaba —cruzar `producto_comercial` (dominio de
  `sales`) desde `inventory`— era la equivocada: el dueño del dato no era
  `sales`, era que a `receta` le faltaba la columna.
  El relleno de la migración atribuye a la única empresa operativa lo que no
  puede derivar de `articulo.empresa_id`; correcto hoy y a revisar a mano el
  día que la base tenga dos. 4 casos nuevos en
  `tests/test_tenant_aislamiento.py` y 1 en `tests/test_sync_motor.py`.
- ✅ 2026-07-25 **Listener `sales.venta_confirmada`** → consumo por receta
  (+merma % + empaque por modalidad) y `sales.venta_anulada` → reposición.
- ✅ 2026-07-25 **Listener `purchases.compra_recibida`** → suma stock en el
  almacén destino y recalcula `articulo.costo_promedio` (promedio
  ponderado solo contra el stock del almacén que recibe — deuda si
  `compra_directa` multi-almacén se vuelve frecuente, ver módulo purchases).
- ✅ 2026-08-06 **Consumo omitido con superficie propia**: nueva entidad
  `incidencia_inventario` (migración `c2f6a94b13de`) escrita por los **seis**
  puntos de omisión del listener (venta, OC, producción × sin almacén / sin
  SKU / stock insuficiente) y reporte `consumos_omitidos`. La venta sigue sin
  bloquearse nunca; lo que cambia es que el stock que se fue de la realidad
  deja de vivir solo en un `log.warning` que nadie lee. El motivo es lo
  accionable: dice si hay que configurar la sucursal, dar de alta un SKU o
  mirar por qué el stock ya venía mal.
- ✅ 2026-08-01 **`reserva_stock` + `solicitud_insumos` + transferencias**
  (ADR-020, migración `d8b35f1ca207`): ciclo completo local pide →
  supervisor aprueba y reserva → central despacha → local recibe. La
  reserva es una promesa (no mueve `stock` ni genera movimiento) y
  `GET /stock` expone `cantidad`/`reservado`/`disponible` (RN-INV-009).
  Reservar bloquea, consumir no: una venta nunca se frena por una reserva.
  `transferencia_item` va por SKU **y lote** (el despacho reparte FEFO y el
  destino recibe los mismos lotes). Diferencias registradas, no corregidas
  (RN-INV-001/002). Transferencia lateral sucursal↔sucursal con la misma
  entidad. Permisos nuevos `solicitar_insumos`/`aprobar_solicitud`/
  `liberar_reserva`; estrena `transferir` y `recepcion`. 23 casos en
  `tests/test_transferencias.py`. Deuda que deja abierta:
  - ✅ 2026-08-06 **Disponible negativo con reporte**
    (`disponible_negativo` en el catálogo, ADR-024). Sigue siendo un estado
    alcanzable a propósito; lo que faltaba era dónde verlo sin saber de
    antemano qué SKU mirar.
  - 🔶 **Tipos de reserva sin productor**: `merma` ya lo tiene
    (2026-08-06, ADR-028). Quedan `produccion` y `carrito`, que esperan a
    sus módulos, y eso **no es un pendiente de este módulo**: construirle un
    productor a un tipo cuyo caso de uso todavía no existe es inventar el
    caso de uso.
  - ✅ 2026-08-07 **Transferencia sin vehículo ni tracking — descartado**
    (decidido con el usuario). No hay flota: el traslado lo hace alguien del
    grupo en su propio vehículo, y la placa se teclea en la guía, que es el
    único documento que la necesita (ADR-027 ya descartó `vehiculo` por lo
    mismo). Una tabla de vehículos sería un formulario que hay que llenar
    antes de poder despachar, y el tracking GPS mide una ruta de veinte
    minutos entre dos locales de la misma ciudad. `transportista_id` alcanza
    para saber quién lo llevó, que es la pregunta que sí se hace cuando algo
    no llega. Vuelve a la mesa si aparece reparto propio con flota.
  - ✅ 2026-08-06 **Recepción parcial**: `{"parcial": true}` ingresa lo
    declarado y deja el resto **en tránsito**. Explícito y no deducido de
    que falten ítems: deducirlo haría que un olvido cierre la transferencia
    dando por perdido lo que todavía viene en camino. El evento
    `transferencia_recibida` sale **una sola vez**, al cerrar — si no,
    `accounting` asentaría el faltante de cada entrega por separado.
  - ✅ 2026-08-07 **El ciclo se replica al hub** (ADR-009 fase 3). El
    local **pide, ve lo que viene y recibe** durante un corte, que es
    justo cuando más falta hace: el camión no espera a que vuelva el
    internet. Bajan `solicitud_insumos`/`solicitud_item` (las que pidió),
    `transferencia`/`transferencia_item` (las que **entran** a su almacén) y
    `reserva_stock` —sin las reservas su `disponible` offline sería el
    físico entero—; suben la solicitud creada y la recepción hecha.
    En el camino se descubrió que el hub **no replicaba su almacén
    abastecedor** (el filtro de `almacen` traía solo los de la sucursal),
    así que `crear_solicitud` fallaba offline con "abastecedor no
    encontrado". Ahora viaja la ficha del central; su *stock* sigue sin
    replicarse.
  - ✅ 2026-08-06 **`inventory.transferencia_recibida` con consumidor en
    `accounting`**: asiento **solo si hubo faltante**. Un traslado entre
    almacenes de la misma empresa no mueve resultado —la mercadería cambia
    de sitio, no de dueño— y un asiento por cada uno llenaría el libro de
    movimientos que se cancelan entre sí; lo que sí es hecho contable es lo
    que salió y no llegó. El evento pasa a llevar `monto_diferencia`,
    valorizado por **el emisor** al `costo_promedio`: el costo es dato de
    `inventory` y hacerlo buscar por `accounting` sería importarle dominio
    ajeno. De paso, `recibir` pasa a publicar con `session=` — se despachaba
    en medio de la transacción, y con consumidor un rollback dejaba el
    asiento de una recepción que nunca ocurrió (ADR-016).
  - ✅ 2026-08-07 **Estado `en_picking` — descartado** (decidido con el
    usuario). Un estado que no gobierna ninguna regla no es un estado, es un
    comentario: entre `aprobada` y `despachada` nada cambia de permiso, de
    validación ni de qué se puede hacer. Agregarlo obliga a que alguien lo
    marque a mano, y un estado que depende de que alguien se acuerde miente
    la mitad del tiempo. Si el negocio pide ver "el central ya empezó a
    armarlo", entra entonces — y con quien lo marca definido.
- ✅ 2026-07-27 **Lote / FEFO** (ADR-015): `lote` + `stock_lote`, control
  opcional por artículo, reparto FEFO al registrar la salida, bloqueo de
  vencidos + `inventory.lote_vencido_detectado`, lote generado por
  recepción de compra y por producción. Deuda que deja abierta:
  - ⬜ **La reposición por venta anulada entra al lote del día**, no al
    lote del que salió: `sales.venta_anulada` no transporta los
    movimientos originales. Con volumen bajo la diferencia es contable,
    no física; si importa, el evento tiene que llevar el detalle.
  - ✅ 2026-08-06 **Ventana de alerta por artículo**
    (`articulo.dias_alerta_vencimiento`, RN-VNC-004 nueva). `GET /lotes`
    marca `por_vencer` con la ventana del artículo; `por_vencer_dias` en la
    consulta la sobrescribe. Un artículo sin ventana no avisa —`False`, no
    `True`: sin política de vencimiento no hay nada que avisar.
  - 🔶 **`inventory.lote_vencido_detectado`: consumidor ✅ 2026-08-06,
    `responsable_id` sigue pendiente.** `users` lo pone en la bandeja del
    almacén con nivel `urgente` —el stock ya se contaba como vendible—.
    Lo que queda es el memorándum a RRHH (RN-VNC), bloqueado no por falta
    de aviso sino porque `almacen` no tiene responsable modelado: se avisa
    al rol, no a una persona.
  - ✅ 2026-08-06 **Motivo del override de lote**
    (`movimiento_inventario.motivo_lote`, RN-LOT-004 nueva). Se exige solo
    cuando el lote elegido **no** es el que FEFO sugería: pedirlo también
    cuando coinciden convierte el campo en un trámite que se llena con
    cualquier cosa, y un motivo que nadie escribe en serio da apariencia de
    control sin darlo.
  - ✅ 2026-08-06 **`recepcion_item` conserva el lote recibido**
    (`lote_codigo` + `fecha_vencimiento`). Lo que declaró el proveedor
    (RN-VNC-002) queda en el documento además de viajar en el evento: si el
    listener falla, ahora hay de dónde reprocesarlo.
  - ✅ 2026-08-06 **Salida sin lote con reporte** (`salidas_sin_lote`).
    Sigue siendo deliberada (RN-LOT-005, nueva): la operación ya ocurrió y
    frenarla sería negar una venta por un dato de trazabilidad que ya está
    mal. Ahora se lista.
- ✅ 2026-08-01 **Conteo cíclico** (ADR-019, migración `c4e70a91d5b8`):
  `conteo` + `conteo_item`, con la periodicidad configurada **en la
  categoría** (`categoria.frecuencia_conteo`: diario/semanal/quincenal/
  mensual/semestral/anual, RN-INV-007) — no hay número universal. El
  calendario se deriva del último conteo cerrado más la frecuencia, sin
  tabla `programa_conteo`; un conteo general pone al día a todas las
  categorías del almacén. Stock esperado congelado al abrir, conteo a
  ciegas por defecto (permiso `inventory.ver_stock_esperado`), cierre que
  genera un `ajuste` pendiente por diferencia (`ajuste.conteo_id`) sin
  mover stock, y `inventory.conteo_vencido` a almacén y gerencia por lo
  que no se contó en su fecha (RN-INV-021). 22 casos en
  `tests/test_conteos.py`. Deuda que deja abierta:
  - ✅ 2026-08-06 **Los tres barridos entran a Celery beat**
    (`inventory.reportar_conteos_vencidos` y
    `inventory.bloquear_lotes_vencidos` diarios a las 06:00 y 06:15 hora
    Perú, `sales.barrer_comprobantes_pendientes` cada 15 min). Beat ya
    existía —la deuda decía que no, y estaba desactualizada: corre desde el
    2026-08-04 con el barrido de pedidos demorados y el latido del worker—,
    así que esto fueron tres entradas de `beat_schedule` y las tareas que
    envuelven casos de uso ya escritos, no infraestructura nueva.
    **Antes del turno y no a cualquier hora**: el vencimiento cambia al
    pasar la medianoche del negocio, y bloquear el lote a media mañana deja
    que la primera salida del día se lo lleve.
    `tests/test_celery_beat.py` congela el cableado — un nombre mal escrito
    en el schedule no falla en ningún lado (beat encola, el worker descarta,
    el barrido no ocurre nunca), que es el modo de falla más silencioso del
    ERP y justo en las tareas que existen para que algo no pase
    inadvertido.
  - ✅ 2026-08-06 **`inventory.conteo_vencido` con consumidor**: va a la
    bandeja del almacén y de gerencia. Se repite cada día hasta que se
    cuente, y eso es deliberado: es un recordatorio, no la noticia de un
    hecho puntual.
  - ✅ 2026-08-06 **Margen de error por empresa, con piso en dinero**
    (`inventory/margen_error_ajuste`, ADR-014/ADR-019): cierra de una vez
    esta deuda y la del piso absoluto. `settings.inventory_margen_ajuste_pct`
    (2 %) deja de ser la regla y queda como default de arranque hasta que
    Gerencia apruebe el suyo. El valor lleva **porcentaje y piso** y basta
    cumplir uno: la diferencia se valoriza al `costo_promedio` del artículo,
    porque el porcentaje solo castiga a las categorías baratas —2 % de S/ 30
    en servilletas son 60 céntimos— y una alerta que siempre suena no la mira
    nadie. Primer parámetro **compuesto** del ERP: se lee con `valor_vigente`,
    no con el envoltorio escalar `umbral_vigente`.
    En el camino se cerró un agujero de control: `POST /inventory/ajustes`
    recibía **`dentro_margen` del cliente**, con default `True` — o sea que
    el mismo request que provoca el descuadre podía declararlo tolerable y
    silenciar `inventory.ajuste_fuera_margen`. Ahora lo calcula el servidor
    contra el stock del almacén, igual que en el cierre de conteo; el campo
    salió de `AjusteCreate` y del contrato. Lógica compartida en
    `application/margenes.py`. 4 casos nuevos en `tests/test_conteos.py`.
  - ✅ 2026-08-07 **El conteo se replica al hub**: se cuenta offline y el
    conteo sube **cerrado**, nunca a medias —reproducir uno abierto en la
    nube generaría ajustes por ítems que nadie llegó a mirar—. El cierre
    genera el `ajuste` pendiente arriba, con su aprobador distinto
    (RN-INV-006), igual que si se hubiera contado en línea.
  - ✅ 2026-08-06 **Anulación de conteo expuesta**
    (`POST /conteos/{id}/anular`, motivo obligatorio). No genera ajustes ni
    pone al día el calendario —el programa solo mira los `cerrado`—, que era
    el daño real de la salida anterior: cerrar en cero afirma "se contó y no
    había diferencias".
  - ✅ 2026-08-07 **Frecuencias en días fijos — descartado** (decidido con
    el usuario). "Mensual" en el almacén significa *cada mes más o menos*,
    no *el día 3 de cada mes*: el conteo se hace cuando el local puede, y
    anclarlo al día del mes haría aparecer un atraso cada febrero por una
    diferencia que a nadie le importa. El día que se pida, es una línea en
    `rules.proxima_fecha_conteo` (`dateutil.relativedelta`) y nada más — el
    resto del cálculo no cambia.
- ✅ 2026-08-05 **Guía de remisión** (ADR-027, migración `a4c8f21e6b09`,
  **aplicada a Supabase el 2026-08-05** junto con el seeder que suma
  `inventory.emitir_guia` al rol `almacenero`):
  `guia_remision` + `guia_remision_item` colgando de `transferencia`, porque
  lo que la guía declara es un traslado y el traslado es un hecho de
  inventario (RN-GDR-002). Las líneas **se derivan** de `transferencia_item`
  agrupadas por SKU —RN-TRP-002 exige que lo transportado coincida con lo
  declarado, y un formulario de ítems aparte es la forma de que no coincidan;
  el reparto FEFO por lote es control interno que SUNAT no declara. Se teclea
  solo lo que el sistema no puede saber: chofer, vehículo, peso bruto y fecha
  de inicio del viaje. Un traslado, una guía (`transferencia_id` único,
  emisión idempotente) y correlativo por `(empresa, serie)` calculado al
  emitir, no reservado antes —una guía reservada que no se emite deja un
  hueco en la numeración que también hay que justificar—. Envío a SUNAT
  asíncrono (`POST /despatch/send` vía Celery, `factiliza/guias.py` aparte
  del mapper de facturas porque una guía no tiene aritmética tributaria).
  Permiso nuevo `inventory.emitir_guia` en el rol `almacenero`. 14 tests
  (`tests/test_guia_remision.py`). **Sin entidad `vehiculo`**: sin flota, una
  tabla de vehículos sería un formulario que hay que llenar antes de emitir
  la primera guía.
- ✅ 2026-08-06 **Devolución** (`devolucion` + `devolucion_item`, ADR-028,
  migración `e7c390a5b41f`). Cubre los dos casos sin camino: **a proveedor**
  la mercadería sale con el lote declarado —obligatorio si el artículo
  controla lote: el reclamo tiene que decir qué se rechaza—, emite **su
  propia guía de remisión** y publica `inventory.devolucion_a_proveedor`;
  **de cliente** entra y `destino` decide si vuelve al estante o se aparta
  como merma en el mismo acto. `reporte_dirigido_a` se deriva del origen
  (RN-INV-020). Anular repone con movimientos contrarios y suelta las
  mermas que había apartado; no borra la fila.
  **Sucursal→central no se modeló acá**: es una `transferencia` (ADR-020) y
  duplicarla sería un segundo camino para el mismo movimiento.
- 🔶 **Guía de una venta con reparto**: `guia_remision.transferencia_id`
  **ya es nullable** desde 2026-08-06 —la devolución a proveedor fue el
  segundo emisor y forzó el cambio, tal como este punto anticipaba—, así
  que el reparto propio solo tendría que sumar su `venta_id`. Sigue abierto
  porque no hay reparto propio todavía.
- ⬜ **Descarga de PDF/XML/CDR de la guía y anulación por comunicación de
  baja**: `FactilizaClient.descargar` apunta a `/invoice/...`; la guía
  necesita su ruta `/despatch/...`, y el payload de `/despatch/send` sigue
  **pendiente de verificación contra el sandbox real** de Factiliza — igual
  que estuvo la boleta antes de su primera emisión.
- ⬜ **`codigo_sunat` por unidad de medida**: hoy el mapper traduce con un
  diccionario de doce unidades y cae en `NIU` lo que no reconoce. El lugar
  correcto es una columna en `unidad_medida` editable desde Catálogo;
  mientras solo la guía lo necesite, una columna que alguien tiene que
  llenar a mano es más trabajo que el diccionario.
- ✅ 2026-08-07 **La guía no se emite offline — decisión, no deuda**
  (decidido con el usuario). El correlativo es único por `(empresa, serie)`
  y dos hubs numerando a la vez colisionarían **con la guía ya impresa y
  viajando en el camión**: el conflicto aparecería recién al sincronizar,
  cuando ya no hay nada que corregir.
  Se evaluaron las dos salidas y se descartaron las dos: una **serie por
  almacén emisor** (lo que SUNAT espera) obliga a registrar cada serie ante
  SUNAT antes de usarla, y un **rango de correlativos por hub** deja huecos
  en la numeración que hay que justificar en una fiscalización. Ninguna de
  las dos se paga con lo que resuelve: hoy el único emisor es el almacén
  central, que está en la nube, y el despacho lateral offline es un caso
  que todavía no ocurre.
  Queda así: el despacho lateral offline **se registra** y su guía se emite
  al reconectar. Si alguna vez el reparto lateral se vuelve rutina, la
  salida es la serie por almacén y este párrafo es el punto de partida.
- ✅ 2026-08-06 **Piso absoluto en el margen de ajuste** — resuelto junto
  con el margen por empresa, ver arriba.
- ✅ 2026-08-06 **Merma** — y **sin tabla `stock_merma`** (ADR-028): lo que
  el modelo de datos anticipaba como "subtipo de stock reservado" es
  exactamente lo que `reserva_stock` ya hacía, así que la merma es una
  reserva de tipo `merma` y la migración fue una columna (`lote_id`: lo que
  se aparta por vencido **es** un lote concreto y el desecho tiene que sacar
  ese, no el que FEFO elegiría). Una tabla aparte habría partido el cálculo
  del disponible en dos restas, y dos restas es una que alguien se olvida.
  Ciclo de dos pasos: **registrar** aparta sin descontar —sigue en el
  estante y el conteo lo va a encontrar— y **resolver** decide
  (`desecho` saca el stock y publica `inventory.merma_registrada`, que
  `accounting` asienta como pérdida; `reintegro` lo devuelve a disponible).
  El asiento va al desechar y no al apartar: mientras la auditoría no
  decide, asentar obligaría a reversar la mitad de los casos. Sin permisos
  nuevos —reusa `solicitar_ajuste`/`aprobar_ajuste`, misma segregación—.
  Esto cierra también el `merma` de "tipos de reserva sin productor".
- ✅ 2026-08-06 **`inventory.stock_bajo_minimo` como evento**, publicado
  **al cruzar** el mínimo y no cada vez que se está por debajo: con el stock
  ya bajo, un evento por venta vuelve ruido la alerta —la misma falla que el
  margen de ajuste sin piso—. Reponer y volver a caer avisa de nuevo, que es
  cuando hay que comprar. Sin consumidor todavía (mismo bloqueo de
  notificaciones que `conteo_vencido` y `lote_vencido_detectado`).
