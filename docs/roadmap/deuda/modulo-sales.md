# Deuda técnica — Módulo sales (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ⬜ **Un cliente natural no se actualiza por planilla** (2026-08-20,
  ADR-052, RN-PTS-007): de uno que ya existe la carga masiva solo puede
  **completar el documento**. Su nombre, teléfono y domicilio viven en
  `persona` (RN-GEN-007) y `sales` no puede escribirla — el contrato público
  de `users` (`queries_publicas`) es de solo lectura. La fila que los cambie se
  reporta con "se corrige en Personas" y no se aplica a medias, que es lo
  correcto hoy; lo que falta es poder corregirlos de golpe. Se cierra con un
  contrato público de **escritura** en `users`, que es un patrón nuevo y no
  debía inventarse dentro de la carga masiva.
- ⬜ **La carga masiva de clientes no consulta a SUNAT ni a RENIEC**
  (2026-08-20, ADR-052): `consultar_documento=False` a propósito — trescientas
  filas serían trescientas llamadas externas secuenciales dentro de un request,
  contra una cuota. Consecuencia asumida: una razón social mal tecleada en la
  planilla entra tal cual, y solo se corrige editando el cliente de a uno. Se
  cierra encolando la consulta después del commit (una tarea por lote), no
  dentro del request.

- ✅ 2026-08-12 **La orden enviada sigue viva** (ADR-043, RN-COM-029):
  admite líneas nuevas sin firma de nadie, y quitarlas es gratis dentro de
  los 5 minutos. Antes agregar era imposible y quitar exigía siempre el PIN
  de un supervisor — un control que se ejecuta veinte veces por turno deja de
  ser un control.
- ✅ 2026-08-12 **Los borradores vacíos ya no se apilan**: el "+" reusa el que
  esté vacío y una pestaña sin líneas se descarta con su "×".
- 🔶 **El KDS no distingue una línea agregada de las originales**
  (2026-08-12, ADR-043): entra a la cola como cualquier otra, sin decir que
  llegó después. Para la cocina está bien —hay que prepararla igual—, y
  desde ADR-044 el despacho **sí ve que el pedido creció**: su tarjeta lista
  todas las líneas con su estación, así que una recién agregada aparece
  esperando y el contador "N de M" la incluye. Queda solo el matiz de
  antigüedad: no se ve **cuándo** llegó cada una, que es lo que permitiría
  distinguir "falta una que pidieron recién" de "falta una que se atascó".
  Se resuelve mostrando la hora de la línea en la tarjeta, dato que
  `venta_item.created_at` ya tiene. Va junto con "KDS sin reloj por pedido".

- ✅ 2026-08-12 **La variante hereda del padre** (ADR-042): ADR-038 arregló el
  catálogo del seeder (grupos en la variante) y dejó roto el armado a mano
  (grupos en el padre, que es donde el lienzo los cuelga mientras el producto
  no tiene tamaños). Ahora el lugar donde quedó colgado el grupo no decide
  nada.
- ✅ 2026-08-12 **El cajero puede anular una orden enviada** con firma de
  supervisor, igual que para quitar una línea (RN-COM-020). `sales.anular` es
  de supervisor y sigue siéndolo; lo que faltaba era el camino del cajero.
- ✅ 2026-08-12 **Pestaña de cuentas abiertas** en el PDV: estaba como nota al
  pie del mapa de mesas y filtraba fuera las de mesa, así que "¿qué falta
  cobrar?" no se podía responder de un vistazo.

- ✅ 2026-08-12 **La carta lleva los grupos de cada variante** (ADR-038):
  `precios.carta` los leía del producto **padre**, que no tiene ninguno, así
  que el PDV no dibujaba "Sabor" y el servidor rechazaba la venta con 409 por
  algo que la pantalla nunca ofreció. Cierra también el segundo bloqueo: los
  sabores del seeder se creaban **sin precio de lista** y la carta descarta
  todo extra sin precio vigente.
- ⬜ **`GET /carta` consulta grupos y extras producto por producto** (N+1).
  Ya era así antes de ADR-038 —dos consultas por producto— pero ahora corre
  también por cada variante: una pizza de tres tamaños pasó de 2 a 8
  consultas. Es el endpoint más caliente del PDV, aunque se pide al abrir la
  caja y al cambiar de modalidad, no por tecla. Se arregla con dos consultas
  por marca (`grupos_de`/`extras_de` en bloque, agrupadas en memoria); no se
  hizo ahora para no mezclar una optimización con el arreglo de un bug que
  impedía vender. Medir antes con un catálogo real: si el número no molesta,
  no vale el cambio.
- ⬜ **La ficha de producto solo muestra lo que cuelga de ese producto**
  (`/catalogo/productos/{id}`, `catalogo.detalle_producto`). No está mal —es
  por producto a propósito: se edita lo propio, y editar lo heredado desde el
  hijo es cómo se termina con dos copias del mismo grupo (ADR-042)— pero deja
  la pantalla mintiendo por omisión en los dos sentidos: el padre no muestra
  los grupos que viven en sus variantes, y la variante no muestra los que
  hereda, aunque el PDV se los ofrezca. Lo que falta es que lo diga: "hereda 1
  grupo de Pizza" con enlace al lienzo, que es el lugar de trabajo de esa
  estructura (ADR-035).
- ⬜ **Los seeders de demo corridos fuera de orden no avisan nada**
  (encontrado 2026-08-12 al verificar la carta). `pizzas_demo._precio` hace
  `if lista is None: return` y envuelve el resto en un `except Exception`
  mudo, así que correrlo **antes** de `pdv_demo` —que es quien crea la lista
  de precios— deja el catálogo entero sin precios y aun así imprime "Carta de
  pizzas lista: 3 tamaños × 6 sabores + 4 extras". El orden correcto está en
  `docs/engineering/devops.md`, pero el seeder debería negarse a correr sin
  lista en vez de dejar una carta muda.

- ✅ 2026-08-03 **Variantes y grupos de opciones** (ADR-023, migración
  `b6d1e83f47ac`): la variante es un `producto_comercial` hijo con receta y
  **precio completo** propios (RN-COM-022) — no un recargo sobre un precio
  base; el padre no se prepara, no admite precio y vender el padre es 409.
  `producto_opcion_grupo` con `minimo`/`maximo` decide qué grupo de extras
  obliga a elegir (RN-COM-023), validado al confirmar la venta y no solo en
  el PDV; el replay del hub se exceptúa. `GET /productos/{id}` (ficha
  completa) y `GET /marcas` nuevos; `GET /carta` devuelve `variantes[]` y el
  grupo de cada extra. Nombres normalizados a formato título en el servidor
  (`shared/texto.py`). Descartados por reemplazo: `modificador` y
  `variante_producto` del data-model.
- ✅ 2026-08-03 **Pantallas de artículos y de recetas**:
  `/inventario/articulos` (alta y edición de insumos, subrecetas, mercadería
  y empaques) y `/catalogo/recetas` (listado + ficha con "¿qué produce?").
  Cierran el hueco que hacía inusable el catálogo: no había forma de crear un
  insumo propio ni de ver una receta que no colgara de un producto. Con esto
  `/inventario` deja de ser un ícono que lleva a 404.
- ⬜ **Quitar líneas de un consumo de personal no reajusta el gasto**
  (ADR-034): el insumo se repone, pero el asiento —que es de la orden
  entera— queda por el monto original. Solo la anulación **completa** lo
  reversa; reversarlo por una línea borraría el gasto de las que sí se
  comieron, y reasentar la diferencia exige valorizar solo lo quitado. Es la
  misma limitación que la nota de crédito parcial.
- ⬜ **Reporte de consumo de personal** (ADR-034): el gasto se registra y se
  asienta, pero no hay reporte propio en el catálogo cerrado (ADR-024). Hoy
  se lee con `GET /sales/ventas?tipo=consumo_personal` y con los movimientos
  `consumo_interno` de inventario — sirve para revisar, no para que gerencia
  compare sucursales por mes. Falta también el consumo por **motivo**, que
  es la razón por la que el motivo es un enum cerrado.
  `inventory.consumo_personal_valorizado` tampoco tiene **emisión** en el
  catálogo de `reports` (ADR-033): nadie se entera del gasto salvo que lo
  vaya a buscar. Es una entrada en `reports/domain/catalogo.py` más su fila
  en `events.md`, pero primero hay que decidir a qué área se dirige —
  gerencia, contabilidad, o el encargado del local.
- ✅ 2026-08-15 **Los íconos del home ya no llevan a 404** — y hacía rato que no
  lo hacían: los siete destinos que la deuda enumeraba (`/produccion`, `/rrhh`,
  `/marketing`, `/gerencia`, `/usuarios`, `/contabilidad` y el resto de
  `/inventario`) se construyeron en las entregas siguientes y nadie volvió a
  marcar el ítem, así que la deuda siguió declarando un 404 que ya no ocurría.
  Lo que **sí** daba 404 era otra cosa: cinco módulos (`catalogo`, `compras`,
  `inventario`, `organizacion`, `rrhh`) tenían carpeta y `layout.tsx` pero
  ninguna ruta en su raíz, porque el ícono apunta a la primera pantalla
  (`/catalogo/productos`). Nada del shell enlaza ahí, pero sí lo teclea quien
  recorta la URL para subir un nivel — justo lo que uno hace cuando se pierde.
  Ahora cada raíz redirige a `modulo.href` (leído de `lib/modulos.ts`, no
  repetido por archivo) y existe `app/not-found.tsx`: hasta ahora el 404 lo
  resolvía la pantalla por defecto de Next, en inglés y sin salida, que en una
  tablet detrás de la barra se resuelve apagando y volviendo a entrar. La causa
  de fondo era que nada ataba los `href` al árbol de archivos:
  `lib/navegacion.test.ts` cruza `MODULOS` con `SUBMENUS`, y los dos pueden
  coincidir apuntando a una ruta que no existe — por eso el ítem sobrevivió sin
  que nadie pudiera decir si seguía siendo cierto. `lib/rutas.test.ts` resuelve
  los 14 íconos y los 25 ítems de submenú contra los `page.tsx` reales.
- ✅ 2026-08-03 **Catálogo separado del PDV en el frontend**: módulo propio
  (`/catalogo/productos`) con gate por permiso **exacto**
  `sales.gestionar_catalogo`, el mismo que la API exige para escribir. El
  filtro por prefijo del home (ADR-013) dejaba entrar a cualquiera con un
  permiso del área: un cajero leía el catálogo completo y recién al guardar
  chocaba con el 403. `puedeVerModulo()` resuelve prefijo vs permiso exacto
  en un solo lugar, usado por el grid y por el guard de `ModuloShell`.
- ⬜ **El backend del catálogo sigue en `sales`**: se evaluó mover
  `producto_comercial`/`precio` a un módulo `catalog` propio y se descartó —
  la autorización es por permiso, no por módulo, así que mover 5 tablas y sus
  FKs no habría ganado nada de seguridad. Revisar si algún día el catálogo
  necesita reglas de dominio que hoy no tiene.
- 🔶 **Ordenar y desarmar grupos de extras**: desarmar ✅ 2026-08-09
  (ADR-035) — `DELETE /productos/{id}/extras/{extra_id}` y
  `DELETE /productos/{id}/grupos/{grupo_id}`; borrar un grupo suelta sus
  extras en vez de borrarlos, porque el extra es un producto con su receta y
  su precio. Queda ⬜ **reordenar por arrastre**: el campo de dominio `orden`
  se sigue tecleando. `@dnd-kit` ya está instalado (se usa en el tablero de
  reportes), así que es trabajo de pantalla, no de contrato. **No confundirlo
  con arrastrar nodos en el lienzo**, que es posición visual y no se guarda.
- ⬜ **`receta_item.quitable`** (2026-08-09, ADR-035 §2): hoy **todo** insumo
  de la receta se puede pedir "sin". Se evaluó un flag para que Producción
  vetara restas absurdas ("pizza sin masa") y se descartó por ser una segunda
  fuente de la misma verdad, y porque el caso es inocuo — la resta no cambia
  el precio y cocina ve el pedido antes de prepararlo. Revisar si aparece un
  caso real donde quitar un insumo arruine el plato de forma cara; es una
  columna y un checkbox.
- ⬜ **Restas en una línea ya enviada a cocina**: al reabrir una línea que ya
  existe como `venta_item`, el PDV no recupera sus restas —
  `GET /ventas/{id}/items` no las devuelve— y las muestra vacías. Hoy
  corregir lo enviado es anular la línea y crear otra (RN-COM-020), así que
  no se pierde nada, pero el contrato debería devolverlas igual.
- ⬜ **La columna de "disponibles" del lienzo lista los sabores de los otros
  tamaños** (2026-08-09). Es correcto según el modelo —para *este* tamaño no
  están vinculados— pero con seis sabores por tres tamaños son dieciocho
  nodos apagados. Se envuelve en subcolumnas y no se monta sobre nada, pero
  conviene filtrarlo (por ejemplo, esconder lo que ya está vinculado a otra
  variante del mismo padre).
- ⬜ **Reabrir una receta editada desde otro nodo no refresca el costo de los
  demás nodos** hasta cambiar de camino: el cache se actualiza por receta, no
  se recalcula el grafo entero. No da un número incorrecto —el nodo editado
  sí se actualiza— pero el pie de otro nodo puede quedar viejo.
- ⬜ **Confirmación al borrar un grupo de opciones**: `DELETE .../grupos/{id}`
  no pregunta nada. Es destructivo y hoy vive detrás de un menú `⋯`; agregar
  el diálogo es cambio de comportamiento, así que va aparte.
- ✅ 2026-08-03 **Convertir un producto simple en uno con presentaciones**
  (`quitar_receta`) y **borrar presentaciones y recetas** con las dos
  negativas que importan: un producto ya vendido se descontinúa en vez de
  borrarse, y una receta en uso nombra al producto que la usa.
- ✅ 2026-07-28 **Slice PDV** (ADR-018, migración `d7e3b8c14f52`): cierra
  los cuatro huecos que destapó el diseño del punto de venta —
  `mesa` tipada por sucursal + `venta.mesa_id`/`comensales` con mapa de
  salón derivado (`GET /sales/mesas/mapa`, permiso `sales.gestionar_mesas`);
  `grupo_cobro` en `venta_item`/`pago`/`comprobante` para dividir la cuenta
  y emitir un comprobante por pagador (RN-COM-018);
  `comprobante.receptor_num_doc`/`receptor_nombre` para el DNI/RUC tecleado
  en caja, que decide boleta o factura sin exigir cliente registrado
  (RN-CPP-003); descuento manual de orden con motivo y autorizador
  (RN-COM-017, permiso `sales.aplicar_descuento` separado de
  `sales.cobrar`). Suma `POST /sales/clientes` (alta desde caja) y
  `GET /sales/ventas` (jornada por sucursal). Migración sin backfill y
  clave de idempotencia del grupo 1 intacta; 24 casos en
  `tests/test_pdv_slice.py`. **Pendiente derivado:**
  - ⬜ **Motor de promociones condicionales** por marca/sucursal — se
    activan solas si el pedido cumple reglas (ej. segunda pizza a mitad de
    precio si pide dos del mismo tamaño, en días vigentes, sobre el precio
    base de la más barata, sin incluir extras). Requiere entidad
    `promocion` con vigencia, condiciones de activación y base de cálculo.
    **No debe reutilizar `venta.descuento_*`**: esos campos son de un acto
    humano autorizado, con motivo y responsable; mezclarlos haría imposible
    auditar cuál descuento fue manual y cuál automático (ADR-018 →
    «Frontera explícita»).
  - ✅ 2026-08-02 **Alta de cliente/proveedor jurídico consulta Factiliza
    para el nombre/razón social** (`RENIEC`/`SUNAT` vía el mismo proveedor,
    ADR-005 ya lo dejaba previsto). `FactilizaClient.consultar_dni`/
    `consultar_ruc` (host propio, `FACTILIZA_CONSULTA_BASE_URL` —
    `api.factiliza.com`, **distinto** de `FACTILIZA_BASE_URL` que es solo
    emisión de comprobantes contra la QA `apife-qa.factiliza.com`; y **token
    propio**, `FACTILIZA_CONSULTA_DOCUMENTO_TOKEN` — acá decía "mismo token"
    y era falso, corregido el 2026-08-22). `nombres_desde_dni`/`razon_social_desde_ruc`
    (`src/shared/integrations/factiliza/`) hacen fallback a lo tecleado si
    Factiliza no responde o no encuentra el documento — el alta nunca se
    bloquea por un proveedor externo caído. Cableado en
    `sales/application/clientes.py` (natural por DNI nuevo, jurídico por RUC
    nuevo) y `purchases/application/proveedores.py` (jurídico por RUC).
    Documento ya registrado en `persona` no vuelve a consultar. Probado con
    datos reales de QA: DNI 73632127 (Carlos Renato Rojas del Aguila) y RUC
    20610077782 (Servicios Rentaurant S.A.C., estado BAJA DE OFICIO — el
    consumo no valida `estado`/`condicion`, solo usa el nombre; bloquear por
    RUC no-HABIDO queda para cuando el negocio lo pida). 20 tests nuevos
    (`tests/test_factiliza_consulta.py` + casos en `test_pdv_slice.py`/
    `test_purchases.py`); `tests/conftest.py` nuevo, autouse que fuerza
    `factiliza_token=""` por test para que el suite nunca dependa de la red
    aunque el `.env` local tenga un token real.
  - ✅ 2026-07-28 **Cliente identificado por teléfono** (migración
    `e1c4a9d6b038`): `persona.numero_documento`/`tipo_documento` pasan a
    nullable, conservando el UNIQUE. Registrar a una persona natural exige
    teléfono, no DNI (RN-PTS-004); el documento se completa después
    (`PATCH /sales/clientes/{id}/documento`). RUC obligatorio solo para
    facturar a empresas. Sin documento o con `00000000` el cliente no
    cuenta como identificado y queda fuera de las promociones para
    clientes registrados (RN-PTS-005). Búsqueda por teléfono, documento o
    nombre (`GET /sales/clientes/buscar`, RN-PTS-006). Trabajador y usuario
    siguen exigiendo documento — validación en `users.application.admin`.
  - ⬜ **Reenvío del comprobante al cliente** (WhatsApp/correo) desde la
    pestaña de cobrados: falta el adaptador de notificaciones.
  - ⬜ `grupo_cobro` es un entero sin entidad detrás: nada impide un grupo 7
    sin grupos 1-6. Se valida en el caso de uso, no en el esquema.
  - ✅ 2026-07-28 **Frontend del PDV** en `frontend/app/pdv/`, contra los
    endpoints reales: apertura de caja con firma del encargado, catálogo con
    extras, ticket multi-borrador con selección por pulsación larga, mapa de
    mesas, cobrados del día y cobro con split de medios. Proxy
    `/api/proxy/[...ruta]` para que el token httpOnly no llegue al navegador.
    Verificado de punta a punta contra la API: venta con extras (94.00
    correcto), cobro dividido en dos cuentas con dos boletas y receptores
    distintos, y factura por RUC. **Pendiente de esta pantalla:** el botón
    "Más opciones" (descuento, anular líneas, precuenta, movimiento de
    efectivo) está cableado en backend pero no en la UI; y agregar productos
    a una orden ya enviada exige abrir una orden nueva — falta un endpoint
    que sume ítems a una `venta` existente.
- ✅ 2026-07-28 **Cierre del PDV para alfa** (ADR-018 §5-7, migraciones
  `f2a8c15e94d7` + `a3f0d29b6c81` + `b6d41e07af92`):
  - **Extras** (RN-COM-021): un extra es un `producto_comercial` con
    `es_extra=True` y receta propia; `producto_comercial_extra` define qué
    producto admite cuál y `venta_item.padre_venta_item_id` de qué línea
    cuelga. Hereda el grupo de cobro del padre y su consumo se multiplica
    por el plato. Reusa precio server-side, carta y descuento de inventario
    sin duplicar nada.
  - **Anular líneas enviadas** (RN-COM-020) y **precuenta** (RN-COM-019).
  - **Autorización de supervisor por PIN** (RN-AUD-005): cierra un hueco de
    seguridad — `autorizado_por` ya no viene del cuerpo del request.
  - **Movimiento de efectivo en caja** (RN-MDP-007) sumado al esperado del
    cierre.
  - **CI ejecuta las migraciones** contra Postgres real, ida y vuelta, más
    `alembic check`. Destapó y corrigió cuatro columnas `json` que debían
    ser `jsonb` y cinco índices/constraints declarados solo en la migración.
  - **Pendiente para después del alfa:** `variante_producto` (tamaños como
    variantes en vez de productos separados), mitad-y-mitad de pizza,
    `cuenta_puntos`/`puntos_movimiento` (canje real de puntos).
- ✅ 2026-07-27 **Precio server-side** (`lista_precio`/`precio`): el PDV
  ya no manda `precio_unitario` — `crear_venta` lo resuelve por
  marca+sucursal+canal+modalidad+fecha (RN-PRC-003/RN-MDC-003). Gana la
  lista promocional, luego la más específica, luego la de vigencia más
  reciente; al vencer la promoción el precio regular vuelve solo. Sin
  precio vigente la venta es 409 y el producto no sale en `GET /carta`.
  `precio` no tiene endpoint de edición: corregir = lista nueva
  (RN-PRC-005). Migración `d4b1f0a7c3e9` (cierra además la FK pendiente
  `medio_pago.lista_precio_credito_id`). El replay offline del hub
  conserva el precio cobrado (`VentaItemSyncIn`, ADR-009). Pendiente:
  `promocion` como entidad propia (material, guion, capacitación) y el
  cálculo de margen de contribución expuesto a Comercial (RN-CML-001).
- ✅ 2026-07-26 **Comprobante** (boleta/factura vía **Factiliza**) — venta
  `pagada` → `facturada`; series por `punto_venta`; correlativo por
  (empresa, serie); cola Celery con reintentos. Migración `b3d7f21ac094`.
- ✅ 2026-08-04 **Nota de crédito** (RN-CPP-009, migración `c2f7a91b4e08`,
  `sales/application/notas_credito.py`): total o **parcial por ítem**, con
  motivo del catálogo 09, contra un comprobante aceptado y una sola vez por
  documento. Serie propia por punto de venta (`serie_nc_boleta`/
  `serie_nc_factura`, nullable — sin ella no emite y lo dice, en vez de
  quemar un correlativo en la serie equivocada). Tres decisiones quedaron
  explícitas porque no tienen respuesta universal: **`repone_stock` lo
  declara quien acredita** (un plato devuelto en cocina rara vez devuelve el
  insumo, y corregir un RUC no toca inventario); **el motivo decide si la
  venta muere** —anulación y devolución la dan de baja, los de corrección de
  datos (02/03) no, solo liberan el comprobante para reemitir el corregido—;
  y **una nota rechazada por SUNAT no corrige nada**, queda registrada con
  su motivo. Las notas parciales sucesivas cuentan contra lo que queda por
  acreditar, no contra lo vendido. Permiso propio `sales.emitir_nota_credito`
  (supervisor). 14 tests.
- ✅ 2026-08-04 **Descarga de PDF / XML / CDR**
  (`GET /sales/comprobantes/{id}/descargar/{formato}`, permiso `sales.leer`):
  el PDF que se entrega al cliente y el **XML firmado** y el **CDR** que son
  el respaldo ante SUNAT. Se piden a Factiliza en el momento y **no se
  archivan**: su copia es la buena mientras el proveedor siga activo, y una
  nuestra podría quedar desincronizada sin ganar nada. Los bytes vuelven tal
  cual — reescribir un XML firmado lo invalida. Solo de un comprobante
  `aceptado`: antes no hay XML ni CDR que bajar.
- ✅ 2026-08-05 **Guía de remisión electrónica** (`/despatch/send`) — se
  construyó en **`inventory`**, no acá (ADR-027): lo que la guía declara es
  un traslado entre almacenes, no una venta, y `sales` no conoce almacenes.
  Que sea un documento de SUNAT no la vuelve de este módulo. Lo que sí es
  deuda de `sales` es la guía de una **venta con reparto a domicilio**, y
  espera a que exista reparto propio.
- ⬜ **Comprobante sin correlativo reservado**: si Factiliza rechaza, el
  correlativo queda consumido por una fila `rechazado`. SUNAT admite
  huecos, pero conviene revisar si el negocio quiere reusarlo.
- ✅ 2026-08-06 **Barrido de comprobantes pendientes**
  (`sales.barrer_comprobantes_pendientes`, cada 15 min). Encola **uno por
  comprobante** en vez de emitir en línea: cada uno conserva su backoff y su
  cuenta de intentos, y un barrido que emitiera en serie convertiría una
  caída de Factiliza en un ciclo de 100 timeouts. `pendientes` gana filtro
  por intentos: un `rechazado` es un veredicto de SUNAT sobre datos malos
  —reenviarlo da el mismo rechazo— y uno que agotó sus 5 intentos daría
  `Conflicto` cada ciclo, para siempre.
- ⬜ **Webhook de pasarela** (Izipay): hoy el pago nace `confirmado`
  (PDV presencial); pago online requiere estado `pendiente` + confirmación.
- ✅ 2026-08-04 **Enlace con caja** (ADR-025): `registrar_pago` rechaza el
  cobro con 409 si el punto de venta no tiene turno abierto, preguntando
  por el contrato público `accounting.hay_caja_abierta`. Vale para todo
  medio de pago, no solo efectivo — el cierre cuadra también las tarjetas
  (RN-POS-004). Única excepción: el replay del push del hub.
- ⬜ **Consumo de subrecetas anidadas**: el listener expande un solo nivel
  de receta; una receta cuyo ítem es `subreceta` no explota recursivo aún.
- ⬜ Modificadores/variantes/combos, `central_pedidos` (pantalla y
  agregación), puntos/loyalty, kiosk UI. **UX definida** (2026-07-26,
  `docs/product/ui-ux.md`): seleccionar un producto comercial en PDV/Kiosk
  abre un dialog de personalización con sus modificadores admitidos
  (tamaño/combinación/extras/restas), que produce una `variante_producto`;
  orden fijo tamaño→combinación→extras→restas (RN-PRD-004). Falta definir
  si combo se configura en el mismo dialog o en uno propio, y el
  comportamiento en Kiosk (autoservicio) vs. PDV asistido.
- ⬜ **Buscador contextual de producto** (PDV/Kiosk/web): por nombre,
  por insumo/ingrediente (cruce `receta_item`) y por exclusión ("que no
  tenga X"); lista de resultados ordenada por relevancia cuando no hay
  match único. Ranking por **historial de uso/patrones detectados**
  (decidido 2026-07-26, no solo similitud de texto) — objetivo explícito:
  reducir fricción de búsqueda en versiones futuras a medida que aprende.
  UX especificada en `docs/product/ui-ux.md`, sin implementar — full-text
  search (`pg_trgm`/`tsvector`) como base, historial como señal encima.
- ⬜ **Dialog de venta sugerida (upsell) al ir al carrito**: productos
  complementarios de adición rápida, descartable sin bloquear el flujo.
  Criterio de sugerencia decidido (2026-07-26): complementos del producto
  elegido (ej. bebidas) + producto en promoción vigente. UX especificada
  en `docs/product/ui-ux.md`; falta definir cómo se configura la relación
  producto→complemento (fija vs. regla de venta cruzada).
- ⬜ **KDS tiempo real**: la pantalla (2026-08-03) refresca por polling
  cada 3 s; push por WebSocket/Redis pub-sub (Redis reservado para
  pantallas/colas/sesiones) sigue sin implementar.
- ⬜ **KDS sin reloj por pedido**: Odoo colorea la tarjeta al superar un
  umbral de espera; acá `GET /kds/pantallas/{id}/cola` no devuelve
  `fecha_orden`, así que no hay de dónde calcular el tiempo transcurrido.
  Va junto con "KDS tiempos" (abajo): agregar el timestamp al payload es
  el primer paso.
- ⬜ **KDS aviso de anulación**: si anulan un pedido ya en preparación, la
  tarjeta solo desaparece al refrescar — falta aviso explícito "ANULADO"
  (llega natural con el push de tiempo real).
- ⬜ **KDS impresión física**: la comanda sale como texto 32 cols; falta
  puente a impresora térmica (ESC/POS por red o agente local) y comanda
  automática al confirmar venta (hoy es bajo demanda).
- ⬜ **KDS tiempos**: alertas por pedido demorado (umbral por pantalla) y
  métricas de tiempo de preparación (base: `venta_item.updated_at`). Con la
  cadena de ADR-044 esto se vuelve **tiempo por estación**, que es lo que
  responde "dónde se atasca la cocina" en vez de "cuánto tardó el pedido".
- ⬜ **La cadena de estaciones no se reordena arrastrando** (2026-08-13,
  ADR-044): el paso se teclea como número en el formulario de la estación.
  Para tres estaciones alcanza; con más, dejar un hueco entre pasos (0, 10,
  20) para poder insertar en el medio es un truco que el usuario tiene que
  saber, y eso ya es una interfaz que no se explica sola.
- ⬜ **Una estación no puede rechazar y devolver una línea al eslabón
  anterior** (2026-08-13, ADR-044): la cadena solo avanza, por RN-CUP-002
  (secuencia estricta, sin retroceso). Si el horno recibe algo mal armado,
  hoy no hay forma de mandarlo de vuelta desde la pantalla — se resuelve
  hablando. Un "devolver al paso anterior" sería una excepción explícita a
  RN-CUP-002 y necesita su propia decisión de negocio, no solo código.
- 🔶 **Cumplimiento de pedido** (`PROC-OPE-002`, definido 2026-07-27):
  preparación + entrega implementadas (`POST /sales/ventas/{id}/entrega`
  → `sales.venta_entregada`). Falta la **rama delivery con trazabilidad**:
  entidad `entrega` especificada en `data-model.md` §6 (repartidor propio
  vs. plataforma externa, hora de salida, resultado `entregado`/`fallido`
  con motivo — RN-CUP-007/008, evidencia). Hoy una entrega fallida no se
  puede registrar: solo se marca el pedido entregado o no se marca nada.
- ⬜ **Plazo de espera de takeout no recogido** (RN-CUP-011): la regla
  existe, el plazo por sucursal no está configurado ni modelado.
- ⬜ **Escalar un problema sin reporte previo** (RN-CTP-004, deuda declarada
  en ADR-036): la cadena de escalamiento ya existe, pero solo se puede abrir
  sobre un `reporte_emitido`, y el catálogo cerrado no produce ninguno para
  `queja`, `error_sistema` ni `desistimiento_no_resuelto`. Un cliente que se
  queja en el mostrador no genera ningún hecho en el bus. Haría falta una
  emisión `sales.queja_registrada` con endpoint de alta — que choca de frente
  con el «no hay `POST /emitidos`» de ADR-033, así que la decisión de fondo es
  **dónde nace una queja**: como venta anotada, como nodo de encuesta, o como
  la primera emisión del ERP que sí admite alta manual.
- ✅ 2026-08-15 **Las FK se validan en todo el suite, no solo en
  `test_pdv_slice`**. Un listener del evento `connect` de SQLAlchemy en
  `tests/conftest.py` enciende `PRAGMA foreign_keys=ON` en **cualquier**
  engine SQLite del proceso: los ~75 fixtures que arman el suyo quedan
  cubiertos sin tocarlos, y no hay forma de olvidárselo en el próximo.
  Destapó cinco violaciones: **dos bugs de producción** —borrar una receta
  con líneas moría por `fk_receta_item_receta_id_receta` (SQLAlchemy ordenaba
  el `DELETE` del padre antes que el de los hijos: ninguna receta con insumos
  se podía borrar) y `reports.emision` guardaba `almacen_id`/`sucursal_id`/
  `actor_id` de filas inexistentes, o sea que el reporte «que no se pudo
  ubicar» —el que más importa investigar— era el único que no se emitía— y
  **tres tests** que sembraban un `uuid4()` en una columna FK
  (`test_sync_motor` ×2, `test_marketing`).
  `test_models.py::test_un_engine_sqlite_nuevo_ya_trae_las_fk_encendidas`
  cuida al guardián.
- ⬜ **La cascada del extra vive en el código, no en el esquema**
  (2026-08-13): `anular_lineas` borra los hijos a mano porque
  `fk_venta_item_padre` es `NO ACTION`. Un `ON DELETE CASCADE` en la FK lo
  haría cumplir aunque otro camino borre el padre. Es una migración de una
  línea; se dejó fuera para no mezclar un cambio de esquema con un arreglo
  que ya estaba probado. **Sigue abierto tras el barrido de FK del
  2026-08-15**: el mismo criterio aplica ahora a
  `fk_receta_item_receta_id_receta`, que se arregló forzando el orden del
  flush (`recetas.eliminar_receta`) y no en el esquema. Las dos son la misma
  migración y conviene hacerlas juntas, contra un Postgres real.
- ✅ **El receptor del comprobante en el PDV no tiene el botón «Buscar por
  DNI/RUC»** (2026-08-15, ADR-041) — **cerrado el 2026-08-22** (addendum de
  ADR-041). Era donde más se teclea un documento —el cajero lo pide para
  emitir la factura— y el único de los cuatro puntos que quedó sin la
  consulta, con el `cajero` teniendo el permiso justamente por este caso.
  Lo que quedaba por decidir era dónde deja el dato: `BuscarDocumento`
  escribe en el **DOM** del `<form>`, y el PDV lleva estado de React. Se
  resolvió con `ConsultaDocumento`, la misma lógica en versión **controlada**
  —recibe el número tecleado y devuelve la respuesta cruda por `onDatos`—, en
  vez de rehacer el diálogo de cobro como formulario no controlado. Quedó en
  los **dos** puntos del PDV donde se identifica a alguien que aún no existe:
  el alta de cliente y el receptor del comprobante. Y con modo `auto`: en caja
  hay un solo campo, así que el largo decide el padrón (RN-CPP-003, regla en
  `frontend/lib/documento.ts` con su prueba).
