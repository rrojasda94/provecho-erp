# Mapa de módulos y eventos

Flechas punteadas = eventos por el bus interno (`src/core/events.py`).
Ningún módulo importa el dominio de otro. Catálogo completo con payloads:
[../architecture/events.md](../architecture/events.md). Solo se dibujan los
eventos que **tienen consumidor en código** (listener suscrito); los que se
publican sin consumidor todavía figuran en el catálogo.

```mermaid
flowchart TB
    subgraph core[core / shared]
        BUS[Event Bus]
        AUTH[Auth JWT + tenant]
        INT[Integraciones: Factiliza, Izipay, Google, Meta]
    end

    USERS[users\nauth, RBAC, organización, bandeja]
    SALES[sales\nPDV, catálogo, pagos, comprobantes]
    INV[inventory\nstock, lotes, transferencias]
    PUR[purchases\nproveedores, OC, recepción]
    ACC[accounting\nasientos, caja, tesorería]
    PROD[production\norden de producción, calidad]
    RRHH[rrhh\ntrabajador, contrato, nómina]
    MKT[marketing\ncampañas, leads, encuestas]
    REP[reports\nemisión y distribución]
    AST[assets\nactivos, mantenimiento, vigencias]
    DLV[delivery\nreparto propio]
    SUP[supervision\ntareas de apertura/cierre]
    WEB[storefront\nsitio público de marca]

    SALES -. venta_confirmada / venta_anulada / lineas_anuladas / nota_credito_emitida / consumo_personal_registrado .-> INV
    SALES -. venta_confirmada / venta_pagada / comprobante_emitido / venta_anulada / lineas_anuladas .-> ACC
    SALES -. venta_confirmada / cliente_registrado_en_promocion .-> MKT
    SALES -. venta_anulada .-> DLV
    DLV -. entrega_registrada .-> SALES
    PUR -. compra_recibida .-> INV
    PUR -. oc_emitida / compra_recibida / comprobante_conforme .-> ACC
    PUR -. requerimiento_activo_recibido .-> AST
    PROD -. consumo_registrado / orden_completada .-> INV
    PROD -. orden_desechada .-> ACC
    INV -. stock_bajo_minimo .-> PROD
    INV -. transferencia_recibida / merma_registrada / consumo_personal_valorizado / consumo_personal_reversado .-> ACC
    AST -. repuesto_consumido .-> INV
    USERS -. organizacion.empresa_creada .-> ACC
    SALES & INV & ACC & PROD & RRHH & AST & SUP -. hechos del catálogo de emisiones .-> REP
    REP -. reporte_emitido .-> USERS

    SALES --> INT
    USERS --> AUTH
```

`reports` escucha los eventos que su catálogo declara
(`reports/domain/catalogo.py`: pedido demorado, descuentos, anulaciones,
stock bajo mínimo, lotes vencidos, caja irregular, no conformidad de
producción, salida sin marcar, informe diario de supervisión, vencimientos de
`assets`, etc.) y publica `reports.reporte_emitido`, que `users` convierte en
la bandeja de notificaciones. `storefront` no publica ni consume eventos en
su slice inicial (ADR-103): lee al ERP por contratos públicos de lectura.
