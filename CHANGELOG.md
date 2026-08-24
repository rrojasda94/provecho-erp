# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Versionado: [SemVer](https://semver.org/lang/es/).

Lo que todavía no se publicó **no se escribe acá**: cada cambio deja su
archivo en [`changelog.d/`](changelog.d/) y `python scripts/cortar_version.py`
los junta en una sección nueva al cortar la versión. Dos ramas en paralelo
editando este archivo chocaban siempre — escribían en la misma línea.

## [Unreleased]

Ver [`changelog.d/`](changelog.d/).

## [0.7.3] - 2026-08-24

### Added

- **Ya se puede decir dónde trabaja alguien y qué locales alcanza su cuenta**
  (2026-08-24, ADR-062, migración `b6d29f10c47e`). Eran dos huecos que desde
  la pantalla se veían como uno: `trabajador` no tenía sucursal —la asistencia
  no tenía a qué local atribuirse y el reemplazo entre sucursales
  (RN-RRHH-011) no era representable— y `usuario_sucursal` tenía endpoints
  desde el slice inicial **pero ninguna pantalla**, así que fuera del seeder
  nadie repartía alcance. Ahora `trabajador.sucursal_id` (nullable) es el
  centro de labores, un hecho laboral que vive en RRHH → Trabajadores, y el
  alcance de datos se reparte en Usuarios → Cuentas con la misma celda de
  chips que ya se usaba para los roles. Un supervisor a cargo de varios
  locales son **varias filas** de `usuario_sucursal`: se descartó una tabla
  `zona` porque hoy ningún reporte, permiso ni regla la nombra — sería una
  entidad con su tenant, su seeder y su CRUD para ahorrar dos clics. El costo
  aceptado: el alcance viaja en el token, así que un cambio le aplica a esa
  cuenta recién cuando su sesión renueve; la pantalla lo advierte en vez de
  invalidar tokens vivos.
- **`GET /users/{id}/sucursales`**: el alcance de una cuenta ajena no se podía
  leer. `/users/me` devolvía el propio, que no sirve para administrar a otro.

- **Staging se despliega desde GitHub** (ADR-060). Actions → *Desplegar* → Run
  workflow, se elige la versión y listo. Se puede desde un teléfono.

  ADR-008 había dejado el despliegue manual "hasta que exista el VPS". El VPS
  existe, y lo que quedó no era un despliegue manual sino uno **atado a una
  máquina**: hace falta esa PC, con esa llave, y la llave tiene passphrase —
  así que tampoco sirve desde un shell no interactivo. Eso dejó staging sin
  actualizar con 0.7.1 ya publicada, porque quien tenía que desplegar estaba
  en otra ubicación.

  Sigue siendo un **acto explícito** (`workflow_dispatch`, no `on: push`), que
  es lo que ADR-008 protegía. Lo que cambia es que ese alguien puede estar en
  cualquier parte.

  - El script de despliegue **viaja del repo al servidor** en cada corrida, en
    vez de asumir que allá hay una copia: una copia vieja es un despliegue que
    hace algo distinto de lo que dice el repo.
  - La huella del servidor va en un secreto, no `StrictHostKeyChecking=no`.
  - Se comprueba la versión **desde afuera**, contra el dominio público: que
    el contenedor arranque no significa que el proxy lo esté sirviendo.
  - La carga del catálogo solo se ofrece **en simulación**, que no escribe
    nada. La de verdad se hace a mano mirando ese resultado.

  Requiere dos secretos, documentados en `docs/engineering/devops.md`.

- **Landing pública «Queremos RE-conocerte» y cupón de 10 %** (2026-08-24,
  ADR-061). Un QR en la mesa lleva a `/reconocerte`, donde un cliente de
  Charlie's deja DNI, cumpleaños, dirección y teléfono sin necesidad de
  cuenta, y recibe un cupón de un solo uso para su siguiente compra. La caja
  lo canjea con `POST /sales/ventas/{id}/cupon`, y ahí queda desactivado para
  siempre.
- **El cupón vive en `sales`, no en `marketing`.** Registrar al cliente y
  descontar la venta son dos escrituras dentro de `sales`, y un módulo solo
  entra a otro por `api.deps` o `queries_publicas` — ninguno de los dos sirve
  para escribir. Ponerlo en `marketing` habría exigido ampliar la lista de
  excepciones cruzadas de `tests/test_arquitectura.py`, que es justo la deuda
  que esa lista existe para no seguir acumulando. Marketing se entera por
  `sales.cliente_registrado_en_promocion` y crea su `lead`, igual que ya hace
  con `sales.venta_confirmada`.
- **El descuento reusa `venta.descuento_*` con un motivo nuevo, `cupon`.** El
  costo aceptado: esas columnas eran del descuento manual, y ahora comparten
  tabla con uno que nadie autorizó. Se paga porque la alternativa —un canal de
  descuento paralelo— obligaba a tocar `total_a_cobrar`, el prorrateo que
  SUNAT exige en el comprobante y las notas de crédito, que es la parte que
  maneja dinero y ya funciona. El motivo propio deja al reporte de descuentos
  separar el margen regalado a criterio del prometido en campaña, que era la
  auditabilidad que ADR-018 protege. **El motor de promociones condicionales
  sigue sin poder reusarlas**: ahí no interviene nadie.
- **El canje no pide PIN de supervisor**, a diferencia del descuento manual
  (RN-COM-017). El cupón ya era del cliente y el cupón es la autorización;
  pedir un supervisor por cada uno haría que la caja deje de canjearlos, que
  es la forma más segura de romper la promesa de la campaña.
- **La superficie pública escribe pero no borra, y solo lee un booleano.** No
  hay ningún `DELETE` —la baja de datos se atiende por `hola@majambo.com.pe`
  con la anonimización de ADR-011, nunca desde una página abierta a internet—,
  la consulta devuelve `{registrado: bool}` y nada más, y el `grupo_id` sale
  de la promoción activa y jamás del request. Lo único que la protege es el
  rate limit por IP, en tres niveles según lo que cuesta cada llamada: el más
  duro (5/hora) es el que convierte un DNI en un nombre, porque es el que
  permitiría enumerar documentos. Es el costo aceptado de que el cliente
  confirme su nombre en vez de teclearlo.
- **El código del cupón es el DNI** (lo pidió el negocio). El cliente no tiene
  nada que recordar ni guardar, y devolverlo en la respuesta no filtra nada
  porque es el número que él mismo acaba de escribir. A cambio, quien conozca
  un DNI ajeno podría intentar su cupón: se acota atándolo al cliente de la
  venta, no se elimina.
- **La empresa puede terminar la promoción en cualquier momento** con
  `POST /sales/promociones-cupon/{id}/termino` (`sales.gestionar_promociones`,
  del rol `supervisor`). Deja de emitir cupones nuevos y **no toca los ya
  entregados**: quien alcanzó a registrarse cumplió su parte del trato.
- **Los logotipos de `frontend/public/marcas/` son provisionales.** Están
  armados con tipografía y los colores de marca, no con los originales. Para
  poner los definitivos alcanza con reemplazar el archivo conservando el
  nombre — ningún componente cambia. Ver `frontend/public/marcas/README.md`.
- **El teléfono reconoce a un cliente, pero no reescribe su identidad.** Se
  le completa el documento solo a quien no tiene ninguno: sin ese candado,
  saber un teléfono ajeno alcanzaba para cambiarle el DNI a su dueño desde
  una página abierta a internet, y quedarse con su historial de compras. Un
  teléfono que ya es de alguien identificado se ignora y el registro entra
  como cliente nuevo — dos fichas con el mismo teléfono se limpian, una
  identidad pisada no. Apareció probando el flujo contra la API real; los
  tests no lo cubrían.

### Fixed

- **La receta de la mitad-y-mitad se veía en plano, sin decir qué mitad lleva
  cada insumo** (enmienda de ADR-056). Con el catálogo de Charlie's cargado,
  el lienzo de `Pizza MitadxMitad Familiar` listaba sus 26 líneas seguidas
  —`Salame Picado` tres veces— y el nodo `Americana F` respondía "no tiene
  receta todavía", que es falso: sus insumos son líneas condicionadas de la
  receta del tamaño.

  El dato estaba bien. `receta_item.aplica_valores` existe desde ADR-056 y el
  motor de descuento lo respeta; lo que faltaba era que la API de la receta
  lo devolviera y lo aceptara. Hasta ahora solo lo tocaba la matriz, y la
  matriz muestra UUID.

  - `GET /inventory/recetas/{id}` devuelve la condición de cada línea, como
    **lista de texto y siempre lista, nunca `null`**: el editor no tiene que
    distinguir dos formas de "sin condición".
  - `POST`/`PATCH .../items` la aceptan. En el `PATCH` los tres estados
    importan: ausente no toca la condición, `[]` la borra y una lista la
    reemplaza. Sin distinguir "no lo edito" de "lo limpio", cambiar un
    gramaje habría borrado la condición de rebote.
  - Tocar el nodo de un sabor abre **sus** líneas y agrega las nuevas ya
    condicionadas a él. En el nodo del tamaño, cada línea muestra su
    condición con nombre ("Mitad 1 F: Americana, Hawaiana") y se edita ahí
    mismo, con casillas agrupadas por atributo y un botón "Aplicar" — un
    `PATCH` por casilla podía dejar el cambio a medias en un 409.
  - El mismo insumo ya se puede repetir con **otra** condición desde el
    editor, que es el caso que todo el modelo existe para resolver: el jamón
    en la Mitad 1 y en la Mitad 2 son dos líneas de la misma receta.

- **Duplicar una receta perdía la condición de sus líneas** (encontrado al
  hacer lo anterior). `duplicar_receta` copiaba artículo, cantidad, expresión
  y merma, y dejaba afuera `aplica_valores`, `unidad_medida_id` y `orden`.
  Duplicar la mitad-y-mitad daba 26 líneas sin condición: una receta que
  descuenta todos los insumos de todas las mitades, siempre, sin que nada lo
  diga hasta cuadrar el mes.

- **La pestaña "Plato" también sumaba las líneas condicionadas como si
  aplicaran siempre** (misma enmienda). El costo simulado del plato quedaba
  por encima del real, y con las condiciones ya visibles en la otra pestaña
  el contraste se notaba más que antes.

  `fusionar()` ahora usa `aplicaAVariante` — un puerto literal de la regla
  del servidor (`inventory/domain/rules.aplica_a_variante`, RN-COM-037):
  mismo agrupado por atributo, mismo Y entre grupos y O dentro de cada uno.
  Es la duplicación que ADR-056 §5 evitó en el backend, aceptada acá a
  propósito — la alternativa era un endpoint nuevo por cada clic en un
  sabor, para un número que ya es una simulación. Las dos implementaciones
  se prueban con los mismos casos, para que un día que diverjan se note en
  la suite.

- **Desplegar dejaba el dominio público en 502 con la API sana.** Caddy
  resuelve `reverse_proxy api:8000` una sola vez, al arrancar; recrear el
  contenedor `api` le da una IP nueva en la red de Docker y Caddy sigue
  hablándole a la vieja. Pasó desplegando la 0.7.2, y cuesta más
  diagnosticarlo que arreglarlo: `api` figura `Up (healthy)`, `init` termina
  en 0 y el `curl` al loopback responde, así que todo apunta a otro lado. Lo
  único que lo delata es el `CREATED` del `docker compose ps -a` — Caddy con
  horas de vida y `api` con minutos.
- `scripts/desplegar.sh` reinicia Caddy después del `up -d`, así que todo
  despliegue lo cubre, incluido el workflow de ADR-060 — que si no habría
  fallado siempre: su último paso comprueba la versión contra el dominio
  público, justo lo que el 502 rompe. El script tampoco se conforma ya con el
  loopback: espera a `/health/ready` **por el dominio**, que es lo único que
  prueba que el proxy está sirviendo, y si falla ahí dice que mire los logs
  del proxy y no los de la API.
- La solución de fondo —los upstreams dinámicos de Caddy, que re-resuelven el
  DNS— queda en `docs/roadmap/deuda/ci-cd.md` con la configuración escrita: un
  reinicio de proxy por despliegue es un corte de segundos que staging se
  banca y producción no, pero un `Caddyfile` inválido deja staging sin proxy y
  eso hay que validarlo contra el servidor antes de aplicarlo.

### Security

- **Asignar un local al alcance de una cuenta no validaba tenant ni dejaba
  rastro** (2026-08-24). `POST/DELETE /users/{id}/sucursales` aceptaba
  cualquier `sucursal_id`: quien administraba las cuentas de su empresa podía
  colgar un usuario a la sucursal de **otra empresa del grupo** y darle acceso
  a datos ajenos, sin que quedara escrito. Ahora las dos operaciones exigen
  que la sucursal sea de la empresa de quien administra —el superusuario sigue
  operando sobre todo el grupo, igual que en el alta de sucursales— y las dos
  quedan en `audit_log`. Se audita también el quite porque es la otra mitad de
  "quién podía ver este local y desde cuándo".

## [0.7.2] - 2026-08-23

### Added

- **Los puntos de venta se dan de alta desde la app** (ADR-059). La caja de
  una sucursal —lo que carga las series SUNAT con las que el local emite—
  solo existía en el seeder: en staging el PDV bloqueaba con "La sucursal no
  tiene puntos de venta" y el mensaje pedía configurar una caja sin decir
  dónde, porque no había dónde. Ahora hay pantalla en **Organización →
  Puntos de venta**, entre Sucursales y Almacenes, con `POST` y
  `PATCH /api/v1/sales/puntos-venta`.
- El alta la firma `organizacion.gestionar` y no un permiso de `sales`:
  asignar una serie SUNAT es identidad fiscal de la empresa, del mismo orden
  que fundar el local, no configurar el salón. El listado acepta cualquiera
  de los dos permisos — el cajero necesita leerlo para abrir el PDV y el
  administrador que da de alta las cajas puede no tener ninguno de venta.
- `GET /api/v1/sales/puntos-venta` ya no exige `sucursal_id`: sin él devuelve
  las cajas de la empresa. Antes, un administrador sin sucursal asignada no
  podía listarlas.
- Se validan las reglas que el seeder daba por buenas porque las tipeaba a
  mano: la **serie no se repite dentro de la empresa** (RN-CPP-007, el
  correlativo es único por empresa y serie), las cuatro series de una caja
  son distintas entre sí (RN-CPP-009), web y kiosko cobran por adelantado
  (RN-POS-005), y un punto de venta web no lleva equipo asociado. La
  unicidad de serie vive en el caso de uso y no en el esquema: `punto_venta`
  no tiene `empresa_id` y el candado que de verdad impide emitir un duplicado
  ya existe en `comprobante`.
- Corregir una serie no reescribe lo ya emitido: cada comprobante guarda la
  suya al emitirse. Lo que no se permite es mudar una caja de sucursal.
- `PuntoVentaOut` expone `serie_nc_boleta`, `serie_nc_factura` y
  `hardware_id`, que existían y no se veían. Sin las primeras no se podía
  saber si una caja puede acreditar lo que emitió.

## [0.7.1] - 2026-08-23

### Fixed

- **Cortar una versión ya no rompe el CI.** `openapi.json` lleva la versión
  adentro (`info.version`) y `cortar_version.py` no lo regeneraba, así que el
  archivo commiteado seguía diciendo la anterior y el job `backend` fallaba
  con un diff de una línea. Pasó en el corte de 0.7.0.

  No se veía venir en local: `settings.app_version` sale de la metadata del
  **paquete instalado**, que en un entorno editable dice la versión con la que
  se instaló hasta que alguien reinstala. En el CI la instalación es limpia,
  así que ahí sí cambia — la misma rama pasaba en local y fallaba en CI.

  Dos arreglos, uno por cada mitad del problema:

  - `cortar_version.py` **regenera el contrato** después de sellar la versión,
    forzándola por `APP_VERSION` en vez de confiar en la metadata: lo que vale
    es la versión que se acaba de sellar, no la que quedó instalada.
  - `test_el_archivo_commiteado_esta_al_dia` deja de comparar `info.version`
    —no es un endpoint, y su desfase es un artefacto del entorno— y aparece
    `test_la_version_del_contrato_es_la_del_proyecto`, que la lee de
    `pyproject.toml` y por eso dice lo mismo en los dos lados.

- **La imagen lleva `scripts/odoo`.** El README del cargador manda correrlo
  dentro del contenedor —`docker compose exec api python -m
  scripts.odoo.cargar_catalogo`— y el `Dockerfile` copiaba solo `src`,
  `alembic` y los archivos de proyecto. El comando documentado fallaba con
  `No module named 'scripts'`, y no hay forma de enterarse sin desplegar:
  pasó al cargar el catálogo en staging.

  Entra `scripts/odoo` y nada más de `scripts/`: `cortar_version.py` y
  `empaquetar_demo.py` son herramientas de desarrollo, y `desplegar.sh` y
  `backup-staging.sh` corren en el host.

  Con guardarraíl: `test_la_imagen_lleva_lo_que_se_corre_dentro_del_contenedor`
  falla si el README vuelve a mandar algo que la imagen no tiene.

## [0.7.0] - 2026-08-23

### Added

- **El catálogo pasa al modelo de Odoo: atributos, variantes y recetas
  condicionadas** (ADR-055, ADR-056, migración `e2b7c40d91af`).

  Hasta ahora cada combinación vendible era una fila de producto con su
  propia receta. Con el catálogo real de Charlie's eso no se sostiene: una
  `Pizza MitadxMitad Familiar` de 19 sabores por mitad son **361 productos y
  361 recetas**, y cambiar los gramos de jamón obliga a abrir 361 fichas.

  - **Seis tablas nuevas** en `sales` — `atributo`, `atributo_valor`,
    `producto_atributo_linea`, `producto_atributo_valor`,
    `producto_variante_valor`, `producto_exclusion` —, las cuatro primeras
    calcadas de `product.attribute*` de Odoo 18.
  - **Los tres modos de `create_variant`**: `siempre` (materializa todas las
    combinaciones), `dinamica` (al venderse la primera vez) y `nunca` (no
    genera filas; el valor solo cambia lo que se consume). Elegir bien es lo
    que hace la diferencia entre 361 filas y ninguna.
  - **`receta_item.aplica_valores`**: una línea de receta puede aplicar solo
    a ciertas combinaciones. La regla es la de Odoo —agrupar por atributo y
    exigir al menos un valor de cada grupo—, así que las 26 líneas del
    archivo de Charlie's entran como 26 líneas.
  - **`receta_item.unidad_medida_id`**: una línea puede expresarse en otra
    UdM de la misma categoría que el artículo (30 ml de aceite sobre un
    artículo que se lleva en litros) y se convierte por `ratio` al descontar
    y al costear.
  - **`receta.es_kit`**, `ref_externa` en artículo, receta, producto y
    atributo (idempotencia al reimportar desde Odoo), `categoria.padre_id`
    (categorías jerárquicas) y `producto_comercial.lienzo_pos`.
  - **Una sola cuenta** de merma y conversión (`consumo_de_linea`) para el
    descuento de stock y el costeo, que antes estaban escritas distinto.

  **La migración es solo aditiva**: ninguna columna existente cambia de tipo
  ni de nulabilidad. La imagen 0.6.0 corre contra este esquema sin enterarse,
  así que volver atrás es desplegar 0.6.0 y no hace falta downgrade.

  Nada del PDV, compras, contabilidad ni almacén cambia de comportamiento
  mientras no se carguen atributos: las 1537 pruebas de 0.6.0 pasan sin
  editar una línea.

- **Entorno de staging** (2026-08-23): droplet en DigitalOcean, dominio y
  TLS automático (Caddy). Nuevo `docker-compose.staging.yml`, `Caddyfile`,
  `.env.staging.example`, `scripts/desplegar.sh` y `docs/engineering/staging.md`
  con la bitácora del servidor (sin secretos).
- **`release.yml` publica también la imagen del frontend** — hasta ahora
  solo empaquetaba el backend en GHCR; sin la imagen web, staging (y
  cualquier despliegue futuro) no tenía pantallas.

- **El recetario se edita en grilla** (`/catalogo/recetas/matriz`, ADR-057).

  Insumos en las filas, recetas en las columnas, gramajes en las celdas.
  Corregir el queso de las tres presentaciones de ocho pizzas eran
  veinticuatro fichas abiertas de a una.

  - **Se pega un rectángulo desde Excel.** La identidad de una celda es
    `(receta, insumo, condición)` y no un id de línea, que es lo que hace
    posible pegar algo que no trae ids: el servidor resuelve solo si es alta,
    edición o borrado. También se copia, en el mismo formato.
  - **Vaciar la celda borra la línea**: en una grilla es la forma natural de
    decir "este insumo no va acá".
  - **Se guarda por lote y solo lo que cambió.** Cada celda va en su propio
    `SAVEPOINT`: pegar cuarenta y perderlas todas por una mal escrita es el
    modo de falla que hace que nadie vuelva a pegar nada.
  - La celda muestra lo tecleado (`450/3`), no el resultado; el número lo
    calcula el servidor (RN-COM-024) y la vista previa va debajo.

- **El lienzo dibuja atributos y carga el árbol de una vez** (ADR-058).

  - `GET /sales/productos/{id}/arbol` reemplaza **una petición por variante**:
    con tres tamaños y ocho sabores eran 27 idas a la red para dibujar un
    árbol.
  - El atributo se dibuja como el grupo y el valor como la opción: el gesto es
    el mismo y el lienzo no gana nada con una segunda forma de mostrarlo.
  - **Lo excluido se apaga, no se oculta** (RN-COM-038), y elegir un valor
    suelta los que quedan excluidos por él, para no mostrar un plato que la
    venta va a rechazar.
  - **El producto y los tamaños guardan dónde quedaron** (`lienzo_pos`). Es lo
    que ADR-035 §5 había dejado fuera con un argumento que valía mientras el
    árbol lo dictaba una topología fija.

- **API de atributos**: crear, agregar valores, ofrecerlos en un producto,
  fijar el precio extra, retirar un valor —que lo **desactiva**, no lo borra,
  porque hay ventas que lo nombran— y declarar exclusiones.

- `recetas.editar_item` acepta `unidad_medida_id` y redondea con los decimales
  de **la unidad de la línea**: quien teclea gramos espera que 24.4 sea 24, no
  tres decimales de un kilo.

- **El catálogo de Odoo se convierte y se carga** (`scripts/odoo/`).

  Dos comandos: `convertir_catalogo` lee los cuatro exports de Odoo 18
  (`product.template`, `product.attribute` y dos de `mrp.bom`) y escribe seis
  libros numerados en el orden en que hay que subirlos, más un `INFORME.md`;
  `cargar_catalogo --simular` los recorre resolviendo cada referencia y
  deshace todo al final, para poder decir "esto entra limpio" antes de tocar
  staging.

  Sobre el catálogo real de Charlie's: 243 artículos, 217 recetas con 523
  líneas, 28 categorías en árbol, 6 atributos con 72 valores, 214 productos
  comerciales y 65 precios. Simulación en cero problemas.

  **No inventa datos de negocio**: los 28 gramajes que Odoo trae en cero
  quedan aparte para que alguien los llene. Sí corrige, y lo escribe todo en
  el informe: 17 artículos cuya unidad no era la que sus recetas consumen,
  4 nombres duplicados, 2 categorías cuya hoja chocaba, 28 vendibles sin
  receta (RN-PRD-001), líneas repetidas del mismo insumo, y los cuatro
  atributos de mitad que venían marcados para materializar 289 variantes por
  tamaño.

- **Una línea de receta acepta unidad propia y condición** en
  `recetas.agregar_item` (`unidad_medida_id`, `aplica_valores`, `orden`). El
  mismo insumo puede repetirse **si cada línea aplica a otra combinación** —
  que es lo que hace posible la pizza mitad-y-mitad—; lo que sigue rechazado
  es la misma condición dos veces. Una unidad de otra categoría de UdM se
  rechaza con un mensaje que lo dice (RN-UDM-001).

- **Las categorías cuelgan unas de otras** (`crear_categoria(padre_id=...)`),
  con tope de profundidad: la base no puede impedir un ciclo en una tabla que
  se apunta a sí misma, y recorrer la cadena sin límite cuelga el request.

- **Las dos mitades de una mitad-y-mitad tienen que ser distintas**
  (RN-COM-038, enmienda de ADR-056).

  Media hawaiana y media hawaiana no es una mitad-y-mitad: es una hawaiana
  entera, que ya se vende como su propio producto con su receta y su precio.
  `producto_exclusion` —creada en ADR-055 y hasta ahora sin usar— declara el
  par imposible, y `POST /sales/ventas` lo rechaza con 409. Se valida al
  confirmar la venta y no solo en el PDV: el kiosko y la central de pedidos
  entran por el mismo endpoint.

  La exclusión se guarda **una vez** y vale en los dos sentidos: el par es
  simétrico y guardar el espejo sería la misma verdad dos veces.

- **Las líneas condicionadas a las dos mitades se parten en una por mitad.**

  Con la regla de arriba, una condición que pide el mismo sabor en las dos
  mitades no se cumple nunca, y una que pide un conjunto en las dos deja de
  descontar en cuanto una mitad se sale. Las 52 líneas del archivo de
  Charlie's resultaron ser **todas simétricas** —el mismo conjunto de sabores
  en las dos mitades—, que es lo que dice cuál era la intención: cada mitad
  aporta lo suyo.

  `scripts/odoo/convertir_catalogo.py` las parte, con la mitad del gramaje y
  escrito como operación (`(0.025)/2`) para que la planilla muestre de dónde
  salió el número (RN-COM-024). Se comporta igual que Odoo cuando Odoo
  acertaba y correctamente cuando no.

  **`A + B` y `B + A` consumen lo mismo por construcción**: con cada línea
  condicionada a una sola mitad, el total no depende de en qué mitad se
  eligió cada sabor. No hace falta canonicalizar nada al guardar.

- Las unidades de medida de la carga pasan a **4 decimales**, el máximo que
  admite `receta_item.cantidad`. Con 3, media línea de 0.025 kg redondea a
  0.013 y la pizza entera lleva un gramo de más que nadie pidió.

- **Paquete de demo portable** (2026-08-09). `python scripts/empaquetar_demo.py`
  arma `ZIP_<versión>/provecho-demo-<versión>.zip` con el ERP entero —imágenes
  incluidas— para que alguien lo pruebe en su PC con doble clic en un `.bat`,
  sin internet, sin servidor y sin escribir un comando. Existe porque poner el
  sistema frente a quien lo va a usar no puede depender de que esa persona
  sepa levantar un compose y correr tres seeders: el servicio `init` migra y
  siembra en cada arranque (los seeders ya eran idempotentes) y el compose de
  demo no tiene `build:` porque en esa PC no hay código fuente.
  `docker-compose.demo.yml` **no sirve para publicar nada**: sus secretos
  están versionados a propósito.
- **Imagen de producción del frontend** (`frontend/Dockerfile`, etapa
  `runtime`, con `output: "standalone"`). La única imagen que existía corría
  `npm run dev`: ~1.5 GB y compilando cada pantalla la primera vez que alguien
  la abría, que quien prueba lee como que el sistema es lento. La etapa `dev`
  se conserva y `docker-compose.yml` la pide con `target: dev`.
- **`COOKIE_SECURE`** en el frontend. La cookie de sesión seguía a `NODE_ENV`,
  así que en un build de producción servido por http —la demo abierta desde la
  tablet del local, `http://192.168.x.x:3000`— el navegador la descartaba y el
  login fallaba **en silencio**, devolviendo al formulario sin error. Sin la
  variable el comportamiento no cambia.
- **Dos coherencias más en `tests/test_repo_coherencia.py`**: que el Node de la
  imagen del frontend sea el que el CI usa para `next build` (mismo riesgo que
  ya se vigilaba con Python), y que las imágenes que nombra el compose de la
  demo sean exactamente las que el empaquetador exporta — si no, el ZIP sale
  incompleto y el tester solo ve una pantalla que no carga.

### Añadido

- El seeder crea `cajero1` con rol `cajero` (PIN `123456`, todas las sucursales),
  además de `admin`. Probar el flujo de caja ya no exige crear el usuario a mano.

### Removed

- **Las 34 "Mitad X" sueltas no entran en la carga.** En Odoo, "Mitad Acecina
  familiar" es un producto con su propia receta y convive con "Pizza
  MitadxMitad Familiar", que es un Kit cuyas líneas ya dicen qué lleva cada
  mitad. Son dos formas de decir lo mismo, y desde que las líneas del Kit se
  parten por mitad la segunda basta: mantener 34 recetas paralelas son 34
  lugares donde el mismo gramaje se puede desincronizar.

  El filtro es "en la categoría del Kit **y sin receta de Kit**": los dos Kits
  viven en esa misma categoría y son justamente los que se quedan.

  Verificado antes de sacarlas: ninguna receta las consume, y los 15 insumos
  que usaban los usa también el Kit, así que ningún artículo queda huérfano.

### Fixed

- **`/health`, `/health/ready` y `/health/backups` rechazaban `HEAD` con 405**
  (encontrado 2026-08-23 al dar de alta el monitor externo de staging en
  UptimeRobot, plan gratis, que sondea con `HEAD` y no permite cambiar a
  `GET`). Causa: la versión instalada de FastAPI dejó de agregar `HEAD`
  automático a las rutas `GET`. Los tres endpoints ahora registran `HEAD`
  explícito, fuera del contrato OpenAPI (es implícito en HTTP, no hace
  falta documentarlo aparte).

- **La versión declarada llevaba tres releases congelada en `0.1.0`**
  (2026-08-09). `scripts/cortar_version.py` cortaba el `CHANGELOG.md` y
  borraba los fragmentos, pero nunca tocaba `pyproject.toml` ni
  `frontend/package.json`: con el repo en `v0.4.0`, los dos seguían diciendo
  `0.1.0` y la versión real vivía solo en el tag de git. Lo destapó el paquete
  de demo, que nombra el ZIP con lo que declara el proyecto y salió etiquetado
  con una versión de hacía un mes. Ahora el script escribe la versión en los
  dos archivos al cortar, y `tests/test_repo_coherencia.py` falla si vuelven a
  separarse entre sí.

## [0.6.0] - 2026-08-23

### Added

### Added

- **El PDV trae el nombre del cliente de RENIEC o SUNAT, y el largo decide a
  cuál.** El botón «Buscar DNI / RUC» aparece en los dos puntos donde caja
  identifica a alguien que todavía no está registrado: al crear el cliente y al
  pedir el documento del comprobante. Un número de 8 dígitos va a RENIEC y trae
  nombre y fecha de nacimiento; uno de 11 va a SUNAT y trae razón social y
  domicilio fiscal — el mismo largo que ya decidía boleta o factura
  (RN-CPP-003). Antes el cajero escribía la razón social de oído y SUNAT
  rechazaba la que no coincidía.
- El campo de documento del alta en caja acepta ahora las dos cosas (era solo
  DNI): con 11 dígitos el cliente nace jurídico, que es lo que el servidor ya
  hacía y la pantalla no dejaba pedir.
- **RRHH → Contratación también trae el nombre de RENIEC.** La ficha del
  trabajador nacía con el nombre que el candidato escribió de sí mismo en el
  formulario público, y es el nombre con el que se firma el contrato y se
  declara a SUNAT. Ahora el diálogo de contratar muestra nombres y apellidos
  editables con «Buscar por DNI» al lado, y el servidor aplica RENIEC aunque
  nadie lo apriete (RN-PTS-004, mismo criterio que el alta de cliente y de
  proveedor).

Prellena, no decide: todo lo traído queda editable, y sin `FACTILIZA_TOKEN` —o
con el proveedor caído— el aviso manda a completar a mano y la venta o la
contratación siguen (ADR-005, ADR-041). El botón solo se le ofrece a quien
tiene `consulta.documento`: cada consulta gasta cuota de un proveedor pago.

### Fixed

- **La consulta de documento usaba el token equivocado.** Emisión y consulta
  son dos productos de Factiliza con **dos credenciales distintas**, y el ERP
  mandaba el de emisión a los dos hosts: contra `api.factiliza.com` eso es un
  401 aunque el token esté vigente, así que el botón «Buscar» nunca podía
  funcionar. Nueva variable `FACTILIZA_CONSULTA_DOCUMENTO_TOKEN`; sin ella se
  cae al de emisión, como antes.
- **Un token rechazado ya no se reporta como «respuesta ilegible».** El 401
  llega con el cuerpo vacío y caía en el parseo de JSON, que mandaba a buscar
  un error de formato donde lo que hay que revisar es la credencial.

- **El reparto propio se cotiza por distancia real** (2026-08-22, ADR-054,
  migración `d41f6a2c98b7`). Con las direcciones ya ancladas en el mapa
  (ADR-053), `POST /sales/ventas/cotizar-delivery` devuelve kilómetros de
  manejo, cuánto sale llevarlo (`base + precio × km`) y si conviene derivarlo.
  El PDV lo muestra en el diálogo de tipo de orden, antes de aceptar el pedido.
- **El cálculo NO sale del navegador.** Define cuánta plata paga el cliente, y
  un número que viaja por el navegador es un número que se puede editar. Lo
  mide la Routes API desde el servidor, con una **segunda clave restringida por
  IP** (`GOOGLE_MAPS_SERVER_KEY`) — son dos claves porque Google no admite
  restringir la misma por referente HTTP y por IP a la vez. De ahí sale un
  invariante verificable: si aparece una llamada a `routes.googleapis.com` en
  la pestaña de red del navegador, está mal hecho.
- **Google caído no impide vender.** Se cae a distancia en línea recta
  (haversine × 1,3) marcada `aproximada`, que el PDV muestra como "aprox.".
  Cobrar de menos por un kilómetro es preferible a no poder tomar el pedido, y
  es además lo único que funciona en el hub offline de una sucursal (ADR-009).
  El `1,3` es una perilla de calibración, no una constante: se ajusta
  comparando cotizaciones aproximadas contra las reales.
- **Pasado el radio, o en distrito vetado, se sugiere DAZ DAZ.** Es un aviso al
  cajero y no una integración: quien decide es la persona, y si acepta se marca
  el campo que **ya existía**, `venta.repartidor_externo_plataforma`
  (`rappi|ubereats|pedidosya|dazdaz`). Cero tablas nuevas. La zona restringida
  se evalúa **antes** de medir: no depende de la distancia, y preguntarle a
  Google costaría una llamada por una respuesta que ya se sabe.
- **Las zonas vetadas son una lista de distritos, no polígonos.**
  `DELIVERY_DISTRITOS_RESTRINGIDOS` se compara sin tildes ni mayúsculas contra
  el distrito que ya viene con la dirección. PostGIS resolvería zonas de verdad
  y traería una extensión, un tipo de columna y una pantalla para dibujar
  polígonos: es mucha máquina para una lista de cuatro nombres (queda en la
  deuda del módulo).
- **Lo cotizado se congela en la venta.** `venta.distancia_entrega_km` y
  `venta.costo_entrega` se guardan al crear la orden y no se recalculan: la
  tarifa cambia y el pedido de ayer no puede cambiar de precio — el mismo
  criterio por el que la guía de remisión congela sus direcciones. El replay
  del hub **no vuelve a cotizar**: esa venta ya se cobró con un precio.
- **La cotización tiene cuota**, por usuario y por IP, reusando el mismo
  mecanismo que la consulta de DNI/RUC (ADR-041). Cada llamada gasta una
  medición de un proveedor pago y un bucle mal escrito en el PDV se come el
  plan del mes. Se suma un `@lru_cache` sobre la medición, con las coordenadas
  redondeadas a ~1 m: cada pedido se cotiza dos veces —la que ve el cajero y la
  que congela la orden— y así paga una sola llamada. Va sobre la medición y no
  sobre la cotización completa para que un fallo de Google **no** quede
  cacheado.
- **Arranca apagado**: `DELIVERY_TARIFA_BASE`, `DELIVERY_PRECIO_POR_KM` y
  `DELIVERY_DISTANCIA_MAXIMA_KM` valen `0` de fábrica y el delivery se sigue
  cobrando como antes hasta que el negocio defina la tarifa.
- Costo aceptado: **el reparto se calcula, se guarda y se muestra, pero todavía
  no suma al total de la venta** ni aparece en el comprobante. Cobrarlo de
  verdad exige una línea de venta sobre un producto de servicio "Delivery", con
  su IGV y su cuenta contable — radio de impacto mucho mayor que el resto de
  este cambio. Queda declarado en la deuda del módulo `sales`.

- **Toda dirección del ERP se elige en un mapa** (2026-08-22, ADR-053,
  migración `c3d8b1f47a95`). Una dirección era `String(255)` en seis lugares y
  nada más: nadie validaba que existiera, nadie podía navegar hacia ella y el
  repartidor recibía una cadena que podía decir "por el mercado, casa azul".
  Ahora `UbicacionMixin` le suma `place_id`, latitud/longitud (6 decimales,
  ~11 cm), plus code y distrito a `sucursal`, `almacen`, `empresa`, `persona`,
  `proveedor` y `venta`. El campo único
  (`components/direccion/campo-direccion.tsx`) autocompleta con Places, muestra
  el punto en un mapa y deja arrastrar el pin para corregir la puerta cuando
  Google la deja a media cuadra.
- **La dirección escrita a mano sigue valiendo, y ese es el caso que se
  prueba.** En Tarapoto hay calles que Google no conoce, en el hub offline de
  una sucursal no hay internet y la clave se puede quedar sin cuota un martes a
  las ocho. Sin `GOOGLE_MAPS_BROWSER_KEY` el campo es el `<input>` de siempre y
  el ERP se comporta **exactamente** como antes de este cambio — lo verifica
  `frontend/uso/direccion.spec.ts`, que corre **sin** clave a propósito. Mismo
  criterio que ADR-005 y ADR-041: la integración prellena, no decide.
- **Editar el texto a mano suelta el pin**, en el servidor
  (`shared/ubicacion.py`) y de paso en la pantalla. Corregir "Jr. Lima 200" por
  "Jr. Lima 400" sin volver a elegir en el mapa dejaría las coordenadas de la
  puerta vieja: el texto diría una calle y el reparto iría a otra, cobrando la
  distancia equivocada. Ante la duda se pierde el pin —que se vuelve a poner en
  dos clicks— y no la verdad. No alcanzaba con la convención de PATCH del ERP
  (`None` = no tocar): justamente por esa convención, un formulario que corrige
  el texto sin ancla nueva no puede pedir el borrado.
- **La dirección de delivery del PDV por fin se guarda.** Se tecleaba en caja y
  se perdía: vivía solo en el borrador del navegador y `venta` no tenía columna
  que la recibiera (`referencia_atencion` es "para quién es el pedido", 50
  caracteres, no adónde va). Ahora viaja a `venta.direccion_entrega`, sube por
  el contrato de sync del hub offline y se imprime en la comanda, que es el
  papel que sale con el repartidor.
- **Anonimizar una persona también le borra el punto en el mapa** (Ley 29733,
  ADR-011). Las coordenadas de la casa de alguien son tan personales como su
  dirección escrita, o más: un punto no admite la ambigüedad de un "por el
  mercado". Sin esto la anonimización dejaba la puerta exacta en la base.
- **La CSP suma hosts de terceros por primera vez.** El mapa lo dibuja el
  navegador con una clave restringida por dominio, porque los tokens de sesión
  de Places —lo que hace que una búsqueda se cobre como una y no como ocho— los
  maneja el elemento oficial de Google y no tienen versión server-side. Se
  aceptó abrir `connect-src`, `img-src`, `font-src`, `style-src`, `script-src`
  y `worker-src` a la lista de Google **recortada a lo que este ERP usa**: sin
  Street View y **sin `'unsafe-eval'`**, que Google recomienda por las dudas.
  Queda pendiente verificarlo en el navegador con clave puesta (deuda
  transversal).
- **La clave del navegador baja por contexto y no es `NEXT_PUBLIC_*`.** La lee
  el proceso de Next y el layout la pasa una vez, así que se cambia reiniciando
  el contenedor en vez de reconstruyendo la imagen — la misma razón por la que
  se eliminó `NEXT_PUBLIC_API_URL`. Paso a paso de la consola de Google Cloud
  en `docs/engineering/integraciones-google.md`.

- **Exportar es la plantilla con los datos adentro** (2026-08-20, ADR-052).
  Hasta ahora lo único que bajaba era una plantilla **vacía** de recetas: servía
  para la primera carga y para nada más — corregir el rendimiento de treinta
  recetas ya cargadas exigía abrir treinta fichas. Ahora las tres entidades
  tienen `…/exportar` en el mismo formato que `…/plantilla`: lo que baja se
  edita en Excel y se vuelve a subir sin traducir nada. Exportar pide permiso de
  **lectura**, no de escritura: son los mismos datos del listado, empaquetados.
- **El catálogo de artículos se carga de golpe** (RN-INV-025):
  `GET /inventory/articulos/plantilla`, `/exportar`, `POST /importar/validar`
  (multipart) e `/importar`. Dos hojas —`Artículos` y `SKUs`— con la misma
  revisión en dos fases que ADR-046 fijó para recetas. Desbloquea de paso la
  peor arista del importador de recetas: cuando el archivo nombraba un insumo
  que no existía, la única salida era irse a `/inventario/articulos` y crearlo a
  mano, uno por uno.
- **El padrón de clientes se carga de golpe** (RN-PTS-007):
  `GET /sales/clientes/plantilla`, `/exportar`, `POST /importar/validar` e
  `/importar`, con permiso propio **`sales.gestionar_clientes`**. Reescribir el
  padrón del grupo desde una planilla no es el mismo acto que registrar a
  alguien en el mostrador, que es lo que hace el cajero con `sales.crear`.
- **La carga de clientes no consulta a SUNAT ni a RENIEC.** `crear_cliente`
  pregunta por el nombre cuando se registra de a uno; trescientas filas serían
  trescientas llamadas externas secuenciales dentro de un solo request, contra
  una cuota (ver `fixed-consulta-documento-visible-y-con-cuota.md`). Se agregó
  `consultar_documento=False` y la planilla manda sobre el nombre; cuando el
  cliente se edita de a uno, SUNAT vuelve a mandar.
- **La E/S de `.xlsx` vive una sola vez, en `src/shared/planilla.py`**: abrir,
  mapear la cabecera, descartar filas vacías, el tope de filas, y convertir una
  celda a texto, número, booleano, fecha o UUID. Lo que **no** se construyó es
  un motor genérico con descriptores de columnas: qué hojas tiene cada libro y
  qué cuenta como "ya existe" son tres significados distintos, y un DSL que
  exprese los tres se lee peor que los tres archivos planos que evita. La regla
  de módulos ya lo hacía imposible de todos modos —`sales` no puede importar de
  `inventory`— y `shared` es el único domicilio legal.
- **Se lee por nombre de cabecera, no por posición de columna.** El parser de
  ADR-046 leía la columna 0, así que agregar `ID` a la izquierda habría roto en
  silencio cualquier archivo ya llenado. Ahora agregar o reordenar columnas no
  rompe nada, y una columna que falta da un error que **la nombra**.
- **La fase de validación pasa a tener `response_model`.** Devolvía un dict
  crudo, así que `openapi.json` la documentaba como `{}` y los tipos del
  frontend no los verificaba nadie — el mismo agujero para las tres entidades.
- Costo aceptado: los **SKU solo se crean**, no se editan (no existe
  `editar_sku`); uno con el código ya usado se informa y no se toca. Y el
  código interno de un artículo sigue siendo de **4 caracteres únicos en todo
  el grupo**: el importador lo exige y valida su largo por fila en vez de
  autogenerarlo, porque un código inventado termina tecleado en una orden de
  compra. Ambas quedan registradas en la deuda del módulo.

- **Las consultas RUC/DNI se prueban también contra Factiliza de verdad**
  (2026-08-22, `tests/test_factiliza_red.py`). Los dobles de `httpx` prueban
  que el cliente manda el token correcto; no prueban que **ese** token sirva.
  La corrida real confirmó las dos mitades: la consulta funciona con
  `FACTILIZA_CONSULTA_DOCUMENTO_TOKEN`, y el token de emisión **no** consulta
  documentos — o sea que tenerlos separados no era una precaución teórica.
- **El suite normal sigue sin salir a internet.** El archivo está marcado
  `red` y `addopts` lleva `-m "not red"`, así que `pytest` a secas —lo que
  corre el CI— no lo toca. Se dispara a mano con `pytest -m red` desde la raíz
  del repo. Sin token, queda `skipped`, no rojo. La alternativa —hacer que el
  suite de siempre pegue a la API— habría atado el CI a que RENIEC y SUNAT
  estén arriba y quemado cuota paga en cada push.
- **Solo consultas, nunca emisión.** Un `POST /invoice/send` real genera un
  comprobante ante SUNAT: eso no lo dispara una prueba.
- Costo aceptado: **no se prueba por red el camino "documento no encontrado"**.
  Dar con un DNI que de verdad no exista obliga a consultar documentos de
  desconocidos hasta que alguno falle — el primer intento devolvió a una
  persona real con nombre y domicilio. Ese caso se queda con dobles, que es
  donde siempre estuvo bien cubierto.

### Changed

- **Una receta que ya existe se actualiza en vez de omitirse** (2026-08-20,
  ADR-052, RN-COM-031). Desde ADR-046 el nombre repetido se informaba y la fila
  no entraba, y la deuda quedó abierta a propósito: actualizar exigía decidir
  qué pasa con los ingredientes que el archivo no menciona, y eso es decisión de
  negocio, no de código. La decisión: **se conservan**, y la revisión deja
  pedir que se quiten **receta por receta**, mostrando antes cuántas líneas se
  pierden. El defecto no borra porque el modo de falla es asimétrico — subir la
  hoja equivocada no puede vaciar una receta sin que nadie vea el número.
- **La identidad de una fila es la columna `ID`, no el nombre.** Sin ella,
  renombrar y duplicar son indistinguibles: el nombre es justamente lo que
  alguien quiere cambiar. La regla que gobierna a las tres entidades es que *la
  clave de actualización tiene que ser un campo que la persona no está
  editando* — de ahí que artículos acepten además su **código interno** y
  clientes su **número de documento**, y que recetas solo acepten `ID`.
- Un `ID` repetido dentro del mismo archivo marca **las dos filas**, no la
  segunda: copiar-pegar una fila entera es el accidente esperable, y silenciarlo
  escribiría dos veces sobre el mismo registro.
- Una fila con `ID` que no resuelve **no se degrada a alta**. Se informa y se
  omite con motivo: un id mal pegado convertido en registro nuevo es un
  duplicado que nadie sale a buscar.
- La respuesta de importar pasa de `{creadas, omitidas}` a
  `{creadas, actualizadas, omitidas}` en las tres entidades.
- **La cantidad se exporta como la expresión tecleada, no como el resultado.**
  Una línea escrita `450/3` vuelve a bajar `450/3`, no `150`: el dominio guarda
  las dos y exportar solo el número perdería justo lo que RN-COM-024 existe para
  conservar.

### Fixed

- **El insumo que falta se crea desde el diálogo de importación** (2026-08-20,
  ADR-046 → ADR-052). Era parte de lo pedido en ADR-046 y nunca se entregó: la
  pantalla dejaba **elegir** uno existente u omitir la línea, y crear uno nuevo
  obligaba a irse a `/inventario/articulos`, crearlo a mano y volver a subir el
  archivo entero. Ahora el `<select>` viene con un botón «Crear» que abre un
  formulario en línea —código, unidad y tipo, con el nombre prellenado con el
  que trajo el archivo— y resuelve esa línea en todas las recetas que la
  nombran.
- **Cuatro lugares afirmaban que eso ya funcionaba.** El docstring de
  `importar-recetas.tsx`, el de `importacion_recetas.py`, la hoja de
  instrucciones de la plantilla y **RN-COM-031** decían "se elige cuál es, se
  crea, o se omite". `catalogoApi.crearArticulo` existía desde ADR-046 con un
  comentario que la describía como "alta rápida desde el diálogo de
  importación" y su único llamador era `contrato.test.ts`: código muerto con un
  comentario que describía una función inexistente. Los cuatro textos ahora
  describen lo que el código hace.
- Esto **no revierte** la alternativa que ADR-046 descartó: lo descartado era
  que el *importador* creara solo los insumos que faltan, porque un "Queso
  mozarela" mal tecleado se volvería un artículo duplicado que después hay que
  fusionar a mano. Que lo cree una persona, viendo el nombre que trajo el
  archivo, es lo contrario de autocrear.
- Mismo patrón para las **categorías** desconocidas al importar artículos:
  elegir, crear, o dejar el artículo sin categoría. Una **unidad de medida**
  desconocida no se crea desde acá a propósito —define cómo se cuenta el stock,
  y necesita categoría, ratio y decimales—: se informa para que se cree en su
  pantalla.

- **`.env.example` volvió a documentar toda la configuración** (2026-08-22).
  Se había quedado 22 variables atrás de `src/config/settings.py`: faltaban
  `ZONA_HORARIA` —de la que sale "qué día es hoy" para el ERP, y sin ella un
  cierre de las 20:00 hora Perú cae al día siguiente porque Docker corre en
  UTC—, `HSTS_MAX_AGE_SEGUNDOS`, los tres límites de la consulta de DNI/RUC
  (`CONSULTA_DOCUMENTO_*`, ADR-041) y **los seis umbrales de negocio**
  (`PURCHASES_UMBRAL_APROBACION_OC`, `ACCOUNTING_UMBRAL_APROBACION_PAGO`,
  `INVENTORY_MARGEN_AJUSTE_PCT`, `PRODUCTION_COSTO_HORA_MANO_OBRA`,
  `RRHH_RMV_VIGENTE`, `RRHH_PLAZO_CONSERVACION_POSTULANTE_MESES`). Estos
  últimos son los que deciden si una OC o un pago pasan solos o piden
  aprobación: existían en el código como valor semilla y no había ni un
  renglón que le dijera al negocio que se podían mover. También se agregaron
  `PROVECHO_IMAGE` y `PROVECHO_WEB_IMAGE`, que `docker-compose.prod.yml`
  exige para desplegar.
- **La deriva ahora la ve el CI, no el día del incidente.** Tres pruebas en
  `tests/test_settings.py`: que todo campo de `Settings` esté documentado en
  `.env.example` o en `.env.hub.example`, que copiar `.env.example` tal cual
  —el primer paso del README— produzca una configuración que **arranca**, y
  que el ejemplo no lleve credenciales de verdad. La última no es paranoia
  barata: `.env.example` sí se commitea, y un JWT copiado del `.env` real
  queda en el historial de git para siempre; rotarlo después es un trámite
  con el proveedor, no un `git revert`.
- **`NUBEFACT_URL` y `NUBEFACT_TOKEN` salieron del ejemplo.** Factiliza lo
  reemplazó el 2026-07-26 y ningún módulo las lee; seguían ahí invitando a
  configurar un proveedor descartado.
- **`GOOGLE_API_KEY` pasó a llamarse `GOOGLE_MAPS_BROWSER_KEY`**, que es lo
  que de verdad es: una clave de navegador restringida por referrer que
  consume el frontend. Ningún código la lee todavía, así que el cambio de
  nombre no rompe nada — y evita que alguien pegue ahí una clave de servidor
  creyendo que el backend la usa.
- Se decidió **no** documentar `APP_NAME`, `APP_VERSION` ni `JWT_ALGORITHM`:
  nadie los ajusta por entorno y ofrecerlos en el ejemplo solo invita a
  romper cosas. Quedan en una lista explícita dentro de la prueba, no como
  olvido.

- **La consulta RUC/DNI tiene su propio token** (2026-08-22, ADR-005).
  Emisión y consulta son dos productos que Factiliza contrata y cobra por
  separado, y entrega una credencial para cada uno — pero el cliente mandaba
  `FACTILIZA_TOKEN` a los dos hosts. Con dos tokens distintos el buscador de
  DNI/RUC del mostrador recibía 401 de `api.factiliza.com` y moría con un 502
  genérico: el síntoma no nombra la causa, y el token de emisión seguía
  funcionando, así que la facturación se veía sana. Ahora
  `FACTILIZA_CONSULTA_DOCUMENTO_TOKEN` alimenta `consultar_dni`/`consultar_ruc`
  y `FACTILIZA_TOKEN` solo la emisión.
- **Vacío se reusa el de emisión**, así que quien tenga un plan con una sola
  credencial no configura nada nuevo. La cascada completa —argumento
  explícito, luego configuración, luego el de emisión— vive en
  `FactilizaClient._resolver_token_consulta`, no repartida por los métodos.
- **Se prueba el cruce en las dos direcciones.** Que la consulta use el suyo
  es la mitad fácil; la otra es que la emisión **nunca** use el de consulta,
  porque un comprobante firmado con la credencial equivocada lo rechaza SUNAT
  y eso sí llega a la caja. Los tests espían la cabecera `Authorization` de
  `httpx`, que es donde el error se vería.
- El token nuevo entra a `CLAVES_SENSIBLES` de `logging_config`, que redacta
  por nombre exacto: sin esa línea, la credencial recién agregada viajaba en
  claro a los logs y a GlitchTip.

- **El paquete decía 0.1.0 con el proyecto en 0.5.0** (2026-08-22). No era
  `settings.app_version` desactualizado: `pyproject.toml` llevaba clavado en
  `0.1.0` desde el 2026-07-04, cuatro releases atrás. `cortar_version.py`
  juntaba los fragmentos en `CHANGELOG.md` y borraba `changelog.d/`, y ahí
  terminaba; la versión se teclea tres veces al cortar un release —argumento
  del script, mensaje de commit y tag— y no aterrizaba en ningún archivo salvo
  el CHANGELOG. Nadie la olvidó una vez: **no había mecanismo**.
- **Costó donde más duele para diagnosticar.** De `pyproject.toml` salen el
  `release` con el que GlitchTip agrupa los errores y la `version` que publica
  `/docs`. Cada error reportado desde julio quedó etiquetado `0.1.0`, así que
  "esto apareció en la 0.4.0" —la mitad del valor de tener reporte de
  errores— no se podía responder. El tag de la imagen sí era correcto (sale
  del tag de git), lo que hacía el desfase más difícil de notar: por fuera
  todo se veía bien versionado.
- **Ahora hay una sola fuente de verdad.** `pyproject.toml` la declara,
  `settings.app_version` la lee de la metadata del paquete instalado en vez de
  repetirla como literal, y `cortar_version.py` la sube al cortar cada
  release. Un literal duplicado era la condición para que esto pasara.
- **`tests/test_version.py` falla si se vuelven a separar**: compara
  `pyproject.toml` con la última sección con número del CHANGELOG. Verificado
  contra la deriva real — con `0.1.0` la prueba se pone roja.
- En desarrollo la versión se refresca al reinstalar (`pip install -e
  ".[dev]"`): la metadata se congela al instalar. La imagen instala desde cero
  en cada build, así que ahí no aplica.

## [0.5.0] - 2026-08-20

### Added

- **Dos agentes ya pueden correr Playwright a la vez** (2026-08-15). El
  puerto web estaba fijo en `3100` dentro del código —`E2E_PUERTO_API` existía,
  su par no— así que la segunda suite que arrancaba chocaba con la primera o,
  peor, reusaba su servidor y corría contra código de otro worktree **en
  verde**. Ahora hay `E2E_PUERTO_WEB` y un esquema de slots (`810N` / `310N` /
  `provecho_slotN`) en `docs/engineering/trabajo-en-paralelo.md`.
- **El intérprete de Python se resuelve solo** (2026-08-15). Los scripts de
  la suite usaban `process.env.PYTHON ?? "python"`, y en un worktree no hay
  `.venv` —vive una sola vez en la raíz del repo principal—: el `python` del
  PATH no tiene instalado el paquete `src` y la corrida moría con
  `ModuleNotFoundError` tres pasos antes de la prueba que alguien quería
  correr. `frontend/e2e/interprete.mjs` busca el `.venv` del worktree, después
  el del repo principal (vía `git rev-parse --git-common-dir`) y recién
  entonces cae a `python`. `PYTHON` sigue mandando sobre todo.
- **Suite de uso separada de la de e2e** (2026-08-15, ADR-047).
  `npm run test:uso` corre `frontend/uso/` con captura en cada hito, traza
  siempre y sin reintentos, y su job de CI **no es requerido**: el techo de
  tres casos de `e2e` sigue vigente porque bloquea todo merge, y un recorrido
  lento no puede frenar un arreglo de caja. El arranque de los dos servidores
  quedó en `frontend/playwright.comun.ts`, que las dos configs comparten en
  vez de copiarse. Esta entrega deja **una sola spec de humo**: prueba el
  arnés, no una pantalla.
- **El seeder de e2e siembra lo que las ramas iban a sembrar de a una**
  (2026-08-15). `src/seeders/e2e.py` agrega `Menú E2E` —producto con
  variantes, grupo de opciones obligatorio y extras, el modelo de nodos
  completo—, cuatro insumos con stock real en el almacén central, un
  proveedor y una orden de compra en borrador. Sigue siendo idempotente y
  prohibido en producción. `Pizza E2E` no se tocó a propósito: es plana
  porque las pruebas del lienzo dependen de que tenga un único insumo.
- **Conteos de pruebas al día en la estrategia** (2026-08-15). Decía 895
  casos de backend, 183 de frontend y 7 de e2e; los reales son **1379**
  (1041 funciones `test_*` en 76 archivos, la diferencia son `parametrize`),
  **258** y **13**. Un conteo escrito a mano envejece sin avisar, y estos
  llevaban nueve días vencidos.

- **Una prueba que recorre el ERP en teléfono, tablet y PC**
  (`frontend/uso/responsive.spec.ts`). No compara píxeles contra una imagen de
  referencia —eso se rompe con cada cambio de copy— sino que afirma las dos
  cosas que sí son bugs: que ningún control quede dibujado fuera de un
  contenedor que lo recorta (una opción que existe y no se puede tocar) y que
  todo diálogo modal quede centrado. Recorre el home, las ocho pantallas de
  inventario, el KDS con una estación de preparación y otra de despacho, y el
  PDV con caja abierta y un pedido en cola, abriendo además cada diálogo que
  la pantalla sepa abrir. Encontró los cinco fallos de esta entrega y ninguno
  era visible en el ancho de escritorio, que es el único en el que se
  desarrolla.

- **La cocina pasa a ser una cadena de estaciones** (2026-08-13, ADR-044,
  RN-CUP-013). El KDS ruteaba solo por categoría: la pizza aparecía a la vez
  en armado y en horno, cualquiera de los dos podía tacharla, y tacharla la
  dejaba lista sin haber pasado por el horno. Ahora cada estación tiene un
  **paso** (`kds_pantalla.orden`) y cada línea sabe en cuál va
  (`venta_item.etapa_kds`): marcarla en una estación intermedia la manda a la
  siguiente que atienda su categoría, y solo queda `listo` cuando ya no le
  queda ninguna. Una bebida se salta el horno sola, sin configurar
  excepciones. Todo lo ya configurado sigue igual — las dos columnas nacen
  en 0, y una cocina de una estación es una cadena de un eslabón.
- **Despacho deja de ser la pantalla de cocina con otro filtro**: era el
  mismo componente, así que ofrecía tachar ítems en vez de decir qué falta.
  Ahora es una tarjeta por **pedido** con cuántas líneas van, en qué
  estación está cada una y por quién se espera; desde ahí solo se entrega,
  porque marcar preparado es un acto de la estación que preparó
  (RN-CUP-003).
- **La cocina volvió a ver los pedidos de consumo de personal**: el
  `response_model` de la cola filtraba en silencio `tipo` y
  `consumo_motivo` pese a que el servidor los devolvía, así que el aviso que
  la pantalla tenía escrito no se mostraba nunca (RN-COM-025).
- **Los PIN del PDV se teclean en un pinpad, sin campo de formulario**
  (ADR-045, RN-POS-014). Los cuatro sitios que piden PIN —apertura y cierre
  de caja, consumo de personal y firma de supervisor— usaban un
  `<input type="password">`: el navegador ofrecía guardarlo, y con el PIN
  guardado en la caja el turno siguiente entra con la cuenta del anterior y
  toda la auditoría nombra a la persona equivocada (RN-AUD-005). Sin campo
  no hay nada que guardar. Fuera del PDV no cambia nada.
- **La pantalla del PDV se bloquea a los 5 minutos y NO cierra sesión**: la
  caja abierta y el pedido a medio armar siguen donde estaban, y se reabre
  con el PIN de quien tiene la sesión contra el nuevo
  `POST /auth/verificar-pin`. Cerrar sesión habría sido peor que no hacer
  nada: el turno habría dejado la pantalla tocada a propósito para no perder
  el pedido. Un intento fallido cuenta contra el mismo bloqueo de cuenta que
  el login, y no contra un contador propio que sería la vía cómoda para
  probar PINes.
- **El PDV con la caja cerrada decía "la carta está vacía: ningún producto
  tiene precio vigente para esta sucursal"**, que manda a revisar listas de
  precios por nada: la carta no se pide hasta abrir caja, así que vacía
  antes de eso no significa lo mismo. Ahora dice "Abre la caja para ver la
  carta".
- **El seeder no corría contra Postgres**: la descripción de
  `users.resetear_pin` medía 260 caracteres y `permiso.descripcion` es
  `VARCHAR(255)`. SQLite no valida el largo, así que la suite entera pasaba
  en verde y el fallo aparecía recién al sembrar una base real — abortando
  el seeder completo con un `StringDataRightTruncation` que no dice qué
  permiso fue. Se acortó a 248, y hay una prueba que compara cada
  descripción contra el largo declarado en el modelo para que la próxima
  falle donde tiene que fallar.
- **El sabor dejó de salir como un plato aparte en cocina** (ADR-044
  enmendado, RN-CUP-014). Una *Pizza Personal Peperoni* aparecía en la
  tarjeta del KDS como dos ítems —`1 Pizza Personal` y `1 Peperoni`— y en
  despacho contaba "2 de 2" por una sola pizza. El extra es fila propia de
  la venta (tiene receta, precio y rastro), pero `kds.py` no mencionaba
  `padre_venta_item_id` en ninguna parte, así que aplanaba. Ahora viaja
  anidado y se muestra tabulado bajo su plato, igual que las restas; la
  comanda impresa lo sangra en vez de imprimirlo como línea de primer nivel;
  el ruteo por estaciones mira la categoría **del plato**; y marcar el plato
  marca sus extras — sin eso, `pedido_entregable` (que suma todos los ítems)
  habría dejado el pedido sin poder entregarse nunca.
- **Un extra sin categoría colgaba el pedido para siempre**: como ítem
  suelto, ninguna estación filtrada por categoría lo atendía, así que se
  quedaba `pendiente` y el pedido no llegaba a entregable. Todos los extras
  del seeder de pizzas estaban en ese caso.
- **Anular un plato con extras reventaba contra Postgres**:
  `fk_venta_item_padre` es `NO ACTION` y el PDV manda solo el id del plato,
  así que borrarlo dejaba al sabor apuntándolo — `ForeignKeyViolation`.
  SQLite no valida FKs, por eso las pruebas pasaban en verde. Ahora la
  anulación se lleva los hijos y **repone también su insumo**, que antes
  quedaba descontado sin haberse preparado. El fixture de `test_pdv_slice`
  enciende `PRAGMA foreign_keys=ON` para que la próxima falle donde tiene
  que fallar.

- **Un reporte ya no es una línea de texto: lleva al lugar donde se actúa**
  (2026-08-09, ADR-036). `reporte_emitido` guardaba `referencia_tipo` +
  `referencia_id` desde ADR-033 y **nadie los renderizaba**; el detalle
  `GET /reports/emitidos/{id}` existía y el frontend **nunca lo llamaba**. Ahora
  hay ficha de reporte (`/reportes/emitidos/[id]`) con quién lo provocó, de
  dónde viene, la foto de datos, a quién le llegó y por qué, y un botón al
  registro. El botón se esconde si el usuario no tiene el permiso del módulo
  dueño: ser destinatario no da acceso al dato (RN-REP-002).
- **Ocho endpoints `GET` que no existían.** Detalle de artículo, SKU, lote,
  categoría y ajuste en `inventory`; cierre de caja y pago a proveedor en
  `accounting`. Los ajustes de inventario **no tenían ni siquiera un listado**:
  se creaban y se aprobaban por API, y el reporte urgente de «ajuste fuera de
  margen» apuntaba a una pantalla que no existía. Ahora se aprueban y se
  rechazan desde `/inventario/ajustes`.
- **`src/core/destinos.py`**: el mapa `referencia_tipo` → endpoint + permiso.
  Vive en `core` porque lo leen `modules/reports` y `core/reportes`, que no
  pueden verse entre sí. `tests/test_destinos.py` verifica que **toda ruta del
  mapa esté montada de verdad** en la app: un rename de endpoint rompe el
  enlace en CI y no en producción (RN-REP-010).
- **Cada fila del tablero de consulta enlaza a su registro.** `Columna` gana
  `enlace` y las cuatro `queries_publicas` de las listas de problemas
  (`pedidos_demorados`, `consumos_omitidos`, `disponible_negativo`,
  `salidas_sin_lote`) proyectan el id que no proyectaban. Solo esas cuatro: el
  total de un martes no es un registro al que se pueda ir.
- **La campana navega al reporte** además de marcarlo leído. Antes decía que
  algo pasó y había que salir a buscarlo a mano.

- **Las devoluciones se pueden usar** (2026-08-13, RN-INV-019/020). La API
  estaba completa —registrar, anular, detalle, listar— y la pantalla era una
  tabla de solo lectura: la única forma de registrar una devolución era
  llamar al endpoint a mano. Ahora hay formulario de registro, botón de
  anular y ficha por devolución con qué se devolvió, por qué, a dónde fue y
  quién la registró o anuló. El destino solo aparece para una devolución de
  cliente: a proveedor la mercadería se va y no hay nada que decidir.
- **Registrar y anular una devolución quedan en `audit_log`**: mueven stock
  real y hasta ahora solo dejaban el evento que avisa a compras o comercial,
  que responde otra pregunta. Anular es además el movimiento con el que se
  podría tapar un faltante, así que tiene que decir quién lo hizo.
- **`GET /inventory/skus`**: no existía listado de SKUs, así que ninguna
  pantalla podía ofrecer "qué se mueve". Va con el nombre del artículo,
  porque el código de un SKU no le dice nada a nadie.
- **El catálogo de recetas se filtra por tipo y categoría** (RN-COM-030). El
  tipo **se deriva** de si la receta produce un artículo (subreceta) o no
  (producto de venta): no se agregó columna, que sería un segundo lugar
  donde puede estar mal. Los filtros viajan en la URL, así que el listado se
  filtra en el servidor —donde están las recetas— y se comparte pegando el
  enlace.
- **El recetario se carga de golpe desde un `.xlsx`** (ADR-046, RN-COM-031).
  Se descarga una plantilla con ejemplos e instrucciones, se sube llena, y
  **antes de guardar nada** la pantalla dice qué entra y qué no: unidad
  desconocida, rendimiento inválido, receta repetida, o ingredientes que
  nombran una receta que la otra hoja no declara —el error de tipeo más
  común del formato—. Un insumo que el catálogo no reconoce no cancela la
  carga: se elige cuál es o se omite esa línea **a la vista**, y lo que se
  elige se aplica a todas las recetas que lo nombran. Una receta que no
  entra se informa y no arrastra a las demás (un `SAVEPOINT` por receta). La
  cantidad acepta aritmética tecleada (`450/3`) igual que en la pantalla,
  porque el importador reusa los mismos casos de uso.
- Se eligió `.xlsx` sobre CSV porque Excel en configuración regional peruana
  usa `;` y coma decimal: abrir y guardar un CSV convierte `0.5` en `0,5` y
  corrompe el archivo en silencio.

- **`statement_timeout`, y son dos** (2026-08-15). `connect_timeout: 5` cubría
  no poder conectar; un Postgres que **acepta la conexión y después se traba**
  —lock ajeno, plan malo, disco al límite— seguía clavando el request sin
  límite, porque `pool_pre_ping` hace un `SELECT 1` al sacar la conexión del
  pool y después no mira más. `src/core/database.py` abre ahora **dos engines**
  contra la misma base: el de operación (`SessionLocal`,
  `DB_STATEMENT_TIMEOUT_SEGUNDOS=15`) es el default de todo el ERP, y el de
  reportes (`SessionReportes`, `DB_STATEMENT_TIMEOUT_REPORTES_SEGUNDOS=120`) lo
  consumen `src/core/reportes/` y el módulo `reports` vía la dependencia
  `get_db_reportes`. Un número único obligaba a elegir entre cancelar reportes
  que estaban trabajando bien o dejar la caja esperando; en el mostrador, un
  error se maneja mejor que una pantalla que no vuelve. Costo aceptado: un
  segundo pool de conexiones — que de paso impide que una consulta pesada de
  reportes se coma las conexiones de la caja. `0` desactiva el límite, y fuera
  de Postgres el parámetro no se pasa (el `e2e` corre sobre SQLite, que no sabe
  cancelar por tiempo). Un test de arquitectura falla si un endpoint queda del
  lado equivocado.
- **Ningún barrido puede abrir la base de producción desde un test**
  (2026-08-15). `inventory/application/tasks.py`, `sales/application/tasks.py`
  y `rrhh/purga.py` llamaban `SessionLocal()` directo: el test que los
  ejercitaba pagaba una conexión real —5 s de `connect_timeout`— o, con la base
  de desarrollo levantada, corría el barrido **contra ella**. Ahora exponen
  `session_factory` como los listeners y entran en el guardián autouse de
  `tests/conftest.py`, que ya cubría a los cinco módulos de listeners.

- **Un reporte se puede elevar, y queda el rastro de quién intentó qué**
  (2026-08-09, ADR-036). `reporte_escalamiento` salda RN-CTP-004 y RN-PRD-014,
  declaradas como deuda desde ADR-033: cadena supervisor → comercial →
  gerencia, un escalón por vez, con historial append-only por nivel. Siete
  endpoints nuevos bajo `/api/v1/reports` y dos permisos —`reports.escalar` y
  `reports.escalamiento_resolver`— separados por lo mismo que solicitar y
  aprobar un ajuste: quien eleva no es quien cierra.
- **Vive en `src/modules/reports/`, no en `shared`**, contra lo que decía
  `data-model.md` §6. Esa línea se escribió cuatro meses antes de que el módulo
  existiera; hoy la entidad tiene un solo escritor y un solo lector, y su
  lógica necesita `Area`, `AreaMiembro` y los resolutores de destinatarios, que
  `shared` tiene prohibido importar.
- **Ancla al `reporte_emitido`, no a la venta.** Los `venta_id` / `carrito_id` /
  `orden_produccion_id` del diseño original son lo que `referencia_tipo` +
  `referencia_id` ya guardan, para los nueve tipos y no para tres — y `carrito`
  ni siquiera existe como tabla. Anclar a la venta perdería la foto de datos,
  el nivel, el actor y la doble puerta de RN-REP-002.
- **A quién elevar, sin jerarquía organizacional**: el ERP no tiene
  `supervisor_id` ni nivel de rol, así que el escalón se resuelve con el
  encargado de turno (nivel supervisor) y las áreas Comercial y Gerencia. El
  seeder pone el rol `supervisor` dentro del área Comercial, así que **elevar
  puede caer en la misma persona**: es la organización de hoy, y el endpoint
  devuelve los destinatarios para que quien eleva lo vea en vez de suponer que
  llegó a otro.

- **Modo oscuro y preferencias de accesibilidad, guardadas en el perfil**
  (ADR-037). Cierra el catálogo que `docs/product/ui-ux.md` dejó especificado
  en julio con hex exactos y nunca se implementó: paleta de alto contraste
  para daltonismo rojo-verde (Okabe-Ito, ~95% de los casos), escala de letra
  en cuatro niveles y modo oscuro. Las tres viven en `usuario`, no en el
  navegador, porque el documento es explícito y el motivo es operativo: en un
  local la misma tablet la usan tres turnos y la misma persona salta de la
  caja a la oficina; guardadas en el dispositivo hay que reconfigurarlas en
  cada máquina, que en la práctica significa no usarlas. Nuevo endpoint
  `PATCH /users/me/preferencias`, **sin permiso**: no hay privilegio que
  otorgar en elegir el tamaño de la propia letra, y pedir uno dejaría la
  accesibilidad fuera del alcance de quien más la necesita.
- Se resuelven **en el servidor**: el layout raíz escribe `class="dark"`,
  `data-escala` y `data-paleta` en `<html>`. No se usa `next-themes` —aunque
  ya estuviera instalado alimentando a `sonner`— porque guarda en
  `localStorage` y necesita un script inline antes del primer pintado, y la
  CSP de `middleware.ts` firma cada script con un nonce por request. Costo
  aceptado: no hay opción "seguir al sistema" (detectarla exige justo ese
  script) y cada cambio es un viaje al servidor.
- **Paleta y tema se combinan**, como pedía ui-ux.md: hay un bloque
  `.dark[data-paleta="alto-contraste"]` con la paleta Okabe-Ito aclarada —sus
  valores están medidos contra blanco y sobre `#101216` el azul cae a 3.6:1—.
  El orden importa: declarado antes del bloque oscuro, el tema apagaba la
  paleta accesible.
- **`Insignia` ata el ícono al tono**, que es lo que hace cumplible la regla
  de que ningún estado se comunique solo por color. Antes «activa» e
  «inactiva» eran la misma píldora gris para quien no distingue rojo de verde.
  De paso, un pago pendiente deja de mostrarse en rojo: no es un error, es
  plata que todavía se puede detener, y se leía igual que uno rechazado.
- **`Ctrl+K` abre cualquier pantalla del ERP** (cierra F2.29, que estaba «sin
  decidir»). Llegar a Plan de cuentas eran tres clics; ahora son cinco teclas.
  Sin dependencias nuevas: `@base-ui/react` Autocomplete + Dialog. `cmdk`
  traería un motor de coincidencia difusa para ~50 entradas estáticas y
  arrastra el árbol de Radix que ADR-013 descartó. Cada resultado es un enlace
  de verdad, así que Enter, clic central y «abrir en pestaña nueva» funcionan
  sin programarlos, y los destinos llegan filtrados por permiso.
- **Esqueletos de carga por módulo** (cierra F2.31, que decía «el dashboard
  hoy no tiene ni loading skeleton»). Sin `loading.tsx` Next espera a que el
  `page.tsx` resuelva y recién ahí pinta: el clic en el sidebar no acusa
  recibo y se lee como que la aplicación se colgó.
- **Ayuda contextual por campo de formulario** (`CampoFormulario`), pendiente
  escrito en ui-ux.md desde julio: quien carga un proveedor no tiene por qué
  saber que "condición de pago" se cuenta en días desde la recepción.

### Added

- **Requerimiento de la jornada** (`inventory`, ADR-051, RN-INV-023/024): el
  local abre `/inventario/solicitudes` y encuentra una lista ya armada con lo
  que está bajo su punto de reorden (`stock_minimo`), la edita, suma lo que
  necesite aunque no esté bajo mínimo —queda marcado como pedido del local,
  no como urgencia— y la envía para aprobación. Nuevo estado `borrador`
  (uno por almacén) en `solicitud_insumos` y columna `bajo_minimo_al_pedir`
  en `solicitud_item`, estampada al agregar cada ítem.
- **Toma de inventario con pantalla propia**: `/inventario/conteos` cubre lo
  que la API ya tenía desde ADR-019 y ningún formulario ofrecía — abrir,
  contar a ciegas, cerrar viendo los ajustes generados, anular con motivo.
  Suma `GET /inventory/conteos`, que faltaba.
- `GET /inventory/solicitudes`, `GET /inventory/conteos` y
  `GET /inventory/conteos/programa` filtran por `sucursal_id` y `marca_id`,
  resueltos por join a través del almacén.

- **Almacén abastecedor de respaldo** (2026-08-12, ADR-040, RN-INV-022,
  migración `a7c04e3b91d5`). Con un solo abastecedor, el día que ese almacén
  se da de baja la sucursal no puede pedir nada y recibe un "almacén
  abastecedor no encontrado" que no le dice a nadie qué hacer. Ahora
  `almacen` declara un respaldo y `crear_solicitud` cae a él **cuando el
  principal está dado de baja** — no cuando está sin stock, que tiene su
  propio camino. Un abastecedor pedido a mano nunca cae al respaldo:
  despachar desde donde no se pidió es lo que el que recibe no puede notar
  hasta contar la mercadería. La columna vive en `almacen` y no en
  `sucursal` (el que se abastece es el almacén, y una sucursal puede tener
  varios), pero se elige desde el formulario de Sucursal, que es donde se
  busca. Dar de baja un almacén ahora mira también a quien lo tenga de
  respaldo, y el respaldo viaja al hub: un corte de red es justo cuando no se
  puede ir a preguntar quién es el suplente.
- **Consulta de DNI y RUC desde la pantalla** (ADR-041). El cliente de
  Factiliza existía desde agosto, con pruebas, y **ninguna pantalla podía
  usarlo**: no había endpoint. `nombres_desde_dni` aplicaba el nombre de
  RENIEC al guardar (RN-PTS-004), así que quien tecleaba descubría recién
  después que el sistema había escrito otro. Ahora hay un botón "Buscar" en
  Personas (rellena nombres, apellidos y fecha de nacimiento) y en Proveedores
  (razón social, dirección y provincia), contra `GET /consulta/{dni,ruc}/{n}`
  en `core` — no tiene dueño de módulo: el mismo documento lo teclean
  personas, proveedores y caja. Prellena y no decide: todo queda editable, y
  si Factiliza no responde el alta sigue siendo posible tecleando. La
  respuesta **no** incluye el cuerpo crudo del proveedor, que trae más datos
  personales de los que la pantalla necesita (Ley 29733).
- **El proveedor guarda su domicilio fiscal** (`direccion`, `provincia`,
  `pais`), partido y no como un solo texto: `provincia` es lo que decide si
  el flete es local o interprovincial, y volver a partir una dirección
  concatenada es adivinar.
- **Reseteo de PIN con cambio obligatorio** (ADR-041). Un PIN olvidado no se
  recuperaba —está hasheado con Argon2id— y el frontend ni siquiera ofrecía
  cambiarlo: sus comentarios afirmaban que "lo cambia su dueño con su propia
  sesión", endpoint que no existía. Ahora `rrhh_admin` (permiso propio
  `users.resetear_pin`, aparte de `users.gestionar` en los dos sentidos)
  devuelve la cuenta al PIN por defecto, y pasan tres cosas juntas porque
  ninguna sirve sola: la cuenta **no puede hacer nada** salvo cambiarlo, se le
  revocan las sesiones abiertas, y se le limpia el lockout —quien olvidó su
  PIN normalmente lo agotó intentando—. La obligación la hace cumplir
  `get_current_user` leyendo la marca **de la base** y no de un claim, así que
  vale desde el request siguiente y no cuando venza el token; se verificó que
  ningún endpoint la esquiva. Suma `POST /users/me/pin`, que no lleva permiso
  —elegir la propia clave no es un privilegio que otorgar— pero exige el PIN
  actual.
- **`/users/me/pin` se declara antes que `/users/{usuario_id}/pin`**: FastAPI
  resuelve por orden de declaración y la ruta con parámetro capturaba `"me"`
  como si fuera un id, con lo que cambiar el PIN propio habría exigido
  `users.gestionar`.

- **Los reportes de la base de desarrollo no se podían usar para nada**
  (2026-08-10). Eran de pruebas sueltas: títulos sin entidad detrás, sin
  actor y sin destino, así que con ADR-036 el botón «ir al registro» llevaba
  a un 404 y la columna «Quién» decía «Sistema» en todas las filas. Nuevo
  `python -m src.seeders.reportes_demo`: borra lo viejo y arma diez
  situaciones con su fila real —un ajuste de −18 pendiente de aprobar, un
  lote vencido hace cuatro días, una caja con S/ 35.50 de faltante, un pago
  de S/ 4800 sobre el umbral— más tres cadenas de escalamiento (abierta,
  elevada a comercial, resuelta). Los hechos se insertan y **el reporte se
  emite por el camino real**: mismo listener, misma resolución de
  destinatarios, misma bandeja.
- **El reparto de la demo respeta el RBAC, no al revés.** Cada cadena la abre
  y la cierra alguien que de verdad puede: la doble puerta de RN-REP-002
  también aplica al escalamiento, y una demo donde el protagonista recibe un
  403 al abrir su propia cadena enseña lo contrario de lo que quiere enseñar.
- **`jefe_cocina` gana `reports.escalamiento_resolver`.** Sin él, una no
  conformidad de producción solo la podía cerrar alguien sin
  `production.leer` — o sea, nadie. RN-PRD-014 ya decía que «el jefe de
  cocina redacta el hallazgo y la acción tomada».
- **`production.no_conformidad_detectada` ahora también avisa al área
  Cocina.** Iba a Gerencia y Almacén: a todos menos a quien RN-PRD-014 pone
  a actuar.
- **La ficha de un reporte de escalamiento ya no ofrece botón de destino.**
  La cadena se ve más abajo en esa misma ficha, y su lectura se gatea contra
  el módulo del reporte de origen, no contra `reports.leer`: era el único
  enlace que podía prometer acceso y terminar en 403.

### Changed

- **El back office deja de vestirse de afiche y se viste de mesa de trabajo**
  (ADR-037). El brandboard de julio se aplicaba por igual a todo: crema de
  pared a pared y cada `h1`–`h4` en Anton itálica y VERSALES. Es la voz
  correcta cuando la marca le habla al cliente —PDV, KDS, carta— y la peor
  posible en una pantalla de trabajo: la itálica en versales es el ajuste
  menos escaneable que existe, y sobre crema las tarjetas blancas pierden
  contraste justo donde están los números. Ahora son **dos voces**: acero,
  Archivo condensada y tinta en el back office; crema, Anton y brasa en PDV,
  KDS y login. Los hex se movieron por contraste medido, no por gusto: el
  naranja `#F4511E` daba 3.4:1 sobre blanco con `text-primary` en 41 lugares
  y pasa a `#C6390F` (5.3:1); el lima `#AEEA00`, que en la práctica era el
  color de ~30 insignias de estado, era ilegible en texto y amarillento en
  insignia, y pasa a verde `#17864B`.
- **La tabla y el diálogo dejan de parecer HTML de 1998**, y con ellos 45
  pantallas que no se editaron. El buscador de `TablaDatos` (28 pantallas) era
  un `<input>` **sin una sola clase de estilo** y el estado del orden un
  `" ↑"` concatenado al texto — el "parece más HTML que elementos
  interactivos" de ADR-035, replicado 28 veces. Suma encabezado pegajoso,
  atajo `/`, filas fantasma mientras carga, vacío que distingue "no encontré"
  de "no hay", selector de tamaño de página, y `meta.numero` para alinear
  cifras a la derecha en monoespaciada tabular: una columna de importes con
  ancho proporcional obliga a leer dígito por dígito para comparar dos filas,
  y comparar dos filas es a lo que se viene a un ERP. `DialogoFormulario` (17
  pantallas) gana backdrop desenfocado, entrada con escala, y encabezado y pie
  fijos con el cuerpo scrolleable — un formulario de doce campos dejaba
  «Guardar» fuera de la pantalla. Las dos mantienen la firma de props
  compatible hacia atrás.
- **Los emoji de los módulos salen**; entran íconos de trazo (`lucide-react`,
  ya instalado). Cada sistema dibuja un emoji distinto —el 🍕 de una tablet
  Android no se parece al de Windows— y doce emoji de colores en la grilla del
  home compiten entre sí. El home además agrupa por área de negocio en vez de
  escupir catorce fichas iguales.
- **Un acento, no una paleta por área.** Se probó un color por área de negocio
  (`--area-*`) y se descartó: ADR-013 §8 ya había rechazado el color por
  módulo o por tarjeta, y cuatro tintes son el mismo arcoíris con menos pasos.
  Las áreas sobreviven como agrupación del home; ordenar no necesita pintar.

- **Un reporte decía qué pasó y no quién ni dónde exactamente** (2026-08-09,
  ADR-036). `reporte_emitido` gana `actor_id` y `almacen_id`, y el catálogo de
  emisiones declara `clave_actor`: qué campo del payload es el actor. Ocho
  eventos de `inventory`, `accounting` y `production` lo publican ahora
  (ampliación aditiva). `sales.pedido_demorado` queda **sin actor a
  propósito**: lo detecta un barrido de Celery, y poner ahí al mozo que tomó
  el pedido convertiría un aviso de proceso en una acusación contra quien no
  provocó la demora. Un test parametrizado congela la lista de emisiones sin
  actor, para que la próxima se declare en vez de perderse en silencio.
- **Los reportes anteriores a este cambio dicen «Sistema»**: las dos columnas
  son nullable y **no hay backfill**. Un reporte de agosto no puede decir quién
  lo provocó porque el dato nunca se guardó, e inventárselo sería peor que
  dejarlo vacío (RN-REP-009).
- **`inventory.ajuste_fuera_margen` publicaba menos de lo que `events.md`
  decía**: la doc prometía `sku_id, diferencia, margen` y el código mandaba
  solo `ajuste_id` y `almacen_id`, así que el reporte decía «ajuste fuera de
  margen» sin decir de qué ni de cuánto. Ahora viajan `sku_id`, `cantidad`,
  `motivo` y `aprobado_por`, y la fila de `events.md` dice la verdad.

- **El cajero abre y cierra su caja solo** (2026-08-15, ADR-049, RN-MDP-008,
  migración `c8b41f60d2a7`). `POST /accounting/cajas/apertura` y
  `.../cierre` dejan de exigir la elevación por PIN con
  `accounting.caja_relevar`: alcanza `accounting.caja_operar`, el permiso
  que el rol `cajero` ya tenía. El campo `autorizacion` desaparece de
  `AbrirCajaIn` y `CerrarCajaIn` (era requerido), y
  `AperturaCajaOut.relevo_encargado_id` pasa a nullable.
  El motivo es de operación, no de modelo: para empezar su turno el cajero
  necesitaba que un encargado caminara hasta la caja a poner su PIN, todos
  los días — y eso se pagaba **dejando la sesión del encargado abierta en la
  caja**, que es exactamente el escenario que hace imposible probar quién
  tenía el efectivo. Lo que prueba cuánto había en el cajón sigue siendo el
  conteo por denominación, no una firma.
- **La firma no se debilitó: se movió a donde la plata cambia de manos.** Al
  cerrar, el efectivo queda `en_caja` a nombre del cajero, y el encargado
  firma la recepción después, en `POST /cajas/custodias/{id}/entregar` —
  ahora el único punto del ciclo que pide `accounting.caja_relevar`. Antes
  la custodia nacía directamente en `en_supervisor`: el sistema declaraba
  entregado a las 23:00 lo que se entregaba a las 09:00 del día siguiente, y
  un faltante detectado en el medio le caía al encargado por una firma que
  el software le había puesto solo. El estado `en_caja` ya existía en el
  enum y en la tabla de transiciones desde el primer día — **no lo escribía
  nadie**, así que no hizo falta migrar datos.
  La segregación que importa sigue en pie sin ningún candado nuevo: el
  cajero no puede firmar que recibió su propia plata porque su rol no tiene
  `caja_relevar`.
- **De regalo, recontar un cierre vuelve a significar algo.** Un cierre se
  corrige mientras el efectivo siga en el local (RN-MDP-005); como ahora
  arranca `en_caja` en vez de saltar a `en_supervisor`, recontar *con la
  plata todavía en el cajón* pasó de ser un estado inalcanzable a ser el
  caso normal.
- **Costo aceptado**: `accounting.queries_publicas.encargado_de_turno` salía
  del `relevo_encargado_id` de la caja abierta y devuelve `None` para toda
  apertura nueva, así que `reports` cae en su respaldo por rol
  (`supervisor`/`admin` de la sucursal). Los avisos siguen llegando, a más
  gente y menos dirigidos. Saber quién está a cargo del local necesita una
  fuente propia —un turno de personal— y queda anotado como deuda junto con
  otros dos huecos de permisos que el recorrido de uso destapó: el encargado
  no puede abrir la pantalla donde firma la recepción, y el cajero no ve los
  terminales que RN-POS-010 le pide verificar al abrir.

### Fixed

- **El PDV pedía abrir una caja que ya estaba abierta** (2026-08-12). El
  cajero entraba, le aparecía el diálogo de apertura, y al aceptarlo el
  servidor lo rechazaba —correctamente— con "ya hay una caja abierta": un
  callejón sin salida donde no se puede ni vender ni entender por qué.
  El origen era un permiso mal elegido: `GET /accounting/cajas/abiertas`
  exigía `accounting.leer`, que es el permiso de **todo** el módulo contable y
  que el rol `cajero` no tiene ni le corresponde. Recibía 403 y el PDV lo
  trataba como "no hay caja". Ahora el endpoint acepta `sucursal_id` y en ese
  caso alcanza con `accounting.caja_operar` —quien opera una caja puede
  preguntar si su turno está abierto— con el alcance validado contra el tenant
  (ADR-004), no contra el parámetro. Sin `sucursal_id` sigue siendo la empresa
  entera y sigue exigiendo `accounting.leer`: quien opera una caja no tiene por
  qué ver el efectivo de los demás locales. La caja es del **punto de venta**,
  así que el turno que abrió un compañero vale para todos los del local.
- **Un fallo al consultar la caja ya no se dibuja como "no hay caja"**: el
  `.catch(() => setCaja(null))` del PDV era el mismo patrón que `useLista` ya
  había corregido en el resto de sus cargas. Ahora la pantalla dice qué pasó y
  no ofrece abrir una caja sobre la que no pudo preguntar.
- **El "volver" de las fichas subía de nivel en vez de volver** (ADR-039).
  Llegando a una receta desde la ficha de un producto, `← Recetas` llevaba al
  listado y no al producto. Cada ficha cableaba su propia salida —nueve en
  total— y todas contestaban "¿qué hay encima?" cuando la pregunta era "¿de
  dónde vengo?". Ahora hay un `<Rastro>` con dos controles: el rastro
  jerárquico (Inicio / Módulo / Sección / lo que se ve), derivado de la ruta
  contra los mismos registros que alimentan el sidebar y la paleta, y un `←`
  que usa el historial propio y cae al padre cuando no lo hay —una entrada por
  URL directa o una recarga—.

- **La búsqueda por DNI/RUC no estaba donde se necesitaba** (2026-08-15,
  ADR-041). El botón existía y se montaba en Personas y en Proveedores, pero
  no en **Ventas → Clientes**, que es la pantalla donde se corrige la razón
  social de un cliente jurídico — y cuyo propio texto de ayuda ya decía que
  "SUNAT manda sobre la razón social tecleada". Ahora está ahí, prellenando
  solo la razón social: `contacto` es el teléfono o el correo de quien
  coordina, y traerle el domicilio fiscal reemplazaría un dato real por otro.
  **No** se montó en el diálogo de documento de un cliente natural: ese
  formulario no tiene ningún campo que la consulta pueda llenar (el nombre
  vive en su `persona`, RN-GEN-007, y ahí el botón ya estaba).
- **El botón se le ofrecía a quien no puede usarlo** (2026-08-15). Ningún
  punto de montaje miraba `consulta.documento`: un `contador` o un
  `almacenero` lo veía, lo apretaba y se comía un 403 dibujado como aviso.
  El gate vive ahora **dentro** de `BuscarDocumento` —repetirlo en cada
  pantalla es cómo la siguiente se lo olvida— y `permisos` es una prop
  obligatoria, así que montarlo sin decir de quién es la sesión no compila.
  Sigue siendo UX: quien manda es `require_permission` en la API.
- **La consulta de DNI/RUC ya tiene cuota propia** (2026-08-15), deuda
  declarada con ADR-041. Cada llamada gasta crédito de un proveedor **pago**,
  así que lo que se cuida no es el abuso sino el gasto: un bucle mal escrito
  en una pantalla agota el plan del mes sin que nadie ataque nada. Se reusó
  `core/rate_limit.py` en vez de escribir otro limitador —fail-open incluido:
  un Redis caído no puede dejar a la caja sin identificar a un cliente—.
  **Por usuario además de por IP** (20 y 60 por minuto, configurables): en un
  local todas las cajas salen por la misma dirección, y un límite solo por IP
  deja al equipo entero sin consultar por culpa de uno. Se cuenta después del
  permiso, porque un 403 no le cuesta un centavo a nadie.

- **Los diecisiete diálogos del ERP se abrían pegados a la esquina superior
  izquierda, no centrados** (2026-08-18). Dos causas encimadas, y ninguna se
  ve leyendo el componente del diálogo. La primera: el preflight de Tailwind
  pone `margin: 0` en todos los elementos y con eso pisa el `margin: auto`
  con el que el navegador centra un `<dialog>` modal. La segunda: `.revelar`
  —la animación de entrada de cada pantalla— usaba
  `animation-fill-mode: both`, que deja la animación aplicada para siempre;
  el `transform` del último fotograma queda computado como
  `matrix(1, 0, 0, 1, 0, 0)`, que es la identidad pero **no es `none`**, y un
  `transform` no-`none` convierte al elemento en bloque contenedor de todo
  `position: fixed` que tenga debajo, incluido el top layer del diálogo. Se
  arregla con `dialog:modal { margin: auto; overflow: auto }` global y con
  `backwards` en lugar de `both` en las tres animaciones de entrada.
- **El PDV escondía el ticket entero por debajo de 60rem** (2026-08-18): el
  pedido, los totales, «Enviar» y «Cobrar» desaparecían con un `display: none`
  en toda tablet en vertical y en todo teléfono, sin nada que los reemplazara.
  Ahora la carta y el ticket comparten la celda y se alternan con el botón
  «Pedido»/«Carta» de la barra, que solo existe en ese ancho.
- **La barra del PDV recortaba «Cuentas» y «Cobrados» a 390 px**: no entraban
  en una línea junto al buscador y `.pdv` tiene `overflow: hidden`, así que
  las dos vistas quedaban dibujadas fuera de la pantalla sin scroll que las
  alcanzara. La barra ahora envuelve.
- **El conteo por denominaciones no entraba en el diálogo en un teléfono**: la
  grilla de dos columnas fijas se desbordaba llevándose «Abrir caja» con ella,
  y sin caja abierta no se vende. Pasa a una columna donde no entren dos.
- Las barras superiores del PDV y del KDS tenían la altura clavada en 56 px:
  el título envuelto a dos líneas se salía de la banda y se montaba sobre el
  contenido de abajo.
- **La pantalla de bloqueo del PDV se pintaba con el fondo blanco del
  navegador**: `.pdv-bloqueo` se monta como hermano de `<main class="pdv">`,
  donde los tokens `--pdv-*` no existen, y un `var()` sin respaldo invalida la
  declaración entera. Deuda declarada en ADR-050 y cerrada acá.

- **La plantilla de recetas se descargaba como un `.json` corrupto**
  (2026-08-15, ADR-048). El backend siempre armó un `.xlsx` de verdad; quien
  lo rompía era el proxy del navegador (`app/api/proxy/[...ruta]/route.ts`),
  que leía todo cuerpo con `text()` —un `.xlsx` es un ZIP y no sobrevive una
  decodificación UTF-8— y lo devolvía con `Content-Type: application/json`
  fijo, descartando el `Content-Disposition`. Sin nombre y con ese tipo, el
  navegador guardaba `plantilla.json`. Ahora el cuerpo viaja como stream y
  conservando el tipo y el nombre de archivo que manda la API.
- **La subida del recetario nunca llegó a funcionar desde la pantalla**
  (2026-08-15, ADR-048). El mismo proxy forzaba `Content-Type:
  application/json` en la ida, y en `multipart/form-data` ese header lleva un
  `boundary` que genera el navegador: pisarlo dejaba al servidor buscando una
  marca que el cuerpo no tenía. La fase 1 del importador (ADR-046) estaba
  rota desde que se escribió y nadie lo reportó porque nadie pudo pasar de la
  descarga. Ahora se reenvía el `Content-Type` entrante y el cuerpo sin
  decodificar.
- **Nada probaba el camino que recorre una persona.** Los tests del
  importador atacan a FastAPI con `TestClient` y el proxy queda fuera del
  recorrido, así que el endpoint podía estar perfecto y llegar roto al
  navegador. Se cierra con `frontend/lib/proxy.test.ts` (8 casos, sin
  levantar nada: binario byte por byte, `boundary` intacto, JSON intacto,
  error literal, 204 y 401) y con el recorrido
  `frontend/uso/importador-recetas.spec.ts` (ADR-047), que descarga la
  plantilla, verifica la firma `PK\x03\x04`, **la abre con openpyxl**, la
  llena, la sube, resuelve un insumo desconocido y la importa. Contra el
  proxy viejo falla con `Received: "plantilla.json"`.
- Costo aceptado: el cuerpo de subida se junta en memoria en vez de
  encadenarse como stream —`duplex: "half"` no está en el tipo estándar de
  `RequestInit`— y de la respuesta se copian solo `Content-Type` y
  `Content-Disposition`. Reenviar `content-encoding`/`content-length` de una
  respuesta que `fetch` ya descomprimió corrompe la descarga, y `set-cookie`
  de la API no tiene por qué cruzar al navegador.

- **Las claves foráneas se hacen cumplir en todo el suite** (2026-08-15). SQLite
  las trae **apagadas** y Postgres no las apaga nunca: el suite dejaba pasar en
  verde borrados e inserciones que la base real rechaza —así estuvo meses roto
  `anular_lineas` contra `fk_venta_item_padre`—. Un listener del evento
  `connect` de SQLAlchemy en `tests/conftest.py` enciende
  `PRAGMA foreign_keys=ON` en **cualquier** engine SQLite del proceso, en vez
  de fixture por fixture: son ~75 y una que se olvide reabre el agujero.
  Corolario para escribir tests: un `uuid.uuid4()` en una columna FK ya no
  pasa, hay que sembrar la fila. Destapó cinco violaciones, dos de ellas bugs
  de producción de verdad.
- **Una receta con insumos no se podía borrar** (2026-08-15). `eliminar_receta`
  borraba las líneas y después la cabecera, pero sin `relationship` entre
  `receta` y `receta_item` SQLAlchemy no sabe que una depende de la otra y
  emitía el `DELETE` del padre **primero**: Postgres lo rechazaba por
  `fk_receta_item_receta_id_receta` y el usuario veía un 500. Como toda receta
  real tiene insumos, la operación estaba rota entera. Se fuerza el flush entre
  los dos borrados; hacerlo cumplir en el esquema (`ON DELETE CASCADE`) queda
  como deuda junto con el caso gemelo de `venta_item`.
- **El reporte que no se podía ubicar era el único que no se emitía**
  (2026-08-15). `reports.emision` guardaba en `almacen_id`, `sucursal_id`,
  `empresa_id` y `actor_id` el id que venía en el payload **aunque esa fila ya
  no existiera** — un almacén dado de baja, un usuario desactivado entre el
  hecho y su emisión (el bus despacha post-commit, ADR-016). Las cuatro son FK:
  el `INSERT` moría y se perdía el reporte completo, justo el que había que
  investigar. Ahora la columna queda nula y el id sobrevive en `datos`, que es
  lo que se lee al investigar: se pierde el enlace, que es exactamente lo que
  dejó de existir.

- **No se podía vender una pizza** (2026-08-12, ADR-038). `GET /sales/carta`
  armaba los grupos de opciones leyendo el producto **padre**, pero los
  sabores cuelgan de la **variante**, que es el producto que se prepara
  (RN-COM-022/023). La carta devolvía `extras: []`, el PDV no dibujaba
  "Sabor", habilitaba Guardar sin elegir ninguno, y el servidor —que sí mira
  los grupos de la variante— rechazaba el pedido con
  `409 'Sabor' exige elegir 1, llegaron 0`. El cajero veía un error que la
  pantalla nunca le dejó evitar, y como sin venta confirmada no hay comanda,
  tampoco llegaba nada al KDS. Ahora cada variante viaja con su propio
  `extras[]` (aditivo, sin migración) y el PDV ofrece los de la presentación
  elegida — que son exactamente los que el servidor acepta. Cambiar de tamaño
  limpia lo ya elegido: los ids son de otra variante.
- **Los sabores del catálogo de demo se creaban sin precio de lista** y la
  carta descarta todo extra sin precio vigente, así que no habrían aparecido
  igual. Se les fija precio 0: el sabor no cobra aparte, pero "vale cero" y
  "no tiene precio" son cosas distintas, y la carta hace bien en no ofrecer
  la segunda.
- **El lienzo de nodos no se podía cablear** (ADR-035, tercera enmienda).
  `conectar()`/`desconectar()` estaban escritos, probados y enchufados, pero
  todos los `<Handle>` llevaban `isConnectable={false}`: react-flow no deja ni
  empezar el arrastre desde un puerto deshabilitado, así que era código
  inalcanzable. Se habilitan los puertos, las aristas se cortan **solo** donde
  el dominio admite desvincular, y `Supr` se suma al `Backspace` de fábrica.
- **Un nodo con acciones ya no se traga sus propios clicks**: `Tarjeta`
  deshabilitaba el `<button>` del nodo cuando no tenía `onToggle`, y un
  `<button disabled>` anula lo que contiene — con eso "receta" y "quitar"
  estaban muertos en el nodo de grupo.
- **El grupo se retira desde su nodo**: `BorrarGrupo` existía como componente
  y no estaba montado en ninguna pantalla, así que la única forma de borrar un
  grupo era el endpoint. Sigue **soltando** sus opciones, no borrándolas.
- **Una acción de estructura del lienzo refresca también la lista de recetas**
  (`router.refresh()`): un tamaño o una opción recién creados mostraban
  `receta` en el pie en vez del nombre de la suya hasta recargar a mano.

- **Una orden ya enviada a cocina admite líneas nuevas** (2026-08-12,
  ADR-043, RN-COM-029). El PDV respondía "Este pedido ya se envió, usa + para
  abrir uno nuevo", así que la mesa que pide una bebida diez minutos después
  terminaba con dos cuentas, que se cobran por separado y se entregan por
  separado. Ahora `POST /ventas/{id}/items` las suma a la misma orden, con el
  mismo permiso que crearla y sin firma de nadie: agregar es lo que el
  negocio quiere que pase, no saca nada del inventario y el rastro queda
  igual. El evento republicado lleva **el incremento** y no el acumulado, así
  que inventory descuenta solo lo nuevo y contabilidad no asienta la venta
  dos veces.
- **Quitar lo recién enviado dejó de necesitar al supervisor**: quitar una
  línea exigía su PIN **siempre**, incluso treinta segundos después de un
  error de tecleo. Un control que se ejecuta veinte veces por turno deja de
  ser un control — se termina dejando la sesión del encargado abierta en la
  caja, que es justo lo que RN-AUD-005 quiere evitar. Ahora hay ventana de
  **5 minutos**: dentro, lo corrige quien opera la caja; fuera, lo firma un
  supervisor como antes (RN-COM-020). La ventana de la orden entera se mide
  contra su **última** línea —una mesa larga sigue teniendo algo recién
  mandado— y un lote necesita firma si **alguna** de sus líneas salió de
  ella, porque si no bastaría con acompañar la vieja de una nueva. El PDV
  intenta sin firma y la pide recién cuando el servidor la exige.
- **Los pedidos vacíos ya no se apilan sin poder cerrarse**: cada toque del
  "+" abría otra pestaña, y ninguna se podía descartar, así que la columna
  derecha se llenaba de pedidos que no eran nada. Ahora el "+" reusa el
  borrador vacío que ya esté abierto —un pedido sin líneas y sin destino no
  es distinto de otro igual— y una pestaña sin líneas y sin enviar se
  descarta con su "×". Una con líneas o ya enviada no: eso es "Anular
  pedido", que repone inventario y queda auditado.

- **La pizza seguía sin poder elegir sabor** (2026-08-12, ADR-042). El arreglo
  anterior (ADR-038) servía para el catálogo del **seeder**, que cuelga el
  grupo de la variante, y dejaba roto el armado **a mano**: el lienzo cuelga
  "+ grupo" del nodo activo, y el nodo activo es el padre mientras el producto
  no tiene tamaños. El recorrido natural —crear "Pizza", armarle los sabores,
  y recién después agregar Personal/Mediana/Familiar— deja los sabores en el
  padre y las variantes vacías. Mientras el lugar donde quedó colgado el grupo
  importe, siempre va a haber una mitad de los casos rota, así que ahora **una
  variante ofrece lo suyo más lo del padre**, y la venta acepta exactamente lo
  que la carta ofreció. El vínculo propio gana sobre el heredado: si la
  Familiar declara su propio "extra queso", manda su tope. Sin migración: es
  una regla de lectura, y los dos catálogos que hay hoy funcionan sin tocar
  sus datos.
- **El cajero no podía anular un pedido ya enviado**: `sales.anular` es un
  permiso de supervisor, así que el botón del PDV devolvía 403 sin decir qué
  hacer y el pedido quedaba en cocina. El permiso sigue siendo de supervisor;
  lo que faltaba era el camino del cajero, que es el mismo que ya existía para
  quitar una línea enviada (RN-COM-020): la pide él y la firma un supervisor
  con su PIN en el mismo terminal. El PDV lo intenta sin firma primero — quien
  ya tiene el permiso no debería teclear su propio PIN para anular su pedido —
  y solo pide la firma si el servidor dice que no le alcanza. El endpoint
  entra con `sales.cobrar` **o** `sales.anular`: son roles disjuntos —el
  cajero cobra y no anula, el supervisor anula y no cobra— y exigir los dos
  habría dejado afuera a los dos.
- **Los pedidos enviados y sin cobrar no se veían**: existían como una nota al
  pie del mapa de mesas, y encima filtrando fuera los de mesa, así que un
  "para llevar" solo se encontraba entrando a Mesas y bajando, y uno de mesa
  había que reconocerlo por el color de una celda. Ahora es una pestaña propia
  ("Cuentas") con todo lo que falta cobrar —mesa, para llevar y delivery en la
  misma lista, con su total— porque esa es la pregunta de la caja y no es una
  pregunta sobre el salón. El mapa de mesas sigue siendo el mapa de mesas.

- **La raíz de cinco módulos daba 404** (2026-08-15). `catalogo`, `compras`,
  `inventario`, `organizacion` y `rrhh` tenían carpeta, `layout.tsx` y todas
  sus pantallas, pero ninguna ruta en la raíz: el ícono del home apunta a la
  primera pantalla (`/catalogo/productos`), así que nada del shell enlazaba
  `/catalogo` y el agujero no se veía. Sí lo teclea quien recorta la URL para
  subir un nivel, que es justo lo que uno hace cuando se perdió. Ahora cada
  raíz redirige a `modulo.href` leído de `lib/modulos.ts`: la primera pantalla
  de un módulo cambia, y dos lugares donde declararla son dos lugares donde
  puede quedar mal.
- **El ERP no tenía pantalla de 404**: cualquier dirección equivocada caía en
  la página por defecto de Next —fondo blanco, "404" en inglés y ninguna
  salida—. En una tablet detrás de la barra, una pantalla sin botón de vuelta
  se resuelve apagando y volviendo a entrar. `app/not-found.tsx` dice qué pasó
  en español y ofrece el inicio. No repite la ruta que falló: quien tecleó la
  dirección ya la vio, lo que le falta es la puerta.
- **Nada ataba la navegación al árbol de archivos**: `lib/navegacion.test.ts`
  cruza `MODULOS` con `SUBMENUS`, pero los dos pueden estar de acuerdo
  apuntando a una pantalla que no existe. Por eso la deuda "7 íconos del home
  llevan a 404" sobrevivió meses después de que esas pantallas se
  construyeran, sin que nadie pudiera decir si seguía siendo cierta.
  `lib/rutas.test.ts` resuelve los 14 íconos y los 25 ítems de submenú contra
  los `page.tsx` reales, y comprueba que ninguna raíz se redirija a sí misma.

### Security

- **El login se teclea en el pinpad, no en un campo de contraseña**
  (2026-08-15, ADR-050, enmienda a ADR-045). `frontend/app/login/page.tsx`
  pedía el PIN en un `<input type="password" autocomplete="current-password">`
  — el patrón exacto que ADR-045 había eliminado dos días antes dentro del
  PDV, en la pantalla que más veces se cruza y desde la misma tablet de la
  caja. El navegador ofrece guardarlo, y con el PIN guardado el turno
  siguiente entra con la cuenta del anterior: toda la auditoría de RN-AUD-005
  nombrando a la persona equivocada. Sacar el campo de los cuatro diálogos del
  PDV y dejarlo en la puerta no protegía nada — basta con entrar una vez.
  Ahora el usuario se teclea (es un identificador, no un secreto) y el PIN se
  toca en un teclado numérico **sin campo de formulario, ni oculto**: el valor
  vive en el estado de React y viaja en el `FormData` del envío. Al sexto
  dígito entra solo. Se descartó la lista de usuarios para elegir: enumerar al
  personal le regala la mitad de la credencial a cualquiera que pase frente a
  la caja.
- **El pinpad dejó de ser del PDV.** Se mudó de `app/pdv/pinpad.tsx` a
  `frontend/components/pinpad/` y su CSS de `pdv.css` a `globals.css`, con
  cada color pedido al token `--pdv-*` **con respaldo** en el del back office
  (`var(--pdv-rojo, var(--primary))`): dentro del PDV se ve exactamente igual
  que antes y fuera cae al sistema visual de ADR-037, modo oscuro incluido,
  sin duplicar el bloque. `app/pdv/pinpad.tsx` queda como re-export de una
  línea a propósito, para no chocar con la rama que trabaja sobre
  `dialogos.tsx`; el puente y `app/cambiar-pin/` quedan anotados como deuda.
- **El login dejó de tratar igual a las tres negativas del servidor.**
  `actions.ts` devolvía `e.message` sin mirar el status, así que "PIN
  equivocado" (401), "cuenta bloqueada quince minutos" (423) y "demasiados
  intentos desde esta IP" (429) llegaban con el mismo texto genérico — y las
  tres terminaban en lo mismo: probar de nuevo hasta bloquear la cuenta. Ahora
  cada una dice qué hacer y cuánto esperar (el 429 lee el `Retry-After`, para
  lo cual `ApiError` lo expone), y un PIN de menos de seis dígitos se corta
  **antes** de llamar a la API: con un pinpad, un "Ingresar" de más gastaría
  uno de los cinco intentos del lockout. Sin contador de intentos en el
  cliente — el estado real vive en el servidor.
- **El usuario tecleado ya no se borra al errar el PIN.** React 19 resetea los
  campos no controlados de un `<form action>` cuando la acción termina,
  también cuando devolvió error; volver a escribir el usuario en cada intento
  es justo la fricción que empuja a dejar la sesión de otro abierta. Mismo
  candado que el back office puso en sus diálogos el 2026-08-10.
- **Tres casos e2e nuevos** (13 → 16, `frontend/e2e/sesion.spec.ts`): que en
  el DOM del login no exista ningún `input` de tipo password ni con
  `autocomplete` de contraseña —se afirma el DOM y no un comportamiento,
  porque un `type="password"` agregado sin querer dejaría todo lo demás en
  verde—, con teclado físico y región viva verificados; que un PIN equivocado
  no borre el usuario; y que una cuenta bloqueada avise distinto que un PIN
  equivocado, agotando de verdad los cinco intentos sobre una cuenta de
  sacrificio del seeder (`bloqueo_e2e`). El 429 no se prueba: la suite sube el
  rate limit a propósito para poder entrar muchas veces desde la misma IP.

## [0.4.0] - 2026-08-10

### Added

- **Los registros maestros por fin se editan desde la pantalla** (2026-08-10).
  Hasta ahora el ERP sabía crear y listar, no corregir: un RUC mal tecleado, un
  cargo que cambió o un código de estante equivocado solo se arreglaban con
  `curl` o tocando la base. El diagnóstico no era el esperado — el backend ya
  tenía `PATCH` para casi todo; lo que faltaba era la pantalla.
  - **Botón "Editar" en la fila** de Proveedores, Artículos, Trabajadores,
    Cuentas de usuario, Plan de cuentas y Divisas. Cada diálogo dice también
    **qué no se puede cambiar y por qué**: la unidad de medida de un artículo
    (el stock y las recetas ya están expresados en ella, cambiarla no convierte
    nada, reinterpreta en silencio lo que ya existe), el `username` de una
    cuenta (firma cada línea del `audit_log`), el código y el tipo de una
    cuenta contable (los asientos registrados dependen de ellos), el tipo de un
    proveedor (dejaría sus órdenes de compra apuntando a algo que ya no es).
  - **Ocho pantallas nuevas**: Usuarios → Personas, Ventas → Clientes,
    Inventario → Categorías y Unidades de medida, y el módulo **Organización**
    completo (empresas, marcas, sucursales, almacenes). Ninguna existía: esos
    registros solo se administraban por API.
  - **Personas lleva bloqueo optimista** y es la única que lo necesita: la
    `version` viaja con el formulario y un 409 se muestra con instrucción de
    recargar. Sin eso, dos administradores editando la misma ficha se pisaban
    en silencio — sobre datos personales eso significa "el domicilio corregido
    volvió al viejo y nadie se enteró". Con esta pantalla el derecho de
    **rectificación** de la Ley 29733 deja de ejercerse por `curl`.
  - **De un cliente natural solo se completa el documento**: su nombre,
    teléfono y dirección viven en su `persona` (RN-GEN-007) y el diálogo
    enlaza allá. Ofrecer esos campos en la pantalla de clientes habría creado
    justo la segunda fuente que esa regla existe para evitar.
  - Tres huecos de API cerrados: `ProveedorUpdate` admite razón social y RUC,
    `ArticuloUpdate` admite `id_interno`, y `sales` gana
    `PATCH /clientes/{id}` más `GET /clientes/listado` paginado.
  - **Costo aceptado**: desde un `PATCH` sigue sin poderse *vaciar* un campo
    opcional (`null` significa "no tocar"). Solo `frecuencia_conteo` tiene su
    centinela; el resto se cambia por otro valor, no se borra.

- **Un formulario del ERP no se administraba solo** (2026-08-10). El shell del
  `<dialog>` estaba copiado y pegado en siete pantallas; con la edición encima
  habrían sido veinte copias del mismo bloque, y la que se olvidara de cerrar
  al `ok` iba a ser un bug sin relación aparente con las otras diecinueve. Vive
  en `components/formulario/dialogo-formulario.tsx` y lo usan tanto las altas
  como las correcciones.

- **Un rechazo del servidor ya no borra lo tecleado** (2026-08-10). React 19
  **resetea solo** el formulario cuando la acción va en el prop `action` de
  `<form>`, y lo hace también cuando la acción devolvió error. Encontrado
  verificando en el navegador: corregir un RUC y errarle al plazo de crédito
  dejaba el diálogo abierto con el RUC viejo de vuelta. Ahora la acción se
  despacha a mano dentro de una transición — sin reset automático y con
  `pendiente` funcionando igual. Es el mismo candado que el conteo de caja ya
  tenía probado en e2e: reteclear un formulario entero porque un campo estaba
  mal es la fricción que termina en un dato inventado.

### Changed

- **El lienzo de nodos deja de ser un visor y pasa a ser el lugar donde se
  arma la carta** (2026-08-09, ADR-035 segunda enmienda). Antes se podía
  recorrer y simular; ahora se edita.
  - **La receta se edita dentro del nodo.** Tocar un tamaño, un sabor o un
    extra abre su receta en el inspector: cambiar cantidades, quitar un
    insumo, agregar otro. La cantidad acepta aritmética ("1000/3") y **la
    evalúa el servidor**, no el navegador (RN-COM-024). Esto revierte la
    regla de editar recetas solo en Catálogo → Recetas: lo que ADR-023 §4
    había corregido era la *duplicación* del editor en dos pantallas que no
    se sabían relacionadas, y el lienzo no es una segunda pantalla — es el
    lugar de trabajo. Catálogo → Recetas sigue siendo el dueño de crear,
    duplicar, escalar y renombrar, con enlace desde cada nodo.
  - **Se conectan y desconectan nodos.** El grupo pasa a ser un nodo porque
    es el destino de la conexión, y los extras que el producto todavía no
    ofrece aparecen apagados en su propia columna para poder cablearlos:
    arrastrar de un grupo a uno de ellos lo cuelga **dentro** de ese grupo;
    del tamaño, lo deja suelto; cortar la arista lo desvincula sin borrar el
    extra. Cualquier otro par se rechaza con un mensaje que dice qué sí se
    puede — la topología tamaño → sabor → plato la dicta RN-PRD-004 y no se
    negocia con el mouse.
  - Una columna que se envuelve en subcolumnas ahora **reserva su ancho**:
    con 18 extras disponibles, la columna de restas se le montaba encima.
- **Carta de pizzas de demo armada con el modelo de nodos**
  (`python -m src.seeders.pizzas_demo`). El catálogo de demo anterior
  modelaba cada combinación como un producto plano —"Pizza pepperoni
  familiar", "Pizza hawaiana mediana"—, que es justo lo que el lienzo vino a
  reemplazar: seis sabores por tres tamaños serían dieciocho productos,
  dieciocho precios y dieciocho recetas a mano. Ahora es **una** Pizza con
  tres tamaños, un grupo Sabor obligatorio de seis opciones con receta
  propia por tamaño, cuatro extras y empaque por modalidad. `--limpiar`
  **desactiva** lo que no es pizza en vez de borrarlo: un producto vendido se
  descontinúa (misma regla que `eliminar_producto`) y el catálogo anterior no
  lo genera ningún seeder del repo, así que borrarlo sería destruir algo que
  nadie puede recrear.
- **El insumo de demo del e2e tiene costo** y **el servidor de e2e sube el
  rate limit de login**: la suite entra once veces desde la misma IP y el
  límite real son diez por minuto, así que las últimas pruebas fallaban con
  "no aparece el inicio", que no menciona el rate limit por ningún lado.

### Fixed

- **El seeder de e2e sembraba códigos que no caben en su columna**
  (2026-08-10). `articulo.id_interno` y `producto_comercial.id_interno` son
  `String(4)` y la siembra escribía `"E2E-H001"` y `"E2E-P001"`, de ocho.
  Entraban igual porque **SQLite no aplica el largo de un `VARCHAR`**; contra
  Postgres la siembra habría reventado. Salió a la luz al estrenar la edición
  de artículos: la pantalla no podía ni reenviar el código existente sin
  recibir un 422 de su propio valor. Ahora son `EH01` y `EP01`.

## [0.3.0] - 2026-08-09

### Added

- **La comida del personal ya se registra: precio cero, costo a gasto**
  (2026-08-09, ADR-034, RN-COM-025/026/027). El grupo alimenta a su gente en
  fines de semana, feriados y días de alta actividad, y eso no existía en
  ningún lado: el costo desaparecía dentro del costo de ventas.
  - Una orden de `tipo="consumo_personal"` se prepara y despacha como
    cualquier pedido —comanda con `** CONSUMO PERSONAL **`, distintivo en el
    KDS, entrega— pero **nace con todas sus líneas en cero**: no se consulta
    lista de precios y **tampoco se acepta el precio que mande el cliente**.
    No se cobra (409), no admite descuento (409) y no emite comprobante.
  - **Por qué no fue un descuento del 100% con motivo `colaborador`**, que ya
    existía y habría sido una línea: esa venta publica
    `sales.venta_confirmada`, que `accounting` asienta como ingreso y
    `marketing` atribuye a una campaña; además no se puede cerrar
    (`registrar_pago` exige `monto > 0` e igualdad exacta) y al cobrarse
    emitiría una boleta de S/ 0.00 a SUNAT. Por eso hay evento propio
    (`sales.consumo_personal_registrado`) y un estado terminal nuevo,
    `cerrada`, que pone la entrega: es el único cierre posible de algo que
    nunca pasa por caja.
  - **El costo sí llega**: sale del almacén con `tipo_movimiento` nuevo
    `consumo_interno` —separado de `consumo_venta` porque no tiene ingreso
    detrás—, `inventory` lo valoriza al `costo_promedio` sobre las mismas
    líneas que movieron el stock (mismo criterio que la merma: valoriza quien
    conoce el movimiento) y `accounting` lo asienta por `regla_asiento` como
    gasto de alimentación de personal. Anular el consumo repone el insumo
    **y reversa el asiento**, o el gasto quedaría inflado por comida que
    nadie comió.
  - Lo **autoriza un encargado con su PIN** (permiso propio
    `sales.registrar_consumo_personal`, separado de `sales.crear`) y exige
    motivo de un enum cerrado (`fin_semana`, `feriado`, `alta_actividad`,
    `capacitacion`, `otro`) — es comida gratis: sin firma cualquiera se
    sirve, y un motivo de texto libre no agrupa el gasto por causa.
  - **No se registra quién comió**, por decisión del negocio: se alimenta al
    turno. La columna nullable puede agregarse después sin romper nada.
  - Costo aceptado: el asiento depende de que la empresa configure sus dos
    cuentas y la regla; sin ella el consumo queda en el movimiento de
    inventario y en el log, como todo el resto de la generación automática.
    El reporte formal por sucursal/mes queda como deuda — hoy se lee por
    `GET /sales/ventas?tipo=consumo_personal`.

- Módulo `reports`: emisión y distribución de reportes (ADR-033). El ERP
  publicaba 52 eventos y solo **cuatro** llegaban a una persona, cableados en
  `users/application/listeners.py`; a quién le llegaban lo decidían dos
  funciones fijas cuyo propio docstring declaraba el hueco («el punto de
  configuración futuro está en `destinatarios_de_sucursal`»). No había forma
  de ver el mapa ni de cambiarlo sin un deploy, y varias reglas de negocio que
  exigen reportes dirigidos (RN-CTP-004, RN-INV-020, RN-INV-021, RN-PRD-009)
  seguían sin implementar — `inventory.conteo_vencido` ya publicaba
  `dirigido_a: ["almacen","gerencia"]` y no había nadie del otro lado. Ahora
  hay áreas, reglas por (empresa, emisión, sucursal) y una **matriz** que
  además marca lo que falta: **huecos** (el hecho ocurre y no se entera nadie)
  y **fugas** (regla activa que no llega a nadie). Trece emisiones cableadas,
  incluidas las cuatro migradas. Migración `9a1c4e7b2d30`.
- El catálogo de emisiones es **cerrado y en código**, no una tabla: la regla
  configura *a quién* llega un reporte, nunca *qué datos* lee. Si fuera
  administrable por API, quien puede crear reglas podría hacerse enviar
  cualquier payload del bus. Costo aceptado: una emisión nueva es un cambio de
  código, no de configuración.
- Leer un reporte exige **dos** puertas: ser destinatario y tener el permiso
  del módulo dueño del hecho. Estar en la lista de distribución no da acceso
  al dato — un cocinero puede enterarse de que hubo un descuadre de caja sin
  ver el detalle de la caja. `reports.leer_matriz` es un permiso aparte
  porque el mapa revela la estructura organizacional; `reports.administrar`
  queda solo en `admin`.
- Las entregas **no son retroactivas**: `regla_id` y el motivo de cada entrega
  (`area:almacen`, `dinamico:encargado_de_turno`) se congelan al emitir, así
  que cambiar la distribución mañana no reescribe a quién le llegó ayer. Todo
  cambio de área o regla queda en `audit_log`, que es la respuesta a «¿alguien
  tocó los flujos?» sin mantener un historial en paralelo.
- Una emisión sin destinatarios ahora **se guarda igual**, con cero entregas.
  Antes era un `log.warning` que nadie leía; un aviso que no llegó a nadie es
  información de gestión, no un no-evento.

- **Restas: "sin cebolla" ya mueve el inventario** (2026-08-09, ADR-035,
  RN-COM-028/RN-PRD-019, migración `a4f1d0c8b573`). `RN-PRD-004` manda aplicar
  los modificadores en el orden **tamaño → combinación → extras → restas**, y
  las restas eran el único tramo sin implementar: se escribían en la nota
  libre a cocina, el plato salía bien y **el inventario descontaba la cebolla
  igual**. Esa cebolla que se quedó en la cámara aparecía como faltante en el
  conteo del mes sin que nadie pudiera explicarlo.
  - `venta_item.sin_articulo_ids` (JSONB, nullable) guarda qué insumos no
    lleva la línea. Guarda `articulo_id` y **no** `receta_item_id` porque la
    línea de receta se edita y se borra, el artículo no: guardando la línea,
    una receta corregida mañana dejaría restas históricas apuntando a nada y
    la comanda reimpresa de una venta vieja diría "sin —". NULL = no quitó
    nada, que es lo que vale para todo lo ya vendido, sin backfill.
  - **Lo quitable es la receta**: `GET /sales/productos/{id}/quitables`
    devuelve los insumos del producto. No hay tabla ni flag de "quitables"
    que mantener — sería la misma verdad escrita dos veces, y dos datos que
    dicen lo mismo terminan diciendo cosas distintas. Pedir quitar algo que
    la receta no pone devuelve 409; el replay del hub se exceptúa (ADR-009),
    porque esa venta ya se preparó y la receta pudo cambiar durante el corte.
  - **No cambia el precio; sí el consumo.** Quitar cebolla no abarata la
    pizza, pero el insumo deja de descontarse, y la reposición por anulación
    o nota de crédito devuelve **solo lo que se consumió** — reponer lo que
    nunca salió dejaría stock de más en el conteo.
  - Cocina las ve: KDS en ámbar y comanda impresa (`SIN CEBOLLA`, sangrada).
    En el PDV son chips rojos y tachados junto a los extras; la nota libre
    sigue existiendo para lo que no es un insumo ("bien cocida").
- **Lienzo de nodos del producto comercial**
  (`/catalogo/productos/{id}/nodos`, 2026-08-09, ADR-035). El árbol completo
  de lo que se puede pedir, sobre un canvas oscuro a pantalla completa con
  pan, zoom, minimapa y aristas curvas (`@xyflow/react`): producto → tamaños
  → grupos (el sabor es uno) → extras → restas → empaque → **PLATO**. Al
  tocar los nodos se arma un plato y el inspector recalcula en vivo la receta
  fusionada, el costo y el margen de esa combinación exacta. Antes había que
  abrir cinco pantallas y sumar a mano.
  - Las columnas de izquierda a derecha **son** RN-PRD-004: hasta ahora la
    regla vivía implícita en el orden vertical de unas filas; ahora es la
    espina visible de la pantalla. Cada nodo elegido tira una arista al
    plato, que es la suma de la receta dibujada; las restas llegan punteadas
    en ámbar y el empaque llega punteado cuando la modalidad no lo consume,
    con lo que RN-EMP-003 deja de ser una nota al pie.
  - La primera versión eran filas de `<div>` con líneas de 1px en CSS y se
    descartó por lo que era: *"parece más HTML que elementos interactivos"*.
    El cambio de decisión está en la enmienda de ADR-035.
  - Vive fuera del shell del módulo, como el PDV y el KDS, para poder tomar
    los 100dvh; a cambio hace **su propio guard de permiso**, con prueba
    Playwright que verifica que un cajero no entra ni por URL directa.
  - Los nodos se arrastran y **no se guarda dónde quedaron**: el orden lo
    dicta RN-PRD-004 y persistirlo sería columna, migración y contrato para
    algo cosmético.
  - Eso **no es un modelo nuevo**: el tamaño ya era un producto hijo
    (RN-COM-022) y el sabor ya era una opción de grupo con receta propia
    (RN-COM-021/023). Lo que faltaba era verlo junto.
  - La fusión se calcula en el cliente y **no se guarda**: es un simulador.
    Lo que se descuenta de verdad sale del servidor al confirmar la venta.
  - Las cantidades de cada receta se siguen editando en Catálogo → Recetas,
    con enlace desde cada nodo (ADR-023 §4: el editor duplicado ya se reportó
    como confuso una vez).
- **Quitar un extra de un producto y borrar un grupo de opciones**
  (`DELETE /sales/productos/{id}/extras/{extra_id}` y
  `DELETE /sales/productos/{id}/grupos/{grupo_id}`). Cierra la deuda que
  ADR-023 dejó anotada. Borrar un grupo **suelta** sus extras en vez de
  borrarlos: el extra es un producto comercial con su receta y su precio, y
  existe con o sin grupo.

- **Tres coherencias entre archivos que no se importan pasan a ser tests**
  (2026-08-08, `tests/test_repo_coherencia.py`). Las tres fallaron de verdad
  el mismo día y las tres se detectaron a mano, después de mergear.
  - **Números de ADR repetidos.** Tres ramas en paralelo eligieron "el
    siguiente" contra el `main` que cada una veía; hubo que renumerar dos
    veces (029 → 031 → 032). El número lo sigue eligiendo una persona —no hay
    forma de reservarlo—, así que lo que cambia es que el choque se ve en el
    PR y no después. También se exige numeración sin huecos: un hueco casi
    siempre es un ADR renumerado a medias.
  - **ADR ausente del índice.** `docs/00_PROJECT.md` es por donde entra
    cualquiera, persona o agente; un ADR que no está listado ahí existe solo
    para quien ya sabía que existía.
  - **El Python del CI contra el de la imagen.** El PR #49 subió el
    `Dockerfile` a 3.14 y dejó los cuatro jobs de `setup-python` en 3.12: el
    job `imagen` solo comprueba que el contenedor construya y conteste
    `/health`, así que una dependencia incompatible con el intérprete nuevo
    habría llegado a producción con `main` en verde.
  - La cadena de Alembic no entra acá: el job `backend` ya falla con más de
    una cabeza.
- **Dependabot agrupa los majors aparte y deja de mandar un PR por action**
  (2026-08-08). Los majors de pip y npm van juntos y separados de los
  menores: un major es trabajo propio, no un bump, y mezclado con los menores
  se revisa con la misma vara que ellos — que es como el #37 entró sin migrar
  nada. Las actions y las imágenes pasan a grupo único: sin agrupar, los #21,
  #22, #24, #25, #35, #36 y #38 fueron siete PRs para siete líneas de YAML, y
  ese ruido es lo que hace que se mergeen sin mirar.
- **`docs/engineering/trabajo-en-paralelo.md`** (2026-08-08): cómo trabajar
  con varias ramas o sesiones a la vez sin duplicar trabajo — PR en borrador
  desde el primer commit, y quién renumera cuando dos ramas piden el mismo
  ADR o la misma cabeza de Alembic. El 2026-08-08 salieron cuatro PRs
  distintos arreglando el mismo bug (#40, #46, #47, #48) y tres se cerraron
  sin mergear: no fue un problema de código, fue de visibilidad.

### Changed

- **El changelog se escribe por fragmentos y `main` quedó protegida**
  (2026-08-08). Dos cosas que se rompían por la misma razón: nada obligaba a
  que un cambio llegara sano a `main`, y todos los cambios se escribían en la
  misma línea.
  - `changelog.d/`: un archivo por cambio (`<tipo>-<slug>.md`), que
    `scripts/cortar_version.py` junta en una sección nueva al cortar la
    versión. `CHANGELOG.md` deja de editarse a mano. El punto de inserción
    compartido —arriba de todo, bajo `## [Unreleased]`— era el conflicto: de
    siete PRs mergeados el 2026-08-08, cinco chocaron ahí y dos como archivo
    entero, sin que el contenido se contradijera en ninguno.
  - Lo acumulado desde el scaffold pasa a `## [0.2.0] - 2026-08-08` y se
    etiqueta `v0.2.0`, el primer tag del repositorio.
    `.github/workflows/release.yml` ya escuchaba `tags: ["v*"]` y nunca se
    había disparado. `[Unreleased]` arranca vacío.
  - **Ruleset en `main`**: PR obligatorio, los seis jobs del CI en verde y la
    rama al día antes de mergear, sin `bypass_actors`. El 2026-08-07 el PR
    #37 se mergeó con `frontend` y `e2e` en rojo y dejó `main` rota 24 h; el
    CI lo había atrapado y no había nada que impidiera el merge. Para
    saltarlo hay que desactivar el ruleset desde Settings, que es un acto
    deliberado y no un botón al lado del merge.

- **La deuda técnica del ROADMAP se partió por área** (2026-08-08). Eran
  2.044 líneas en una sola sección de `ROADMAP.md` con 17 subsecciones, y era
  el otro punto donde chocaban las ramas paralelas: dos PRs de módulos
  distintos conflictuaban por compartir archivo, no por contradecirse. Ahora
  cada área vive en `docs/roadmap/deuda/<área>.md` y `ROADMAP.md` conserva un
  índice con el conteo de ⬜ abiertos y ✅ cerrados. Las referencias en prosa
  del tipo «ver ROADMAP → Deuda técnica → Frontend» siguen valiendo: el área
  es el nombre del archivo.
  - De paso se fusionó la fila **duplicada** `Módulo \`sales\` (PDV)` de la
    tabla de estado F0. Eran dos versiones parciales de la misma fila —una
    con la pantalla KDS, otra con variantes y opciones—, resultado de un
    merge anterior; ninguna contenía a la otra, así que leer la tabla daba
    una respuesta distinta según qué fila mirabas.

- **Todo el repositorio pasa a LF, y `.gitattributes` lo hace cumplir**
  (2026-08-08). `CLAUDE.md` → Formato exigía LF desde el principio, pero no
  había nada que lo aplicara: convivían **789 archivos en LF con 116 en CRLF
  y 2 mezclados**, según el sistema donde se hubiera editado cada uno.
  - El costo no es estético. Cuando dos ramas tocan el mismo archivo y una lo
    guardó en CRLF, git no ve tres líneas distintas: ve el archivo entero
    distinto, y el merge se vuelve un conflicto de 3.000 líneas que nadie
    puede revisar. Pasó dos veces el mismo 2026-08-08, con `ROADMAP.md` y con
    `docs/security/security.md`, y ninguna de las dos veces el contenido se
    contradecía.
  - `* text=auto eol=lf` normaliza el índice y el checkout en cualquier
    sistema operativo. `text=auto` deja que git detecte qué es texto, y los
    tres binarios del repositorio (dos `.docx` y el `.bpm` de Bizagi) quedan
    además pinneados explícitos: son formatos comprimidos y una sola
    conversión los corrompe sin aviso.
  - El commit toca 118 archivos y **no cambia una sola línea de contenido**:
    `git diff --ignore-cr-at-eol` sobre el cambio devuelve solo el propio
    `.gitattributes`.

- **El major de `@types/node` queda en `ignore`** (2026-08-08). Los tipos
  describen el runtime que el código va a encontrar, así que subirlos por
  delante del runtime es peor que quedarse atrás: los de Node 26 aprueban
  APIs que Node 24 —el que corren los jobs `frontend` y `e2e`— no tiene, y
  `tsc` daría verde sobre código que muere en ejecución. Se cerró dos veces
  por el mismo motivo (PR #29 y #55) y volvía cada semana; ahora el motivo
  está escrito donde se toma la decisión. Se quita al subir el CI a Node 26,
  en el mismo cambio: el número del `ignore` y el `node-version:` de `ci.yml`
  son el mismo número.

- `users` deja de decidir a quién le llega cada aviso y se queda con lo que
  siempre dijo ser: la bandeja. `destinatarios_de_sucursal` y
  `destinatarios_de_almacen` se mudaron tal cual a
  `reports/application/destinatarios.py`, donde pasan de ser *la* regla a ser
  dos resolutores dinámicos entre cuatro tipos de destinatario. Los cuatro
  handlers de `users/application/listeners.py` se reemplazan por uno solo, que
  consume `reports.reporte_emitido` con la lista ya resuelta. El usuario sigue
  teniendo **una sola campana**: `reports` publica un evento en vez de escribir
  en `notificacion`, que sigue siendo de `users`.
- `users.application.queries_publicas` expone `permisos_de(session,
  usuario_id)`: todos los códigos en una consulta, para **filtrar listas** por
  permiso (negar un acceso sigue siendo `require_permission`). Sin él, recortar
  un catálogo de 13 entradas costaba una consulta por entrada.
- Tres eventos ganan un campo, aditivo y compatible:
  `accounting.cierre_caja_irregular` += `sucursal_id`,
  `accounting.pago_requiere_aprobacion` += `empresa_id`,
  `production.no_conformidad_detectada` += `almacen_id`. Sin ellos el hecho no
  se puede atribuir a un tenant y su reporte no se puede escopar.

### Fixed

- Copiar `.env.example` a `.env` —el primer paso del README— dejaba la API en
  bucle de reinicio: `ALLOWED_HOSTS=*` reventaba el arranque con
  `SettingsError`. El `.env.example` documenta «listas separadas por coma» y
  `settings.py` tenía el validador para eso, pero pydantic-settings decodifica
  como JSON todo campo de tipo complejo **antes** de que corra ningún
  validador, así que `_lista_por_comas` no se ejecutaba nunca. Se marcan
  `allowed_hosts` y `cors_origins` con `NoDecode` para que el valor llegue
  crudo al validador, que ahora también resuelve el JSON que antes resolvía
  pydantic-settings — quien ya tenía su `.env` en ese formato no se entera.
  Solo se veía al levantar `docker compose` desde un clon limpio: los tests
  corren con los valores por defecto y nunca leían un `.env`. Van seis casos
  en `tests/test_settings.py`, incluido el que congela que en producción el
  comodín `*` siga abortando el arranque: arreglar el parseo no podía ablandar
  el endurecimiento.

- **La imagen del frontend no arrancaba, y nadie se enteraba hasta
  reconstruirla** (2026-08-09). El `Dockerfile` de `frontend/` copiaba solo
  `package.json` —sin el lock— y resolvía los rangos de nuevo en cada build;
  después, el `COPY . .` metía el `node_modules` **del host** encima del que
  acababa de instalar, porque no había `.dockerignore`. Con el árbol local
  desactualizado (Next 15) sobre una instalación de Next 16, el contenedor
  moría al arrancar:

  ```
  ⚠ Mismatching @next/swc version, detected: 16.3.0 while Next.js is on 15.5.22
  [Error: Missing field `writeRoutesHashesManifest`]
  ```

  El contenedor parecía sano porque venía corriendo con una imagen vieja,
  anterior a la deriva: el fallo aparecía recién al reconstruir.
  Ahora `npm ci` sobre `package-lock.json` —las versiones exactas que probó
  el CI— y un `.dockerignore` que deja fuera `node_modules`, `.next` y el
  `.env`, que además se colaba en la imagen. De paso el contexto de build
  baja de cientos de MB a lo que ocupa el código.

- `core/sync/serializacion.marca_de` devolvía marcas *naive* mientras el resto
  del motor de sync trabaja en UTC *aware*, así que el pull de un recurso con
  más de una página reventaba con `TypeError: can't compare offset-naive and
  offset-aware datetimes`. El bug estaba desde que existe la paginación y
  nunca se había visto porque ningún recurso sembrado pasaba de 100 filas:
  apareció al sumar los permisos de `reports` (`rol_permiso` pasó de 97 a
  109). Se normaliza en `marca_de`, que es el único borde donde un texto
  entrante se vuelve `datetime`, así que cubre a todo el motor de una vez.

- **Guardar un tablero pedía el nombre con `window.prompt`** (2026-08-08).
  El prompt nativo no se puede etiquetar ni estilar, y ningún automatismo de
  navegador lo alcanza: el guardado de un tablero de reportes **no tenía forma
  de probarse de punta a punta**. Ahora el nombre se pide en un diálogo de la
  página, con su `<label>` y su `id`. De paso, guardar sobre un tablero propio
  ya existente dejó de preguntar: conserva su nombre, y solo el alta y
  "Guardar como…" piden uno.
- **Cuatro campos del PDV no tenían nombre accesible** (2026-08-08). El monto
  declarado y el usuario/PIN del encargado en la apertura, y el destino del
  efectivo en el cierre, se apoyaban solo en su `placeholder`: un lector de
  pantalla no anuncia nada y el campo es imposible de alcanzar por nombre. Se
  les agregó `aria-label`.
- **El puerto de la API del suite e2e se puede mover** (2026-08-08). Estaba
  fijo en 8100 en tres archivos (`playwright.config.ts`, `e2e/servidor-api.mjs`
  y `e2e/servidor-web.mjs`) y en una máquina donde ese puerto ya está tomado
  —el `docker-compose` de otro proyecto, sin ir más lejos— la suite entera no
  arranca. `E2E_PUERTO_API` lo mueve sin tocar código; el default no cambia.
- **`TUNNEL_HOST` para probar el dev server desde afuera** (2026-08-08).
  Server Actions rechaza toda request cuyo `Origin` no coincida con el `Host`,
  así que detrás de un túnel público —probar el PDV en un celular real, por
  ejemplo— el login moría con `Invalid Server Actions request`. La variable es
  inerte si no está definida: nunca se activa en producción.

## [0.2.0] - 2026-08-08

Primera versión **etiquetada** (el `0.1.0` de abajo se escribió al arrancar y
nunca se llegó a taggear). Recoge todo lo construido sobre el scaffold: los
ocho módulos, el PDV, el ciclo de caja, la facturación electrónica, el modo
offline, el frontend y la infraestructura de despliegue. El ERP todavía no
opera en producción, de ahí el `0.x`.

### Added

- **La encuesta de satisfacción sale de verdad, y es una conversación**
  (2026-08-08, ADR-031, migración `c1f80b6a2d34`). Hasta ahora `POST
  /marketing/encuestas` creaba una fila y publicaba un evento: **nada salía
  del ERP**. Ahora hay un adaptador de la WhatsApp Cloud API
  (`src/shared/integrations/whatsapp/`) y un guion de preguntas que es dato,
  no código.
  - **Nodos, no formulario.** WhatsApp no tiene formulario: tiene mensajes,
    uno a la vez. Cada `encuesta_pregunta` declara a dónde sigue la
    conversación (`siguiente_codigo`) y por dónde se desvía según lo que el
    cliente contestó (`saltos`). Un 2 de 5 pregunta **qué** falló; un 5
    pregunta si nos recomendaría. Preguntarles las dos cosas a todos alarga
    la encuesta y baja la tasa de respuesta, que es la métrica que hace que
    el resto sirva.
  - **El primer "ok" del cliente no es el puntaje.** Meta solo acepta
    plantillas aprobadas fuera de la ventana de 24 h, así que la encuesta se
    abre con una plantilla y la ventana la abre la respuesta del cliente.
    Contar ese "ok" como respuesta dejaría a media base con la nota de haber
    dicho que sí; `conversacion_abierta` lo distingue.
  - **Los ciclos se rechazan al guardar el guion**, no al enviarlo: A → B → A
    no rompe nada al crear la plantilla y convierte la encuesta en un bucle
    que le escribe al cliente para siempre.
  - Tres puertas de entrada —webhook de Meta, enlace público con token, y la
    tablet del local— con **un solo caso de uso** detrás.
  - Expiración automática por barrido horario (Celery beat); antes
    `expirar_encuesta` era un endpoint que alguien tenía que acordarse de
    llamar.
- **Calendario de contenido con el arte** (2026-08-08). `pieza_contenido`
  guardaba título, canal, fecha y métricas: todo menos la pieza. Un
  calendario sin el arte obliga a abrir otra carpeta para saber qué se
  publica el jueves, y ahí es donde se publica la versión vieja del banner.
  `GET /marketing/piezas/calendario` agrupa por día y cuenta los adjuntos;
  los archivos cuelgan de `archivo` (`src/shared/`, ya polimórfico) en vez de
  un storage propio de marketing.
- **Evaluación de agencia vs. interna** (2026-08-08, RN-MKT-006, ADR-030).
  La decisión se documentaba fuera del ERP; seis meses después nadie podía
  mostrar por qué se pagó lo que se pagó. `evaluacion_agencia` +
  `opcion_agencia` congelan los criterios ponderados **antes** de ver las
  propuestas, obligan a que la opción interna compita (comparar tres agencias
  entre sí no contesta si hace falta una agencia), y separan evaluar de
  decidir en dos permisos. Apartarse de la recomendada o del presupuesto se
  puede, en silencio no: el motivo pasa a ser obligatorio.
- **Los eventos de marketing ya tienen quién los escuche** (2026-08-08,
  ADR-030). `marketing.campana_lanzada` y `marketing.lead_generado` se
  publicaban al vacío. Ahora el propio módulo los consume en
  `campana_metrica`, junto con tres eventos nuevos (`lead_atribuido`,
  `pieza_publicada`, `encuesta_respondida`). La satisfacción se le acredita a
  la campaña por la cadena lead → venta → encuesta: una encuesta de un
  cliente que llegó solo no le suma a ninguna campaña, que es lo correcto. El
  acumulado es derivado y se puede reconstruir
  (`POST /campanas/{id}/metricas/recalculo`).

### Changed

- **`POST /marketing/encuestas/{id}/respuesta` cambia de contrato**
  (2026-08-08). Recibe `{"valor": "..."}` —la respuesta a **un** nodo— en vez
  de `{"puntaje": n, "comentario": "..."}`, y devuelve
  `{encuesta, pregunta_actual, url_publica}` en vez de la encuesta pelada.
  `POST /marketing/encuestas` devuelve la misma envoltura. No hay datos
  productivos afectados: el módulo se creó el 2026-08-01 y no hay campañas
  cargadas. Las encuestas anteriores al guion (`plantilla_id` NULL) se siguen
  contestando con un puntaje suelto.
- **`marketing` dejó su jerarquía de errores propia** (2026-08-08). Era el
  único de los ocho módulos que declaraba `MarketingError(Exception)` y
  traducía a HTTP en cada endpoint: 17 `try/except` cuyo único cuerpo era
  `raise _http(e)`. Ahora hereda de `src/shared/errors.py` y el mapeo lo hace
  `src/core/error_handlers.py`, una sola vez para todo el ERP. Mismos códigos
  de respuesta, 60 líneas menos.
- **Token de API para cuentas de agente** (2026-08-08, ADR-032, migración
  `b3f7d21a9c04`). Un `usuario` con `tipo=agente_ia` —n8n, el bot de
  pedidos, el hub de sucursal— se autenticaba con username + PIN de 6
  dígitos, o sea con un secreto de 20 bits guardado en un `.env`, sujeto a
  un lockout de 5 intentos que apaga la integración y a un refresh que hay
  que rotar cada 7 días desde un proceso desatendido. Ahora tiene su propia
  credencial: `token_agente`, 256 bits de `secrets`, del que se persiste
  solo el SHA-256 (el claro sale una única vez, al emitirlo).
  - `POST/GET/DELETE /api/v1/users/{id}/tokens[/{token_id}]` con
    `users.gestionar`. Se revoca de a uno, sin apagar la cuenta ni las
    demás integraciones. `expira_en` opcional (NULL = sin vencimiento) y
    `ultimo_uso_en` con granularidad de una hora, para poder apagar lo que
    ya nadie usa.
  - **El RBAC no cambia**: `api/deps.get_claims` distingue por el prefijo
    `prv_`, resuelve el usuario contra la tabla y arma los mismos claims que
    armaría un login. De ahí para abajo —tenant, permisos, restricciones,
    auditoría— nada distingue una credencial de la otra. Un usuario `humano`
    no puede tener token (409) y el `tipo` se revalida en cada request.
  - SHA-256 y no Argon2 como el PIN: 256 bits aleatorios no se rompen por
    fuerza bruta, y esto se verifica en **cada** request.
  - El hub sigue con username + PIN: migrarlo obliga a rotar el secreto de
    cada local y es un cambio de operación (ROADMAP → Deuda técnica).
- **CRUD de organización por API** (2026-08-08). Grupo, empresa, marca,
  licencia de marca, sucursal y almacén solo los escribía el seeder: dar de
  alta un local obligaba a correr un script contra la base. Sin cambios de
  esquema — las seis tablas ya existían.
  - Permiso propio `organizacion.gestionar`, separado de `users.gestionar`:
    quien crea cajeros no tiene por qué poder fundar sucursales ni cambiar
    el RUC de la empresa. Fundar un grupo o una empresa exige además `*`.
  - La API valida lo que el seeder tipeaba a mano: una sucursal solo opera
    una marca **licenciada** a su empresa (409 si no), la licencia liga
    marca y empresa del mismo grupo, un almacén de tipo `sucursal` exige
    `sucursal_id` de su misma empresa, y ninguno se abastece de sí mismo.
  - La baja es **lógica** y se niega con dependientes vivos: una empresa con
    sucursales o almacenes activos, una marca con locales abiertos o
    licencias vigentes, un central del que otros se abastecen. Cerrar un
    local es `estado="inactiva"` y no hay DELETE de sucursal: sigue siendo el
    ancla de sus ventas, cajas y trabajadores.
  - `DELETE /almacenes/{id}` no mira el stock: vive en `inventory` y `users`
    no importa el dominio de otro módulo (ROADMAP → Deuda técnica).

### Changed

- **`auth_headers(session, username)` en `tests/conftest.py`** (2026-08-08):
  emite el mismo JWT que emitiría `/auth/login` —mismos claims, misma
  firma— sin verificar el PIN, que ya tiene sus propios tests en
  `test_users_auth.py`. Lo usan los tests que necesitan **varias identidades
  distintas** en la misma corrida: el CRUD de organización compara lo que ve
  un superusuario con lo que ve un admin de una sola empresa, y cada login
  gasta cuota del limiter, que desde `_rate_limit_en_memoria` se ejercita de
  verdad y son 10 por ventana.
  - Deliberadamente **no** se usa el token de agente para autenticar los
    tests: haría que el suite ejerciera un camino de autenticación que
    ningún humano usa, y obligaría a sembrar un token en cada fixture.
- **La imagen y el CI corren el mismo Python: 3.14** (2026-08-08). El bump
  del `Dockerfile` a `python:3.14-slim` venía solo: los cuatro jobs que usan
  `actions/setup-python` seguían en 3.12, así que `pytest` nunca tocaba el
  intérprete que la imagen ejecuta. El job `imagen` solo comprueba que el
  contenedor construya y conteste `/health`; una incompatibilidad de una
  dependencia con 3.14 se habría descubierto en producción con `main` en
  verde. `requires-python` ya decía `>=3.12`, así que no hay nada que
  relajar.

### Fixed

- **Un fetch caído se dibujaba igual que "no hay datos"** (2026-08-07). El
  patrón `.catch(() => setLista([]))` estaba en cuatro lugares y convirtió un
  fallo real en algo indiagnosticable desde la pantalla: una venta con pago
  dividido no aparecía en la pestaña "Cobrados" del PDV, la venta **sí**
  estaba en la base, y la única pista que daba la UI era una lista vacía —
  exactamente lo mismo que se ve un día sin ventas.
  - Clasificador nuevo en `frontend/lib/carga.ts`, sin dependencias y
    probado con `node --test` (`lib/carga.test.ts`, 7 casos). Lee el status
    **por forma** y no por `instanceof`, porque el proyecto tiene dos clases
    de error de API (`ApiError` en el servidor, `ErrorApi` en el navegador) y
    a un Server Component pueden llegarle las dos. `Falla` guarda además el
    mensaje del servidor como `detalle`: sin eso, saber qué pasó exigía abrir
    las herramientas de desarrollo.
  - **PDV**: mesas, pedidos cobrados y pedidos en cocina muestran un panel de
    error con el detalle y un botón "Reintentar" que llama a la misma función
    que hace la carga inicial. El reintento es en sitio a propósito: recargar
    la página del PDV pierde los borradores abiertos en las pestañas del
    ticket. El estado vacío ("Todavía no hay pedidos cobrados hoy") queda
    reservado para respuestas exitosas sin filas.
  - **Dashboard**: el `opcional()` que devolvía `null` ante cualquier
    `ApiError` trataba igual "no tienes permiso" y "no se pudo preguntar", y
    de paso dejaba que un error de red tumbara la página entera (no hay
    `error.tsx`). Ahora solo el **403** se traga —el servidor contestó y dijo
    que no—; red, 5xx y 401 salen en `components/shell/aviso-fallo.tsx`, con
    reintento vía `router.refresh()`. El tablero sigue armándose con los
    bloques que sí cargaron.
  - Cuatro cargas del PDV conservan el patrón viejo (carta, medios de pago,
    POS y caja abierta) — quedan anotadas en ROADMAP → Deuda técnica →
    Frontend, no se tocaron en este cambio.
- **Los eventos de `marketing` se despachaban antes del commit**
  (2026-08-08). `campana_lanzada`, `lead_generado` y `encuesta_enviada` se
  publicaban sin `session=`, o sea en el acto, en medio de una transacción
  que todavía podía fallar — justo lo que ADR-016 existe para evitar. Con el
  envío real de la encuesta el bug dejaba de ser teórico: el worker abre su
  propia sesión y habría buscado una fila que aún no estaba escrita.
- **`normalizar_telefono` no sacaba el prefijo troncal** (2026-08-08). Un
  contacto tecleado en caja como `(051) 987-654-321` quedaba en
  `051987654321`, que Meta rechaza. Los ceros de la izquierda son prefijo de
  marcado, nunca parte del número: E.164 no empieza con cero.
- **`main` estaba en rojo desde el bump a `@tanstack/react-table` 9**
  (2026-08-08). El PR #37 (2026-08-07, dependabot) subió la librería de
  8.21.3 a 9.0.0 sin migrar una línea. En v9 no existe `useReactTable` —es
  `ReactTable` + `createCoreRowModel`—, `VisibilityState` no se exporta y
  `ColumnDef` toma dos genéricos: las 13 pantallas que usan
  `components/tabla/tabla-datos.tsx` quedaron rotas. Vuelve a `^8.21.3` y su
  major queda en `ignore` en `.github/dependabot.yml`; la migración a v9 es
  trabajo aparte (ver ROADMAP → Deuda técnica → Frontend).
  - **El CI lo atrapó y el PR se mergeó igual, en rojo**: fallaron los jobs
    `frontend` y `e2e`, primero en el PR (run `31202169287`) y otra vez en
    `main` tras el merge (`31210826670`). No fue un agujero de cobertura: fue
    un merge sobre CI rojo.
- **El job `frontend` no corría un chequeo de tipos propio** (2026-08-08).
  Ahora corre `npm run typecheck` (`tsc --noEmit`, script nuevo en
  `frontend/package.json`) junto a `npm run lint`, bloqueante. No es
  cobertura nueva —`next build` ya typechequea: Next 16 corre el `tsc` del
  proyecto con el mismo `tsconfig.json`— sino momento y claridad: 6 s contra
  ~40 s, antes de los tests y del build, y falla diciendo "tipos". En el caso
  de #37 el build ni llegó a esa etapa: murió antes empaquetando, con
  `Export useReactTable doesn't exist in target module` de Turbopack.
  `npm run lint` pasó igual, porque ESLint revisa el árbol sintáctico y no si
  el símbolo importado existe.
- **`frontend/package-lock.json` fijado a LF** (2026-08-08, `.gitattributes`
  nuevo). npm lo reescribe con los saltos de línea del sistema: el
  `npm install` de este mismo cambio, en Windows, lo pasó entero a CRLF y
  convirtió un cambio de tres entradas en un diff de 10 000 líneas. Un
  lockfile ilegible es un lockfile que nadie revisa.
- **Dos temporales de Word estaban versionados en la raíz** (2026-08-07).
  `~$F1.docx` (el archivo de bloqueo que Word crea al abrir un documento) y
  `~WRL0908.tmp` (su respaldo de autoguardado) entraron en el import inicial
  del repositorio. Son basura de sesión: no describen nada del proyecto y el
  `.tmp` es una copia parcial de un documento que ya está versionado. Se
  sacaron del índice y del disco, y `.gitignore` ahora tapa `~$*` y
  `~WRL*.tmp` para que no vuelvan. El `.dockerignore` ya los excluía del
  contexto de build, pero eso no impedía que se versionaran.
- **Los campos de apertura y cierre de caja no tenían nombre accesible**
  (2026-08-07). Usuario, PIN, destino de custodia, atribución del descuadre y
  el monto declarado eran `<input>`/`<select>` con solo `placeholder`. Un
  `placeholder` no es un nombre: desaparece al escribir y ningún lector de
  pantalla lo anuncia como el nombre del campo. Se agregó `aria-label` a los
  seis. Se usó `aria-label` y no un `<label>` envolvente porque los pares
  usuario/PIN son celdas de la grilla `.pdv-dos` y envolverlos la rompe.
  - Salió de una corrida de pruebas por navegador: el agente no encontraba el
    PIN de quien recibe y no podía cerrar la caja. El `e2e` existente no lo
    vio nunca porque maneja los diálogos por `data-testid`, un atributo
    nuestro que existe aunque el campo esté mudo para asistencia técnica. La
    prueba nueva busca por etiqueta a propósito.
- **El nombre del tablero se pedía con `window.prompt`** (2026-08-07). El
  prompt nativo no se puede etiquetar ni estilar, y ningún automatismo de
  navegador lo alcanza: guardar un tablero no tenía forma de probarse de
  punta a punta. Ahora es un diálogo con campo etiquetado. Guardar sobre un
  tablero propio existente ya no pregunta nada — conserva su nombre; solo el
  alta y "Guardar como…" piden uno.

### Fixed

- **El engine no tenía timeout de conexión: un Postgres mudo colgaba el
  request para siempre** (2026-08-08). `create_engine(settings.database_url,
  pool_pre_ping=True)`, sin `connect_args`. Un servidor que **no rechaza** —
  acepta el TCP y se queda callado, o se le cae la red de por medio— dejaba a
  psycopg en `wait_conn` sin límite: el ERP no daba error, se quedaba mudo, y
  en caja mudo es peor que roto. Ahora `connect_timeout: 5`, aplicado solo
  cuando la URL es Postgres (`connect_args()` en `src/core/database.py`): es
  parámetro de libpq y el `e2e`, que levanta la API contra un SQLite
  desechable, revienta al arrancar si se lo pasan.
  - Se descubrió midiendo el suite: diez tests tardaban **130 s cada uno**,
    el tope del stack TCP de Windows. Ocho de ellos son barridos de Celery
    (`inventory`, `sales`) que usan `SessionLocal` directo, más `/health/sync`
    del hub. Con el timeout bajan a **5.2 s**.
  - Los otros dos son `test_esquema.py::test_base_inalcanzable_*`, que arman
    su propio engine contra `127.0.0.1:1`. La docstring decía que el puerto
    "se rechaza en el acto, sin esperas" — cierto en Linux, falso en Windows,
    que descarta el SYN en silencio. Ahora reusan el mismo `connect_args()`:
    130 s → 5.1 s.
- **El suite del backend no tardaba: se colgaba, y de paso escribía en la base
  de desarrollo** (2026-08-08). Cada `env` de test parchea el
  `session_factory` de los listeners que su test ejercita, y **solo esos**.
  Los otros dos módulos de listeners quedaban apuntando al Postgres real, así
  que confirmar una venta despertaba `accounting.on_venta_confirmada`, que
  abre su propia sesión —el evento se despacha después del commit, cuando la
  del request ya no existe— y se quedaba en `psycopg.wait_conn`. Sin timeout:
  para siempre. Se encontró con `py-spy dump` sobre cinco corridas trabadas
  hacía entre 30 y 90 minutos, todas en el mismo `POST /sales/ventas`.
  - Con el Postgres de desarrollo levantado no se colgaba, que es lo peor de
    todo: el listener conectaba **de verdad** y sembraba asientos de prueba en
    la base real, mientras el test miraba su SQLite y no veía nada.
  - Arreglo: `_listeners_sin_base_real` (conftest, autouse) apunta los tres
    `session_factory` a algo que revienta. Es seguro porque
    `EventBus._despachar` ya atrapa y registra lo que falle en un handler; el
    test que necesita el listener lo parchea como siempre, y el que no, ve una
    línea en el log en vez de un cuelgue. `tests/test_kds.py` pasó de colgarse
    a 12 casos en 16 s.

### Changed

- **La base de desarrollo pasó de Supabase al Postgres del `docker-compose`**
  (2026-08-08). Cada consulta a Supabase costaba ~130 ms de ida y vuelta —
  distancia, no trabajo de base: `SELECT 1` tardaba lo mismo que contar
  usuarios. Como todo request autenticado consulta permisos, una pantalla
  típica se iba a 2-3 segundos de puro viaje de red. En local esa latencia
  baja al orden del milisegundo.
  - `.env` guarda ahora la URL vista **desde el host** (`localhost:5433`,
    porque el 5432 lo ocupa Charlie's), que es la que usan alembic, pytest y
    un uvicorn suelto. Los contenedores ven otros nombres (`db:5432`,
    `redis:6379`), así que `docker-compose.yml` se los inyecta con el bloque
    `x-conexiones-internas` — `environment` gana sobre `env_file`. Un solo
    `.env` sirve a los dos y no hay que editarlo al alternar.
  - Costo aceptado: los datos de desarrollo dejan de ser compartidos y de
    verse en el Table Editor de Supabase. Se regeneran con
    `alembic upgrade head` + `python -m src.seeders.seed` (idempotente).
    Volver a Supabase son dos pasos, documentados en
    `docs/engineering/devops.md`.
  - Producción no cambia: `docker-compose.prod.yml` sigue sin servicio de
    base de datos y espera una gestionada por `DATABASE_URL`.
- **El suite del backend se paralelizó y dejó de pagar Argon2id de
  producción** (2026-08-08). **956 casos en 1 min 1 s**, contra los más de 10
  minutos de antes —cuando terminaba— y ningún test por encima de 6 s.
  Corría en serie y **ninguna fixture tenía `scope=`**, así que cada uno rearma su
  motor SQLite, sus 99 tablas, el seeder completo y la app FastAPI entera.
  Medido con `cProfile` sobre `tests/test_accounting.py` (22 tests, 16 s): el
  KDF se llevaba 3.9 s —46 hash de 55 ms del seeder más 24 verify de los
  logins—, y 24 intentos de conexión a un Redis que no está corriendo se
  colaban por los endpoints con rate limit.
  - `_argon2_barato` (conftest, sesión) baja Argon2id a `t=1, m=8 KiB, p=1`:
    de 55 ms a 0.1 ms por hash. Los parámetros reales quedan guardados en
    `HASHER_PRODUCCION` y ahora **sí** los vigila un test
    (`test_seguridad_del_hasher_de_produccion`, piso RFC 9106); antes ningún
    test los miraba.
  - `_rate_limit_en_memoria` (conftest, por test) reemplaza el cliente Redis
    por un contador en memoria, mismo criterio que el token de Factiliza y el
    broker de Celery que ya vivían ahí. De paso el límite deja de estar
    fail-open en pruebas: antes nunca se ejercitaba de verdad.
  - `pytest-xdist` con `addopts = "-n auto --dist loadfile"`. `loadfile` y no
    el reparto por test porque varios archivos tocan estado de módulo (el
    corta-circuito del limiter, la config de Celery) y así cada archivo vive
    entero en un proceso. Para depurar en serie: `pytest -n0`.
- **`F1.docx` pasó de la raíz a `docs/foundation/`** (2026-08-07). Es el brief
  original del ERP —el dictado del que salieron `vision.md`, `glossary.md` y
  `business-philosophy.md`— y estaba suelto en la raíz sin que ningún
  documento lo referenciara. Ahora vive junto a lo que originó y aparece en
  el índice `docs/00_PROJECT.md` marcado como material fuente **no
  normativo**: ante una diferencia mandan el glosario y la visión.
- **El puerto de la API del `e2e` sale de `E2E_PUERTO_API`** (2026-08-07). Era
  `8100` fijo en tres archivos; en una máquina con ese puerto tomado por otro
  proyecto la suite no arrancaba y el error —"already used"— no decía cuál de
  los dos servidores era. El default sigue siendo `8100`.
- **Tres pendientes de `inventory` cerrados como descartados** (2026-08-07,
  decididos con el usuario). No se difieren: se cierran con su razón escrita,
  para que no vuelvan a la lista cada vez que alguien la relea.
  - **`en_picking`**: un estado que no gobierna ninguna regla no es un
    estado, es un comentario. Entre `aprobada` y `despachada` no cambia
    ningún permiso ni validación, y habría que marcarlo a mano — un estado
    que depende de que alguien se acuerde miente la mitad del tiempo.
  - **Vehículo y tracking en la transferencia**: no hay flota. El traslado
    lo hace alguien del grupo en su propio vehículo y la placa se teclea en
    la guía, que es el único documento que la necesita (mismo criterio que
    ADR-027). El GPS mediría una ruta de veinte minutos entre dos locales de
    la misma ciudad; `transportista_id` ya responde quién lo llevó.
  - **Frecuencias de conteo ancladas al día del mes**: "mensual" en el
    almacén significa *cada mes más o menos*, no *el día 3*. Anclarlo haría
    aparecer un atraso cada febrero por una diferencia que a nadie le
    importa.
  De paso se barrieron las contradicciones que dejaban: el diagrama de
  estados de la solicitud todavía dibujaba `en_picking` —y le faltaba
  `cancelada`—, y ADR-020 seguía listando como pendientes la recepción
  parcial, el ciclo offline, el disponible negativo y `stock_merma`, los
  cuatro ya resueltos.

### Added

- **`audit_log` transversal, y usado** (2026-08-08, ADR-031, migración
  `b3d9f1c2a077`). La tabla decía en su docstring "consumido por todos los
  módulos" y el código decía otra cosa: el único escritor era
  `AuditLogRepo` en `users`, `rrhh` lo alcanzaba importando repositorios
  ajenos (excepción declarada en `test_arquitectura.py`), y anular una
  venta, aprobar un ajuste, emitir una OC o sacar plata del cajón no dejaban
  rastro alguno. Tampoco había forma de *leerlo*.
  - **Un solo punto de escritura**: `src.shared.auditoria.registrar(session,
    …)`, con el modelo mudado a `src/shared/models/audit_log.py`. Escribe en
    la misma transacción que el cambio auditado — si el cambio se revierte,
    el rastro también; auditar algo que no pasó es peor que no auditarlo.
  - **Escritura explícita, no captura automática por ORM**: el actor y la IP
    no están en la sesión, y un rastro que registra cada `UPDATE` no lo lee
    nadie. Se audita el acto de autoridad. El razonamiento completo y la
    alternativa descartada están en el ADR.
  - **Cinco módulos nuevos dejan rastro**: anulación de venta y descuento
    manual (`sales`), aprobación de ajuste de inventario (`inventory`),
    emisión de OC (`purchases`), ejecución de pago a proveedor e
    ingreso/retiro de efectivo del cajón (`accounting`), además de lo que ya
    auditaban `users` y `rrhh`.
  - **`GET /api/v1/auditoria`** (permiso `auditoria.leer`, rol `contador` —
    Contabilidad audita a Compras, Almacén y cajas, RN-CTB-009), paginado
    (ADR-026) y filtrable por entidad, acción, usuario y rango de fechas.
    **Sin `POST`**: el auditado no dicta lo que dice su auditoría.
  - **`empresa_id` nuevo (nullable) + índices** `(entidad, entidad_id)` y
    `(ts)`. Sin `empresa_id` la lectura no se puede escopar por tenant y un
    contador vería el rastro de otra empresa; nullable porque un login o un
    alta de rol no tienen empresa, y esas filas solo las ve el superusuario.
  - `rrhh` sale de las excepciones de acoplamiento cruzado: la lista de
    `test_arquitectura.py` encogió, que es la única dirección permitida.
  - **Sigue pendiente** la purga por antigüedad (deuda ya declarada): la
    tabla crece por inserción pura y no tiene retención automática.

- **El ciclo de abastecimiento funciona sin conexión** (2026-08-07, ADR-009
  fase 3). El hub replicaba catálogo y stock para poder **vender** offline;
  ahora el local también **pide, ve lo que viene y recibe**, que es lo que
  pasa cuando el internet no está — el camión no espera.
  - **Baja**: `solicitud_insumos`/`solicitud_item` (las que pidió),
    `transferencia`/`transferencia_item` (las que **entran** a su almacén) y
    `reserva_stock` —sin las reservas su `disponible` offline sería el
    físico entero y comprometería stock ya prometido—. De 28 a 35 recursos.
  - **Sube**: la solicitud creada, la recepción hecha y el conteo cerrado.
  - **El motor deja de estar cableado a `sales`.** El push era de un solo
    módulo; ahora hay un registro (`MODULOS_PUSH`) y **cada uno lleva su
    propio watermark**: si `inventory` se traba con una recepción que la
    nube rechaza, las ventas siguen subiendo. Que un conteo bloquee el
    dinero sería exactamente al revés de lo que importa.
  - Tres decisiones que valen más que las tablas: **la recepción no es una
    fila que sube, es un hecho** —la transferencia la creó el central, así
    que reproducirla dos veces tiene que ser inocuo o un error ajeno traba
    el recurso para siempre—; **el conteo sube cerrado, nunca a medias**
    —uno abierto generaría arriba ajustes por ítems que nadie miró—; y el
    orden del push es `sales` y después `inventory`, para que el conteo mida
    contra un stock que ya incluye lo vendido durante el corte.
  - En el camino se descubrió que **el hub no replicaba su almacén
    abastecedor**: `crear_solicitud` exige que exista, así que pedir offline
    fallaba con "abastecedor no encontrado". Ahora viaja la **ficha** del
    central; su stock sigue sin replicarse.

### Changed

- **Next.js 15.5.22 → 16.3.0, TypeScript 5.5 → 6.0.3 y ESLint pasado a flat
  config** (2026-08-07). Sale de tener `main` en rojo: el PR #28 subió
  `eslint-config-next` a 16.3.0, que solo publica configuración plana,
  mientras el repo seguía con `.eslintrc.json` y `next lint`. `npm run lint`
  moría con `Converting circular structure to JSON` y, como
  `next.config.mjs` no desactiva el lint del build, `npm run build` se caía
  detrás. Los cuatro PR de Dependabot abiertos fallaban por herencia de eso,
  no por lo suyo.
  - `frontend/.eslintrc.json` → `frontend/eslint.config.mjs`, y el script
    `lint` pasa de `next lint` (que Next 16 eliminó) a `eslint .`. El CLI de
    ESLint no descarta `.next/` ni `out/` por su cuenta: van explícitos en
    `ignores`.
  - `eslint .` analiza además archivos que `next lint` nunca miró. Eso
    destapó dos variables muertas en `playwright.config.ts` (`PYTHON` y
    `RAIZ`, que quedaron sin uso cuando los servidores se movieron a
    `e2e/servidor-*.mjs`). Se borraron.
  - `agentRules: false` en `next.config.mjs`. Next 16 escribe `AGENTS.md` y
    un `CLAUDE.md` en `frontend/` cada vez que corre `next dev`. `CLAUDE.md`
    es el archivo de reglas del proyecto y lo carga Claude Code como
    instrucciones: que una dependencia lo genere sola convierte un `npm
    update` en un cambio de las reglas de trabajo sin revisión, y además
    ensucia el árbol en cada arranque.
  - `tsconfig.json` lo reescribe Next 16 al arrancar (`jsx` pasa de
    `preserve` a `react-jsx`, entra `.next/dev/types` en `include`). Se
    commitea como Next lo deja, para que `next dev` no deje el árbol sucio.
  - Verificado en local: `npm run lint` sin errores, 176/176 de `npm test`,
    `npm run build` con las 31 rutas.
  - Queda deuda declarada en ROADMAP → Deuda técnica → Frontend: 34
    hallazgos nuevos del React Compiler en `warn`, y `middleware.ts`
    deprecado a favor de `proxy`.
- **Deuda "migraciones con vuelta atrás probada" cerrada en el ROADMAP**
  (2026-08-06): seguía abierta pese a que el job `migraciones` de
  `.github/workflows/ci.yml` corre `alembic downgrade base` y vuelve a subir
  desde 2026-07-28. `docs/engineering/devops.md` tampoco listaba ese job en
  la tabla de CI; ahora sí, junto con el chequeo del contrato OpenAPI del
  job `backend`.

### Fixed

- **`release.yml` no publicaba ninguna imagen** (2026-08-06). El job
  `publicar` moría en `docker/build-push-action` con `Cache export is not
  supported for the docker driver`: usa `cache-to: type=gha` pero nunca
  llamaba a `docker/setup-buildx-action`, y el driver por defecto no sabe
  exportar caché. Fallaba en **cada** push a `main` desde que existe el
  workflow, así que GHCR nunca recibió una imagen y la entrega continua
  del artefacto (ADR-008) era nominal. El job `imagen` de `ci.yml` ya
  traía el paso; ahora `release.yml` también.

- **Tres jobs de CI en rojo, destapados al integrar la rama a `main`**
  (2026-08-06). Los tres pasaban desapercibidos porque la rama nunca había
  corrido el pipeline completo contra `main`:
  - `migraciones`: `alembic check` proponía borrar y recrear el mismo
    `UNIQUE (empresa_id, serie, correlativo)` de `guia_remision` en cada
    corrida. La convención de nombres de `database.py` rinde
    `uq_<tabla>_<primera columna>` —o sea `uq_guia_remision_empresa_id`—
    y la migración `a4c8f21e6b09` le había puesto el nombre con las tres
    columnas. Nombre explícito en el modelo; sin migración nueva, porque el
    nombre en la base ya era el correcto.
  - `imagen`: el guard de deriva de esquema (`src/core/esquema.py`) mataba
    el contenedor al arrancar cuando la base no responde. El job levanta la
    imagen con un `DATABASE_URL` de juguete solo para ver si contesta
    `/health`, así que nunca llegaba a servir. Una base inalcanzable ahora
    es **alerta, no deriva**: no se pudo mirar no es lo mismo que faltan
    tablas, y de la base caída avisa `/health/ready`, que es quien la mide.
  - `frontend`: `npm test` moría con `ERR_UNKNOWN_FILE_EXTENSION` en los
    tres `.test.ts` antes de ejecutar un solo caso. El job estaba fijado en
    Node 20 y el stripping de tipos de `node --test` recién viene de fábrica
    desde 22.18; pasa a Node 24, que es el de la máquina de desarrollo.
- **`inventory.transferencia_recibida` se despachaba antes del commit**
  (2026-08-06). Era el único `publish` de escritura del módulo sin
  `session=`, así que el handler corría en medio de la transacción y un
  rollback posterior dejaba al consumidor actuando sobre una recepción que
  nunca ocurrió (ADR-016). Inofensivo mientras el evento no tenía
  consumidor; dejó de serlo el mismo día que ganó dos.
- **El cliente declaraba si su propio ajuste de inventario estaba dentro de
  margen** (2026-08-06). `POST /inventory/ajustes` recibía `dentro_margen` en
  el body, con default `True`, y ese campo es el único que decide si al
  aprobar se publica `inventory.ajuste_fuera_margen`: el mismo request que
  provoca el descuadre podía declararlo tolerable y apagar la alerta. Ahora
  lo calcula el servidor contra el stock del almacén y el margen aprobado
  para la empresa, igual que el cierre de conteo. El campo salió de
  `AjusteCreate` y del contrato OpenAPI; ningún cliente lo enviaba.
- **Cinco desacuerdos de contrato en el PDV**, destapados al tipar los
  cuerpos de request (2026-08-06). Ninguno había fallado todavía, y los
  cinco son de la misma familia que el 422 de la caja:
  - `modalidad` podía viajar `null` en `POST /sales/ventas`, que el
    contrato exige. El guard de pantalla existía (RN-COM-005); el tipo no lo
    sabía, así que nada impedía una llamada nueva sin él.
  - `pos_verificados` estaba tipado con `PosVerificado` —lo que se **lee**,
    que trae `serie`— cuando el request es `PosVerificadoIn`, que no la
    tiene. Leer y escribir no son el mismo schema.
  - `custodia` y `descuadre_atribucion` viajaban como `string` suelto sobre
    dos columnas `Enum`. Es el mismo agujero que se cerró el 2026-08-05 en
    el schema del servidor, que seguía abierto del lado del cliente: ahora
    son uniones tipadas con su guard (`esCustodia`, `esAtribucion`).
- **Las pruebas e2e del flujo del dinero pasan de rojo a verde y entran a
  CI** (2026-08-06). Dos causas, ninguna de la pantalla:
  1. **La prueba se saltaba el tipo de orden.** El PDV no deja cobrar sin él
     (RN-COM-005), así que el primer "Cobrar" abría el diálogo de tipo y no
     el de cobro. El test tomaba un atajo que el cajero no tiene; ahora pasa
     por el candado ("Para llevar", el único que no pide dato extra).
  2. **El `SyntaxError: Unexpected end of JSON input` que se venía
     atribuyendo a inestabilidad de `next dev` era el timeout disfrazado.**
     El presupuesto por test eran 90 s y el modo desarrollo compila cada
     ruta la primera vez que se la pide; la corrida moría a mitad de camino
     y el reporte señalaba el `expect` que quedó colgando. Como cada corrida
     dejaba la caché más tibia, el punto de falla se movía solo — que es
     justo lo que se lee como flakiness. Con 240 s el recorrido entra en
     ~96 s. **No hizo falta pasar a `build`+`start`**, así que tampoco hace
     falta tocar el origen de las Server Actions.
  Se suma `test.describe.serial`: la segunda prueba necesita la caja que
  cierra la primera, y en serie queda **saltada** en vez de fallar con un
  síntoma que no dice nada.
- **La apertura y el cierre de caja del PDV devolvían 422** (2026-08-05,
  ADR-025 Addendum). Los diálogos existían desde antes de ADR-025 y seguían
  mandando el contrato viejo (`monto_apertura` en vez de `monto_declarado`,
  el id del encargado en vez del token de `autorizacion`, un monto tecleado
  en vez del conteo por denominación). Estuvo roto un día entero sin que
  nada lo detectara: ninguna prueba automatizada toca esas pantallas.
- **`custodia` y `descuadre_atribucion` aceptaban texto libre sobre una
  columna `Enum`** (2026-08-05). Lo escrito entraba sin protestar y la fila
  quedaba **ilegible**: la lectura reventaba después con `LookupError` al
  mapear el enum, sobre una fila que es evidencia contable. Ahora se validan
  con `pattern` en el schema (422 en el borde) y la UI ofrece los valores
  reales. `custodia` es *a dónde va el efectivo*
  (`local_caja_fuerte`/`traslado_contabilidad`), no quién lo recibe — eso ya
  lo prueba la firma del PIN.
- **Las pestañas de cobrados y pedidos abiertos del PDV se dibujaban
  vacías** (2026-08-05). Desde la paginación del 2026-08-04 `GET /ventas`
  devuelve `{items, total, ...}` y `lib/pdv.ts` lo seguía leyendo como
  array; el `vs.filter is not a function` lo tragaba un `.catch` y la
  pantalla mostraba una jornada sin ventas. No había un solo test HTTP del
  listado; ahora hay cuatro.

### Added

- **Merma y devolución** (2026-08-06, ADR-028, migración `e7c390a5b41f`).
  Los dos slices grandes que le faltaban a `inventory`:
  - **La merma no es una tabla nueva.** El modelo de datos anticipaba
    `stock_merma` como "subtipo de stock reservado", y eso es exactamente
    lo que `reserva_stock` ya hacía: presente en el almacén, no disponible.
    Una tabla aparte habría duplicado almacén/SKU/cantidad/estado y —peor—
    partido el cálculo del disponible en **dos restas**, que es una que
    alguien se olvida. Lo único que faltaba era `reserva_stock.lote_id`: lo
    que se aparta por vencido o dañado **es** un lote concreto, y el desecho
    tiene que sacar ese y no el que FEFO elegiría (que puede ser el bueno).
  - **El ciclo de la merma tiene dos pasos y eso es la regla.** Registrar
    aparta **sin descontar stock** —el producto sigue en el estante hasta
    que alguien lo tire, y descontarlo antes haría que el conteo cíclico lo
    declarara sobrante al día siguiente—; resolver decide: `desecho` saca el
    stock y publica `inventory.merma_registrada` (que `accounting` asienta
    como pérdida), `reintegro` lo devuelve a disponible. El asiento va al
    desechar y no al apartar: mientras la auditoría no decide, asentar
    obligaría a reversar la mitad de los casos. Lo resuelve otro usuario,
    con los permisos del ajuste — la segregación es la misma y un permiso
    nuevo para la misma idea sería una segunda matriz que mantener.
  - **`devolucion` + `devolucion_item`** cubren los dos casos que no tenían
    camino. **A proveedor**: sale con el lote declarado (obligatorio si el
    artículo controla lote — el reclamo tiene que decir qué se rechaza),
    emite **su propia guía de remisión** y avisa a `purchases`. **De
    cliente**: entra, y `destino` decide si vuelve al estante o se aparta
    como merma en el mismo acto — sin ese segundo paso la próxima venta se
    la lleva. Sucursal→central **no se modeló**: es una `transferencia`
    (ADR-020) y duplicarla sería un segundo camino para el mismo movimiento.
  - **La guía de remisión gana un segundo emisor**:
    `guia_remision.transferencia_id` pasa a nullable y aparece
    `devolucion_id`. Motivo de traslado `13` y no `04`, porque `04` es
    "entre establecimientos de la misma empresa" y el destino es otro
    contribuyente. `lugar_destino` se teclea: `proveedor` no tiene dirección
    modelada, y eso cae en la misma categoría que el chofer y la placa.
- **Recepción parcial de transferencia** (2026-08-06): `{"parcial": true}`
  ingresa lo declarado y deja el resto **en tránsito** — el camión que trae
  la mitad hoy. Explícito y no deducido de que falten ítems: deducirlo haría
  que un olvido cierre la transferencia dando por perdido lo que todavía
  viene en camino. El evento `inventory.transferencia_recibida` sale **una
  sola vez**, al cerrar; si no, `accounting` asentaría el faltante de cada
  entrega por separado.
- **`recepcion_item` conserva el lote que declaró el proveedor**
  (`lote_codigo` + `fecha_vencimiento`, RN-VNC-002). El dato viajaba solo en
  el evento hacia `inventory`: si el listener fallaba, no quedaba dónde
  leerlo para reprocesar.
- **`receta` gana su columna de empresa** (2026-08-06, migración
  `d5b81e0c37a4`). Era la última entidad del catálogo sin tenant: el CRUD
  listaba las recetas de todas las empresas del grupo y el hub de cada
  sucursal las replicaba completas. Ahora el listado filtra, cada ruta por
  id pasa por `exigir_receta`, el **nombre es único por empresa y no por
  grupo** —dos empresas pueden vender la misma pizza con recetas
  distintas— y un ítem no puede tomar un artículo ajeno: eso responde
  **404, no 403**, porque para esa empresa el artículo no existe.
  `receta_item` no lleva columna propia; se acota por su receta.
  La salida que ADR-009 anticipaba —cruzar `producto_comercial`, dominio de
  `sales`, desde `inventory`— era la equivocada: el dueño del dato no era
  `sales`, era que a `receta` le faltaba la columna. El relleno de la
  migración atribuye a la única empresa operativa lo que no puede derivar de
  `articulo.empresa_id`; correcto hoy y a revisar a mano el día que la base
  tenga dos.
- **Los avisos de inventario llegan a alguien** (2026-08-06). Tres eventos
  se publicaban desde sus slices y nadie los escuchaba, así que enterarse
  seguía dependiendo de que alguien abriera la pantalla correcta:
  `inventory.stock_bajo_minimo` (nivel `aviso` — todavía hay stock, falta
  reponer), `inventory.lote_vencido_detectado` (`urgente`: ese stock ya se
  contaba como vendible y alguien pudo haberlo servido) e
  `inventory.conteo_vencido` (recordatorio que se repite cada día hasta que
  se cuente). Los tres van a la bandeja de `users`, que es el dueño del
  destinatario.
  Requirió `notificaciones.destinatarios_de_almacen`, porque
  `destinatarios_de_sucursal` no alcanzaba: **el central y el de producción
  no cuelgan de ninguna sucursal** y ahí no hay encargado de turno que
  valga. La regla es por rol (`almacenero`/`supervisor`/`admin`): en un
  almacén de sucursal, los de esa sucursal más quien está de turno; en uno
  de empresa, los de cualquier sucursal de la empresa — más gente de la
  necesaria, y a propósito, porque un aviso sin destinatario es un aviso
  perdido.
- **`inventory.transferencia_recibida` con consumidor en `accounting`**
  (2026-08-06): asiento **solo si el traslado llegó con faltante**. Mover
  mercadería entre almacenes de la misma empresa no mueve resultado —cambia
  de sitio, no de dueño— y un asiento por cada traslado llenaría el libro de
  movimientos que se cancelan entre sí; lo que sí es hecho contable es lo
  que salió y no llegó. El evento suma `monto_diferencia`, valorizado por
  **el emisor** al `costo_promedio`: el costo es dato de `inventory`, y
  hacerlo buscar por `accounting` sería importarle dominio ajeno.
- **Los tres barridos que nadie disparaba entran a Celery beat**
  (2026-08-06). `POST /conteos/verificar-vencidos` y
  `POST /lotes/bloquear-vencidos` existían desde sus slices y solo corrían
  si alguien los llamaba a mano — o sea, si alguien ya sospechaba; y
  `ComprobanteRepo.pendientes` no la llamaba nadie. Ahora:
  - `inventory.bloquear_lotes_vencidos` (06:00 hora Perú) y
    `inventory.reportar_conteos_vencidos` (06:15). **Antes del turno y no a
    cualquier hora**: el vencimiento cambia al pasar la medianoche del
    negocio, y bloquear el lote a media mañana deja que la primera salida
    del día se lo lleve. El picking ya bloquea el vencido que se topa, pero
    solo cuando alguien lo toca: en un almacén de baja rotación el vencido
    se cuenta como disponible hasta que a alguien se le ocurre pedirlo.
  - `sales.barrer_comprobantes_pendientes` (cada 15 min), que **encola uno
    por comprobante** en vez de emitir en línea — así cada uno conserva su
    backoff, y una caída de Factiliza no se convierte en un ciclo de 100
    timeouts. Filtra por intentos: un `rechazado` es un veredicto sobre
    datos malos y reenviarlo da el mismo rechazo; uno que agotó sus 5
    intentos daría `Conflicto` cada ciclo, para siempre.
  `tests/test_celery_beat.py` congela el cableado: un nombre mal escrito en
  `beat_schedule` no falla en ningún lado —beat encola, el worker descarta,
  el barrido no ocurre nunca—, el modo de falla más silencioso del ERP y
  justo en las tareas que existen para que algo no pase inadvertido. El test
  carga `include` como lo hace el worker, así que cubre también el módulo de
  tareas que nadie agregó a la lista.
- **Las excepciones de inventario dejan de ser invisibles** (2026-08-06,
  migración `c2f6a94b13de`). El módulo toma tres decisiones deliberadas que
  dejan el stock distinto de lo ideal **sin frenar la operación** —y las
  tres son correctas—, pero ninguna tenía dónde verse: un `log.warning` no
  es una superficie, nadie lee los logs buscando por qué el queso no cuadra.
  Ahora cada una tiene su reporte en el catálogo (ADR-024, que pasa de 10 a
  13):
  - `consumos_omitidos` ← **`incidencia_inventario`**, entidad nueva escrita
    por los **seis** puntos de omisión del listener (venta, OC y producción,
    por sucursal sin almacén / artículo sin SKU / stock insuficiente). El
    motivo es lo accionable: dice si hay que configurar la sucursal, dar de
    alta un SKU o mirar por qué el stock ya venía mal. Sin `atendida_at` a
    propósito: el reporte va por rango y una configuración rota reaparece
    mañana, que es la señal correcta.
  - `disponible_negativo` — SKUs con más reservado que físico. Reservar
    exige disponible, consumir no se bloquea nunca (RN-INV-009), así que el
    estado es alcanzable a propósito; lo que faltaba era verlo sin saber de
    antemano qué SKU mirar.
  - `salidas_sin_lote` — salidas de artículos con control de lote que ningún
    lote respalda (**RN-LOT-005**, nueva).
- **`inventory.stock_bajo_minimo` se publica de verdad** (2026-08-06), y
  **al cruzar** el mínimo, no cada vez que se está por debajo: con el stock
  ya bajo, un evento por venta convierte la alerta en ruido y deja de
  mirarse justo cuando importa —la misma falla que el margen sin piso—.
  Reponer y volver a caer avisa de nuevo. Sin consumidor todavía.
- **Motivo obligatorio al saltearse FEFO** (`movimiento_inventario.motivo_lote`,
  **RN-LOT-004** nueva). Se exige solo cuando el lote elegido no es el que
  FEFO sugería: pedirlo también cuando coinciden convierte el campo en un
  trámite que se llena con cualquier cosa, y un motivo que nadie escribe en
  serio da apariencia de control sin darlo.
- **Ventana de alerta de vencimiento por artículo**
  (`articulo.dias_alerta_vencimiento`, **RN-VNC-004** nueva): la leche avisa
  con días y una conserva con meses, y un número único dejaba a uno de los
  dos avisando cuando ya no sirve. `GET /lotes` marca `por_vencer` con la
  ventana del artículo; el `por_vencer_dias` de la consulta la sobrescribe.
- **Anulación de conteo** (`POST /inventory/conteos/{id}/anular`, motivo
  obligatorio). La única salida anterior era cerrarlo vacío, y un conteo
  cerrado en cero afirma "se contó y no había diferencias" —lo contrario de
  lo que pasó— además de correr el calendario de una categoría que nadie
  contó. Anular no genera ajustes ni mueve el programa.
- **Margen de error del ajuste por empresa, con piso en dinero**
  (2026-08-06, `inventory/margen_error_ajuste`, ADR-014/ADR-019). El margen
  deja de ser una constante del deploy: se lee del parámetro que Gerencia
  aprueba, y `INVENTORY_MARGEN_AJUSTE_PCT` (2 %) queda como default de
  arranque mientras no haya valor vigente. El valor lleva **dos tolerancias
  que conviven** y basta cumplir una: el **porcentaje** sobre la cantidad
  esperada y un **piso en dinero** sobre la diferencia valorizada al
  `costo_promedio` del artículo. El piso es lo que faltaba: 2 % de un conteo
  de S/ 30 en servilletas son 60 céntimos, así que cualquier diferencia real
  escalaba a Gerencia y la alerta se volvía ruido que nadie mira — la peor
  falla posible en un control. Con sistema en 0 sigue sin haber base para el
  porcentaje, pero el piso aplica igual.
  Primer parámetro **compuesto** del ERP: se lee con `valor_vigente`, no con
  el envoltorio escalar `umbral_vigente` que usan `purchases/oc_umbral` y
  `accounting/pago_umbral`. Lógica compartida por los dos productores de
  ajustes en `src/modules/inventory/application/margenes.py`.
  4 casos nuevos en `tests/test_conteos.py` (26 en total), incluido el que
  comprueba que una propuesta **sin aprobar** no rige.
- **Contrato extendido al resto del frontend** (2026-08-06): de 58 a **162
  casos**, en ~350 ms. Dos profundidades, y la diferencia importa:
  - **Los cuatro módulos importables** (`pdv` 19 operaciones, `catalogo` 20,
    `kds` 7, `reportes` 6) exponen la API como objeto llamable y se
    ejercitan de verdad. Cada lista se compara contra el objeto real del
    módulo: una operación nueva sin caso **hace fallar el test**. El arnés
    además respeta el código de respuesta del contrato, así que un `204` se
    responde vacío y ejercita la rama de `pedir` que existe porque pedirle
    `.json()` a una respuesta sin cuerpo revienta.
  - **Todo el resto** (Compras, Inventario, RRHH, Gerencia, Contabilidad,
    Marketing, Usuarios) llama desde Server Components y Server Actions, que
    piden `next/headers` y no se pueden importar en un `node --test`. Para
    esos hay un escaneo del código fuente: **~170 llamadas**, toda ruta que
    el frontend nombra tiene que existir en el contrato con ese método, en
    14 ms. Caza lo que antes no cazaba nada: un endpoint renombrado en el
    backend rompe veinte pantallas y el diff de `openapi.json` no sabe quién
    lo llamaba.
  El único caso irresoluble estáticamente —
  `marketing/campanas/${id}/${paso}`, cuyo último segmento toma tres valores
  literales— se declara con sus tres valores y se verifican todos, en vez de
  quedar como agujero. Y el test exige un piso de llamadas encontradas: si
  cambia la forma de llamar a la API, el escaneo daría cero y pasaría por
  vacío. Cinco mutaciones, cinco rojos.
- **Test de contrato cliente↔servidor** (2026-08-06,
  `frontend/lib/contrato.test.ts`), el que la estrategia de pruebas
  declaraba prioridad por encima de más e2e. 58 casos en ~250 ms, sin
  servidores. Dos capas, y la primera pesa más:
  1. **El tipo.** Los cinco cuerpos de request del PDV viajaban como
     `Record<string, unknown>` — sin contrato del lado del cliente, que es
     por donde entró el bug de ADR-025. Tipados desde `openapi.json`, `tsc`
     los verifica en cada punto de llamada y ya corre en CI.
  2. **El test.** Por cada operación de `lib/pdv.ts`, con `fetch`
     intervenido: que la ruta y el método existan en el contrato, que el
     cuerpo valide contra su `requestBody`, y —alimentando al cliente con
     una respuesta **generada desde el contrato**— que la sepa leer. Eso
     último caza ADR-026: el cliente recibe `{items, total, …}` de verdad y
     tiene que devolver un array.
  Verificado **por mutación**: reintroducidos los dos bugs históricos más un
  endpoint renombrado, los tres fallan nombrando operación y campo. Un test
  verde que nadie vio ponerse rojo no prueba nada.
- **`npm test` entra a CI** (2026-08-06). Los 72 casos de unidad del
  frontend **nunca habían corrido en CI**: el job hacía solo `lint` y
  `build`.
- **Pruebas de pantalla de sesión y del gate de módulo por permiso**
  (2026-08-06, `frontend/e2e/sesion.spec.ts`). Con esto quedan cubiertos los
  **tres** casos que `docs/engineering/testing-strategy.md` da por
  justificados para un e2e; el documento es también el techo, no una lista
  de deseos. Siete casos en total:
  - Una ruta protegida sin sesión manda al login.
  - El login deja el token en cookie **httpOnly** —el atributo se afirma
    explícitamente porque no se ve en ninguna pantalla y se rompe en
    silencio; un token legible por `document.cookie` lo roba cualquier XSS—
    y el logout la mata de verdad: la ruta protegida vuelve a rebotar, no
    solo cambia la pantalla.
  - **El cajero no ve Catálogo ni entrando por `/catalogo/productos`**, y el
    admin sí. Se prueba de a pares a propósito: un gate que esconde el
    módulo para *todos* pasaría por bueno con la mitad de la prueba. Por URL
    directa y no solo por el home, porque el filtro del home es UX — lo que
    decide es el `layout.tsx` (ADR-013 + enmienda 2026-08-03).
  - **Un rechazo del servidor deja el formulario de apertura abierto con lo
    tecleado.** Recontar el cajón entero porque alguien erró seis dígitos
    del PIN es la clase de fricción que termina en un conteo inventado, y
    ese conteo es la evidencia sobre la que se calcula el descuadre del
    turno.
  Sigue faltando —y sigue siendo la prioridad— el test de contrato
  cliente↔servidor: estos e2e cubren arranque y candados, no el desacuerdo
  de forma que originó los dos bugs de ADR-025/026.
- **`cajero_e2e` en el seeder de e2e** (2026-08-06): el usuario con menos
  permisos que igual opera una pantalla. Existe para probar lo contrario que
  el encargado — qué **no** se ve.
- **Job `e2e` en `ci.yml`** (2026-08-06): corre `npm run test:e2e` sobre
  chromium y sube `test-results/` como artefacto cuando falla — sin el trace
  y las capturas, un rojo en CI es una línea de texto. Es el único job que
  comprueba que cliente y servidor estén de acuerdo: los dos bugs que
  motivaron la suite pasaban `pytest` y `npm run build` sin despeinarse.
- **Seis diagramas BPMN de las áreas nuevas** (2026-08-05), con sus PROC
  registrados en el maestro y su narrativa en `workflows.md`. El enfoque
  vigente era *primero SOP, luego BPMN*; los SOPs ya estaban estables.
  `PROC-RRH-001` incorporación de personal · `PROC-RRH-002` contingencia de
  personal faltante (RN-RRHH-011) · `PROC-RRH-003` tardanza o falta del
  encargado (RN-RRHH-010) · `PROC-CMP-001 v2.0` compras con sus tres
  caminos · `PROC-COM-003` definición y revisión de precio ·
  `PROC-INV-001 v0.2` abastecimiento de locales, que además pasa de
  Borrador a **Vigente** porque el ciclo está implementado (ADR-020) y el
  traslado ya emite guía (ADR-027).
- **Entidades de Comercial-estrategia y RRHH-proceso en `data-model.md`**
  (2026-08-05): `meta_venta` + `meta_venta_seguimiento`, `hallazgo_mercado`,
  `entrevista`, `plan_induccion` + `plan_induccion_item`,
  `evaluacion_periodo_prueba`, `evaluacion_desempeno` y `capacitacion` +
  `capacitacion_asistente`. Especificadas, sin implementar.
- **Valores propuestos para los 13 `parametro_empresa`** (2026-08-05) con
  su sustento en `docs/gerencia/propuesta-parametros-operativos.md`,
  cargados en estado `propuesto` a la espera de Gerencia
  (`python -m src.seeders.parametros`).

- **Guía de remisión de traslados** (2026-08-05, ADR-027, migración
  `a4c8f21e6b09`). Charlie's Pizzas mueve mercadería entre el almacén
  central, CH1 y CH2 todos los días y hasta hoy ese traslado viajaba sin el
  documento que lo sustenta. `guia_remision` + `guia_remision_item` cuelgan
  de `transferencia`, en `inventory` y no en un módulo `logistics` ni en
  `sales`: lo que la guía declara es un traslado, y el traslado es un hecho
  de inventario (RN-GDR-002, la emite el almacén).
  Las líneas **se derivan** de `transferencia_item`, agrupadas por SKU:
  RN-TRP-002 exige que lo transportado coincida exactamente con lo
  declarado, y un formulario de ítems aparte es justamente la forma de que
  no coincidan. Se teclea solo lo que el sistema no puede saber —chofer,
  vehículo, peso bruto, fecha de inicio del viaje—. Un traslado, una guía
  (emisión idempotente) y correlativo por `(empresa, serie)` calculado al
  emitir, no reservado antes. Envío a SUNAT asíncrono vía Celery
  (`POST /despatch/send`): la guía impresa es la que viaja, y un rechazo se
  corrige y reemite en vez de detener el camión. Permiso nuevo
  `inventory.emitir_guia` en el rol `almacenero`; 14 tests.
- **Pantalla de caja en contabilidad** (2026-08-05): turnos cerrados con su
  descuadre y el tramo de la cadena de custodia, entrega de custodia firmada
  con PIN, reapertura de un cierre con motivo (RN-MDP-005) e inventario de
  terminales de tarjeta. Nuevo `GET /accounting/cajas/turnos` (turno +
  cierre + custodia en una consulta, no un N+1 por turno) y
  `pos_verificados` en `CajaAbiertaOut`, que es lo que le dice al cierre a
  qué terminales pedirles su reporte de lote.
- **Campana de notificaciones en la barra superior** (2026-08-05): los
  endpoints existían desde el 2026-08-04 sin ninguna pantalla que los
  usara. Muestra solo lo no leído y marca leída al abrir la fila, no al
  abrir el panel — mirar de reojo no es haberse enterado.
- **`GET /sales/ventas` con rango de fechas** (2026-08-05): `desde`/`hasta`
  inclusivos, sucursal opcional dentro del alcance del tenant y filtro por
  punto de venta. Un solo endpoint para la jornada del PDV y el histórico
  del back-office.

### Changed

- **Paginación real en los listados operativos** (2026-08-04, ADR-026).
  Ningún endpoint paginaba: cada listado devolvía la tabla entera y la guía
  de API lo documentaba honestamente como deuda. Ahora los **18 listados
  que crecen con la operación** —ventas del día, artículos, stock,
  movimientos, solicitudes, transferencias, proveedores, órdenes de compra,
  asientos, pagos a proveedor, trabajadores, postulantes, campañas, leads,
  personas, usuarios y notificaciones— devuelven
  `{items, total, page, page_size}` con `page`/`page_size` (defecto 50,
  máximo 200: sin techo, `page_size=1000000` es una forma cómoda de tumbar
  la API con una sola petición autenticada).
  **Los catálogos de configuración siguen devolviendo un array plano**
  (roles, permisos, divisas, unidades de medida, medios de pago,
  sucursales, mesas, plan de cuentas…). La frontera no es cuántas filas
  tiene la tabla hoy sino qué las crea: si nacen de la operación, crecen
  solas y se paginan; si las escribe alguien configurando el sistema, son
  decenas y se consumen enteras para llenar un `<select>`.
  El corte va **en la base** (`LIMIT`/`OFFSET` + `COUNT`), no trayendo todo
  y cortando en Python: cada repositorio expone ahora `q_list()` —la
  consulta sin ejecutar— junto a su `list()` de siempre, así que solo
  cambia el router.
  **Cambio de contrato, no compatible hacia atrás**: frontend migrado
  (5 fetchers), `openapi.json` regenerado y `api-guidelines.md` actualizado
  con los dos formatos. Todavía sin controles de paginación en pantalla —
  las 4 tablas existentes muestran la primera página. 9 tests en
  `tests/test_paginacion.py`.

### Added

- **El cierre de caja cuadra tarjetas** (2026-08-04, RN-POS-004). Hasta
  ahora el cierre verificaba solo el cajón: la mitad del turno se cerraba a
  ojo y un cobro mal pasado en el POS aparecía recién en la liquidación del
  operador, semanas después. Ahora exige el **reporte de lote de cada
  terminal que abrió operativo** —uno averiado no cobró nada, así que no se
  le pide— y contrasta la suma contra lo cobrado con tarjeta en el turno.
  `descuadre_monto` sigue siendo el del efectivo (es la plata que alguien
  responde) y el de tarjetas viaja aparte; **cualquiera de los dos deja el
  cierre irregular**, porque cuadrar el cajón no dice nada de lo que pasó
  por los terminales. Un local sin POS verificados no tiene nada que cuadrar
  y el cierre no le pide nada.

- **Descarga de PDF, XML y CDR** (2026-08-04,
  `GET /sales/comprobantes/{id}/descargar/{formato}`). El PDF que se entrega
  al cliente, y el **XML firmado** y el **CDR** que son el respaldo ante
  SUNAT y hay que poder recuperar años después. Se piden a Factiliza en el
  momento y **no se archivan**: su copia es la buena mientras el proveedor
  siga activo, y guardar una propia agregaría un archivo que puede quedar
  desincronizado sin ganar nada. Los bytes vuelven sin tocar — reescribir un
  XML firmado lo invalida. Solo de un comprobante aceptado: antes de eso no
  hay XML ni CDR que bajar.

- **Pantalla de nota de crédito** (2026-08-04, en la jornada de Ventas). El
  diálogo pide el motivo del catálogo 09 y **avisa cuando el elegido corrige
  el documento en vez de la operación**; permite acreditar todo o elegir
  líneas con su cantidad (las líneas se piden al abrir, no al pintar la
  jornada: traerlas por cada venta del día sería un viaje por fila para algo
  que casi nunca se usa); y la casilla de devolver el insumo viene marcada
  salvo en los motivos de corrección, que no tocan inventario. La fila
  ofrece **anular o acreditar, nunca las dos**: antes de cobrar se anula,
  después solo queda la nota.

- **Nota de crédito** (2026-08-04, RN-CPP-009, migración `c2f7a91b4e08`).
  Cierra el hueco funcional más grande que quedaba: **una venta ya cobrada
  no tenía forma de corregirse**. `anular_venta` seguía cubriendo solo la
  orden sin pagar y mandaba al resto a un slice que no existía.
  Ahora `POST /sales/comprobantes/{id}/nota-credito` acredita un comprobante
  aceptado, **total o parcial por ítem**, con motivo del catálogo 09 de
  SUNAT y una sola vez por documento. Numera en **serie propia** por punto
  de venta: mezclarla con la de la boleta o factura es rechazo seguro.
  Tres decisiones quedaron explícitas porque no tienen respuesta universal:
  **`repone_stock` lo declara quien acredita** —un plato devuelto en cocina
  rara vez devuelve el insumo, y corregir el RUC de una factura no toca el
  inventario—; **el motivo decide si la venta muere** —anulación (01) y
  devolución (06/07) la dan de baja; error en el RUC (02) o en la
  descripción (03) **no**, porque la operación ocurrió y solo el papel
  estaba mal, así que el comprobante queda liberado para reemitir el
  corregido—; y **una nota rechazada por SUNAT no corrige nada**: queda
  registrada con su motivo y la venta sigue igual.
  Las notas parciales sucesivas cuentan contra lo que queda por acreditar y
  no contra lo vendido, que es lo que impide devolver dos veces el mismo
  plato. Permiso propio `sales.emitir_nota_credito` (supervisor): acreditar
  devuelve dinero y no es acto de cajero. 14 tests.

- **Chequeo de deriva de esquema** (2026-08-04, `src/core/esquema.py`).
  Nace de un fallo real: las dos bases de desarrollo tenían
  `alembic_version` en una revisión **posterior** a la que crea
  `decision_gerencial`, sin que la tabla existiera. `alembic current` decía
  "al día", CI estaba verde —`alembic check` compara modelo contra
  migraciones sobre una base **limpia**, no contra la base real— y
  `GET /decisiones-gerenciales` respondía 500. Se descubrió abriendo la
  pantalla.
  Ahora `python -m src.core.esquema` responde dos preguntas que fallan
  distinto: **qué tablas del modelo no están en la base** (mira el estado
  real, atrapa la migración marcada y no corrida, la aplicada a medias y la
  base restaurada de un backup viejo) y **si la revisión coincide con la
  cabeza del repo** (mira el marcador, atrapa el despliegue sin `upgrade`
  aunque todas las tablas existan). El mismo chequeo corre al arrancar el
  servidor: en producción **aborta**, en desarrollo avisa — mismo criterio
  que la validación de configuración.
  Se compara solo existencia de tablas, no columnas ni tipos: el grueso del
  daño con muy poco código y sin los falsos positivos que da comparar tipos
  por dialecto. 8 tests.

- **Pantallas de Gerencia y Ventas back-office** (2026-08-04). Con estas
  **ningún tile del home queda en 404**: los doce módulos del shell tienen
  pantalla.
  **Gerencia**: bandeja de parámetros operativos con las tres salidas de
  ADR-014 (aprobar, aprobar modificando el valor, rechazar con motivo), y el
  formulario de propuesta obliga a declarar **qué clase de magnitud** es el
  valor —monto con divisa, cantidad con unidad de medida, o adimensional—
  que es justo lo que RN-GER-010 exige. Actas de decisión gerencial, donde
  las condiciones aparecen y se vuelven obligatorias solo al elegir
  "aprobado con condiciones", y firmar exige `gerencia.decidir`: el área
  ejecutora lee pero no firma (RN-GER-005). Divisas con sus decimales.
  **Ventas back-office**: la jornada de una sucursal por fecha y estado, con
  totales y el comprobante de cada venta, más sus dos acciones reales —
  reintentar la emisión que SUNAT rechazó (con el detalle del rechazo y los
  intentos) y anular una orden que nunca se cobró. Los filtros viven en la
  URL, no en estado del cliente: la jornada de una sucursal en una fecha es
  una dirección que se comparte y se recarga.
  El tile del home de Ventas pasó a apuntar al back-office y el PDV se abre
  desde su sidebar; antes el tile iba directo al PDV y lo administrativo no
  tenía puerta de entrada.

- **Pantallas de Producción y Marketing** (2026-08-04). Otros dos tiles del
  home que llevaban a un 404.
  **Producción**: órdenes con su ciclo real (crear → registrar el consumo
  que la cocina sacó de verdad → cerrar con el control de calidad). La
  columna de acciones muestra **solo el paso que aplica** al estado de la
  orden; ofrecer el otro solo invita al 409. El diálogo de cierre cambia
  según el resultado: cantidad producida si es conforme, evidencia de
  destrucción si se desecha.
  **Marketing**: campañas con el ciclo brief → aprobada → en curso →
  cerrada, donde la tabla dice **qué campo del brief falta** en vez de
  fallar recién al aprobar, y el botón de aprobar aparece solo si el usuario
  tiene el permiso — quien redacta el brief no lo aprueba (RN-MKT-003), así
  que ofrecérselo a todos sería prometer un 403. Contenido con el calendario
  de piezas y sus dos validaciones de marca como etiquetas que se tocan
  (RN-MKT-001/002); publicar queda deshabilitado hasta tener las dos.
  **Tres endpoints de lectura que no existían** y que estas pantallas
  necesitaban: `GET /production/ordenes` (solo se podía ver una orden
  sabiendo su id — la cocina no tenía forma de mirar su propia jornada),
  `GET /marketing/piezas` (sin él no hay calendario de contenido) y
  `GET /api/v1/marcas` en `users`, porque el de `sales` exige `sales.leer` y
  pedirle eso a un usuario de marketing para llenar un `<select>` sería
  abrirle la carta entera. Los dos primeros paginados (ADR-026); el tercero
  plano, que es lo que corresponde a un catálogo de organización.

- **Pantallas de Usuarios y Contabilidad** (2026-08-04). Dos de los siete
  tiles del home que llevaban a un 404.
  **Usuarios**: cuentas con sus roles editables en la misma fila (asignar y
  quitar es lo que más se hace en esa pantalla; un modal por cambio sería un
  clic de más cada vez), alta de cuenta, activar/desactivar y filtro por
  rol. La subpantalla de **Roles** es un acordeón y no una tabla —un rol
  tiene decenas de permisos y una celda con 30 etiquetas no se lee— con el
  selector de permisos agrupado por módulo, porque el catálogo pasa los 90.
  Requirió **dos endpoints de lectura que no existían**: `GET
  /users/{id}/roles` (el token trae los nombres de rol pero no sus ids, así
  que desde la UI no se podía desasignar nada) y `GET /roles/{id}/permisos`
  (asignar un rol sin ver qué habilita es justo el error que se quiere
  evitar).
  **Contabilidad**: asientos (listado, alta manual con líneas dinámicas y
  **cuadre debe/haber en vivo** —RN-CTB-001, el error típico es un monto de
  más y verlo antes de enviar ahorra el viaje— y anulación por asiento
  inverso), periodos contables (abrir y cerrar: sin un periodo abierto el
  primer asiento falla, y abrirlo era exclusivamente por API — la pantalla
  de asientos no se podía estrenar sin curl), plan de cuentas (listado y
  alta), pagos a proveedor (cola
  filtrada a pendientes, ejecutar con medio de pago y constancia, rechazar)
  y caja (turnos abiertos con su efectivo esperado, leídos del reporte
  `estado_caja` del catálogo en vez de recalcular el mismo número por
  segunda vez).
  De paso, `apiFetch` dejó de reventar con las respuestas **204 sin cuerpo**
  (asignar/quitar rol, marcar notificación leída): pedirle `.json()` a un
  204 falla sobre una llamada que salió bien.

- **Ciclo de caja completo** (2026-08-04, ADR-025, migración
  `f3a1c62d90b4`). El slice mínimo registraba el ciclo; ahora lo verifica.
  Cuatro cambios que van juntos porque solos no sirven:
  **(1) No se cobra sin caja abierta.** `POST /sales/ventas/{id}/pagos`
  responde 409 si el punto de venta no tiene turno, preguntando por el
  contrato público `accounting.hay_caja_abierta` (`sales` nunca ve
  `AperturaCaja`). Vale para todo medio de pago, no solo efectivo. La plata
  cobrada fuera de un turno no la espera ningún cierre: el faltante recién
  aparecía en contabilidad, sin responsable posible. Única excepción, el
  replay del push del hub (ADR-009): el cobro ya ocurrió en la sucursal con
  su caja abierta.
  **(2) El monto sale del conteo, no del teclado.** Apertura y cierre
  reciben el desglose por billete y moneda (RN-POS-003/007) validado contra
  las denominaciones de curso legal, y el servidor suma. En la apertura, la
  diferencia entre lo que el encargado declara entregar y lo que el cajero
  cuenta **se calcula** y no bloquea abrir (RN-POS-011): el local abre en
  su horario y el problema queda reportado.
  **(3) Cada relevo lo firma quien recibe, con su PIN** (RN-MDP-002),
  reusando la elevación de `POST /auth/autorizar` con el permiso nuevo
  `accounting.caja_relevar` — el identificador del encargado sale del
  token, nunca del cuerpo, que sería una firma falsificable. Nadie se
  releva a sí mismo. `custodia_efectivo` pasa a ser máquina de estados real
  (`en_caja → en_supervisor → en_contabilidad → disponible`, con el atajo a
  `disponible` de RN-MDP-006 cuando el efectivo se queda en la caja fuerte
  del local).
  **(4) Un cierre con faltante se corrige, no se reescribe.**
  `POST /cajas/cierres/{id}/reabrir` lo devuelve a `en_proceso` guardando
  motivo, autorizador y descuadre anterior en `cierre_caja.correcciones`
  (RN-MDP-005); volver a cerrar recalcula **el mismo** registro. Solo
  mientras el efectivo siga en el local: una vez en contabilidad, corregir
  es un asiento, no un recuento.
  Suma `pos_tarjeta` — inventario de terminales con serie y código de
  comercio (RN-POS-010), donde el de emergencia es una fila con
  `sucursal_id` en NULL (RN-POS-009) que el listado por sucursal siempre
  incluye — y la verificación de POS al abrir, que marca el averiado y
  publica `accounting.pos_averiado_reportado` sin bloquear la apertura.
  De paso, `efectivo_esperado` del reporte de caja y el arqueo pasan a
  descontar `movimiento_caja`: eran un techo, no un arqueo.
  Permisos nuevos: `accounting.caja_relevar`, `accounting.caja_reabrir`,
  `accounting.pos_administrar`. 17 tests en `tests/test_caja_ciclo.py`.

- **Tablero de reportes con catálogo cerrado** (2026-08-04, ADR-024,
  migración `998e335369a1`). El dashboard deja de ser tres tarjetas fijas:
  ahora el usuario arma sus vistas, elige rango (preset o personalizado),
  filtra sucursales por checkbox, ajusta ancho (1-4/4) y alto de cada
  tarjeta, cambia entre tabla/barras/líneas y **guarda la disposición**
  (`tablero`, personal por usuario). Cinco reportes iniciales:
  `ventas_por_dia`, `ventas_por_sucursal`, `top_productos`,
  `compras_por_proveedor` y `solicitudes_por_articulo`.
  `GET /reportes`, `POST /reportes/{codigo}/datos`, CRUD de `/tableros`.
  **No hay constructor de consultas a propósito**: el cliente manda un
  `codigo` del catálogo y filtros tipados, nunca tablas ni columnas —
  evita a la vez la superficie de inyección y la fuga de RBAC que un
  armador genérico abriría sobre todo el ERP. Cada reporte declara el
  permiso de su módulo dueño, así que un `comprador` ve compras y no
  ventas. Frontend en `frontend/components/reportes/` con Tailwind y
  gráficos sin librería (barras = divs con ancho porcentual, serie =
  `<polyline>` SVG). 21 tests y verificación end-to-end en navegador.

- **Stack de observabilidad: GlitchTip + Loki + Alloy + Grafana**
  (2026-08-04, `docker-compose.observabilidad.yml`). Va en un compose
  **aparte** a propósito: son ocho contenedores que no son el negocio, y
  poder pararlos sin tocar el del ERP es justo lo que se quiere el día que el
  VPS ande corto de memoria. GlitchTip habla el protocolo de Sentry, así que
  `src/core/sentry.py` no cambió una línea (ADR-006). Guía de puesta en
  marcha en `docs/engineering/observabilidad.md`.

- **`worker` y `beat` quedaban `unhealthy` para siempre** (2026-08-04).
  Heredaban el `HEALTHCHECK` del Dockerfile, que pega a
  `http://127.0.0.1:8000/health` — correcto para la API, pero ninguno de los
  dos levanta servidor HTTP. Más que cosmético: un
  `depends_on: service_healthy` o una política de reinicio por salud los
  habría reiniciado en bucle. Se deshabilita en ambos; la salud real del
  worker la da su latido (`/health/ready`), que es el mecanismo que existe
  para eso. Encontrado al levantar el stack de verdad.

- **`beat` faltaba en docker-compose** (2026-08-04). Se agregaron las tareas
  periódicas en el turno anterior pero no el servicio que las corre: sin él
  ni el barrido de pedidos demorados ni el latido del worker se ejecutaban
  nunca. Agregado en dev y en producción, con la advertencia de **una sola
  instancia por despliegue** — dos programadores encolarían cada tarea dos
  veces.

- **La alerta de cocina le llega al encargado de turno** (2026-08-04,
  migración `7fda1eb759f7`). Entidad `notificacion` (bandeja por usuario,
  transversal) + listener de `users` sobre `sales.pedido_demorado`.
  Quién es el encargado de turno **no necesitó una entidad nueva**: sale del
  `relevo_encargado_id` de la caja abierta, que ya registra quién está a
  cargo del local (RN-MDP-002). Sin caja abierta, el aviso cae en los
  supervisores de la sucursal — un aviso sin destinatario es un aviso
  perdido. La regla vive en **una sola función**
  (`notificaciones.destinatarios_de_sucursal`) para que hacerla configurable
  después no toque ni el listener ni la entidad ni la pantalla.
  `GET /notificaciones`, `POST /notificaciones/{id}/leer`,
  `POST /notificaciones/leer-todas`.

- **Salud del worker: se pregunta en vez de inferirse** (2026-08-04). Una
  tarea de beat escribe un latido en Redis con TTL y `/health/ready` lo lee.
  Antes se deducía de la profundidad de la cola, que solo delata al worker
  cuando hay trabajo: con la cola vacía —la mayor parte del día en un
  restaurante— un worker muerto y uno ocioso se veían idénticos.

- **El flujo `auditoria` del log estructurado dejó de estar vacío**
  (2026-08-04): `AuditLogRepo.registrar` emite además al logger
  `provecho.auditoria`, solo metadatos. La tabla sigue siendo el rastro
  legal; el log es lo que un colector externo puede vigilar en vivo.

- **Alerta de pedido demorado en cocina** (2026-08-04, migración
  `d4e21b0c13d0`). Al confirmarse una venta, un listener agenda una revisión
  para 15 minutos después; si el pedido sigue en cocina, se registra
  `alerta_pedido` y se publica `sales.pedido_demorado`. Un barrido de Celery
  beat cada 5 minutos repasa lo que siga abierto: la tarea puntual sola se
  pierde si el worker estuvo caído, y para una alerta el fallo que importa
  es no avisar. Los dos caminos convergen en la misma fila sin duplicar
  (`UNIQUE (venta_id, minutos_umbral)` + pre-chequeo + SAVEPOINT). El umbral
  lo fija Gerencia por empresa (`parametro_empresa`) y **queda congelado en
  la alerta**: subirlo después no reescribe lo que ya fue demora.

- **Dos reportes nuevos en el tablero**: `pedidos_demorados` y
  `estado_caja` — este último con horas sin cerrar y efectivo esperado, no
  solo el conteo que ya daba el KPI. Diez reportes en total.

- **ADR-013 instalado, tres semanas después de decidirse** (2026-08-04):
  shadcn/ui sobre **Base UI** (cero paquetes de Radix, como exigía la
  decisión) más Recharts, dnd-kit, react-day-picker y sonner. Obligó a subir
  a **Tailwind v4** — el registro de Base UI solo existe en shadcn v4, que
  no corre sobre v3. `tailwind.config.ts` desaparece: el tema vive en
  `globals.css`, con los roles semánticos de shadcn apuntando a la paleta
  Provecho y no al gris del preset.

- **El tablero se comparte, se exporta y se reordena** (2026-08-04,
  ADR-024 Addendum, migración `5e1c7775f6ca`). Cierra la deuda declarada el
  mismo día:
  - **Compartir por rol** (`tablero.rol_id`): NULL = privado; con rol lo ve
    en solo lectura quien lo tenga, lo edita el dueño. Por rol y no por
    lista de personas porque se administra solo — quien cesa deja de verlo
    al perder el rol, sin que nadie lo saque a mano de cada tablero.
    Compartir **no expone datos**: cada tarjeta revalida el permiso de su
    módulo, así que se comparte la disposición, no el contenido.
  - **Exportación a CSV** por tarjeta, armada en el cliente (los datos ya
    están ahí). RFC 4180, BOM UTF-8 para Excel y montos crudos —
    `S/ 1,234.50` no lo suma ninguna hoja de cálculo.
  - **Reordenar por arrastre** con HTML5 nativo, sin librería.
  - **Caché de 30 s** por (reporte + filtros): reordenar dentro de la
    ventana cuesta 0 peticiones.
  - **Tres reportes más**: `ventas_por_hora` (en hora del negocio: se
    agrupa en UTC y se reetiqueta con `fechas.desfase_horas()`),
    `ventas_por_trabajador` (primer contrato público de `rrhh` — nombre y
    cargo, nada más) y `margen_por_producto`, donde un producto **sin
    receta muestra costo y margen vacíos, nunca cero**: cero se leería como
    100 % de margen sobre un dato que falta.

- **Contrato público `inventory` → `purchases`** (2026-08-04):
  `solicitudes_resumen_para_negociacion` / `GET /inventory/solicitudes/resumen`
  (permiso `inventory.leer_solicitudes_externas`, sembrado en `comprador`) —
  qué artículo pide más cada almacén, para negociar volumen con
  proveedores. Suma lo **solicitado** (no lo aprobado ni lo despachado: es
  la demanda real) y excluye las canceladas.

- **`GET /api/v1/sucursales`** (2026-08-04): catálogo de referencia con el
  mismo criterio que `/almacenes` — cualquier autenticado que tenga que
  elegir una sucursal lo necesita, escopado por tenant. Lo pedía el filtro
  de sucursales del tablero y no existía.

- **`.github/dependabot.yml`** (2026-08-04): pip, npm, github-actions y
  docker. Complementa a `pip-audit`, que solo avisa de una CVE publicada —
  Dependabot abre el PR que la cierra.

### Fixed

- **El timestamp del log no era RFC3339** (2026-08-04,
  `src/core/logging_config.py`). `ts` salía como `2026-08-04T12:35:19-0500`:
  offset **sin los dos puntos**, que es ISO 8601 pero no RFC3339. El
  colector no lo parsea y lo descarta en silencio, estampando la hora de
  ingesta — así que un hub de sucursal que sube sus logs atrasados tras un
  corte los mostraría como recién ocurridos, que es justo cuando la hora
  real importa. Ahora se emite en RFC3339 UTC, por la misma regla que ya
  fijaba `shared/fechas.py`: un instante va en UTC. Test que congela el
  contrato: `test_el_timestamp_es_rfc3339_en_utc`.

- **Encolar una tarea podía colgar el request que la encola** (2026-08-04,
  `src/core/celery_app.py`). Lo destapó el listener de alertas: al encolar
  en cada venta confirmada, el suite de tests pasó de ~5 a **63 minutos**.
  La causa no era el listener sino Celery: `apply_async` abre la conexión al
  broker **dentro de la llamada** y con reintentos, así que con Redis
  inalcanzable (el `.env` local apunta a `redis://redis:6379`, el hostname
  de Docker) cada encolado pagaba segundos de DNS fallido. En producción eso
  es un cajero mirando una pantalla congelada cuando Redis se cae. Ahora el
  broker tiene timeouts de 1 s, no reintenta al arrancar, y el encolado de
  la alerta usa `retry=False`: o entra al instante o no entra, y el barrido
  periódico lo recupera. Los tests usan el transporte en memoria de kombu
  (`memory://`), con el mismo criterio que ya se aplicaba al token de
  Factiliza: ningún test habla con un servicio externo real.

### Security

- **Content-Security-Policy en la API y en el frontend** (2026-08-04). La
  API devuelve JSON y no debe cargar nada, así que va la más restrictiva
  posible (`default-src 'none'` + `frame-ancestors`/`base-uri`/`form-action`
  en `'none'`), lo que además vuelve inerte cualquier respuesta que
  llegara a interpretarse como HTML; `/docs` se exceptúa porque Swagger UI
  carga de un CDN y en producción no existe. El frontend usa **nonce por
  request** con `'strict-dynamic'` (`frontend/middleware.ts`): Next inyecta
  scripts inline propios y sin nonce habría que admitir `'unsafe-inline'`
  en `script-src`, que anularía la protección contra XSS. `style-src`
  mantiene `'unsafe-inline'` — concesión conocida del patrón, no afecta al
  vector de ejecución de script.

### Changed

- **Las colas de preparación ya no esconden el ítem recién tachado**
  (2026-08-03, `kds.cola_pantalla`): una pantalla de `preparacion`
  devolvía solo los ítems `pendiente`/`en_preparacion` de sus categorías,
  así que marcar un ítem lo hacía **desaparecer** de la tarjeta — lo
  contrario de lo que necesita la cocina (y de lo que hace Odoo, donde la
  línea queda tachada). Ahora la pantalla devuelve todos sus ítems con su
  estado, y el pedido sale de esa cola cuando la estación terminó todo lo
  suyo. Se detectó verificando el KDS end-to-end contra el stack real.
  Test nuevo:
  `test_item_tachado_sigue_visible_hasta_terminar_la_estacion`.

- **Cliente HTTP del navegador extraído a `frontend/lib/cliente-api.ts`**
  (2026-08-03): el `fetch` contra `/api/proxy`, el parseo de `detail` y
  `claveIdempotencia` vivían dentro de `lib/pdv.ts`; con el KDS pasaron a
  tener dos consumidores. `lib/pdv.ts` los re-exporta, ningún import
  existente cambia.

### Fixed

- **El calendario se corría un día pasadas las 19:00 hora Perú** (2026-08-03,
  `src/shared/fechas.py`). Estaba anotado en el ROADMAP como una falla de los
  tests de `conteos`; al ir a arreglarla resultó ser de la aplicación. El ERP
  tenía tres relojes y los mezclaba: la base escribe sus timestamps en **UTC**
  (`func.now()`), el proceso corre con la zona del sistema —**UTC dentro de
  Docker**— y el negocio abre y cierra en **America/Lima**. `conteos` derivaba
  "hoy" con `date.today()` y lo comparaba contra `cerrado_at`, en UTC: un
  conteo cerrado el lunes a las 20:00 contaba como martes y el programa de
  conteo cíclico se desfasaba entero.
  - El mismo patrón estaba en otros 10 archivos, varios con consecuencia de
    caja: correlativo de venta por día, resolución de precio vigente (una
    promoción que vence "hoy" dejaba de aplicar cinco horas antes),
    vencimiento de lotes y FEFO, fecha del asiento contable y del pago a
    proveedor, y el día del mapa de mesas. Todos derivan la fecha de
    calendario con `fechas.hoy()`; los instantes siguen guardándose en UTC,
    que es lo correcto.
  - La zona es configuración (`settings.zona_horaria`), no una constante: el
    grupo opera en Perú hoy, pero el dato no es del código.
  - Los 4 casos de `test_conteos` que fallaban pasaron **sin tocar un solo
    test** — la prueba de que el error nunca estuvo ahí.
    `tests/test_fechas_negocio.py` congela la regla y falla si algún módulo
    vuelve a usar `date.today()`.
- **`npm audit` del frontend en cero** (2026-08-03). Eran 4 altas:
  `brace-expansion` (la resolvió `npm audit fix`) y tres colgando de `next`.
  El JSON del audit deja claro que `next` **no** estaba marcado por CVEs
  propias — su `via` es literalmente `["postcss","sharp"]`: todo venía de
  que Next pinea `postcss@8.4.31` y arrastra `sharp<0.35`. Subir de major
  no arreglaba nada (**Next 16 pinea el mismo postcss**) y
  `npm audit fix --force` proponía `next@9.3.3`, un downgrade de 6 majors.
  Se fuerzan las versiones parcheadas con `overrides` en
  `frontend/package.json`, y el rango de `next` sube a `^15.5.22` — que ya
  era la versión instalada; el `^15.3.0` viejo daba la impresión falsa de
  estar atrasado. `tsc`, `next lint` y `next build` limpios después.

- **`postulante.estado` no entraba en su propia columna** (2026-08-02,
  migración `e4a2f9c17b3d`). La columna nació como
  `Enum('en_proceso','rechazado','contratado')` → VARCHAR(10), y el slice de
  contratación (`a7f2c81e4b95`) la pasó a nueve estados migrando los datos
  pero **sin ensanchar el tipo**. En Postgres, mover un postulante a
  `preseleccionado` (15 caracteres) u `oferta_enviada` (14) fallaba con
  `value too long for type character varying(10)`. Los tests no lo cazaron
  porque SQLite ignora el largo de VARCHAR; lo cazó el job `migraciones` de
  CI (`alembic check`), que llevaba en rojo desde ese slice. De paso se da de
  baja el `UNIQUE` redundante de `convocatoria.token_publico`: el modelo
  declara `unique=True, index=True`, que SQLAlchemy resuelve como **un**
  índice único, y la migración además creaba una constraint aparte.

### Added

- **Variantes de producto, grupos de opciones y recetas** (2026-08-03,
  ADR-023, migración `b6d1e83f47ac`). Una Pizza
  Peperoni se vende en Personal, Mediana y Familiar: **tres productos hijos**
  (`producto_comercial.producto_padre_id`) con receta y **precio completo**
  propios —no un recargo sobre un precio base—, porque cada tamaño lleva
  otra receta de verdad. El padre agrupa y no se vende: `receta_id` pasa a
  nullable, `fijar_precio` lo rechaza y venderlo devuelve 409 (RN-COM-022).
  Se eligió esto sobre atributos con recargo porque precio server-side,
  margen por tamaño, descuento de insumos, KDS y réplica al hub siguen
  funcionando sin escribir una línea.
  - **Grupos de opciones** (`producto_opcion_grupo`, RN-COM-023): "Salsas:
    elige 1" y "Toppings: hasta 3, opcional" son el mismo mecanismo con
    distinto mínimo. `minimo >= 1` **es** ser obligatorio — no hay columna
    `obligatorio`, sería el mismo dato dos veces. La regla se hace cumplir al
    confirmar la venta y no solo en el PDV, porque el kiosko entra por el
    mismo endpoint; el replay del hub se exceptúa (ADR-009): una venta ya
    cobrada no se rechaza por una regla que cambió durante el corte.
  - **Aritmética en la cantidad de receta** (RN-COM-024): se teclea "1000/3"
    y se guarda **el resultado**, redondeado a los decimales de la unidad de
    medida del insumo, más la expresión al lado para poder reeditarla. La
    evalúa el servidor (`shared/aritmetica.py`, `ast` con lista blanca de
    nodos, nunca `eval`): si el cliente mandara resultado y expresión por
    separado, nada garantizaría que uno corresponda al otro. Suma
    **duplicar** una receta con sufijo "(copy)" y **escalar por factor**,
    que redondea cada línea con *su propia* unidad — 1.5 bollos de masa son
    2, mientras el queso en gramos sí admite el decimal.
  - **Nombres en formato título** (`shared/texto.py` + `frontend/lib/texto.ts`):
    "queso mozzarella", "Queso Mozzarella" y "QUESO MOZZARELLA" son tres
    filas distintas en un reporte. Regla del español —conectores en
    minúscula salvo al inicio, siglas cortas respetadas— aplicada al salir
    del campo y **de nuevo en el servidor**, que tiene más clientes que esa
    pantalla.
  - Endpoints nuevos: `POST/GET/PATCH /inventory/recetas` + `items`,
    `/recetas/{id}/duplicar`, `/recetas/{id}/escalar`,
    `GET /inventory/unidades-medida`, `POST /sales/productos/{id}/grupos`,
    `GET /sales/productos/{id}`, `GET /sales/marcas`. `GET /sales/carta`
    gana `variantes[]` por ítem y el grupo de cada extra.
  - **Convertir un producto simple en uno con presentaciones**:
    `PATCH /sales/productos/{id}` acepta `quitar_receta: true` (bandera
    explícita, porque `receta_id: null` es indistinguible de "no lo mandaron",
    mismo criterio que `quitar_frecuencia` en categorías). La receta soltada
    **no se borra**: queda en el módulo de recetas, lista para asignarse a la
    primera presentación. Se niega en una presentación y en un extra: sin
    receta no se podrían preparar.
  - **Borrar presentaciones y recetas**: `DELETE /sales/productos/{id}` borra
    un producto **que nunca se vendió** —con su precio y sus vínculos de
    extra, que solo existían por él— y responde 409 si ya tiene ventas,
    porque `venta_item` apunta ahí y borrarlo reescribiría lo ya cobrado; en
    ese caso se descontinúa (RN-GEN-006). `DELETE /inventory/recetas/{id}`
    borra la receta y sus líneas, y responde 409 **nombrando** a los
    productos que la usan: la clave foránea lo impediría igual, pero con un
    error de integridad que no dice qué corregir. Esa consulta va por un
    contrato público nuevo de `sales` (`productos_que_usan_receta`), no por
    su ORM.
  - **En la ficha del producto la receta se elige, no se edita**: el editor
    completo estaba incrustado ahí y también en Catálogo → Recetas, y tener
    lo mismo en dos lados hacía pensar que eran dos recetas distintas. Ahora
    la ficha muestra una tabla de **presentaciones** —una fila por tarjeta del
    PDV: nombre, receta (desplegable de las ya creadas), orden y precio— con
    un enlace "editar" al módulo que sí las arma. Crear una presentación sin
    elegir receta crea una vacía con su nombre, para no mandar al usuario a
    otro módulo antes de poder cargar la fila.
  - **La tarjeta del PDV muestra la etiqueta corta**: dentro del diálogo de
    "Pizza Peperoni" las tarjetas dicen "Personal" y "Familiar", no "Pizza
    Peperoni Personal" — el nombre del producto ya está en el título. El
    nombre completo se conserva en la línea, que es lo que sale impreso en el
    ticket y el comprobante.
  - **Pantalla de artículos** (`/inventario/articulos`): crear insumos,
    subrecetas, mercadería y empaques con su unidad de medida, costo de
    arranque, categoría y control de lote. Era el bloqueante real del
    catálogo — sin insumos propios, una receta solo podía usar los tres
    artículos del seeder de demo. El backend existía desde el slice 1 de
    `inventory`; faltaba la pantalla. La UdM no se edita después de crear el
    artículo: cambiarla reescribiría en silencio el significado de todo el
    stock y de cada receta que lo use (RN-UDM-002).
  - **Listado de recetas** (`/catalogo/recetas`) y ficha propia: hasta ahora
    una receta solo era visible desde el producto que la usaba, así que las
    **subrecetas** —lo que la cocina produce para usar después: masa, salsa—
    no tenían dónde existir, y las copias sueltas quedaban invisibles. La
    ficha suma "¿Qué produce?", que liga la receta al artículo `subreceta`
    que genera (`PATCH /inventory/recetas/{id}` acepta `articulo_id`, con la
    relación exclusiva: dos recetas produciendo lo mismo dejarían a
    `production` sin saber cuál explotar).
  - **El formato título también se aplica a artículos y categorías**: se
    normalizaba el nombre de receta y de producto, pero no el de un insumo
    —"masa de pizza" se guardaba tal cual—, que es justo donde el duplicado
    por mayúsculas más daña un reporte de consumo.
  - **La receta se puede renombrar, rehacer y cambiar desde la ficha**
    (2026-08-03, tarde): faltaba lo que hacía útil a todo lo demás. El
    nombre, el rendimiento y su unidad se editan donde se leen (`PATCH
    /inventory/recetas/{id}`, que ya existía pero no tenía UI), un botón
    "Otra receta" arma una desde cero para un producto que ya tiene otra, y
    el selector "…o reusar una existente" permite apuntar a otra receta ya
    cargada. Sin esto, duplicar dejaba una copia llamada "(copy)" para
    siempre y no había forma de partir de cero: el único camino era duplicar.
  - **El sufijo de copia deja de apilarse**: duplicar "Pizza (copy)" ahora da
    "Pizza (copy) 2", no "Pizza (copy) (copy)" — a la tercera el nombre ya
    era ilegible.
  - **Catálogo es su propio módulo, separado del punto de venta** (enmienda a
    ADR-013): administrar la carta es acto de supervisor, no de quien vende
    con ella. Las pantallas se mudan de `/ventas/productos` a
    `/catalogo/productos` y el módulo se abre con el **permiso exacto**
    `sales.gestionar_catalogo` en vez del prefijo `sales.` — con el prefijo,
    un cajero (`sales.crear`) veía el módulo y leía el catálogo entero,
    chocando con el 403 recién al guardar. `lib/modulos.ts` acepta `permiso`
    exacto y `puedeVerModulo()` es el único punto que decide, usado tanto por
    el grid del home como por el guard de `ModuloShell`. El módulo Ventas
    queda apuntando al PDV.
  - Frontend: módulo **Catálogo** con la ficha que edita producto,
    variantes y recetas en la misma pantalla (patrón Odoo), y selector
    obligatorio de tamaño + extras agrupados en el PDV, que bloquea el
    agregado cuando falta algo en vez de dejar que el servidor lo rechace al
    enviar.
  - Contrato público nuevo de `inventory`: `queries_publicas.receta_resumen`.
    Descartados por reemplazo: `modificador` y `variante_producto` del
    data-model, nunca implementados.
- **`decision_gerencial` — acta de decisión gerencial** (2026-08-03,
  migración `1805c0904c5c`, RN-GER-002): documentada en `data-model.md` §8c
  desde el slice de Gerencia (2026-07-22), ahora con modelo (en `shared`),
  repo, casos de uso y API. `POST/GET /api/v1/decisiones-gerenciales[/{id}]`
  con permisos nuevos `gerencia.decidir` (firmar) y
  `gerencia.leer_decisiones` (consultar — el área ejecutora la necesita sin
  poder decidir, RN-GER-005; sembrado en `supervisor`). `decidido_por_id`
  sale del token, nunca del cuerpo: atribuirle la decisión a otro gerente
  invalidaría el acta. `referencia_tipo`/`referencia_id` son polimórficos
  **sin FK** — la decisión aplica a una OC escalada, una campaña sobre
  presupuesto o una sanción, y ni `shared` gana una FK hacia los módulos ni
  al revés. `aprobado_con_condiciones` sin condiciones es 409: un acta que
  no dice qué cumplir no le sirve al área ejecutora. 12 tests. Ningún
  módulo la escribe todavía — ese es el paso siguiente.

- **Guía para crear un módulo + tests que la exigen** (2026-08-03,
  `docs/engineering/module-guide.md`). La estructura de un módulo ya era
  replicable; lo que no estaba escrito en ningún lado es que **activarlo son
  siete registros fuera de su carpeta** (router, tag OpenAPI y `register()`
  de listeners en `core/app.py`; import en `models_registry.py`; migración;
  `PERMISOS`/`ROLES` del seeder; entrada en `frontend/lib/modulos.ts`) —
  olvidar uno da errores que no apuntan a la causa: Alembic proponiendo
  borrar tablas ajenas, o un 403 permanente por un permiso que ningún rol
  puede tener. La guía los lista con archivo y consecuencia, nombra a
  `purchases` como módulo de referencia y aclara cuándo corresponde
  `listeners.py`/`queries_publicas.py`. Tres de los siete pasan de disciplina
  a test en `tests/test_arquitectura.py`: modelos registrados para Alembic,
  routers montados en la app (detecta también los secundarios, tipo
  `kds_routers`) y **todo permiso exigido por un endpoint existe en el
  seeder** — se leen los 63 códigos del closure de `require_permission`
  recorriendo las 221 rutas montadas. De paso se corrige la afirmación de
  CLAUDE.md de que un módulo es "removible": lo es para el dominio de los
  demás, no para el ensamblado. Deuda declarada en `ROADMAP.md` →
  Transversal.
- **Pantalla de cocina (KDS)** (2026-08-03, `frontend/app/kds/`): pantalla
  completa táctil fuera del shell (como el PDV, ADR-013), una tarjeta por
  pedido con `#orden`, `referencia_atencion`, modalidad/canal y estado
  agregado. **Un toque tacha el ítem preparado** y "Todo listo" tacha el
  pedido entero — patrón de la *preparation display* de Odoo, cuya
  documentación se revisó antes de diseñar la pantalla. El toque encadena
  `en_preparacion → listo` porque `POST /kds/items/{id}/avanzar` solo
  acepta el estado inmediatamente siguiente (RN-CUP-002). Lo tachado en
  una estación aparece en **toda otra pantalla de la sucursal** que
  muestre ese pedido: el avance vive en `venta_item.estado_preparacion`
  (fuente única, RN-CUP-003) y ninguna pantalla guarda estado propio; la
  propagación es por polling cada 3 s (pausado con la pestaña oculta) —
  el push WS/Redis sigue como deuda. Sin "recall" de Odoo: el retroceso
  está prohibido, tocar un ítem tachado avisa en vez de deshacer. En
  pantallas de `despacho` y solo con `sales.entregar_pedido` aparece
  "Entregar" (RN-CUP-006). La estación va en la URL
  (`/kds?pantalla=<id>`); tile propio en el home filtrado por `kds.*`.
  Sin endpoints nuevos: el backend del KDS estaba completo desde
  2026-07-25/27.

- **Tablero de estaciones del KDS** (2026-08-03): `/kds` sin `?pantalla=`
  lista las estaciones de la sucursal y, con `kds.configurar`, permite
  **crear, editar y desactivar** pantallas (nombre, tipo
  `preparacion`/`despacho`, filtro por categorías contra
  `GET /inventory/categorias`; sin categorías = todas). Cierra el hueco de
  que `kds_pantalla` solo se creara por API: una sucursal nueva no podía
  arrancar su cocina desde la UI. Desactivar es baja lógica — la pantalla
  deja de aparecer en cocina, no se borra.

- **Restricciones JSONB de permiso, aplicadas (ADR-022)** (2026-08-02):
  `permiso.restricciones` pasa de campo descriptivo a evaluado.
  `users.domain.rules.ContextoPermiso`/`cumple_restricciones` (monto/
  estado/horario, puras) + `UsuarioRepo.restricciones` (comodín `*` o
  cualquier rol que otorgue el permiso sin condición ⇒ sin restricción) +
  `check_permission(session, usuario, *codigos, contexto=...)`
  (`users/api/deps.py`, retrocompatible — sin `contexto` no cambia nada;
  re-exporta `ContextoPermiso` para que otros módulos no toquen
  `users.domain` directo, exigido por `tests/test_arquitectura.py`).
  `require_permission` no cambia — no tiene el body para evaluar una
  condición. Primer uso real: `sales.aplicar_descuento` respeta un
  `monto_maximo` por rol (el router calcula el descuento real con
  `ventas.calcular_monto_descuento` y valida ANTES de aplicarlo, 403 si lo
  supera). 15 tests nuevos.

- **Consulta RUC/DNI vía Factiliza en alta de cliente/proveedor jurídico**
  (2026-08-02): `FactilizaClient.consultar_dni`/`consultar_ruc`
  (`src/shared/integrations/factiliza/`) contra `api.factiliza.com`
  (`FACTILIZA_CONSULTA_BASE_URL`, host distinto al de emisión de
  comprobantes) — RENIEC/SUNAT, mismo token. `nombres_desde_dni`/
  `razon_social_desde_ruc` hacen fallback a lo tecleado si Factiliza no
  responde o no encuentra el documento, para que el alta nunca se bloquee
  por un proveedor externo caído. Cableado en `sales.crear_cliente`
  (natural por DNI nuevo, jurídico por RUC nuevo) y
  `purchases.crear_proveedor` (jurídico por RUC nuevo); un documento ya
  registrado en `persona` no vuelve a consultar. Probado con datos reales
  de QA (DNI 73632127, RUC 20610077782). 20 tests nuevos
  (`tests/test_factiliza_consulta.py` + casos en `test_pdv_slice.py`/
  `test_purchases.py`); `tests/conftest.py` nuevo, autouse que fuerza
  `factiliza_token=""` por test para que el suite nunca dependa de la red.

- **`personas.leer`, CRUD de `unidad_medida`/`categoria_udm`/`divisa`, y
  proveedor natural en el frontend** (2026-08-02):
  - **`GET /personas/buscar?q=`** (permiso nuevo `personas.leer`, sembrado
    en `comprador` y `rrhh_admin`): responde `PersonaBusquedaOut` (id,
    nombres, apellidos, numero_documento) — nunca domicilio/teléfono/
    email/fecha de nacimiento, así que no exige `users.gestionar` como
    `GET /personas` (que sigue igual, sin cambios). Cierra el gap de RBAC
    que RRHH/Trabajadores había encontrado: un rol RRHH puro ya puede
    armar su propio selector de alta.
  - **CRUD de `unidad_medida`/`categoria_udm`** (`inventory`, permiso
    `gestionar_catalogo`) y de **`divisa`** (`users`, permiso
    `gerencia.gestionar_parametros_empresa`, lectura abierta a cualquier
    autenticado) — ambos antes solo se editaban por seeder/migración
    (ADR-014 Addendum b). `decimales` por unidad/divisa (RN-GER-010) ahora
    se corrige con un `PATCH`, sin migración.
  - **`components/persona-picker/`**: buscador reusable con debounce
    contra `/personas/buscar` — reemplaza el `<select>` con todo el
    catálogo cargado (no escala) en RRHH/Trabajadores, y habilita
    **proveedor natural en Compras/Proveedores** (toggle jurídico/natural
    en el diálogo). `ProveedorOut.persona_id` no viajaba y se agregó: sin
    eso, un proveedor natural no tenía forma de mostrarse por nombre en
    la tabla.
  - 11 tests nuevos (`tests/test_catalogo_udm_divisa.py`): CRUD de UdM/
    divisa, permisos, y que `/personas/buscar` de verdad solo devuelve
    los 4 campos mínimos.

- **Tres pantallas reales más — Inventario/Artículos, Compras/Órdenes de
  compra, RRHH/Trabajadores** (2026-08-02), siguiendo el patrón de
  Compras/Proveedores (tabla TanStack + alta con `<dialog>` nativo):
  - **Inventario → Artículos**: crear exige `unidad_medida_id`, que no
    tenía ningún endpoint de lectura — nuevo `GET /api/v1/inventory/
    unidades-medida` (catálogo global, sin filtro de tenant:
    `UnidadMedidaRepo`, `catalogo.listar_unidades_medida`). Seeder de
    demo (`pdv_demo.py`, no `seed.py` — ver más abajo) agrega Kilo/Litro
    además del "Unidad" que ya creaba.
  - **Compras → Órdenes de compra**: alta con ítems dinámicos
    (agregar/quitar fila, total en vivo) e `idempotency_key` generada en
    el cliente (`crypto.randomUUID()`). Dos endpoints nuevos que
    bloqueaban la pantalla: `GET /api/v1/purchases/ordenes-compra`
    (`OrdenCompraRepo.list`, tenant vía join a `almacen` — la orden no
    tiene `empresa_id` propio) y `GET /api/v1/almacenes` (`AlmacenRepo`
    en `users`, sin `require_permission` a propósito: catálogo de
    referencia, no dato sensible, pero sí escopado por tenant).
  - **RRHH → Trabajadores**: alta exige una `persona_id` existente
    (party model) — sin endpoint nuevo, ya existía `GET /personas`, pero
    gatillado por `users.gestionar` en vez de algo más acorde a RRHH; un
    rol RRHH puro sin ese permiso no puede armar el selector de alta hoy
    (gap de RBAC documentado, no corregido en este cambio).
  - Home tile de **Ventas** corregido: apuntaba a `/ventas` (404); el PDV
    es pantalla completa fuera del shell a propósito (ADR-013), el tile
    ahora enlaza directo a `/pdv`.
  - Cerrados los tres hallazgos menores de la revisión del PR anterior:
    `<select>` sin estilo en `globals.css`, altura del sidebar con
    número mágico (`calc(100vh-56px)` → `flex-1` real), y comentario en
    `lib/sesion.ts` documentando la dependencia de la memoización de
    `fetch` de Next.js.
  - **`pdv_demo.py` (no `seed.py`) gana 2 `Persona` de demo** —
    necesarias para poder probar el alta de Trabajador sin una pantalla
    de Personas que todavía no existe. Se evaluó agregar UdM/Personas al
    propio `seed()`, pero **17 archivos de test** crean su propia
    `CategoriaUdm("Peso")` asumiendo que `seed()` no toca `inventory`;
    ese camino se revirtió antes de commitear.
  - Verificado end-to-end en Docker con datos reales (curl + navegador):
    crear artículo → aparece en la tabla; crear OC de 2 ítems → total
    calculado correcto (390.00 = 20×18.50 + 5×4.00); crear trabajador →
    nombre resuelto desde `persona_id`.

- **Shell estilo Odoo, F2.11 (tablas) y primera pantalla real de frontend**
  (2026-08-02): TanStack Table como librería de tabla del ERP
  (`frontend/components/tabla/tabla-datos.tsx`, v1 orden/búsqueda/filtro/
  paginación). Shell en dos niveles (`frontend/app/(app)/`): guard de
  sesión real vía `/users/me` + barra superior compartida, y sidebar +
  guard de permiso real por `[modulo]/layout.tsx` (server-side, no solo
  filtro visual — entrar por URL sin el permiso cae en "Sin permiso").
  Home de apps con grid de 10 módulos filtrado por `permisos`. Dashboard
  existente relocalizado bajo el shell y migrado a leer `empresa_id` de
  `/users/me` en vez del JWT decodificado sin verificar. Primera pantalla
  real de un módulo: Compras → Proveedores, listado + alta con `<dialog>`
  nativo (sin shadcn/ui, YAGNI hasta que un formulario lo exija). Tailwind
  CSS instalado sobre los tokens existentes. Verificado end-to-end en
  Docker. Deuda: CRUD de proveedor natural (falta selector de persona),
  resto de módulos sin pantalla (solo tile + 404).

- **Toda magnitud lleva su unidad — RN-GER-010, ADR-014 Addendum b**
  (2026-08-02, migración `c93e5a7b1d42`): un parámetro monetario declara su
  `divisa` y uno físico su `unidad_medida_id`; un número suelto (`{"monto":
  2000}`) responde 409 — `MagnitudInvalida` hereda de `ReglaNegocio`, la
  jerarquía común de `src/shared/errors.py`, así que la traduce el handler
  global sin `try/except` por endpoint. Los **decimales son configurables
  por unidad**:
  nueva entidad transversal `divisa` (`codigo`, `nombre`, `simbolo`,
  `decimales`, `activa`; sembrada con PEN/S//2) y nueva columna
  `unidad_medida.decimales` (default 3 — Kilo necesita gramos, Unidad
  necesita 0). `src/shared/magnitudes.py` valida la forma del valor y
  redondea con los decimales de esa unidad, en texto y no en float, con
  `ROUND_HALF_UP` (en dinero el medio centavo sube). Nueva columna
  `parametro_empresa.valor_display` con la magnitud formateada ("S/ 2000.00",
  "5.000 Kilo") tal como se le mostró a Gerencia, congelada con la fila. La
  misma validación corre al proponer y al modificar-y-aprobar. La UdM se lee
  por el contrato público nuevo
  `inventory.application.queries_publicas.unidad_medida_para_magnitud` —
  `shared` no consulta el catálogo de otro módulo. La migración completa
  `divisa: PEN` en los umbrales que venían de `regla_aprobacion`. Tests en
  `tests/test_magnitudes.py`. **No** cambia RN-PRC-004: `precio` sigue sin
  columna de divisa, la operación sigue siendo PEN única. Sin CRUD de
  `divisa`/`unidad_medida` todavía (ROADMAP → Deuda técnica → Transversal).

- **`parametro_empresa` con aprobación de Gerencia — ADR-014 Addendum**
  (2026-08-02, RN-GER-008/009): los valores operativos configurables
  (umbral de OC, margen de contribución mínimo, frecuencia de conteo,
  margen de error de ajuste, monto de caja chica, plazo de envío de
  comprobantes, rangos salariales) se **proponen desde el módulo al que
  pertenecen** y **no surten efecto hasta que Gerencia los aprueba**, que
  puede aceptar, rechazar con motivo, o modificar el valor al aprobar.
  Mientras la propuesta está pendiente, el módulo sigue leyendo el valor
  anterior. Sin tabla de solicitudes aparte: cada propuesta es una fila de
  `parametro_empresa` con `estado` (`propuesto` → `vigente` | `rechazado`,
  más `reemplazado`) y un índice único parcial `WHERE estado='vigente'`;
  la lectura (`src/shared/parametros.py::valor_vigente`) solo devuelve el
  vigente, así que una propuesta pendiente es invisible para el módulo. El
  historial (quién propuso, quién resolvió, cuándo, valor anterior) es la
  propia tabla — no escribe en `audit_log`. Endpoints
  `POST/GET /api/v1/parametros`, `POST /api/v1/parametros/{id}/aprobar`
  (con `valor` opcional = modificar al aprobar) y `.../rechazar`.
  Migración `a71c9f4b2e60`. **Un permiso por módulo** para proponer
  (`<modulo>.proponer_parametro`, catálogo en
  `src/shared/parametros.py::MODULOS`) — Compras no propone parámetros de
  RRHH; el `modulo` se valida como `Literal` en el schema (422 si es
  inventado) y `GET /parametros` sin filtro de `modulo` exige el permiso de
  Gerencia, porque los rangos salariales de RRHH no son de lectura general.
  Aprobar/rechazar/modificar sigue bajo
  `gerencia.gestionar_parametros_empresa`. Tests en
  `tests/test_parametros_empresa.py`.
- **Slice core del módulo `marketing`** (2026-08-01, migración
  `e9c3b7412a68`). El módulo existía solo como README de spec desde el
  2026-07-22; ahora tiene código. Las 5 entidades de data-model §8d y 17
  endpoints bajo `/api/v1/marketing`:
  - **`campana`** con brief obligatorio: sin objetivo, público, presupuesto
    y KPI no se aprueba, y sin aprobación no sale a canal (RN-MKT-003). El
    rol semilla `marketing` **no** lleva `marketing.campana_aprobar` — ese
    permiso vive en `supervisor`: quien redacta el brief no lo aprueba.
  - **`pieza_contenido`**: solo se publica si es pertinente a la marca y su
    uso de marca está validado (RN-MKT-001/002). Contenido viral pero ajeno
    a la marca queda bloqueado por el propio endpoint, no por criterio.
  - **`lead` con atribución a la venta real** (RN-MKT-003). La automática la
    hace `marketing` escuchando `sales.venta_confirmada`, y **solo cuando no
    hay ambigüedad**: un único lead abierto del cliente en campaña en curso.
    Con dos o más no atribuye nada y queda
    `POST /leads/{id}/atribucion` — adivinar qué campaña convirtió falsearía
    justo la métrica por la que la campaña existe. `sales.venta_confirmada`
    suma `cliente_id` al payload para hacerlo posible.
  - **`implementacion_material_sucursal`**: enviar el material no cierra la
    tarea, se verifica en sitio (RN-MKT-005); una implementación incompleta
    exige incidencia.
  - **`encuesta_satisfaccion`** (RN-COM-007): selectiva y solo sobre venta
    ya entregada y con cliente registrado. Estaba descrita en data-model §6
    (ventas) porque su disparador es `sales.venta_entregada`; la tabla es de
    marketing, que es quien elige a qué venta encuestar.
  - `marketing` no importa `Venta`: lee sucursal, cliente y estado de
    entrega por el contrato público nuevo
    `sales::venta_para_encuesta`. Alcance de tenant por `campana.empresa_id`
    y, para la encuesta, por la sucursal de su venta (ADR-004).
  - 13 tests en `tests/test_marketing.py`. Diferido: aprobación contra
    presupuesto anual (`decision_gerencial`), envío real de la encuesta y
    expiración programada — ver `ROADMAP.md` → Deuda técnica → marketing.
- **Convocatoria y tablero de contratación en `rrhh`** (2026-08-01, migración
  `a7f2c81e4b95`). El reclutamiento tenía SOPs y plantillas pero en código
  `postulante` nacía suelto, sin búsqueda a la que pertenecer y sin más
  estados que `en_proceso`/`rechazado`/`contratado`. Ahora:
  - **`convocatoria`** es el expediente de la búsqueda (empresa, sucursal,
    puesto, motivo, vacantes, rango salarial aprobado, fecha límite):
    borrador → publicada → cerrada. **RN-RRHH-013 pasa a estar aplicada en
    código**: sin `perfil_puesto` registrado el sistema no deja publicar.
  - **Formulario público de postulación** — `POST /rrhh/postulaciones/{token}`
    sin JWT. El token nace al publicar y desaparece al cerrar: es lo único
    que autoriza a escribir y solo crea un postulante de esa convocatoria.
    Rate limit de 20/hora por IP, campos y `respuestas` acotados,
    consentimiento obligatorio (RN-PER-004) y **fecha puesta por el
    servidor** — si la mandara el cliente, podría postular vencida la fecha
    límite. El formulario es Google Forms con un Apps Script de 12 líneas
    (SOP de publicación de convocatoria); no se construyó un formulario
    propio ni se integró la API de Google.
  - **El candidato ya no entra a `persona`**: `postulante` lleva sus propios
    nombres/apellidos/teléfono/email y `respuestas` JSONB. El pool es gente
    ajena a la empresa y la mayoría nunca se contrata; `persona` y
    `trabajador` se crean recién en `POST /postulantes/{id}/contratar` (o se
    reusa la `persona` del ex-trabajador recontratado, RN-GEN-007).
  - **Un solo tablero** para los 13 pasos de incorporación: `recibido` →
    `preseleccionado` → `entrevistado` → `verificado` → `oferta_enviada` →
    `contratado` → `inducido` → `confirmado`, más `descartado`.
    `GET /convocatorias/{id}/tablero` devuelve las columnas en orden (el
    cliente no replica ese orden). Se avanza de a una columna, sin saltos ni
    retrocesos, y descartar exige motivo: el historial del proceso es la
    defensa ante un reclamo de discriminación (Ley 26772).
  - `postulante` gana `empresa_id` y queda escopado por tenant — cierra la
    excepción declarada en el cambio de tenant del mismo día. Permiso nuevo
    `rrhh.convocatoria_gestionar` (publicar/cerrar lo aprueba el
    administrador, no quien pide el puesto); contratar exige
    `rrhh.trabajador_gestionar`, que es donde nace la planilla.

  Diferido a propósito: entidad `requisicion` aparte (la convocatoria en
  borrador ya lo es), checklist de inducción paso por paso (las columnas del
  tablero alcanzan), cálculo de PLAME y modelado de uniforme/EPP.

- **Derechos ARCO sobre `postulante`** (2026-08-01, migración
  `b1d09e574c23`, ADR-011). Sacar al candidato de `persona` dejó sus datos
  fuera del alcance de `POST /personas/{id}/anonimizar`; ahora tiene los
  suyos: `GET /rrhh/postulantes/{id}` (acceso),
  `PATCH /rrhh/postulantes/{id}` (rectificación de contacto, 409 sobre una
  ficha ya anonimizada) y `POST /rrhh/postulantes/{id}/anonimizar`
  (cancelación irreversible). Reusa el permiso `personas.anonimizar` — misma
  capacidad legal, mismo custodio, otra tabla — y deja rastro en `audit_log`
  registrando **qué** se borró, nunca el valor.
  - Se anonimiza en vez de borrar aunque, a diferencia de `persona`, **nada
    referencie la fila**: el borrado se llevaría `motivo_descarte` y
    `canal_origen`, o sea la evidencia de por qué se descartó a alguien
    (Ley 26772) y la constancia de que la solicitud existió. Corolario que
    quedó documentado en el modelo: el motivo de descarte se escribe como
    criterio, nunca con datos personales, porque sobrevive.
  - Contratado → 409: sus datos ya pasaron a `persona` y están bajo
    retención laboral; su ARCO se ejerce allá.
  - **El plazo de conservación pasa de declarado a aplicado**: cada ficha
    nace con `plazo_conservacion_declarado`
    (`RRHH_PLAZO_CONSERVACION_POSTULANTE_MESES`, 12 por defecto) — antes
    quedaba en NULL, lo que volvía la ficha inpurgable y el aviso de
    privacidad una promesa vacía — y `python -m src.modules.rrhh.purga`
    anonimiza lo vencido desde el cron del host (mismo criterio que
    backups), sin tocar nunca al contratado. Falta darlo de alta en el
    servidor.

### Security

- **Contexto de tenant desde el JWT en toda la API** (2026-08-01, ADR-004).
  `purchases`, `production`, `accounting`, `rrhh` y el dashboard gerencial
  todavía recibían `empresa_id` del cliente: cualquier usuario autenticado con
  el permiso correspondiente podía leer y escribir datos de otra empresa
  mandando el UUID ajeno en el body o el query string. Ahora el alcance sale
  de los claims (`tenant.empresa` / `tenant.filtro_empresa`) y cada recurso se
  valida contra su fila real mediante un `application/scope.py` por módulo —
  proveedor y OC por su empresa, orden de producción por su almacén, cuenta /
  periodo / asiento / pago por `empresa_id`, caja y arqueo por la sucursal de
  su punto de venta, y todo `rrhh` por el trabajador o la empresa del
  documento. `empresa_id` en el body pasa a ser opcional y solo lo usa un
  superusuario sin empresa asignada. `accounting` resuelve la sucursal de un
  punto de venta con un contrato público nuevo de `sales`
  (`sucursal_de_punto_venta`), sin importar su dominio. Excepción declarada:
  `rrhh.postulante` no tenía `empresa_id` y quedó sin escopar — **cerrada el
  mismo día** por el slice de convocatoria (ver Added).

- **Autorización de supervisor por PIN** (2026-07-28, RN-AUD-005, ADR-018 §6).
  Corrige un defecto introducido el mismo día: `POST /sales/ventas/{id}/descuento`
  recibía `autorizado_por` como UUID **en el cuerpo del request, sin validar**,
  mientras el permiso se comprobaba contra el token de quien llamaba — el cajero
  no podía ejecutarlo y el campo de auditoría era falsificable.
  Nuevo `POST /api/v1/auth/autorizar`: verifica usuario + PIN **y** que tenga el
  permiso, y devuelve un JWT de 3 minutos con `typ=autorizacion` acotado a esa
  acción. Un access token normal no sirve como autorización (si sirviera, el
  cajero se autorizaría con su propia sesión); una elevación obtenida para
  descontar no vale para anular. Va detrás del mismo rate limit que el login y
  devuelve el mismo error tenga o no el permiso, para no revelar qué PIN es
  válido ni quién es supervisor. Deja rastro en `audit_log` y en el log de
  seguridad. Lo exigen descuento de orden, anulación de líneas enviadas y
  retiro de efectivo.

### Fixed

- **Instalación nueva inutilizable: el seeder no asignaba sucursales al
  `admin`** (2026-08-01). Sin filas en `usuario_sucursal` el JWT sale sin
  `empresa_id`, así que toda operación escopada respondía 403 "usuario sin
  empresa asignada" (ADR-004) apenas se levantaba el sistema. El seeder ahora
  asigna al `admin` todas las sucursales que crea, de forma idempotente.
  Cubierto por `test_seed_deja_al_admin_con_empresa`.
- **El extra cobraba una porción y descontaba varias** (2026-07-28). La
  cantidad del extra es **por plato**: dos pizzas con extra queso son dos
  porciones. El consumo enviado a inventory ya se multiplicaba por el plato,
  pero la línea cobrada no, así que dos pizzas con extra cobraban S/ 5 y
  descontaban dos porciones de queso — la diferencia habría aparecido como
  faltante de inventario todos los días. Ahora se multiplica una sola vez, al
  armar la línea, y el cobro y el consumo salen del mismo número. El lote de
  sincronización exporta la cantidad **por plato** para que el replay no la
  vuelva a multiplicar (ADR-009). Detectado al operar el PDV real contra la
  API, no por los tests.
- **`created_at`/`updated_at` sin `server_default` en las tablas nuevas**
  (2026-07-28): `mesa`, `producto_comercial_extra` y `movimiento_caja` se
  crearon con las columnas `NOT NULL` pero sin default, mientras el modelo
  las declara con `server_default=now()`. Los tests no lo veían porque usan
  `create_all` (que sí aplica el default del modelo); insertar contra la base
  migrada fallaba con `NotNullViolation`. Es justo el hueco que `alembic
  check` no cubre: compara tipos y nulabilidad, no defaults.
- **`json` → `jsonb` en cuatro columnas** (2026-07-28, migración
  `b6d41e07af92`). `acta.participantes`, `boleta_pago.ingresos`,
  `boleta_pago.descuentos` y `comprobante.respuesta_proveedor` se habían creado
  con `sa.JSON()` genérico en vez del `JsonB` que declaran los modelos, y en
  Postgres quedaron como `json` mientras las otras 19 columnas JSON del esquema
  son `jsonb`. `json` guarda el texto literal y **no admite los operadores ni
  los índices GIN de `jsonb`**. Detectado al agregar `alembic check` al CI.
- **Índices y constraints declarados solo en la migración** (2026-07-28): los
  índices de `mesa`, `movimiento_caja`, `venta_item.padre_venta_item_id` y
  `comprobante(venta_id, grupo_cobro)`, y los nombres de las constraints únicas
  de `mesa` y `producto_comercial_extra`, existían en la migración pero no en
  los modelos. Un `create_all` (tests) no los creaba. Ahora coinciden y
  `alembic check` pasa limpio.

### Added

- **Abastecimiento interno: reserva de stock, solicitud de insumos y
  transferencias** (2026-08-01, ADR-020, migración `d8b35f1ca207`,
  RN-INV-001/002/003/009/010/011). El ERP ya sabía cuánto stock hay en cada
  almacén; ahora sabe moverlo entre ellos. Cierra el ciclo que los SOP de
  Almacén describen desde el modelado y que no tenía una línea de código.
  - **`reserva_stock` es una promesa, no un movimiento**: no toca `stock`
    ni genera `movimiento_inventario`. `GET /inventory/stock` devuelve
    ahora `cantidad` (físico), `reservado` y `disponible` = físico − Σ
    reservas activas (RN-INV-009). Sin esto, entre que un supervisor
    aprueba un requerimiento y el central arma el picking pasan horas
    durante las cuales dos sucursales se prometen el mismo saco de harina.
  - **Reservar bloquea, consumir no**: aprobar una solicitud exige
    disponible suficiente (409 si no alcanza), pero una venta o un consumo
    de producción **nunca** se frenan por una reserva — esa operación ya
    ocurrió en el mundo real y negarla en el ERP solo desincroniza los
    libros. La consecuencia aceptada es que el disponible puede quedar
    negativo: es la señal de una promesa sin respaldo, no un error.
  - **Ciclo completo**: `POST /solicitudes` (el local pide) →
    `/aprobar` (recorta por SKU si hace falta y reserva en el abastecedor)
    → `POST /transferencias` (descuenta el origen, deja el stock
    `en_transito`) → `/recibir` (suma el destino). `/rechazar` y
    `/cancelar` sueltan las reservas (RN-INV-010); `/reservas/{id}/liberar`
    es la liberación manual ante desabastecimiento (RN-INV-011).
  - **La solicitud va por almacén, no por sucursal** como decía el
    borrador del modelo: producción también solicita y la transferencia
    opera sobre almacenes. El abastecedor sale de
    `almacen.almacen_abastecedor_id` y se copia a la fila, para que
    cambiarlo después no reescriba la historia de lo ya pedido.
  - **`transferencia_item` va por SKU y lote**: el despacho reparte por
    FEFO, así que sacar 10 kg puede tomar tres lotes y el destino recibe
    esos mismos tres. Por SKU a secas, el destino elegiría un lote
    distinto al que salió y la trazabilidad de ADR-015 se cortaría justo
    en el traslado.
  - **Las diferencias se registran, no se corrigen**: no se despacha más de
    lo aprobado ni se recibe más de lo enviado (RN-INV-001/002) — menos sí,
    en ambos casos. Si llegaron 28 de 30, al stock entra 28 y la diferencia
    viaja en `inventory.transferencia_recibida`. Cuadrar el papel a la
    fuerza es lo que despega el inventario teórico del real.
  - **Transferencia lateral** sucursal↔sucursal: misma entidad, sin
    solicitud detrás e ítems explícitos.
  - Permisos nuevos `inventory.solicitar_insumos`,
    `inventory.aprobar_solicitud` y `inventory.liberar_reserva`; el slice
    estrena además `inventory.transferir` e `inventory.recepcion`,
    sembrados desde el slice 1 y sin uso hasta hoy. Aprobar y solicitar son
    permisos distintos y el aprobador no puede ser quien pidió (RN-INV-006).
  - Desbloquea el contrato de lectura `purchases` ↔ `solicitud_insumos`
    ("qué sucursales piden más"), que esperaba a que la entidad existiera.
  - 23 casos en `tests/test_transferencias.py`; migración verificada ida y
    vuelta contra Postgres real más `alembic check`.
- **Conteo cíclico de inventario, con la frecuencia en la categoría**
  (2026-08-01, ADR-019, migración `c4e70a91d5b8`, RN-INV-007/014/021).
  `conteo` + `conteo_item` cierran el pendiente más viejo de `inventory`:
  hasta ahora el ERP sabía qué stock debía haber, pero no tenía cómo
  contrastarlo contra lo que hay en el estante.
  - **La periodicidad la fija la categoría**, no un número universal:
    `categoria.frecuencia_conteo` (diario / semanal / quincenal / mensual /
    semestral / anual; NULL = fuera del ciclo). Un perecible se cuenta a
    diario y un abarrote al mes en el mismo almacén. Se configura en
    `PATCH /inventory/categorias/{id}` — endpoint nuevo. Esto **corrige a
    ADR-014**, que había anticipado la frecuencia como `parametro_empresa`:
    esa tabla guarda un valor por empresa y aquí hace falta uno por
    categoría, con FK de verdad.
  - **El calendario se deriva, no se guarda**: la próxima fecha es el
    último conteo cerrado más los días de la frecuencia. Sin tabla
    `programa_conteo` que mantener sincronizada con cuatro caminos de
    escritura. `GET /inventory/conteos/programa` muestra estado (`al_dia` |
    `vence_hoy` | `vencido`) y días de atraso, lo vencido primero. Un
    conteo general (sin categoría) pone al día a todas las del almacén.
  - **Lo no contado en su fecha se reporta a almacén y gerencia**
    (RN-INV-021): `POST /inventory/conteos/verificar-vencidos` publica
    `inventory.conteo_vencido`. El día en que vence todavía no es falta.
  - **Stock esperado congelado al abrir**, no al cerrar: el almacén sigue
    operando mientras se cuenta, y medir contra un stock que se movió
    durante el recuento inventa diferencias que nadie provocó. Mismo
    criterio de "congelar el fondo" del arqueo de caja.
  - **A ciegas por defecto** (RN-INV-005): el detalle del conteo oculta
    `cantidad_sistema` y `diferencia` salvo permiso
    `inventory.ver_stock_esperado`. El rol `almacenero` cuenta sin verlo —
    conocer el número esperado convierte la auditoría en una confirmación.
    Permisos nuevos `inventory.contar` y `inventory.ver_stock_esperado`.
  - **Cerrar solicita, no corrige**: cada diferencia genera un `ajuste`
    `pendiente` con `ajuste.conteo_id` (columna nueva), que sigue exigiendo
    un aprobador distinto de quien contó (RN-INV-006). Los ítems que nadie
    contó se ignoran: un conteo parcial no puede declarar faltante lo que
    no se miró. `dentro_margen` sale de `INVENTORY_MARGEN_AJUSTE_PCT` (2%,
    RN-INV-015); con stock esperado en 0 no hay porcentaje posible y la
    diferencia queda fuera de margen.
  - Un SKU contado que no estaba en el snapshot entra con sistema en 0 —
    encontrar en el estante algo que el ERP no registra es justo el
    sobrante que el conteo existe para detectar.
  - Resuelve los `[[ COMPLETAR ]]` de periodicidad y margen en
    `docs/almacen-logistica/politica-almacen-logistica.md`. 22 casos en
    `tests/test_conteos.py`; migración verificada ida y vuelta contra
    Postgres real más `alembic check`.
- **Slice PDV: mesa tipada, cobro dividido, receptor en caja y descuento de
  orden** (2026-07-28, ADR-018, migración `d7e3b8c14f52`). Cierra los cuatro
  huecos que el diseño del punto de venta destapó y el modelo no daba:
  - **`mesa`** (`sucursal_id`, `numero` único por sucursal, `zona`,
    `capacidad`, `activa`) + `venta.mesa_id` / `venta.comensales`. El salón
    deja de vivir en el texto libre de `venta.referencia_atencion`, que se
    conserva para takeout/delivery. `GET /sales/mesas/mapa` devuelve la
    ocupación **derivada** de las ventas en `orden` — la mesa no guarda
    estado propio. Permiso `sales.gestionar_mesas`.
  - **`grupo_cobro`** (entero, default 1) en `venta_item`, `pago` y
    `comprobante` (RN-COM-018): una orden se divide en cuentas, cada una con
    sus pagos, su receptor y **su propio comprobante**. La venta pasa a
    `pagada` recién cuando ninguna cuenta queda con saldo. `venta_id` deja
    de identificar un único comprobante: usar `por_venta_y_grupo` /
    `todos_de_venta`.
  - **`comprobante.receptor_num_doc` / `receptor_nombre`** (RN-CPP-003): el
    DNI o RUC que el cajero teclea al cobrar, sin exigir cliente registrado.
    11 dígitos → factura; 8, `00000000` o vacío → boleta. Un documento a
    medio teclear se rechaza en el dominio, no en SUNAT.
  - **Descuento manual de orden** en `venta` (`descuento_modo`,
    `descuento_valor`, `descuento_motivo`, `descuento_autorizado_por`,
    RN-COM-017), `POST /sales/ventas/{id}/descuento`, permiso
    `sales.aplicar_descuento` separado de `sales.cobrar` para que el cajero
    no se autorice a sí mismo. Se prorratea entre grupos de cobro y baja a
    las líneas al emitir. Publica `sales.descuento_aplicado`.
  - **Cliente identificado por teléfono** (migración `e1c4a9d6b038`):
    `persona.numero_documento` y `tipo_documento` pasan a **nullable** — el
    UNIQUE se conserva porque admite varios NULL. Registrar a una persona
    natural exige **teléfono, no DNI** (RN-PTS-004): mucha gente no lo da en
    el mostrador y negarse a registrarla perdía la venta y su historial. El
    documento se completa después con
    `PATCH /sales/clientes/{id}/documento`. Para **facturar a una empresa el
    RUC sigue siendo obligatorio**. Un cliente sin documento o con el
    genérico `00000000` **no cuenta como identificado** y queda fuera de las
    promociones para clientes registrados (RN-PTS-005) — regla derivada
    `rules.cliente_identificado`, no una columna. `00000000` se persiste como
    `NULL`: es "sin documento", no un documento, y guardarlo literal haría
    chocar al segundo anónimo contra el UNIQUE. **Trabajador y usuario
    siguen exigiendo documento** — esa validación vive en
    `users.application.admin`, no en el esquema.
  - **`POST /sales/clientes`**: alta desde caja. El documento decide el tipo
    (RUC → jurídico; el resto → natural con su `persona`, reutilizándola si
    ya existe). Antes solo había `GET /sales/clientes`.
  - **`GET /sales/clientes/buscar?q=`**: búsqueda de caja por teléfono,
    documento o nombre (RN-PTS-006), separada del listado de análisis
    externo, que usa otro permiso.
  - **`GET /sales/ventas`**: jornada por sucursal, base de la pestaña de
    cobrados del PDV.
  - Replay del hub (ADR-009) transporta los campos nuevos; los lotes viejos
    siguen entrando (`grupo_cobro` asume 1, el resto es opcional).
  - Migración sin backfill: todo lo agregado es nullable o con
    `server_default`. La clave de idempotencia del grupo 1 sigue siendo
    `venta:{id}`. 24 casos nuevos en `tests/test_pdv_slice.py`, incluidos
    los de compatibilidad hacia atrás. `docs/architecture/openapi.json`
    regenerado.

  **No incluye promociones.** El descuento manual es un acto humano
  autorizado; las promociones condicionales por marca/sucursal necesitan un
  motor de reglas que sigue pendiente (ver ADR-018 → «Frontera explícita» y
  `ROADMAP.md`).

- **Extras de producto** (2026-07-28, RN-COM-021, migración `f2a8c15e94d7`).
  Un extra (extra queso, doble carne) **es un `producto_comercial`** con
  `es_extra=True` y su propia receta, que se ejecuta en la sucursal y se suma
  a la del producto al agregarse. Modelarlo así en vez de como entidad aparte
  le da gratis precio server-side por lista, aparición en la carta y descuento
  de insumos por el mismo `sales.venta_confirmada`. Lo propio son
  `producto_comercial_extra` (qué producto admite qué extra, con tope por
  línea) y `venta_item.padre_venta_item_id` (de qué línea cuelga). El extra
  **hereda el grupo de cobro del padre** — dividir la cuenta no puede dejar la
  pizza en una cuenta y su extra en otra — y su consumo se multiplica por el
  plato: tres pizzas con extra queso descuentan tres porciones. `GET /carta`
  devuelve los extras dentro de cada producto; los extras no salen sueltos.
  Nuevo `POST /sales/productos/{id}/extras`.
- **Anular líneas de una orden ya enviada** (2026-07-28, RN-COM-020):
  `POST /sales/ventas/{id}/anular-lineas` con autorización de supervisor y
  motivo obligatorio. Publica `sales.lineas_anuladas` → inventory repone lo
  que ya no se prepara (mismo listener que `venta_anulada`). Quitar todas
  anula la orden. Antes de enviar a cocina el pedido vive en el PDV y no toca
  el servidor.
- **Precuenta** (2026-07-28, RN-COM-019): `GET /sales/ventas/{id}/precuenta`,
  documento **no fiscal** para que el cliente revise su consumo antes de
  pagar, opcionalmente por cuenta. Sin serie ni correlativo, no cambia el
  estado de la venta y no se audita: pedirla dos veces es normal.
- **Movimiento de efectivo en caja** (2026-07-28, RN-MDP-007, migración
  `a3f0d29b6c81`): `movimiento_caja` por apertura, con motivo obligatorio.
  `POST` y `GET /accounting/cajas/apertura/{id}/movimientos`. **Retirar exige
  autorización de supervisor** (permiso nuevo `accounting.caja_retirar`) y no
  puede exceder el efectivo disponible; ingresar no la exige. El cierre suma
  el neto al monto esperado — sin esto, pagarle a un repartidor dejaba el
  cierre descuadrado y la diferencia se le atribuía al cajero (RN-MDP-005).
- **Frontend del punto de venta** (2026-07-28, `frontend/app/pdv/`). Primera
  pantalla operativa del PDV contra los endpoints reales: apertura de caja
  por denominación con firma del encargado, catálogo con extras por producto,
  ticket con varios pedidos abiertos en paralelo, selección de líneas por
  pulsación larga, mapa de mesas, cobrados de la jornada, y los diálogos de
  cliente, tipo de orden y cobro con split de medios.
  - El pedido **vive en el navegador** hasta enviarlo o cobrarlo: recién ahí
    nace la `venta` (RN-COM-005). Por eso se pueden tener varios borradores
    abiertos sin ensuciar la base.
  - **Proxy `/api/proxy/[...ruta]`**: el navegador llama sin credenciales y
    Next adjunta el `Authorization` desde la cookie httpOnly. El token nunca
    llega al JavaScript del cliente. No filtra rutas a propósito — la
    autorización real la hace la API en cada request (ADR-004), y duplicar
    esa lista solo crearía un segundo lugar donde olvidarse de actualizarla.
  - Nuevo `GET /sales/puntos-venta?sucursal_id=`: sin saber qué caja es, el
    PDV no puede abrir turno ni emitir con la serie correcta.
  - Nuevo seeder de desarrollo `python -m src.seeders.pdv_demo`: caja, carta
    con un extra, medios de pago y 12 mesas. `seed.py` deja la organización
    pero nada que vender.
  - `comprobante` expone `grupo_cobro`, `receptor_num_doc` y
    `receptor_nombre`: la pestaña de cobrados los necesita para reimprimir el
    comprobante correcto de una venta dividida.
  - La regla `no-unused-vars` de ESLint pasa a la variante de
    `@typescript-eslint`: la del core no entiende TypeScript y marcaba como
    no usados los nombres de parámetro en las firmas de tipo.
- **CI: las migraciones se ejecutan de verdad** (2026-07-28). Los tests corren
  sobre SQLite con `create_all` y nunca ejecutaban una sola migración; un
  `alembic upgrade head` roto se descubría al desplegar. Nuevo job
  `migraciones` con un Postgres real: `upgrade head` sobre base vacía,
  `downgrade base`, volver a subir, y `alembic check` para que un modelo sin
  migración no pase. Verificado localmente contra Postgres 16.

### Fixed

- **Los eventos internos se despachan después del commit** (2026-08-01,
  ADR-016). El bus entregaba el evento en el acto, en medio de la
  transacción del emisor: cuando esa transacción hacía rollback —el
  `UNIQUE (sucursal, fecha, numero_orden)` de dos cajas simultáneas, un
  ítem rechazado en el replay del hub, la rama de error de la tarea del
  comprobante— `inventory` ya había descontado y commiteado stock de una
  venta que no llegó a existir. Ahora `publish(..., session=session)`
  acumula el evento en la sesión y un listener de `after_commit` lo vacía;
  el rollback lo descarta. Efecto lateral: el consumidor puede leer lo que
  escribió el emisor, y un handler que falla se loguea sin romper al
  emisor ni a los demás suscriptores.

### Changed

- **ADR-013 revisado — shadcn/ui en vez de Base UI directo** (2026-07-27):
  las primitivas de interacción del frontend pasan de "Base UI construido a
  mano" a **shadcn/ui** (que corre sobre Base UI — sigue sin Radix). Motivo:
  el objetivo real de negocio es poder editar color y forma por marca
  rápido; shadcn trae un token set semántico (`--primary`, `--muted`,
  `--radius`...) ya cableado a todo su catálogo de componentes, en vez de
  construir ese mismo mecanismo de theming a mano componente por
  componente. shadcn/ui no es una dependencia instalada — el CLI copia el
  código fuente a `components/ui/`, se edita directo. `docs/architecture/adr/ADR-013-arquitectura-frontend.md`,
  `docs/product/frontend-architecture.md`, `docs/prompts/frontend.md`,
  `docs/architecture/tech-stack.md` y `docs/architecture/overview.md`
  actualizados. Sin implementación de código todavía.

- **Una sola jerarquía de errores y un solo mapeo a HTTP** (2026-08-01,
  ADR-017). `NoEncontrado`/`Conflicto`/`ReglaNegocio` pasan a
  `src/shared/errors.py` sobre una base `AppError`; la traducción a HTTP
  vive en `src/core/error_handlers.py` y `users` registra desde su capa
  `api` sus estados propios (401/423/422). Se eliminan las 7 bases por
  módulo, las 8 copias de `_HTTP_STATUS`/`_http()` y 86 `try/except`
  cuyo cuerpo completo era `raise _http(e)` — 251 líneas netas menos en los
  routers. Cierra un bug latente: seis de las ocho copias resolvían por
  `type(err)` exacto, así que una subclase como `PrecioNoDefinido` habría
  devuelto 400 en vez de 409. Conservan su `try/except` los tres endpoints
  que commitean en el camino de error (login fallido, reuso de refresh
  token, intento contado de Factiliza).

- **`purchases` y `accounting` dejan de importar `users.domain`**
  (2026-08-01): la consulta "¿este actor puede aprobar sobre el umbral?"
  pasa por el contrato público
  `users/application/queries_publicas.py::tiene_permiso`, en vez de
  `users.domain.rules` + `UsuarioRepo`. Era la única violación literal de
  "nunca importar el dominio de otro módulo".

### Added

- **Auditoría arquitectónica** (2026-08-01):
  `docs/architecture/audit-2026-08-01.md` — riesgos priorizados con
  severidad, beneficio, costo y recomendación, incluido el detalle de lo
  **descartado** (dividir `rules.py`, dividir `repositories.py`, eventos
  tipados, separar eventos síncronos de asíncronos) y por qué.

- **`tests/test_arquitectura.py`** (2026-08-01, 98 casos): las reglas de
  CLAUDE.md como test. Pureza de `domain` (sin ORM, framework ni `core`),
  `application` sin FastAPI, ningún módulo entrando a otro fuera de su
  contrato público, `core` sin dominio ajeno y `shared` sin mirar hacia
  arriba. Los acoplamientos que la auditoría difiere quedan como
  excepciones nominales: la lista puede encogerse, no crecer en silencio.

- **`tests/test_errores_http.py`** (2026-08-01, 13 casos): fija el mapeo
  unificado, incluidas las subclases que antes caían al 400.

### Removed

- **`regla_aprobacion` retirada** (2026-08-02, migración `b82d4c1f7a35`,
  ADR-014 Addendum): `parametro_empresa` queda como **única** tabla de
  configuración por empresa. La migración copia las filas vigentes como
  parámetros ya aprobados (`valor={"monto": ...}`, atribuidos a `admin`) y
  borra la tabla; se van también el modelo, el repo, los tres endpoints
  `/api/v1/reglas-aprobacion` y el permiso
  `gerencia.gestionar_reglas_aprobacion`. `permiso_requerido` se descarta:
  era informativo, la verificación real siempre la hizo el módulo
  consumidor. `src/shared/aprobaciones.py::umbral_vigente` sobrevive como
  envoltorio tipado (`Decimal`) sobre `parametro_empresa`, así
  `purchases`/`accounting` no cambiaron una línea. Se descarta también la
  FK `parametro_empresa.decision_gerencial_id` prevista en ADR-014: el par
  propuesta/aprobación ya deja ese rastro. La migración de datos se prueba en
  `tests/test_migracion_retiro_regla_aprobacion.py` (copia solo lo vigente,
  no pisa un parámetro ya cargado a mano, monto canónico a 2 decimales).


- **Permiso `gerencia.gestionar_parametros_empresa`** (2026-07-27,
  ADR-014): sembrado en `src/seeders/seed.py` adelantado a la entidad
  `parametro_empresa`, implementada el 2026-08-02 (entrada de arriba).

- **Lote y FEFO en `inventory` — ADR-015** (2026-07-27, RN-VNC-001..003,
  RN-LOT-001): nuevas entidades `lote` (código, vencimiento, origen,
  condición de almacenamiento) y `stock_lote` (saldo y estado por lote),
  con control **opcional por artículo** (`articulo.controla_lote`) — los
  perecibles lo llevan, las servilletas no. Toda salida de un artículo con
  control se reparte por FEFO (vence antes, sale antes; el lote sin
  vencimiento va al final y cae en FIFO) y genera **un movimiento por lote
  tomado**, cada uno con su `lote_id`; un `lote_id` explícito es el
  override del lote sugerido. El lote vencido se bloquea en el momento en
  que el picking lo toca y publica `inventory.lote_vencido_detectado`, más
  un barrido a demanda `POST /inventory/lotes/bloquear-vencidos`. Nuevos
  endpoints `POST /inventory/lotes` y
  `GET /inventory/lotes?almacen_id&sku_id&por_vencer_dias`. La recepción de
  compra transporta `lote_codigo` y `fecha_vencimiento` declarados por el
  proveedor (RN-VNC-002) y producción crea su lote con `origen=produccion`.
  El hub de sucursal replica `lote` y `stock_lote` (ADR-009, 28 recursos):
  sin ellos la venta offline no podría aplicar FEFO. Migración
  `c9a2f4e18b60`. Tests: `tests/test_lotes.py`.

- **Arquitectura frontend — ADR-013** (2026-07-27): Tailwind CSS sobre los
  tokens de marca ya definidos en `globals.css` (`tailwind.config.ts` mapea
  `bg-primary` → `var(--color-primary)`, nunca hex fijo); **Base UI**
  (`@base-ui-components/react`) en vez de Radix para overlays/combobox/dialog
  con accesibilidad no trivial, sin kit ya estilizado (shadcn/ui) encima;
  shell estilo Odoo — home de apps (grilla de módulos) + sidebar dentro de
  cada módulo, ambos filtrados por `permisos` de `GET /users/me` (endpoint ya
  existente, sin cambio de backend), con guard real server-side por módulo
  (el filtro del grid es solo UX). Decide de paso el pendiente de ROADMAP
  "App Android": PWA/responsive, no app nativa. Sin librería de estado
  global (YAGNI); Playwright para e2e de flujos críticos. Solo
  especificación — sin implementación de código. `docs/prompts/frontend.md`
  actualizado con las reglas técnicas.

- **Precio server-side — `lista_precio` + `precio`** (2026-07-27,
  RN-PRC-003/004/005, RN-MDC-003): el PDV deja de enviar
  `precio_unitario`; `crear_venta` lo resuelve por
  marca+sucursal+canal+modalidad+fecha. Entre listas vigentes gana la
  promocional, luego la más específica, luego la de vigencia más reciente
  — al vencer la promoción el precio regular se restaura solo. Sin precio
  vigente la venta responde 409 y el producto no aparece en la carta.
  Nuevos endpoints `POST/GET /sales/listas-precio`,
  `POST /sales/listas-precio/{id}/precios` y `GET /sales/carta`
  (catálogo con precio ya resuelto, lo que renderiza el PDV). `precio` no
  tiene edición: corregir un precio es una lista nueva, auditable.
  Migración `d4b1f0a7c3e9`, que además cierra la FK pendiente
  `medio_pago.lista_precio_credito_id` (RN-MDP-001).
  Tests: `tests/test_precios.py`.

- **Contexto de tenant desde el JWT** (2026-07-27, ADR-004):
  `src/core/tenant.py` + dependencia `get_tenant`. El `empresa_id` y el
  `sucursal_id` de una operación se derivan de los claims del token, no
  del body ni del query string; un recurso de otro tenant responde 403 vía
  un handler único de `FueraDeAlcance` en el app factory. Aplicado a
  `users`, `inventory`, `sales` y `kds`, con helpers de alcance por módulo
  (`*/application/scope.py`). Escape explícito y documentado: un
  superusuario (permiso `*`) sin sucursal asignada puede indicar la
  empresa, necesario para el bootstrap del sistema.
  Tests: `tests/test_tenant_aislamiento.py`.

### Changed

- `POST /api/v1/inventory/movimientos` devuelve una **lista** de
  movimientos en vez de uno solo: una salida FEFO puede repartirse entre
  varios lotes y cada lote es un movimiento propio (ADR-015). El body
  acepta además `lote_id` opcional. Cambio incompatible del contrato,
  todavía sin consumidores (el frontend hoy es login + dashboard).

- `VentaItemIn` (API pública de venta) ya no acepta `precio_unitario` ni
  `descuento`. El lote de sincronización del hub usa un tipo propio,
  `VentaItemSyncIn`, que sí los lleva: una venta ya cobrada offline
  conserva el precio al que se cobró, porque recotizarla en la nube
  cambiaría el monto si la promoción venció entre el corte y el push
  (ADR-009).
- `CategoriaCreate`, `ArticuloCreate` y `MedioPagoCreate` pasan a tener
  `empresa_id` opcional: se toma del JWT, y una empresa ajena da 403.

- **Decisiones de negocio — ranking del buscador y criterio de upsell**
  (2026-07-26, `docs/product/ui-ux.md`): el ranking del buscador se basa
  en historial de uso/patrones detectados (no solo similitud de texto),
  con el objetivo explícito de reducir fricción en versiones futuras a
  medida que el sistema aprende; el dialog de upsell del carrito sugiere
  complementos del producto elegido (ej. bebidas) y/o producto en
  promoción vigente. Solo especificado, implementación pendiente.

- **Spec de UX — buscador contextual y upsell en carrito** (2026-07-26,
  `docs/product/ui-ux.md`): buscador de producto (PDV/Kiosk/web) por
  nombre, por insumo/ingrediente (cruce `receta_item`) y por exclusión
  ("que no tenga X"), con lista de resultados ordenada por relevancia
  cuando no hay match único; vía técnica sugerida: full-text search
  (`pg_trgm`/`tsvector`), sin necesitar IA. Al ir al carrito, dialog de
  productos sugeridos de adición rápida, descartable sin bloquear el
  flujo. Solo especificado, implementación pendiente.

- **Spec de UX — breadcrumb por ruta de usuario y tooltips de formulario**
  (2026-07-26, `docs/product/ui-ux.md`): breadcrumb crece según la
  navegación del usuario (patrón Odoo), no según la jerarquía de la
  funcionalidad — cada eslabón es clicable para volver al punto exacto de
  origen; la navegación jerárquica va por menús desplegables, mecanismo
  separado del breadcrumb. Todo campo de formulario lleva hover explicando
  el término o formato esperado. Solo especificado, implementación
  pendiente.

- **Spec de UX — dialog de personalización de producto en PDV/Kiosk**
  (2026-07-26, `docs/product/ui-ux.md`): seleccionar un producto comercial
  abre un dialog con sus modificadores admitidos (tamaño/combinación/
  extras/restas) para producir una `variante_producto`; cruza con
  RN-PRD-004/005 ya existentes. Solo especificado, implementación
  pendiente (ver ROADMAP — deuda técnica módulo sales).

- **Spec de theming multi-marca, accesibilidad y plataformas** (2026-07-25,
  `docs/product/ui-ux.md`, `docs/prompts/frontend.md`): PDV/Kiosk = mayor
  variación de skin (branding por marca de Grupo Majambo), resto de módulos
  usa Provecho/Majambo; modo daltonismo y tamaño de fuente ajustable como
  preferencia por usuario; táctil obligatorio en Android para
  PDV/Kiosk/KDS/Inventario, resto de módulos PC-first pero responsive. Solo
  especificado, implementación pendiente (ver ROADMAP — Deuda técnica
  transversal).

- **Cumplimiento de pedido — PROC-OPE-002 v1.0** (2026-07-27): cierra el
  pendiente de decisión abierto el 2026-07-14 (qué pasa después de Venta).
  Es **un** proceso del área Operaciones con Preparación y Despacho/Entrega
  como etapas internas, **no** dos procesos: hay un solo resultado y ningún
  artefacto de traspaso entre cocina y despacho; la máquina de estados ya
  implementada (`venta_item.estado_preparacion`) es una sola y las
  pantallas KDS `preparacion`/`despacho` son vistas de ella; y "Producción"
  ya nombra la cocina de producción central (`PROC-PRD-001`), por lo que
  reusar `PRD` para la cocina de sucursal rompía la nomenclatura.
  Especificación completa: registro maestro en `process-nomenclature.md`,
  proceso en `workflows.md`, `CU-OPE-001/002/003` por modalidad en
  `use-cases.md`, **RN-CUP-001..012** en `business-rules.md`, máquina
  oficial en `state-machines.md`, entidad `entrega` en `data-model.md`.
  **Código**: `sales/application/cumplimiento.py::registrar_entrega` +
  `POST /api/v1/sales/ventas/{id}/entrega` (permiso propio
  `sales.entregar_pedido`, rol nuevo `despachador`) — exige todos los ítems
  en `listo` (RN-CUP-005), idempotente, publica `sales.venta_entregada`.
  Eventos nuevos en el catálogo: `sales.venta_entregada` y
  `marketing.encuesta_enviada`; de paso se regulariza `sales.pedido_listo`,
  que el KDS publicaba desde 2026-07-25 sin fila en `events.md`. Sin
  migración: el enum ya tenía `entregado`. `tests/test_kds.py` +5 casos.
- **Organización real del Grupo Majambo en el seeder** (2026-07-27): el
  seeder creaba grupo, empresa y marca, pero ninguna sucursal ni almacén —
  el ERP arrancaba sin los locales sobre los que opera. Ahora siembra la
  estructura completa y real: empresa **Inversiones Turísticas y
  Alimentarias Majambo EIRL** (RUC 20450311520, domicilio fiscal Jr. Ramón
  Castilla 248 - Tarapoto, zona `amazonia_ley27037`), la **licencia** de la
  marca Charlie's Pizzas a esa empresa (`licencia_marca` nunca se había
  sembrado, y `sucursal.empresa_id` existe justamente vía licencia), las
  sucursales **CH1** (Jr. Ramón Castilla 248) y **CH2** (Jr. Lamas 299),
  ambas `activa` y `alquilada` — tenencia confirmada con el usuario, decide
  predial/arbitrios (RN-IMP-004) — y el almacén central **WH1** (Jr. Ramón
  Castilla 248, `sucursal_id` NULL: el central no cuelga de ninguna
  sucursal, las abastece). El domicilio fiscal se sincroniza en cada corrida
  porque `_get_or_create` no toca lo ya creado y el valor sembrado antes era
  el genérico "Tarapoto, San Martín". `tests/test_seed_organizacion.py`
  (6 casos, incluida la idempotencia). Los almacenes de sucursal de CH1/CH2
  no se siembran: no fueron pedidos y su stock mínimo/máximo depende de
  datos de operación que aún no existen.

- **Modo offline del PDV — fase 2: motor de sync del hub** (2026-07-27):
  ADR-009 (sección "Fase 2"), migración `e5c47b90f118`. El hub de sucursal
  ya no solo sabe *si* tiene internet: ahora sincroniza de verdad. Un ciclo
  (`src/core/sync/motor.py`, proceso aparte `python -m src.core.sync.runner`,
  servicio `sync` del `docker-compose.hub.yml`) **empuja y después jala**,
  en ese orden y no al revés: si jalara primero, el hub sobreescribiría su
  stock con el de una nube que todavía no sabe nada de las ventas del
  corte. Corolario que evita un bug caro: **el hub no empuja movimientos de
  inventario** — el listener de la nube los genera al recibir la venta, y
  empujarlos además contaría el consumo dos veces.
  - **Cambio previo que pedía la fase 1, hecho**: `crear_venta`,
    `registrar_pago` y `registrar_movimiento` aceptan un `id` opcional
    generado por el cliente (sin migración: `UuidPkMixin` genera el UUID en
    Python). Así una venta conserva su identidad entre hub y nube, sin
    tabla de mapeo. Expuesto también en `POST /sales/ventas` y
    `/pagos`, que es lo que permitirá a las tres apps (web/Android/PC)
    crear la venta sin depender del servidor para tener su id.
  - **`GET /sync/pull` + `POST /sync/push`** (permisos `sync.leer` /
    `sync.empujar`, rol `hub_sucursal`) en vez de reusar los endpoints
    públicos como preveía la fase 1. Al implementarlo no alcanzaban: no
    exponen los campos que el hub necesita (`empaque_id`,
    `modalidades_empaque`, y directamente no hay endpoint de `receta`,
    `sku` ni `punto_venta`), ninguno es incremental por `updated_at`, y el
    `pin_hash` —sin el cual nadie se autentica offline— no puede vivir en
    `UsuarioOut`. Del lado ascendente, `POST /sales/ventas` toma el
    `usuario_id` del JWT (todas las ventas quedarían a nombre del hub) y
    recalcula `fecha_orden`/`numero_orden`, con lo que el número que el
    cliente vio impreso no coincidiría. **El push no escribe filas crudas**:
    ejecuta los mismos casos de uso de `sales`, con sus validaciones,
    idempotencia y eventos — la objeción que hundió a la replicación lógica
    de Postgres en el ADR sigue respetada. El tenant sale de la cuenta de
    servicio (exactamente una sucursal), nunca de un parámetro.
  - **Contrato declarativo por módulo**: cada módulo declara sus
    `RecursoSync` en `application/sincronizacion.py` (modelo, campos que
    viajan, filtro de tenant y por qué el hub lo necesita) y
    `core/sync/registro.py` los ensambla en orden de dependencia — igual
    que `core/app.py` ensambla routers. El motor no conoce ninguna entidad
    de negocio. 24 recursos: organización, RBAC, catálogo de inventario,
    stock y catálogo comercial. `campos` es explícito: agregar una columna
    al modelo no la manda al hub sin que alguien lo decida.
  - **`usuario.pin_hash` viaja; el lockout no.** El hash Argon2id es
    indispensable para validar el PIN durante un corte (es la única salida
    de un hash de credencial en la API, acotada a los usuarios de esa
    sucursal); `intentos_fallidos`/`bloqueado_hasta` son estado vivo de
    cada lado y replicarlos bloquearía a un cajero en el local por intentos
    hechos contra la nube. `persona` viaja recortada (nombre y documento,
    sin domicilio/teléfono/email) — minimización de datos sobre hardware
    que vive en un local.
  - **Tabla `sync_watermark`** (una fila por recurso y dirección, no un
    outbox): la fase 1 suponía que bastaba `max(updated_at)` local, y no
    basta — el hub *escribe* localmente algunas de las tablas que replica
    (cada venta mueve `stock`), y la dirección ascendente necesita memoria
    durable de qué se empujó. Guarda también el último error. Un recurso
    que falla no avanza su marca y se reintenta entero; los demás siguen.
  - **`/health/sync` ahora muestra el avance por recurso** (marca, último
    OK, último error), leído de la base porque el runner es otro proceso.
    `GET /sync/recursos` documenta el contrato vigente.
  - **`sales.tasks.encolar` es no-op en un hub**: sin esa guarda, cobrar
    durante un corte intentaría hablarle a un broker que en el Raspberry Pi
    no existe (el hub corre sin Celery/Redis por diseño).
  - **Alta de la cuenta de servicio**: `python -m src.seeders.hub
    --sucursal <uuid> --username hub_<local>`, idempotente y apto para
    producción (a diferencia del seeder de desarrollo).
  - `tests/test_sync_motor.py` (24 casos) monta **las dos bases** —nube y
    hub— y sincroniza entre ellas por la API real vía `TestClient`
    autenticado: carga inicial, login offline contra el hash replicado,
    pull incremental, aislamiento entre sucursales, venta/cobro/anulación
    reproducidos con su identidad, convergencia de stock, ítem rechazado
    que no arrastra al lote, y recurso caído que no cancela a los demás.
    En el camino apareció otra vez el desfase de microsegundos de SQLite
    (`CURRENT_TIMESTAMP` sin ellos vs. el bind de Python con ellos, ya
    documentado en el dashboard de caja): acá **sí** se resolvió en el
    código (`core/sync/tiempo.para_dialecto` ensancha el borde un segundo
    solo en SQLite) porque el `>=` afectado es una consulta de producción,
    no una aserción de test; en Postgres —la base real de hub y nube— no
    aplica, y como todo el sync es idempotente, reprocesar el borde no
    cuesta nada mientras que perderlo sería perder una venta.

- **Dashboard gerencial mínimo + slice de caja (PROC-CTB-001/002)**
  (2026-07-26): ADR-012. `GET /api/v1/dashboard/resumen`
  (`src/core/dashboard_router.py`, permiso `dashboard.leer`): ventas del
  día (cantidad+total), stock bajo mínimo, cajas abiertas — vive en `core`
  y no en un módulo de negocio porque compone lecturas de `sales`,
  `inventory` y `accounting` sin importar el dominio de ninguno directo
  (mismo patrón que `sales.queries_publicas.listar_clientes_para_analisis`,
  extendido con `resumen_ventas_del_dia` y `puntos_venta_de_empresa`;
  `inventory.contar_bajo_minimo` nuevo). Construir esto expuso dos huecos
  reales: `sales` no tenía ningún endpoint de listado de ventas, y
  `accounting` tenía los modelos de caja (`apertura_caja`/`cierre_caja`/
  `arqueo`, migrados desde 2026-07-20) sin ninguna capa de aplicación —
  PROC-CTB-001/002 nunca se había construido. **Slice mínimo, no el
  proceso completo**: `accounting.application.caja` abre, cierra y arquea
  con **reconciliación real** — el cierre calcula
  `monto_esperado = monto_apertura + efectivo cobrado desde la apertura`
  (vía el contrato público de `sales`, `total_efectivo_cobrado` — primera
  vez que un módulo consulta a otro en tiempo real para una escritura
  propia, no solo para un reporte) y lo compara contra el conteo físico;
  sin esa cuenta, un cierre sería un formulario sin ningún valor de
  control. Deliberadamente fuera de esta fase: verificación de series de
  POS y denominaciones (RN-POS-009..013), relevo autenticado por PIN propio,
  `custodia_efectivo` como máquina de estados — ese es un slice de negocio
  del tamaño de los ya construidos para `sales`/`purchases`/`production`,
  no algo para colar bajo "hacer un dashboard". Permisos nuevos:
  `dashboard.leer`, `accounting.caja_operar` (rol `cajero` — abre/cierra su
  propia caja sin permisos de administración), `accounting.arqueo_registrar`
  (`supervisor`/`contador`). **Primer frontend real**: login por PIN +
  pantalla de dashboard en Next.js/React, reemplazando el scaffold por
  defecto. `tests/test_dashboard_caja.py` (16 casos) — incluye un caso de
  flakiness real detectado y corregido: SQLite guarda `created_at` sin
  microsegundos pero SQLAlchemy los agrega al enlazar un `datetime` de
  Python, así que dos eventos en el mismo segundo de reloj comparan mal
  como texto (`"...25" < "...25.000000"`); Postgres (columna timestamp
  real) no tiene este problema — se documentó y se resolvió a nivel de
  prueba, no tocando la lógica de producción.

- **Protección de datos personales — derechos ARCO (Ley 29733)**
  (2026-07-26): ADR-011, migración `dad43729501d`. `docs/security/proteccion-datos-personales.md`
  nuevo: qué datos personales trata el ERP y dónde viven (`persona` es la
  fuente única — RN-GEN-007, casi todo ARCO se resuelve tocando una sola
  entidad), derechos ARCO y su estado (Acceso/Rectificación ya existían;
  Oposición queda como política sin contraparte técnica porque no hay
  marketing automatizado todavía), plazos de conservación por tipo de dato,
  medidas de seguridad ya vigentes (referenciadas a `security.md`/ADR-006/
  ADR-007, no reconstruidas), proceso de brecha de seguridad, y una lista
  separada de pendientes que son **acción del usuario, no de código**
  (registro ante la ANPD, aviso de privacidad público, designación de
  responsable, plazos de retención confirmados con contador/abogado).
  **Cancelación implementada como anonimización irreversible**, no `DELETE`:
  `persona` la referencian `trabajador`/`cliente`/`usuario`, un borrado
  físico rompería esas FK o dejaría planillas/comprobantes sin sustento
  legal (retención tributaria/laboral que prevalece mientras esté vigente).
  `POST /api/v1/personas/{id}/anonimizar` (permiso dedicado
  `personas.anonimizar`, distinto de `users.gestionar` — una acción
  irreversible no hereda un permiso de CRUD normal) sobrescribe
  `nombres`/`apellidos`/`numero_documento`/`fecha_nacimiento`/`domicilio`/
  `telefono`/`email` (RN-PER-007); `numero_documento` es `UNIQUE`, se
  reemplaza por un valor derivado del propio `id`, no un texto fijo. El
  `audit_log` de la acción registra qué campos se anonimizaron y el motivo,
  **nunca el valor real anterior** — guardarlo ahí habría dejado la PII
  accesible para siempre, vaciando de sentido la anonimización.
  `PATCH /personas/{id}` sobre una persona ya anonimizada ahora da 409: no
  hay dato real que rectificar. Sin bloqueo automático cross-módulo (p. ej.
  contra `trabajador.estado=activo`) a propósito — `users` es el módulo más
  foundational del ERP y consultar hacia `rrhh` invertiría la dirección de
  dependencia que todo el código ya asume; se documenta un checklist manual
  en su lugar. `docs/domain/business-rules.md` (RN-PER-007),
  `docs/architecture/data-model.md` y `docs/foundation/glossary.md`
  (Derechos ARCO, Anonimización) actualizados. `tests/test_users_persona.py`
  +5 casos.

- **Contrato OpenAPI exportado y verificado en CI** (2026-07-26): ADR-010.
  `src/core/openapi_export.py` (`python -m src.core.openapi_export`) escribe
  `docs/architecture/openapi.json` desde la app real — determinista (claves
  ordenadas, salto de línea final) para que el diff entre corridas refleje
  solo cambios reales del contrato. `ci.yml` lo regenera y compara contra el
  commiteado: un endpoint que cambió sin actualizar el contrato falla el PR
  que lo causó, no cuando Android/PC/una integración se entera por las
  malas. `TAGS_METADATA` nuevo en `src/core/app.py` describe los 13 tags de
  la API (antes FastAPI solo agrupaba por nombre); un test falla si aparece
  un tag sin su entrada. `app.version` ahora usa `settings.app_version` en
  vez de un `"0.1.0"` hardcodeado aparte (duplicación encontrada de paso).
  **Dos afirmaciones falsas corregidas en `api-guidelines.md`**, detectadas
  al auditar la doc contra el código real: `idempotency_key` siempre viajó
  como **campo del body**, la guía decía "header"; ningún endpoint de
  listado pagina, la guía prometía `{items, total, page, page_size}` — se
  documentó el formato real (array plano) y la paginación real queda en
  deuda técnica en vez de fingirse implementada. `tests/test_openapi_export.py`
  (7 casos).

- **Modo offline del PDV — diseño y plumbing base (fase 1)** (2026-07-26):
  ADR-009. Arquitectura de **hub local dedicado por sucursal** (mini-PC/
  Raspberry Pi, siempre encendido): corre la **misma imagen** del backend
  contra su **propio Postgres local** — no una versión recortada. Los tres
  clientes de PDV (web, Android, PC) le hablan siempre al hub por LAN,
  nunca directo a internet, resolviendo el requisito de "equipos en la
  misma red local se ven entre sí durante un corte". Alcance offline:
  catálogo, ventas/cobro/KDS y —por necesidad lógica, no solo lo pedido—
  RBAC/usuarios (sin eso nadie se autentica en el hub) e inventory/stock (el
  listener `sales.venta_confirmada` ya corre en el mismo proceso). El sync
  hub↔nube **reusa la propia API REST** existente en vez de inventar un
  protocolo de replicación: descendente por `updated_at` (ya presente vía
  `TimestampMixin`), ascendente reintentando las mismas llamadas idempotentes
  que el hub ya ejecutó offline (`idempotency_key` ya exigida en ventas/
  pagos). Comprobantes se crean `pendiente` en el hub pero **la emisión a
  Factiliza ocurre solo en la nube**, tras sincronizar — el hub no necesita
  Celery/Redis/worker. `src/core/sync/estado_conexion.py`: detector de
  conectividad con racha de fallos antes de declarar `offline` (un timeout
  puntual no basta) y recuperación inmediata al primer éxito;
  `GET /health/sync` — siempre 200 (a diferencia de `/health/ready`, estar
  offline es el modo de diseño del hub, no un fallo: sacarlo de rotación por
  eso sería contraproducente). `DEPLOYMENT_MODE=hub` con validación de
  config que aborta el arranque si falta algo (sucursal, URL de sync,
  credenciales de la cuenta de servicio). `docker-compose.hub.yml` +
  `.env.hub.example` nuevos. **Fase 2 (motor de sync real) queda
  explícitamente pendiente**: requiere primero extender `crear_venta`/
  `registrar_pago`/movimientos para aceptar un `id` client-generado (ya
  posible sin migración — `UuidPkMixin` genera el UUID en Python, no en la
  base), evitando así una tabla de mapeo hub-id↔nube-id. Fix de paso en
  `.gitignore`: `.env.hub.example` quedaba tapado por la regla `.env.*`, el
  mismo tipo de trampa que `backups/` en el commit anterior.
  `tests/test_offline_hub.py` (17 casos).

- **Entrega continua — imagen en GHCR y CI endurecida** (2026-07-26):
  `ci.yml` gana tres verificaciones que no existían. **Cabeza única de
  Alembic**: dos ramas que crean migraciones en paralelo hacían fallar
  `upgrade head` durante el despliegue, no en el merge que lo causó.
  **Job `imagen`**: nadie comprobaba que el `Dockerfile` siquiera
  construyera — ahora además se levanta el contenedor y se le pide `/health`,
  lo que valida el `CMD`, el usuario sin privilegios y el `HEALTHCHECK`.
  **`pip-audit`** informativo (no bloquea: un aviso en una dependencia
  transitiva no puede frenar un arreglo urgente en caja). Se suman caché de
  pip/npm y `npm ci` en vez de `npm install`. `release.yml` nuevo: cada push
  a `main` publica la imagen en **GHCR**, y los tags `v*` publican además la
  versión exacta — GHCR y no Docker Hub porque autentica con el
  `GITHUB_TOKEN` del propio workflow, sin secreto que rotar.
  **`docker-compose.prod.yml` nuevo**: el `docker-compose.yml` existente es
  solo de desarrollo (monta el código, `uvicorn --reload`, Postgres con
  contraseña de juguete) y desplegarlo habría publicado esa configuración; el
  de producción no incluye base de datos (gestionada vía `DATABASE_URL`),
  publica la API solo en `127.0.0.1` y no expone el puerto de Redis. El
  `Dockerfile` pasa a correr como usuario sin privilegios (uid 10001) y trae
  `HEALTHCHECK`. **El despliegue sigue siendo manual y documentado**
  (ADR-008): automatizar por SSH contra un servidor que todavía no existe
  daría automatización imposible de probar. `alembic upgrade head` queda como
  paso explícito del despliegue y no al arrancar la aplicación — con varias
  réplicas todas migrarían a la vez y una migración fallida dejaría el
  contenedor en bucle de reinicio en lugar de fallar con un error legible.

- **Chequeos de salud y alertas** (2026-07-26): `src/core/health.py` +
  `health_router.py`. `/health` queda como **liveness** puro, sin tocar
  dependencias — si fallara por la base de datos, el orquestador reiniciaría
  en bucle un proceso sano. `/health/ready` es **readiness**: base de datos
  (crítica → `caido` + 503), Redis y profundidad de la cola de tareas
  (degradan a 200 con estado `degradado`, porque sin Redis el rate limit
  falla abierto y los comprobantes esperan, pero la caja tiene que seguir
  vendiendo). `/health/backups` va aparte a propósito: que falte un backup es
  grave, pero devolver 503 en readiness sacaría la API de rotación y dejaría
  al restaurante sin vender. Ese endpoint cubre el caso que el reporte de
  errores **no puede** cubrir — un backup que falla avisa por Sentry, pero
  uno que nunca corrió (cron desactivado, servidor reinstalado) no genera
  ningún evento; solo se detecta preguntando por la frescura del archivo
  (umbral 26 h, con margen sobre el cron diario). **El ERP no alerta por su
  cuenta**: expone estado y un monitor externo avisa (ADR-007) — alertas que
  viven en el servidor monitoreado dejan de avisar justo cuando ese servidor
  cae. Los tres endpoints son públicos (un monitor no puede autenticarse) y
  devuelven estados, nunca hostnames, DSN ni errores crudos. Los endpoints se
  extrajeron a su propio router: `create_app` había superado el umbral de
  complejidad de ruff. `tests/test_health.py` (20 casos).

- **Observabilidad — logs estructurados y reporte de errores** (2026-07-26):
  `src/core/logging_config.py` y `src/core/sentry.py`. Los logs salen en JSON
  (una línea por evento) en producción y en texto legible en local, con los
  **tres flujos** que `security.md` ya declaraba —`app`, `seguridad`,
  `auditoria`— derivados del nombre del logger, sin parámetro extra en cada
  llamada. **Correlación por `request_id`**: se genera por request (o se
  respeta el `X-Request-ID` entrante, para seguir una traza que venía del
  proxy), viaja en un `contextvar`, sale en la cabecera de toda respuesta y
  se devuelve en el cuerpo del error 500 — sin él, un "me dio error" de un
  cajero no se cruza con ningún log. **Redacción** de PIN, contraseñas,
  tokens y cabeceras `Authorization`/`Cookie` antes de escribir el log y
  antes de salir hacia Sentry (`send_default_pii=False`, Ley 29733). El
  flujo `seguridad` estrena usuarios reales: login fallido, bloqueo de
  cuenta, reuso de refresh token y rate limit superado. Reporte de errores
  activo en los tres componentes que hasta ahora fallaban en silencio —
  `api`, `worker` (señal `celeryd_init`: un comprobante que agotaba
  reintentos contra Factiliza no avisaba a nadie) y `backups` (un fallo de
  madrugada quedaba solo en el log del cron). Sirve igual para Sentry o
  GlitchTip autoalojado; sin `SENTRY_DSN` no se envía un solo byte.
  `sentry-sdk` va en dependencias base a propósito: como extra opcional, un
  despliegue que lo olvidara se quedaría justo sin lo que avisa que algo
  falla. `configurar_logging` etiqueta su handler y retira solo el propio,
  para no desconectar a un colector externo (ni a pytest).
  `tests/test_observabilidad.py` (33 casos).

- **Backups automáticos con restauración probada** (2026-07-26):
  `src/backups/backup.py` (`python -m src.backups.backup`) encadena dump →
  verificación → restauración de prueba → copia externa → purga, y sale con
  código 1 si algo falla para que el cron pueda alertar. `pg_dump
  --format=custom` con la contraseña por `PGPASSWORD` (nunca en `argv`, que
  `ps` expone). La verificación comprueba la firma del dump y que
  `pg_restore --list` traiga las tablas críticas — detecta el dump truncado
  por disco lleno, que a simple vista parece sano. Con
  `BACKUP_VERIFY_DATABASE_URL` restaura de verdad contra una base desechable
  y cuenta filas; se niega a restaurar sobre la base de origen, porque
  `pg_restore --clean` borra el esquema destino. La purga por retención
  **nunca borra el backup más reciente**, aunque esté vencido: si el cron
  llevaba meses caído, borrarlo dejaría al ERP sin ninguna copia. Copia a S3
  (o compatible) detrás de credenciales, con `boto3` como dependencia
  opcional `[backups]` para no cargarla en la imagen de la API. **Frecuencia
  revisada de mensual+incremental a diaria con retención de 30 días**
  (`glossary.md`, `security.md`): un negocio que vende todos los días no
  puede perder un mes de caja, y el dump completo pesa megas. Runbook de
  restauración y línea de cron en `docs/engineering/devops.md`.
  `tests/test_backups.py` (17 casos). Verificación pendiente: el camino feliz real (pg_dump contra Postgres) no se pudo ejecutar en la máquina de desarrollo — falta `postgresql-client`.

- **Facturación electrónica — Factiliza (SUNAT)** (2026-07-26): migración
  `b3d7f21ac094`. **Cambio de proveedor: Factiliza reemplaza a Nubefact**
  (decisión del usuario); las columnas `comprobante.estado_nubefact`/
  `respuesta_nubefact` se sustituyen por `estado_emision`
  (`no_aplica|pendiente|aceptado|rechazado|error`), `hash_proveedor`,
  `detalle_emision`, `intentos_emision` y `respuesta_proveedor`. Adaptador
  nuevo en `src/shared/integrations/factiliza/`: `client.py` (`POST
  /invoice/send`, Bearer) y `mapper.py` (traducción a catálogos SUNAT 01/
  06/07/51/52 + leyenda 1000 en letras vía `num2words`). Cola nueva:
  `src/core/celery_app.py` + tarea `sales.emitir_comprobante` con reintento
  exponencial, y servicio `worker` en `docker-compose.yml`.
  `sales.registrar_pago` crea el `comprobante` `pendiente` al cubrirse el
  total y el router encola el envío **después del commit**; aceptado →
  venta `facturada` + `sales.comprobante_emitido`; rechazo de SUNAT se
  guarda como veredicto sin reintentar; fallo de transporte reintenta.
  Boleta vs factura por `rules.tipo_comprobante` (factura solo con cliente
  jurídico + RUC; anónimo → `CLIENTES VARIOS`). **IGV desglosado hacia
  atrás** desde el precio de carta, y **exoneración automática** para
  empresas de zona `amazonia_ley27037` (RN-IMP-001 — el caso real de
  Majambo en Tarapoto). Sin `FACTILIZA_TOKEN` la emisión queda desactivada
  y los comprobantes se acumulan pendientes: la caja nunca se bloquea
  (RN-COM-003). Permiso `sales.emitir_comprobante` + endpoints
  `GET /ventas/{id}/comprobante` y `POST /comprobantes/{id}/reintentar`.
  Dependencias nuevas: `httpx` (pasa de dev a runtime), `num2words`.
  `tests/test_facturacion_electronica.py` (23 casos).

- **Endurecimiento de producción — rate limit, secretos y HTTPS**
  (2026-07-26): `src/core/rate_limit.py` nuevo — límite por IP con contador
  en Redis (ventana fija), aplicado a `/auth/login` y `/auth/refresh`
  (10/min configurable); el lockout por cuenta no frenaba a quien rota
  usernames desde una misma IP. Fail-open si Redis no responde: una caída de
  Redis no puede dejar sin operar al restaurante. `settings` valida la
  configuración al arrancar y **aborta** con `ENVIRONMENT=production` si
  `JWT_SECRET` es el placeholder o mide menos de 32 caracteres, si
  `DEBUG=true`, si `DATABASE_URL` conserva la contraseña por defecto o si
  `ALLOWED_HOSTS`/`CORS_ORIGINS` quedaron en `*`. `create_app` suma
  `TrustedHostMiddleware`, CORS con orígenes explícitos (antes no había CORS:
  el frontend no podía llamar a la API), cabeceras `X-Content-Type-Options`/
  `X-Frame-Options`/`Referrer-Policy` en toda respuesta, `HSTS` solo en
  producción, y `/docs` + `/openapi.json` deshabilitados en producción.
  Dockerfile arranca uvicorn con `--proxy-headers` (detrás de nginx la IP
  real llega en `X-Forwarded-For`; sin esto el rate limit y el `audit_log`
  registraban la IP del proxy). `docker-compose.yml` toma la contraseña de
  Postgres de `POSTGRES_PASSWORD`. Runbook de rotación de credenciales y
  custodia de `.env`, y guía de despliegue tras nginx/Caddy, en
  `docs/engineering/devops.md`; `docs/security/security.md` actualizado.
  `tests/test_security.py` (13 casos).

- **`rrhh`: slice completo — ciclo laboral** (2026-07-25): migración
  `9e1b6a4c7d23`, 12 tablas nuevas sobre `trabajador` (que solo tenía modelo,
  sin capa de aplicación). `application/trabajadores.py` completa el ciclo
  crear/actualizar/cesar (RN-PER-002: `locacion_servicios` fuerza
  `registra_asistencia=false`). `contratos.py`: `contrato_laboral`
  borrador→firmado→finalizado (RN-RRHH-012). `postulantes.py`: exige
  `consentimiento_datos` antes de guardar CV (RN-PER-004). `socios.py`:
  participación societaria. `nomina.py`: `boleta_pago`/`liquidacion_bss`
  idempotentes por `idempotency_key` (RN-RRHH-001/003, flag
  `dentro_de_plazo` de 48h). `disciplina.py`: `memorandum`/`amonestacion`/
  `acta`/`certificado_trabajo` (RN-RRHH-002/004/007). `permisos.py`:
  `solicitud_permiso` pendiente→aprobada/rechazada (RN-RRHH-005).
  `capacitacion.py`: `pacto_permanencia` con reembolso proporcional al
  tiempo no cumplido (RN-RRHH-006). `asistencia.py`: marcar entrada/salida,
  bloqueado para trabajadores que no registran asistencia. 11 permisos
  `rrhh.*` nuevos, rol `rrhh_admin`, `supervisor` gana lectura/aprobación de
  permisos y marcado de asistencia. Constante `rrhh_rmv_vigente` en
  settings (RN-PER-001). Endpoints bajo `/api/v1/rrhh`. `tests/test_rrhh.py`
  (17 casos). Diferido: ver ROADMAP — eventos `rrhh.*` sin consumidor
  todavía, `contrato`/`solicitud` transversales, cálculo automático de
  PLAME.

- **Pago a proveedor (PROC-CTB-003) — tesorería en `accounting`** (2026-07-25):
  migración `cbf904a9fc1b` (`movimiento_dinero`). `feat(purchases)`: nuevo
  `application/comprobantes.py::dar_conformidad_comprobante` (permiso
  `purchases.dar_conformidad`) registra el `comprobante` recibido
  (transversal, `shared`), lo liga a la última `recepcion_compra` de la OC
  y publica `purchases.comprobante_conforme` (empresa_id, condición de
  pago, `sujeto_spot`/`porcentaje_deteccion`, monto). `feat(accounting)`:
  `application/pagos.py` — `registrar_pago` encola un `movimiento_dinero`
  `pendiente` (idempotente por `comprobante_id`, RN-CTB-008), `ejecutar_pago`
  exige permiso `accounting.pago_gestionar` y revisa el umbral configurable
  (`regla_aprobacion`, código `pago_umbral`, RN-CTB-005 — sobre el umbral
  exige además `accounting.pago_aprobar`) antes de generar el asiento vía
  `regla_asiento` (evento `accounting.pago_ejecutado`; sin mapeo
  configurado, el pago igual se ejecuta y el asiento se omite),
  `rechazar_pago` cierra la cola sin ejecutar. Nuevo helper compartido
  `asientos.crear_asiento_automatico_si_hay_regla` (usado también por
  `application/listeners.py`, dedup de la búsqueda de `regla_asiento`).
  Endpoints `/api/v1/accounting/pagos-proveedor` (registrar, listar,
  ejecutar, rechazar) y `/api/v1/purchases/ordenes-compra/{id}/conformidad-comprobante`.
  Roles: `comprador` gana `purchases.dar_conformidad`; `contador` gana
  `accounting.pago_gestionar`; `supervisor` gana `accounting.pago_aprobar`.
  Tests en `tests/test_accounting.py`. Deuda: detracción SPOT se calcula
  pero el asiento no la desglosa en cuenta propia; `purchases` no marca la
  OC como pagada; `rechazar_pago` no libera el comprobante para reintentar
  — ver ROADMAP.
- **Módulo `accounting` — slice core (libro contable)** (2026-07-25): migración
  `5402d99333fa` (`cuenta_contable`, `periodo_contable`, `asiento`,
  `asiento_linea`, `regla_asiento`) aplicada. Endpoints `/api/v1/accounting`:
  plan de cuentas (permiso `accounting.cuenta_administrar`), abrir/cerrar
  periodo contable (`accounting.periodo_administrar`, RN-CTB-010), asiento
  manual con cuadre obligatorio debe=haber (`accounting.asiento_manual`,
  RN-CTB-001) y anulación por asiento inverso — nunca borra/edita
  (RN-CTB-002). `regla_asiento` (nuevo): mapeo configurable evento→cuentas
  por empresa, mismo criterio que `regla_aprobacion` (RN-CTB-011: sin regla
  configurada, el asiento automático se omite y loguea, nunca bloquea el
  proceso de origen). **Listener** (`application/listeners.py`) genera
  asiento automático para los 3 eventos que sus módulos de origen ya
  publican en código: `purchases.oc_emitida`, `purchases.compra_recibida`,
  `sales.venta_confirmada` — se agregó `empresa_id` al payload de
  `oc_emitida` y `total` al de `venta_confirmada` (campos aditivos,
  `events.md` actualizado). Rol semilla `contador`. Tests en
  `tests/test_accounting.py`. Deuda registrada en ROADMAP (resto de eventos
  aún no publicados por sus módulos, pago a proveedor, conciliación
  bancaria, arqueo backend, ciclo de caja sin conectar al libro contable,
  activo fijo/ITAN).
- **Persona CRUD + lock optimista + matriz de aprobaciones + contrato
  público de lectura** (2026-07-25): migración `af8a246e2c25`.
  - `feat(users)`: CRUD de `persona` sin Delete (`POST/GET/PATCH
    /api/v1/personas`, permiso `users.gestionar`) — antes solo se creaba
    de rebote vía trabajador/cliente/proveedor. `PATCH` exige `version`
    vigente (lock optimista, `VersionedMixin` nuevo en
    `src/core/model_base.py`): dos ediciones concurrentes ya no se pisan
    en silencio, la segunda recibe 409.
  - `feat(shared)`: `regla_aprobacion` (nuevo, `src/shared/`) — la matriz
    de aprobaciones deja de ser solo un documento con `[[COMPLETAR]]`;
    umbral de OC de `purchases` migrado a leerla (con fallback al valor
    semilla de config si la empresa no configuró ninguna fila). Admin en
    `/api/v1/reglas-aprobacion`, permiso
    `gerencia.gestionar_reglas_aprobacion`.
  - `feat(sales)`: primer contrato público de lectura cross-módulo del
    repo (`application/queries_publicas.py`) — `GET /api/v1/sales/clientes`
    expone `cliente` (join con `persona` si es natural) para que
    `marketing`/`comercial` lo consuman sin importar el dominio de
    `sales`, permiso `sales.leer_clientes_externos`. Patrón documentado en
    `docs/architecture/events.md` para replicar cuando `inventory`
    implemente `solicitud_insumos` (caso `purchases` ↔ `inventory`, hoy
    bloqueado).
  - Tests: `tests/test_users_persona.py` (CRUD + lock optimista),
    `tests/test_sales_clientes_publico.py`, nuevo caso en
    `tests/test_purchases.py` (override de umbral por empresa).
- **Módulo `production` — slice core** (2026-07-25): migración
  `f78501175fba` (orden_produccion, consumo_produccion_item,
  receta.articulo_id) aplicada. Construido antes de tiempo (primera
  cocina real planeada 2027) a pedido explícito del usuario, mismo
  patrón slice-por-slice. `receta.articulo_id` nuevo (nullable) liga una
  receta a la subreceta que produce — separado del uso existente de
  `producto_comercial.receta_id`. Endpoints
  `/api/v1/production`: crear orden ad-hoc (sin plan/cronograma),
  registrar consumo real de insumos, completar con resultado de control
  de calidad (`conforme`/`no_conforme_reprocesado`/`no_conforme_desechado`)
  y costeo automático (`costo_insumos` + `costo_mano_obra` vía tarifa
  configurable `production_costo_hora_mano_obra` → `costo_real_unitario`).
  Desecho exige merma + motivo + evidencia (RN-PRD-015). **Listeners en
  inventory**: `consumo_registrado` descuenta insumos,
  `orden_completada` suma el producto terminado y recalcula su
  `costo_promedio` (mismo patrón que `purchases.compra_recibida`). Rol
  semilla `jefe_cocina`. Sin migración generada aún. Tests en
  `tests/test_production.py`. Deuda registrada en ROADMAP (cronograma,
  checklist de inocuidad, reporte consolidado, reporte de escalamiento
  real, merma→accounting, lote/trazabilidad, subrecetas anidadas).
- **Módulo `purchases` — slice core** (2026-07-25): migración `4ff85f833b29`
  (proveedor, orden_compra, orden_compra_item, recepcion_compra,
  recepcion_item) aplicada a la BD dev (Supabase). Endpoints
  `/api/v1/purchases`: CRUD de proveedores (natural liga a `persona`,
  mismo party model que `cliente`, RN-GEN-007; jurídico con razón
  social/RUC propios), ciclo de OC tipo `insumo` (crear borrador →
  emitir → recibir total/parcial → anular), todo con idempotencia.
  Emitir exige `purchases.aprobar` si el total supera el umbral
  configurable `purchases_umbral_aprobacion_oc` (semilla: 2000). Eventos
  `purchases.oc_emitida` / `compra_recibida` / `oc_anulada`. **Listener
  en inventory**: `compra_recibida` suma stock en el almacén destino y
  recalcula `articulo.costo_promedio` (promedio ponderado). Rol semilla
  `comprador`. Tests en `tests/test_purchases.py`. Deuda registrada en
  ROADMAP (cotización, OC tipo `activo` + `requerimiento_activo`,
  compra_directa + caja chica, evaluación de proveedor automática,
  comprobante recibido, devolución a proveedor).
- **Módulo `sales` — KDS** (2026-07-25): migración `7672566bf189` —
  `kds_pantalla` (pantallas por sucursal, tipo preparación/despacho, filtro
  por categorías de producto comercial), `venta_item.estado_preparacion`
  (pendiente → en_preparacion → listo → entregado, sin retroceso; fuente
  única del avance: todas las pantallas muestran el progreso real del
  pedido), `producto_comercial.categoria_id` (ruteo a estaciones),
  `venta.comanda_impresa_veces`, `venta.referencia_atencion` (migración
  `617845c27651` — "Mesa 5"/"Carlos"/"Rappi #1042", texto libre visible en
  tarjetas KDS y comanda sin exigir cliente registrado). Endpoints
  `/api/v1/kds`: CRUD de pantallas,
  cola por pantalla, bump de ítems, avance de pedido y comanda imprimible
  (texto 32 cols para térmica 58 mm, reimpresión marcada). Evento
  `sales.pedido_listo` al completarse todos los ítems. Permisos
  `kds.configurar`/`kds.operar`; rol `cocinero` en el seeder. Fix en el
  listener de inventory: cierre de sesión sin rollback en early-return
  (rompía transacción compartida en tests SQLite). Tests en
  `tests/test_kds.py`. Deuda: tiempo real (WebSocket/Redis), impresión
  física ESC/POS, alertas de demora, estados de entrega según proceso de
  cumplimiento.
- **Módulo `sales` — slice PDV** (2026-07-25): sin migración (esquema del
  slice Venta/Cobro ya existía). Endpoints `/api/v1/sales`: crear venta
  (correlativo `numero_orden` por sucursal+día, idempotencia por
  `idempotency_key`, total server-side), cobro con pagos parciales (suma ==
  total → `pagada`, sin sobrepago), anulación de orden no pagada, CRUD de
  productos comerciales y medios de pago. Eventos `sales.venta_confirmada` /
  `venta_pagada` / `venta_anulada`. **Listener en inventory**: consume insumos
  por receta (+merma % + empaque según modalidad RN-EMP-003) al confirmar y
  repone al anular; nunca bloquea la venta (omisiones se loguean). Kiosk y
  Central de Pedidos definidos como clientes del mismo contrato de venta, no
  módulos. Permisos `sales.anular` y `sales.gestionar_catalogo` en el seeder.
  Tests en `tests/test_sales.py`. Deuda registrada en ROADMAP (precio
  server-side, comprobante, nota de crédito, webhook pasarela, enlace caja,
  subrecetas anidadas).
- **Módulo `inventory` — slice core** (2026-07-25): migración `be914c92a94b`
  con 3 tablas (`stock`, `movimiento_inventario` insert-only, `ajuste`).
  Endpoints `/api/v1/inventory`: CRUD de artículos/categorías/SKUs, consulta de
  stock por almacén con alerta `bajo_minimo`, registro de movimientos (el stock
  nunca se edita directo; salida no deja negativo) y ajuste con segregación de
  funciones (`inventory.solicitar_ajuste` ≠ `inventory.aprobar_ajuste`, y el
  aprobador no puede ser el solicitante; al aprobar genera el movimiento y
  refleja el stock). Evento `inventory.ajuste_fuera_margen`. Permisos nuevos en
  el seeder, asignados a roles `almacenero`/`supervisor`. Reusa el auth/RBAC de
  `users`. Tests en `tests/test_inventory.py`. Diferido: lote/FEFO,
  `reserva_stock`, conteo, transferencias, devolución, guía de remisión,
  listeners de eventos, tenant desde el JWT.
- **Módulo `users` — slice auth + RBAC + CRUD** (2026-07-25): primer código de
  negocio del ERP. Migración `c16d615f6afd` con 7 tablas (`rol`, `permiso`,
  `usuario_rol`, `rol_permiso`, `usuario_sucursal`, `refresh_token`,
  `audit_log`) + columnas de lockout (`intentos_fallidos`, `bloqueado_hasta`)
  en `usuario`, aplicada a la BD dev. Endpoints `POST /api/v1/auth/login`
  (username + PIN 6 dígitos, Argon2id), `/auth/refresh` (rotativo con
  detección de reuso que revoca la cadena), `/auth/logout`, `GET /users/me`, y
  CRUD admin de usuarios/roles/permisos/asignaciones bajo `require_permission`
  (deny por defecto, comodín `*`). Access token JWT (claims: sub, tipo, roles,
  sucursales, empresa_id) 15 min + refresh 7 días. Lockout tras 5 intentos
  fallidos (ventana 15 min). Seeder `src/seeders/seed.py` (idempotente,
  prohibido en prod): org base Majambo + matriz de roles/permisos + `admin`
  (PIN `123456`). Tests en `tests/test_users_auth.py`. Router montado en
  `src/core/app.py`. Pendiente: aplicar restricciones JSONB por permiso.
- **Área Contabilidad** (2026-07-24): `docs/contabilidad/` (política de
  segregación de funciones/supervisión de Gerencia, marco legal tributario PE,
  perfil de contador/tesorero), 3 SOPs nuevos en
  `docs/diagrams/Procesos/Contabilidad/` (Tesorería: pago a proveedor
  PROC-CTB-003, conciliación bancaria PROC-CTB-004; Control: arqueo sorpresa
  PROC-CTB-005), 4 plantillas en `docs/templates/contabilidad/`. Reglas
  RN-CTB-004 a RN-CTB-009 (incluye auditoría interna: Contabilidad audita a las
  áreas operativas aguas arriba pero no a sí misma; su tesorería la audita
  Gerencia — modelo de control en dos niveles). Glosario: Tesorería, Finanzas,
  Flujo de caja, Conciliación bancaria, Arqueo, Auditoría interna, Orden de
  pago, Detracción, Activo No Corriente, Depreciación, Periodo contable.
  Nomenclatura: CAJ/TES/ACT confirmadas bajo Contabilidad. Eventos
  `accounting.pago_ejecutado`, `accounting.pago_requiere_aprobacion`,
  `accounting.arqueo_registrado`. Spec `src/modules/accounting/README.md`
  actualizada (tesorería/finanzas). Propuestos PROC-CTB-006..013 (reposición
  caja chica, flujo de caja, cierre de periodo, depósito, activo fijo, contador
  externo, auditoría de almacén, conciliación de facturas/comprobantes).
- **Área RRHH** (2026-07-19): `docs/rrhh/` (marco legal laboral REMYPE,
  perfiles de puesto), 13 SOPs en
  `docs/diagrams/Procesos/Recursos-Humanos/` (Reclutamiento, Contratación,
  Inducción), 9 plantillas en `docs/templates/rrhh/`. Reglas RN-RRHH-012 a
  RN-RRHH-014; RN-RRHH-005 corregida (15 días de vacaciones REMYPE).
- **Área Compras** (2026-07-19): `docs/compras/` (marco legal-tributario
  Amazonía/SPOT, perfil de encargado), 11 SOPs en
  `docs/diagrams/Procesos/Compras/` (Proveedores, Cotización-OC,
  Recepción-Pago, Caja-Chica, Activos-Equipamiento), 6 plantillas.
  Reglas RN-CMP-008 a RN-CMP-017. Spec `src/modules/purchases/README.md`
  actualizada (3 caminos de compra, caja chica, OC tipo activo, pago lo
  ejecuta accounting).
- **Área Comercial** (2026-07-19): `docs/comercial/` (política de
  precio/margen/promociones/metas, perfil de jefe comercial), 9 SOPs
  nuevos en `docs/diagrams/Procesos/Comercial/` (Estrategia-Mercado,
  Precios-Promociones, Metas-Desempeno), 5 plantillas. Reglas RN-CML-001
  a RN-CML-006; glosario: Margen de Contribución. Spec
  `src/modules/sales/README.md` actualizada (vigencia de promoción,
  margen de contribución, precio por nueva versión).
- **Área Almacén y Logística** (2026-07-19): `docs/almacen-logistica/`
  (política FEFO/FIFO, conteo/ajuste, perfiles de almacén y chofer),
  8 SOPs nuevos en `docs/diagrams/Procesos/Logistica-Almacen/`
  (Conteo-Auditoria, Vencimientos-Mermas, Transporte-Transferencias),
  6 plantillas. Spec `src/modules/inventory/README.md` actualizada
  (lote, merma, ajuste solicitar/aprobar, transferencia lateral).
- **Área Producción** (2026-07-20, spec a futuro — primera cocina de
  producción planeada 2027): `docs/produccion/` (política de cronograma,
  calidad/no conformidad, inocuidad, inventario de cocina, soporte a
  I+D+i; perfiles de jefe de cocina y cocinero), 4 SOPs nuevos en
  `docs/diagrams/Procesos/Produccion/` (Planificacion, Calidad-Inocuidad,
  Inventario-Cocina, Soporte-IDI), 5 plantillas en
  `docs/templates/produccion/`. Reglas RN-PRD-011 a RN-PRD-017; entidad
  `plan_produccion` nueva, `orden_produccion`/`reporte_escalamiento`
  ampliadas. Nuevo módulo `src/modules/production/README.md` (spec
  técnica, sin implementar) y evento
  `production.no_conformidad_detectada`.
- **Producción — costeo, desperdicio e inocuidad** (2026-07-20, mismo
  día): tabla de desperdicio por insumo/tipo/peso en `orden-produccion.md`;
  costeo real automático (insumos + mano de obra, RN-PRD-018); reporte de
  conteo de cocina pasa a autogenerado, el jefe de cocina solo visa;
  verificación de temperatura de equipos de frío con alerta automática a
  Gerencia (RN-CDP-005). Nuevas entidades `consumo_produccion_item` y
  `checklist_inocuidad_turno`; evento `production.equipo_frio_fuera_rango`.
- **Área Gerencia** (2026-07-22, versión ligera — autoridad/estrategia/
  control, sin módulo backend): `docs/gerencia/` (política de gobierno
  corporativo + matriz de aprobaciones como fuente única de umbrales,
  perfil de Gerente General), 2 plantillas en `docs/templates/gerencia/`
  (acta de decisión gerencial, evaluación de nuevo mercado/marca). Reglas
  RN-GER-001 a RN-GER-006; entidad transversal `decision_gerencial`
  (`data-model.md` §8c); glosario: Gerente General, Matriz de
  aprobaciones, Acta de decisión gerencial. Sin PROC ni evento ni módulo
  (la facultad de aprobar es RBAC, no una tabla).
- **Área Marketing** (2026-07-22): `docs/marketing/` (política de uso de
  marca/contenido/campañas, perfil de jefe de Marketing), 6 SOPs en
  `docs/diagrams/Procesos/Marketing/` (Marca-Contenido, Campanas,
  Proveedores-Agencias), 4 plantillas. Reglas RN-MKT-001 a RN-MKT-007;
  entidades `campana`, `pieza_contenido`, `lead`,
  `implementacion_material_sucursal` (`data-model.md` §8d); eventos
  `marketing.campana_lanzada`, `marketing.lead_generado`; PROC-MKT-001
  (Campaña de marketing, Borrador). Módulo `src/modules/marketing/README.md`
  (spec técnica). Glosario: Lead, Campaña, Naming, Jefe de Marketing.
  Frontera: Marketing atrae leads, Comercial cierra.
- **Presupuesto anual (Gerencia)** (2026-07-22): RN-GER-007, PROC-GER-001
  (reunión anual donde cada área presenta propuesta y Gerencia designa
  presupuesto + límite de gasto autónomo), SOP `definicion-presupuesto-anual.md`,
  plantilla `propuesta-presupuesto-anual.md`, fila en la matriz de
  aprobaciones. Ajuste Marketing: RN-MKT-001 (Marketing gestiona las
  marcas sin burocracia extra), RN-MKT-006 (agencias las evalúa Marketing
  y valida Gerencia, no pasan por Compras; el material sí).
- **Reglas de conducta laboral** (2026-07-22): RN-RRHH-015 (uniforme
  completo/limpio/presentable en jornada), RN-RRHH-016 (no contratar
  parientes de 1.er/2.º grado), RN-RRHH-017 (no relaciones sentimentales
  en el mismo centro ni con subordinación directa), RN-RRHH-018 (no usar
  conocimiento ni recursos de la empresa para terceros/beneficio personal).
- ADR-004: aislamiento de tenant por filtro de aplicación con
  `empresa_id` obligatorio + tests (RLS de Postgres como refuerzo futuro).
- Catálogo de eventos completado con los eventos ya declarados en las
  specs de módulos: `inventory.merma_registrada`,
  `inventory.devolucion_a_proveedor`, `inventory.ajuste_fuera_margen`,
  `inventory.lote_vencido_detectado` (nuevo — lote vencido hallado
  disponible notifica y dispara memorándum), `purchases.comprobante_conforme`,
  `purchases.caja_chica_rendida`, `purchases.evaluacion_proveedor_actualizada`,
  `users.sesion_iniciada`, `accounting.asiento_generado`,
  `accounting.periodo_cerrado` (`docs/architecture/events.md`).
- Modelo de datos: entidades `plantilla`, `flota`, `combo`/`combo_item`,
  `stock_lote` (stock por lote — hace implementable FEFO/FIFO),
  `ajuste`, `apertura_caja`, `cierre_caja`, `arqueo`,
  `reporte_escalamiento` (definición mínima, por validar), y bloque de
  Compras (`caja_chica_compras`, `caja_chica_movimiento`,
  `compra_directa`, `rendicion_caja_chica`, `evaluacion_proveedor`,
  `requerimiento_activo`); `articulo.tipo` gana `suministro` (consumo
  interno: limpieza, oficina) y queda declarado como enum extensible.
- Glosario: "Horario laboral" y "Horario de atención" (términos oficiales,
  reemplazan "horario de trabajo").
- Repositorio git inicializado (commit inicial con el estado
  pre-correcciones para trazabilidad).
- Modelado de BD — bloque transversal + organización (11 tablas):
  `persona`, `grupo`, `empresa`, `marca`, `licencia_marca`, `sucursal`,
  `almacen`, `categoria`, `categoria_udm`, `unidad_medida`, `archivo`.
  Modelos SQLAlchemy 2.0 tipados en
  `src/modules/{users,inventory}/infrastructure/models/` y
  `src/shared/models/`; mixins comunes (`UuidPkMixin`, `TimestampMixin`,
  `SoftDeleteMixin`, `JsonB`) en `src/core/model_base.py`; naming
  convention de constraints en `Base.metadata`; registro central
  `src/core/models_registry.py` cableado a Alembic; migración inicial
  Alembic validada contra Postgres 16 (ciclo upgrade/downgrade/upgrade);
  tests de esquema (`tests/test_models.py`).
- Puerto de Postgres en el host movido a **5433** (`docker-compose.yml`,
  `.env.example`) — el 5432 local lo ocupa la plataforma de Charlie's
  Pizzas; dentro de la red de compose sigue siendo `db:5432`.
- **BD de desarrollo movida a Supabase** (Postgres gestionado): la
  migración inicial (`a06c1d0a0913`) se aplicó contra el proyecto
  Supabase del usuario — 11 tablas + `alembic_version` verificadas.
  Motivo: visualización (Table Editor) y disponibilidad en línea de cara
  al despliegue futuro. Explícitamente **no** se activa Supabase
  Auth/RLS — sigue rigiendo `users` (JWT+PIN+Argon2id+RBAC) y el
  aislamiento de tenant por filtro de aplicación (ADR-004). Detalle y
  cómo alternar con el contenedor Docker local:
  `docs/engineering/devops.md`. Connection string solo en `.env`
  (gitignorado), plantilla sin secretos en `.env.example`.
- `reporte_escalamiento` definido con el negocio: cadena atención al
  cliente → supervisor (redacta solución) → comercial/gerencia; se
  almacena para mejora continua (`data-model.md` §6).
- **Slice Venta — núcleo de datos** (11 tablas nuevas, 22 en total):
  `usuario` (mínimo), `trabajador` (nuevo módulo `src/modules/rrhh/`),
  `articulo`/`sku`/`receta`/`receta_item` (base de productos, inventory),
  `cliente`/`punto_venta`/`producto_comercial`/`venta`/`venta_item`
  (nuevo módulo `src/modules/sales/`). Conecta venta con cliente y
  trabajador para habilitar historial de compras del cliente y ranking
  de ventas por trabajador — ambos probados en
  `tests/test_venta_slice.py`. Migración `08c7aa59dd6e` aplicada y
  verificada en Supabase (ciclo upgrade/downgrade/upgrade).
- **`venta.numero_orden`** (RN-COM-014, nueva): correlativo legible por
  sucursal y día (único junto a `sucursal_id`+`fecha_orden`) — lo que ve
  el personal en cocina/mostrador/KDS; distinto de `idempotency_key`
  (técnico) y del correlativo del comprobante (fiscal). Aplica tenga o
  no `cotizacion_id` la venta.
- **`cliente.usuario_id`** opcional (RN-COM-015, nueva): cuenta de
  autoservicio web — nunca requerida para comprar en sucursal o Central
  de Pedidos, esas ventas enrutan al mismo `cliente` sin login.
  Migración `90116965bfa8` aplicada y verificada en Supabase.
- **Slice Cobro y Comprobante (PROC-COM-002) + ciclo de caja
  (PROC-CTB-001/002)** — 8 tablas nuevas (30 en total): `medio_pago`
  (catálogo por empresa, decisión 2026-07-20), `pago` (RN-COM-016 —
  pago dividido confirmado real, suma de montos debe igualar
  `venta.total`), `comprobante` (nuevo módulo transversal en
  `src/shared/models/` — sirve a sales/purchases/accounting, correlativo
  único por empresa+serie, RN-CPP-007), `apertura_caja`,
  `custodia_efectivo`, `cierre_caja`, `arqueo` (nuevo módulo
  `src/modules/accounting/`, ciclo completo de caja). `punto_venta` gana
  `serie_boleta`/`serie_factura` (series SUNAT separadas por punto de
  venta, decisión 2026-07-20) — `comprobante.serie` las copia como
  snapshot inmutable al emitir. 3 tests nuevos
  (`tests/test_cobro_caja_slice.py`): pago dividido, unicidad de
  correlativo, cadena apertura→custodia→cierre. 13/13 tests pasan.
  Migración `8cde35e4f3f2` aplicada y verificada en Supabase (ciclo
  upgrade/downgrade/upgrade).

- Branding Provecho aplicado: paleta, tipografías (Anton Italic + Inter) y
  tokens CSS (`docs/product/ui-ux.md`).
- ADR-003: Izipay como pasarela de pago.
- `PROC-COM-002` Cobro y Emisión de Comprobante de Pago v1.0: narrativa +
  Mermaid en `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Comercial/PROC-COM-002-v1.0.bpmn` (detalle del
  paso "cobro" de `PROC-COM-001`, RN-COM-005).
- `PROC-CTB-002` Apertura de caja v1.0: narrativa + Mermaid en
  `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Contabilidad/PROC-CTB-002-v1.0.bpmn`. Nuevas
  reglas RN-POS-009 a RN-POS-013 y RN-MDP-006.
- `PROC-OPE-001` Apertura de sucursal v1.0: nueva área `OPE` (Operaciones)
  en `process-nomenclature.md`; narrativa + Mermaid en
  `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Operaciones/PROC-OPE-001-v1.0.bpmn` (checklist
  físico de apertura, recepción de pedido, limpieza, apertura de caja
  referenciada). Nuevas reglas RN-SUC-006 a RN-SUC-012, RN-PER-006 y
  RN-RRHH-009 a RN-RRHH-011. Glosario: agrega "Supervisor" (Actores) y
  "Alarma" (Recursos).
- SOPs de limpieza (14) y de lavado de menaje en
  `docs/diagrams/Procesos/Operaciones/Limpieza/`.
- SOPs de procesos comerciales/caja/apertura (9) derivados de los BPMN
  vigentes, en `Comercial/Ventas/`, `Comercial/Cobros/`,
  `Contabilidad/Caja/` y `Operaciones/Apertura-Sucursal/`.
- SOPs de `PROC-INV-001` (3): conteo de insumos y envío de requerimiento,
  picking y despacho en almacén central, recepción y devoluciones en
  local — nueva área `Logistica-Almacen` en
  `docs/diagrams/Procesos/`.

### Changed

- **RN-COM-007 reactivada** (2026-07-27): la encuesta de satisfacción
  vuelve a tener disparador (`sales.venta_entregada`) tras quedar sin él
  desde el recorte de alcance de Venta del 2026-07-14. Desbloquea
  `encuesta_satisfaccion` en el módulo `marketing`.
- **El bump del KDS ya no marca `entregado`** (2026-07-27):
  `POST /kds/items/{id}/avanzar` devuelve 409 apuntando al endpoint de
  entrega. Antes cualquiera con `kds.operar` cerraba el pedido ítem por
  ítem, lo que dejaba decorativo cualquier permiso de entrega; ahora la
  entrega exige `sales.entregar_pedido` y cierra la venta completa de una
  vez (RN-CUP-005/006). Cambio de contrato para clientes del KDS que
  usaran ese estado.
- **`almacen.direccion`** (2026-07-27, migración `e5a1c93b7d40`): columna
  nueva, nullable. El almacén central tiene `sucursal_id` NULL, así que no
  había dónde registrar su ubicación física; los almacenes de sucursal
  heredan la dirección de su sucursal y los virtuales (`activos`, futuro
  `transporte`) no tienen ninguna — de ahí que sea nullable y no obligatoria.

### Changed

- **Documentación al día con lo construido** (2026-07-26): tres ADR nuevos
  para decisiones que se habían tomado sin registrar —
  **ADR-005** (Factiliza como proveedor de facturación electrónica; deja
  constancia de que **Nubefact nunca fue un ADR**, era un supuesto heredado
  del scaffold que arrastraron trece archivos), **ADR-006** (logs con la
  biblioteca estándar en vez de `structlog`; Sentry/GlitchTip intercambiables
  por DSN, así que elegir backend no es decisión de arquitectura) y
  **ADR-007** (backups por `pg_dump` + cron y no Celery beat, porque el
  backup debe correr justo cuando la aplicación está caída; salud expuesta a
  un monitor externo). Barrido de las trece menciones obsoletas a Nubefact en
  `data-model.md`, `overview.md`, `tech-stack.md`, `marco-legal-contabilidad.md`,
  `diagrams/modules.md`, `business-rules.md`, `domain-model.md`,
  `state-machines.md`, `workflows.md`, `glossary.md` y `vision.md`.
  `overview.md` documenta ahora la infraestructura de operación de
  `src/core/` (tabla archivo → responsabilidad) y `src/backups/`, más el
  índice completo de ADR; `00_PROJECT.md` y el `README.md` raíz actualizados
  con salud, backups y observabilidad.

### Fixed

- `data-model.md` §6 `venta.estado`: seguía con el enum viejo de 8
  estados; corregido al enum vigente desde 2026-07-14
  (`orden|pagada|facturada|anulada`, RN-COM-005) — `state-machines.md`
  ya lo tenía correcto, quedaron desalineados.
- `data-model.md` §3 `articulo`: le faltaba `empresa_id` directo,
  rompiendo la convención de tenant (ADR-004) porque `categoria_id` es
  opcional.

### Changed

- `PROC-CMP-001` Compras v1.0 → v2.0: tres caminos de compra (informal/
  caja chica, preferente sin cotización comparativa, estándar/activo con
  RFQ) y ejecución del pago trasladada a Contabilidad (Compras solo
  sustenta el comprobante conforme). Registro maestro y `workflows.md`
  actualizados.
- Identidad de nombres unificada: **Provecho** = ERP, **Grupo Majambo** =
  grupo empresarial (corregido `docs/00_PROJECT.md`, aclarado en
  `CLAUDE.md`).
- Referencias de ADR normalizadas a 3 dígitos (`ADR-001`..`ADR-004`);
  ruta corregida en `CLAUDE.md` (`docs/architecture/adr/`).
- Entidad `contrato` reubicada como transversal (antes aparecía dentro de
  la sección de Inventario del data-model); referencia rota de
  `contrato_laboral` corregida.
- Specs de módulos sincronizadas con el catálogo de eventos (secciones
  Publica/Escucha de sales, inventory, purchases, accounting) y mapa
  `docs/diagrams/modules.md` regenerado.
- `docs/diagrams/README.md` actualizado a la convención real: SOPs
  primero y BPMN después, taxonomía `Procesos/<Área>/<Grupo>/`, versiones
  antiguas de BPMN se conservan para análisis.

- `PROC-INV-001` Abastecimiento de locales v0.1 → v0.2: detalla el conteo
  de fin de jornada en sucursal (balanzas, lector QR, ventana de 5 min
  fuera de refrigeración, alerta por margen de error RN-INV-015, cálculo
  de sugerido por punto de reorden RN-INV-013). Sigue en Borrador —
  picking/packing/transporte en almacén central aún sin este nivel de
  detalle.
- `PROC-CTB-001` Cierre de caja v1.0 → v1.1: agrega la bifurcación de
  custodia del fondo/caja chica (local en sucursal vs. traslado a
  oficinas de contabilidad, RN-MDP-006); RN-MDP-002 ampliada para cubrir
  la cadena de custodia en sentido inverso (apertura). Máquina de estados
  "Custodia de efectivo" actualizada en `docs/domain/state-machines.md`.
- Referencias a Mercadopago eliminadas (decisión: Izipay).
- Docs reorganizados por tema (`foundation/`, `domain/`, `architecture/`,
  `engineering/`, `security/`, `product/`) en vez de numeración plana;
  índice y orden de lectura en `docs/00_PROJECT.md`.
- Nuevos documentos de conocimiento: glosario (lenguaje ubicuo), filosofía del
  negocio, reglas de negocio (separadas del modelo de dominio), catálogo de
  eventos, máquinas de estado, autorización (RBAC, separada de seguridad).
- `AI_RULES` → `engineering/engineering-guide.md` (guía extensa; `/CLAUDE.md`
  la resume y apunta a ella).

### Removed

- Borradores duplicados de Venta: carpeta `docs/diagrams/Procesos/Ventas/`
  (BPMN/BPM de borrador — el vigente es
  `Comercial/PROC-COM-001-v1.0.bpmn`) y `docs/diagrams/Ventas.bpm`.
  `Cobro-PROC-COM-002-v1.0.bpmn.bpm` renombrado a
  `PROC-COM-002-v1.0.bpm` (archivo de proyecto Bizagi, doble extensión
  corregida).

## [0.1.0] - 2026-07-04

### Added

- Scaffold inicial: modular monolith (FastAPI + Next.js + PostgreSQL).
- Core: app factory, settings por entorno, sesión SQLAlchemy, event bus interno.
- Endpoint `/health` con tests.
- Especificaciones (contratos) de módulos: users, inventory, sales, purchases, accounting.
- Documentación: arquitectura, ADRs, modelo de negocio, modelo de datos v1.
- Docker Compose (api, web, postgres, redis), CI con GitHub Actions.
- Reglas de desarrollo en `CLAUDE.md`.
