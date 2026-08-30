# Deuda técnica — Transversal

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-08-15 **`statement_timeout`, en dos engines**. `connect_timeout: 5`
  tapaba no poder conectar; un Postgres que **acepta la conexión y después se
  traba** —lock ajeno, plan malo, disco al límite— clavaba el request sin
  límite, porque `pool_pre_ping` hace un `SELECT 1` al sacar la conexión del
  pool y después no mira más. Se resolvió con **dos engines** sobre la misma
  base (`src/core/database.py`): `SessionLocal` con
  `DB_STATEMENT_TIMEOUT_SEGUNDOS` (15) es el default de todo el ERP, y
  `SessionReportes` con `DB_STATEMENT_TIMEOUT_REPORTES_SEGUNDOS` (120) lo usan
  `src/core/reportes/` y el módulo `reports` vía la dependencia
  `get_db_reportes`. Un número único obligaba a elegir entre cancelar reportes
  sanos o dejar la caja colgada; se aceptó el costo de un segundo pool de
  conexiones —que además aísla a la caja de una consulta pesada—. Fuera de
  Postgres el parámetro no se pasa (el `e2e` corre sobre SQLite).
  `test_arquitectura` falla si un endpoint queda del lado equivocado.
- ✅ 2026-08-15 **Los barridos ya no pueden abrir la sesión de producción en
  los tests**. `inventory/application/tasks.py`, `sales/application/tasks.py`
  y `rrhh/purga.py` llamaban `SessionLocal()` directo; ahora exponen
  `session_factory` como los listeners y están en
  `MODULOS_CON_SESSION_FACTORY`, así que el guardián autouse de
  `tests/conftest.py` los cubre: el test que ejercita un barrido parchea el
  suyo (`test_lotes`, `test_conteos`) y el que no, ve un error explícito en
  vez de una conexión real de 5 s —o, con la base de desarrollo levantada, un
  barrido corriendo contra ella—. `marketing/application/tasks.py` ya tenía
  `session_factory` y solo faltaba en la lista.
- **Cada test rearma el esquema, el seeder y la app desde cero** (2026-08-08).
  44 de los 58 archivos de test copiaron el mismo fixture `env` —
  `create_engine("sqlite://")` + `create_all` de las 99 tablas + `seed(s)` +
  `create_app()`— y **ninguno declara `scope=`**. Costo medido por test: 65 ms
  el esquema, ~112 ms el seeder y ~200 ms `create_app()`, que hace a FastAPI
  reanalizar la firma de todas las rutas (49.005 llamadas a `get_dependant` en
  un solo archivo de 22 tests). Es la mayor parte de lo que queda: el trabajo
  real del test es la minoría. Ya se atacó lo barato (Argon2id de prueba,
  Redis en memoria, `pytest-xdist`, ver CHANGELOG 2026-08-08) y con eso
  alcanza por ahora. Cuando vuelva a molestar, en este orden: **(a)**
  `create_app()` una sola vez por sesión con `dependency_overrides[get_db]`
  por test —quita el ~30% y es un fixture compartido, no un rediseño—; **(b)**
  esquema + seed una sola vez y cada test dentro de una transacción con
  `SAVEPOINT` que se revierte al terminar, que es el cambio grande porque
  obliga a revisar los tests que hacen `commit()` a mano. No hacer (b) antes
  de (a): puede que con (a) ya no haga falta.
- ✅ 2026-08-08 **`audit_log` transversal de verdad** (ADR-031). La tabla
  declaraba "consumido por todos los módulos" y el código decía otra cosa:
  el único escritor era `AuditLogRepo` en `users`, `rrhh` lo alcanzaba
  importando repositorios ajenos —una excepción declarada en
  `test_arquitectura.py`— y los actos que un auditor viene a revisar
  (anular una venta, aprobar un ajuste, emitir una OC, ejecutar un pago,
  sacar efectivo del cajón) no dejaban rastro. Ahora el modelo vive en
  `src/shared/models/`, se escribe solo por `src.shared.auditoria.registrar`
  —en la misma transacción que el cambio auditado— y se lee por
  `GET /api/v1/auditoria` (paginado, filtrable, sin `POST`). Se descartó la
  captura automática por evento de SQLAlchemy: el actor y la IP no están en
  la sesión y un rastro de cada `UPDATE` no lo lee nadie (ADR-031 → punto 2).
  `rrhh` salió de `_EXCEPCIONES_CRUZADAS`: la lista encogió, que es la única
  dirección permitida.
- **Un módulo se activa a mano en siete lugares** (2026-08-03). La estructura
  interna es replicable —los 8 módulos tienen la misma forma— pero no hay
  manifiesto por módulo ni autodescubrimiento: router y tag OpenAPI y
  `register()` de listeners en `src/core/app.py`, import en
  `models_registry.py`, migración, `PERMISOS`/`ROLES` en `src/seeders/seed.py`
  y entrada en `frontend/lib/modulos.ts`. Consecuencia: **borrar la carpeta de
  un módulo deja `core` sin compilar** — la promesa de "removible" es hoy del
  dominio, no del ensamblado. Mitigado, no resuelto:
  `docs/engineering/module-guide.md` documenta los siete pasos y
  `tests/test_arquitectura.py` exige tres de ellos (modelos en el registro,
  router montado, permisos de la API sembrados). Pendiente si algún día hay
  módulos opcionales de verdad: `MODULOS_ACTIVOS` en settings + carga por
  convención (`importlib`), que colapsa 1-4 en una línea; y `PERMISOS`
  declarados en el módulo en vez del seeder. No hacerlo antes de tener un
  caso real de módulo instalable/desinstalable — hoy los 8 están siempre
  encendidos.
- ✅ 2026-08-02 **`GET /personas` exigía `users.gestionar`, demasiado
  amplio para un lookup**: nuevo endpoint minimizado
  `GET /personas/buscar?q=` (permiso `personas.leer`, nuevo) que responde
  `PersonaBusquedaOut` — id/nombres/apellidos/numero_documento, nunca
  domicilio/teléfono/email/fecha de nacimiento — así que puede abrirse sin
  el permiso de administración completo. `personas.leer` sembrado en los
  roles `comprador` y `rrhh_admin`. `GET /personas` (ficha completa) sigue
  exigiendo `users.gestionar` sin cambios — el lookup es un recurso
  distinto, no un permiso más ancho sobre el mismo. RRHH/Trabajadores y
  Compras/Proveedores (natural) ya migraron a este endpoint.
- ✅ 2026-08-02 **CRUD de `unidad_medida`/`categoria_udm` (inventory) y
  `divisa` (gerencia)** — antes solo se editaban por seeder/migración
  (ADR-014 Addendum b). `POST/PATCH /inventory/unidades-medida[/{id}]`,
  `POST /inventory/categorias-udm` (permiso `inventory.gestionar_catalogo`)
  y `POST/PATCH /divisas[/{id}]` (permiso
  `gerencia.gestionar_parametros_empresa`, lectura abierta a cualquier
  autenticado — cualquier módulo que declare un monto necesita listar
  divisas válidas). `decimales` por unidad/divisa (RN-GER-010) ahora se
  corrige sin migración.
- ✅ 2026-08-02 **Cuatro endpoints de lectura que faltaban y bloqueaban
  pantallas de frontend**: `GET /api/v1/inventory/unidades-medida`
  (catálogo global, sin tenant — Inventario/Artículos lo necesita para el
  selector de `unidad_medida_id`), `GET /api/v1/purchases/ordenes-compra`
  (listado, no existía ni por error — solo había `GET .../{id}`),
  `GET /api/v1/almacenes` (nuevo en `users`, sin `require_permission` a
  propósito — catálogo de referencia, no dato sensible — pero sí escopado
  por tenant), `GET /api/v1/personas/buscar` (ver arriba).
- ✅ 2026-08-04 **Dos endpoints de lectura de RBAC que faltaban** y hacían
  inútil la pantalla de Usuarios: `GET /users/{id}/roles` —el token trae
  `roles` por nombre, sin id, así que desde la UI no había forma de
  desasignar— y `GET /roles/{id}/permisos`, porque asignar un rol sin poder
  ver qué habilita es exactamente el error que hay que evitar. Ambos con
  `users.gestionar`, sin permiso nuevo: son la misma administración que ya
  cubría crear y asignar.
- ✅ 2026-08-02 **Deriva de esquema del slice de contratación** (migración
  `e4a2f9c17b3d`): `postulante.estado` seguía en VARCHAR(10) con nueve
  estados de hasta 15 caracteres — `preseleccionado` fallaba en Postgres y
  pasaba en los tests porque SQLite ignora el largo. Además, `UNIQUE`
  duplicado en `convocatoria.token_publico`. Con esto el job `migraciones`
  de CI vuelve a verde: llevaba en rojo desde el 2026-08-01 y ningún PR
  podía pasar el check.
- ✅ **Contexto de tenant desde el JWT** (ADR-004): resuelto 2026-07-27 en
  `users`, `inventory`, `sales` y `kds`; completado 2026-08-01 en
  `purchases`, `production`, `accounting`, `rrhh` y el dashboard gerencial
  (`sync` ya lo derivaba de la cuenta de servicio). `src/core/tenant.py` +
  dependencia `get_tenant`; el `empresa_id`/`sucursal_id` sale de los
  claims, no del body, y un recurso ajeno responde 403 vía el handler de
  `FueraDeAlcance` del app factory. Tests en
  `tests/test_tenant_aislamiento.py`. Escape explícito documentado:
  superusuario (`*`) sin sucursal asignada puede indicar la empresa — sin
  eso el bootstrap del sistema sería imposible.
- ✅ 2026-08-01 `rrhh.postulante` **escopado por empresa**: se decidió con el
  usuario que la contratación es de la empresa, no del grupo (el grupo no
  tiene planilla). `postulante.empresa_id` obligatorio, heredado de la
  convocatoria cuando viene del formulario público.
- ✅ 2026-08-03 **Zona horaria del negocio** (`src/shared/fechas.py`,
  `settings.zona_horaria = "America/Lima"`). Se había anotado como "falla de
  los tests de conteos"; al revisarla resultó ser **de producción**: la
  aplicación derivaba "hoy" con `date.today()` —la zona del proceso, que en
  Docker es UTC— y la comparaba contra `created_at`/`cerrado_at`, que la base
  escribe en UTC. Pasadas las 19:00 hora Perú los dos relojes discrepaban un
  día y el calendario de conteo cíclico se corría entero. El mismo patrón
  estaba en otros 10 archivos —correlativo de venta por día, precio vigente,
  vencimiento de lotes, fecha de asiento contable, cierre de caja—, así que
  todos pasan por `fechas.hoy()`. Los 4 casos de `test_conteos` pasaron **sin
  tocar un solo test**, que es la prueba de que el error no estaba ahí.
  `tests/test_fechas_negocio.py` congela la regla, incluido un caso que falla
  si algún módulo vuelve a usar `date.today()`.
- ⬜ **Las direcciones ya cargadas no tienen ancla** (2026-08-22, ADR-053):
  las cinco tablas ganaron sus columnas nullable y nadie las llenó. No hay
  backfill porque geocodificar en masa se cobra por registro y el dato viejo no
  urge: cada ficha queda anclada la próxima vez que alguien la edite. Si algún
  día hace falta de golpe, es un comando que recorra las filas sin
  `ubicacion_place_id` con la clave del servidor y un tope de gasto.
- ⬜ **La CSP no se probó contra el mapa real** (2026-08-22, ADR-053): la lista
  de hosts de Google salió de su guía oficial recortada a lo que este ERP usa,
  **sin `'unsafe-eval'`**, que Google recomienda por las dudas. Falta la
  verificación en el navegador con clave puesta: si un mapa muere con un error
  de `eval` en consola, esa es la línea que falta y la decisión hay que volver a
  tomarla a conciencia, no agregarla de reflejo.
- ⬜ Los tests de `conteos` comparan contra `date.today()` local mientras
  `created_at` usa `CURRENT_TIMESTAMP` (UTC): corriendo después de las
  19:00 hora Perú fallan cuatro casos por un día de diferencia. Falla
  preexistente de zona horaria, no de la lógica de conteo.
- ✅ 2026-08-02 `users`: aplicar **restricciones JSONB** por permiso
  (ADR-022). `rules.ContextoPermiso`/`cumple_restricciones` (monto/estado/
  horario) + `UsuarioRepo.restricciones` + `check_permission(...,
  contexto=...)` (`api/deps.py`, retrocompatible — sin `contexto` se
  comporta igual que siempre; `require_permission` no cambia, no tiene
  acceso al body). Primer uso real: `sales.aplicar_descuento` acepta
  `monto_maximo` por rol, validado antes de aplicar el descuento. 15 tests
  nuevos (`tests/test_restricciones_permiso.py` + 3 casos HTTP en
  `test_sales.py`).
- ⬜ `users`: auth de **`agente_ia` por token** (hoy exige PIN como humano).
- ⬜ **Theming multi-marca + accesibilidad** (frontend, spec en
  `docs/product/ui-ux.md`): resolver de tema por marca/sucursal para
  PDV/Kiosk, preferencias de accesibilidad (paleta daltonismo, tamaño de
  fuente) persistidas en el perfil de `usuario`. Catálogo de paletas y
  niveles ya definido (2026-07-27) — sin implementar.
- ✅ 2026-08-02 **`parametro_empresa` con aprobación de Gerencia**
  (ADR-014 + Addendum, RN-GER-008/009): entidad transversal implementada
  (`src/shared/models/parametro_empresa.py`, migración `a71c9f4b2e60`).
  **El área propone desde su módulo, Gerencia acepta / rechaza / modifica**
  y recién ahí el valor llega al módulo. Lectura vía
  `src.shared.parametros.valor_vigente`. Permisos:
  `<modulo>.proponer_parametro` (uno por módulo) y
  `gerencia.gestionar_parametros_empresa`. Sigue sin existir un rol
  `gerente` explícito — hoy solo `admin` vía `*`. Falta que cada área
  proponga sus valores reales (ver "Pendientes de decisión") y el frontend
  de la bandeja.
- ✅ 2026-08-02 **`regla_aprobacion` retirada** (migración `b82d4c1f7a35`):
  sus umbrales vigentes se copiaron a `parametro_empresa` como
  `{"monto": ...}` ya aprobados; se borraron tabla, modelo, repo, los tres
  endpoints `/reglas-aprobacion` y el permiso
  `gerencia.gestionar_reglas_aprobacion`. `permiso_requerido` se descartó
  (era informativo). `umbral_vigente()` queda como envoltorio tipado
  (`Decimal`) sobre `parametro_empresa`. Una sola tabla de configuración
  por empresa, un solo flujo de aprobación.
- ✅ 2026-08-02 **RBAC por módulo al proponer parámetros**: un permiso por
  módulo (`<modulo>.proponer_parametro`, catálogo en
  `src/shared/parametros.py::MODULOS`) — Compras no propone parámetros de
  RRHH. `modulo` se valida como `Literal` en el schema (422 si es
  inventado) y `GET /parametros` sin filtro de `modulo` exige el permiso de
  Gerencia, porque los rangos salariales no son de lectura general.
- ✅ 2026-08-02 **`parametro_empresa.decision_gerencial_id` descartado**
  (previsto en ADR-014): el par propuesta/aprobación ya registra quién,
  qué, cuándo y con qué sustento (`motivo`) — la FK duplicaba ese rastro.
- ✅ 2026-08-02 **Toda magnitud lleva su unidad** (RN-GER-010, ADR-014
  Addendum b, migración `c93e5a7b1d42`): nueva entidad `divisa`
  (codigo/simbolo/**decimales**, sembrada con PEN), nueva columna
  `unidad_medida.decimales` (default 3) y `parametro_empresa.valor_display`
  con la magnitud formateada que lee Gerencia. `src/shared/magnitudes.py`
  valida y redondea con los decimales de la unidad (`ROUND_HALF_UP`, texto
  no float). Un monto sin `divisa` o una cantidad sin `unidad_medida_id`
  responden 422, al proponer y al modificar-y-aprobar.
- ✅ 2026-08-02 **CRUD de `divisa` y de `unidad_medida`** — resuelto el
  mismo día; ver la entrada de la sección *Transversal* de esta lista.
  `decimales` ya se corrige con un `PATCH`, sin migración.
  La frecuencia de conteo cíclico **salió de esta lista** (ADR-019,
  2026-08-01): es por categoría, no por empresa, y vive en
  `categoria.frecuencia_conteo`.
- ✅ 2026-08-03 **`decision_gerencial`** (acta de decisión gerencial,
  RN-GER-002, `data-model.md` §8c, migración `1805c0904c5c`): documentado
  desde el slice de Gerencia (2026-07-22), ahora con modelo en `shared`,
  repo, casos de uso y API — `POST/GET /api/v1/decisiones-gerenciales[/{id}]`,
  permisos nuevos `gerencia.decidir` y `gerencia.leer_decisiones` (el área
  ejecutora lee sin poder firmar, RN-GER-005; `leer_decisiones` sembrado en
  `supervisor`). `decidido_por_id` sale del token, no del cuerpo.
  `referencia_tipo`/`referencia_id` polimórficos sin FK: la decisión aplica
  a una OC escalada, una campaña sobre presupuesto o una sanción, y ningún
  módulo gana una FK hacia `shared`. `aprobado_con_condiciones` sin
  condiciones es 409 — un acta que no dice qué cumplir no sirve. 12 tests
  (`tests/test_decision_gerencial.py`). **Pendiente derivado:** ningún
  módulo la escribe todavía — `campana.aprobada_por` y la OC escalada
  siguen resolviendo por permiso, sin generar el acta (ver deuda de
  `marketing` más abajo).
- ✅ 2026-07-25 **Lock optimista en `persona`** (`VersionedMixin`,
  `src/core/model_base.py`): `PATCH /api/v1/personas/{id}` exige `version`
  vigente, 409 si está desactualizada. Aplicado solo a `persona` por
  ahora — extender a otras entidades compartidas si aparecen más choques
  reales de edición concurrente.
- ✅ 2026-08-04 **Contrato de lectura `purchases` ↔ `inventory.solicitud_insumos`**
  ("qué se pide más y desde dónde", insumo para negociar volumen con
  proveedores): mismo patrón de `sales.cliente`.
  `inventory/application/queries_publicas.py::solicitudes_resumen_para_negociacion`
  suma `cantidad_solicitada` por artículo y sucursal (`Almacen.sucursal_id`),
  excluye solicitudes `cancelada` —lo pedido cuenta como demanda real aunque
  no se haya aprobado ni despachado— y filtra por rango de fecha en zona de
  negocio (`fechas.zona()`, no UTC crudo). Expuesto en
  `GET /api/v1/inventory/solicitudes/resumen`, permiso nuevo
  `inventory.leer_solicitudes_externas` (sembrado en el rol `comprador`).
  `sucursal_id` sale `None` para almacenes sin sucursal (central,
  producción) — su demanda cuenta, solo no se atribuye a un local.

- ✅ **La base de desarrollo estaba en la nube y eso hacía lento todo**
  (medido 2026-08-05, **resuelto 2026-08-08**): `DATABASE_URL` apuntaba a
  Supabase y cada consulta costaba **~130 ms de ida y vuelta** — `SELECT 1`
  tardaba lo mismo que contar usuarios, así que era distancia, no trabajo de
  base. Todo request autenticado paga una consulta solo para resolver
  permisos, y una pantalla típica (4 llamadas × 3-6 consultas) se iba a
  **2-3 segundos de puro viaje de red** antes de renderizar nada.
  Ahora `DATABASE_URL` apunta al Postgres del `docker-compose` (host
  `localhost:5433`), lo que baja esos 130 ms al orden del milisegundo. Para
  que un solo `.env` sirva a la vez al host y a los contenedores —que ven
  `db:5432`, no `localhost:5433`— el `docker-compose.yml` inyecta la URL
  interna con el bloque `x-conexiones-internas` (`environment` gana sobre
  `env_file`). Mismo tratamiento para `REDIS_URL`.
  Costo aceptado: los datos de desarrollo ya no son compartidos ni
  visualizables desde el Table Editor; se regeneran con
  `alembic upgrade head` + `python -m src.seeders.seed`. Volver a Supabase
  son dos pasos documentados en `docs/engineering/devops.md`.
  Mitigado en paralelo: `next dev --turbopack` (2026-08-05) saca la
  recompilación por ruta, que era el otro sumando.

- ⬜ **La consulta de documento se paga dos veces por cada alta** (declarado
  2026-08-26): no hay caché de ningún tipo sobre `consultar_dni` /
  `consultar_ruc`. El botón «Buscar» del formulario consulta una vez, y al
  guardar `nombres_desde_dni` / `razon_social_desde_ruc` vuelven a consultar
  el mismo documento desde el servidor para no confiar en lo que llegó del
  cliente. Son dos llamadas a un proveedor pago por cada persona que se da de
  alta, y con el proveedor caído son dos timeouts seguidos. Un `lru_cache` con
  TTL corto —o Redis, que ya está— resuelve ambos; la razón por la que no se
  hizo ahora es que la doble validación es deliberada (ADR-041) y quitar la
  segunda llamada sin caché sería confiar en el cliente. Contraste: la tarifa
  de delivery sí cachea su geometría (`_distancia_cacheada`).

- ⬜ **112 columnas `Enum(native_enum=False)` sin CHECK** (113 en total, una arreglada) (encontrado 2026-08-30
  arreglando `persona.tipo_documento`). `create_constraint` vale `False` por
  defecto desde SQLAlchemy 1.4 y `validate_strings` también: un valor fuera del
  vocabulario **entra sin ruido** —el bind processor lo deja pasar y la columna
  es un `VARCHAR` del largo del valor más largo— y después revienta en la
  **lectura**, con `LookupError` → 500 en cada consulta que cargue esa fila. No
  es un alta rechazada: es una fila ilegible para todos hasta que alguien la
  corrija a mano en la base. `persona.tipo_documento` es la que mordió (se le
  puso `create_constraint=True` y el CHECK en la migración `c9f4a2e70b18`); el
  patrón está en todo el repo. Barrerlo es una migración con un CHECK por
  columna y el saneo previo de cada una, así que va aparte. De paso: SQLite
  **sí** hace cumplir los CHECK, así que ponerlos también cierra el hueco de
  que la suite pase en verde sobre algo que Postgres rechaza.

- ⬜ **El 8/11 del documento está escrito a mano en cuatro sitios más**
  (2026-08-30). El vocabulario y los largos por tipo ya viven en
  `src/shared/documento.py` y `frontend/lib/documento.ts`, pero siguen
  reescritos como literales en `src/core/consulta_router.py:120,144`,
  `frontend/app/(app)/ventas/clientes/actions.ts:78` y las tres regex
  `/^\d{8}$/` de `frontend/app/(publico)/reconocerte/`. Y
  `frontend/app/pdv/dialogos.tsx:1554` declara un `documentoValido` local que
  **sombrea** el importado en `:9` y se saltea el chequeo de dígitos. No se
  tocaron acá porque el PDV está en manos de otra rama y el conflicto costaría
  más que la deuda. Ojo con `consulta_router`: ahí el 8/11 puede ser el
  contrato del proveedor (RENIEC/SUNAT) y no la regla del ERP — mirarlo antes
  de "arreglarlo".
