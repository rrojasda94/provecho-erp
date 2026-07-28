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
  middleware de tenant y auditoría. Además, la infraestructura de operación:

  | Archivo | Responsabilidad |
  |---------|-----------------|
  | `app.py` | Factory: middleware, correlación por `request_id`, handler de error no controlado |
  | `events.py` | Bus de eventos interno (síncrono, en proceso) |
  | `celery_app.py` | Cola de tareas en segundo plano (Redis) |
  | `rate_limit.py` | Límite por IP en autenticación (contador Redis, falla abierto) |
  | `logging_config.py` | Logs JSON, tres flujos, redacción de datos sensibles |
  | `sentry.py` | Reporte de errores (no-op sin DSN) |
  | `health.py` + `health_router.py` | Liveness, readiness y frescura de backups |
  | `model_base.py` | Mixins de modelo (UUID, timestamps, soft delete, lock optimista) |
  | `sync/` | Replicación con el hub local de sucursal: contrato declarativo, motor (push→pull), runner y API (ADR-009) |

- `src/shared/`: utilidades sin lógica de negocio; `shared/integrations/`
  para adaptadores externos (Factiliza, Google, Meta, Izipay).
- `src/config/`: settings por entorno (pydantic-settings, `.env`), con
  validación que **aborta el arranque** si producción quedó con valores de
  desarrollo (ver [../security/security.md](../security/security.md)).
- `src/backups/`: copia, verificación y purga de la base de datos. Se
  ejecuta por cron, no por la aplicación (ADR-007).

## Multi-tenant

Jerarquía: Grupo → Empresa → Marca → Sucursal → Almacén. Todo request
autenticado lleva contexto de tenant (claims JWT + asignaciones
usuario-sucursal). Toda query filtra por ese contexto.

## ADRs

Decisiones con alternativas viables se registran en [adr/](adr/). Vigentes:

| ADR | Decisión |
|-----|----------|
| [001](adr/ADR-001-modular-monolith.md) | Modular monolith sobre microservicios |
| [002](adr/ADR-002-stack-tecnologico.md) | Stack tecnológico |
| [003](adr/ADR-003-pasarela-izipay.md) | Pasarela de pago: Izipay |
| [004](adr/ADR-004-estrategia-tenant.md) | Tenant filtrado en aplicación (no RLS) |
| [005](adr/ADR-005-facturacion-electronica-factiliza.md) | Facturación electrónica: Factiliza (reemplaza el supuesto Nubefact) |
| [006](adr/ADR-006-observabilidad.md) | Logs con la biblioteca estándar; errores a Sentry/GlitchTip |
| [007](adr/ADR-007-backups-y-salud.md) | Backups por `pg_dump` + cron; salud expuesta a monitor externo |
| [008](adr/ADR-008-entrega-continua.md) | Imagen publicada en GHCR; despliegue manual hasta tener servidor |
| [009](adr/ADR-009-modo-offline-pdv.md) | Modo offline del PDV: hub local por sucursal; sync por la propia API REST con contrato declarativo por módulo (fase 2) |
| [010](adr/ADR-010-contrato-openapi-exportado.md) | Contrato OpenAPI exportado a `docs/architecture/openapi.json`, verificado en CI |
| [011](adr/ADR-011-derechos-arco-anonimizacion.md) | Derechos ARCO: cancelación de `persona` por anonimización, no borrado físico |
| [012](adr/ADR-012-dashboard-gerencial-y-slice-minimo-de-caja.md) | Dashboard gerencial (agregador en `core`) + slice mínimo de caja con reconciliación real |
| [013](adr/ADR-013-arquitectura-frontend.md) | Arquitectura frontend: Tailwind + Base UI, shell estilo Odoo, gate por permiso |
| [014](adr/ADR-014-parametros-configurables-por-empresa.md) | Parámetros operativos configurables por empresa (`parametro_empresa`), distinta de `regla_aprobacion` |
| [015](adr/ADR-015-lote-y-fefo.md) | Lote y FEFO: `stock_lote` como detalle de `stock`, control opcional por artículo, un movimiento por lote |
