# Historial — Módulo `reports` (incluye Gerencia/dashboards)

Estado vigente: 🔶 En curso — el motor de consulta (BI) y la emisión/distribución de reportes están construidos y en uso (catálogo cerrado, escalamiento, matriz de áreas editable), pero editar las reglas de distribución sigue siendo por API y el droplet de Superset sigue sin desplegar.

## Cronología

### 2026-07-14/15 — Pendiente señalado en el slice Venta (aún sin modelar)
Pendiente del slice Venta (señalado por el usuario, no modelado aún):
escalamiento de reclamos post-venta, monitoreo del pedido ya en curso,
manejo de errores técnicos/demoras del sistema. (Desistimiento durante la
toma del pedido SÍ quedó cubierto con RN-COM-010/011/012.) Módulo
`marketing` sigue sin README/contrato propio.

**Estado vigente (de este punto):** resuelto — ver `reporte_escalamiento` (2026-07-20 / implementado 2026-08-09) más abajo.

### 2026-07-20 — `reporte_escalamiento` definido (Pendientes de decisión)
✅ 2026-07-20 `reporte_escalamiento`: definido con el usuario — cadena
atención al cliente → supervisor (redacta solución) → comercial/gerencia
(acciones reportadas); se almacena para mejora continua
(`data-model.md` §6). **Implementado el 2026-08-09** (ADR-036) en
`src/modules/reports/`, no en `shared`: ancla al `reporte_emitido` y no a la
venta, y el escalón se resuelve con áreas + encargado de turno porque el ERP
no tiene jerarquía organizacional.

### 2026-07-22 — Área Gerencia: gobierno y matriz de aprobaciones (transversal, no reportes)
> Nota: esta sección documenta la autoridad/gobierno de Gerencia (no tiene módulo backend propio ni es parte de `reports`); se incluye completa por instrucción explícita, marcada como **transversal**.

Fila de F0: | Gerencia: gobierno + matriz de aprobaciones + presupuesto anual | ✅ 2026-07-22 | `docs/gerencia/`, política + perfil + 3 plantillas + 1 SOP (definición de presupuesto anual, PROC-GER-001) — ver detalle abajo. Área de autoridad/estrategia/control; sin módulo backend (RBAC + documentos) |

Documentación del área Gerencia a partir de la descripción del usuario:
parte estratégica y de autoridad, guía a nuevos mercados/marcas, último
visado cuando las áreas necesitan aprobar propuestas, y vela por que
empresa y trabajadores cumplan. Gerencia ya aparecía en ~57 archivos como
"aprobador final" pero sin dueño ni matriz propia — esta sesión lo
formaliza.

3 decisiones con el usuario antes de escribir:

1. **Actor**: Gerente General **delegado por los socios** — se respeta la
   línea del glosario (Gerencia/Directivo = trabajador con facultades
   delegadas; Socio = dueño). Decisiones reservadas a socios (PI, marca,
   alta/baja de empresa) quedan fuera del alcance del gerente.
2. **Control/disciplina**: Gerencia **decide/ordena, RRHH ejecuta** con
   el debido proceso ya documentado (RN-RRHH-004) — Gerencia no aplica la
   sanción por sí misma.
3. **Alcance ligero** (elección del usuario): **matriz de aprobaciones +
   política de gobierno**, sin SOPs estratégicos paso a paso. La
   estrategia se registra por decisión (acta), no por procedimiento fijo.

Consecuencia de diseño: **sin módulo backend** `gerencia` — la facultad
de aprobar es un permiso RBAC, no una tabla; Gerencia es autoridad +
documentos. Único artefacto de datos: `decision_gerencial` (transversal,
`shared`).

Incorporado:
- `docs/gerencia/` (nuevo): `README.md` (qué hace / qué no duplica),
  `politica-gerencia.md` (gobierno corporativo, **matriz de aprobaciones**
  como fuente única de umbrales, dirección estratégica, supervisión y
  control), `perfiles/gerente-general.md`.
- `docs/templates/gerencia/` — 2 plantillas: acta de decisión gerencial,
  ficha de evaluación de nuevo mercado/marca.
- `business-rules.md` — nueva sección "Gerencia — dirección y gobierno":
  RN-GER-001 a RN-GER-006 (facultades delegadas, decisión siempre
  documentada, matriz de aprobaciones como fuente única, abstención por
  conflicto de interés, decide→ejecuta el área competente, entrada a
  nuevo mercado con estudio previo).
- `data-model.md` §8c (nueva) — entidad transversal `decision_gerencial`;
  la matriz de aprobaciones queda como política/config, no tabla.
- `glossary.md` — **Gerente General**, **Matriz de aprobaciones**, **Acta
  de decisión gerencial** agregados.
- `00_PROJECT.md` — entrada `gerencia/` y `templates/gerencia/` en el mapa.

No genera PROC (no hay SOPs de proceso), ni evento, ni módulo — coherente
con el alcance ligero elegido.

Pendiente (declarado, no bloquea): umbral exacto de OC y de escalamiento
de lanzamientos a Gerencia (quedan `[[ COMPLETAR ]]` en la matriz, se
resuelven con los mismos pendientes de Compras/Comercial ya listados);
rango salarial del Gerente General (con los socios).

### 2026-07-22 — Ajustes de Marketing y Gerencia: presupuesto anual (transversal, no reportes)
> Nota: es un proceso de gobierno de Gerencia (presupuesto), no del módulo `reports`; se incluye por instrucción explícita, marcada como **transversal**.

3. **Presupuesto anual — nuevo proceso en Gerencia** — el usuario pidió un
mecanismo para definir presupuestos: reunión anual donde cada área
presenta propuesta y Gerencia designa presupuesto + límite de gasto
autónomo por área (bajo el límite, el área ejecuta sin aprobación
puntual; sobre él o fuera de presupuesto, aprueba Gerencia). Nuevo
**RN-GER-007**, **PROC-GER-001** (workflows + registro), SOP
`definicion-presupuesto-anual.md`, plantilla `propuesta-presupuesto-anual.md`,
y fila en la matriz de aprobaciones. Reemplaza el `[[ COMPLETAR ]]` de
"umbral de presupuesto de campaña" por el marco de presupuesto anual
(los montos/límites por área siguen `[[ COMPLETAR ]]`, se fijan en la
reunión).

### 2026-07-26 — Dashboard gerencial mínimo (F0, ADR-012)
| Dashboard gerencial mínimo | ✅ 2026-07-26 | `GET /api/v1/dashboard/resumen` (`src/core/dashboard_router.py`, permiso `dashboard.leer`): ventas del día (cantidad+total), stock bajo mínimo, cajas abiertas — agregador en `core`, nunca importa dominio de otro módulo (ADR-012). Requirió construir dos huecos que no existían: `sales` no tenía ningún listado de ventas, `accounting` tenía los modelos de caja (`apertura_caja`/`cierre_caja`/`arqueo`, migrados desde 2026-07-20) sin capa de aplicación. **Slice mínimo de caja** (`accounting.application.caja`): abrir/cerrar/arquear con **reconciliación real** (el cierre calcula `monto_esperado` desde los pagos en efectivo reales, vía contrato público de `sales`, no un número tipeado sin verificar). Primer frontend real: login por PIN + pantalla de dashboard en Next.js. Fuera de esta fase, a propósito: RN-POS-009..013 completas, relevo autenticado por PIN, máquina de estados de `custodia_efectivo` — ver Deuda técnica. |

### 2026-08-01 — Auditoría arquitectónica (F0, mención de contrato público)
| Auditoría arquitectónica | ✅ 2026-08-01 | ... Diferido: `Empresa`/`Sucursal`/`Almacen`/`Persona` de `users` a `shared/models` (37 archivos; conviene junto al CRUD de organización), contrato público de `inventory` para `Articulo`/`Receta`, y `core/dashboard_router` a un módulo propio. |

### 2026-08-04 — `core/reportes` (motor de consulta, ADR-024) y BI/reportes revisado (F0)
| Supervisión, CRM, tesorería, activos, proyectos, BI/reportes | 🔶 revisada 2026-08-05 | **Cuatro de los siete ya no son futuros y dos no van a ser módulos.** **BI/reportes** ✅ 2026-08-04: `src/core/reportes/` (ADR-024) con catálogo cerrado de 13 reportes, tableros guardados por usuario y compartidos por rol, filtros y exportación a CSV. **Desde 2026-08-08 hay una segunda mitad**, y son cosas distintas: `core/reportes` es la **consulta** (el usuario pide, se calcula) y el módulo `reports` (ADR-033) es la **emisión y distribución** (pasa un hecho, se genera, se guarda y se reparte). ADR-024 descartó un módulo porque el *motor de consulta* no tiene dominio propio; la distribución sí lo tiene —áreas, reglas, emisiones, entregas— así que paga sus siete registros de alta. **BI autoservicio 🔶 Fases A-E ✅ 2026-08-29** (ADR-081): la demanda de "elegir libremente eje X/Y/valor, más tipos de gráfico, comparar periodos" que ADR-024 anticipó se resuelve con Apache Superset, no abriendo el constructor de consultas que ese ADR rechazó. Infra corregida antes de construir Superset: droplet aparte y chico (~$8/mes, 1 vCPU/1 GB) en vez de agrandar el de staging — el volumen real es decenas de consultas al mes, sin apuro de latencia. **Fase A**: diez vistas `vw_bi_*` + `bi_alcance_usuario` (RN-BI-001/002), rol de Postgres `bi_lector` sin acceso a ninguna tabla base, índices de soporte, y `tests/test_bi_alcance.py` que congela la equivalencia con `Tenant.sucursal_ids` contra Postgres real. **Fase B**: Provecho como proveedor OAuth2 (`src/core/oauth/`, sin tabla nueva — código y token viven en Redis, TTL corto, fallan cerrado). El hallazgo que definió el diseño: la sesión de Provecho es una cookie host-only de `staging.majambo.com.pe` que nunca llega a `api-staging.majambo.com.pe`, así que el paso que ve el navegador (`GET /oauth/authorize`) es un Route Handler del **frontend**, no un endpoint de FastAPI — la API solo entra ya autenticada, para validar `client_id`/`redirect_uri` y emitir el código. De paso, el login ahora acepta un `?next=` whitelisteado a `/oauth/authorize`, para no dejar a alguien a mitad del SSO si todavía no había entrado a Provecho. Permiso `bi.acceder` (RN-BI-004/005/006) seedeado en `admin`/`supervisor`/`contador`, adelantado desde Fase D porque el endpoint no tiene sentido sin él. **Fase C** (código y ensayo local hechos — sin acceso a DigitalOcean del usuario, el droplet real queda pendiente, ver `docs/engineering/bi-superset.md`): `docker-compose.bi.yml` + `deploy/bi/` + `scripts/superset_provision_db.sql` + `scripts/superset_init.py`, ensayados de punta a punta contra un Superset y una Postgres reales en Docker local — no solo revisados a ojo. Encontró cuatro bugs reales que ninguna lectura de código habría atrapado: la imagen "lean" de Superset no trae `psycopg2`; el `pip install` del driver tiene que apuntar al venv de Superset (`/app/.venv`), no al del sistema; `current_username()` sin llaves no es SQL de Postgres —es un macro de **Jinja** que Superset interpola antes de mandar la consulta, necesario porque la conexión analítica corre siempre como `bi_lector` para cualquier usuario—; y sin la feature flag `ENABLE_TEMPLATE_PROCESSING` ese macro no se interpola igual, así que la RLS filtraba en silencio a **cero filas para todo el mundo** sin ningún error que avisara. Se detectó inspeccionando el SQL efectivo que Superset mandaba a Postgres, y también que el rol `Gamma` de fábrica no alcanza los datos sin `datasource_access` explícito por dataset (403 `DATASOURCE_SECURITY_ACCESS_ERROR`) — el script ya se lo otorga al rol marcador `ProvechoBI`. **Fase D**: permiso y navegación (`bi.acceder` exacto, no por prefijo — entrar ya es un privilegio), guest tokens para embeber (`GET /bi/dashboards/{id}/guest-token`, whitelist `BI_DASHBOARDS_EMBEBIBLES`, cuenta de servicio propia de Superset — distinta del SSO humano de Fase B), y tres mejoras al tablero de ADR-024 sin depender de Superset: filtro por marca (se une con el de sucursal, no lo reemplaza — cero cambios en los 14 reportes), `pie`/`area` como visuales (universales, vía el default de `VISUALES`), y título de tarjeta editable. Todo verificado en un navegador real (Docker: Postgres + backend + frontend, admin/cajero1 de verdad) — no solo lectura de código. Un hallazgo de entorno en el camino: la primera pasada mostraba solo 3 visuales porque `localhost:8000` resolvía por IPv6 al contenedor de **otra sesión** concurrente en la misma máquina, no al backend de prueba — forzar IPv4 lo resolvió, sin tocar código. **Fase E**: imprimir el tablero (`window.print()` + `print:` de Tailwind, escondiendo edición y navegación del shell — comprobado en el CSS de producción), y `POST /reportes/{codigo}/exportar` para el dataset completo (50 000 filas, no 500 — mismo permiso y mismo rango que `/datos`, comparten la resolución de reporte/alcance), con los montos como número real y no como texto, así que una fórmula de suma funciona sola. Cierra la deuda "la exportación baja lo que se ve, no el dataset completo". Verificado con 5 tests que leen el `.xlsx` real con `openpyxl`. Pendiente real: crear el droplet (VPC, firewall, DNS — runbook listo, requiere acceso del usuario a DigitalOcean) y curar los primeros tableros de Superset con `@superset-ui/embedded-sdk` para el widget de embebido (el mecanismo del backend ya está, la whitelist está vacía a propósito — no se inventó ningún dashboard de ejemplo) — detalle completo en el propio ADR. **Tesorería** ✅ 2026-07-25: vive **dentro de `accounting`** por decisión explícita del usuario —pago a proveedor, `movimiento_dinero`, caja y custodia— y separarla al salir de REMYPE es un pendiente de organización, no de código. **Supervisión** no es módulo: es el rol RBAC `supervisor` más la matriz de aprobaciones de Gerencia (`parametro_empresa` + `decision_gerencial`); un módulo "supervisión" sería un permiso disfrazado de dominio. **CRM** parcial: `sales.cliente` (con contrato público de lectura) y `marketing.lead`/`campana`/`encuesta_satisfaccion` con atribución lead→venta ya cubren captar y medir; falta historial de interacciones y segmentación, sin caso hasta que haya campañas reales corriendo. **Activos** ⬜ pero **ya tiene dueño**: se compran en `purchases` (OC tipo `activo` + `requerimiento_activo`, deuda declarada) y se deprecian en `accounting` (activo fijo/depreciación, PROC-CTB-007/010) — partirlos en un tercer módulo cortaría el ciclo de compra en dos. **Proyectos** ⬜ sin caso: el grupo no ejecuta obra ni proyectos facturables hoy. |

### 2026-08-08 — Módulo `reports` (emisión y distribución, ADR-033) reemplaza el cableado manual de notificaciones
| Notificaciones | ✅ 2026-08-08 | **Resueltas como distribución, no como transporte** (ADR-033). El problema real no era el canal: era que de 52 eventos publicados solo 4 llegaban a alguien, cableados en `users/application/listeners.py`, y no había forma de ver ni cambiar quién recibía qué sin un deploy. El módulo `reports` lo vuelve administrable: catálogo cerrado de 13 emisiones, áreas, reglas por (empresa, emisión, sucursal) y una matriz que marca **huecos** (el hecho ocurre y no se entera nadie) y **fugas** (regla que no llega a nadie). El transporte sigue siendo la bandeja in-app existente; correo y WhatsApp son un slice aparte (el campo `canal` ya está en el modelo). Migración `9a1c4e7b2d30`. |

### 2026-08-09 — `reporte_escalamiento` implementado (ADR-036)
(Ver también la entrada de 2026-07-20 arriba — mismo pendiente, cerrado acá.)
Implementado en `src/modules/reports/`, no en `shared`: ancla al `reporte_emitido` y no a la
venta, y el escalón se resuelve con áreas + encargado de turno porque el ERP
no tiene jerarquía organizacional.

### 2026-07-22 / ~2026-08 — Producción (spec a futuro): no conformidad reutiliza `reporte_escalamiento`
> Nota: sesión de Producción documentando spec a futuro (cocina de producción, planeada para 2027); se incluye porque extiende el dominio de `reports`.

2. **No conformidad de calidad**: se evalúa si el lote es corregible
(reproceso) o no (desecho); en ambos casos se genera un
`reporte_escalamiento` (reutiliza el patrón ya definido para
atención al cliente); el desecho exige evidencia de destrucción
(foto/video + testigo) para prevenir sustracción disfrazada de merma.

`data-model.md` §7 — nueva entidad `plan_produccion`; `orden_produccion`
ampliada con `plan_produccion_id` y `control_calidad_resultado`;
`reporte_escalamiento` ampliado con origen `produccion` y motivo
`no_conformidad_calidad` + `evidencia_id`.

### 2026-08-12 — UX transversal: dashboards configurables queda pendiente
| UX: menús, buscadores, breadcrumbs, atajos, sidebars, dashboards | 🔶 2026-08-12 | **Paleta de comandos** (`Ctrl+K`, `components/shell/paleta-comandos.tsx`) sobre Base UI Autocomplete — sin `cmdk`: motor de fuzzy search para ~50 entradas estáticas y arrastra Radix, que ADR-013 descartó. Los destinos salen de `lib/navegacion.ts`, se arman en servidor y llegan filtrados por permiso; cada resultado es un `<Link>` real (Enter, clic central y «abrir en pestaña nueva» funcionan solos). Sidebar con ítem activo y submenú registrado en un solo archivo. Atajo `/` para el buscador de la tabla. Pendiente: breadcrumb por ruta recorrida, atajos por acción dentro de una pantalla, dashboards configurables |

### 2026-08-27 — Catálogo de reportes suma `mesas_preferidas` (ADR-024)
> Extracto de la fila del módulo `sales` (2026-08-27, ADR-069) — el resto de esa fila es de mesas/PDV y no se reproduce acá.

Suma al catálogo de reportes (ADR-024) **`mesas_preferidas`**: qué mesa pide más el cliente por sucursal, reusando `_ventas_en_rango` para no contradecir a los demás reportes del mismo rango.

### 2026-08-27 — Semáforo de espera en KDS, pantalla `/gerencia/kds`
> Extracto de la fila del módulo `sales` (2026-08-26/27) — dashboard operativo hacia Gerencia, no parte del catálogo de reportes ADR-024/033 pero sí de "dashboards de Gerencia".

**Semáforo de espera** (`application/kds_semaforo.py`, pantalla `/gerencia/kds`): la cocina no tenía **ninguna** noción de tiempo —un pedido de hace cuarenta minutos se veía igual que uno recién tomado— y ahora cada tarjeta lleva su reloj y cambia de color a los minutos que Gerencia apruebe; el reloj lo corre el navegador a partir de `creado_en`.

### 2026-08-30 — Consumo de personal pasa a emitirse por el catálogo de reportes
> Extracto de la fila del módulo `sales` (slice 6, 2026-08-30).

En la misma entrega, ... `sales.consumo_personal_registrado` pasa a ser **emisión del catálogo de reportes** hacia Gerencia y Contabilidad.

### 2026-08-29 — Parche compras/inventario: KPI de incidencias en el dashboard
| # | Qué | Estado |
|---|---|---|
| 5 | KPI de incidencias de inventario en el dashboard (el descuento de stock ya funcionaba y estaba testeado) | ✅ 2026-08-29 |

### 2026-08-30 — Parche 0.9.1: el dashboard ofrece el pase al BI
| # | Qué | Estado |
|---|---|---|
| 2 | El dashboard ofrece el pase al BI (existía el módulo, faltaba el enlace) | ✅ 2026-08-30 |

### 2026-09-05 — Ola 3 de la auditoría 2026-08-30: matriz de edición de áreas de reportes
| Bloque | Qué | Estado |
|---|---|---|
| `feat/reports-matriz-edicion` | Áreas y miembros de distribución editables: el mapa mostraba los huecos y no había cómo taparlos | ✅ 2026-09-05 — editar reglas de distribución queda como deuda |

Texto de contexto de esa Ola (aplica a los cinco bloques, incluido este):
Y la **Ola 3** de la auditoría del 2026-08-30
([`docs/roadmap/auditoria-erp-2026-08-30.md`](docs/roadmap/auditoria-erp-2026-08-30.md)):
cinco bloques, todos del mismo patrón que esta bitácora viene anotando desde
la 0.8.0 — endpoints entregados, probados y sin pantalla que los llame.

**Estado vigente (de este punto):** ✅ implementado 2026-09-05, con "editar reglas de distribución" declarado deuda explícitamente en la propia fila.

**Verbatim del changelog fragment `changelog.d/added-areas-de-reportes-editables.md`** (mismo hecho, más detalle):
- **El mapa de distribución mostraba los huecos y no había cómo taparlos**
  (2026-09-05, Ola 3 de la auditoría del 2026-08-30). `/reportes/distribucion`
  marca en rojo los **huecos** —un hecho que ocurre y no se entera nadie— y
  las **fugas** —una regla sin destinatarios—, y el CRUD para arreglarlos
  existía en el backend desde ADR-033 sin que ninguna pantalla lo llamara.
  Ahora `/reportes/areas` crea áreas, las renombra, las desactiva y les suma
  o quita miembros. Un miembro es **un rol o una persona, nunca las dos**: el
  rol es «quien ocupe ese puesto» y sobrevive al cambio de gente, la persona
  es esa persona, y mezclarlos dejaría sin saber cuál manda cuando el puesto
  cambia de manos. El código del área no se edita —las reglas lo nombran— y un
  área sin miembros se dice en la pantalla: recibe y no se lo pasa a nadie,
  que es la mitad de una fuga.
  Costo aceptado: **editar las reglas** sigue siendo por API. Una regla lleva
  código de emisión, nivel, canal, sucursal y destinatarios de cuatro tipos
  distintos: es una pantalla propia, no un diálogo. Queda anotado como deuda.

### 2026-09-05 — Ola 4 de la auditoría (calidad): prueba que congela listas de pantalla contra el enum
> Nota: hallazgo transversal (afecta muchas pantallas, no específico de `reports`), pero incluido porque el dato objetivo del encargo lo señala como fuente a revisar; no se encontró mención específica al enum de `reports`/escalamiento dentro de este hallazgo — ver Nota de cobertura.

| Bloque | Qué | Estado |
|---|---|---|
| `fix/contrato-tests-y-tipos-duplicados` | #15 una prueba parametrizada compara nueve listas de pantalla contra el enum del modelo —encontró una que ofrecía un valor que la API rechaza— y las formas `{id, nombre}` dejan de estar declaradas diecinueve veces | ✅ 2026-09-05 |

Verbatim del changelog fragment `changelog.d/fixed-listas-de-pantalla-contra-el-enum.md`:
- **Una lista de la pantalla que se separa del enum no falla: ofrece un valor
  que la API rechaza recién al guardar** (2026-09-05, hallazgo #15 de la
  auditoría del 2026-08-30). El repo tenía dos pruebas de coherencia escritas
  a mano —los motivos de descuento del PDV y los estados de la jornada— y
  quince listas más con el mismo riesgo y ninguna prueba. Ahora es **una
  prueba parametrizada** que lee el `Enum` del modelo —no una copia— y lo
  compara con la lista de la pantalla: sumar una es agregar una fila, que era
  el punto de extenderla en vez de escribir la prueba número dieciséis.
  **Encontró una de entrada**: el diálogo de amonestación del legajo ofrecía
  «suspensión», que no es un valor de `amonestacion.tipo` — elegirla terminaba
  en un 422 al firmar la sanción.
- **`{ id, nombre }` estaba declarado diecinueve veces** (2026-09-05, mismo
  hallazgo): `Sucursal` once, `Categoria` cuatro, `Marca` tres, `Almacen` dos.
  Con la duplicación vino algo peor — pantallas importando el tipo de **otra
  pantalla**, que acopla dos vistas por un detalle que no es de ninguna de las
  dos. Viven ahora en `lib/catalogos.ts`.

## Fuentes

Rangos de línea de `ROADMAP.md` consumidos (estado al momento de escribir este historial):
- 5-66 (tabla F0): líneas 35, 40, 45, 53-54, 61
- 68-373 (bitácora de parches/auditorías): líneas 164-183 (contexto, solo fila 5 relevante), 222-238 (contexto, solo fila 2 relevante), 289-328 (Ola 3, incluye `feat/reports-matriz-edicion`)
- 375-573 (pendientes de decisión): líneas 442-448 (`reporte_escalamiento`)
- 606-1413 (orden sugerido de desarrollo): líneas 624-686 (slice Venta, pendiente de escalamiento), línea 24 completa (módulo `sales`, de la que se extrajeron los fragmentos de `mesas_preferidas`, semáforo `/gerencia/kds` y `consumo_personal_registrado`), líneas 1121-1159 (Producción — no conformidad → `reporte_escalamiento`), líneas 1211-1263 (Área Gerencia — gobierno y matriz de aprobaciones), líneas 1323-1349 (Ajustes de Marketing y Gerencia — presupuesto anual)
- 574-605 (índice de Deuda técnica): NO tocado, por instrucción explícita.

Changelog fragments leídos directamente (fuera de `ROADMAP.md`):
- `changelog.d/added-areas-de-reportes-editables.md`
- `changelog.d/fixed-listas-de-pantalla-contra-el-enum.md`

## Nota de cobertura

- El `ROADMAP.md` sí refleja la matriz de edición de áreas de reportes (`feat/reports-matriz-edicion`, línea 321, 2026-09-05) y coincide en contenido con `changelog.d/added-areas-de-reportes-editables.md`. No se encontró contradicción entre ambas fuentes.
- `changelog.d/fixed-listas-de-pantalla-contra-el-enum.md` (hallazgo #15/#16 de la auditoría) es un hallazgo transversal de calidad (contrato de tipos y enums en pantallas) que **no menciona específicamente** al módulo `reports` ni a `reporte_escalamiento`; se referencia en este historial por ser una de las fuentes objetivas señaladas en el encargo, pero no se debe inferir que tocó código de `reports` — solo se confirma que corrige RRHH (amonestación) y duplicación de tipos `{id, nombre}` en varias pantallas.
- No se encontró en `ROADMAP.md` un ADR o slice narrativo dedicado en exclusiva y de punta a punta al módulo `reports` fuera de las menciones dentro de la fila F0 "Supervisión, CRM, tesorería, activos, proyectos, BI/reportes" (línea 40) y "Notificaciones" (línea 45) — el detalle línea-por-línea de ADR-033/ADR-036/ADR-081 vive en sus propios documentos de ADR (no reproducidos acá porque no son parte de `ROADMAP.md`).
- No se verificaron directamente `test_reportes.py`, `test_reports.py` ni `test_reports_escalamiento.py` contra este historial (fuera del alcance de esta tarea, que es solo sobre `ROADMAP.md`); si su contenido difiere de lo aquí registrado, ese contraste queda pendiente para quien mantenga `src/modules/reports/README.md`.
