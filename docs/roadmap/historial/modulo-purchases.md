# Historial — Módulo `purchases`

Estado vigente: 🔶 En curso — proveedores, ciclo de OC (crear→emitir→recibir→anular,
con idempotencia y umbral de aprobación), recepción con entrada a inventario,
conformidad de comprobante con cola de pago hacia `accounting`, y compra directa
sin OC previa (ADR-081) ya están implementados en código; quedan pendientes la
caja chica para pagar la compra directa, la OC tipo activo con doble validación,
y la reconciliación completa estilo Odoo entre compras/inventario/contabilidad
(ver Deuda técnica).

## Cronología

### 2026-07-04 — Especificación inicial de módulos base

> Especificaciones de módulos base | ✅ 2026-07-04 | READMEs de users, inventory, sales, purchases, accounting

(Fuente: fila de la tabla F0, línea 12 — mención genérica junto a los demás
módulos base; el README propio de `purchases` nace en esta fecha.)

### 2026-07-19 — Área Compras: procesos y plantillas (proveedores, cotización, OC, recepción, pago)

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
  proveedor). 8 SOPs (con el ajuste posterior de caja chica y activos:
  11 en total).
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

(Fuente: líneas 839-907, sección "Orden sugerido de desarrollo".)

### 2026-07-20 — Revisión de consistencia: `comprobante` transversal y bloque Compras en data-model

Del listado de correcciones aplicadas en la revisión completa del proyecto:

> 8 tablas nuevas (30 en total): `medio_pago`, `pago` (sales);
> `comprobante` (nuevo módulo transversal `src/shared/models/` — sirve a
> sales/purchases/accounting, ningún módulo lo posee en exclusiva);
> `apertura_caja`, `custodia_efectivo`, `cierre_caja`, `arqueo` (nuevo
> módulo `src/modules/accounting/`, solo el ciclo de caja — plan de
> cuentas/asiento/periodo_contable siguen pendientes).

> Data-model: bloque Compras completo (caja chica, compra directa,
> evaluación de proveedor, requerimiento de activo), `stock_lote`
> (FEFO/FIFO implementable + bloqueo de vencidos con memorándum),
> `ajuste`, `apertura_caja`/`cierre_caja`/`arqueo` (caja ya no es módulo
> "futuro"), `flota`, `combo`, `plantilla`; `contrato` reubicado como

(Fuente: líneas 1063-1065 y 1095-1096, sección "Revisión de consistencia y
correcciones (2026-07-20)".)

### 2026-07-14 (plan original, previo al enfoque de slices verticales) — Orden de desarrollo de fases

Del plan de fases horizontales que quedó revertido el mismo 2026-07-14 en
favor de slices verticales por proceso de negocio (el detalle de entidades
ya relevado siguió siendo insumo válido):

> ### Fase de procesos (tras el modelado de BD)
>
> 1. `users`: auth (login PIN → JWT/refresh), RBAC, contexto de tenant, auditoría base.
> 2. Organización: grupo → empresa → marca → sucursal → almacén (vive en `users` o módulo `organization`).
> 3. `inventory`: artículos, stock por almacén, movimientos.
> 4. `purchases`: proveedores, OC, recepción → entrada a almacén central.
> 5. Solicitudes + transferencias central → local.
> 6. `sales`: PDV, recetas, descuento automático de insumos, pagos, Nubefact.
> 7. Producción, contabilidad, RRHH, resto de módulos.

(Fuente: líneas 1405-1413, cola del archivo — remanente del plan de fases
horizontales anterior al giro a slices verticales documentado en la línea 608.)

### 2026-07-25 (actualizado 2026-08-29, ADR-081) — Slice core de `purchases` y cola de pago en `accounting`

Fila F0 del módulo `purchases`:

> Módulo `purchases` | 🔶 slice core ✅ 2026-07-25 | CRUD de proveedores (natural liga a `persona`, jurídico con RUC propio) y ciclo de OC tipo `insumo` (crear → emitir → recibir → anular), con idempotencia y umbral de aprobación configurable. `purchases.compra_recibida` → inventory suma stock y recalcula `costo_promedio`. Conformidad de comprobante (`purchases.dar_conformidad`) registra el `comprobante` recibido y dispara `purchases.comprobante_conforme` → cola de pago en `accounting`. Migración `4ff85f833b29` aplicada. Diferido: ver Deuda técnica.

Fila F0 del módulo `accounting` (integración directa con `purchases` — cola
de pago a proveedor, eventos de OC/recepción/conformidad, IGV de compra):

> Módulo `accounting` | 🔶 slice core+tesorería ✅ 2026-07-25 | Libro contable núcleo: plan de cuentas (`cuenta_contable`), periodo (`periodo_contable`, abrir/cerrar), asiento manual (`asiento`/`asiento_linea`, cuadre RN-CTB-001, anulación por asiento inverso RN-CTB-002) y mapeo configurable evento→cuentas (`regla_asiento`) que alimenta la generación automática para 4 eventos operativos ya publicados en código (`purchases.oc_emitida`, `purchases.compra_recibida`, `sales.venta_confirmada`, `purchases.comprobante_conforme`). **Pago a proveedor** (PROC-CTB-003, `movimiento_dinero`): cola idempotente por comprobante (RN-CTB-008) → ejecutar con umbral configurable + permiso (RN-CTB-005) → asiento automático. Migraciones `5402d99333fa`+`cbf904a9fc1b` aplicadas. **Contabilidad peruana** (2026-08-29, ADR-081, **sin migración**): el plan de cuentas de fábrica pasa a ser el **PCGE** —Plan Contable General Empresarial 2019, el catálogo obligatorio en el Perú— en `domain/pcge.py`, sembrable por empresa con `POST /accounting/cuentas-contables/pcge` (idempotente, botón en Plan de cuentas). Vive en código y no en configuración porque no es una decisión de la empresa sino norma nacional, la misma para las tres empresas del grupo y para el contador externo; lo que sigue configurándose es qué cuenta usa cada evento. Cubre elementos 1-7 y 9 a nivel de rubro con las divisionarias de un restaurante (del 8 solo 87 y 88; el 0 queda fuera, ver deuda). **Los asientos automáticos dejan de ser de dos líneas**: `regla_asiento` no podía expresar ningún asiento peruano real —una venta gravada son tres líneas y una compra cinco contando el asiento de destino—, así que `domain/plantillas.py` trae el asiento oficial por evento (venta 1212/40111/7011, compra 6011/40111/4212 + 201/611, consumo de personal 625/201, merma y faltante 6599/201, pago 4212/1041) y `regla_asiento` pasa a ser el **override** que gana cuando la empresa lo configuró. El **IGV se desagrega** de lo que trae cada evento y **por diferencia contra el total** —redondear base e IGV por separado descuadra el asiento por un céntimo—, con tasa cero en Amazonía (Ley 27037) y sin escribir la línea en 0.00. Un asiento solo se imputa en cuentas de último nivel. **Estados financieros** (`application/estados_financieros.py`, `GET /accounting/reportes/*`, pantalla Contabilidad → Estados financieros): balance de comprobación, libro mayor, Estado de Situación Financiera y Estado de Resultados **por naturaleza** —el por función necesita los asientos de destino del elemento 9 contra la 79, que nadie genera, y saldría sin cuadrar—. Son consulta pura sobre `asiento_linea`, sin tabla de saldos: un saldo materializado es un segundo lugar donde vive la verdad. **Ninguna consulta filtra por `asiento.estado`**: el anulado y su reversión suman cero, y excluir el anulado restaría el hecho dos veces. El resultado se devuelve por líneas **y** leído del libro entero, con un `cuadra` que expone el descuadre en pantalla. **El IGV se elige y nace con el comprobante** (2026-08-29, misma ADR-081 enmendada, migración `dfb195b14433`): el régimen estaba cableado a `empresa.zona_tributaria` en **dos** sitios con la misma línea copiada —el asiento contable y el comprobante electrónico de `sales`—, así que no había dónde elegirlo y no había forma de que una operación puntual se apartara de él. Majambo vende exonerada por Amazonía y aun así **compra con IGV** a proveedores de fuera de la región: ese crédito fiscal no se registraba en ninguna parte. Ahora lo resuelve `src/shared/tributos.py`, único lugar del ERP que decide el régimen, con tres niveles —la casilla de la operación (`comprobante.gravado_igv`, nullable) → el default de la empresa (`empresa.config_fiscal["igv_por_defecto"]`, un select en Organización → Empresas; la columna JSONB ya existía y no la leía nadie) → su zona tributaria, que es el comportamiento histórico y por eso desplegar esto no cambia de régimen a ninguna empresa viva—. La exoneración de Amazonía depende de zona **y actividad**, así que el enum de zona solo no alcanzaba. **El IGV se reconoce con el comprobante**: la venta confirmada y la compra recibida asientan sin IGV y lo asientan `sales.comprobante_emitido` (7011/40111, débito fiscal — evento que `accounting` por fin consume, uno de los pendientes de la deuda) y `purchases.comprobante_conforme` (40111/4212, crédito fiscal). No es un rodeo: el crédito solo se toma con el comprobante válido y anotado, el débito nace con el emitido, y de paso el flag queda en una sola tabla en vez de repartido entre `venta` y `orden_compra` —que además se asientan antes de que el comprobante exista—. La casilla se marca donde alguien tiene el documento delante: un select de tres estados en el diálogo de cobro del PDV y un campo en la conformidad de compras. De paso se corrigió el payload de `sales.comprobante_emitido`, que mandaba `venta.total` en vez del importe de **su** grupo de cobro: con la cuenta dividida (RN-COM-018) habría reconocido el IGV una vez por comprobante sobre la venta entera. Con IGV exonerado los dos asientos nuevos quedan en cero y no se escriben, así que para Majambo el libro queda igual. Migración validada contra Postgres (`alembic check` sin drift). Tests: `tests/test_accounting_pcge.py`. Diferido: ver Deuda técnica.

(Fuente: líneas 23 y 26, tabla F0.)

### 2026-07-27 / 2026-08-02 / 2026-08-05 — Parámetros operativos configurables: umbral de OC, caja chica, suplente de OC

> ✅ 2026-07-27 **Mecanismo para los valores operativos configurables**
> (umbral de OC, margen de contribución mínimo,
> margen de error de ajuste, monto de caja chica, plazo de envío de
> comprobantes, rangos salariales): decidido con el usuario que **no son
> valores fijos** — se configuran en `parametro_empresa` por empresa, los
> gestiona Gerencia, y un cambio puede sustentarse en un acta
> (`decision_gerencial`) cuando amerite (no obligatorio para un ajuste
> rutinario). Ver ADR-014, `data-model.md` §8c, RN-GER-008 y
> `docs/gerencia/politica-gerencia.md#parámetros-operativos-configurables`.
> **Ampliado 2026-08-02** (ADR-014 Addendum, RN-GER-009): cada parámetro
> se configura **desde el módulo al que pertenece**, pero el cambio **no
> surte efecto hasta que Gerencia lo aprueba** en su sección de
> aprobaciones (aceptar / rechazar / modificar). Implementado: entidad,
> migración `a71c9f4b2e60`, endpoints `/api/v1/parametros[/{id}/aprobar|
> /rechazar]`, un permiso por módulo `<modulo>.proponer_parametro`.
> Lo que queda abierto por cada uno de los puntos de abajo ya **no es el
> mecanismo** (resuelto e implementado) sino que **el área proponga y
> Gerencia apruebe el valor real** — trabajo de configuración/negocio, no
> bloquea código:
> **Propuestos 2026-08-05** con su sustento en
> `docs/gerencia/propuesta-parametros-operativos.md` y cargados como
> `estado='propuesto'` (`python -m src.seeders.parametros`, idempotente):
> 13 filas esperando en `/gerencia/parametros`. Cada propuesta declara de
> dónde sale el número, **qué pasa si está mal** y cuándo revisarlo — un
> parámetro mal puesto no rompe nada, distorsiona una decisión diaria
> durante meses sin que nadie lo note.
> - 🔶 `purchases/oc_umbral` — propuesto S/ 2,000 (confirma el semilla).
>   **El de menor base**: no hay histórico de OC contra el cual calibrarlo.
>   Sigue abierto si hace falta un umbral separado para activos.
> - 🔶 `purchases/monto_caja_chica` — propuesto S/ 500 con reposición al
>   bajar de S/ 150.
>
> Quedan **fuera** de este mecanismo por ser decisión de rol, no de valor
> (resueltas 2026-08-05 con el usuario):
> - ✅ 2026-08-05 **El suplente de OC es otro administrador**, no el
>   encargado de turno: una OC sobre el umbral es una decisión de plata.
>   Consecuencia en código: se **retiró** `purchases.aprobar` del rol
>   `supervisor`, que lo tenía desde el slice inicial y contradecía esta
>   decisión. Revocado también en la BD dev — el seeder solo agrega.

(Fuente: líneas 380-408, 417-418 y 428-434, sección "Pendientes de decisión
(registro vivo)" — se omiten aquí, por no ser de `purchases`, las
propuestas de `sales/margen_minimo`, `sales/incentivo_meta_pct`,
`inventory/margen_error_ajuste`, `accounting/plazo_envio_comprobante` y
`rrhh/rango_salarial_<perfil>` que comparten el mismo mecanismo.)

### 2026-08-05 — BPMN de Compras v2.0 (los tres caminos)

> ✅ 2026-08-05 BPMN de las cuatro áreas nuevas, con sus PROC registrados
> en el maestro y su narrativa en `workflows.md` (el enfoque era *primero
> SOP, luego BPMN*, y los SOPs ya estaban estables):
> [...] **PROC-CMP-001 v2.0** Compras (los tres caminos: informal con caja chica,
> preferente sin cotización, estándar/activo con RFQ) [...]

(Fuente: línea 495, sección "Pendientes de decisión (registro vivo)" —
bullet compartido con PROC-RRH-001, PROC-COM-003 y PROC-INV-001 v0.2, que
no son de `purchases`.)

### 2026-08-29 — Parche compras/inventario: borrador de OC, selector de artículos, OC editable en borrador, compra directa

## Parche compras/inventario (2026-08-29)

Reporte del usuario: no se podía crear un borrador de OC, el selector de
artículos no mostraba todo el catálogo (se replicaba en compras), la OC era
100% inmutable incluso en borrador, y no había forma de registrar una compra
a partir de solo una factura (sin OC previa). Investigación con 3 agentes
Explore confirmó causa raíz de cada uno con evidencia de código; el
descuento de stock por venta (que también se reportó como roto) resultó
estar correctamente implementado y testeado — se le agregó visibilidad en
vez de tocar la lógica.

| # | Qué | Estado |
|---|---|---|
| 1 | Rol `comprador` sin `inventory.leer`: tumbaba la pantalla entera de nueva OC | ✅ 2026-08-29 |
| 2 | Selector de artículos truncado a 50 (paginación sin `page_size`), en inventario, OC e importador de recetas | ✅ 2026-08-29 |
| 3 | OC editable mientras está en `borrador` (`PATCH`); inmutable desde `emitida` como ya era | ✅ 2026-08-29 |
| 4 | Compra directa sin OC previa, reutilizando `orden_compra` (ADR-081) | ✅ 2026-08-29 |
| 5 | KPI de incidencias de inventario en el dashboard (el descuento de stock ya funcionaba y estaba testeado) | ✅ 2026-08-29 |
| 6 | Alerta de stock bajo en el PDV, sin bloquear la venta (`GET /carta` → `stock_bajo`) | ✅ 2026-08-29 |

Lo que **no** se hizo y quedó como deuda (`docs/roadmap/deuda/modulo-purchases.md`):
la reconciliación completa estilo Odoo 18 entre compras/inventario/
contabilidad (más allá de los eventos puntuales que ya existen) y la caja
chica que la compra directa todavía no usa para pagar.

(Fuente: líneas 164-187, sección "Parche compras/inventario (2026-08-29)".)

### 2026-08-30 — Parche 0.9.1: ciclo de la OC en pantalla y factura de proveedor completa (ADR-085)

> | 4 y 5 | Ciclo de la OC en pantalla y factura de proveedor completa (ADR-085) | ✅ 2026-08-30 |

(Fuente: línea 236, tabla del "Parche 0.9.1 — tercer turno de prueba en
staging (2026-08-30)"; el resto de la tabla — dashboard→BI, despacho del
PDV, stock/kardex, duración de sesión, cuenta contable heredada — no es de
`purchases`.)

### 2026-09-04 — Ola 2 de la auditoría: la pantalla de OC ya estaba gateada desde ADR-085

> | `fix/rbac-botones-resto` | #3 los botones de trabajadores, artículos y devoluciones (la OC ya estaba gateada desde ADR-085) | ✅ 2026-09-04 |

Nota tomada al planificar la Ola 2: `compras/ordenes-compra/[id]`
**ya está gateado** y es el modelo a copiar para los demás botones-403 de
la auditoría del 2026-08-20.

También en la tabla de la Ola 1 (2026-08-30, cerrada 2026-09-04):

> | 3 | «Reintentar emisión», «Nota de crédito» y «Anular» gateados por permiso | ✅ 2026-09-04 — el resto de los botones-403 (pagos, asientos, trabajadores, artículos, devoluciones) se cerró en la Ola 2; la OC ya estaba gateada desde ADR-085 |

(Fuente: línea 200, tabla "Auditoría del 2026-08-20 — Ola 1"; línea 277 y
línea 283 (paráfrasis), tabla y texto de la "Ola 2".)

## Fuentes

Rangos de línea de `ROADMAP.md` (versión de este worktree, 1413 líneas
totales) usados para este historial:

- Línea 12 — fila F0 "Especificaciones de módulos base".
- Línea 23 — fila F0 del módulo `purchases`.
- Línea 26 — fila F0 del módulo `accounting` (cola de pago a proveedor,
  eventos de `purchases`, IGV de compra).
- Líneas 164-187 — "Parche compras/inventario (2026-08-29)".
- Línea 200 — tabla "Auditoría del 2026-08-20 — Ola 1".
- Línea 236 — tabla "Parche 0.9.1 — tercer turno de prueba en staging (2026-08-30)".
- Línea 277 y 283 — bloques y texto de la "Ola 2" de la auditoría (2026-09-04).
- Líneas 380-408, 417-418, 428-434 — "Pendientes de decisión (registro vivo)":
  mecanismo de parámetros operativos, `purchases/oc_umbral`,
  `purchases/monto_caja_chica`, suplente de OC.
- Línea 495 — BPMN PROC-CMP-001 v2.0, dentro de "Pendientes de decisión (registro vivo)".
- Línea 599 — índice de Deuda técnica, fila del módulo `purchases`
  (no se tocó `docs/roadmap/deuda/modulo-purchases.md`, solo se referencia).
- Líneas 839-907 — sección "Área Compras — proveedores, cotización, OC,
  recepción y pago (2026-07-19)", dentro de "Orden sugerido de desarrollo".
- Líneas 1063-1065 y 1095-1096 — "Revisión de consistencia y correcciones
  (2026-07-20)".
- Líneas 1405-1413 — cola del archivo, plan original de fases (2026-07-14,
  revertido el mismo día en favor de slices verticales, línea 608).

Secciones revisadas y descartadas por no aportar contenido específico de
`purchases` más allá de una mención de paso: línea 40 (fila F0 "Supervisión,
CRM, tesorería, activos, proyectos, BI/reportes" — solo nombra que los
activos "se compran en `purchases`"), línea 43 (integraciones Google Maps —
`proveedor` solo aparece como uno de los seis modelos con `UbicacionMixin`),
línea 38 (Contabilidad: procesos y plantillas — el SOP de pago a proveedor
es un proceso de `accounting`), y las menciones de "Compras" en la sección
de Marketing (líneas 1294-1337, sobre el material comprado para campañas,
no sobre el módulo `purchases`).
