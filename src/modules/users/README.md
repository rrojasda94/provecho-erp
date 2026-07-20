# Módulo `users` — Usuarios, autenticación y RBAC

## Objetivo

Autenticar personas y agentes de IA, y autorizar cada acción según la cadena:
Usuario → Rol → Permisos → Acciones → Restricciones → Sucursales → Empresa → Datos.
Provee el contexto de tenant a todos los demás módulos y la auditoría central.

## Entidades

`usuario` (username, pin_hash Argon2id, tipo humano|agente_ia), `rol`, `permiso`
(código `modulo.accion` + restricciones), `usuario_rol`, `rol_permiso`,
`usuario_sucursal`, `refresh_token`, `audit_log`.
Incluye además la organización: `grupo`, `empresa`, `marca`, `sucursal`, `almacen`.
Detalle en `docs/architecture/data-model.md` (§1, §2).

## Casos de uso

- Login con username + PIN (6 dígitos) → access token (15 min) + refresh (7 días, rotativo).
- Refresh y logout (revocación de refresh token).
- CRUD de usuarios, roles y permisos (solo admin).
- Asignar usuario a sucursales (alcance).
- Consultar permisos efectivos de un usuario.
- Registrar entrada en `audit_log` (consumido por todos los módulos).

## Contrato API (v1)

| Método | Ruta | Body | Respuesta |
|--------|------|------|-----------|
| POST | `/api/v1/auth/login` | `{username, pin}` | `{access_token, refresh_token, token_type}` |
| POST | `/api/v1/auth/refresh` | `{refresh_token}` | tokens nuevos (rotación) |
| POST | `/api/v1/auth/logout` | `{refresh_token}` | 204 |
| GET | `/api/v1/users/me` | — | usuario + roles + sucursales |

Claims del JWT: `sub` (usuario_id), `roles`, `sucursales`, `empresa_id`, `exp`.

## Reglas

- PIN: exactamente 6 dígitos, hasheado con Argon2id. Nunca en logs.
- Bloqueo tras 5 intentos fallidos consecutivos (ventana 15 min).
- Refresh tokens rotativos: usar uno viejo revoca toda la cadena.
- Agentes de IA son usuarios tipo `agente_ia` con permisos restringidos (ej. solo `sales.crear_pedido`).
- Seeder de desarrollo: usuario `admin` / PIN `123456` con rol admin. Prohibido en producción.

## Flujo

Login → validar PIN → emitir tokens → cada request valida JWT → middleware
resuelve tenant y permisos → endpoint autoriza acción → auditoría registra cambios.

## Relaciones

- Publica: `users.usuario_creado`, `users.sesion_iniciada`.
- Todos los módulos dependen de este para autorización y auditoría (vía core, no import directo).
