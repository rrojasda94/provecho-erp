# Deuda técnica — Módulo inventory (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-08-30 **Pantalla de stock y kardex**: `GET /inventory/stock` existía
  desde el primer slice y no lo consumía nadie; `MovimientoRepo.q_list`
  existía sin un solo llamador y no había `GET /inventory/movimientos`. Ahora
  `StockOut` viaja rotulado (almacén, artículo, SKU, unidad y sus decimales),
  la consulta filtra por sucursal, categoría, texto y bajo mínimo, y la ficha
  del SKU muestra su kardex. Deuda que queda: la pantalla pide `page_size=200`
  y pagina en el navegador — cablear los controles al servidor sigue anotado
  en `contrato-de-api.md`, y ahora hay una pantalla más que lo espera.

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
- ✅ 2026-08-13 **Las devoluciones se pueden usar**: la API estaba completa
  y la pantalla era una tabla de solo lectura, así que registrar una
  devolución solo se podía llamando al endpoint a mano. Formulario, anular,
  ficha de detalle y `audit_log` en registrar/anular. Suma
  `GET /inventory/skus`, que no existía.
- ⬜ **La devolución se registra de a una línea** (2026-08-13): la API acepta
  varias desde el primer día y el formulario manda una sola. Es el caso real
  —vuelve un producto, se decide qué hacer con él— así que ampliarlo es solo
  pantalla, cuando alguien lo pida.
- ⬜ **La ficha de devolución muestra el UUID de quien la registró**, no su
  nombre (2026-08-13). `inventory` no puede leer `usuario`; hace falta un
  contrato público de `users` tipo `nombres_de_usuarios`, igual que el que
  `sales` usa para los nombres de artículo en el KDS.
- ⬜ **La nota de crédito sigue sin pantalla** (`sales/application/notas_credito.py`):
  es la devolución de una **venta**, no de mercadería, y por eso no entró
  con esto. Sin ella, deshacer algo ya cobrado no tiene camino por UI.
- ✅ 2026-08-15 **El importador se puede usar de verdad** (ADR-048). Desde
  ADR-046 el backend estaba bien y la pantalla no servía para nada: el proxy
  del navegador (`frontend/app/api/proxy/[...ruta]/route.ts`) decodificaba
  todo cuerpo a texto y le fijaba `application/json`, así que la plantilla
  `.xlsx` se bajaba corrupta y con nombre `plantilla.json` —un ZIP no
  sobrevive un `text()` en UTF-8— y la subida de la fase 1 perdía el
  `boundary` del `multipart` antes de salir. Ahora el proxy pasa bytes en las
  dos direcciones y conserva `Content-Type` y `Content-Disposition`.
  Lo que dejó al descubierto es de dónde venía el agujero: los tests del
  importador (`tests/test_recetas_variantes.py`) atacan a FastAPI con
  `TestClient` y **nunca pasan por el proxy**, así que el endpoint podía estar
  perfecto y llegar roto al navegador. Se cierra con dos pruebas nuevas:
  `frontend/lib/proxy.test.ts` (8 casos, milisegundos) y
  `frontend/uso/importador-recetas.spec.ts`, que descarga la plantilla, la
  abre con openpyxl, la llena, la sube y confirma (ADR-047).
- ✅ 2026-08-19 **Requerimiento de la jornada** (ADR-051, RN-INV-023/024,
  migración `b5f27ac41e83`): el local no tenía cómo armar su lista de pedido
  ni el almacén cómo distinguir urgencia de decisión propia, pese a que la
  API de solicitudes existía desde el slice 4. `GET
  /solicitudes/borrador?almacen_id=` arma sola la lista con lo bajo
  `stock_minimo` y `solicitud_item.bajo_minimo_al_pedir` se estampa al
  agregar cada ítem. Suma `GET /conteos` (faltaba) y pantallas
  `/inventario/solicitudes` + `/inventario/conteos`. Deuda que deja abierta:
  - ⬜ **El borrador no se encadena al cierre de un conteo cíclico**: hoy lee
    el `stock_minimo` vigente al abrir la pantalla, independiente de
    ADR-019. El SOP de abastecimiento (`docs/domain/workflows.md`
    §Abastecimiento de locales, paso 4) describe que el conteo **genera**
    el borrador; conectar los dos es una decisión de flujo —¿todo cierre de
    conteo dispara un borrador, o solo el conteo general?— que no se tomó
    en este slice.
  - ⬜ **Recortar lo aprobado por SKU sin pantalla**: `SolicitudAprobar.aprobadas`
    existe desde ADR-020 y la pantalla nueva solo ofrece aprobar tal cual se
    pidió (`aprobadas: []`). Falta el formulario que deje editar cantidad
    por ítem al aprobar.
- ✅ 2026-08-20 **El importador crea el insumo que falta desde el diálogo**
  (ADR-052). El `<select>` de resolución tiene ahora un botón «Crear» con un
  formulario en línea —código, unidad y tipo, con el nombre prellenado del
  archivo— contra `catalogoApi.crearArticulo`, que existía desde ADR-046 y
  cuyo único llamador era `contrato.test.ts`. Lo que dejó al descubierto: el
  docstring del componente, el del caso de uso, la hoja de instrucciones de la
  plantilla y **RN-COM-031** afirmaban desde el 2026-08-13 que eso ya se podía
  hacer. Cuatro textos describiendo una función que no existía; los cuatro
  corregidos con la entrega. Mismo patrón aplicado a las **categorías** al
  importar artículos.
- ✅ 2026-08-20 **La importación actualiza recetas existentes** (ADR-052,
  RN-COM-031). La decisión de negocio que faltaba —qué pasa con los
  ingredientes que el archivo no menciona— se cerró así: **se conservan**, y
  la revisión deja pedir que se quiten **receta por receta**, mostrando cuántas
  líneas se pierden antes de confirmar. El defecto no borra porque el modo de
  falla es asimétrico: subir la hoja equivocada no puede vaciar una receta sin
  que nadie vea el número. La identidad es la columna `ID` que escribe el
  export, no el nombre — el nombre es justamente lo que se edita.
- ⬜ **Los SKU solo se crean por planilla, no se editan** (2026-08-20,
  ADR-052): no existe `editar_sku` en `catalogo.py`, así que un SKU cuyo
  código ya existe se informa como omitido y no se toca. Tocarlo a medias sería
  peor que informarlo, pero corregir un código de barras mal tecleado sigue
  exigiendo la pantalla de a uno. Se cierra agregando `editar_sku` con las
  mismas reglas de unicidad que `crear_sku`.
- ⬜ **`articulo.id_interno` son 4 caracteres únicos en TODO el grupo**
  (2026-08-20): no por empresa —`UniqueConstraint("id_interno")` sin
  `empresa_id`—, así que un catálogo de trescientos artículos exige trescientos
  códigos distintos de cuatro caracteres compartidos entre todas las empresas.
  El importador lo exige y **valida el largo por fila** en vez de
  autogenerarlo, porque un código inventado termina tecleado en una orden de
  compra. Ensancharlo es una migración con datos existentes y no entró acá.
- ⬜ **Los importadores no tienen carril de pruebas contra Postgres**
  (2026-08-20): `pytest` corre sobre SQLite con `create_all`, y el job
  `migraciones` corre Alembic contra Postgres pero **no la suite**
  (`.github/workflows/ci.yml`). SQLite no aplica el largo de un `VARCHAR`, así
  que una fila con el código demasiado largo pasa en verde y da
  `StringDataRightTruncation` en producción. La defensa actual es validar el
  largo **en el importador** y un test que ata la constante a la columna del
  modelo (`test_importacion_articulos.py`), pero eso cubre las columnas que
  alguien se acordó de atar. Se cierra corriendo la suite también contra
  Postgres en CI.

## ~~Mitad-y-mitad: la regla de Odoo descuenta de menos~~ — SALDADA 2026-08-23

`aplica_a_variante` implementa la regla de Odoo 18 al pie de la letra: se
agrupan los valores de la condición por atributo y se exige **al menos uno de
cada grupo**. La consecuencia es que una línea que nombra `Mitad 1` y
`Mitad 2` en la misma condición —que es como viene el archivo de Charlie's—
**no aplica** si solo una de las dos mitades califica. Media americana + media
peperoni no descuenta el jamón.

No es un bug del motor: es el comportamiento del sistema del que salen los
datos, y cambiarlo haría que importar su catálogo descontara distinto a como
descuenta hoy en Odoo, que es peor.

**Cómo se salda: con datos, no con código.** Una línea por mitad, a media
cantidad, cada una condicionada a un solo atributo. Se hace desde la planilla
(ADR-057) sin tocar el motor. `tests/test_variantes_odoo.py` tiene las dos
formas lado a lado —el jamón a la manera de Odoo, la piña por mitad— para que
la diferencia sea visible y para que quien lo arregle sepa contra qué
comparar.

**Saldada el mismo día**, al aparecer la regla que faltaba: las dos mitades
tienen que ser **distintas** (RN-COM-038). Con eso, una condición que pide el
mismo sabor en las dos mitades no es que descuente de menos — es que no se
cumple nunca. Las 52 líneas del archivo resultaron ser **todas simétricas**, y
`scripts/odoo/` las parte en una por mitad con la mitad del gramaje. Ver la
enmienda de ADR-056.

## La condición de una línea no se valida contra el producto (2026-08-23)

`receta_item.aplica_valores` guarda PTAV de `sales`, y `inventory` no puede
verificar contra su ORM que esos valores pertenezcan al producto que usa la
receta. Hoy el único guardarraíl es la lectura conservadora: un valor que
`atributo_de_valores` no reconoce forma su propio grupo y la línea no aplica.

Alcanza para no descontar de más, que es el lado caro, pero deja pasar una
receta mal armada sin avisar. Cuando se construya el editor de la condición
(F4/F5) conviene validarla ahí, donde `sales` sí está a mano, y no en el
camino del descuento.

**Sigue abierta** (2026-08-24, ADR-063). El editor de receta —hoy
`components/catalogo/receta-editor.tsx`, antes el lienzo— solo ofrece las
casillas de los valores del producto abierto, con lo que el caso malo se
reduce a un cliente que llame la API a mano o a una carga masiva. Pero el
servidor sigue sin verificar nada: la validación tiene que vivir en
`inventory/api`, contra el contrato público de `sales`.

## ~~`fusionar()` sumaba las líneas condicionadas como si aplicaran siempre~~ — VOID 2026-08-24 (ADR-063)

Describía un bug de `frontend/lib/nodos.ts::fusionar`, dentro del lienzo. El
lienzo se borró entero en ADR-063 y con él ese archivo, `nodos.aplicaAVariante`
y `lib/nodos.test.ts`. La regla que portaba a JS —agrupar por atributo, Y
entre grupos, O dentro de cada uno, valor huérfano en su propio grupo— sigue
viviendo, y solo, en `inventory/domain/rules.aplica_a_variante`
(`tests/test_receta_condicionada.py`), que es lo único que hoy decide qué
descuenta una venta. No hay una segunda implementación en el cliente que
mantener sincronizada.

## ~~La ficha de receta suelta no muestra la condición~~ — SALDADA 2026-08-24 (ADR-063)

`frontend/components/catalogo/receta-editor.tsx` listaba las líneas planas:
con la mitad-y-mitad se veían veintiséis filas, varias del mismo insumo, sin
decir por qué.

**Cómo se saldó**: `GET /sales/recetas/{id}/atributos` (ADR-063 §4) resuelve
el camino inverso receta → producto → atributos, con herencia del padre
(ADR-042) — el dato que faltaba y que este documento ya anotaba como
solución correcta ("va por el mismo dato que consume el lienzo",
`GET /sales/productos/{id}/arbol`, aunque terminó siendo un endpoint propio
y no el árbol entero). El editor pide esos ejes una vez al montar y dibuja
una columna «Condición» con casillas agrupadas por atributo; lista vacía =
ningún producto usa esta receta, y la columna no se dibuja.

**El bloqueo de insumo repetido (`yaUsados`) también se corrigió**, y no era
solo cosmético: filtraba por `articulo_id` a secas, así que era **imposible**
poner el jamón en la Mitad 1 y en la Mitad 2 — el caso exacto por el que
existe ADR-056. Ahora filtra por `(insumo, condición)`, la misma identidad
del 409 del servidor y de la celda de la matriz.

