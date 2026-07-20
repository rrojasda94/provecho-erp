# Arquitectura

## Estilo

**Modular Monolith**: un solo deployable, módulos internos aislados.
Cada módulo aplica **Clean Architecture** y **DDD**:

```
src/modules/<módulo>/
    domain/          # entidades, value objects, reglas de negocio, eventos de dominio
    application/     # casos de uso (servicios de aplicación), Unit of Work
    infrastructure/  # repositorios SQLAlchemy, adaptadores
    api/             # routers FastAPI, schemas Pydantic (contratos)
    README.md        # especificación del módulo
```

Regla de dependencias: `api → application → domain`. `infrastructure`
implementa interfaces del dominio (Repository Pattern). El dominio no conoce
FastAPI ni SQLAlchemy.

## Comunicación entre módulos

**Event-driven interno** vía `src/core/events.py` (bus síncrono en proceso).
Ejemplo: `sales` publica `sales.venta_confirmada` → `inventory` descuenta
insumos según receta. Prohibido importar el dominio de otro módulo. Si un
módulo necesita datos de otro, consume su contrato público (servicio de
aplicación) o escucha eventos. Mapa: [../diagrams/modules.md](../diagrams/modules.md);
catálogo de eventos: [events.md](events.md).

Esto permite agregar/quitar módulos sin romper el resto y migrar módulos a
servicios separados (Celery ya está en el stack) si alguno lo exige a futuro.

## Capas transversales

- `src/core/`: app factory, base de datos, event bus, seguridad (JWT),
  middleware de tenant y auditoría.
- `src/shared/`: utilidades sin lógica de negocio; `shared/integrations/`
  para adaptadores externos (Nubefact, Google, Meta, Izipay).
- `src/config/`: settings por entorno (pydantic-settings, `.env`).

## Multi-tenant

Jerarquía: Grupo → Empresa → Marca → Sucursal → Almacén. Todo request
autenticado lleva contexto de tenant (claims JWT + asignaciones
usuario-sucursal). Toda query filtra por ese contexto.

## ADRs

Decisiones con alternativas viables se registran en [adr/](adr/).
Vigentes: ADR-001 (modular monolith), ADR-002 (stack), ADR-003 (Izipay).
