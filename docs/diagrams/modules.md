# Mapa de módulos y eventos

Flechas punteadas = eventos por el bus interno (`src/core/events.py`).
Ningún módulo importa el dominio de otro. Catálogo completo con payloads:
[../architecture/events.md](../architecture/events.md).

```mermaid
flowchart TB
    subgraph core[core / shared]
        BUS[Event Bus]
        AUTH[Auth JWT + tenant]
        INT[Integraciones: Factiliza, Izipay, Google, Meta]
    end

    USERS[users\nauth, RBAC, auditoría]
    SALES[sales\nPDV, recetas, pagos]
    INV[inventory\nstock, lotes, transferencias]
    PUR[purchases\nOC, recepción, caja chica]
    ACC[accounting\nasientos, pagos, periodos]
    PROD[production*\nfabricación]
    RRHH[rrhh*\nmemorándums, planilla]

    SALES -. venta_confirmada .-> INV
    SALES -. venta_confirmada / pago_registrado / comprobante_emitido .-> ACC
    PUR -. compra_recibida .-> INV
    PUR -. oc_emitida / compra_recibida / comprobante_conforme / caja_chica_rendida .-> ACC
    PROD -. orden_completada .-> INV
    INV -. stock_bajo_minimo / lote_vencido_detectado .-> USERS
    INV -. transferencia_recibida / merma_registrada / ajuste_fuera_margen .-> ACC
    INV -. devolucion_a_proveedor .-> PUR
    INV -. lote_vencido_detectado .-> RRHH

    SALES --> INT
    USERS --> AUTH
```

`*` = módulo futuro.
