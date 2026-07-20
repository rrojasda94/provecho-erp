# Contexto para trabajar en base de datos

Leer antes: [architecture/data-model.md](../architecture/data-model.md) y README del módulo.

## Reglas duras

- Todo cambio de esquema = migración Alembic (`alembic revision --autogenerate`)
  + actualización de `docs/architecture/data-model.md`. Nunca SQL manual en producción.
- Convenciones: `snake_case`, PK `id` UUID, `created_at`/`updated_at`,
  `deleted_at` para borrado lógico donde aplique.
- Toda tabla de negocio referencia su tenant (directa o transitivamente).
- Tablas de movimientos y auditoría son solo-inserción (inmutables).
- Montos: `NUMERIC`, nunca float. Fechas en UTC.
- Índices para toda FK consultada y para claves de idempotencia (únicas).
