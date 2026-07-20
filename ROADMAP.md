# Bitácora de construcción — Provecho ERP

Registro de lo construido y lo pendiente. Actualizar en cada cambio relevante.

## Estado — F0 (Fundaciones)

| Área | Estado | Notas |
|------|--------|-------|
| Scaffold del proyecto | ✅ 2026-07-04 | Estructura, Docker, CI, docs, reglas |
| Reestructura de docs por temas (foundation/domain/architecture/engineering/security/product) | ✅ 2026-07-04 | Índice en `docs/00_PROJECT.md` |
| Docs de conocimiento (glosario, filosofía, reglas, eventos, máquinas de estado, autorización) | ✅ 2026-07-04 | Base para desarrollo asistido por IA |
| Especificaciones de módulos base | ✅ 2026-07-04 | READMEs de users, inventory, sales, purchases, accounting |
| Modelo de datos (v1, documento) | ✅ 2026-07-04 | `docs/architecture/data-model.md` |
| Modelo de datos ampliado (bloques Inventario, Documentos, Movimientos, Operación comercial, Recursos, Información, RRHH, Actores) | ✅ 2026-07-14 | `docs/architecture/data-model.md` — ~50 entidades nuevas/enriquecidas; ver detalle abajo |
| Core (app factory, settings, db, event bus) | ✅ 2026-07-04 | Endpoint `/health` operativo |
| Modelado de base de datos completo (SQLAlchemy + Alembic) | ⬜ | Ya no es el siguiente paso único — ver "Orden sugerido de desarrollo" (slices verticales). El detalle relevado sigue siendo insumo válido, ver abajo. |
| Módulo `users` (auth JWT + PIN + RBAC) | ⬜ | Tras el modelado de BD — contrato ya especificado |
| Migraciones Alembic iniciales | ⬜ | Junto con el modelado de BD completo (no incremental por módulo) |
| Seeders (admin / PIN 123456, org base) | ⬜ | |
| Módulo `inventory` | ⬜ | Almacenes, stock, movimientos, transferencias |
| Módulo `purchases` | ⬜ | Proveedores, OC, recepción |
| Módulo `sales` (PDV) | ⬜ | Venta, recetas, descuento de insumos, branding por marca |
| Módulo `accounting` | ⬜ | |
| Producción (fabricación) | ⬜ | Módulo futuro `production` |
| Solicitudes / picking / transporte | ⬜ | Módulos futuros `requests`, `logistics` |
| RRHH: procesos y plantillas (reclutamiento, contratación, inducción) | ✅ 2026-07-19 | `docs/rrhh/`, 13 SOPs, 9 plantillas — ver detalle abajo. Módulo backend `rrhh` sigue pendiente |
| Compras: procesos y plantillas (proveedores, cotización, OC, recepción, pago, caja chica, activos) | ✅ 2026-07-19 | `docs/compras/`, 9 SOPs, 6 plantillas — ver detalle abajo. Módulo backend `purchases` actualizado conforme al flujo |
| Comercial: procesos y plantillas (precio/margen, promociones, mercado, metas, desempeño, capacitación) | ✅ 2026-07-19 | `docs/comercial/`, 9 SOPs, 5 plantillas — ver detalle abajo. Módulo backend `sales` ajustado (margen, vigencia de promoción) |
| Almacén-Logística: procesos y plantillas (conteo, vencimientos/merma, transporte/transferencias) | ✅ 2026-07-19 | `docs/almacen-logistica/`, 8 SOPs, 6 plantillas — ver detalle abajo. Módulo backend `inventory` ajustado (lote, merma, ajuste solicitar/aprobar) |
| Producción, Contabilidad, Marketing, Gerencia: procesos y plantillas | ⬜ | Mismo patrón que RRHH/Compras/Comercial/Almacén-Logística — pendiente, un área a la vez |
| Mantenimiento, Sistemas/TI como áreas propias | ⬜ | Definidas como áreas del negocio (posible tercerización); documentación pendiente, desactivadas por ahora |
| RRHH backend, supervisión, CRM, tesorería, activos, proyectos, BI, reportes | ⬜ | Módulos futuros |
| Integración Nubefact | ⬜ | Adaptador en `src/shared/integrations/` |
| Integración Izipay | ⬜ | Proveedor decidido (ADR 0003) |
| Integraciones Google / Meta | ⬜ | |
| Agentes IA para pedidos | ⬜ | |
| Notificaciones | ⬜ | Celery + canales por definir |
| Auditoría (audit_log) | ⬜ | Especificada en data-model |
| App Android (15+) | ⬜ | Evaluar PWA vs nativo (ADR pendiente) |
| Backups automáticos | ⬜ | |
| Observabilidad (métricas, trazas, logs centralizados) | ⬜ | |
| UX: menús, buscadores, breadcrumbs, atajos, sidebars, dashboards | ⬜ | Definición pendiente con el usuario |
| Branding (paleta, tipografías, tokens CSS) | ✅ 2026-07-04 | Brandboard aplicado — `docs/product/ui-ux.md` |

## Orden sugerido de desarrollo

**Decisión del usuario (2026-07-14: "modelar toda la BD antes de
procesos") queda revertida (2026-07-14, sesión posterior).** Nuevo
enfoque: **slices verticales por proceso de negocio**, no fases
horizontales para todo el negocio. Un proceso a la vez (ej. "Compra de
insumos") atraviesa junto: procesos → reglas → casos de uso → eventos →
modelo de datos de ese proceso — antes de pasar al siguiente proceso.
Motivo: reglas (`business-rules.md`, 713 líneas) y modelo de datos
(`data-model.md`, 500 líneas) ya avanzaron adelantados y por separado del
resto — señal de que las fases se solapan naturalmente; evita también
rehacer entidades/reglas si aparece un caso raro tarde en un proceso ya
"cerrado" en otra fase.

El detalle de entidades ya relevado en la sesión de modelado de BD
(abajo) sigue siendo insumo válido — se incorpora al slice del proceso
correspondiente en vez de migrarse todo de una sola vez.

### Slice vertical en curso: Venta — PROC-COM-001 (2026-07-14/15)

**Nomenclatura de procesos** (2026-07-15, `docs/domain/process-nomenclature.md`):
código de área es el área real de la empresa, no el módulo del ERP —
Venta pertenece a Comercial (`COM`), no a un área "Ventas" (`VNT`).
Renombrado en todo lo ya escrito: `RN-VNT-*`→`RN-COM-*`, `CU-VNT-*`→
`CU-COM-*`, proceso registrado como `PROC-COM-001` (v1.0, Vigente) en el
[registro maestro](docs/domain/process-nomenclature.md#registro-maestro).
El módulo de código sigue llamándose `sales` y los eventos siguen
`sales.venta_*` — el código de área NO reemplaza el nombre del módulo
técnico, son cosas distintas.

Primer proceso elegido para atravesar completo. Avance de esta sesión:

- **Mapa visual end-to-end** (FigJam, todos los procesos conectados,
  incluye Venta) — ver enlace en la conversación; ya tenía "Producción en
  sucursal" y "Marketing" como secciones separadas de "Comercial / Venta"
  — coincide con el recorte de alcance de abajo, no hizo falta tocarlo.
- **Procesos**: `docs/domain/workflows.md`.
- **Reglas**: `docs/domain/business-rules.md`.
- **Casos de uso** (F4, doc nuevo): `docs/domain/use-cases.md` —
  CU-COM-001 (mesa), CU-COM-002 (takeout/delivery).
- **Eventos**: `docs/architecture/events.md`.
- **Estados**: `docs/domain/state-machines.md`.
- **Datos**: `docs/architecture/data-model.md` §6 — entidad
  `encuesta_satisfaccion` (queda igual, es de un módulo futuro).

**Corrección de alcance (2026-07-14, mismo día, tras revisar contra un
BPMN de Bizagi que trajo el usuario)**: Venta termina en el envío del
pedido a cocina + el cobro (RN-COM-005). Preparación, emplatado/
empaquetado, despacho y entrega al cliente NO son Venta — se retiraron de
`workflows.md`/`business-rules.md`/`use-cases.md`/`state-machines.md`/
`events.md` y quedaron marcados "fuera de Venta, borrador sin confirmar"
en esos mismos archivos (no se borró contenido, se reetiquetó). Pendiente
del usuario: si eso es UN proceso ("Cumplimiento de pedido") o DOS
(Producción/Cocina + Despacho/Entrega) — dijo "defino después".

**Relato detallado de los 3 canales (2026-07-14, mismo día)** — el usuario
narró la experiencia real de venta en Web, Central de Pedidos y Sucursal,
paso a paso, con puntos de abandono y su resolución. Incorporado:
- `use-cases.md` — CU-COM-001/002/003 reescritos por canal (antes eran
  por modalidad mesa/takeout-delivery, ahora son por canal real).
- `business-rules.md` — RN-COM-008 (datos obligatorios takeout/delivery),
  RN-COM-009 (confirmar pedido completo antes del precio), RN-COM-010/011/012
  (resolución de desistimiento por stock/precio/tiempo de espera),
  RN-COM-013 (registro de abandono para análisis de embudo).
- `events.md` — `sales.carrito_abandonado`.
- `workflows.md` — diagrama por canal, termina igual en "envío a cocina".
- **BPMN 2.0 para Bizagi** (generado, no a mano):
  `docs/diagrams/Procesos/Comercial/PROC-COM-001-v1.0.bpmn` — 5 lanes
  (Cliente, Web/Kiosko, Central de Pedidos, Atención al Cliente, Cocina),
  80 nodos, 96 flujos, arranca en 1 gateway de canal y converge en "Fin de
  Venta". Generado con script (no a mano) y validado estructuralmente
  (sin referencias colgantes, sin huérfanos, DI completo) — falta
  confirmar que Bizagi lo importe sin fricción, el usuario lo prueba.

Pendiente del slice Venta (señalado por el usuario, no modelado aún):
escalamiento de reclamos post-venta, monitoreo del pedido ya en curso,
manejo de errores técnicos/demoras del sistema. (Desistimiento durante la
toma del pedido SÍ quedó cubierto con RN-COM-010/011/012.) Módulo
`marketing` sigue sin README/contrato propio.

### Modelado de BD — siguiente sesión

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

### Apertura y Cierre de Caja — PROC-CTB-002 / PROC-CTB-001 (2026-07-16)

`PROC-CTB-002` Apertura de caja documentado (v1.0, Vigente), cerrando el
placeholder pendiente de `workflows.md`. Requirió también actualizar
`PROC-CTB-001` Cierre de caja (v1.0 → v1.1) para resolver una
inconsistencia real: el cierre asumía que el efectivo siempre termina en
contabilidad, pero la custodia puede quedarse en la sucursal (caja fuerte)
según seguridad del local y monto — ver RN-MDP-006.

Incorporado:
- `business-rules.md` — RN-POS-009 (POS de emergencia por grupo de
  sucursales), RN-POS-010 (inventario de POS con serie/código de
  comercio), RN-POS-011 (apertura no se bloquea por faltante/POS
  averiado), RN-POS-012 (encargado prevé sencillo), RN-POS-013 (dedicación
  exclusiva del encargado durante conteo/apertura), RN-MDP-002 ampliada
  (cadena de custodia inversa en apertura), RN-MDP-006 (custodia local vs.
  traslado a oficinas).
- `state-machines.md` — Custodia de efectivo: ciclo completo
  `en_caja → en_supervisor → (en_contabilidad → disponible | directo) →
  en_caja`, en vez de un `[*]` genérico.
- `workflows.md` — narrativa + Mermaid de Apertura de caja; Cierre de caja
  actualizado con la bifurcación de custodia.
- `process-nomenclature.md` — registro maestro actualizado.
- **BPMN 2.0 para Bizagi**: `PROC-CTB-002-v1.0.bpmn` (nuevo) y
  `PROC-CTB-001-v1.1.bpmn` (reemplaza v1.0), en
  `docs/diagrams/Procesos/Contabilidad/`.

### Apertura de Sucursal — PROC-OPE-001 (2026-07-16)

`PROC-OPE-001` Apertura de sucursal documentado (v1.0, Vigente). Primer
proceso del área nueva `OPE` (Operaciones), creada porque el proceso cruza
seguridad física, higiene/inocuidad, recepción de mercadería y RRHH sin
tener una sola área de negocio dueña. Resolvió una contradicción real
planteada en la descripción original: el aire acondicionado no puede
encenderse en paralelo a la limpieza (el polvo levantado acelera su
deterioro) — la apertura de caja (que enciende AC, pantallas, extractores)
pasa a ser secuencial, después de terminada la limpieza, no paralela a
ella.

Incorporado:
- `business-rules.md` — RN-SUC-006 a RN-SUC-012 (checklist de apertura de
  5 minutos no bloqueante, AC apagado durante limpieza, plaga/baños no
  bloquea pero exige desinfección + reporte a Mantenimiento, triage de
  falla de frío, tanque de gas de repuesto obligatorio + sanción por falta
  de aviso, contingencias de luz/agua, doble custodio de llave), RN-PER-006
  (jerarquía Supervisor sobre Encargado de tienda), RN-RRHH-009 a
  RN-RRHH-011 (no marcar entrada no se paga, memorándum vs. carta de
  amonestación por tardanza/falta del encargado según impacto en la
  apertura, compensación de personal faltante).
- `glossary.md` — "Supervisor" (Actores, con alcance RBAC de marca vs. el
  Encargado de tienda de una sola sucursal) y "Alarma" (Recursos, tipo
  Equipamiento).
- `workflows.md` — narrativa + Mermaid de Apertura de sucursal; referencia
  a PROC-CTB-002 (apertura de caja) y a los pasos 6-9 de PROC-INV-001
  (recepción de pedido) en vez de duplicarlos.
- `process-nomenclature.md` — área `OPE` agregada a la tabla; registro
  maestro actualizado.
- **BPMN 2.0 para Bizagi**: `PROC-OPE-001-v1.0.bpmn` (nuevo), en
  `docs/diagrams/Procesos/Operaciones/`. 3 carriles (Encargado/Supervisor,
  Atención al Cliente, Cocina), 59 nodos, 67 flujos — checklist de
  apertura con gateways de excepción para agua/luz/plaga-higiene/frío/gas
  inline; apertura de caja y recepción de pedido representadas como tareas
  que remiten a sus procesos ya documentados.

Pendiente (declarado, no bloquea): diagrama BPMN de las contingencias de
personal faltante (RN-RRHH-011) y de tardanza/falta del encargado o
supervisor (RN-RRHH-010) — la regla de negocio ya existe, el diagrama se
detalla en otra sesión.

### Área RRHH — reclutamiento, contratación e inducción (2026-07-19)

Documentación completa del área de Recursos Humanos: reclutamiento de
personal operativo, selección, elección de modalidad de contrato,
firma/alta, inducción y entrega de uniforme. Empresa acreditada como
**microempresa en REMYPE** (D.S. 013-2013-PRODUCE); saldrá del régimen
aprox. julio 2027 — documentación deja el punto de cambio marcado.

Incorporado:
- `docs/rrhh/` (nuevo): `README.md` (mapa del área, flujo de 13 pasos de
  incorporación), `marco-legal-laboral.md` (régimen microempresa vs.
  general, las 6 modalidades de contrato del grupo, obligaciones legales al
  contratar, plan de salida de REMYPE), `perfiles/` (cocina, atención al
  cliente/mozo-cajero — no existe puesto de cajero separado —, limpieza y
  apoyo, + plantilla para nuevos perfiles).
- `docs/diagrams/Procesos/Recursos-Humanos/` (área nueva en la taxonomía de
  SOPs): 13 SOPs en `Reclutamiento/` (requisición y perfil, convocatoria,
  filtrado, entrevista, verificación de referencias, selección y oferta),
  `Contratacion/` (elección de modalidad, firma y alta en T-Registro,
  apertura de file personal) e `Induccion/` (inducción grupo/empresa/marca,
  inducción al puesto, entrega de uniforme, evaluación de periodo de
  prueba).
- `docs/templates/rrhh/` — 9 plantillas nuevas: 3 contratos (indeterminado,
  sujeto a modalidad, tiempo parcial — con cláusulas de régimen
  microempresa), convocatoria, ficha de entrevista, carta de oferta, ficha
  de datos del trabajador, checklist de alta, acta de entrega de uniforme.
- `business-rules.md` — RN-RRHH-005 corregida (15 días de vacaciones bajo
  REMYPE, no 30); RN-RRHH-012 a RN-RRHH-014 (sin alta en T-Registro no hay
  primer turno, sin perfil ni requisitos discriminatorios no hay
  convocatoria, uniforme como condición de trabajo con acta y registro en
  ERP).
- `00_PROJECT.md` — entrada `rrhh/` en el mapa de documentación; tabla de
  `templates/` y `diagrams/` actualizadas.

Pendiente (declarado, no bloquea): módulo `rrhh` del ERP en sí (spec en
`data-model.md` §8b) — esta sesión documentó proceso y plantillas, no
implementó backend. Definir con contador/abogado el tratamiento de
contratos vigentes al momento de salir de REMYPE.

### Área Compras — proveedores, cotización, OC, recepción y pago (2026-07-19)

Documentación completa del área de Compras: alta/evaluación de
proveedores, cotización (RFQ), emisión y aprobación de OC, recepción en
Almacén Central, conformidad de comprobante y pago. Compra centralizada:
ninguna sucursal compra directo a proveedor externo. Puesto dedicado de
**encargado de compras** (a diferencia de RRHH, no lo ejecuta el
administrador). Pago mixto según proveedor (contado o crédito pactado por
ficha).

Incorporado:
- `docs/compras/` (nuevo): `README.md` (flujo de 7 pasos),
  `marco-legal-compras.md` (régimen Amazonía/Ley 27037 — IGV exonerado
  dentro de zona, comprobantes, detracciones SPOT, plazos de pago,
  centralización), `perfiles/encargado-compras.md`.
- `docs/diagrams/Procesos/Compras/` (área nueva): `Proveedores/` (alta y
  evaluación, evaluación periódica), `Cotizacion-OC/` (solicitud de
  cotización, emisión de OC, aprobación sobre umbral), `Recepcion-Pago/`
  (recepción en Almacén Central, conformidad de comprobante, pago a
  proveedor). 7 SOPs.
- `docs/templates/compras/` — 4 plantillas: ficha de proveedor, solicitud
  de cotización (RFQ), orden de compra, evaluación de proveedor.
- `business-rules.md` — RN-CMP-008 a RN-CMP-010 (bloqueo de OC sobre
  umbral y prohibición de fraccionamiento, RUC verificado antes del alta
  de proveedor, compra siempre centralizada en Almacén Central).
- `00_PROJECT.md` — entrada `compras/` en el mapa; tablas de `templates/` y
  `diagrams/` actualizadas.

Pendiente (declarado, no bloquea): definir el monto exacto del umbral de
aprobación de OC (queda `[[ COMPLETAR ]]` en el marco legal, la plantilla
de OC y el SOP de aprobación) y el plazo interno de envío de comprobantes
al contador.

**Segundo ajuste — sanción por faltante de caja chica (2026-07-19):** si la
rendición de caja chica queda con faltante no sustentado, Contabilidad
reporta a RRHH (identifica responsable y monto); tras derecho a descargo
(mismo principio que RN-RRHH-004), RRHH emite memorándum (plantilla ya
existente `templates/rrhh/memorandum.md`) y aplica descuento por planilla
del monto faltante; reincidencia (2+) puede escalar a amonestación.
Incorporado: `rendicion-caja-chica.md` (pasos 8-9 nuevos), RN-CMP-017,
`marco-legal-compras.md §7` actualizado.

**Ajuste de flujo real (2026-07-19, mismo día):** el usuario corrigió el
diseño inicial tras revisar. Cambios: (1) proveedores informales
(mercado/supermercado) compran sin OC, sustentados con boleta/factura y
pagados con **caja chica de compras** (fondo fijo, rendición semanal a
Contabilidad); (2) con proveedor "preferente" recurrente, la OC se emite
**sin cotización comparativa** (sustento = requerimiento de almacén +
factura) — la comparación de precio vive en la evaluación periódica, no en
cada compra; (3) el encargado de compras también busca y negocia
**activos/equipamiento**, siempre con cotización comparativa y validación
de especificación/precio por el **área solicitante + gerencia** antes de
la OC; (4) **Contabilidad ejecuta el pago**, no Compras — Compras solo
sustenta el comprobante conforme; (5) la **evaluación de proveedor es
automática en el ERP** a partir de recepciones, con revisión humana solo
sobre alertas.

Incorporado en el ajuste: `docs/compras/perfiles/encargado-compras.md`,
`README.md` y `marco-legal-compras.md` reescritos (3 caminos de compra,
caja chica, activos); 2 SOPs nuevos en `Caja-Chica/` (compra a proveedor
informal, rendición semanal) y 1 en `Activos-Equipamiento/` (búsqueda y
negociación); SOPs de cotización/OC/pago/evaluación corregidos; 2
plantillas nuevas (rendición de caja chica, ficha de requerimiento de
activo); RN-CMP-011 a RN-CMP-016 nuevas; **spec técnica
`src/modules/purchases/README.md` actualizada** para que el módulo real
del ERP se construya conforme a este flujo (camino simplificado, compra
directa, caja chica, OC tipo activo con doble validación, evento de
comprobante conforme a `accounting` en vez de que `purchases` pague).

### Área Comercial — precio, margen, promociones, mercado y desempeño de venta (2026-07-19)

Documentación completa del área Comercial, a partir de un alcance amplio
dado por el usuario: no solo vender, sino mejorar procesos de venta, buscar
mercado/público nuevo, impulsar producto nuevo (coordina con
Producción/I+D+i), coordinar leads con Marketing, ofertas/promociones,
metas de venta, evaluación de desempeño del personal operativo, y
capacitación conjunta con RRHH/Marketing. Puesto dedicado: **jefe/encargado
comercial**. Decisión clave: la evaluación de desempeño de venta que hace
Comercial **alimenta** el proceso de RRHH pero no reemplaza su decisión de
continuidad laboral (periodo de prueba sigue siendo de RRHH). Metas de
venta: sin esquema de incentivo/comisión definido aún — se documentó el
criterio de cómo se aprobaría (Comercial + RRHH + Gerencia, nunca
retroactivo) sin inventar cifras.

Incorporado:
- `docs/comercial/` (nuevo): `README.md` (mapa de responsabilidades →
  SOPs), `politica-comercial.md` (margen de contribución, precios,
  ofertas/promociones, metas/incentivos, coordinación con áreas aún no
  documentadas), `perfiles/jefe-comercial.md`.
- `docs/diagrams/Procesos/Comercial/` — 9 SOPs nuevos en
  `Estrategia-Mercado/` (mejora continua de experiencia de cliente,
  investigación de mercado/público objetivo, coordinación de desarrollo de
  nuevo producto), `Precios-Promociones/` (evaluación de precio y margen,
  creación de oferta/promoción) y `Metas-Desempeno/` (coordinación de leads
  con Marketing, definición/seguimiento de metas, evaluación de desempeño
  comercial del personal, capacitación de venta). Se suman a `Ventas/` y
  `Cobros/` ya existentes.
- `docs/templates/comercial/` — 5 plantillas: ficha de precio/margen,
  brief de oferta/promoción, ficha de requerimiento de nuevo producto,
  reporte de desempeño comercial, plan de capacitación de venta.
- `business-rules.md` — nueva sección "Comercial — estrategia" con
  RN-CML-001 a RN-CML-006 (margen obligatorio antes de publicar precio,
  brief obligatorio de promoción, incentivo nunca retroactivo, evaluación
  de desempeño como insumo de RRHH sin reemplazar su decisión, producto
  nuevo no se compromete sin validar viabilidad, decisión de mercado
  requiere hallazgo documentado).
- `glossary.md` — término **Margen de Contribución** agregado (se usaba en
  varios lugares sin definición formal).
- `src/modules/sales/README.md` (spec técnica) — `lista_precio` con
  vigencia de promoción auto-restaurable, cálculo de margen de
  contribución expuesto a Comercial, cambio de precio siempre por nueva
  versión (nunca edición directa), igual que las OC de `purchases`.
- `00_PROJECT.md` — entrada `comercial/` en el mapa; tablas actualizadas.

Pendiente (declarado, no bloquea): margen de contribución mínimo objetivo
(queda `[[ COMPLETAR ]]`, a definir con contabilidad); esquema de
incentivo/comisión de metas de venta (queda como criterio a definir, sin
cifra); documentación propia de **Marketing** e **I+D+i/Producción** —
Comercial coordina con ambas pero solo documentó su propio lado del
proceso.

### Área Almacén y Logística — conteo, vencimientos/merma, transporte (2026-07-19)

Documentación completa del área, complementando lo que ya existía
(`Abastecimiento-Locales/`, 3 SOPs del ciclo sucursal↔central, y RN-ALM-*/
RN-INV-* ya cubrían bastante del modelo). Se agregó lo que faltaba: conteo
cíclico y ajuste con discrepancia investigada, control FEFO/FIFO explícito,
gestión de vencimiento próximo, registro de merma/desperdicio, devolución a
proveedor, y transporte/transferencias (incluye **transferencia lateral
entre sucursales**, confirmada por el usuario como excepción real del
negocio). Puesto dedicado: **encargado de Almacén Central**; transporte con
**flota propia** (perfil de chofer/repartidor, kilometraje obligatorio
RN-VEH-004).

Incorporado:
- `docs/almacen-logistica/` (nuevo): `README.md` (deja explícito qué NO
  duplica — recepción de compra vive en Compras, ciclo de requerimiento ya
  documentado), `politica-almacen-logistica.md` (FEFO/FIFO, conteo/ajuste,
  punto de reorden — quién lo define [Producción+Contabilidad+Logística,
  RN-INV-008] vs. quién compra [Compras], vencimiento/merma, devoluciones,
  transferencia lateral, transporte), `perfiles/` (encargado de almacén
  central, chofer/repartidor).
- `docs/diagrams/Procesos/Logistica-Almacen/` — 8 SOPs nuevos en
  `Conteo-Auditoria/` (conteo cíclico, ajuste por discrepancia),
  `Vencimientos-Mermas/` (FEFO/FIFO, vencimiento próximo, merma/desperdicio)
  y `Transporte-Transferencias/` (transferencia lateral, logística de
  reparto, devolución a proveedor). Se suman a `Abastecimiento-Locales/`
  ya existente.
- `docs/templates/almacen-logistica/` — 6 plantillas: reporte de conteo
  cíclico, ficha de ajuste, reporte de merma, guía de transferencia
  lateral, guía de devolución a proveedor, hoja de ruta de reparto.
- `src/modules/inventory/README.md` (spec técnica) — entidades `lote`,
  `stock_merma`, `conteo`, `ajuste`, `devolucion`; casos de uso de FEFO/FIFO,
  ajuste con permisos separados de solicitar/aprobar, transferencia lateral
  (ya soportada por el modelo genérico origen/destino, sin cambio de
  esquema); eventos nuevos `inventory.merma_registrada`,
  `inventory.devolucion_a_proveedor`, `inventory.ajuste_fuera_margen`.
- `00_PROJECT.md` — entrada `almacen-logistica/` en el mapa; tablas
  actualizadas.

No se generaron reglas de negocio nuevas — RN-ALM-001..007 y RN-INV-001..020
ya cubrían el modelo; los SOPs las aplican en vez de duplicarlas.

Pendiente (declarado, no bloquea): frecuencia exacta de conteo cíclico y
margen de error de ajuste (quedan `[[ COMPLETAR ]]`, a definir con
Contabilidad); quién autoriza ajustes (admin vs. supervisor de logística,
rol aún no existe formalmente).

### Fase de procesos (tras el modelado de BD)

1. `users`: auth (login PIN → JWT/refresh), RBAC, contexto de tenant, auditoría base.
2. Organización: grupo → empresa → marca → sucursal → almacén (vive en `users` o módulo `organization`).
3. `inventory`: artículos, stock por almacén, movimientos.
4. `purchases`: proveedores, OC, recepción → entrada a almacén central.
5. Solicitudes + transferencias central → local.
6. `sales`: PDV, recetas, descuento automático de insumos, pagos, Nubefact.
7. Producción, contabilidad, RRHH, resto de módulos.
