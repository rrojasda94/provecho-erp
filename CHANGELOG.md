# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added

- **Token de API para cuentas de agente** (2026-08-08, ADR-029, migración
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

- **Los tests dejan de pagar el login por HTTP** (2026-08-08).
  `tests/conftest.py` expone `auth_headers(session, username)`, que emite el
  mismo JWT que emitiría `/auth/login` sin verificar el PIN, y una fixture
  autouse alimenta el rate limit con un contador que no crece. El límite es
  por IP y para `TestClient` todo el suite es la misma IP: el test número 11
  que hacía login recibía 429 y fallaba por una razón ajena a lo que
  probaba. Cada login además costaba un Argon2 completo (~50 ms) para
  verificar un PIN que ya tiene sus propios tests. `test_security.py` sigue
  probando el rate limit de verdad: monkeypatchea `_client` dentro del test
  y eso pisa la fixture.

### Fixed

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
