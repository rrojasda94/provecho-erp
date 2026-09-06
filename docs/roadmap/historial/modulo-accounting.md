# Historial — Módulo `accounting` (incluye tesorería)

Estado vigente: 🔶 En curso — núcleo contable (PCGE, asientos automáticos y
manuales, periodos, libro mayor, estados financieros) y ciclo completo de
caja/custodia/tesorería (pago a proveedor) están en producción desde
2026-09-05, con deuda técnica declarada (fecha del asiento, incremento de
una orden ya confirmada, separación tesorería/registro al salir de REMYPE).

## Cronología

### 2026-07-14/15 — Modelado de BD, entidades transversales (planificación)

Del bloque "Modelado de BD — siguiente sesión", entidades nuevas a
incorporar al modelado, dentro del bloque **Operación comercial**:

> - **Operación comercial**: `carrito`, `medio_pago`, `custodia_efectivo`,
>   `promocion`, `cuenta_puntos`+`puntos_movimiento`, `programa_puntos_config`,
>   `declaracion_itan`.

(`custodia_efectivo` es la primera mención en la bitácora de la entidad que
luego pasa a vivir en `accounting`.)

### 2026-07-16 — Apertura y Cierre de Caja — PROC-CTB-002 / PROC-CTB-001

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

### 2026-07-19 — Área Compras: decisión de que Contabilidad ejecuta el pago

Del área "Compras — proveedores, cotización, OC, recepción y pago",
ajuste de flujo real acordado con el usuario el mismo día del primer
diseño:

> **Ajuste de flujo real (2026-07-19, mismo día):** el usuario corrigió el
> diseño inicial tras revisar. Cambios: (1) proveedores informales
> (mercado/supermercado) compran sin OC, sustentados con boleta/factura y
> pagados con **caja chica de compras** (fondo fijo, rendición semanal a
> Contabilidad); (2) con proveedor "preferente" recurrente, la OC se emite
> **sin cotización comparativa** (sustento = requerimiento de almacén +
> factura) — la comparación de precio vive en la evaluación periódica, no en
> cada compra; (3) el encargado de compras también busca y negocia
> **activos/equipamiento**, siempre con cotización comparativa y validación
> de especificación/precio por el **área solicitante + gerencia** antes de
> la OC; (4) **Contabilidad ejecuta el pago**, no Compras — Compras solo
> sustenta el comprobante conforme; (5) la **evaluación de proveedor es
> automática en el ERP** a partir de recepciones, con revisión humana solo
> sobre alertas.
>
> Incorporado en el ajuste: `docs/compras/perfiles/encargado-compras.md`,
> `README.md` y `marco-legal-compras.md` reescritos (3 caminos de compra,
> caja chica, activos); 2 SOPs nuevos en `Caja-Chica/` (compra a proveedor
> informal, rendición semanal) y 1 en `Activos-Equipamiento/` (búsqueda y
> negociación); SOPs de cotización/OC/pago/evaluación corregidos; 2
> plantillas nuevas (rendición de caja chica, ficha de requerimiento de
> activo); RN-CMP-011 a RN-CMP-016 nuevas; **spec técnica
> `src/modules/purchases/README.md` actualizada** para que el módulo real
> del ERP se construya conforme a este flujo (camino simplificado, compra
> directa, caja chica, OC tipo activo con doble validación, evento de
> comprobante conforme a `accounting` en vez de que `purchases` pague).

También, dentro del mismo bloque de Compras, sobre la sanción por faltante
de caja chica:

> **Segundo ajuste — sanción por faltante de caja chica (2026-07-19):** si la
> rendición de caja chica queda con faltante no sustentado, Contabilidad
> reporta a RRHH (identifica responsable y monto); tras derecho a descargo
> (mismo principio que RN-RRHH-004), RRHH emite memorándum (plantilla ya
> existente `templates/rrhh/memorandum.md`) y aplica descuento por planilla
> del monto faltante; reincidencia (2+) puede escalar a amonestación.
> Incorporado: `rendicion-caja-chica.md` (pasos 8-9 nuevos), RN-CMP-017,
> `marco-legal-compras.md §7` actualizado.

### 2026-07-20 — Slice Cobro, Comprobante y Caja

Segundo incremento del proceso Venta, a pedido del usuario: PROC-COM-002
(Cobro y Emisión de Comprobante) + el ciclo de caja completo
(PROC-CTB-001/002), que el cobro en efectivo necesita para cerrar su
cadena de custodia. Antes de modelar, alineamos 4 decisiones reales con
el usuario (no asumidas):

1. Alcance: caja completa (apertura/cierre/custodia) esta misma vuelta,
   no diferida.
2. Series de comprobante separadas por punto de venta (boleta ≠
   factura, típico SUNAT) — `punto_venta.serie_boleta`/`serie_factura`.
3. `medio_pago` es catálogo **por empresa**, no global del grupo.
4. Pago dividido (varios medios en una misma venta) es un caso real del
   negocio, no solo capacidad técnica — RN-COM-016 nueva.

Gaps reales encontrados y corregidos en `data-model.md` antes de
modelar: `pago` no tenía `monto` ni `idempotency_key` (imposible validar
pago dividido sin monto por fila); `medio_pago` no tenía `empresa_id`;
`punto_venta` no tenía dónde vivir la serie que `comprobante.serie`
dice heredar.

8 tablas nuevas (30 en total): `medio_pago`, `pago` (sales);
`comprobante` (nuevo módulo transversal `src/shared/models/` — sirve a
sales/purchases/accounting, ningún módulo lo posee en exclusiva);
`apertura_caja`, `custodia_efectivo`, `cierre_caja`, `arqueo` (nuevo
módulo `src/modules/accounting/`, solo el ciclo de caja — plan de
cuentas/asiento/periodo_contable siguen pendientes). 3 eventos nuevos en
`events.md`: `accounting.apertura_caja_registrada`,
`accounting.cierre_caja_registrado`, `accounting.cierre_caja_irregular`.

Deliberadamente diferido: `carta_disputa_pago` (RN-MDP-004, camino de
excepción — reclamo de doble cobro).

Migración `8cde35e4f3f2`, verificada en Supabase (ciclo upgrade/
downgrade/upgrade). 13/13 tests pasan (3 nuevos en
`tests/test_cobro_caja_slice.py`).

### 2026-07-20 — Revisión de consistencia y correcciones

Del bloque de correcciones aplicadas en la misma sesión de revisión
completa del proyecto:

> - Data-model: bloque Compras completo (caja chica, compra directa,
>   evaluación de proveedor, requerimiento de activo), `stock_lote`
>   (FEFO/FIFO implementable + bloqueo de vencidos con memorándum),
>   `ajuste`, `apertura_caja`/`cierre_caja`/`arqueo` (caja ya no es módulo
>   "futuro"), `flota`, `combo`, `plantilla`; `contrato` reubicado como
>   transversal; `articulo.tipo` + `suministro` (enum extensible).
> - `PROC-CMP-001` v1.0 → v2.0 (3 caminos de compra, pago en Contabilidad).

### 2026-07-24 — Contabilidad: procesos y plantillas (F0)

| Área | Estado | Notas |
|------|--------|-------|
| Contabilidad: procesos y plantillas | ✅ 2026-07-24 | `docs/contabilidad/` (política + marco legal + perfil contador/tesorero), 3 SOPs nuevos (pago a proveedor PROC-CTB-003, conciliación bancaria PROC-CTB-004, arqueo sorpresa PROC-CTB-005), 4 plantillas — ver detalle abajo. Área = tesorería + finanzas + registro + auditoría interna en un solo responsable, supervisada por Gerencia (RN-CTB-004..009; control en dos niveles: Contabilidad audita a las operativas, Gerencia audita a Contabilidad). Quedan propuestos PROC-CTB-006..013 |

Del registro de "Pendientes de decisión":

> - ✅ 2026-07-24 Área Contabilidad documentada — `docs/contabilidad/`
>   (tesorería + finanzas + registro en un responsable, supervisada por
>   Gerencia); resuelve el pendiente "Contabilidad: procesos y plantillas" y
>   confirma CAJ/TES/ACT bajo Contabilidad. Incluye auditoría interna en dos
>   niveles (RN-CTB-009): Contabilidad audita a Compras/Almacén/cajas de
>   sucursal; Gerencia audita a Contabilidad. Propuestos PROC-CTB-006..013.
>   Pendientes de este mismo pendiente: separar tesorería/registro al salir de
>   REMYPE, y llevar entidades contables (asiento, plan de cuentas, activo
>   fijo, conciliación) a `data-model.md` en su slice.

### 2026-07-25 — Módulo `accounting` — slice core + tesorería (F0)

| Área | Estado | Notas |
|------|--------|-------|
| Módulo `accounting` | 🔶 slice core+tesorería ✅ 2026-07-25 | Libro contable núcleo: plan de cuentas (`cuenta_contable`), periodo (`periodo_contable`, abrir/cerrar), asiento manual (`asiento`/`asiento_linea`, cuadre RN-CTB-001, anulación por asiento inverso RN-CTB-002) y mapeo configurable evento→cuentas (`regla_asiento`) que alimenta la generación automática para 4 eventos operativos ya publicados en código (`purchases.oc_emitida`, `purchases.compra_recibida`, `sales.venta_confirmada`, `purchases.comprobante_conforme`). **Pago a proveedor** (PROC-CTB-003, `movimiento_dinero`): cola idempotente por comprobante (RN-CTB-008) → ejecutar con umbral configurable + permiso (RN-CTB-005) → asiento automático. Migraciones `5402d99333fa`+`cbf904a9fc1b` aplicadas. **Contabilidad peruana** (2026-08-29, ADR-081, **sin migración**): el plan de cuentas de fábrica pasa a ser el **PCGE** —Plan Contable General Empresarial 2019, el catálogo obligatorio en el Perú— en `domain/pcge.py`, sembrable por empresa con `POST /accounting/cuentas-contables/pcge` (idempotente, botón en Plan de cuentas). Vive en código y no en configuración porque no es una decisión de la empresa sino norma nacional, la misma para las tres empresas del grupo y para el contador externo; lo que sigue configurándose es qué cuenta usa cada evento. Cubre elementos 1-7 y 9 a nivel de rubro con las divisionarias de un restaurante (del 8 solo 87 y 88; el 0 queda fuera, ver deuda). **Los asientos automáticos dejan de ser de dos líneas**: `regla_asiento` no podía expresar ningún asiento peruano real —una venta gravada son tres líneas y una compra cinco contando el asiento de destino—, así que `domain/plantillas.py` trae el asiento oficial por evento (venta 1212/40111/7011, compra 6011/40111/4212 + 201/611, consumo de personal 625/201, merma y faltante 6599/201, pago 4212/1041) y `regla_asiento` pasa a ser el **override** que gana cuando la empresa lo configuró. El **IGV se desagrega** de lo que trae cada evento y **por diferencia contra el total** —redondear base e IGV por separado descuadra el asiento por un céntimo—, con tasa cero en Amazonía (Ley 27037) y sin escribir la línea en 0.00. Un asiento solo se imputa en cuentas de último nivel. **Estados financieros** (`application/estados_financieros.py`, `GET /accounting/reportes/*`, pantalla Contabilidad → Estados financieros): balance de comprobación, libro mayor, Estado de Situación Financiera y Estado de Resultados **por naturaleza** —el por función necesita los asientos de destino del elemento 9 contra la 79, que nadie genera, y saldría sin cuadrar—. Son consulta pura sobre `asiento_linea`, sin tabla de saldos: un saldo materializado es un segundo lugar donde vive la verdad. **Ninguna consulta filtra por `asiento.estado`**: el anulado y su reversión suman cero, y excluir el anulado restaría el hecho dos veces. El resultado se devuelve por líneas **y** leído del libro entero, con un `cuadra` que expone el descuadre en pantalla. **El IGV se elige y nace con el comprobante** (2026-08-29, misma ADR-081 enmendada, migración `dfb195b14433`): el régimen estaba cableado a `empresa.zona_tributaria` en **dos** sitios con la misma línea copiada —el asiento contable y el comprobante electrónico de `sales`—, así que no había dónde elegirlo y no había forma de que una operación puntual se apartara de él. Majambo vende exonerada por Amazonía y aun así **compra con IGV** a proveedores de fuera de la región: ese crédito fiscal no se registraba en ninguna parte. Ahora lo resuelve `src/shared/tributos.py`, único lugar del ERP que decide el régimen, con tres niveles —la casilla de la operación (`comprobante.gravado_igv`, nullable) → el default de la empresa (`empresa.config_fiscal["igv_por_defecto"]`, un select en Organización → Empresas; la columna JSONB ya existía y no la leía nadie) → su zona tributaria, que es el comportamiento histórico y por eso desplegar esto no cambia de régimen a ninguna empresa viva—. La exoneración de Amazonía depende de zona **y actividad**, así que el enum de zona solo no alcanzaba. **El IGV se reconoce con el comprobante**: la venta confirmada y la compra recibida asientan sin IGV y lo asientan `sales.comprobante_emitido` (7011/40111, débito fiscal — evento que `accounting` por fin consume, uno de los pendientes de la deuda) y `purchases.comprobante_conforme` (40111/4212, crédito fiscal). No es un rodeo: el crédito solo se toma con el comprobante válido y anotado, el débito nace con el emitido, y de paso el flag queda en una sola tabla en vez de repartido entre `venta` y `orden_compra` —que además se asientan antes de que el comprobante exista—. La casilla se marca donde alguien tiene el documento delante: un select de tres estados en el diálogo de cobro del PDV y un campo en la conformidad de compras. De paso se corrigió el payload de `sales.comprobante_emitido`, que mandaba `venta.total` en vez del importe de **su** grupo de cobro: con la cuenta dividida (RN-COM-018) habría reconocido el IGV una vez por comprobante sobre la venta entera. Con IGV exonerado los dos asientos nuevos quedan en cero y no se escriben, así que para Majambo el libro queda igual. Migración validada contra Postgres (`alembic check` sin drift). Tests: `tests/test_accounting_pcge.py`. Diferido: ver Deuda técnica. |

Nota relacionada del módulo `purchases` (mismo día, mismo slice): "Conformidad
de comprobante (`purchases.dar_conformidad`) registra el `comprobante`
recibido y dispara `purchases.comprobante_conforme` → cola de pago en
`accounting`."

### 2026-07-26 — Dashboard gerencial mínimo (slice mínimo de caja)

> `GET /api/v1/dashboard/resumen` (`src/core/dashboard_router.py`, permiso
> `dashboard.leer`): ventas del día (cantidad+total), stock bajo mínimo,
> cajas abiertas — agregador en `core`, nunca importa dominio de otro
> módulo (ADR-012). Requirió construir dos huecos que no existían: `sales`
> no tenía ningún listado de ventas, `accounting` tenía los modelos de
> caja (`apertura_caja`/`cierre_caja`/`arqueo`, migrados desde 2026-07-20)
> sin capa de aplicación. **Slice mínimo de caja**
> (`accounting.application.caja`): abrir/cerrar/arquear con
> **reconciliación real** (el cierre calcula `monto_esperado` desde los
> pagos en efectivo reales, vía contrato público de `sales`, no un número
> tipeado sin verificar). Primer frontend real: login por PIN + pantalla
> de dashboard en Next.js. Fuera de esta fase, a propósito: RN-POS-009..013
> completas, relevo autenticado por PIN, máquina de estados de
> `custodia_efectivo` — ver Deuda técnica.

### 2026-08-04 / 2026-08-05 / 2026-08-15 — Ciclo de caja completo (ADR-025, ADR-049)

> Ciclo de caja completo | ✅ 2026-08-04 | ADR-025, migración `f3a1c62d90b4`.
> **No se cobra sin caja abierta** (contrato público
> `accounting.hay_caja_abierta`; el replay del hub es la única excepción);
> el monto de apertura y cierre **sale del conteo por denominación**
> (RN-POS-003/007) y la diferencia contra lo declarado se calcula sin
> bloquear la apertura (RN-POS-011); **cada relevo lo firma quien recibe
> con su PIN** (RN-MDP-002, permiso `accounting.caja_relevar`) y
> `custodia_efectivo` es máquina de estados real hasta `disponible`; **un
> cierre con faltante se reabre y se recuenta** dejando motivo y
> autorizador en `cierre_caja.correcciones` (RN-MDP-005), solo mientras el
> efectivo siga en el local. Nueva entidad `pos_tarjeta` (serie + código de
> comercio, RN-POS-010; emergencia = `sucursal_id` NULL, RN-POS-009)
> verificada al abrir. `tests/test_caja_ciclo.py` (17 casos).
> **Pantallas (2026-08-05)**: los diálogos del PDV se pusieron al día con
> este contrato —hablaban el anterior y devolvían 422 desde el día que se
> implementó— y contabilidad gana `/contabilidad/caja` con turnos cerrados,
> cadena de custodia firmada con PIN, reapertura e inventario de POS (`GET
> /accounting/cajas/turnos`). En el camino se cerró un agujero de
> integridad: `custodia` y `descuadre_atribucion` son enums y el schema los
> aceptaba como texto libre, dejando la fila ilegible al leerla. 24 casos.
> **Enmendado el 2026-08-15 (ADR-049, RN-MDP-008, migración
> `c8b41f60d2a7`)**: la firma con PIN salió de la apertura y del cierre
> —**el cajero opera su turno solo**, le basta `accounting.caja_operar`—
> y quedó donde la plata cambia de manos. Al cerrar, el efectivo nace
> `en_caja` a nombre del cajero y el encargado firma la recepción después
> (`en_caja → en_supervisor`), un estado que existía en el enum desde el
> primer día y que el sistema no escribía nunca. El motivo es de
> operación, no de modelo: exigir que un encargado viniera a firmar cada
> apertura se pagaba dejando su sesión abierta en la caja todo el turno,
> que es lo contrario de lo que la firma buscaba probar.
> `relevo_encargado_id` queda NULLABLE y `encargado_de_turno` se apaga en
> la práctica (ver Deuda técnica → Dashboard y caja). Recorrido de uso
> nuevo: `frontend/uso/caja-custodia.spec.ts`.

### 2026-07-25 (documentado 2026-08-05) — Tesorería vive dentro de `accounting`

Del bloque "Supervisión, CRM, tesorería, activos, proyectos, BI/reportes":

> **Tesorería** ✅ 2026-07-25: vive **dentro de `accounting`** por decisión
> explícita del usuario —pago a proveedor, `movimiento_dinero`, caja y
> custodia— y separarla al salir de REMYPE es un pendiente de
> organización, no de código.

Y sobre Activos (dueño repartido entre `purchases` y `accounting`):

> **Activos** ⬜ pero **ya tiene dueño**: se compran en `purchases` (OC
> tipo `activo` + `requerimiento_activo`, deuda declarada) y se deprecian
> en `accounting` (activo fijo/depreciación, PROC-CTB-007/010) — partirlos
> en un tercer módulo cortaría el ciclo de compra en dos.

### 2026-08-05 — Pendiente `accounting/plazo_envio_comprobante`

De los parámetros operativos propuestos:

> - 🔶 `accounting/plazo_envio_comprobante` — propuesto 5 días hábiles
>   desde el cierre. Es plazo **interno**: el vencimiento real de SUNAT
>   depende del último dígito del RUC.

### 2026-08-30 — Parche 0.9.1: la cuenta contable se hereda de la categoría (ADR-086)

Del parche de tercer turno de prueba en staging:

> Siete reportes. **Cinco no eran código faltante en el backend**: eran
> superficies que nunca se construyeron sobre endpoints que ya existían y
> ya tenían pruebas verdes — el patrón que se repite desde la 0.8.0 y que
> este parche corta. Los otros dos sí eran decisiones pendientes: cuánto
> dura una sesión y **de dónde sale la cuenta contable de lo que se compra
> y se vende**.
>
> | 7 | La cuenta contable se configura en la categoría y se hereda (ADR-086) | ✅ 2026-08-30 |

### 2026-09-04 — Auditoría del 2026-08-30, Ola 2: RBAC de pagos y asientos

> La auditoría backend↔frontend del 2026-08-30 dejó 18 hallazgos repartidos
> en cuatro olas. [...] Ésta es la **Ola 2**: seis bloques, una rama y un
> PR cada uno.
>
> Lo que une a los seis no es un error visible —es el patrón que la
> auditoría vino a buscar—: un botón que promete 403, un formulario que se
> borra solo cuando el servidor rechaza, un cuadre que dice «no cuadra»
> por un centavo que no existe [...]
>
> | `fix/contabilidad-pagos-rbac` | #3 ejecutar/rechazar pago sin gate + #4 diálogo con reset-on-error + #11 el rechazo descartaba su resultado | ✅ 2026-09-04 |
> | `fix/contabilidad-asientos-rbac` | #3 «+ asiento manual» y «Anular» sin gate + #4 diálogo + #16 el cuadre se comparaba en `float` | ✅ 2026-09-04 |

También, en la Ola 1 (2026-08-30), sobre botones gateados por permiso:

> | 3 | «Reintentar emisión», «Nota de crédito» y «Anular» gateados por permiso | ✅ 2026-09-04 — el resto de los botones-403 (pagos, asientos, trabajadores, artículos, devoluciones) se cerró en la Ola 2; la OC ya estaba gateada desde ADR-085 |

### 2026-09-05 — La contabilidad que no registraba, y la Ola 3

Reportado operando en staging: **las ventas cerradas no aparecían en el
balance y la comida de personal no costaba nada**. La hipótesis era que
faltaba cablear algo, o que la facturación en pruebas solo reconoce
comprobantes oficiales.

No era eso, y vale escribirlo porque es el patrón que se repite: **el
cableado estaba completo y probado**. El asiento de la venta se genera al
confirmar la orden —del comprobante aceptado cuelga solo el IGV— y el de la
comida de personal existe desde ADR-034. Lo que fallaba es que el asiento
**se descartaba en silencio** por dos cosas que había que hacer a mano y
nadie sabía: importar el plan de cuentas y abrir el periodo del mes. Un mes
que nadie abría descartaba todos los asientos automáticos del ERP entero, y
el único aviso era un `log.info` que además decía el motivo equivocado.

| Bloque | Qué | Estado |
|---|---|---|
| `fix/contabilidad-no-asienta` | La empresa nace con su PCGE, el periodo se abre al primer asiento del mes, y la omisión queda en `asiento_omitido` con su motivo (ADR-089) | ✅ 2026-09-05 |
| `fix/contabilidad-cobro-y-anulacion` | El cobro cancela la `1212` y mueve caja/bancos según con qué se cobró; la venta anulada revierte su ingreso | ✅ 2026-09-05 — el incremento de una orden ya confirmada y la fecha del asiento quedan como deuda, ver `deuda/modulo-accounting.md` |

Y la **Ola 3** de la auditoría del 2026-08-30: cinco bloques, todos del
mismo patrón que esta bitácora viene anotando desde la 0.8.0 — endpoints
entregados, probados y sin pantalla que los llame.

| Bloque | Qué | Estado |
|---|---|---|
| `feat/contabilidad-arqueos-libro-mayor` | Arqueos (con su `GET`, que faltaba), reglas de asiento, libro mayor navegable y detalle de asiento | ✅ 2026-09-05 |

Fuera de alcance y anotado como deuda: préstamos, premios de concurso y
mover efectivo del banco a caja chica se registran por ahora con el asiento
manual —el cómo está en
[`docs/contabilidad/operaciones-no-operativas.md`](../../contabilidad/operaciones-no-operativas.md)—
porque el circuito de custodia de ADR-025 cuelga de una apertura de caja del
PDV y el efectivo que viene del banco no tiene dónde colgarse.

## Estado vigente

🔶 En curso. El núcleo contable (PCGE sembrable, periodos, asientos
manuales y automáticos por evento con IGV desagregado, libro mayor, arqueos
y estados financieros) y la tesorería/ciclo de caja completo (apertura,
custodia, relevo por PIN, cierre con reconciliación, pago a proveedor
idempotente) están construidos, probados y en producción desde 2026-09-05.
Queda declarado como deuda técnica (ver `docs/roadmap/deuda/modulo-accounting.md`,
que este historial no reproduce por instrucción explícita): la fecha real
del asiento, el asiento de un incremento sobre una orden ya confirmada, el
registro de préstamos/premios/traspaso banco→caja chica sin asiento manual,
y la separación tesorería/registro como pendiente organizacional al salir
de REMYPE (~jul 2027).

## Fuentes

Rangos de línea de `ROADMAP.md` usados (antes de esta reorganización):

- 12-66 (tabla F0): filas 23 (`purchases`, mención comprobante_conforme→accounting),
  26 (`accounting` slice core+tesorería+PCGE+IGV), 38 (Contabilidad: procesos y
  plantillas), 40 (Tesorería vive dentro de accounting; Activos), 53 (Ciclo de
  caja completo, ADR-025/ADR-049), 54 (Dashboard gerencial mínimo, slice
  mínimo de caja).
- 189-221 (Auditoría 2026-08-20, Ola 1): fila 200 (botones-403 de asientos/pagos).
- 222-240 (Parche 0.9.1): filas 224-228 (intro) y 237 (ADR-086, cuenta contable
  por categoría).
- 260-288 (Auditoría 2026-08-30, Ola 2): intro 267-271 y filas 275-276
  (`fix/contabilidad-pagos-rbac`, `fix/contabilidad-asientos-rbac`).
- 289-329 (La contabilidad que no registraba, y la Ola 3): sección completa.
- 375-573 (Pendientes de decisión): líneas 419-421 (`accounting/plazo_envio_comprobante`),
  461-469 (Área Contabilidad documentada, pendiente separar tesorería/registro).
- 713 (Modelado de BD — entidades transversales, `custodia_efectivo`).
- 731-757 (Apertura y Cierre de Caja — PROC-CTB-002/PROC-CTB-001).
- 882-907 (Área Compras — ajuste de flujo real: Contabilidad ejecuta el pago;
  sanción por faltante de caja chica).
- 1041-1078 (Slice Cobro, Comprobante y Caja).
- 1095-1101 (Revisión de consistencia y correcciones — data-model caja/pago).

No se modificó `ROADMAP.md` ni ningún otro archivo existente al producir
este historial.
