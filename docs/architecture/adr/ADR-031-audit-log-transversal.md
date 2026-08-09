# ADR-031 — `audit_log` transversal: un solo punto de escritura, escritura explícita

- Estado: aceptado
- Fecha: 2026-08-08

## Contexto

`audit_log` nació dentro de `users` (migración `c16d615f6afd`, slice de
auth): el primer hecho que hubo que auditar fue un login fallido, y la tabla
se quedó donde estaba quien la escribía. Su docstring ya decía "consumido
por todos los módulos vía core", pero el código decía otra cosa:

- El único escritor era `users.infrastructure.repositories.AuditLogRepo`.
- `rrhh` lo usaba importando los repositorios de `users` — una excepción
  declarada en `tests/test_arquitectura.py`, es decir, una violación
  documentada de la regla de CLAUDE.md.
- Ningún otro módulo auditaba nada. Anular una venta, aprobar un ajuste de
  inventario, emitir una OC sobre el umbral, ejecutar un pago o sacar
  efectivo del cajón —los actos que un auditor viene a revisar— no dejaban
  rastro consultable. Solo existían como eventos del bus, que nadie
  persiste para leerlos después.
- No había forma de *leer* el rastro: ni endpoint, ni índices. La única
  consulta posible era `SELECT` a mano contra la base.

La seguridad de CLAUDE.md ("Auditoría: quién, qué, cuándo, dónde, valor
anterior/nuevo") estaba escrita, no implementada.

## Decisión

**El `audit_log` es transversal: la tabla vive en `src/shared/models/` y
`src/shared/auditoria.py` es su único punto de escritura.**

1. **`registrar(session, ...)`, no un repositorio de módulo.** Cualquier
   módulo la llama sin importar nada de otro. La entrada se agrega a la
   **misma sesión** que el cambio auditado: si el cambio se revierte, el
   rastro también — auditar algo que no pasó es peor que no auditarlo.
2. **Escritura explícita en el caso de uso, no captura automática.** La
   alternativa era un listener de SQLAlchemy (`after_flush`) que auditara
   todo `UPDATE`. Se descartó: (a) el actor y la IP no están en la sesión
   —habría que empujarlos por `contextvar` y el trabajo de Celery quedaría
   sin actor—; (b) auditar cada `UPDATE` produce un rastro que nadie lee
   —y el que no se lee no controla nada—; (c) el criterio de qué es un acto
   de autoridad es del dominio, no del ORM: `venta.total` cambia por sumar
   una línea y por regalar un descuento, y son cosas distintas.
   **Qué se audita**: aprobar, autorizar, anular, descontar, pagar, retirar
   efectivo, anonimizar. No el alta rutinaria ni la lectura.
3. **Tabla y log, no uno u otro.** Cada `registrar` deja la fila (rastro
   legal, consultable, con su retención) y una línea en el logger
   `provecho.auditoria` (lo que un colector externo vigila en vivo — si
   alguien borrara la fila, la línea ya salió del proceso). El log lleva
   **solo metadatos**: `datos_antes`/`datos_despues` pueden traer PII (Ley
   29733) y ese detalle se queda en la tabla.
4. **`empresa_id` nuevo, nullable.** Sin él la lectura no se puede escopar
   por tenant (ADR-004). Nullable porque no todo hecho auditable tiene
   empresa: un login fallido todavía no la tiene, un alta de rol es global.
5. **Lectura por `GET /api/v1/auditoria`** (permiso `auditoria.leer`, en
   `core` como el dashboard), paginada (ADR-026) y filtrable por entidad,
   acción, usuario y fechas. **No hay `POST`**: el rastro lo escribe el caso
   de uso que hace el cambio. Un endpoint de escritura le permitiría al
   auditado dictar lo que dice su auditoría.

### Alcance de lectura

| Quién | Qué ve |
|---|---|
| Superusuario (permiso `*`) | Todo, incluidas las filas sin tenant (login, RBAC) |
| Usuario con empresa/sucursales | Filas de su empresa **o** de sus sucursales |
| Usuario sin empresa ni sucursales | Nada |

Las filas sin empresa ni sucursal quedan fuera del alcance acotado a
propósito: no hay forma de atribuirlas a una empresa sin adivinar, y
adivinar acá es mostrarle a una empresa lo que pasó en otra. El superusuario
las ve aunque tenga sucursales asignadas — si no, el rastro de RBAC y de
sesiones no lo podría leer nadie (el `admin` sembrado tiene todas las
sucursales).

## Consecuencias

- `rrhh` sale de `_EXCEPCIONES_CRUZADAS` en `tests/test_arquitectura.py`:
  entraba a `users.infrastructure.repositories` solo por esto.
- `users` deja de ser dueño de la tabla; sigue siendo el mayor escritor.
- Cinco módulos empiezan a dejar rastro (`sales`, `inventory`, `purchases`,
  `accounting` y el `users`/`rrhh` que ya lo hacían). La lista no es
  exhaustiva ni pretende serlo: se agrega el acto cuando se implementa.
- La tabla crece por inserción pura y **no tiene retención automática**
  (deuda declarada en `ROADMAP.md` → Protección de datos). Los dos índices
  nuevos (`entidad`+`entidad_id`, `ts`) aguantan la consulta mientras tanto.
- Migración `b3d9f1c2a077` (aditiva: columna nullable + índices). Mover el
  modelo de módulo no genera DDL — la tabla y su nombre no cambian.
