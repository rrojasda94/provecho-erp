# Módulo `users` — Usuarios, autenticación y RBAC

## Objetivo

Autenticar personas y agentes de IA, y autorizar cada acción según la cadena:
Usuario → Rol → Permisos → Acciones → Restricciones → Sucursales → Empresa → Datos.
Provee el contexto de tenant a todos los demás módulos y la auditoría central.

## Entidades

`usuario` (username, pin_hash Argon2id, tipo humano|agente_ia), `rol`, `permiso`
(código `modulo.accion` + restricciones), `usuario_rol`, `rol_permiso`,
`usuario_sucursal`, `refresh_token`, `audit_log`. `persona` (party model,
`version` para lock optimista — ver Estado abajo).
Incluye además la organización: `grupo`, `empresa`, `marca`, `sucursal`, `almacen`.
Detalle en `docs/architecture/data-model.md` (§1, §2).

## Casos de uso

- Login con username + PIN (6 dígitos) → access token (15 min) + refresh (7 días, rotativo).
- Refresh y logout (revocación de refresh token).
- CRUD de usuarios, roles y permisos (solo admin).
- CRUD de `persona` (Create/Read/Update — sin Delete, el ciclo de vida real
  se maneja en la entidad que la referencia). `PATCH` exige la `version`
  vigente (lock optimista): `version` desactualizada → 409, en vez de
  pisar en silencio el cambio de otro editor concurrente.
- Derecho de cancelación (Ley 29733, ADR-011): `POST /personas/{id}/anonimizar`
  sobrescribe los campos identificables de forma irreversible — no es un
  Delete, la fila y sus referencias (`trabajador`/`cliente`/`usuario`)
  permanecen. Permiso dedicado `personas.anonimizar`, distinto de
  `users.gestionar`.
- Administrar la matriz de aprobaciones (`regla_aprobacion`, entidad de
  `shared` — umbrales cuantitativos que otros módulos, ej. `purchases`,
  consultan en vez de hardcodear).
- Asignar usuario a sucursales (alcance).
- Consultar permisos efectivos de un usuario.
- Registrar entrada en `audit_log` (consumido por todos los módulos).

## Contrato API (v1)

| Método | Ruta | Body | Respuesta |
|--------|------|------|-----------|
| POST | `/api/v1/auth/login` | `{username, pin}` | `{access_token, refresh_token, token_type}` |
| POST | `/api/v1/auth/refresh` | `{refresh_token}` | tokens nuevos (rotación) |
| POST | `/api/v1/auth/logout` | `{refresh_token}` | 204 |
| GET | `/api/v1/users/me` | — | usuario + roles + sucursales + permisos |

Claims del JWT: `sub` (usuario_id), `tipo`, `roles`, `sucursales`, `empresa_id`, `iat`, `exp`, `jti`.

### Administración (requiere permiso `users.gestionar` o comodín `*`)

| Método | Ruta | Acción |
|--------|------|--------|
| POST/GET | `/api/v1/users` | Crear / listar usuarios |
| PATCH | `/api/v1/users/{id}` | Editar usuario |
| POST | `/api/v1/users/{id}/pin` | Cambiar PIN |
| POST/DELETE | `/api/v1/users/{id}/roles[/{rol_id}]` | Asignar / quitar rol |
| POST/DELETE | `/api/v1/users/{id}/sucursales[/{suc_id}]` | Asignar / quitar sucursal (alcance) |
| POST/GET | `/api/v1/roles` | Crear / listar roles |
| POST/DELETE | `/api/v1/roles/{id}/permisos[/{permiso_id}]` | Asignar / quitar permiso a rol |
| POST/GET | `/api/v1/permisos` | Crear / listar permisos |
| POST/GET/PATCH | `/api/v1/personas[/{id}]` | CRUD de persona (party model) — `PATCH` exige `version` |
| POST | `/api/v1/personas/{id}/anonimizar` | Derecho de cancelación (Ley 29733) — permiso `personas.anonimizar` |
| POST/GET/PATCH | `/api/v1/reglas-aprobacion[/{id}]` | CRUD de la matriz de aprobaciones (permiso `gerencia.gestionar_reglas_aprobacion`) |

## Estado (implementado 2026-07-25)

Slice auth + RBAC + CRUD operativo. Capas: `domain/rules.py` (formato de PIN,
umbrales de lockout, deny por defecto), `infrastructure/` (modelos, `security.py`
con Argon2id + JWT, `repositories.py`), `application/` (`auth.py`, `admin.py`),
`api/` (`schemas.py`, `deps.py`, `routers.py`). Seeder:

```
python -m src.seeders.seed
```

Pendiente: aplicar las `restricciones` (JSONB) de cada permiso — hoy la
autorización solo valida el código, no la condición (monto/estado/horario).

## Reglas

- PIN: exactamente 6 dígitos, hasheado con Argon2id. Nunca en logs.
- Bloqueo tras 5 intentos fallidos consecutivos (ventana 15 min).
- Refresh tokens rotativos: usar uno viejo revoca toda la cadena.
- Agentes de IA son usuarios tipo `agente_ia` con permisos restringidos (ej. solo `sales.crear_pedido`).
- Seeder de desarrollo: usuario `admin` / PIN `123456` con rol admin. Prohibido en producción.
- El seeder deja montada la organización real del grupo: empresa
  Majambo EIRL (RUC 20450311520, zona `amazonia_ley27037`), marca
  Charlie's Pizzas licenciada a esa empresa, sucursales `CH1` y `CH2`
  (alquiladas, activas) y almacén central `WH1`. Es idempotente: correrlo de
  nuevo no duplica ni reescribe, salvo el domicilio fiscal, que se
  sincroniza siempre.

## Flujo

Login → validar PIN → emitir tokens → cada request valida JWT → middleware
resuelve tenant y permisos → endpoint autoriza acción → auditoría registra cambios.

## Relaciones

- Publica: `users.usuario_creado`, `users.sesion_iniciada`.
- Todos los módulos dependen de este para autorización y auditoría (vía core, no import directo).
