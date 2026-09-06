# Historial — Fundaciones, arquitectura y plataforma transversal

Estado vigente: 🔶 En curso — el núcleo (scaffold, core, RBAC base, migraciones,
seeders, CI/CD, observabilidad, backups, contrato OpenAPI, endurecimiento de
producción, protección de datos, offline del PDV, arquitectura frontend/UX)
está construido y operando en staging; queda pendiente completar el primer
despliegue de staging, levantar producción, terminar el droplet de BI/Superset
y cerrar los puntos anotados como deuda técnica transversal.

## Cronología

### 2026-07-04 — Scaffold del proyecto
| Scaffold del proyecto | ✅ 2026-07-04 | Estructura, Docker, CI, docs, reglas |

### 2026-07-04 — Reestructura de docs por temas
| Reestructura de docs por temas (foundation/domain/architecture/engineering/security/product) | ✅ 2026-07-04 | Índice en `docs/00_PROJECT.md` |

### 2026-07-04 — Docs de conocimiento
| Docs de conocimiento (glosario, filosofía, reglas, eventos, máquinas de estado, autorización) | ✅ 2026-07-04 | Base para desarrollo asistido por IA |

### 2026-07-04 — Especificaciones de módulos base
| Especificaciones de módulos base | ✅ 2026-07-04 | READMEs de users, inventory, sales, purchases, accounting |

### 2026-07-04 — Modelo de datos (v1, documento)
| Modelo de datos (v1, documento) | ✅ 2026-07-04 | `docs/architecture/data-model.md` |

### 2026-07-14 — Modelo de datos ampliado
| Modelo de datos ampliado (bloques Inventario, Documentos, Movimientos, Operación comercial, Recursos, Información, RRHH, Actores) | ✅ 2026-07-14 | `docs/architecture/data-model.md` — ~50 entidades nuevas/enriquecidas; ver detalle abajo |

### 2026-07-04 (revisado 2026-08-01) — Core (app factory, settings, db, event bus)
| Core (app factory, settings, db, event bus) | ✅ 2026-07-04 | Endpoint `/health` operativo. **Bus revisado 2026-08-01 (ADR-016)**: el evento se despacha recién al commitear la sesión que lo publicó — antes se entregaba en medio de la transacción y un rollback dejaba stock descontado por una venta inexistente. |

### 2026-08-01 — Auditoría arquitectónica
| Auditoría arquitectónica | ✅ 2026-08-01 | `docs/architecture/audit-2026-08-01.md`. Veredicto: arquitectura sana y proporcionada, sin sobreingeniería; separación de capas al 100 % y dominio puro. Aplicado: eventos post-commit (ADR-016), jerarquía de errores unificada (ADR-017, −251 líneas en routers), contrato público `users.tiene_permiso`, y `tests/test_arquitectura.py` (98 casos) que congela los límites. Descartado con justificación: dividir `rules.py` (120 líneas el mayor), dividir `repositories.py` (ya son 9-13 clases pequeñas por archivo), eventos tipados (sin type checker en CI el beneficio es solo documental) y separar eventos sync/async (lo asíncrono real ya vive en Celery). Diferido: `Empresa`/`Sucursal`/`Almacen`/`Persona` de `users` a `shared/models` (37 archivos; conviene junto al CRUD de organización), contrato público de `inventory` para `Articulo`/`Receta`, y `core/dashboard_router` a un módulo propio. |

### 2026-08-30 — Errores de la API legibles
| Errores de la API legibles | ✅ 2026-08-30 | ADR-017 addendum. El 422 de validación dejó de salir en el formato crudo de FastAPI (`detail` como lista de `{loc, msg, type}`, en inglés): `src/core/validacion.py` lo traduce a `detail` en español nombrando cada campo, más `errores: [{campo, etiqueta, mensaje}]` con los que el diálogo de formulario marca y enfoca el input rechazado. Etiquetas por palabra en `src/shared/etiquetas.py` (regla para `-ción`/`-sión`, diccionario solo para siglas y excepciones). En el frontend, el parseo del error queda en un solo lugar (`lib/errores.ts`): estaba duplicado en los dos clientes HTTP y el helper `mensajeDe` copiado en quince `actions.ts`. |

### 2026-07-25 (en curso) — Modelado de base de datos completo (SQLAlchemy + Alembic)
| Modelado de base de datos completo (SQLAlchemy + Alembic) | 🔶 en curso 2026-07-25 | Bloque transversal + organización (11) + slice Venta núcleo (11) + slice Cobro/Comprobante/Caja (8) + slice auth/RBAC (7) + slice inventory core (3) — 40 tablas en total. BD de desarrollo corre en el **Postgres del `docker-compose`** (host `localhost:5433`) desde 2026-08-08, por latencia; Supabase queda como alternativa documentada en `docs/engineering/devops.md`. Resto por slice vertical. |

### 2026-08-24 (cabeza) — Migraciones Alembic
| Migraciones Alembic | 🔶 cabeza `a7c3e1f508b2` (2026-08-24, cupón de promoción, encadenada detrás de `e2b7c40d91af`) | **Aplicada en la BD dev el 2026-08-09** (`alembic upgrade head` + `downgrade` probados contra el Postgres local; el permiso nuevo `sales.registrar_consumo_personal` lo siembra el seeder). Nota para futuras migraciones de enums: los `Enum(native_enum=False)` del proyecto **no crean CHECK** en Postgres (default de SQLAlchemy 2.0), son `VARCHAR` — agregar un valor que entre en el largo declarado no toca el esquema. Con una migración sin aplicar, `python -m src.core.esquema` reporta deriva a propósito. Dos ramas que salen del mismo commit crean **dos cabezas**, y `alembic upgrade head` falla en el despliegue, no en el merge que las causó: lo atrapan `test_el_repo_tiene_una_sola_cabeza` y el job `backend`, y se arregla repuntando el `down_revision` de la que llega segunda. Ojo: la base es **una sola para todos los worktrees**, así que otra rama en curso puede dejarla en una revisión que la tuya todavía no conoce — es el mismo comportamiento que había con Supabase, no lo trajo la mudanza. Las primeras seis fueron transversal+org, slice Venta, cobro/caja, cliente opcional, slice auth/RBAC e inventory core; el detalle de cada slice posterior va en su fila. Tras aplicar una migración que suma permisos hay que correr `python -m src.seeders.seed` (idempotente): la migración crea tablas, no filas de RBAC. |

### 2026-07-27 — Seeders (admin / PIN 123456, org base)
| Seeders (admin / PIN 123456, org base) | ✅ 2026-07-27 | `src/seeders/seed.py` (idempotente, prohibido en prod): matriz de roles/permisos semilla, `admin`/PIN `123456` y la **organización real** del grupo — empresa Majambo EIRL (RUC 20450311520, Jr. Ramón Castilla 248 - Tarapoto, zona `amazonia_ley27037`), marca Charlie's Pizzas **licenciada** a la empresa (`licencia_marca`), sucursales `CH1` (Jr. Ramón Castilla 248) y `CH2` (Jr. Lamas 299) activas y alquiladas (RN-IMP-004), almacén central `WH1` (`sucursal_id` NULL). Requirió `almacen.direccion` (migración `e5a1c93b7d40`): el central no cuelga de ninguna sucursal y no había dónde guardar su ubicación. Correr: `python -m src.seeders.seed`. **CRUD de organización por API: ✅ 2026-08-08** — el seeder deja de ser la única vía para crear empresa/marca/sucursal/almacén. Diferido: almacenes de sucursal de CH1/CH2 (no pedidos; su mín./máx. por SKU depende de datos de operación inexistentes). |

### 2026-07-25 — Persona CRUD + lock optimista + matriz de aprobaciones + contrato público
| Persona CRUD + lock optimista + matriz de aprobaciones + contrato público | ✅ 2026-07-25 | `POST/GET/PATCH /api/v1/personas` (sin Delete); `persona.version` con lock optimista (409 si desactualizada); `regla_aprobacion` (nuevo, `src/shared/`) reemplaza el umbral fijo de `purchases` por empresa, admin en `/api/v1/reglas-aprobacion`; primer contrato público de lectura cross-módulo (`sales.cliente` para marketing/comercial, `GET /api/v1/sales/clientes`). Migración `af8a246e2c25`. Ver detalle abajo. |

### 2026-08-05 (revisada) — BI/reportes, Superset, y decisiones de módulo transversal (Supervisión, CRM, tesorería, activos, proyectos)
| Supervisión, CRM, tesorería, activos, proyectos, BI/reportes | 🔶 revisada 2026-08-05 | **Cuatro de los siete ya no son futuros y dos no van a ser módulos.** **BI/reportes** ✅ 2026-08-04: `src/core/reportes/` (ADR-024) con catálogo cerrado de 13 reportes, tableros guardados por usuario y compartidos por rol, filtros y exportación a CSV. **Desde 2026-08-08 hay una segunda mitad**, y son cosas distintas: `core/reportes` es la **consulta** (el usuario pide, se calcula) y el módulo `reports` (ADR-033) es la **emisión y distribución** (pasa un hecho, se genera, se guarda y se reparte). ADR-024 descartó un módulo porque el *motor de consulta* no tiene dominio propio; la distribución sí lo tiene —áreas, reglas, emisiones, entregas— así que paga sus siete registros de alta. **BI autoservicio 🔶 Fases A-E ✅ 2026-08-29** (ADR-081): la demanda de "elegir libremente eje X/Y/valor, más tipos de gráfico, comparar periodos" que ADR-024 anticipó se resuelve con Apache Superset, no abriendo el constructor de consultas que ese ADR rechazó. Infra corregida antes de construir Superset: droplet aparte y chico (~$8/mes, 1 vCPU/1 GB) en vez de agrandar el de staging — el volumen real es decenas de consultas al mes, sin apuro de latencia. **Fase A**: diez vistas `vw_bi_*` + `bi_alcance_usuario` (RN-BI-001/002), rol de Postgres `bi_lector` sin acceso a ninguna tabla base, índices de soporte, y `tests/test_bi_alcance.py` que congela la equivalencia con `Tenant.sucursal_ids` contra Postgres real. **Fase B**: Provecho como proveedor OAuth2 (`src/core/oauth/`, sin tabla nueva — código y token viven en Redis, TTL corto, fallan cerrado). El hallazgo que definió el diseño: la sesión de Provecho es una cookie host-only de `staging.majambo.com.pe` que nunca llega a `api-staging.majambo.com.pe`, así que el paso que ve el navegador (`GET /oauth/authorize`) es un Route Handler del **frontend**, no un endpoint de FastAPI — la API solo entra ya autenticada, para validar `client_id`/`redirect_uri` y emitir el código. De paso, el login ahora acepta un `?next=` whitelisteado a `/oauth/authorize`, para no dejar a alguien a mitad del SSO si todavía no había entrado a Provecho. Permiso `bi.acceder` (RN-BI-004/005/006) seedeado en `admin`/`supervisor`/`contador`, adelantado desde Fase D porque el endpoint no tiene sentido sin él. **Fase C** (código y ensayo local hechos — sin acceso a DigitalOcean del usuario, el droplet real queda pendiente, ver `docs/engineering/bi-superset.md`): `docker-compose.bi.yml` + `deploy/bi/` + `scripts/superset_provision_db.sql` + `scripts/superset_init.py`, ensayados de punta a punta contra un Superset y una Postgres reales en Docker local — no solo revisados a ojo. Encontró cuatro bugs reales que ninguna lectura de código habría atrapado: la imagen "lean" de Superset no trae `psycopg2`; el `pip install` del driver tiene que apuntar al venv de Superset (`/app/.venv`), no al del sistema; `current_username()` sin llaves no es SQL de Postgres —es un macro de **Jinja** que Superset interpola antes de mandar la consulta, necesario porque la conexión analítica corre siempre como `bi_lector` para cualquier usuario—; y sin la feature flag `ENABLE_TEMPLATE_PROCESSING` ese macro no se interpola igual, así que la RLS filtraba en silencio a **cero filas para todo el mundo** sin ningún error que avisara. Se detectó inspeccionando el SQL efectivo que Superset mandaba a Postgres, y también que el rol `Gamma` de fábrica no alcanza los datos sin `datasource_access` explícito por dataset (403 `DATASOURCE_SECURITY_ACCESS_ERROR`) — el script ya se lo otorga al rol marcador `ProvechoBI`. **Fase D**: permiso y navegación (`bi.acceder` exacto, no por prefijo — entrar ya es un privilegio), guest tokens para embeber (`GET /bi/dashboards/{id}/guest-token`, whitelist `BI_DASHBOARDS_EMBEBIBLES`, cuenta de servicio propia de Superset — distinta del SSO humano de Fase B), y tres mejoras al tablero de ADR-024 sin depender de Superset: filtro por marca (se une con el de sucursal, no lo reemplaza — cero cambios en los 14 reportes), `pie`/`area` como visuales (universales, vía el default de `VISUALES`), y título de tarjeta editable. Todo verificado en un navegador real (Docker: Postgres + backend + frontend, admin/cajero1 de verdad) — no solo lectura de código. Un hallazgo de entorno en el camino: la primera pasada mostraba solo 3 visuales porque `localhost:8000` resolvía por IPv6 al contenedor de **otra sesión** concurrente en la misma máquina, no al backend de prueba — forzar IPv4 lo resolvió, sin tocar código. **Fase E**: imprimir el tablero (`window.print()` + `print:` de Tailwind, escondiendo edición y navegación del shell — comprobado en el CSS de producción), y `POST /reportes/{codigo}/exportar` para el dataset completo (50 000 filas, no 500 — mismo permiso y mismo rango que `/datos`, comparten la resolución de reporte/alcance), con los montos como número real y no como texto, así que una fórmula de suma funciona sola. Cierra la deuda "la exportación baja lo que se ve, no el dataset completo". Verificado con 5 tests que leen el `.xlsx` real con `openpyxl`. Pendiente real: crear el droplet (VPC, firewall, DNS — runbook listo, requiere acceso del usuario a DigitalOcean) y curar los primeros tableros de Superset con `@superset-ui/embedded-sdk` para el widget de embebido (el mecanismo del backend ya está, la whitelist está vacía a propósito — no se inventó ningún dashboard de ejemplo) — detalle completo en el propio ADR. **Tesorería** ✅ 2026-07-25: vive **dentro de `accounting`** por decisión explícita del usuario —pago a proveedor, `movimiento_dinero`, caja y custodia— y separarla al salir de REMYPE es un pendiente de organización, no de código. **Supervisión** no es módulo: es el rol RBAC `supervisor` más la matriz de aprobaciones de Gerencia (`parametro_empresa` + `decision_gerencial`); un módulo "supervisión" sería un permiso disfrazado de dominio. **CRM** parcial: `sales.cliente` (con contrato público de lectura) y `marketing.lead`/`campana`/`encuesta_satisfaccion` con atribución lead→venta ya cubren captar y medir; falta historial de interacciones y segmentación, sin caso hasta que haya campañas reales corriendo. **Activos** ⬜ pero **ya tiene dueño**: se compran en `purchases` (OC tipo `activo` + `requerimiento_activo`, deuda declarada) y se deprecian en `accounting` (activo fijo/depreciación, PROC-CTB-007/010) — partirlos en un tercer módulo cortaría el ciclo de compra en dos. **Proyectos** ⬜ sin caso: el grupo no ejecuta obra ni proyectos facturables hoy. |

### 2026-08-08 — Auditoría (audit_log), transversal
| Auditoría (audit_log) | ✅ 2026-08-08 | Transversal (ADR-031): `src/shared/auditoria.py` es el único escritor, `GET /api/v1/auditoria` (permiso `auditoria.leer`) el lector. Cinco módulos nuevos dejan rastro; `empresa_id` + índices en migración `b3d9f1c2a077`. Pendiente la purga por antigüedad (ver Deuda técnica → Protección de datos) |

### 2026-09-05 — Pantalla de auditoría (Ola 3, exclusivamente la parte transversal)
| `feat/auditoria-pantalla` | `GET /api/v1/auditoria`: quién hizo qué, cuándo y con qué valor anterior | ✅ 2026-09-05 |

(Este ítem es parte del bloque `Ola 3` de la auditoría del 2026-08-30, cuyo
detalle completo de hallazgos vive en `calidad-y-auditorias.md`; se incluye
aquí solo porque construye la pantalla del `audit_log` transversal descrito
arriba.)

### 2026-07-26 — Endurecimiento de producción (rate limit, secretos, HTTPS, cabeceras)
| Endurecimiento de producción (rate limit, secretos, HTTPS, cabeceras) | 🔶 base ✅ 2026-07-26 | Rate limit por IP en login/refresh (Redis, fail-open), validación de config que aborta el arranque en `production` con valores de desarrollo, CORS + `TrustedHost` + cabeceras de seguridad + HSTS, `/docs` cerrado en producción, uvicorn `--proxy-headers`. Runbook de rotación de credenciales y custodia de `.env` en `docs/engineering/devops.md`. Pendiente: ver Deuda técnica → Seguridad. |

### 2026-07-27 (ADR-013) — App Android: decisión PWA/responsive
| App Android (15+) | ⬜ | **Decidido (ADR-013): PWA/responsive, no app nativa** — Next.js + Tailwind + Base UI es 100% web, sin base de código separada; debe hablar con el hub local de sucursal igual que web y PC, ver ADR-009 |

### 2026-07-27 (actualizado hasta 2026-08-18) — Arquitectura frontend (Tailwind, shadcn/ui, shell estilo Odoo)
| Arquitectura frontend (Tailwind, shadcn/ui, shell estilo Odoo) | ✅ spec 2026-07-27 | ADR-013 (revisado): Tailwind sobre los tokens de marca existentes (`tailwind.config.ts` → `var(--color-*)`, sin hex mágico); **shadcn/ui** (componentes copiados y editables, corre sobre Base UI, no Radix) para overlays/combobox/dialog y catálogo base — token set semántico + `--radius` único, mejor ajuste para editar color/forma por marca rápido que construir a mano; home de apps + sidebar por módulo estilo Odoo; grid y rutas filtrados por `permisos` de `GET /users/me` (ya existente, sin cambio de backend), guard real server-side en cada `layout.tsx` de módulo — el filtro del grid es solo UX. Sin librería de estado global (YAGNI). Playwright para e2e de flujos críticos: **13 casos en verde y en CI desde 2026-08-06** (flujo del dinero, sesión, gate de módulo por permiso, lienzo de nodos y bloqueo de pantalla), ver Deuda técnica → Frontend. **2026-08-15 (ADR-047)**: se le suma una **suite de uso** aparte (`frontend/uso/`, `npm run test:uso`) para recorridos completos con captura en cada hito — el techo de tres casos de `e2e` sigue vigente porque `e2e` bloquea todo merge, y `uso` deliberadamente no lo hace. `docs/prompts/frontend.md` actualizado con las reglas técnicas. Sin implementación de código todavía. **2026-08-10 — el ERP ya corrige, no solo crea**: botón "Editar" en la fila de seis pantallas existentes y ocho rutas nuevas (Usuarios → Personas, Ventas → Clientes, Inventario → Categorías y Unidades de medida, y el módulo **Organización** con empresas/marcas/sucursales/almacenes). El backend ya tenía `PATCH` para casi todo: lo que faltaba era la pantalla. Molde único en `components/formulario/dialogo-formulario.tsx` (antes copiado en siete pantallas) que además arregla que **React 19 reseteaba el formulario al fallar la acción**, borrando lo tecleado. Personas lleva bloqueo optimista por `version` — con eso la rectificación de la Ley 29733 deja de ejercerse por `curl`. **2026-08-15 (ADR-048) — el proxy del navegador pasa bytes, no texto**: `app/api/proxy/[...ruta]/route.ts` leía todo cuerpo con `text()` y le fijaba `Content-Type: application/json` en las dos direcciones. Estaba escrito para un mundo de puro JSON y rompía en silencio lo primero que no lo fuera: la plantilla `.xlsx` del recetario se bajaba corrupta y con nombre `plantilla.json`, y toda subida `multipart` perdía su `boundary`. Ahora reenvía el `Content-Type` entrante, devuelve el cuerpo como stream y conserva `Content-Disposition`; se descartó la alternativa de rutas dedicadas por descarga (una copia por endpoint binario, y el proxy genérico seguiría roto para el resto). Lo fijan `frontend/lib/proxy.test.ts` (8 casos) y el recorrido de uso del importador. Ver Deuda técnica → Frontend. **2026-08-15 (ADR-050) — el login se teclea en el pinpad**: seguía pidiendo el PIN en un `<input type="password" autocomplete="current-password">`, o sea el patrón que ADR-045 había eliminado dos días antes dentro del PDV, en la pantalla que más veces se cruza y desde la misma tablet de la caja — sacarlo de los cuatro diálogos y dejarlo en la puerta no protegía nada. Ahora el usuario se teclea y el PIN se toca, **sin campo de formulario ni oculto**; el pinpad salió de `app/pdv/` a `components/pinpad/` (CSS a `globals.css`, con los tokens `--pdv-*` como preferencia y los del back office como respaldo, así una sola regla sirve a las dos paletas) y `app/pdv/pinpad.tsx` queda como re-export temporal para no chocar con la rama que trabaja `dialogos.tsx`. El login además **distingue las tres negativas** (401 / 423 con sus 15 minutos / 429 con su `Retry-After`), corta un PIN incompleto antes de gastar un intento del lockout, y deja de borrar el usuario tecleado al fallar. Deuda que deja: el puente del re-export y `app/cambiar-pin/`, el último PIN que se escribe en un campo. **2026-08-10 — el ERP ya corrige, no solo crea**: botón "Editar" en la fila de seis pantallas existentes y ocho rutas nuevas (Usuarios → Personas, Ventas → Clientes, Inventario → Categorías y Unidades de medida, y el módulo **Organización** con empresas/marcas/sucursales/almacenes). El backend ya tenía `PATCH` para casi todo: lo que faltaba era la pantalla. Molde único en `components/formulario/dialogo-formulario.tsx` (antes copiado en siete pantallas) que además arregla que **React 19 reseteaba el formulario al fallar la acción**, borrando lo tecleado. Personas lleva bloqueo optimista por `version` — con eso la rectificación de la Ley 29733 deja de ejercerse por `curl`. Ver Deuda técnica → Frontend. **2026-08-18 — los diálogos se centran y el PDV cabe en una tablet**: los diecisiete diálogos del ERP se abrían pegados a la esquina superior izquierda por dos causas encimadas —el preflight de Tailwind pisa con `margin: 0` el `margin: auto` con el que el navegador centra un `<dialog>` modal, y el `animation-fill-mode: both` de `.revelar` deja computado un `transform` identidad, que convierte al contenedor en bloque contenedor de todo `position: fixed`, top layer incluido—; se arregla con `dialog:modal { margin: auto; overflow: auto }` global y `backwards` en las animaciones de entrada. El PDV escondía el ticket entero (`display: none`) por debajo de 60rem, o sea en toda tablet en vertical y todo teléfono: pedido, totales, «Enviar» y «Cobrar» dejaban de existir. Ahora carta y ticket comparten celda y se alternan con un botón que solo aparece en ese ancho. Con eso van la barra del PDV que recortaba «Cuentas» y «Cobrados» a 390 px, el conteo por denominaciones que se desbordaba llevándose «Abrir caja», las barras superiores de PDV y KDS con la altura clavada, y la pantalla de bloqueo pintada con el blanco del navegador (deuda de ADR-050, cerrada). Lo fija `frontend/uso/responsive.spec.ts`, que recorre home, inventario, KDS con dos estaciones y PDV con caja abierta en 390×844, 820×1180 y 1440×900 afirmando dos cosas: que ningún control quede fuera de un contenedor que lo recorta y que todo modal quede centrado. |

### 2026-07-26 / 2026-07-27 / 2026-08-07 — Modo offline del PDV — hub local de sucursal
| Modo offline del PDV — hub local de sucursal | ✅ fase 1 2026-07-26 · fase 2 2026-07-27 · fase 3 2026-08-07 | ADR-009: hub local dedicado por sucursal (misma imagen del backend, Postgres propio), los 3 clientes (web/Android/PC) le hablan siempre al hub por LAN. **Fase 1**: `DEPLOYMENT_MODE=hub` + validación de config, detector de conectividad, `GET /health/sync`, `docker-compose.hub.yml`. **Fase 2 — motor de sync**: ciclo que **empuja y después jala** (`src/core/sync/motor.py`, proceso `python -m src.core.sync.runner`); `id` client-generado en `crear_venta`/`registrar_pago`/`registrar_movimiento` (el cambio previo que pedía la fase 1, sin migración); endpoints dedicados `GET /sync/pull` + `POST /sync/push` (permisos `sync.leer`/`sync.empujar`, rol `hub_sucursal`) porque los públicos no alcanzaban (no traen `pin_hash` ni los campos del catálogo, no son incrementales, y el push necesita conservar quién vendió y el número de orden); contrato declarativo por módulo (`application/sincronizacion.py`, 35 recursos tras sumar precios y lote/FEFO) que el motor solo ensambla; tabla `sync_watermark` por recurso y dirección; `/health/sync` con avance y último error por recurso; alta de la cuenta de servicio con `python -m src.seeders.hub`. El hub NO empuja movimientos de inventario (el listener de la nube los regenera; duplicaría el consumo). 33 casos en `tests/test_sync_motor.py` sincronizando dos bases reales. **Fase 3 (2026-08-07)**: el ciclo de abastecimiento offline — el local pide, ve lo que viene y recibe, y cuenta su almacén. El motor deja de estar cableado a `sales`: hay un registro `MODULOS_PUSH` y **cada módulo lleva su propio watermark**, así un conteo trabado no frena el dinero. La guía de remisión **no se emite offline** y eso es decisión tomada, no deuda (ADR-009). Pendiente: ver Deuda técnica. |

### 2026-07-26 — Backups automáticos
| Backups automáticos | ✅ 2026-07-26 | `python -m src.backups.backup`: dump `pg_dump --format=custom` → verificación del archivo (firma + tablas críticas) → restauración probada contra base desechable → copia a S3 (opcional) → purga con retención de 30 días que nunca borra la copia más reciente. **Diario** (antes se declaraba mensual e incremental). Cron del host, no Celery beat. Runbook en `docs/engineering/devops.md#backups`. Pendiente: alerta ante fallo, ver Deuda técnica. |

### 2026-07-26 — Dashboard gerencial mínimo
| Dashboard gerencial mínimo | ✅ 2026-07-26 | `GET /api/v1/dashboard/resumen` (`src/core/dashboard_router.py`, permiso `dashboard.leer`): ventas del día (cantidad+total), stock bajo mínimo, cajas abiertas — agregador en `core`, nunca importa dominio de otro módulo (ADR-012). Requirió construir dos huecos que no existían: `sales` no tenía ningún listado de ventas, `accounting` tenía los modelos de caja (`apertura_caja`/`cierre_caja`/`arqueo`, migrados desde 2026-07-20) sin capa de aplicación. **Slice mínimo de caja** (`accounting.application.caja`): abrir/cerrar/arquear con **reconciliación real** (el cierre calcula `monto_esperado` desde los pagos en efectivo reales, vía contrato público de `sales`, no un número tipeado sin verificar). Primer frontend real: login por PIN + pantalla de dashboard en Next.js. Fuera de esta fase, a propósito: RN-POS-009..013 completas, relevo autenticado por PIN, máquina de estados de `custodia_efectivo` — ver Deuda técnica. |

### 2026-07-26 — Protección de datos personales (Ley 29733)
| Protección de datos personales (Ley 29733) | 🔶 ARCO técnico ✅ 2026-07-26 | `docs/security/proteccion-datos-personales.md`: qué datos trata el ERP y dónde viven (casi todo en `persona`, fuente única — RN-GEN-007; la excepción deliberada es `postulante`, ver 2026-08-01), derechos ARCO, plazos de conservación, medidas de seguridad ya vigentes (referenciadas, no reconstruidas), proceso de brecha. Cancelación implementada como **anonimización irreversible** de `persona`, no `DELETE` — `POST /api/v1/personas/{id}/anonimizar`, permiso dedicado `personas.anonimizar`, migración `dad43729501d` (RN-PER-007, ADR-011). Acceso/Rectificación ya existían (`GET`/`PATCH /personas/{id}`). Pendiente de **acción del usuario, no de código**: registro del banco de datos ante la ANPD, aviso de privacidad público, confirmar plazos de retención con el contador/abogado, jurisdicción de transferencia internacional. Pendiente técnico: ver Deuda técnica. |

### 2026-07-26 — Contrato OpenAPI de la API
| Contrato OpenAPI de la API | ✅ 2026-07-26 | `docs/architecture/openapi.json` exportado (`python -m src.core.openapi_export`) y verificado en CI — un endpoint que cambia sin regenerar el contrato falla el PR (ADR-010). `TAGS_METADATA` en `src/core/app.py` describe los 15 tags de la API; un tag nuevo sin descripción falla un test. De paso, corregidas dos afirmaciones falsas en `api-guidelines.md`: `idempotency_key` es campo del body, no header; las colecciones devuelven array plano, no `{items,total,page,page_size}` (nunca se implementó paginación). |

### 2026-07-26 (actualizado hasta 2026-08-15) — CI/CD
| CI/CD | 🔶 CI + entrega ✅ 2026-07-26 · e2e en CI 2026-08-06 | **Job `e2e`** (2026-08-06): el flujo del dinero de punta a punta sobre chromium, con `test-results/` como artefacto cuando falla — el único job que comprueba que cliente y servidor estén de acuerdo. `ci.yml` gana tres verificaciones que no existían: cabeza única de Alembic (una doble falla en el despliegue, no en el merge que la crea), construcción de la imagen **y arranque real del contenedor** contra `/health`, y `pip-audit` informativo. `release.yml` publica la imagen en GHCR en cada push a `main` (tags `v*` → versión exacta). `docker-compose.prod.yml` nuevo: el compose existente es solo desarrollo y desplegarlo publicaría esa configuración. Dockerfile con usuario sin privilegios y `HEALTHCHECK`. El **despliegue sigue manual** y documentado hasta que exista el VPS (ADR-008). **Job `uso`** (2026-08-15, ADR-047): recorridos completos con captura, artefacto **siempre** (no solo al fallar). Queda **fuera de los seis checks requeridos** por el ruleset y con `continue-on-error` — un recorrido lento no puede bloquear un arreglo de caja; agregarlo al ruleset sería cambiar esa decisión, no corregir un olvido. **Arnés de paralelo** (2026-08-15): `E2E_PUERTO_WEB` (el par de `E2E_PUERTO_API`, que existía solo) y resolución automática del `.venv` desde un worktree, para que dos agentes puedan correr Playwright a la vez — esquema de slots en `docs/engineering/trabajo-en-paralelo.md`. |

### 2026-08-09 — Paquete de demo portable
| Paquete de demo portable | ✅ 2026-08-09 | `python scripts/empaquetar_demo.py` → `ZIP_<versión>/provecho-demo-<versión>.zip`: el ERP entero en la PC de quien prueba, sin internet ni servidor, con doble clic en `INICIAR.bat` (`admin` / PIN `123456`). Nace de que no hay VPS todavía y esperar a tenerlo era esperar para poner el sistema frente a la gente que lo va a usar. `docker-compose.demo.yml` **no publica nada en internet** —secretos versionados a propósito— y no tiene `build:` porque en esa PC no hay código fuente; su servicio `init` migra y siembra en cada arranque, que es lo que convierte cuatro comandos de consola en un solo `up`. Trajo dos cosas que faltaban por su cuenta: la **imagen de producción del frontend** (etapa `runner` con `output: "standalone"`, ~250 MB contra ~1.5 GB del `npm run dev` que era la única que existía) y `COOKIE_SECURE`, sin el cual la sesión moría en silencio al entrar desde la tablet del local por http. Vigilado por `tests/test_repo_coherencia.py` (imágenes del compose == imágenes que el ZIP exporta, y el Node de la imagen == el del CI). De paso destapó que la **versión declarada llevaba tres releases congelada**: `cortar_version.py` cortaba el CHANGELOG pero nunca tocaba `pyproject.toml` ni `frontend/package.json`, que seguían en `0.1.0` con el repo en `v0.4.0` — la versión vivía solo en el tag de git. Ahora el script las escribe y un test las vigila; el ZIP además lleva `VERSION.txt` con el commit exacto. Límites conocidos: un solo usuario, reset manual, y Docker Desktop como requisito duro. Ver `docs/engineering/devops.md#paquete-de-demo-portable`. |

### 2026-07-26 — Chequeos de salud y alertas
| Chequeos de salud y alertas | ✅ 2026-07-26 | `src/core/health.py` + `health_router.py`: `/health` (liveness, sin dependencias), `/health/ready` (base de datos crítica → 503; Redis y cola degradan sin sacar de rotación) y `/health/backups` (503 pasadas 26 h — cubre el backup que nunca corrió, que no genera evento de error). El ERP expone estado; **un monitor externo alerta** (ADR-007): construir alertas dentro del servidor que se monitorea deja de avisar justo cuando ese servidor cae. Pendiente: contratar el monitor y dar de alta las sondas. |

### 2026-07-26 — Observabilidad (métricas, trazas, logs centralizados)
| Observabilidad (métricas, trazas, logs centralizados) | 🔶 logs + errores ✅ 2026-07-26 | `src/core/logging_config.py`: JSON en producción, tres flujos (`app`/`seguridad`/`auditoria`) derivados del nombre del logger, `request_id` por request (respeta `X-Request-ID` entrante, sale en la cabecera y en el cuerpo del error 500), redacción de PIN/tokens/`Authorization`. `src/core/sentry.py`: reporte de errores en `api`, `worker` (señal `celeryd_init`) y `backups`; sirve para Sentry o GlitchTip autoalojado, no-op sin DSN. Pendiente: métricas, trazas y colector de logs — ver Deuda técnica. |

### 2026-08-12 — UX: menús, buscadores, breadcrumbs, atajos, sidebars, dashboards
| UX: menús, buscadores, breadcrumbs, atajos, sidebars, dashboards | 🔶 2026-08-12 | **Paleta de comandos** (`Ctrl+K`, `components/shell/paleta-comandos.tsx`) sobre Base UI Autocomplete — sin `cmdk`: motor de fuzzy search para ~50 entradas estáticas y arrastra Radix, que ADR-013 descartó. Los destinos salen de `lib/navegacion.ts`, se arman en servidor y llegan filtrados por permiso; cada resultado es un `<Link>` real (Enter, clic central y «abrir en pestaña nueva» funcionan solos). Sidebar con ítem activo y submenú registrado en un solo archivo. Atajo `/` para el buscador de la tabla. Pendiente: breadcrumb por ruta recorrida, atajos por acción dentro de una pantalla, dashboards configurables |

### 2026-07-26 — UX: breadcrumb por ruta de usuario + tooltip de ayuda por campo (spec)
| UX: breadcrumb por ruta de usuario (no jerárquico) + tooltip de ayuda por campo de formulario | ✅ spec 2026-07-26 | `docs/product/ui-ux.md` — breadcrumb crece con la navegación (patrón Odoo), navegación jerárquica va por menús desplegables; todo campo de formulario lleva hover explicando término/formato. Solo especificado |

### 2026-07-04 — Branding (paleta, tipografías, tokens CSS)
| Branding (paleta, tipografías, tokens CSS) | ✅ 2026-07-04 | Brandboard aplicado — `docs/product/ui-ux.md` |

### 2026-08-12 — Skins multi-marca, accesibilidad y plataformas por módulo
| Skins multi-marca (PDV/Kiosk por marca vs **Provecho** en el resto — Majambo no tiene tema propio, decidido 2026-07-27), accesibilidad (2 paletas + 4 niveles de tamaño de fuente, catálogo definido 2026-07-27) y plataformas por módulo (táctil Android en PDV/Kiosk/KDS/Inventario, PC-first en el resto) | 🔶 accesibilidad ✅ 2026-08-12 | **Accesibilidad implementada (ADR-037)**: paleta de alto contraste (Okabe-Ito, cubre el par rojo-verde), escala de letra en cuatro niveles y modo oscuro, las tres en el perfil del usuario y no en el dispositivo — en un local la misma tablet la usan tres turnos. Se resuelven en el servidor (`class="dark"`, `data-escala`, `data-paleta` en `<html>`): `next-themes` exigiría un script inline que la CSP con nonce tendría que autorizar. Paleta y tema se combinan. `Insignia` ata el ícono al tono, que es lo que hace cumplible «ningún estado solo por color». Pendiente: resolver de tema por marca para PDV/Kiosk |

### 2026-07-27 — F2: Arquitectura de frontend (documento maestro)
| F2 — Arquitectura de frontend (documento maestro) | ✅ spec 2026-07-27 | `docs/product/frontend-architecture.md` — 31 secciones (tokens, componentes base/especializados, layout, navegación, estado, tablas, formularios, tiempo real, permisos visuales por rol, etc.) con estado por sección y los 6 puntos a cerrar antes de los diseños finales del alfa (layout general, componentes base, tablas, permisos visuales, arquitectura de carpetas, decisión de estado). Solo especificado — ver detalle en Deuda técnica → Frontend |

### 2026-08-29 (en curso) — Parche desplegables con búsqueda (combobox transversal)

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

### 2026-07-27 / 2026-08-02 — Mecanismo para los valores operativos configurables
- ✅ 2026-07-27 **Mecanismo para los valores operativos configurables**
  (umbral de OC, margen de contribución mínimo,
  margen de error de ajuste, monto de caja chica, plazo de envío de
  comprobantes, rangos salariales): decidido con el usuario que **no son
  valores fijos** — se configuran en `parametro_empresa` por empresa, los
  gestiona Gerencia, y un cambio puede sustentarse en un acta
  (`decision_gerencial`) cuando amerite (no obligatorio para un ajuste
  rutinario). Ver ADR-014, `data-model.md` §8c, RN-GER-008 y
  `docs/gerencia/politica-gerencia.md#parámetros-operativos-configurables`.
  **Ampliado 2026-08-02** (ADR-014 Addendum, RN-GER-009): cada parámetro
  se configura **desde el módulo al que pertenece**, pero el cambio **no
  surte efecto hasta que Gerencia lo aprueba** en su sección de
  aprobaciones (aceptar / rechazar / modificar). Implementado: entidad,
  migración `a71c9f4b2e60`, endpoints `/api/v1/parametros[/{id}/aprobar|
  /rechazar]`, un permiso por módulo `<modulo>.proponer_parametro`.
  Lo que queda abierto por cada uno de los puntos de abajo ya **no es el
  mecanismo** (resuelto e implementado) sino que **el área proponga y
  Gerencia apruebe el valor real** — trabajo de configuración/negocio, no
  bloquea código (los valores propuestos por cada módulo el 2026-08-05 se
  documentan en el historial de su propio módulo).

### 2026-07-27 — Catálogo de paletas de accesibilidad y niveles de tamaño de fuente
- ✅ 2026-07-27 Catálogo de paletas de accesibilidad y niveles de tamaño de
  fuente — propuesta técnica definida (dos paletas: Provecho estándar y
  un modo alto contraste/daltonismo inspirado en Okabe-Ito que cubre
  protanopía+deuteranopía; 4 niveles de tamaño de fuente vía
  `--font-scale`). `docs/product/ui-ux.md#catálogo-de-paletas-y-tamaños-de-fuente-propuesta-técnica-2026-07-27`.
  Sujeta a ajuste si aparece validación real con usuarios daltónicos/baja
  visión. Sin implementar todavía.

### 2026-07-27 — Grupo Majambo no tiene tema propio
- ✅ 2026-07-27 Grupo Majambo **no tiene tema propio** — Provecho es el
  único tema fuera de PDV/Kiosk (`docs/product/ui-ux.md`).

### 2026-08-23 — Droplet de staging levantado
- ✅ 2026-08-23 **Droplet de staging levantado** (DigitalOcean, ver
  [`docs/engineering/staging.md`](docs/engineering/staging.md) para IP,
  dominios y bitácora — nunca secretos ahí). Usuario `app` sin root/password
  por SSH, firewall, Docker, DNS de `staging.majambo.com.pe` y
  `api-staging.majambo.com.pe` ya resueltos. Escrito en el repo:
  `docker-compose.staging.yml`, `Caddyfile` (TLS automático, elegido sobre
  nginx+certbot para no mantener renovación a mano), `.env.staging.example`,
  `scripts/desplegar.sh` y `release.yml` publicando también la imagen del
  frontend (`ghcr.io/rrojasda94/provecho-erp-web`) — antes solo publicaba el
  backend, staging no habría tenido pantallas.

### Pendiente — Falta para terminar el primer despliegue de staging
- ⬜ **Falta para terminar el primer despliegue de staging:**
  1. `.env` real en el servidor (`JWT_SECRET`/`POSTGRES_PASSWORD` generados
     ahí, nunca en una conversación — un secreto que la pasó deja de serlo).
  2. `docker login ghcr.io` con el token de lectura ya generado.
  3. Primer `docker compose -f docker-compose.staging.yml up -d` y
     verificación de `/health/ready`.
  4. Cron de backup diario (`python -m src.backups.backup`) y purga semanal
     de postulantes (`python -m src.modules.rrhh.purga`) dados de alta en
     el droplet.
  5. Monitor externo (healthchecks.io/UptimeRobot) contra `/health`,
     `/health/ready`, `/health/backups` — es lo único que no se puede
     resolver dentro del VPS (ADR-007).

### 2026-08-27 — Landing pública del QR con dominio propio
- ✅ 2026-08-27 **La landing pública del QR tiene dominio propio**
  (`clientes.majambo.com.pe`, ADR-080). El QR de la mesa apuntaba a
  `staging.majambo.com.pe/reconocerte`: un nombre que dice «staging» y cuya
  raíz es el ERP entero. El recorte va en el `Caddyfile` —no en
  `middleware.ts`, cuyo `matcher` excluye los prefetch y dejaría el guard
  esquivable con una cabecera— y solo deja pasar `/reconocerte*`,
  `/_next/static/*`, `/_next/image*`, `/marcas/*` y el favicon; el resto
  redirige 302 a la landing. Verificado con `caddy validate` + `caddy adapt` y
  un Caddy local contra el dev server: las dos trampas de sintaxis que caza
  ese paso (`redir` sin `*`, orden de los `handle`) producen configuraciones
  **válidas** que hacen otra cosa. **No es un control de seguridad** y **no es
  el padrón real**: `/login` sigue público en el otro dominio, y lo que se
  registre cae en la base desechable de staging. Nada de esto llega al droplet
  hasta que alguien copie el `Caddyfile` a mano — ver `staging.md` y
  `deuda/ci-cd.md`.

### Pendiente (decisión 2026-08-05) — Producción sigue parqueada
- ⬜ **Producción sigue parqueada** (decisión 2026-08-05): dominio real,
  decidir dónde vive la copia on-premise de los backups, y stack de
  observabilidad (`docker-compose.observabilidad.yml`) — todo eso se retoma
  cuando exista la máquina de producción, staging no la reemplaza.

### 2026-07-14/15 (plan original) — Fase de procesos (tras el modelado de BD)

1. `users`: auth (login PIN → JWT/refresh), RBAC, contexto de tenant, auditoría base.
2. Organización: grupo → empresa → marca → sucursal → almacén (vive en `users` o módulo `organization`).
3. `inventory`: artículos, stock por almacén, movimientos.
4. `purchases`: proveedores, OC, recepción → entrada a almacén central.
5. Solicitudes + transferencias central → local.
6. `sales`: PDV, recetas, descuento automático de insumos, pagos, Nubefact.
7. Producción, contabilidad, RRHH, resto de módulos.

### 2026-07-25 (siguiente sesión tras el slice de Venta) — Modelado de BD

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

### 2026-07-20 — Revisión de consistencia y correcciones

Revisión completa del proyecto (SOPs, áreas, docs transversales, specs).
Correcciones aplicadas en la misma sesión:

- **git init** con commit inicial del estado previo (trazabilidad).
- Identidad: Provecho = ERP, Grupo Majambo = grupo (00_PROJECT, CLAUDE).
- ADRs normalizados a 3 dígitos; ruta corregida en CLAUDE.md; **ADR-004**
  nuevo: tenant por filtro de aplicación (`empresa_id` obligatorio +
  tests; RLS como refuerzo futuro).
- Glosario: **Horario laboral** vs **Horario de atención** definidos;
  "horario de trabajo" reemplazado; `sucursal.horario_atencion` en
  data-model.
- Catálogo de eventos sincronizado con las specs (10 eventos agregados,
  incl. `inventory.lote_vencido_detectado`); READMEs de módulos y mapa
  `diagrams/modules.md` alineados.
- Data-model: bloque Compras completo (caja chica, compra directa,
  evaluación de proveedor, requerimiento de activo), `stock_lote`
  (FEFO/FIFO implementable + bloqueo de vencidos con memorándum),
  `ajuste`, `apertura_caja`/`cierre_caja`/`arqueo` (caja ya no es módulo
  "futuro"), `flota`, `combo`, `plantilla`; `contrato` reubicado como
  transversal; `articulo.tipo` + `suministro` (enum extensible).
- `PROC-CMP-001` v1.0 → v2.0 (3 caminos de compra, pago en Contabilidad).
- Limpieza: borradores `Procesos/Ventas/` y `diagrams/Ventas.bpm`
  eliminados; doble extensión `.bpmn.bpm` corregida; `diagrams/README.md`
  reescrito (SOP primero → BPMN después; versiones antiguas se conservan).
- CHANGELOG puesto al día (todo el trabajo del 2026-07-19 + esta sesión).
- Skill `sop-creator` endurecida para no dejar cabos sueltos (ver skill).

## Fuentes

Rangos de línea de `ROADMAP.md` usados (estado del archivo al iniciar esta
tarea, sin modificarlo):

- Líneas 9-21 (tabla F0: scaffold, docs, core, auditoría arquitectónica,
  errores de API, modelado de BD, migraciones, seeders).
- Línea 25 (Persona CRUD + lock optimista + contrato público).
- Línea 40 (BI/reportes/Superset/Supervisión/CRM/tesorería/activos/proyectos).
- Líneas 46-50/51 (auditoría transversal, endurecimiento de producción, app
  Android, arquitectura frontend, offline PDV — hub local, nótese que la fila
  50-51 es una sola celda de tabla partida en dos líneas físicas).
- Líneas 52, 54-62, 64-66 (backups, dashboard, protección de datos, OpenAPI,
  CI/CD, demo portable, salud, observabilidad, UX, branding, skins/
  accesibilidad, F2 frontend).
- Líneas 96-135 (parche de desplegables con búsqueda / combobox transversal).
- Línea 318 (fila `feat/auditoria-pantalla` de la Ola 3, solo la parte de la
  pantalla transversal de `audit_log`).
- Líneas 380-398 (mecanismo de parámetros operativos configurables — solo el
  mecanismo, no los valores propuestos por cada módulo).
- Líneas 508-516 (catálogo de paletas de accesibilidad; Majambo sin tema
  propio).
- Líneas 532-568 (droplet de staging, pendientes de despliegue, landing con
  dominio propio).
- Líneas 569-572 (producción parqueada).
- Líneas 688-730 (Modelado de BD — siguiente sesión).
- Líneas 1079-1107 (Revisión de consistencia y correcciones).
- Líneas 1405-1413 (Fase de procesos, plan original).

Excluido a propósito (va en `calidad-y-auditorias.md` u otros historiales por
módulo): las rondas "Auditoría Ola 1/2/4" y "Catálogo modelo Odoo" (líneas
189-373 salvo las excepciones puramente transversales ya listadas), los
parches de PDV/compras/inventario/contabilidad específicos de cada módulo
(líneas 68-95, 137-330), y el índice de Deuda técnica (líneas 574-605, fuera
de alcance por instrucción explícita).
