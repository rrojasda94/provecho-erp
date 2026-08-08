# Módulo `users` — Usuarios, autenticación y RBAC

## Objetivo

Autenticar personas y agentes de IA, y autorizar cada acción según la cadena:
Usuario → Rol → Permisos → Acciones → Restricciones → Sucursales → Empresa → Datos.
Provee el contexto de tenant a todos los demás módulos. La auditoría
dejó de ser suya: `audit_log` es transversal y vive en `src/shared`
(ADR-031), aunque `users` siga siendo su mayor escritor.

## Entidades

`usuario` (username, pin_hash Argon2id, tipo humano|agente_ia), `rol`, `permiso`
(código `modulo.accion` + restricciones), `usuario_rol`, `rol_permiso`,
`usuario_sucursal`, `refresh_token`. `persona` (party model,
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
- Alojar el flujo de **parámetros operativos por empresa**
  (`parametro_empresa`, entidad de `shared`, ADR-014 + Addendum): el área
  propone desde su módulo, Gerencia acepta / rechaza / modifica, y recién
  ahí el valor llega al módulo consumidor. Incluye los umbrales
  cuantitativos que otros módulos consultan en vez de hardcodear
  (`purchases/oc_umbral`, `accounting/pago_umbral`). Vive aquí porque
  `users` es el hogar de lo administrativo transversal, no porque el
  parámetro sea de `users`.
- Asignar usuario a sucursales (alcance).
- Consultar permisos efectivos de un usuario.
- Dejar rastro de los actos de autoridad (login fallido, alta de usuario,
  asignación de rol/permiso, elevación de PIN, anonimización) llamando a
  `src.shared.auditoria.registrar` — la tabla ya no es de este módulo.

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

### Búsqueda de persona (permiso `personas.leer`, no `users.gestionar`)

| Método | Ruta | Acción |
|--------|------|--------|
| GET | `/api/v1/personas/buscar?q=` | Selector de "elegir persona existente" para otro módulo (RRHH al contratar, Compras al dar de alta un proveedor natural). Responde `PersonaBusquedaOut` (id, nombres, apellidos, numero_documento) — nunca domicilio/teléfono/email/fecha de nacimiento, así que puede abrirse sin exigir el permiso de administración completo. Ruta declarada antes de `/personas/{persona_id}` a propósito. |

### Organización — solo lectura (`Almacen` vive en `users` por historia, ver data-model §1)

| Método | Ruta | Acción |
|--------|------|--------|
| GET | `/api/v1/almacenes` | Lista de referencia (nombre/tipo), escopada por tenant — sin `require_permission`: no es dato sensible, lo necesita cualquiera que elija un destino (ej. `purchases` al crear una OC) |

### Divisas (RN-GER-010) — lectura abierta, escritura de Gerencia

| Método | Ruta | Acción |
|--------|------|--------|
| GET | `/api/v1/divisas` | Cualquier autenticado — cualquier módulo que declare un monto necesita poder listar divisas válidas |
| POST/PATCH | `/api/v1/divisas[/{id}]` | Permiso `gerencia.gestionar_parametros_empresa`. Antes solo se editaba por seeder/migración (ADR-014 Addendum b) — esto es lo que lo vuelve CRUD de verdad |

### Parámetros operativos por empresa (ADR-014, RN-GER-009)

| Método | Ruta | Acción |
|--------|------|--------|
| POST | `/api/v1/parametros` | El área propone un cambio desde su módulo (permiso `<modulo>.proponer_parametro`); nace en estado `propuesto` y **no afecta al módulo todavía** |
| GET | `/api/v1/parametros` | Lista con `?empresa_id&estado&modulo`; `?estado=propuesto` es la bandeja de Gerencia. Sin `?modulo` exige el permiso de Gerencia (los rangos salariales de RRHH no son de lectura general) |
| POST | `/api/v1/parametros/{id}/aprobar` | Gerencia aprueba (permiso `gerencia.gestionar_parametros_empresa`); `{"valor": ...}` opcional = modificar antes de aprobar |
| POST | `/api/v1/parametros/{id}/rechazar` | Gerencia rechaza con `{"motivo_rechazo": ...}`; queda el valor anterior |

**Toda magnitud lleva su unidad** (RN-GER-010): un valor monetario declara
`divisa` (`{"monto":"2000.00","divisa":"PEN"}`) y uno físico
`unidad_medida_id` (`{"cantidad":"5.000","unidad_medida_id":"..."}`); un
número suelto es 409. El redondeo usa los decimales de esa unidad
(`divisa.decimales`, `unidad_medida.decimales`), y `valor_display` guarda la
magnitud formateada que leyó Gerencia al decidir. Lo adimensional
(`{"porcentaje":2.5}`, `{"dias":5}`) va sin unidad.

Los módulos **no consultan la tabla**: leen con
`src.shared.parametros.valor_vigente(session, empresa_id, modulo, codigo, default)`,
o con `src.shared.aprobaciones.umbral_vigente(...)` si el valor es un monto
que se compara como `Decimal`. Ambos devuelven solo el valor aprobado.
Catálogo de módulos válidos: `src.shared.parametros.MODULOS`.

## Estado (implementado 2026-07-25)

Slice auth + RBAC + CRUD operativo. Capas: `domain/rules.py` (formato de PIN,
umbrales de lockout, deny por defecto), `infrastructure/` (modelos, `security.py`
con Argon2id + JWT, `repositories.py`), `application/` (`auth.py`, `admin.py`),
`api/` (`schemas.py`, `deps.py`, `routers.py`). Seeder:

```
python -m src.seeders.seed
```

**Restricciones de permiso (ADR-022, 2026-08-02):** `permiso.restricciones`
(JSONB) ya se evalúa, no solo se guarda. `domain/rules.ContextoPermiso` +
`cumple_restricciones` (monto/estado/horario — claves `monto_maximo`,
`estados_permitidos`, `horario`) son puras; `UsuarioRepo.restricciones(usuario_id,
codigo)` resuelve la del usuario (comodín `*` o cualquier rol que lo otorgue
sin condición ⇒ sin restricción, mismo criterio OR que `permite`).
`check_permission(session, usuario, *codigos, contexto=...)` (`api/deps.py`,
re-exporta `ContextoPermiso` para que otros módulos lo usen sin tocar
`users.domain`) la aplica cuando el llamador pasa `contexto`; sin él, se
comporta igual que siempre. `require_permission` (el `Depends` sin acceso al
body) no cambia — la condición depende del body, así que solo
`check_permission` puede evaluarla. Primer uso real:
`sales.aplicar_descuento` acepta un `monto_maximo` por rol (ver
`sales/README.md`).

## Sincronización con el hub de sucursal (implementado 2026-07-27)

`application/sincronizacion.py` declara qué replica este módulo hacia el
hub local (ADR-009 fase 2): la organización (grupo, empresa, marca,
sucursal, almacén) y el RBAC completo de esa sucursal (persona, usuario,
rol, permiso y sus asignaciones). Sin RBAC replicado nadie puede
autenticarse en el hub durante un corte.

- `usuario.pin_hash` **sí** viaja (Argon2id, nunca el PIN): es lo que
  permite validar el PIN sin nube. Es la única salida de un hash de
  credencial en toda la API, detrás del permiso `sync.leer` y acotada a
  los usuarios de esa sucursal.
- `intentos_fallidos`/`bloqueado_hasta` **no** viajan: el lockout es estado
  vivo de cada lado; replicarlo bloquearía a un cajero en el local por
  intentos hechos contra la nube.
- `persona` viaja recortada (nombres, apellidos, documento) — el PDV
  muestra un nombre, no una ficha.
- Rol `hub_sucursal` (`sync.leer` + `sync.empujar`) y alta de la cuenta de
  servicio: `python -m src.seeders.hub`.

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
- Escucha (`application/listeners.py`): `sales.pedido_demorado` → avisa al
  encargado de turno; y desde 2026-08-06 los tres avisos de inventario —
  `inventory.stock_bajo_minimo`, `inventory.lote_vencido_detectado` y
  `inventory.conteo_vencido` → avisan al almacén.
- Todos los módulos dependen de este para autorización y auditoría (vía core, no import directo).

## Notificaciones

`users` es el dueño del **destinatario**, así que es el módulo que sabe a
quién avisarle. Los que publican el hecho no conocen al encargado de turno
ni a la bandeja: publican qué pasó y siguen.

`notificacion` es **bandeja, no transporte**. La fila se crea siempre y el
frontend la consulta (`GET /notificaciones`, `POST /notificaciones/{id}/leer`,
`POST /notificaciones/leer-todas`, todos sin `require_permission` a
propósito: cada uno ve lo suyo y el filtro es la identidad, no un rol).
Empujarla a un teléfono es una capa que todavía no existe, y cuando exista
leerá de esta tabla en vez de reemplazarla — un aviso que solo viajó por
push no deja rastro de si alguien lo vio.

**A quién le llega** lo deciden `destinatarios_de_sucursal` (hechos de un
local) y `destinatarios_de_almacen` (hechos de un almacén), y esos son los
únicos puntos a tocar cuando haya que hacerlo configurable.

Por sucursal:

1. El **encargado de turno**, derivado del `relevo_encargado_id` de la caja
   abierta (contrato público de `accounting`). No hizo falta una entidad
   "turno": ese dato ya se registra al abrir caja (RN-MDP-002) y es
   exactamente la persona a cargo del local en ese momento.
2. Sin caja abierta (local cerrado, o abrieron sin registrarla), los
   `supervisor`/`admin` asignados a esa sucursal. Un aviso sin destinatario
   es un aviso perdido: prefiere avisarle a alguien de más que a nadie.
3. Si no hay nadie, se registra en el log y se sigue — no poder avisar nunca
   tumba la operación que originó el aviso.

Por almacén, que **no** puede reusar lo anterior: el central y el de
producción no cuelgan de ninguna sucursal (`almacen.sucursal_id` NULL) y
ahí no existe encargado de turno. La regla es por rol
(`almacenero`/`supervisor`/`admin`):

1. Almacén **de sucursal**: los roles de almacén asignados a esa sucursal,
   más el encargado de turno — es quien está parado ahí ahora.
2. Almacén **de empresa**: los roles de almacén asignados a cualquier
   sucursal de esa empresa. Es más gente de la necesaria y es a propósito;
   un aviso del central sin destinatario es un aviso perdido.
