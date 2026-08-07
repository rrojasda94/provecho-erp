# Flujos operativos

Cada proceso lleva código y versión — nomenclatura y reglas en
[process-nomenclature.md](process-nomenclature.md). Registro maestro con
estado de cada uno: [tabla](process-nomenclature.md#registro-maestro).

## Compras

`PROC-CMP-001` · v2.0 · Vigente

v2.0 (2026-07-19/20): el flujo único proveedor→OC→recepción se reemplaza
por **tres caminos de compra** según proveedor y tipo (decisión del
usuario tras revisar el flujo real); **Contabilidad ejecuta el pago**,
Compras solo sustenta el comprobante conforme. Detalle narrativo y SOPs:
[docs/compras/README.md](../compras/README.md) y
[docs/diagrams/Procesos/Compras/](../diagrams/Procesos/Compras/).

```mermaid
flowchart TB
    N[Necesidad / requerimiento] --> T{Tipo de compra}
    T -->|Menor, proveedor informal| CD[Compra directa con caja chica] --> RD[Rendición semanal] --> CTB
    T -->|Proveedor preferente recurrente| OCS[OC directa sin cotización] --> R
    T -->|Estándar o activo/equipamiento| RFQ[Cotización comparativa RFQ] --> AP{¿Sobre umbral / activo?}
    AP -->|Sí| VAL[Aprobación admin / área + gerencia] --> OC[Orden de Compra]
    AP -->|No| OC
    OCS -.-> OC
    OC --> R[Recepción en Almacén Central] --> CF[Conformidad de comprobante] --> CTB[Contabilidad ejecuta pago]
```

## Producción

`PROC-PRD-001` · v1.0 · Borrador (spec completa; sin operación real —
primera cocina de producción planeada 2027, ver
[docs/produccion/README.md](../produccion/README.md))

```mermaid
flowchart TB
    PL[Plan de producción: cronograma fijo] --> OP[Orden de producción]
    NEC[Necesidad urgente Almacén Central, RN-PRD-007] -.ajuste.-> OP
    OP --> CONS[Consumo de insumos/subrecetas] --> ELAB[Elaboración según receta]
    ELAB --> CC{Control de calidad}
    CC -->|Conforme| EMP[Empacado y etiquetado] --> AP[Almacén de producción] --> DESP[Despacho a Almacén Central]
    CC -->|No conforme, corregible| RPR[Reproceso] --> CC
    CC -->|No conforme, no corregible| DESC[Desecho con evidencia] --> ESC[Reporte de escalamiento]
    RPR -.también.-> ESC
```

Cronograma fijo por tipo de receta/proceso (evita contaminación cruzada,
RN-PRD-012) más ajuste por necesidad de Almacén Central (RN-PRD-011).
Toda orden pasa control de calidad antes de despachar (RN-PRD-013); no
conformidad —corregida o desechada— siempre genera reporte de
escalamiento, con evidencia de destrucción si termina en desecho
(RN-PRD-014/015). Detalle narrativo, SOPs y plantillas:
[docs/produccion/README.md](../produccion/README.md) y
[docs/diagrams/Procesos/Produccion/](../diagrams/Procesos/Produccion/).

Producción también da soporte técnico a I+D+i/Comercial para viabilidad
de nuevo producto (RN-PRD-017) y ejecuta su propio conteo cíclico de
inventario (RN-PRD-016) — ambos fuera de este diagrama por no ser parte
del flujo de una orden de producción.

Dos controles automáticos transversales al flujo, sin mano humana que
transcriba: el ERP calcula el costo real de cada orden (insumos + mano de
obra, con el desperdicio por insumo/tipo contrastado contra lo esperado
en la receta, RN-PRD-018), y el checklist de turno bloquea la cocina y
alerta a Gerencia de inmediato si un equipo de frío queda fuera de rango
(RN-CDP-005).

## Definición del presupuesto anual

`PROC-GER-001` · v1.0 · Borrador (spec del proceso; límites de gasto por
área aún `[[ COMPLETAR ]]`, ver
[docs/gerencia/README.md](../gerencia/README.md))

```mermaid
flowchart TB
    CONV[Gerencia convoca reunión anual + marco financiero] --> PROP[Cada área presenta su propuesta]
    PROP --> REV[Gerencia revisa vs. proyección y prioridades]
    REV --> DES[Gerencia designa presupuesto por área, en acta]
    DES --> LIM[Gerencia fija límite de gasto autónomo por área]
    LIM --> REG[Presupuesto y límites registrados en el ERP]
    REG --> EJE{Gasto del año}
    EJE -->|Dentro de presupuesto y bajo límite| AUT[Área ejecuta autónoma]
    EJE -->|Sobre límite o fuera de presupuesto| GER[Aprobación puntual de Gerencia]
```

Cada área presenta su propuesta una vez al año; Gerencia designa el
presupuesto y fija el límite de gasto autónomo por área (RN-GER-007) —
dentro del presupuesto y bajo el límite el área ejecuta sin aprobación
caso por caso; sobre el límite o fuera de lo presupuestado, aprueba
Gerencia (matriz de aprobaciones, RN-GER-003). Detalle:
[docs/diagrams/Procesos/Gerencia/Presupuesto/](../diagrams/Procesos/Gerencia/Presupuesto/).

## Campaña de marketing

`PROC-MKT-001` · v1.0 · Borrador (spec completa; sin ejecución real aún —
área Marketing recién documentada, ver
[docs/marketing/README.md](../marketing/README.md))

```mermaid
flowchart TB
    OBJ[Objetivo con Comercial si es impulso de venta] --> BR[Brief: público, canal, mensaje, presupuesto, KPI]
    BR --> AP{¿Presupuesto sobre umbral?}
    AP -->|Sí| GER[Aprobación de Gerencia] --> NAM
    AP -->|No| NAM[Naming + uso de marca validados]
    NAM --> MAT[Material vía Compras + agencia evaluada]
    MAT --> LAN[Lanzamiento en canal]
    LAN --> LEAD[Leads registrados] --> ATR[Atribución lead→venta con Comercial/sales]
    ATR --> CIE[Cierre: medir resultado vs. objetivo]
```

Marketing atrae el lead, Comercial cierra la venta e investiga la
oportunidad (RN-MKT-003). Toda campaña sale con brief aprobado; el
contenido es pertinente a la marca, no viral por viral (RN-MKT-002); el
naming y el uso de marca se validan antes (RN-MKT-001/007); el material se
compra vía Compras y se **verifica implementado** en sucursal, no solo
enviado (RN-MKT-004/005). Detalle narrativo, SOPs y plantillas:
[docs/marketing/README.md](../marketing/README.md) y
[docs/diagrams/Procesos/Marketing/](../diagrams/Procesos/Marketing/).

## Abastecimiento de locales

`PROC-INV-001` · v0.2 · Borrador

Diagrama BPMN completo:
[PROC-INV-001-v0.2.bpmn](../diagrams/Procesos/Logistica-Almacen/PROC-INV-001-v0.2.bpmn).

```mermaid
flowchart LR
    CT[Conteo de fin de jornada: cocina + atencion al cliente] --> VD{Se desvia del margen de error? RN-INV-015}
    VD -- si --> AL[Alerta / auditoria]
    VD -- no --> VS[Encargado/Supervisor valida insumos principales]
    AL --> VS
    VS --> SUG[ERP calcula sugerido de requerimiento, RN-INV-013]
    SUG --> A{Supervisor aprueba/ajusta cantidad?}
    A -- si --> ENV[Envia Requerimiento a Almacen Central]
    A -- no --> X[Ajusta cantidad sugerida] --> A
    ENV --> PK[Picking] --> PA[Packing] --> S[Salida/Transporte]
    S --> T[Transferencia en transito] --> RC[Recepcion en local]
    RC --> UP[Stock del local sube]
```

> Borrador (se revisa/corrige en otra sesión): detalle de conteo en
> sucursal ya está a este nivel; picking/packing/transporte en almacén
> central todavía no.
>
> 1. El conteo de fin de jornada lo hacen Personal de cocina y Personal de
>    atención al cliente, usando balanza, lector QR (si aplica) y el ERP.
>    Empieza al menos 10 minutos antes del cierre de puertas, para dejar
>    todo listo.
> 2. Insumos refrigerados/congelados a medio usar: se pesan en balanza
>    descontando el peso del envase. Insumos aún sellados de almacén
>    central: se escanean por QR o se suma directamente el peso indicado al
>    stock. En ambos casos, no más de 5 minutos fuera de refrigeración.
> 3. Insumos que no se descuentan automáticamente del stock por venta
>    (limpieza, menaje, servilletas, bolsas, etc.) se cuentan aparte, con la
>    periodicidad que le corresponda según la lista de inventario a la que
>    pertenecen (RN-INV-007).
> 4. El conteo se ingresa al ERP → genera un borrador.
> 5. El sistema emite una alerta si el stock declarado se desvía del margen
>    de error configurado (RN-INV-015) → dispara auditoría.
> 6. El Encargado/Supervisor valida el conteo, verificando en persona los
>    insumos principales o más costosos antes de continuar — control
>    cruzado sobre lo que declaró el personal.
> 7. El ERP calcula si hay stock suficiente o si hace falta programar un
>    envío, según el punto de reorden (RN-INV-013).
> 8. Se genera automáticamente un borrador de solicitud de requerimiento
>    (editable); el Encargado/Supervisor puede pedir una cantidad menor a
>    la sugerida si evalúa que no hace falta.
> 9. El Encargado/Supervisor aprueba y envía el Requerimiento a Almacén
>    Central vía ERP.
> 10. Almacén central recibe el pedido y arma el picking.
> 11. En la jornada/turno siguiente, el repartidor entrega los productos en
>     el orden correspondiente.
> 12. Devoluciones o productos no solicitados se fotografían, se suben al
>     ERP, y se devuelven.
> 13. Se verifican montos y se firma.
> 14. Se registra el aumento de stock del almacén de sucursal.

SOPs derivados de este proceso:
[conteo de insumos y envío de requerimiento](../diagrams/Procesos/Logistica-Almacen/Abastecimiento-Locales/conteo-insumos-requerimiento.md),
[picking y despacho en almacén central](../diagrams/Procesos/Logistica-Almacen/Abastecimiento-Locales/picking-despacho-almacen-central.md),
[recepción y devoluciones en local](../diagrams/Procesos/Logistica-Almacen/Abastecimiento-Locales/recepcion-requerimiento-devoluciones.md).

## Venta

`PROC-COM-001` · v1.0 · Vigente

**Alcance (2026-07-14, decisión del usuario): Venta termina con el envío
del pedido a cocina y el cobro.** Preparación, emplatado/empaquetado,
despacho y entrega al cliente NO son parte de Venta: desde 2026-07-27 son
un proceso propio, [PROC-OPE-002 Cumplimiento de pedido](#cumplimiento-de-pedido),
del área Operaciones. Venta lo dispara con `sales.venta_confirmada` y no
espera su resultado.

```mermaid
flowchart LR
    PC[Producto comercial] --> RE[Receta] --> DES[Descuenta insumos del almacén del local]
    V[Venta confirmada] --> OP[Orden de Pedido enviada a cocina]
    V --> PG[Pago: efectivo / Izipay] --> CO[Comprobante electrónico]
    V -. evento sales.venta_confirmada .-> DES
```

Canales: Web (autoatención), Central de Pedidos (llamada/WhatsApp),
Sucursal (mesa/takeout/delivery presencial). Detalle paso a paso de cada
uno, con abandono y resolución: [use-cases.md](use-cases.md) CU-COM-001/002/003.

```mermaid
flowchart LR
    subgraph web ["Web"]
        w1[Ingresa o se registra] --> w2[Elige productos] --> w3[Carrito]
        w3 --> w4[Modalidad: recojo o delivery] --> w5[Upsell] --> w6[Pasarela de pago]
    end
    subgraph cp ["Central de Pedidos"]
        c1[Bienvenida] --> c2[Cliente registrado?] --> c3[Delivery o recojo] --> c4[Carta o pedido directo]
        c4 --> c5[Upsell] --> c6[Repite pedido] --> c7[Presenta monto] --> c8[Medio de pago]
    end
    subgraph suc ["Sucursal"]
        s1[Bienvenida] --> s2[Tipo de pedido] --> s3[Cliente registrado?] --> s4[Carta / pantalla]
        s4 --> s5[Arma carrito] --> s6[Upsell] --> s7[Repite pedido] --> s8[Cobra]
    end
    w6 --> FIN[Envío a cocina + comprobante]
    c8 --> FIN
    s8 --> FIN
```

**Pendiente, fuera del alcance de Venta**: escalamiento de reclamos
post-venta, monitoreo del pedido ya en cocina/camino, manejo de errores
técnicos/demoras del sistema. Desistimiento del cliente durante la toma
del pedido SÍ está cubierto (con resolución) — ver RN-COM-010/011/012 y
`sales.carrito_abandonado` (RN-COM-013).

### Qué pasa después de Venta

Preparación, emplatado/empaquetado, despacho y entrega viven en
[PROC-OPE-002 Cumplimiento de pedido](#cumplimiento-de-pedido). Ahí también
se resuelven la encuesta de satisfacción (RN-COM-007) y el pago al
finalizar en mesa (RN-POS-005).

## Cobro y Emisión de Comprobante de Pago

`PROC-COM-002` · v1.0 · Vigente

Detalle del paso "cobro" dentro de Venta (RN-COM-005, [PROC-COM-001](#venta)).
Empieza en uno de dos momentos: cobro inmediato al confirmar el pedido
(billetera digital, link de pago, transferencia, o efectivo/POS solo si el
cliente está en sucursal) o cobro post-entrega (billetera digital,
transferencia, tarjeta o efectivo, cobrado por el repartidor). Termina con
la entrega del comprobante de pago al cliente. Diagrama BPMN completo:
[PROC-COM-002-v1.0.bpmn](../diagrams/Procesos/Comercial/PROC-COM-002-v1.0.bpmn).

El cajero (Atención al Cliente) es responsable del proceso en todo momento:
si el cobro físico lo ejecuta otro trabajador (repartidor u otro personal),
el cajero debe exigir el monto completo y reportar de inmediato cualquier
falla — de no reportarla, la responsabilidad recae en él.

```mermaid
flowchart LR
    subgraph cobro ["Cobro"]
        m1[Medio de pago] -->|Efectivo| v1[Verificar billetes: UV / marcador / contraluz] --> v2{Monto exacto?}
        v2 -->|No| vu[Calcular y entregar vuelto optimo] --> ok[Cobro conforme]
        v2 -->|Si| ok
        m1 -->|Tarjeta / billetera / link / transferencia| d1[Verificar monto en dispositivo] --> d2[Registrar en POS: voucher] --> d3{Transaccion exitosa?}
        d3 -->|Si| ok
        d3 -->|No| rep[Reporte + mostrar al cliente] -->|Se opone: insistir garantia 48h| m1
        rep -->|Acepta| m1
    end
    ok --> mc{Cobro post-entrega por repartidor?}
    mc -->|Si| vc{Cajero verifica monto completo} -->|Incompleto: reporta falla y exige| vc
    mc -->|No| sal[Pago saldado]
    vc -->|Completo| sal
    sal --> lote[Ingresa lote/referencia si tarjeta o billetera digital] --> comp{Boleta o factura?}
    comp -->|Boleta| dni{Da DNI?}
    dni -->|Si| bd[Boleta con DNI] --> ent
    dni -->|No| bs[Boleta simple] --> ent
    comp -->|Factura| ruc[Solicita RUC] --> fa[Factura con RUC] --> ent
    ent{Fisico o digital?} -->|Fisico| ef[Entrega fisica] --> FIN[Comprobante entregado]
    ent -->|Digital| ed[Envio por mensajeria] --> FIN
```

Garantía ante error de cobro con tarjeta/billetera digital: si el cliente
detecta un doble cobro en las siguientes 48 horas, la empresa lo ayuda a
reclamar ante el banco; si la empresa lo detecta primero, el monto se
retorna al cliente.

## Cumplimiento de pedido

`PROC-OPE-002` · v1.0 · Vigente

Toma el relevo exactamente donde termina Venta (RN-COM-005). Empieza
cuando la Orden de Pedido confirmada llega al KDS de la sucursal
(`sales.venta_confirmada`) y termina cuando el pedido está en manos del
cliente (`sales.venta_entregada`). Área dueña: Operaciones — cruza cocina
de sucursal, atención al cliente y reparto, sin pertenecer a una sola.
Reglas: RN-CUP-001 a RN-CUP-012. Casos de uso por modalidad:
[use-cases.md](use-cases.md) CU-OPE-001/002/003.

**Es UN proceso con dos etapas, no dos procesos** (decisión 2026-07-27):
entra una Orden de Pedido y sale un pedido entregado — un solo resultado,
un solo registro (`venta_item.estado_preparacion`), sin artefacto de
traspaso entre cocina y despacho. Las pantallas KDS de tipo `preparacion`
y `despacho` son vistas distintas del mismo avance, no procesos distintos.
Si el reparto a domicilio llega a tener ruteo, flota propia y liquidación
de repartidores, se separa entonces como versión MAYOR.

> **No confundir con `PROC-PRD-001` (Producción)**: ese es la cocina de
> producción central (subrecetas y lotes, 2027). Acá se prepara el pedido
> de un cliente en la cocina de una sucursal.

```mermaid
flowchart LR
    OP[Orden de Pedido confirmada] --> KDS[Pantallas KDS por estacion]
    KDS --> PR[Prepara segun receta y modificadores]
    PR --> LI[Item listo] --> TODO{Todos los items listos?}
    TODO -->|No| KDS
    TODO -->|Si| VER[Verifica pedido completo contra comanda]
    VER --> MOD{Modalidad}
    MOD -->|Mesa| EMP[Emplata] --> LLE[Lleva a la mesa] --> ENT
    MOD -->|Takeout| EPT[Empaca] --> LLA[Llama por numero de orden] --> ENT
    MOD -->|Delivery| EPD[Empaca] --> ASI[Asigna repartidor propio o plataforma] --> RUT[Sale a ruta] --> ENT
    ENT[Entrega al cliente] --> COB{Cobro pendiente?}
    COB -->|Si| PC["Cobro post-entrega o al finalizar (PROC-COM-002)"] --> FIN
    COB -->|No| FIN[Pedido entregado]
```

**Etapa 1 — Preparación.** El KDS muestra la Orden de Pedido ya enviada
(no el Carrito); cada estación ve solo los ítems de las categorías que le
tocan y los avanza `pendiente → en_preparacion → listo`, sin retroceso
(RN-CUP-002). El avance es único y compartido: todas las pantallas leen el
mismo estado. Cuando todos los ítems están listos se emite
`sales.pedido_listo`.

**Etapa 2 — Despacho y entrega.** Antes de entregar, quien despacha
verifica el pedido completo contra la comanda (RN-CUP-004) — control de
salida, último punto donde un error todavía es barato. Luego:

- **Mesa**: emplatado y entrega en mesa. La entrega habilita el cierre del
  servicio y, con él, el pago al finalizar el consumo (RN-POS-005,
  RN-CUP-009).
- **Takeout**: empaquetado y entrega en mostrador contra número de orden.
- **Delivery**: empaquetado, asignación de repartidor —propio o de
  plataforma externa (RN-PER-003)— y entrega en el domicilio. Si el cobro
  es contra entrega, lo ejecuta quien entrega y responde por el monto ante
  el cajero (PROC-COM-002, RN-MDP-005).

Emplatado (mesa) o empaquetado (takeout/delivery) consumen el `empaque`
que corresponda según modalidad (RN-EMP-003).

**Excepciones** (detalle en los CU): cliente ausente o dirección errada en
delivery, pedido no recogido en takeout, producto rechazado en la entrega
(reproceso o devolución), y anulación posterior al envío a cocina.

**Después de la entrega**: `sales.venta_entregada` habilita a Marketing a
seleccionar al cliente para la encuesta de satisfacción — selectiva, nunca
automática para toda venta (RN-COM-007) — que emite `marketing.encuesta_enviada`.

## Apertura de sucursal

`PROC-OPE-001` · v1.0 · Vigente

Empieza cuando el encargado de tienda o el supervisor llega a la sucursal,
al menos 45 minutos antes de la hora de apertura al público. Termina con
la sucursal abierta al público (cortinas levantadas, letrero "Abierto").
Reglas: RN-SUC-006 a RN-SUC-012, RN-PER-006. Detalle completo del paso
"apertura de caja": [PROC-CTB-002](#apertura-de-caja). Detalle de la
recepción del pedido de almacén central: pasos 6-9 de
[PROC-INV-001](#abastecimiento-de-locales). Diagrama BPMN completo:
[PROC-OPE-001-v1.0.bpmn](../diagrams/Procesos/Operaciones/PROC-OPE-001-v1.0.bpmn).

```mermaid
flowchart LR
    subgraph enc ["Encargado de tienda / Supervisor"]
        e1[Abre la puerta y desactiva la alarma] --> e2[Marca su entrada, enciende luces ambientales]
        e2 --> e3{Checklist de apertura: agua, banos, plagas, frios, gas - meta 5 min}
        e3 --> e4[Espera el pedido de almacen central] --> e5[Recepciona, cuenta, pesa e ingresa al sistema]
    end
    subgraph ate ["Personal de Atencion al Cliente"]
        a1[Higiene + marca entrada] --> a2[Checklist de limpieza: pisos, superficies, ventanas, exterior]
        a2 --> a3[Enciende pantallas, AC, extractores, decorativas, letrero]
        a3 --> a4["Apertura de caja (PROC-CTB-002)"]
    end
    subgraph coc ["Personal de Cocina"]
        c1[Higiene + marca entrada] --> c2[Limpia hornos, mise en place, calienta equipos] --> c3[Guarda lo que requiere refrigeracion]
    end
    e5 --> JOIN
    a4 --> JOIN
    c3 --> a2
    JOIN{Llega la hora de apertura} --> CORT[Levanta cortinas + letrero Abierto]
    CORT --> BRIEF{Hay indicaciones? Si: reune al equipo, menos de 3 min}
    BRIEF --> OPEN[Sucursal abierta al publico]
```

Contingencias resueltas dentro del BPMN (gateways del checklist de
apertura): sin agua de red (abre tanque de reserva), sin electricidad
(motor o UPS), rastros de plaga o baños sucios (desinfecta y reporta a
Mantenimiento, no bloquea la apertura — a diferencia de RN-CDP-002 en
cocina de producción), falla de frío (RN-SUC-009: triage NO USAR /
traslado a otro frío / uso normal si conserva frío / reporte urgente a
almacén central y gerencia), falta de gas (RN-SUC-010: tanque de repuesto,
pedido urgente a Compras, proveedor de urgencia, sanción por falta de
aviso).

> Pendiente (BPMN detallado en otra sesión): contingencia de personal
> faltante en apertura (RN-RRHH-011) y de tardanza/falta del encargado o
> supervisor (RN-RRHH-010) — ya tienen regla de negocio, falta el
> diagrama.

## Apertura de caja

`PROC-CTB-002` · v1.0 · Vigente

Empieza cuando el cajero asignado solicita al encargado de tienda/
supervisor el efectivo (fondo/caja chica), los POS de pago con tarjeta y
las llaves de la gaveta. Termina con la caja aperturada en el ERP y el
efectivo asegurado en la gaveta, lista para recibir pedidos y cobros.
Sigue la cadena de custodia obligatoria del efectivo (RN-MDP-002) en
sentido inverso al cierre: área contable/encargado de tienda/supervisor →
cajero, con autenticación (usuario + PIN) y confirmación de valores en el
relevo. Durante el conteo y la apertura, el encargado de tienda/supervisor
no atiende otro proceso (RN-POS-013). Ni el faltante de efectivo, la
escasez de sencillo, ni un POS averiado bloquean la apertura: se abre en
el horario normal dejando constancia del problema (RN-POS-011). Diagrama
BPMN completo:
[PROC-CTB-002-v1.0.bpmn](../diagrams/Procesos/Contabilidad/PROC-CTB-002-v1.0.bpmn).

```mermaid
flowchart LR
    subgraph ca1 ["Cajero"]
        a1[Solicitar al encargado/supervisor: efectivo, POS y llaves de la gaveta]
    end
    a1 --> b1
    subgraph en ["Encargado de tienda / Supervisor"]
        b1[Recibir solicitud y autenticarse: usuario + PIN] --> b2[Contar junto al cajero el efectivo del fondo/caja chica, por denominacion]
        b2 --> b3{Coincide con el monto y denominacion del cierre anterior?}
        b3 -->|No| b4[Reportar a contabilidad y gerencia via ERP: faltante o escasez de sencillo] --> b5
        b3 -->|Si| b5[Revisar que los POS de pago con tarjeta tengan bateria y funcionen]
        b5 --> b6{Todos los POS funcionan?}
        b6 -->|No| b7[Reportar a contabilidad: serie y codigo de comercio del POS averiado; solicitar POS de emergencia RN-POS-009] --> b8
        b6 -->|Si| b8[Entregar efectivo, POS y llaves de la gaveta al cajero, autenticado]
    end
    b8 --> c1
    subgraph ca2 ["Cajero"]
        c1[Ir al terminal de punto de venta fisico y encender la computadora] --> c2[Iniciar el ERP con el modulo de punto de venta]
        c2 --> c3[Ingresar su usuario] --> c4[Abrir el modulo de punto de venta]
        c4 --> c5[Abrir caja indicando el monto de apertura, RN-POS-003] --> c6[Guardar el efectivo ordenado en los casilleros de la gaveta y asegurar con llave]
    end
```

El faltante/escasez de sencillo y la falla de POS reportados en b4/b7 se
resuelven en paralelo, sin detener la apertura (RN-POS-011): buscando
cambio en otro establecimiento o sucursal cercana, solicitando a
contabilidad y recogiendo el cambio en sus oficinas, o usando el POS de
emergencia del grupo de sucursales cercanas (RN-POS-009). Prever sencillo
para la jornada siguiente es responsabilidad del encargado de tienda/
supervisor (RN-POS-012), no solo una reacción al reporte.

## Cierre de caja

`PROC-CTB-001` · v1.1 · Vigente

Empieza al llegar la hora de cierre del establecimiento, dentro del
horario de la jornada (RN-POS-004). Termina con el dinero en custodia
local en la sucursal o a disposición de la empresa en contabilidad, según
RN-MDP-006. Sigue la cadena de custodia obligatoria del efectivo
(RN-MDP-002): cajero → encargado de tienda/supervisor → (área contable, si
corresponde traslado), con autenticación (usuario + PIN) y confirmación de
valores en cada relevo. Diagrama BPMN completo:
[PROC-CTB-001-v1.1.bpmn](../diagrams/Procesos/Contabilidad/PROC-CTB-001-v1.1.bpmn).

```mermaid
flowchart LR
    subgraph ca ["Cajero"]
        a1[Cerrar mesas/cuentas abiertas] --> a2[Contar caja chica por denominación]
        a2 --> a3{Coincide con apertura?}
        a3 -->|No| a4[Registrar diferencia] --> a5
        a3 -->|Si| a5[Contar efectivo de ventas]
        a5 --> a6[Cierre de lote por POS + reporte detallado]
        a6 --> a7[Sistema verifica links de pago de la sucursal]
        a7 --> a8[Caja: Iniciar cierre] --> a9{Dentro del horario de jornada?}
        a9 -->|No| esp[Esperar horario] --> a8
        a9 -->|Si| a10[Ingresar montos reales] --> a11{Cuadra?}
        a11 -->|No| a12[Confirmar o recontar] --> a10
        a11 -->|Si| a13[Preparar sobre: dinero + reportes + cierre]
    end
    a13 --> b1
    subgraph en ["Encargado de tienda / Supervisor"]
        b1[Recibir sobre: usuario + PIN] --> b2{Cierre correcto?}
        b2 -->|No| b3[Reportar irregularidad: contable + gerencia + RRHH] --> b4
        b2 -->|Si| b4[Buen recaudo, sobre sellado y firmado]
        b4 --> b4g{Local seguro (camaras/caja fuerte/alarma) y contabilidad determina poco efectivo?}
        b4g -->|Si, RN-MDP-006| blocal[Custodia local: guardar el sobre en la caja fuerte de la sucursal para la siguiente apertura]
        b4g -->|No| b5[Entregar el sobre al area contable]
    end
    b5 --> c1
    subgraph ac ["Área contable"]
        c1[Recepcionar: usuario + PIN] --> c2[Verificar contenido y valores]
        c2 --> c3{Falta cambio para apertura?}
        c3 -->|Si| c4[Entregar cambio en sobre] --> c5
        c3 -->|No| c5{Hay faltante?}
        c5 -->|Si| c6[Atribuir responsable: RN-MDP-005] --> c7
        c5 -->|No| c7[Dinero a disposición de la empresa]
    end
```

Atribución del faltante — ver [RN-MDP-005](business-rules.md#medio-de-pago):
depende de en qué etapa se detecta y documenta (cierre/validación vs.
recién en contabilidad), y de si el cajero ya había reportado un cobro mal
hecho por un tercero según [PROC-COM-002](#cobro-y-emisión-de-comprobante-de-pago).

## Incorporación de personal

`PROC-RRH-001` · v1.0 · Vigente

Empieza cuando un encargado detecta que hay que cubrir un puesto y termina
cuando el trabajador supera —o no— el periodo de prueba. Cubre los 13 pasos
de [docs/rrhh/](../rrhh/README.md). Tres reglas lo gobiernan y explican por
qué el proceso tiene la forma que tiene: **sin perfil de puesto no se
publica convocatoria** (RN-RRHH-013), porque una búsqueda sin perfil no
sabe a quién busca; **nadie inicia labores sin contrato firmado y alta en
T-Registro** (RN-RRHH-012); y **todo descarte lleva motivo**, que es la
defensa documental ante un reclamo por la Ley 26772. El candidato no entra
a `persona` mientras es candidato: vive en `postulante`, y `persona` +
`trabajador` nacen recién al contratar. Diagrama BPMN completo:
[PROC-RRH-001-v1.0.bpmn](../diagrams/Procesos/Recursos-Humanos/PROC-RRH-001-v1.0.bpmn).

Estado de implementación: convocatoria, formulario público de postulación y
tablero de 13 columnas están en código (2026-08-01). Entrevista, plan de
inducción y evaluación de periodo de prueba quedaron **especificados** en
`data-model.md §8b` (2026-08-05) y esperan su slice.

## Contingencia de personal faltante en la apertura

`PROC-RRH-002` · v1.0 · Vigente

Empieza cuando falta personal en la apertura de una sucursal y termina con
el turno cubierto y la consecuencia económica resuelta (RN-RRHH-011).

Lo primero que hay que entender es lo que el proceso **no** hace: no
posterga la apertura. El personal presente redistribuye las funciones
críticas y el local abre en su horario mientras Administración busca
reemplazo en otra sucursal o entre quienes están en día de descanso. El
reemplazo recibe pago extra y ese monto se le descuenta al trabajador
faltante, **salvo que presente constancia médica** — que es la única
excepción y por eso es una decisión explícita del flujo, no un criterio de
quien liquida. Diagrama BPMN completo:
[PROC-RRH-002-v1.0.bpmn](../diagrams/Procesos/Recursos-Humanos/PROC-RRH-002-v1.0.bpmn).

Se cruza con [PROC-OPE-001](#apertura-de-sucursal): es el proceso que esta
contingencia tiene prohibido detener.

## Tardanza o falta del encargado a la apertura

`PROC-RRH-003` · v1.0 · Vigente

Empieza cuando el encargado de tienda o el supervisor no llega a la hora de
apertura **sin aviso previo de al menos 24 horas ni coordinación con un
supervisor**, y termina con la medida documentada (RN-RRHH-010).

La gradualidad es el punto: hasta 30 minutos de retraso es **memorándum, y
un memorándum no es sanción** —es la constancia de que se advirtió—; más de
30 minutos, o falta completa, es carta de amonestación (RN-RRHH-004) y el
encargado asume la responsabilidad documentada. Con aviso previo o
coordinación el proceso ni se dispara: hay cobertura acordada y no hay nada
que sancionar. Diagrama BPMN completo:
[PROC-RRH-003-v1.0.bpmn](../diagrams/Procesos/Recursos-Humanos/PROC-RRH-003-v1.0.bpmn).

## Definición y revisión de precio

`PROC-COM-003` · v1.0 · Vigente

Empieza con un disparador —producto nuevo, cambio de costo de insumo,
revisión periódica o presión de la competencia— y termina con el precio
publicado en la lista vigente. Tres áreas aportan lo suyo antes de que
exista un precio: Comercial el valor percibido y la competencia, I+D+i la
receta, Contabilidad el costo variable real (RN-PRC-002).

Dos reglas hacen el proceso: **todo precio se calcula con margen de
contribución explícito antes de publicarse** (RN-PRC-001), y **el precio en
POS es fijo e innegociable, solo varía por lista de precios** (RN-PRC-003)
— nunca se edita en caja. Un precio bajo el margen mínimo no está prohibido,
pero necesita sustento escrito y aprobación de Gerencia: la excepción existe
y queda registrada como excepción. Diagrama BPMN completo:
[PROC-COM-003-v1.0.bpmn](../diagrams/Procesos/Comercial/PROC-COM-003-v1.0.bpmn).

## Estados clave

- Solicitud: `pendiente → aprobada|rechazada|cancelada → despachada → recibida`
  (`en_picking` se descartó: no gobierna ninguna regla — ADR-020)
- Transferencia: `en_transito → recibida` (diferencias registradas y auditadas).
  La recepción puede ser **parcial**: lo que no llegó sigue en tránsito.
- OC: `borrador → emitida → recibida_parcial → recibida | anulada`
- Venta: confirmación exige stock de receta; anulación genera contramovimientos.
- Cumplimiento de pedido (por ítem): `pendiente → en_preparacion → listo → entregado`,
  sin retroceso; el pedido hereda el estado de su ítem más atrasado.
