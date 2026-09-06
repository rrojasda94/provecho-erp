# Historial — Módulo `rrhh`

Estado vigente: 🔶 En curso — ciclo laboral, contratación/convocatoria, ARCO de
postulante, asistencia PAD, terminal de marcaje y legajo+permisos están
construidos y probados; boletas/liquidaciones se registran por API (la nómina
se calcula fuera del ERP) y queda deuda declarada en
`docs/roadmap/deuda/modulo-rrhh.md`.

## Cronología

### 2026-07-14 — Modelo de datos ampliado
> Modelo de datos ampliado (bloques Inventario, Documentos, Movimientos, Operación comercial, Recursos, Información, RRHH, Actores) | ✅ 2026-07-14 | `docs/architecture/data-model.md` — ~50 entidades nuevas/enriquecidas; ver detalle abajo

Detalle de entidades listado más adelante en el propio ROADMAP.md (sección
"Orden sugerido de desarrollo", líneas 716-721):

> - **RRHH** (`docs/architecture/data-model.md#8b`): `trabajador`,
>   `contrato_laboral`, `boleta_pago`, `memorandum`, `amonestacion`, `acta`,
>   `certificado_trabajo`, `liquidacion_bss`, `solicitud_permiso`,
>   `pacto_permanencia`, `asistencia`, `postulante`, `socio`.

### 2026-07-19 — Área RRHH: procesos y plantillas (reclutamiento, contratación, inducción)
> RRHH: procesos y plantillas (reclutamiento, contratación, inducción) | ✅ 2026-07-19 | `docs/rrhh/`, 13 SOPs, 9 plantillas — ver detalle abajo.

Detalle completo (sección "Orden sugerido de desarrollo"):

> Documentación completa del área de Recursos Humanos: reclutamiento de
> personal operativo, selección, elección de modalidad de contrato,
> firma/alta, inducción y entrega de uniforme. Empresa acreditada como
> **microempresa en REMYPE** (D.S. 013-2013-PRODUCE); saldrá del régimen
> aprox. julio 2027 — documentación deja el punto de cambio marcado.
>
> Incorporado:
> - `docs/rrhh/` (nuevo): `README.md` (mapa del área, flujo de 13 pasos de
>   incorporación), `marco-legal-laboral.md` (régimen microempresa vs.
>   general, las 6 modalidades de contrato del grupo, obligaciones legales al
>   contratar, plan de salida de REMYPE), `perfiles/` (cocina, atención al
>   cliente/mozo-cajero — no existe puesto de cajero separado —, limpieza y
>   apoyo, + plantilla para nuevos perfiles).
> - `docs/diagrams/Procesos/Recursos-Humanos/` (área nueva en la taxonomía de
>   SOPs): 13 SOPs en `Reclutamiento/` (requisición y perfil, convocatoria,
>   filtrado, entrevista, verificación de referencias, selección y oferta),
>   `Contratacion/` (elección de modalidad, firma y alta en T-Registro,
>   inducción al puesto, entrega de uniforme, evaluación de periodo de
>   prueba).
> - `docs/templates/rrhh/` — 9 plantillas nuevas: 3 contratos (indeterminado,
>   sujeto a modalidad, tiempo parcial — con cláusulas de régimen
>   microempresa), convocatoria, ficha de entrevista, carta de oferta, ficha
>   de datos del trabajador, checklist de alta, acta de entrega de uniforme.
> - `business-rules.md` — RN-RRHH-005 corregida (15 días de vacaciones bajo
>   REMYPE, no 30); RN-RRHH-012 a RN-RRHH-014 (sin alta en T-Registro no hay
>   primer turno, sin perfil ni requisitos discriminatorios no hay
>   convocatoria, uniforme como condición de trabajo con acta y registro en
>   ERP).
> - `00_PROJECT.md` — entrada `rrhh/` en el mapa de documentación; tabla de
>   `templates/` y `diagrams/` actualizadas.
>
> Pendiente (declarado, no bloquea): módulo `rrhh` del ERP en sí (spec en
> `data-model.md` §8b) — esta sesión documentó proceso y plantillas, no
> implementó backend. Definir con contador/abogado el tratamiento de
> contratos vigentes al momento de salir de REMYPE.

### 2026-07-20 — Slice Venta: nace la entidad `trabajador`
> 11 tablas nuevas (22 en total con el bloque transversal):
> - `usuario` (alcance mínimo — sin rol/permiso/RBAC todavía, eso es el
>   slice de auth dedicado).
> - `trabajador` (RRHH — nuevo módulo `src/modules/rrhh/`, solo esta
>   entidad; el resto de §8b sigue pendiente del slice de RRHH).

Primer código real del módulo `rrhh`: solo la entidad `trabajador`, para
habilitar el ranking de ventas por trabajador del slice de Venta —núcleo—.
El resto de §8b (contrato, boleta, permisos, asistencia, postulante...)
quedó explícitamente pendiente del slice propio de RRHH.

### 2026-07-25 — Módulo `rrhh`: ciclo laboral completo
> Ciclo laboral completo: `trabajador` (con capa de aplicación que faltaba) + 12 entidades de §8b — `contrato_laboral` (borrador→firmado→finalizado), `postulante` (RN-PER-004), `socio`, `boleta_pago`/`liquidacion_bss` (idempotentes, RN-RRHH-001/003), `memorandum`/`amonestacion`/`acta`/`certificado_trabajo` (RN-RRHH-002/004/007), `solicitud_permiso` (RN-RRHH-005), `pacto_permanencia` (reembolso proporcional, RN-RRHH-006), `asistencia` (RN-RRHH-009, bloqueada para locación de servicios RN-PER-002). Migración `9e1b6a4c7d23`.

### 2026-07-26 — ARCO técnico (Ley 29733): excepción declarada de `postulante`
> Protección de datos personales (Ley 29733) | 🔶 ARCO técnico ✅ 2026-07-26 | `docs/security/proteccion-datos-personales.md`: qué datos trata el ERP y dónde viven (casi todo en `persona`, fuente única — RN-GEN-007; la excepción deliberada es `postulante`, ver 2026-08-01), derechos ARCO, plazos de conservación, medidas de seguridad ya vigentes (referenciadas, no reconstruidas), proceso de brecha. Cancelación implementada como **anonimización irreversible** de `persona`, no `DELETE` — `POST /api/v1/personas/{id}/anonimizar`, permiso dedicado `personas.anonimizar`, migración `dad43729501d` (RN-PER-007, ADR-011). Acceso/Rectificación ya existían (`GET`/`PATCH /personas/{id}`). Pendiente de **acción del usuario, no de código**: registro del banco de datos ante la ANPD, aviso de privacidad público, confirmar plazos de retención con el contador/abogado, jurisdicción de transferencia internacional. Pendiente técnico: ver Deuda técnica.

### 2026-08-01 — Slice contratación (convocatoria, postulación pública, tablero de incorporación)
> **Slice contratación** (2026-08-01, migración `a7f2c81e4b95`): `convocatoria` como expediente de la búsqueda (borrador→publicada→cerrada) con RN-RRHH-013 aplicada en código —sin perfil de puesto no se publica—; formulario público de postulación por token (`POST /rrhh/postulaciones/{token}`, sin JWT, rate limit 20/h por IP, consentimiento obligatorio RN-PER-004, fecha puesta por el servidor) que se llena con **Google Forms + un Apps Script de 12 líneas**, no con un formulario propio ni la API de Google (lo primero, superado el 2026-08-30 por ADR-087: hoy la página propia es el camino normal y Google Forms el alterno); `postulante` con datos propios y `respuestas` JSONB — **el candidato no entra a `persona` mientras es candidato**, `persona`+`trabajador` nacen al contratar (o se reusa la persona del recontratado, RN-GEN-007); y **un solo tablero** para los 13 pasos de incorporación (`recibido`→`preseleccionado`→`entrevistado`→`verificado`→`oferta_enviada`→`contratado`→`inducido`→`confirmado`, más `descartado`), avance de a una columna y descarte con motivo obligatorio porque el historial es la defensa ante un reclamo (Ley 26772). `postulante` gana `empresa_id` y cierra la excepción de tenant del mismo día. Permiso nuevo `rrhh.convocatoria_gestionar`. Tests: `tests/test_rrhh_convocatoria.py`.

### 2026-08-05 — Entidades Comercial-estrategia y RRHH-proceso llevadas a `data-model.md`
> Entidades de **Comercial-estrategia** y **RRHH-proceso**
> llevadas a `data-model.md`. `convocatoria` y `postulante` ya estaban
> desde el slice de contratación (2026-08-01) — la entrada las seguía
> listando como pendientes. Especificadas ahora, sin implementar:
> `meta_venta` + `meta_venta_seguimiento` y `hallazgo_mercado` en §6;
> `entrevista`, `plan_induccion` + `plan_induccion_item`,
> `evaluacion_periodo_prueba`, `evaluacion_desempeno` y `capacitacion` +
> `capacitacion_asistente` en §8b.
> Tres decisiones que valen más que las tablas: (a) **la escala 1-4 es la
> misma en toda la organización** —entrevista, periodo de prueba, desempeño
> comercial— para poder comparar a una persona consigo misma a lo largo del
> tiempo, y los criterios van en JSONB porque cada puesto pregunta lo suyo;
> (b) **evaluación de desempeño y capacitación viven en `rrhh` aunque las
> ejecute Comercial**: su artefacto termina en el file personal y `sales`
> no puede ser dueño de datos de `trabajador` — Comercial produce, RRHH
> custodia, y `evaluador_id` deja visible que el evaluador fue de otra
> área; (c) **el seguimiento de la meta es tabla, no columna**: guardar
> solo el cumplimiento final convierte la meta en un número que se mira
> cuando ya no hay nada que hacer, que es justo lo que el SOP quiere
> evitar. Falta el slice que las implemente.

También el 2026-08-05, BPMN de las áreas nuevas:

> BPMN de las cuatro áreas nuevas, con sus PROC registrados
> en el maestro y su narrativa en `workflows.md` (el enfoque era *primero
> SOP, luego BPMN*, y los SOPs ya estaban estables):
> **PROC-RRH-001** Incorporación de personal · [...]

Y BPMN de las dos contingencias declaradas, sin soporte en código todavía:

> BPMN de las dos contingencias:
> **PROC-RRH-002** personal faltante en la apertura (RN-RRHH-011 — el local
> **abre igual**, el pago extra del reemplazo se le descuenta al faltante
> salvo constancia médica) y **PROC-RRH-003** tardanza o falta del encargado
> (RN-RRHH-010 — hasta 30 min es memorándum y *no es sanción*, más de 30 min
> o falta es amonestación). Ninguna de las dos tiene soporte en código
> todavía: son proceso, no pantalla.

### 2026-08-22 — Contratación toma el documento verificado, no el autodeclarado
Dentro del gran parche acumulado de `users` (línea larga del ROADMAP,
apartado "**Y RRHH, donde más pesa**"):

> `contratar_postulante` creaba la `persona` con lo que el candidato escribió
> de sí mismo en el formulario **público** —sin sesión ni permiso—, y con ese
> nombre se firma el contrato y se declara a SUNAT; `sales` y `purchases` ya
> pasaban el documento por `nombres_desde_dni` y RRHH no. Ahora el servidor
> lo aplica aunque nadie apriete el botón, y el diálogo de contratar suma
> nombres/apellidos editables para poder verlo antes (precedencia RENIEC >
> lo revisado > lo declarado; con carné o pasaporte no se consulta).

### 2026-08-23 — Staging: cron de purga de postulantes pendiente
Parte de "Falta para terminar el primer despliegue de staging":

> Cron de backup diario (`python -m src.backups.backup`) y purga semanal
> de postulantes (`python -m src.modules.rrhh.purga`) dados de alta en
> el droplet.

(Marcado ⬜ — no ejecutado todavía, pendiente de acceso del usuario al
droplet.)

### 2026-08-24 — Turno de trabajo, PAD de asistencia y centro de labores
> **Turno de trabajo y pad de asistencia** (2026-08-24, ADR-064/065, migración `c4d17b93e0af`): `turno_sucursal` es la primera entidad de **horario laboral** del ERP —el glosario lo nombraba desde el principio y nada lo modelaba, así que `asistencia.tardanza_min` la mandaba el cliente—; lleva entrada, salida, tolerancia y **hora límite de marcaje de salida**, y una hora de salida menor que la de entrada significa que el turno cruza la medianoche. No fue a `parametro_empresa`: ese índice es por empresa y meter la sucursal en el `codigo` pierde la FK (mismo precedente que `categoria.frecuencia_conteo`, ADR-014). El pad (`frontend/app/asistencia/`, pantalla completa fuera del shell como PDV y KDS) se abre con una **cuenta de servicio por local** —rol `terminal_asistencia`, permiso único `rrhh.asistencia_terminal`— y cada marcación la firma el **PIN del propio trabajador** (RN-RRHH-020), verificado contra el mismo lockout del login por el contrato público nuevo `users.queries_publicas.verificar_pin_de` — el acoplamiento que la auditoría de arquitectura pedía resolver desde el 2026-08-01. Se descartó que cada trabajador iniciara sesión para marcar: en el cambio de turno son diez personas en fila, y la primera vez que se hace lento alguien deja la sesión abierta y marca por los demás. El servidor decide hora, día laboral (corta a las 05:00, así el turno noche no se parte), entrada o salida y tardanza; la tarjeta muestra **solo el nombre** porque la pantalla está a la vista de toda la cocina; quien no marca asistencia (locación de servicios, RN-PER-002) no aparece. Barrido horario de salidas sin marcar → aviso al trabajador en **su** campana y emisión `rrhh.salida_sin_marcar` al encargado del local y a RRHH: dos caminos porque abrir un reporte exige el permiso del módulo dueño (RN-REP-002) y un cocinero no tiene `rrhh.leer`. Sin actor, como `sales.pedido_demorado` — el hecho es «falta una marcación», no «alguien hizo algo mal». **Nunca genera horas extra** (RN-RRHH-022): la hora extra se autoriza antes, no se deduce de un reloj. Tests: `tests/test_rrhh_asistencia_pad.py`.

También el 2026-08-24, se separó "centro de labores" de "alcance de datos":

> **Dónde trabaja alguien y qué datos alcanza son dos cosas**
> (ADR-062, migración `b6d29f10c47e`, RN-RRHH-019). No se podía asignar un
> trabajador a una sucursal ni un supervisor a varias: `trabajador` no tenía
> local (la asistencia no tenía a qué sucursal atribuirse) y `usuario_sucursal`
> tenía endpoints desde el slice inicial **pero ninguna pantalla** — fuera del
> seeder nadie repartía alcance. Ahora `trabajador.sucursal_id` (nullable) es
> el **centro de labores**, un hecho laboral de RRHH, y `usuario_sucursal`
> sigue siendo el **alcance de datos** de la cuenta; se editan por separado en
> RRHH → Trabajadores y Usuarios → Cuentas. Un supervisor sobre varios locales
> son **varias filas**: se descartó una tabla `zona` porque hoy ningún reporte,
> permiso ni regla la nombra —sería una entidad con tenant, seeder y CRUD para
> ahorrar dos clics—. De paso se cerraron dos agujeros del endpoint que ya
> existía: no validaba tenant (se podía dar acceso al local de otra empresa del
> grupo) y no auditaba. Nuevo `GET /users/{id}/sucursales`. Tests en
> `tests/test_rrhh.py` y `tests/test_organizacion_crud.py`.

### 2026-08-27 — La cuenta se liga al trabajador por la persona
> **La cuenta se liga al trabajador por la persona** (2026-08-27, ADR-070, migración `d3f8a2c1e947`): el vínculo cuenta↔trabajador vivía duplicado en dos columnas que nadie sincronizaba — `usuario.persona_id` (Usuarios → "Persona vinculada") y `trabajador.usuario_id` (RRHH → Trabajadores → "Cuenta", la única que leía el pad) — así que vincular desde Usuarios no habilitaba el pad, y el campo tampoco se pintaba al reabrir el editor porque `PersonaPicker` no aceptaba valor inicial. `trabajador.usuario_id` dejó de ser columna: se deriva con una subconsulta (`column_property`, no `relationship` — un joined eager load duplicaría la fila padre con dos usuarios sobre una persona) de `usuario.persona_id`, que pasa a ser la **única** arista, con índice único parcial (`uq_usuario_persona_viva`) y `PATCH /users/{id}` en `exclude_unset` para poder desvincular. Una persona puede tener más de un `trabajador` (recontratación) y comparten cuenta; `nombres_por_usuario` desempata por el no cesado. De paso, `contratar_postulante` gana `sucursal_id` — sin él la ficha nacía sin centro de labores y no aparecía en ningún pad. Tests: `tests/test_migracion_cuenta_por_persona.py`, casos nuevos en `tests/test_rrhh_asistencia_pad.py`, `tests/test_users_persona.py`, `tests/test_rrhh_convocatoria.py`.

### 2026-08-28 — Terminal de marcaje enrolado y evidencia de marcaje
> **Terminal enrolado y evidencia de marcaje** (2026-08-28, ADR-079, RN-RRHH-023/024, migración `a1c9e5f2b364`): ADR-065 resolvió quién marca, no dónde — la sesión de la cuenta de servicio del pad es exportable a cualquier navegador, así que un supervisor podía marcar entrada sin haber llegado, y el PIN se presta sin que nadie lo note. `terminal_marcaje` es el dispositivo autorizado a marcar por una sucursal: nace inactivo con un código de 6 dígitos vigente 30 minutos (`POST /rrhh/terminales`, permiso nuevo `rrhh.terminal_gestionar` — alta de infraestructura, igual criterio que `kds.configurar`), la tablet lo teclea una vez en `frontend/app/asistencia/activar-cliente.tsx` y recibe un secreto propio (SHA-256, igual criterio que `TokenAgente`) que manda en `X-Terminal` en cada marcación; sin terminal activo de esa sucursal, 403 aunque el PIN sea correcto. Cada toque del pad escribe además una fila `marcacion` (terminal, IP, ubicación, foto) colgada de la `asistencia` del día — ninguno de esos campos bloquea: sin permiso de cámara o de GPS se marca igual con esos campos en NULL. La distancia a la sucursal se calcula con `shared.ubicacion.metros_entre` (haversine) contra `sucursal.radio_marcaje_m` (nullable, por sucursal); la "anomalía" no se guarda, se deriva al leer, así que corregir el radio reclasifica el histórico solo. Se descartó lista de IPs por sucursal (la IP del ISP rota y dejaría al local sin marcar) y reconocimiento facial (biometría es categoría sensible, Ley 29733, desproporcionado frente a una foto que un humano revisa). De paso se corrigió que `app/api/proxy/[...ruta]/route.ts` **no reenviaba** `X-Forwarded-For` a la API: `ip_de()` siempre veía la IP del contenedor `web`, nunca la del local — requiere que `FORWARDED_ALLOW_IPS` en producción confíe también en ese salto. Foto con retención (`rrhh_marcaje_foto_retencion_dias`, 90 por defecto, tarea diaria `rrhh.purgar_fotos_de_marcacion`): se purga el binario, la fila y el resto de la evidencia quedan. Migración validada contra Postgres (`alembic check` sin drift). Tests: casos nuevos en `tests/test_rrhh_asistencia_pad.py`.

### 2026-08-30 — La postulación se llena en el ERP (deja de depender de Google Forms como camino principal)
> **La postulación se llena en el ERP** (2026-08-30, ADR-087, hallazgo #5 de la auditoría backend↔frontend, sin migración): el «enlace del formulario público» que la pantalla de contratación entregaba al publicar era `/api/v1/rrhh/postulaciones/<token>` —una ruta **POST-only**—, así que abrirlo en el navegador o pegarlo en el aviso daba 405, y el único camino real era duplicar un Google Form y pegarle el token a mano en un Apps Script por cada convocatoria. La decisión de 2026-08-01 («no con un formulario propio») se tomó cuando el ERP no tenía ninguna superficie pública; desde ADR-061 existe `frontend/app/(publico)` con su layout, su CSP con nonce y el patrón de Server Action sin sesión, así que la segunda página pública dejó de ser infraestructura y pasó a ser una carpeta. Ahora `/postular/{token}` muestra puesto, vacantes, jornada y plazo, y la postulación cae en la columna `recibido`. **Google Forms sigue entrando por el mismo endpoint y con el mismo token**: los scripts vivos no se tocan, y sigue siendo el camino cuando la búsqueda necesita preguntas propias. Suma `GET /rrhh/postulaciones/{token}` (público, rate limit 60/h por IP) con cuatro campos y ninguno más —sin `id`, sin `empresa_id` y **sin el rango salarial**, que es dato de negociación y no del aviso— y recorta el acuse del `POST` a `{recibida, puesto}`: le devolvía a un anónimo el id de la ficha, la empresa, el estado interno del proceso y el plazo de conservación, inofensivo frente a un Apps Script que ignora la respuesta y no frente a un navegador. La regla de «cuándo una convocatoria sigue abierta» se extrajo a `convocatorias.publicada_por_token` porque ahora la usan los dos lados. Se descartó adjuntar CV (anonimizar todavía no borra el `archivo`: aceptar archivos antes de poder borrarlos crea un problema de Ley 29733) y las preguntas configurables por convocatoria. Tests: casos nuevos en `tests/test_rrhh_convocatoria.py`. Diferido: ver Deuda técnica.

### 2026-09-04 — Auditoría del 2026-08-30, Ola 2: botones RBAC y diálogos de RRHH
> `fix/rbac-botones-resto` | #3 los botones de trabajadores, artículos y devoluciones (la OC ya estaba gateada desde ADR-085) | ✅ 2026-09-04

> `fix/dialogos-migracion-sweep` | #4 los diálogos restantes migran a `DialogoFormulario`: 9 archivos, 15 diálogos, más el clon privado del tablero de contratación | ✅ 2026-09-04

Y, en la misma auditoría (Ola 1, cerrado en Ola 2):

> el resto de los botones-403 (pagos, asientos, trabajadores, artículos, devoluciones) se cerró en la Ola 2; la OC ya estaba gateada desde ADR-085

### 2026-09-05 — Legajo del trabajador, bandeja de permisos, sanciones y certificados
> `feat/rrhh-nomina-permisos-disciplina` | Legajo del trabajador (contratos, permisos, disciplina, certificados, pactos, boletas y liquidaciones en una lectura), bandeja de permisos y emisión de sanciones y certificados | ✅ 2026-09-05 — registrar boletas y liquidaciones queda como deuda: la nómina se calcula fuera del ERP

Detalle del fragmento de changelog aún no volcado a `CHANGELOG.md`
(`changelog.d/added-legajo-y-permisos-de-rrhh.md`), verbatim:

> **RRHH tenía ocho familias de endpoints y una sola pantalla** (2026-09-05,
> Ola 3 de la auditoría del 2026-08-30). Contratos, sanciones, memorandos,
> certificados, permisos, pactos, boletas y liquidaciones estaban entregados,
> probados y con permisos sembrados, y el módulo mostraba la lista de
> trabajadores y nada más.
> - **Legajo del trabajador** (`/rrhh/trabajadores/[id]`): todo el expediente
>   en una lectura. El endpoint ya devolvía las ocho listas juntas y nadie lo
>   llamaba. Se entra desde el nombre en la lista, que antes no llevaba a
>   ningún lado. La nómina se muestra solo con `rrhh.nomina_gestionar`, y
>   cuando no, **se dice** — sin eso, un legajo sin sueldos se lee igual que
>   uno censurado.
> - **Bandeja de permisos** (`/rrhh/permisos`): abre en las pendientes, porque
>   quien entra ahí entra por «qué tengo que resolver». La consulta de la
>   bandeja estaba escrita en el backend desde el slice del ciclo laboral.
>   Aprobar y rechazar muestran su error debajo: la acción devuelve el motivo
>   —solapamiento, trabajador cesado— y descartarlo dejaba la fila igual que
>   si no hubiera pasado nada.
> - **Amonestación, memorándum y certificado de trabajo** se emiten desde el
>   legajo. Quién firma sale de la sesión y no del formulario: dejarlo elegir
>   sería poder firmar por otro, que es exactamente lo que un descargo va a
>   discutir (RN-RRHH-002). El tiempo de servicios y el «dentro de plazo» del
>   certificado los calcula el servidor: son la razón de ser del documento.
> - Costo aceptado: **registrar boletas y liquidaciones sigue siendo por API**.
>   El ERP no liquida sueldos —registra lo que el contador liquidó— y el
>   cuerpo lleva los conceptos como diccionario libre: eso pide una pantalla
>   propia, no un diálogo. Queda anotado como deuda, igual que actas y socios.

**Estado vigente:** el ciclo laboral, la contratación (convocatoria +
postulación pública + tablero de incorporación), el ARCO de postulante, la
asistencia por PAD con terminal enrolado y evidencia de marcaje, y el legajo
del trabajador con su bandeja de permisos están implementados y probados. La
nómina (boletas y liquidaciones) se registra por API a propósito — el ERP no
calcula sueldos, eso lo hace el contador externo — y queda como deuda
declarada junto con actas y socios en `docs/roadmap/deuda/modulo-rrhh.md`
(11 puntos de deuda, 4 de ellos ya reflejados en tests/UI parcial, según el
índice del propio ROADMAP.md).

## Fuentes

Rangos de línea de `ROADMAP.md` consumidos (numeración al momento de esta
extracción, 2026-09-06):

- 14 (modelo de datos ampliado, mención RRHH)
- 29-30 (fila F0 del módulo `rrhh` — bloque narrativo largo con toda la
  cronología 2026-07-25 a 2026-08-30 — y fila de procesos/plantillas)
- 55 (ARCO técnico, excepción de `postulante`)
- 197-202 (Auditoría Ola 1 — botones de trabajadores gateados)
- 260-279 (Auditoría Ola 2 — `fix/rbac-botones-resto`, diálogo del tablero de contratación)
- 305-319 (Auditoría Ola 3 — `feat/rrhh-nomina-permisos-disciplina`)
- 375, 411-413, 422-427 (pendientes de decisión — rangos salariales de RRHH)
- 470-490 (pendientes de decisión — entidades Comercial-estrategia/RRHH-proceso)
- 491-507 (BPMN PROC-RRH-001/002/003)
- 517-531 (ADR-062 — centro de labores vs. alcance de datos)
- 532-553 (staging — cron de purga de postulantes, pendiente)
- 602 (índice de Deuda técnica → `docs/roadmap/deuda/modulo-rrhh.md`, no tocado ni copiado su contenido)
- 716-721 (entidades §8b de RRHH en el orden sugerido de desarrollo)
- 800-838 (Área RRHH — reclutamiento, contratación e inducción, 2026-07-19)
- 1008-1027 (Slice Venta — núcleo de datos, nace `trabajador`)

## Nota de cobertura

El fragmento `changelog.d/added-legajo-y-permisos-de-rrhh.md` (legajo del
trabajador, bandeja de permisos, emisión de sanciones/certificados) **sí**
está reflejado en `ROADMAP.md` — fila `feat/rrhh-nomina-permisos-disciplina`
(línea 319, Ola 3 de la auditoría del 2026-08-30, ✅ 2026-09-05) — aunque de
forma mucho más resumida que el changelog. No se detectó contenido del
changelog ausente del ROADMAP.md; la única diferencia es de nivel de detalle
(el changelog documenta decisiones puntuales — quién firma, cómo se oculta
la nómina sin permiso, el cálculo de plazos en servidor — que el ROADMAP no
narra). Se deja esta nota porque la instrucción original pedía verificarlo
explícitamente, no porque se haya encontrado una brecha real.
