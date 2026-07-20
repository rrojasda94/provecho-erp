# Mapa de módulos y eventos

Flechas punteadas = eventos por el bus interno (`src/core/events.py`).
Ningún módulo importa el dominio de otro.

```mermaid
flowchart TB
    subgraph core[core / shared]
        BUS[Event Bus]
        AUTH[Auth JWT + tenant]
        INT[Integraciones: Nubefact, Izipay, Google, Meta]
    end

    USERS[users\nauth, RBAC, auditoría]
    SALES[sales\nPDV, recetas, pagos]
    INV[inventory\nstock, transferencias]
    PUR[purchases\nOC, recepción]
    ACC[accounting\nasientos]
    PROD[production*\nfabricación]

    SALES -. sales.venta_confirmada .-> INV
    SALES -. sales.venta_confirmada / pago_registrado .-> ACC
    PUR -. purchases.compra_recibida .-> INV
    PUR -. purchases.compra_recibida .-> ACC
    PROD -. production.orden_completada .-> INV
    INV -. inventory.stock_bajo_minimo .-> USERS

    SALES --> INT
    USERS --> AUTH
```

`*` = módulo futuro.
