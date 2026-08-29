# ADR-082 — BI autoservicio con Superset sobre vistas de solo lectura

- **Estado:** aceptada, en implementación por fases
- **Fecha:** 2026-08-29
- **Contexto:** `core/reportes` (motor de consulta), `core/dashboard_router`
  (KPIs), `core/tenant` (alcance), `frontend/app/(app)/dashboard`
- **Relacionado:** ADR-024 (catálogo cerrado de reportes — esta ADR ejecuta
  la salida que dejó escrita, no la revoca), ADR-004 (estrategia de tenant),
  ADR-012 (dashboard gerencial), ADR-036 (destinos accionables)

## Contexto

ADR-024 le puso un límite deliberado al dashboard: catálogo cerrado, sin
constructor de consultas, por tres motivos — superficie de inyección SQL,
fuga de RBAC ("el permiso protege recursos, no tablas") y costo real de
mantener un motor de exploración libre. Ese ADR dejó la puerta de salida
escrita:

> Si aparece demanda real de exploración libre, el camino no es abrir el
> constructor sino exportar a una herramienta de BI con su propio control de
> acceso sobre una réplica de lectura.

Esa demanda apareció: elegir libremente qué va en el eje X, el eje Y y el
valor; cruzar dimensiones; más tipos de gráfico (pie, área, apiladas,
heatmap); comparar contra el periodo anterior; buscar valores escribiendo
texto. Nada de eso cabe en un catálogo de reportes fijos sin que cada
combinación nueva sea una entrada más en `catalogo.py`.

Además, tres módulos con datos ricos no tienen ningún reporte hoy
(`production`, `rrhh`, `marketing`) y `accounting` tiene uno solo
(`estado_caja`). Sumarlos al catálogo cerrado, uno por uno, no escala al
mismo ritmo que abrirlos como datasets de un BI.

## Decisión

**El catálogo cerrado de ADR-024 no se toca** (salvo sumar `pie`/`area` como
visuales y `marca_id` como filtro — ver Fase D). Sigue siendo el dashboard
operativo del día a día: rápido, con el permiso de cada módulo dueño, con
enlaces accionables (ADR-036). El constructor de consultas que ADR-024
rechazó **sigue rechazado ahí**.

Lo que se agrega es un producto aparte, detrás de su propia puerta:
**Apache Superset**, conectado a Postgres con un rol de solo lectura que
**no ve ninguna tabla base**, solo un conjunto de vistas SQL creadas para
este propósito.

### Por qué Superset y no Metabase

Metabase OSS no trae *row-level security* multi-tenant en su edición
gratuita — es función de pago (sandboxing). Dado que Majambo es multi-marca
y multi-sucursal, y que filtrar por alcance es la condición no negociable de
este ADR, Metabase gratis solo serviría para tableros de solo lectura
curados por un admin, no para autoservicio real. Superset es Apache 2.0
completo: RLS, constructor "Explore" con ~40 tipos de gráfico, filtros con
búsqueda de texto y *guest tokens* para embeber, todo sin licencia.

### Tres barreras independientes

1. **Rol de Postgres `bi_lector`**: `GRANT SELECT` únicamente sobre las
   vistas `vw_bi_*` y `bi_alcance_usuario`. No alcanza `usuario`,
   `boleta_pago`, ni ninguna tabla base — aunque la RLS de Superset o el
   permiso de la aplicación fallaran, el rol de base de datos por sí solo
   ya limita el daño.
2. **RLS de Superset**, una cláusula por grupo de datasets, contra
   `bi_alcance_usuario`.
3. **Permiso de aplicación `bi.acceder`**: sin él Provecho no emite código
   OAuth (Fase B) y no hay login posible en Superset.

### Dónde corre (corregido 2026-08-29)

Uso real esperado: decenas de consultas al mes sobre miles de filas, sin
apuro de latencia. Eso descarta agrandar el droplet de staging (2 vCPU/4 GB,
donde vive caja/PDV) a 4 vCPU/8 GB solo para esto — sería pagar de más y,
peor, compartir recursos entre una consulta analítica pesada y el cobro.

Superset corre en un **droplet aparte y chico** (DigitalOcean, tier
Premium ~$8/mes, 1 vCPU/1 GB), en la misma VPC privada que el droplet de
staging. Postgres sigue siendo uno solo —el de staging—; Superset guarda su
metadata en un esquema aparte ahí y llega por la red privada, nunca por IP
pública. El firewall de DO solo deja pasar el puerto de Postgres desde la
IP interna de este droplet nuevo.

Para caber en 1 GB se recorta lo que pide más memoria: sin Celery
worker/beat, sin Redis propio, sin *Alerts & Reports* (el PDF programado por
correo, que necesita Chromium headless). Las consultas corren de forma
sincrónica —aceptable porque nadie mira el reloj— y la exportación se
resuelve por el navegador (imprimir/CSV/XLSX), no por el servidor. Un swap
de 2 GB cubre el margen que la RAM física no da.

### El costo que se acepta

ADR-004 filtra tenant **en la aplicación** (`src/core/tenant.py`), no con
RLS de Postgres. Superset se conecta directo a la base: `Tenant` no lo
protege. La regla de "qué sucursales ve cada quien" pasa a vivir en **dos
lugares** — los claims del JWT que resuelve `Tenant`, y la vista
`bi_alcance_usuario` que consulta la RLS de Superset — y pueden divergir en
silencio si alguien cambia uno sin el otro.

La mitigación no es duplicar la lógica sino duplicar el *punto de
aplicación*: ambos leen, en última instancia, las mismas tablas
(`usuario_sucursal`, `rol_permiso`, `permiso`). `bi_alcance_usuario` es una
vista sobre esas tablas, no una copia de su contenido. Y hay un test que
congela la equivalencia: `tests/test_bi_alcance.py`, que compara, para cada
usuario, el conjunto de sucursales que devuelve la vista contra el que
resolvería `UsuarioRepo.sucursal_ids` (lo mismo que `build_claims` pone en
el JWT). Corre contra Postgres real en el job `migraciones` de CI. Si este
test se borra alguna vez, la advertencia de este párrafo deja de tener
quien la sostenga.

## Fases

| Fase | Qué entrega | Estado |
|---|---|---|
| A | Vistas `vw_bi_*` + `bi_alcance_usuario`, rol `bi_lector`, índices de soporte, test de equivalencia | **Hecho** |
| B | Provecho como proveedor OAuth2 para el SSO de Superset | **Hecho** (esta entrega) |
| C | Superset desplegado en droplet aparte (compose, Caddy, RLS, aprovisionamiento) | Código y ensayo local **hechos**; el droplet real, pendiente |
| D | Integración en Provecho (permiso, navegación, tableros embebidos, mejoras al tablero ADR-024) | **Hecho** (esta entrega) — verificado en navegador real |
| E | Exportación (print, XLSX completo, CSV) | **Hecho** (esta entrega) |
| F | Resto de documentación/registros de cada fase | Junto con cada una |

### Fase A — capa semántica (esta entrega)

Migración `832ff01ed33f_vistas_bi_y_rol_de_solo_lectura`:

- Diez vistas `vw_bi_*` (ventas, pagos, inventario, stock, compras,
  contabilidad, caja, producción, asistencia RRHH, encuestas de marketing).
  Cada una repite el criterio que ya usa su `queries_publicas.py`: fecha de
  negocio (`fecha_orden`, nunca `created_at`), mismo predicado de "ingreso
  real" (`estado in ('pagada','facturada')`), `marca_id` resuelto vía
  `sucursal.marca_id` (dimensión que **ningún** reporte del catálogo usa
  hoy), y ninguna columna sensible (RRHH expone tardanzas y horas extra,
  nunca remuneración — mismo límite que
  `rrhh/queries_publicas.nombres_por_usuario`).
- `bi_alcance_usuario`: el puente descrito arriba.
- Rol `bi_lector`, creado solo si `BI_LECTOR_PASSWORD` está en el entorno
  (en dev/CI sin esa variable, las vistas igual se crean — son las que
  valida el test — pero no un rol con clave vacía). `statement_timeout` de
  120 s, mismo criterio que `SessionReportes`
  (`src/core/database.py`).
- Índices: `venta(fecha_orden, estado)`, `movimiento_inventario(ts,
  almacen_id)`, `asiento(fecha, empresa_id)`, `asistencia(fecha,
  trabajador_id)` — declarados también en los modelos SQLAlchemy
  correspondientes para que `alembic check` no los vea como deriva.
- `inventory.application.stock.contar_bajo_minimo` pasó de traer toda la
  tabla `stock` de la empresa a Python y contar en un bucle, a un
  `COUNT` agregado en SQL — mismo resultado, sin el full-scan que la carga
  adicional del BI habría hecho notar tarde o temprano.

### Fase B — Provecho como proveedor OAuth2 (esta entrega)

El obstáculo que decidió el diseño: la sesión de Provecho
(`provecho_token`) es una cookie **httpOnly y host-only** de
`staging.majambo.com.pe` (`frontend/lib/sesion-refresh.ts`), y la API vive
en `api-staging.majambo.com.pe` — otro subdominio al que esa cookie nunca
llega. Un `/oauth/authorize` implementado como endpoint puro de FastAPI no
podría leer esa sesión desde el navegador. Ampliar la cookie a
`.majambo.com.pe` para que "llegara" está descartado desde el planteo
original de este ADR.

La solución: el paso que ve el navegador —`GET /oauth/authorize`— vive en
**el frontend** (`frontend/app/oauth/authorize/route.ts`), donde la cookie
sí existe. Ese Route Handler:

1. Lee la sesión de la cookie. Sin ella, redirige a `/login?next=...` con
   la URL de vuelta exacta — el `next` se valida contra
   `^/oauth/authorize(\?...)?$` en `login/actions.ts`, la única ruta que
   puede pedir un destino distinto de `/`; cualquier otro valor cae al
   home. Es la única defensa contra que ese parámetro se use como open
   redirect.
2. Con sesión, llama a `POST /api/v1/oauth/codigo` (backend, JWT + permiso
   `bi.acceder`) para que la API — no el frontend — valide `client_id` y
   `redirect_uri` contra lo configurado y emita un código de un solo uso.
3. Solo si la API aceptó el `redirect_uri` (si no, `apiFetch` lanza y el
   handler responde un JSON de error desde el propio origen, sin
   redirigir a ningún lado) arma la redirección final hacia Superset con
   `code` y `state`.

`src/core/oauth/` (router + `servicio.py`) implementa el resto, sin tabla
nueva — código y access token viven en **Redis** con TTL corto (ninguno de
los dos se pensó para durar una sesión) y **fallan cerrado**: al revés que
`core/rate_limit.py` (fail-open a propósito, ahí lo peor es no frenar a
alguien), acá un Redis caído tiene que cortar el SSO, no dejarlo pasar.

| Endpoint | Quién lo llama | Auth |
|---|---|---|
| `POST /oauth/codigo` | `frontend/app/oauth/authorize/route.ts` | JWT de Provecho + `bi.acceder` |
| `POST /oauth/token` | Superset, servidor-a-servidor | `client_id`/`client_secret` (RFC 6749 §4.1.3) |
| `GET /oauth/userinfo` | Superset, servidor-a-servidor | El access token que acaba de emitir `/token` |

El código se canjea con `GETDEL` (Redis ≥ 6.2): lectura y borrado en un solo
comando atómico, así que dos canjes concurrentes con el mismo código nunca
pueden ganar los dos.

`bi.acceder` (RN-BI-004) queda seedeado en `admin` (vía `*`), `supervisor` y
`contador` — la asignación de rol que Fase D iba a hacer se adelantó acá
porque `/oauth/codigo` no tiene sentido sin ella. Lo que queda para Fase D
es la navegación (entrada en `frontend/lib/modulos.ts`), no el permiso.

### Fase C — Superset desplegado (código y ensayo local hechos)

Sin acceso a la cuenta de DigitalOcean del usuario ni a los droplets, esta
fase se cerró hasta donde se puede verificar sin infraestructura real:
`docker-compose.bi.yml`, `deploy/bi/` (Dockerfile, `superset_config.py`,
`Caddyfile`), `scripts/superset_provision_db.sql` y `scripts/
superset_init.py`, todo ensayado de punta a punta contra un Superset y una
Postgres reales corriendo en Docker localmente — no solo revisado a ojo.
El runbook completo (droplet, VPC, firewall, DNS, Postgres remoto) vive en
`docs/engineering/bi-superset.md`, junto con el detalle de cada bug.

El ensayo local encontró cuatro problemas reales que ninguna revisión de
código habría atrapado, todos ya corregidos:

- La imagen "lean" de `apache/superset` (la que corresponde a producción,
  sin sufijo `-dev`) no trae `psycopg2` — `superset db upgrade` fallaba con
  `ModuleNotFoundError`. Se resolvió con una imagen propia de una capa
  (`deploy/bi/Dockerfile`).
- Ese `pip install` tiene que apuntar al venv de Superset
  (`/app/.venv`, sin `pip` propio) y no al `pip` del sistema, que
  "funciona" pero instala en el lugar equivocado.
- `current_username()` sin llaves no es SQL de Postgres: es un macro de
  **Jinja** de Superset (`{{ current_username() }}`) que se interpola del
  lado de Superset antes de mandar la consulta. Necesario porque la
  conexión analítica corre siempre como `bi_lector` — una sola credencial
  para todos los usuarios de Superset — así que un `current_user` de
  Postgres jamás distinguiría a una persona de otra.
- Sin la feature flag `ENABLE_TEMPLATE_PROCESSING`, ese macro tampoco se
  interpola aunque esté bien escrito: la RLS queda comparando contra el
  texto literal, nadie coincide nunca, y la consulta responde `200` con
  cero filas para todo el mundo — sin ningún error que avise. Se detectó
  inspeccionando el SQL efectivo que Superset mandaba a Postgres
  (`POST /api/v1/chart/data`), no por inferencia.
- El rol `Gamma` de fábrica no alcanza los datos: sin `datasource_access`
  explícito por dataset, cualquier consulta devuelve 403
  `DATASOURCE_SECURITY_ACCESS_ERROR`. `scripts/superset_init.py` se lo
  otorga al rol marcador `ProvechoBI` — los diez datasets, ni uno más, que
  es exactamente lo único que la conexión `bi_lector` puede ver.

La verificación real —RLS aplicada, permiso concedido, consulta ejecutada
como un usuario sin `Admin`, con el SQL final inspeccionado— se hizo contra
una Postgres y un Superset desechables en Docker, con las mismas vistas y
el mismo rol `bi_lector` de la Fase A. Lo que falta y **no** se puede cerrar
sin las credenciales del usuario: crear el droplet real, la VPC, el
firewall, el registro DNS, y correr el mismo `scripts/superset_init.py`
contra la Postgres de staging de verdad.

### Fase D — Integración en Provecho (esta entrega, verificada en navegador real)

**D.1 Permiso y navegación.** Entrada `bi` en `frontend/lib/modulos.ts`, con
`permiso: "bi.acceder"` explícito (no por prefijo): entrar acá ya es un
privilegio, mismo criterio que "Catálogo" en ese archivo. `frontend/app/
(app)/bi/{layout,page}.tsx` — la página es hoy un enlace a Superset
(`BI_URL`, leída del servidor y no como `NEXT_PUBLIC_*`, mismo criterio que
`GOOGLE_MAPS_BROWSER_KEY`) con degradación explícita a "no configurado" si
la variable está vacía.

**D.2 Guest tokens para embeber (mecanismo listo, sin dashboards reales
todavía).** `src/shared/integrations/superset/client.py` — adaptador nuevo
bajo `shared/integrations/` (regla del proyecto: nunca llamar a un externo
desde fuera de un adaptador), con su propia cuenta de servicio de Superset
(`SUPERSET_INTERNAL_URL`/`SUPERSET_SERVICE_USERNAME`/`_PASSWORD`) — **no**
la misma vía que el SSO humano de Fase B, son dos direcciones de la misma
integración sin nada en común salvo el destino. `src/core/bi_router.py`
expone `GET /bi/dashboards/{id}/guest-token`, con `bi.acceder` y una
whitelist explícita (`BI_DASHBOARDS_EMBEBIBLES`) — aunque la fila ya la
filtra la RLS del dataset (Fase C), no cualquier UUID que alguien mande en
la URL debe poder pedirse un token. Whitelist vacía por defecto: **no se
inventó ningún dashboard de ejemplo** para no fingir un embebido que no
existe. El widget de embebido del lado del frontend
(`@superset-ui/embedded-sdk`) queda para cuando haya tableros reales que
apuntar —construirlo antes sería exactamente el patrón que este ADR viene
evitando: código que nadie puede ejecutar contra algo real todavía.

**D.3 Mejoras al tablero de ADR-024, sin depender de Superset.**
- **Filtro por marca**: `marca_ids` en `FiltrosIn`
(`src/core/reportes/router.py`) se resuelve a las sucursales de esas marcas
y se **une** con `sucursal_ids` explícito —no lo reemplaza— antes de pasar
por `_sucursales_efectivas`, así que ningún reporte cambió una sola línea:
"marca" es un atajo sobre el mismo mecanismo de sucursal que ya existía y
ya tenía el RBAC resuelto.
- **`pie` y `area`** sumados a `VISUALES` (`catalogo.py`) y al `Literal` de
`TarjetaIn.visual` (`router.py`): como son el valor por defecto de
`visuales` en cada `Reporte`, los 14 reportes los ofrecen sin tocarlos uno
por uno. `GraficoPie`/`GraficoArea` en `graficos.tsx`, mismo patrón que
`GraficoBarras`/`GraficoLineas` (Recharts + `ChartContainer` del wrapper de
shadcn ya instalado — cero dependencias nuevas).
- **Título editable**: el campo ya se persistía
(`Tarjeta.titulo`) pero no había UI. `tarjeta-reporte.tsx` cambia el
`CardTitle` de solo lectura por un `Input` en modo edición.

Verificado de punta a punta en un navegador real (Docker: Postgres +
backend + frontend, admin/cajero1 de verdad, no solo lectura de código):
el selector de visualización ofrece las 5 opciones, `pie` renderiza (vacío,
sin datos de venta en la base de prueba, sin romper), el título se edita y
persiste, el filtro "Marcas" aparece junto al de sucursales, `/bi` degrada
a "no configurado" para `admin`, y `cajero1` (sin `bi.acceder`) recibe
"Sin permiso" — RBAC real, no solo el 403 de la API.

**Un bug de entorno, no del código, que vale dejar anotado**: la primera
pasada de esta verificación mostraba solo 3 visuales en vez de 5. La causa
no fue el código de Fase D sino que `localhost:8000` resolvía por IPv6 a un
contenedor Docker de **otra sesión** de trabajo en esta misma máquina, no a
mi backend de prueba — dos sesiones concurrentes pueden compartir puerto
por accidente si una hace un bind amplio. Forzar `API_INTERNAL_URL` a
`http://127.0.0.1:8000` (IPv4 explícito) lo resolvió. No es un problema de
producción —ahí cada entorno tiene su propio host— pero si alguna vez un
ensayo local da un resultado que no cuadra con lo que el backend responde
por `curl` directo, esta es la primera sospecha.

### Fase E — Exportación (esta entrega)

Tres formas de sacar un reporte de la pantalla, cada una para un caso
distinto — ninguna suma una dependencia nueva:

- **Imprimir el tablero**: `window.print()` + la variante `print:` de
  Tailwind (`@media print` bajo el capó — comprobado en el CSS de
  producción). Se esconde toda la interfaz de edición (barra de acciones,
  filtros, "+Agregar reporte", "Compartir con el rol", asa de arrastre,
  botones CSV/XLSX de cada tarjeta) y también la navegación del shell
  (sidebar, barra superior, pie de página) — sin eso, imprimir un tablero
  imprimía la aplicación entera. El navegador ya ofrece "Guardar como PDF"
  en su propio diálogo de impresión; no hace falta generarlo en el
  servidor.
- **CSV por tarjeta**: sin cambios, ya existía.
- **XLSX del dataset completo**: `POST /reportes/{codigo}/exportar`
  (`src/core/reportes/router.py`) corre el **mismo** reporte, con el
  **mismo** permiso y el **mismo** rango que `/datos` —comparten
  `_reporte_y_filas`, la única diferencia es el tope— pero con
  `catalogo.LIMITE_MAXIMO_EXPORTACION` (50 000) en vez de
  `LIMITE_MAXIMO` (500). Arma el `.xlsx` con `src/shared/planilla.py`
  (ya usado por la carga masiva de recetas, ADR-052) y lo sirve con
  `Content-Disposition: attachment`. A diferencia del CSV, los montos
  salen como número real (`Decimal` → `float`), no como texto: una
  fórmula `=SUMA(...)` sobre la columna funciona sin que nadie la
  convierta antes — un aprovechamiento del formato que el CSV, por ser
  texto plano, no puede ofrecer.

Cierra la deuda abierta de `docs/roadmap/deuda/dashboard-y-caja.md`
("la exportación baja lo que se ve, no el dataset completo"). Verificado
con 5 tests que leen el `.xlsx` de verdad con `openpyxl` (no solo el
status code): encabezado, tipo de dato de cada celda, y que el tope real
sea 50 000 y no 500.

## Lo que NO se hace (en ninguna fase)

- No se construye un constructor de consultas dentro de Provecho. Es lo que
  ADR-024 rechazó; el constructor vive en Superset, detrás de un rol de
  base de datos que Provecho no le da acceso a nada más.
- No hay réplica de lectura todavía (lo que sugería ADR-024). El BI consulta
  la base viva, con `bi_lector` de solo lectura y `statement_timeout`
  propio. Deuda anotada: si una consulta pesada empieza a molestar al PDV,
  ahí se paga la réplica — no antes.
- No se amplía la cookie de sesión (`provecho_token`, httpOnly, host-only en
  `staging.majambo.com.pe`) a `.majambo.com.pe` para que "llegue" a
  `bi.majambo.com.pe`. Sería exponerla a todo subdominio para ahorrarse el
  flujo OAuth de la Fase B.
- No entra `react-grid-layout`, `cmdk` ni ninguna librería de PDF en el
  frontend de Provecho para esto — ver el detalle de cada fase cuando
  aterricen.
- No se agranda el droplet de staging para el BI, y no corre *Alerts &
  Reports* (PDF programado por correo) de Superset: piden Celery
  worker/beat y Chromium headless, que no entran cómodos en el droplet de
  1 GB elegido para este volumen de uso. Se retoma si el uso crece al punto
  de justificar más máquina — no antes.

## Consecuencias

- Un reporte que hoy tomaría una entrada nueva en `catalogo.py` puede, en
  cambio, resolverse en Superset sin tocar código de Provecho — a costa de
  que ese reporte ya no tenga el enlace accionable de ADR-036 ni el permiso
  granular por fila que sí tiene el catálogo (Superset filtra por
  sucursal/empresa, no por el permiso fino de cada módulo dueño).
- `production`, `rrhh` (más allá de nombres) y `marketing` quedan
  analizables sin sumar reportes al catálogo cerrado.
- El equipo gana una segunda superficie de administración (Superset) con su
  propio ciclo de vida, sus propios usuarios y su propia curva de
  aprendizaje — no es gratis operarla.
- Mientras las Fases B-E no aterricen, las vistas y el rol de Fase A no
  tienen consumidor: quedan listas y probadas, pero inertes. Es deliberado
  — permite verificar la capa semántica (la parte de mayor riesgo de fuga)
  de forma aislada antes de exponerla vía SSO.

## Alternativas descartadas

- **Agrandar el droplet de staging a 4 vCPU/8 GB en vez de un droplet
  aparte**: primera decisión tomada, revertida el 2026-08-29 al confirmar el
  volumen real de uso (decenas de consultas/mes). Habría costado más y
  habría puesto al PDV a competir por recursos con una consulta analítica
  ocasional — exactamente lo que separar en dos máquinas evita.
- **Metabase OSS**: ver "Por qué Superset y no Metabase" arriba.
- **Metabase Pro/Enterprise**: resuelve RLS y embebido de fábrica, pero es
  una suscripción mensual recurrente; se descarta mientras Superset (sin
  costo de licencia) cumpla el mismo contrato de seguridad.
- **Ampliar el catálogo cerrado en vez de un BI**: no resuelve "elegir
  libremente eje X/Y/valor" sin convertirse, de facto, en el constructor de
  consultas que ADR-024 rechazó.
- **RLS de Postgres nativa en vez de vistas + rol dedicado**: más "correcto"
  en abstracto, pero exigiría replantear cómo se conectan *todos* los roles
  de la aplicación (no solo Superset) y no está en el alcance de esta
  decisión — queda anotado como posible evolución futura.

## Referencias

- `alembic/versions/832ff01ed33f_vistas_bi_y_rol_de_solo_lectura.py`
- `tests/test_bi_alcance.py`
- `docs/architecture/adr/ADR-024-catalogo-cerrado-de-reportes.md`
- `docs/architecture/adr/ADR-004-estrategia-tenant.md`
- `docs/roadmap/deuda/dashboard-y-caja.md`
