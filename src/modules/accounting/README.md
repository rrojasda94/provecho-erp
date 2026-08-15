# Módulo `accounting` — Contabilidad

> Área de negocio documentada en [docs/contabilidad/](../../../docs/contabilidad/README.md).
> El área concentra hoy **tesorería, finanzas y registro contable** en un solo
> responsable, bajo supervisión de Gerencia (RN-CTB-004); este módulo es su
> soporte de software.

## Objetivo

Registrar asientos contables generados por los eventos de los módulos
operativos (ventas, compras, inventario), permitir asientos manuales
controlados y dar soporte a **tesorería** (ciclo de caja, pago a proveedor,
conciliación bancaria, arqueos) y a **finanzas** (flujo de caja, insumos de
presupuesto).

## Entidades

`cuenta_contable` (plan de cuentas), `asiento`, `asiento_linea` (debe/haber),
`periodo_contable`, `regla_asiento` (mapeo evento→cuentas),
`movimiento_dinero` (tesorería — pago a proveedor). Detalle en
`docs/architecture/data-model.md` §8.

**Estado de implementación (2026-07-25):** libro contable núcleo construido
— `cuenta_contable` (plan de cuentas), `periodo_contable` (abrir/cerrar),
`asiento`/`asiento_linea` (manual con permiso `accounting.asiento_manual`,
cuadre RN-CTB-001, anulación por asiento inverso RN-CTB-002) y
`regla_asiento` (mapeo configurable evento→cuentas que alimenta la
generación automática, `application/listeners.py`). Cubre hoy 6 eventos
operativos: `purchases.oc_emitida`, `purchases.compra_recibida`,
`sales.venta_confirmada`, `purchases.comprobante_conforme`,
`inventory.transferencia_recibida` —que **solo asienta cuando el traslado
llegó con faltante**: mover mercadería entre almacenes de la misma empresa
no mueve resultado, lo que sí es hecho contable es lo que salió y no
llegó— y —desde 2026-08-09— `inventory.consumo_personal_valorizado`, la
comida del personal llevada a **gasto de alimentación de personal** y no a
costo de ventas (ADR-034); `inventory.consumo_personal_reversado` anula ese
asiento si el consumo se anula. El monto viene valorizado en el evento (el
costo es dato de `inventory`). El resto de eventos listados abajo quedan pendientes de
que esos módulos los publiquen (deuda técnica, ver ROADMAP).

**Pago a proveedor (PROC-CTB-003, mismo día):** `movimiento_dinero`
(tesorería, genérico egreso/ingreso) — `purchases.comprobante_conforme`
encola un pago `pendiente` (`application/pagos.registrar_pago`, idempotente
por `comprobante_id`, RN-CTB-008); `application/pagos.ejecutar_pago` exige
permiso `accounting.pago_gestionar`, revisa el umbral configurable
(`parametro_empresa`, código `pago_umbral`, RN-CTB-005 — sobre el umbral
exige además `accounting.pago_aprobar`) y genera el asiento vía
`regla_asiento` (evento `accounting.pago_ejecutado`; sin mapeo configurado,
el pago igual se ejecuta y el asiento se omite). `rechazar_pago` cierra la
cola sin ejecutar. Detracción SPOT se calcula (`monto_detraccion`) pero el
asiento no la desglosa en cuenta propia — ver deuda técnica en ROADMAP.

Ciclo de caja (PROC-CTB-001/002) ya existía — `apertura_caja`,
`custodia_efectivo`, `cierre_caja`, `arqueo`
(`src/modules/accounting/infrastructure/models/`), dependencia del slice de
Cobro (PROC-COM-002), aún sin conectar al libro contable (no genera asiento
todavía). `comprobante` NO vive aquí — es transversal, está en
`src/shared/models/`.

## Casos de uso

- Mantener plan de cuentas.
- Generación automática de asientos desde eventos (venta, compra, ajuste de inventario).
- Asientos manuales con permiso `accounting.asiento_manual`.
- Cierre de periodo (bloquea modificaciones).
- Pago a proveedor: registrar (cola) → ejecutar (permiso + umbral) →
  asiento automático, o rechazar.

## Reglas

- Todo asiento cuadra: suma debe = suma haber. Validación en dominio.
- Asientos de periodo cerrado son inmutables.
- Ninguna eliminación física: reversión mediante asiento inverso.

## Flujo

Evento operativo → regla de mapeo contable → asiento generado → mayor/balances.

## Relaciones

- Escucha: `sales.venta_confirmada`, `sales.pago_registrado`,
  `sales.comprobante_emitido`, `purchases.oc_emitida` (provisiona),
  `purchases.compra_recibida`, `purchases.comprobante_conforme` (decide y
  ejecuta el pago según condición del proveedor),
  `purchases.caja_chica_rendida` (concilia y repone fondo),
  `inventory.transferencia_recibida`, `inventory.merma_registrada`
  (reporte de pérdidas), `inventory.ajuste_fuera_margen` (alerta de
  auditoría).
- Publica: `accounting.asiento_generado`, `accounting.periodo_cerrado`,
  `accounting.apertura_caja_registrada`, `accounting.cierre_caja_registrado`,
  `accounting.cierre_caja_irregular`, `accounting.pago_ejecutado`,
  `accounting.pago_requiere_aprobacion`, `accounting.arqueo_registrado`
  (ver [events.md](../../../docs/architecture/events.md)).

## Tesorería y finanzas (procesos del área)

Además del registro contable, el módulo soporta los procesos de tesorería/
finanzas documentados en el área:

- **Pago a proveedor** (PROC-CTB-003, implementado 2026-07-25): ejecuta el
  pago con comprobante conforme (RN-CMP-014), umbral de aprobación de
  Gerencia (RN-CTB-005), detracción SPOT (calculada, sin desglose contable
  propio aún) e idempotencia contra doble pago (RN-CTB-008).
- **Ciclo de caja** (PROC-CTB-002/001, slice mínimo 2026-07-26 con ADR-012,
  **completado 2026-08-04 con ADR-025**, **enmendado 2026-08-15 con
  ADR-048**): `abrir_caja`/`cerrar_caja`/
  `reabrir_cierre`/`entregar_custodia`/`registrar_arqueo` en
  `application/caja.py`, inventario de terminales en `application/pos.py`.
  - El cierre **reconcilia de verdad**: `esperado = apertura + efectivo
    cobrado desde la apertura + ingresos − retiros del turno`, el cobrado
    vía el contrato público de `sales` (`total_efectivo_cobrado` —
    `accounting` no importa el dominio de `sales`).
  - **Y cuadra tarjetas** (RN-POS-004, 2026-08-04): exige el reporte de lote
    de cada POS que abrió operativo —uno averiado no cobró nada— y lo
    contrasta con `total_tarjeta_cobrado`. `descuadre_monto` sigue siendo el
    del cajón; el de tarjetas va en `montos_esperados`/`montos_reales` y
    cualquiera de los dos deja el cierre irregular.
  - **El monto sale del conteo por denominación** (RN-POS-003/007), no de
    un número tecleado; en la apertura la diferencia contra lo declarado
    por el encargado se calcula y **no bloquea abrir** (RN-POS-011).
  - **El turno lo abre y lo cierra el cajero solo** (RN-MDP-008, ADR-048):
    basta `accounting.caja_operar`, sin elevación de PIN. Lo que prueba
    cuánto había es el conteo, no una firma — y pedir que un encargado
    viniera a firmar cada apertura terminaba con su sesión abierta en la
    caja todo el turno.
  - **Cada entrega de efectivo la firma quien recibe con su PIN**
    (RN-MDP-002, permiso `accounting.caja_relevar`): el cierre deja la plata
    `en_caja` a nombre del cajero, y de ahí `custodia_efectivo` avanza
    `en_caja → en_supervisor → en_contabilidad | disponible`, un tramo por
    firma. `POST /cajas/custodias/{id}/entregar` es el **único** punto del
    ciclo que pide elevación. El cajero no puede firmar que recibió su
    propia plata: no tiene `caja_relevar`, y eso alcanza — no hace falta un
    candado de dominio contra relevarse a sí mismo.
  - **Un cierre con faltante se corrige, no se reescribe**: reapertura con
    motivo y autorizador en `cierre_caja.correcciones` (RN-MDP-005). Vale
    mientras el efectivo siga en el local, y desde ADR-048 eso incluye el
    caso que antes era inalcanzable: recontar con la plata todavía en el
    cajón.
  - **No se cobra sin caja abierta**: `sales.registrar_pago` pregunta por
    `queries_publicas.hay_caja_abierta`. Excepción única, el replay del
    push del hub (ADR-009), porque el cobro ya ocurrió en la sucursal.
  - Permisos: `accounting.caja_operar` (`cajero`, `supervisor`),
    `accounting.caja_relevar` y `accounting.caja_reabrir`
    (`supervisor`/`contador`), `accounting.pos_administrar` (`contador`),
    `accounting.arqueo_registrar` (`supervisor`/`contador`).
  - **`custodia` y `descuadre_atribucion` son enums, no texto libre**:
    `custodia` es *a dónde va el efectivo* (`local_caja_fuerte` /
    `traslado_contabilidad`) —a quién se le entregó lo prueba la firma del
    tramo de custodia— y `descuadre_atribucion` es `cajero` / `encargado` /
    `tercero_reportado`. Los dos se validan con `pattern` en el schema: sin
    eso, un texto libre se escribía sin protestar y dejaba la fila
    **ilegible**, porque la lectura reventaba después al mapear el enum.
  - **Turnos cerrados**: `GET /accounting/cajas/turnos` devuelve el cierre,
    el descuadre y el tramo de custodia en una sola consulta — es la lista
    con la que trabaja contabilidad para reabrir un cierre o recibir el
    efectivo, y traerlos por separado era un N+1 por turno.
  - **Quién está a cargo del local**: `queries_publicas.encargado_de_turno`
    salía del `relevo_encargado_id` de la caja abierta. Con ADR-048 esa
    columna queda en NULL en toda apertura nueva, así que devuelve `None` y
    `reports` cae en su respaldo por rol (ADR-036). Sigue leyendo bien las
    aperturas anteriores. Recuperarlo de verdad necesita una fuente propia
    —un turno de personal, no la caja— y está anotado como deuda.
  - **Fuera del slice**: el turno de caja no se replica al hub, y
    RN-POS-012/013 (prever sencillo, dedicación exclusiva durante el
    conteo) son organizativas — viven en el SOP, no en código.
- **Conciliación bancaria** (PROC-CTB-004): cuadra movimientos vs. extracto;
  visada por Gerencia, requisito de cierre de periodo (RN-CTB-006).
- **Flujo de caja** y **activo fijo/depreciación**: pendientes de slice
  dedicado (PROC-CTB-007/010, propuestos).

## Contrato API — caja

| Método | Ruta | Permiso |
|--------|------|---------|
| POST | `/accounting/cajas/apertura` | `accounting.caja_operar` — sin PIN (RN-MDP-008) |
| POST | `/accounting/cajas/apertura/{id}/cierre` | `accounting.caja_operar` — sin PIN (RN-MDP-008) |
| POST | `/accounting/cajas/apertura/{id}/movimientos` | `accounting.caja_operar` (+ PIN `caja_retirar` si es retiro) |
| GET | `/accounting/cajas/apertura/{id}/movimientos` | `accounting.leer` |
| GET | `/accounting/cajas/apertura/{id}/custodia` | `accounting.leer` |
| POST | `/accounting/cajas/custodias/{id}/entregar` | `accounting.caja_operar` + PIN `caja_relevar` — la única firma del ciclo |
| POST | `/accounting/cajas/cierres/{id}/reabrir` | `accounting.caja_operar` + PIN `caja_reabrir` |
| GET | `/accounting/cajas/abiertas?empresa_id=` | `accounting.leer` |
| GET | `/accounting/cajas/turnos?desde=&hasta=` | `accounting.leer` |
| GET | `/accounting/cajas/cierres/{id}` | `accounting.leer` — el turno con montos esperados vs. contados y reportes de POS; a donde lleva `cierre_caja_irregular` (ADR-036) |
| GET | `/accounting/pagos-proveedor/{id}` | `accounting.leer` — a donde lleva `pago_requiere_aprobacion` |
| POST | `/accounting/arqueos` | `accounting.arqueo_registrar` |
| POST | `/accounting/pos-tarjeta` | `accounting.pos_administrar` |
| GET | `/accounting/pos-tarjeta?sucursal_id=` | `accounting.leer` |
| PATCH | `/accounting/pos-tarjeta/{id}` | `accounting.pos_administrar` |

"+ PIN" = token de `POST /auth/autorizar` en el cuerpo (`autorizacion`): la
sesión del cajero no alcanza, tiene que firmar quien recibe o autoriza
(RN-MDP-002, RN-AUD-005). Se pide donde la plata cambia de manos o donde se
corrige evidencia ya escrita — **no** para abrir ni cerrar el turno, que son
actos del cajero (RN-MDP-008, ADR-048).
