# Historial — Módulo `marketing`

Estado vigente: 🔶 En curso — core implementado (campañas con brief/aprobación,
piezas de contenido, leads con atribución a venta, encuestas de satisfacción
por WhatsApp, evaluación de agencias) más el parche de listados del
2026-09-05; queda deuda declarada (5 ítems, 2 alto impacto — ver
`docs/roadmap/deuda/modulo-marketing.md`, que este documento no toca).

## Cronología

### 2026-07-14/15 — Slice vertical Venta (PROC-COM-001): primeras menciones de `encuesta_satisfaccion`

Del bloque "Datos" del slice de Venta:

> **Datos**: `docs/architecture/data-model.md` §6 — entidad
> `encuesta_satisfaccion` (queda igual, es de un módulo futuro).

Y en los pendientes señalados por el usuario al cierre de ese slice:

> Pendiente del slice Venta (señalado por el usuario, no modelado aún):
> escalamiento de reclamos post-venta, monitoreo del pedido ya en curso,
> manejo de errores técnicos/demoras del sistema. (Desistimiento durante la
> toma del pedido SÍ quedó cubierto con RN-COM-010/011/012.) Módulo
> `marketing` sigue sin README/contrato propio.

### 2026-07-20 — Cumplimiento de pedido definido como UN proceso (desbloquea el disparador de encuesta)

> ✅ 2026-07-20 `reporte_escalamiento`: definido con el usuario — cadena
> atención al cliente → supervisor (redacta solución) → comercial/gerencia
> (acciones reportadas); se almacena para mejora continua
> (`data-model.md` §6). **Implementado el 2026-08-09** (ADR-036) en
> `src/modules/reports/`, no en `shared`: ancla al `reporte_emitido` y no a la
> venta, y el escalón se resuelve con áreas + encargado de turno porque el ERP
> no tiene jerarquía organizacional.
> - ✅ 2026-07-27 Cumplimiento de pedido: **UN** proceso — `PROC-OPE-002`
>   (área Operaciones), con Preparación y Despacho/Entrega como etapas
>   internas, no dos procesos. Razones: un solo resultado (entra Orden de
>   Pedido, sale pedido entregado) sin artefacto de traspaso; la máquina de
>   estados ya implementada (`venta_item.estado_preparacion`) es una sola y
>   las pantallas KDS `preparacion`/`despacho` son vistas de ella; "Producción"
>   ya nombra la cocina de producción central (`PROC-PRD-001`, 2027) y
>   reusarlo rompía la nomenclatura. Desbloquea `sales.venta_entregada` y
>   `marketing.encuesta_enviada`; se separa como v2.0 si el reparto llega a
>   tener ruteo/flota/liquidación propios.
> - ✅ 2026-07-22 Módulo `marketing`: README/contrato propio —
>   `src/modules/marketing/README.md` + área documentada en `docs/marketing/`.

### 2026-07-22 — F0: documentación del área Marketing (tabla de estado)

> | Marketing: procesos y plantillas (marca/naming, contenido, campañas,
> material en sucursal, agencias) | ✅ 2026-07-22 | `docs/marketing/`, 6 SOPs,
> 4 plantillas — ver detalle abajo. PROC-MKT-001 registrado. Resuelve el
> pendiente "módulo marketing README/contrato propio" |

### 2026-07-22 — Área Marketing: marca, contenido, campañas y material

Documentación completa del área Marketing a partir del alcance dado por el
usuario. Frontera clave confirmada: **Marketing atrae el lead, Comercial
cierra la venta e investiga la oportunidad**. Marketing = crecimiento,
notoriedad, marca, contenido; Comercial = conversión y exploración de
mercado. Puesto dedicado: **jefe/encargado de Marketing**.

Distinción respetada: `MKT` (Marketing, ejecución) ≠ `MRC` (Manejo de
marca, identidad del holding) — Marketing asegura el **buen uso** de la
marca, no modifica su identidad (reservado, RN-MAR-004). Consecuencia de
diseño: Marketing sí tiene módulo backend (a diferencia de Gerencia),
porque maneja entidades propias (campaña, contenido, lead, material).

Incorporado:
- `docs/marketing/` (nuevo): `README.md` (frontera con Comercial y qué NO
  hace), `politica-marketing.md` (uso de marca, pertinencia sobre
  viralidad, brief/aprobación de campañas, material vía Compras, agencias),
  `perfiles/jefe-marketing.md`.
- `docs/diagrams/Procesos/Marketing/` (área nueva) — 6 SOPs:
  `Marca-Contenido/` (uso de marca + naming, plan de contenido y redes),
  `Campanas/` (lanzamiento de producto, medios y eventos),
  `Proveedores-Agencias/` (material promocional e implementación en
  sucursal, evaluación de propuesta de agencia/interna).
- `docs/templates/marketing/` — 4 plantillas: brief de campaña, calendario
  de contenido, evaluación de propuesta de agencia, checklist de material
  en sucursal.
- `business-rules.md` — nueva sección "Marketing": RN-MKT-001 a RN-MKT-007
  (uso de marca sin modificarla, pertinencia sobre viralidad, brief +
  handoff de leads con Comercial, material vía Compras, verificación en
  sucursal, evaluación de agencia con matriz de aprobaciones, naming).
- `data-model.md` §8d (nueva) — entidades `campana`, `pieza_contenido`,
  `lead`, `implementacion_material_sucursal`; `encuesta_satisfaccion`
  reasignada a este módulo.
- `events.md` — `marketing.campana_lanzada`, `marketing.lead_generado`
  (consumido por `sales` para atribución lead→venta).
- `workflows.md` + `process-nomenclature.md` — **PROC-MKT-001** (Campaña
  de marketing) v1.0 Borrador con narrativa + Mermaid.
- `glossary.md` — **Lead**, **Campaña**, **Naming**, **Jefe de Marketing**.
- **`src/modules/marketing/README.md`** (nuevo, spec técnica) — resuelve
  el pendiente de "módulo marketing README/contrato propio".
- `00_PROJECT.md` — entradas `marketing/` y `templates/marketing/`.

Pendiente (declarado, no bloquea): periodicidad del calendario de
contenido.

### 2026-07-22 — Ajustes de Marketing y Gerencia — feedback del usuario

Tras revisar el primer borrador de Marketing, el usuario corrigió 3 cosas:

1. **Marketing gestiona las marcas sin burocracia extra** — RN-MKT-001
   reescrita: Marketing es dueño operativo de las marcas (uso,
   consistencia, contenido, naming); solo lo reservado a socios
   (modificación estructural de identidad, venta de PI — RN-MAR-004,
   RN-GRP-006) lo excede. Se eliminó la capa de "elevar a Manejo de marca"
   para el trabajo cotidiano.
2. **Agencias las evalúa Marketing, Gerencia valida** — RN-MKT-006
   reescrita: la agencia es un servicio; Marketing la evalúa por su
   conocimiento, Gerencia valida, se formaliza por contrato y paga
   Contabilidad — **no pasa por Compras**. El **material** (bien) sí sigue
   vía Compras (RN-MKT-004). Ajustados el SOP de evaluación de agencia, la
   plantilla, el SOP de medios/eventos, el módulo backend y `data-model`.
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

### 2026-07-27 — Cumplimiento de pedido (PROC-OPE-002): la encuesta recupera su disparador

Del cierre de esa decisión (área Operaciones, no Marketing, pero fija el
evento que dispara la encuesta de satisfacción):

> **Especificación.** `process-nomenclature.md` (registro maestro + nota que
> distingue `PRD` de la preparación en sucursal), `workflows.md` (sección
> propia con gateway por modalidad; el borrador "fuera de Venta" se
> reemplaza por un puntero), `use-cases.md` (CU-OPE-001/002/003 por
> modalidad, con excepciones: cliente ausente, pedido no recogido, producto
> rechazado), `business-rules.md` (**RN-CUP-001..012** nuevas; RN-COM-005
> apunta al proceso; **RN-COM-007 reactivada** — la encuesta recupera su
> disparador tras 13 días sin dueño), `state-machines.md` (la máquina pasa
> de borrador a oficial, y se declara qué NO es estado: entrega fallida,
> devolución y el pago al finalizar en mesa), `events.md` (filas de
> `sales.venta_entregada` y `marketing.encuesta_enviada`), `data-model.md`
> (entidad `entrega` especificada para el slice de delivery).

### 2026-08-08 — Módulo `marketing`: primer código (slices 1-2)

> | Módulo `marketing` | 🔶 slices 1-2 ✅ 2026-08-08 | Primer código del
> módulo: `campana` con brief obligatorio (RN-MKT-003 — sin objetivo,
> público, presupuesto y KPI no se aprueba, y sin aprobación no sale a
> canal; quien redacta el brief no lo aprueba: `marketing.campana_aprobar`
> vive en `supervisor`, no en el rol `marketing`), `pieza_contenido` que
> solo se publica si es pertinente a la marca y su uso de marca está
> validado (RN-MKT-001/002), `lead` medido por conversión real y no por
> volumen, `implementacion_material_sucursal` (verificación en sitio,
> RN-MKT-005) y `encuesta_satisfaccion` (RN-COM-007), que la migración saca
> de §6 y le da dueño. La **atribución lead→venta** es automática solo
> cuando no hay ambigüedad —un único lead abierto del cliente en campaña en
> curso—; con dos o más queda manual, porque adivinar qué campaña convirtió
> falsea justo la métrica que la campaña existe para medir. Marketing lee el
> estado de entrega por el contrato público `sales::venta_para_encuesta`,
> nunca importando `Venta`. Migración `e9c3b7412a68`, 17 endpoints, 13
> tests. **Slice 2** (2026-08-08, ADR-031/030, migración `c1f80b6a2d34`): la
> encuesta **sale de verdad** y deja de ser un formulario — el guion vive en
> `encuesta_plantilla`/`encuesta_pregunta` como un grafo de nodos donde cada
> respuesta elige la siguiente pregunta (un 2 de 5 pregunta qué falló, un 5
> pregunta si nos recomendaría), y `encuesta_satisfaccion` recuerda en qué
> nodo está el cliente porque en WhatsApp no hay formulario, hay mensajes de
> a uno. Adaptador nuevo `src/shared/integrations/whatsapp/` (Cloud API de
> Meta), webhook público con firma HMAC, enlace público con token, y
> expiración automática por barrido horario. El primer mensaje del cliente
> **no** se cuenta como respuesta: solo abre la ventana de 24 h que Meta
> exige. Suma calendario de contenido con adjuntos (`GET /piezas/calendario`,
> arte colgado de `archivo`), evaluación agencia-vs-interna con criterios
> ponderados congelados antes de ver las propuestas y permisos separados
> para evaluar y decidir (RN-MKT-006), y `campana_metrica` — que convierte
> en consumidores reales a los eventos que el módulo publicaba al vacío.
> Diferido: ver Deuda técnica. |

### 2026-08-24 — Cupón "Queremos RE-conocerte": vive en `sales`, pero crea el `lead` de Marketing

Fragmento embebido en la fila F0 del módulo `sales` (no hay sección propia
de Marketing para esto — se conserva verbatim por el evento y el `lead`
que involucran):

> **Cupón de promoción y landing pública** (2026-08-24, ADR-062, migración
> `a7c3e1f508b2`): la campaña «Queremos RE-conocerte» — un QR en la mesa
> lleva a `/reconocerte`, el cliente deja DNI, cumpleaños, dirección y
> teléfono **sin cuenta**, y se lleva un cupón de 10 % de un solo uso que la
> caja canjea con `POST /sales/ventas/{id}/cupon`. Vive en `sales` y no en
> `marketing` porque sus dos operaciones son escrituras acá —crear o
> encontrar el `cliente`, descontar la `venta`— y un módulo solo entra a
> otro por `api.deps` o `queries_publicas`, que son de lectura: ponerlo allá
> exigía ampliar las excepciones cruzadas de `test_arquitectura`, que es la
> deuda que esa lista existe para no seguir acumulando. **Marketing se
> entera por `sales.cliente_registrado_en_promocion` y crea su `lead`**.
> Reusa `clientes.crear_cliente` entero, con su consulta a RENIEC y su
> fallback (RN-PTS-004), y reconoce por documento **o por teléfono** para no
> duplicar a la media base que se dio de alta en caja sin DNI. El descuento
> reusa `venta.descuento_*` con motivo nuevo `cupon` —un canal paralelo
> obligaba a tocar `total_a_cobrar`, el prorrateo SUNAT del comprobante y
> las notas de crédito— y el motivo propio es lo que deja al reporte separar
> el margen regalado a criterio del prometido en campaña; **el motor de
> promociones condicionales sigue sin poder reusarlas**. El canje **no pide
> PIN de supervisor** (a diferencia de RN-COM-017): el cupón ya era del
> cliente y es la autorización. La superficie pública **escribe pero no
> borra** —la baja va por `hola@majambo.com.pe` y la anonimización de
> ADR-011—, su consulta devuelve solo `{registrado: bool}`, y el `grupo_id`
> sale de la promoción activa y nunca del request. Lo único que la protege
> es el rate limit por IP, con el techo más duro (5/h) en el endpoint que
> convierte un DNI en un nombre, que es el que permitiría enumerar
> documentos. El código del cupón **es el DNI** (lo pidió el negocio): el
> cliente no guarda nada, y el costo —quien sepa un DNI ajeno puede
> intentarlo— se acota atándolo al cliente de la venta. Terminar la campaña
> es `POST /sales/promociones-cupon/{id}/termino` con
> `sales.gestionar_promociones`, y **no toca los cupones ya entregados**.
> Frontend: `frontend/app/(publico)/` — el primer grupo de rutas sin guard
> de sesión, con la voz de marca de Charlie's, el logo de Majambo en el pie
> y los términos completos. Los logotipos de `frontend/public/marcas/` son
> **provisionales**: reemplazar el archivo con el mismo nombre y listo. Sin
> pantalla de back-office ni QR generado por el ERP (decisión del usuario).
> Tests: `tests/test_cupones.py`.

**Estado vigente de este punto:** el motor de promociones condicionales
(tanda 3 del parche del PDV, ✅ 2026-08-28, ADR-076) es un desarrollo
posterior y separado de `promocion_cupon`/RE-conocerte — soporta N×M, X
unidades, combo, monto mínimo y vigencia por día/hora, y explícitamente
**no puede escribir en `venta.descuento_*`** (ese campo es el acto humano
firmado). RE-conocerte sigue sin poder reusar ese motor.

### 2026-09-05 — La Ola 3 de la auditoría: Marketing dejaba tres cosas sin listar

Del bloque "La contabilidad que no registraba, y la Ola 3 (2026-09-05)":

> | `feat/marketing-leads-encuestas-agencia` | Leads, encuestas y evaluación
> de agencias — con los tres endpoints de listado que faltaban y
> `encuesta_satisfaccion.empresa_id`, sin el cual no había filtro de tenant
> posible | ✅ 2026-09-05 — cargar opciones y firmar la decisión de agencia
> siguen por API |

**Estado vigente:** el módulo `marketing` tiene su core operativo (campañas
con brief/aprobación, contenido, leads con atribución automática/manual a
venta, encuestas conversacionales por WhatsApp, evaluación ponderada de
agencias) desde 2026-08-08, y el parche de 2026-09-05 cerró los tres
endpoints de listado que faltaban (`/marketing/leads`, `/marketing/encuestas`,
`/marketing/agencias`) más el filtro de tenant en `encuesta_satisfaccion`.
Quedan por API (sin pantalla): atribuir un lead a una venta a mano, cargar
opciones de agencia y firmar la decisión de Gerencia con motivo cuando se
aparta de la recomendada. El cupón "RE-conocerte" (2026-08-24) es una
promoción que vive en `sales` por decisión arquitectónica explícita, pero
notifica a Marketing vía `sales.cliente_registrado_en_promocion` y ahí nace
un `lead`; el motor de promociones condicionales (2026-08-28) es un
desarrollo aparte que no la reemplaza. Deuda declarada pendiente: ver
`docs/roadmap/deuda/modulo-marketing.md` (5 ítems, 2 de alto impacto — no
tocado ni reproducido aquí).

## Fuentes

Rangos de línea consumidos de `ROADMAP.md` (estado al momento de esta
extracción):

- Líneas 19-26, 36-37 (F0: filas `sales`, `marketing` y bloque "Supervisión,
  CRM..." con mención de `marketing.lead`/`campana`/`encuesta_satisfaccion`)
- Líneas 68-90 (parche PDV, tanda 3 — motor de promociones automáticas,
  contexto del "Estado vigente" de RE-conocerte)
- Línea 289, 305-321 (Ola 3 de la auditoría 2026-08-30,
  `feat/marketing-leads-encuestas-agencia`)
- Líneas 442-460 (pendientes de decisión: `reporte_escalamiento`,
  Cumplimiento de pedido como un proceso, módulo `marketing` README/contrato)
- Líneas 598-605 (índice de Deuda técnica — solo referenciado, no reproducido)
- Líneas 606-654, 678-686 (Orden sugerido de desarrollo: slice Venta
  2026-07-14/15, `encuesta_satisfaccion` como "módulo futuro", pendiente de
  README de `marketing`)
- Líneas 1277-1321 (Área Marketing — marca, contenido, campañas y material)
- Líneas 1323-1349 (Ajustes de Marketing y Gerencia)
- Líneas 1351-1388 (Cumplimiento de pedido PROC-OPE-002 — RN-COM-007
  reactivada, evento `marketing.encuesta_enviada`)

## Nota de cobertura

No aplica: el trabajo de leads/encuestas/agencias descrito en
`changelog.d/added-leads-encuestas-y-agencias.md` y cubierto por
`test_marketing.py`, `test_marketing_agencia.py`, `test_marketing_contenido.py`
y `test_marketing_encuestas.py` **ya está reflejado en `ROADMAP.md`**, en la
fila `feat/marketing-leads-encuestas-agencia` de la Ola 3 (línea 320,
✅ 2026-09-05) — coincide en fecha, migración implícita y alcance (los tres
listados faltantes + `encuesta_satisfaccion.empresa_id`) con el fragmento de
changelog. No se detectó contenido de código real sin cobertura en el
ROADMAP para este módulo.
