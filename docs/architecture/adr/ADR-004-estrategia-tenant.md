# ADR-004 — Aislamiento de tenant: filtro a nivel de aplicación

- **Estado**: Aceptada (2026-07-20)
- **Contexto**: todo dato de negocio pertenece a un tenant
  (empresa/marca/sucursal). Había dos alternativas para garantizar el
  aislamiento: Row-Level Security (RLS) de PostgreSQL o filtro a nivel de
  aplicación. La decisión estaba pendiente y bloqueaba el modelado de BD.

## Decisión

Filtro a nivel de aplicación: toda consulta de negocio incluye
`empresa_id` obligatorio (y marca/sucursal según alcance del permiso),
inyectado por el contexto de tenant que resuelve el middleware de `users`
a partir del JWT. Se acompaña de:

1. Repositorios base que exigen el contexto de tenant — no existe método
   de consulta sin él (falla en tiempo de desarrollo, no en producción).
2. Tests obligatorios de aislamiento por módulo: un usuario de la empresa
   A nunca ve datos de la empresa B.
3. RLS de Postgres queda como refuerzo futuro opcional (defensa en
   profundidad) si la operación lo amerita — el esquema no lo impide.

## Alternativas consideradas

- **RLS de Postgres**: aislamiento a nivel de motor, robusto incluso ante
  bugs de aplicación. En contra: más complejo de operar y debuggear en un
  monolito (variables de sesión por conexión, interacción con el pool de
  SQLAlchemy, migraciones de políticas), y el equipo es pequeño.

## Consecuencias

- Toda tabla de negocio referencia su tenant directa o transitivamente
  (ya es convención del data-model).
- El repositorio base de `shared`/`core` es el único punto de acceso a
  datos — saltárselo es violación de arquitectura.
- Si se adopta RLS después, se agrega como capa extra sin cambiar el
  contrato de los repositorios.

## Implementación (2026-07-27)

`src/core/tenant.py` — `Tenant` se construye desde los claims del JWT
(`empresa_id`, `sucursales`, `su`) y se inyecta con la dependencia
`get_tenant` de `users`. **El `empresa_id`/`sucursal_id` de una operación
ya no se lee del body ni del query string**: como mucho el cliente puede
repetir el suyo, y uno ajeno responde 403.

- `tenant.empresa(explicito)` — escrituras: exige una empresa concreta.
- `tenant.filtro_empresa(explicito)` — listados: `None` = sin filtro (solo
  superusuario sin empresa asignada).
- `tenant.exigir_sucursal(id)` / `tenant.exigir_empresa(id)` — validan un
  recurso ya cargado; lanzan `FueraDeAlcance`, que el app factory mapea a
  403 en un solo lugar para que ningún endpoint nuevo olvide hacerlo.

Helpers por módulo: `inventory/application/scope.py` (almacén, artículo,
ajuste) y `sales/application/scope.py` (venta, ítem, pantalla KDS), que
resuelven el tenant del recurso a partir de su fila real.

**Escape explícito — superusuario**: un usuario con permiso `*` y sin
`usuario_sucursal` (la cuenta de administración, que existe antes que
cualquier sucursal) puede indicar `empresa_id` explícitamente. Sin esto el
bootstrap del sistema sería imposible. Se resuelve al emitir el token
(claim `su`), no por request.

Cobertura actual: `users`, `inventory`, `sales` y `kds`. **Pendiente**:
`purchases`, `production`, `accounting`, `rrhh` y el dashboard gerencial
siguen recibiendo `empresa_id` del cliente — ver Deuda técnica en
`ROADMAP.md`. `sync` ya derivaba el tenant de la cuenta de servicio.

Tests de aislamiento: `tests/test_tenant_aislamiento.py`.
