# ADR-001 — Modular Monolith

- Estado: aceptado
- Fecha: 2026-07-04

## Contexto

ERP para un grupo de restaurantes (una empresa, varias marcas y locales).
Se requiere modularidad total (agregar/quitar funcionalidades), despliegue
local en Docker y en servidor, y un equipo pequeño.

## Alternativas

1. **Microservicios**: aislamiento máximo, pero costo operativo alto
   (red, colas, observabilidad distribuida, transacciones distribuidas) que no
   se justifica para el tamaño actual.
2. **Monolito clásico**: simple, pero acoplamiento crece y quitar módulos es caro.
3. **Modular monolith** (elegida): un deployable, módulos con fronteras duras
   (eventos + contratos), transacciones ACID locales, camino de salida a
   microservicios si un módulo lo exige.

## Consecuencias

- Comunicación entre módulos solo por event bus interno o contratos públicos.
- Un módulo = una carpeta autocontenida en `src/modules/`; se puede desactivar
  no registrando su router/handlers.
- Base de datos única (PostgreSQL) con esquemas/prefijos por módulo si hace falta.
