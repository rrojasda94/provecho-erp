# Contexto para trabajar en base de datos

Leer antes: [architecture/data-model.md](../architecture/data-model.md) y README del módulo.

## Reglas duras

- Todo cambio de esquema = migración Alembic (`alembic revision --autogenerate`)
  + actualización de `docs/architecture/data-model.md`. Nunca SQL manual en producción.
- Convenciones: `snake_case`, PK `id` UUID, `created_at`/`updated_at`,
  `deleted_at` para borrado lógico donde aplique.
- Toda tabla de negocio referencia su tenant (directa o transitivamente).
- Tablas de movimientos y auditoría son solo-inserción (inmutables).
- Montos: `NUMERIC`, nunca float. **Instantes** (`created_at`, `cerrado_at`,
  cualquier "cuándo pasó") en UTC. Pero la **fecha de calendario** del negocio
  —de qué día es un turno, un conteo, una venta— se deriva con
  `src/shared/fechas.py`, que la traduce a la zona del negocio
  (`settings.zona_horaria`). Nunca `date.today()`: devuelve la zona del
  proceso, que en Docker es UTC, y pasadas las 19:00 hora Perú corre el
  calendario un día (ver CHANGELOG 2026-08-03).
- Índices para toda FK consultada y para claves de idempotencia (únicas).
