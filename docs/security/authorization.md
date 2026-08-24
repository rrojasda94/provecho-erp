# Autorización (RBAC)

Modelo de control de acceso. Crece de forma independiente de la
[seguridad](security.md) base. Referencia viva: se amplía al agregar módulos y
acciones. Terminología en el [glosario](../foundation/glossary.md).

## Cadena de acceso

```
Usuario → Rol → Permisos → Acciones → Restricciones →
Sucursales → Empresa → Datos
```

Toda query respeta el contexto de tenant; ningún dato se sirve fuera del
alcance del usuario.

## Conceptos

- **Rol**: agrupa permisos (admin, supervisor, cajero, almacenero, agente_ia, ...).
- **Permiso**: código `modulo.accion` (ej. `inventory.transferir`,
  `sales.anular`, `purchases.aprobar`).
- **Acción**: operación concreta que un permiso habilita.
- **Restricción**: condición que acota un permiso (JSONB): por monto, por
  estado, por horario, etc.
- **Alcance (scope)**: dónde aplica el permiso. Jerarquía de restricción:

| Nivel | Ejemplo de restricción |
|-------|------------------------|
| Empresa | El usuario solo opera una empresa del grupo |
| Marca | Supervisor de una sola marca. **No es un claim del token**: hoy se expresa como varias filas de `usuario_sucursal` — el supervisor lleva los locales que tenga a cargo, uno por fila (ADR-062) |
| Sucursal | Cajero atado a su(s) local(es) (`usuario_sucursal`) |
| Almacén | Almacenero limitado al almacén central |
| Módulo | Rol sin acceso al módulo de contabilidad |

## Reglas de autorización

- **Deny por defecto**: sin permiso explícito, la acción se rechaza (403).
- El alcance por sucursal **viaja en el token** (claim `sucursales`): asignar o
  quitar un local (`POST`/`DELETE /users/{id}/sucursales`) no le cambia nada a
  una sesión ya abierta hasta que renueve (refresh o login). Las dos
  operaciones exigen que la sucursal sea de la empresa de quien administra
  —salvo el superusuario, que administra el grupo— y quedan en `audit_log`.
- El alcance de una cuenta **no es** el centro de labores del trabajador
  (`trabajador.sucursal_id`, ADR-062): dónde trabaja alguien es un hecho
  laboral de RRHH, qué datos alcanza es autorización.
- El alcance sale de los claims del JWT + asignaciones del usuario, nunca del
  body del request sin verificar.
- Un permiso sin restricción aplica a todo el alcance del usuario; con
  restricción, solo donde la condición se cumple.
- Cambios de roles/permisos se auditan.
- **Todo endpoint que reciba un PIN cuenta contra el mismo bloqueo de
  cuenta** (5 intentos / 15 min, 423) y va detrás del mismo rate limit que
  el login: `login`, `autorizar` y `verificar-pin`. Un contador propio por
  endpoint sería el camino cómodo para probar PINes sin agotar los cinco
  del login.

Los tres caminos con PIN responden preguntas distintas y no se sustituyen:

| Endpoint | Pregunta | Efecto |
|---|---|---|
| `/auth/login` | ¿quién sos? | abre sesión (rota tokens) |
| `/auth/autorizar` | ¿este OTRO tiene tal permiso? | token corto acotado a una acción (RN-AUD-005) |
| `/auth/verificar-pin` | ¿seguís siendo vos? | ninguno — 204 o 401 (RN-POS-014) |

## Matriz de permisos (semilla)

| Rol | Permisos base |
|-----|---------------|
| admin | `*` (todo, solo entornos internos) |
| — | `organizacion.gestionar`: CRUD de grupo, empresas, marcas, licencias, sucursales, almacenes y **puntos de venta**. **Aparte de `users.gestionar`**: quien crea cajeros no funda sucursales. Fundar un grupo o una empresa exige además `*` — el recurso nuevo todavía no pertenece a la empresa de nadie |
| — | El **punto de venta** (la caja del local) vive en `sales` pero se administra con este permiso y no con uno `sales.*` (ADR-059): asignarle una serie SUNAT es identidad fiscal de la empresa, del mismo orden que fundar el local, no configurar el salón. `GET /sales/puntos-venta` acepta **`sales.leer` o `organizacion.gestionar`** — el cajero necesita leerlo para abrir el PDV, y quien da de alta las cajas puede no tener ningún permiso de venta |
| supervisor | `inventory.*`, `purchases.aprobar`, `sales.leer`, aprueba solicitudes |
| almacenero | `inventory.transferir`, `inventory.recepcion`, `inventory.ajustar` |
| cajero | `sales.crear`, `sales.cobrar`, `sales.leer`, `sales.entregar_pedido`, `kds.operar`, `accounting.caja_operar` (su sucursal) |
| — | `accounting.caja_operar` alcanza para **preguntar** por la caja de la sucursal propia (`GET /accounting/cajas/abiertas?sucursal_id=`), no solo para abrirla y cerrarla: el PDV tiene que saber si el turno ya está abierto antes de ofrecer abrirlo. Sin el `sucursal_id` la consulta es de toda la empresa y sigue exigiendo `accounting.leer` — quien opera una caja no tiene por qué ver el efectivo de los demás locales |
| — | **Abrir y cerrar el turno no piden elevación de PIN** (RN-MDP-008, ADR-049): `accounting.caja_operar` es el único candado, y es el permiso que el cajero ya tiene. La firma con `accounting.caja_relevar` quedó donde la plata cambia de manos (`POST /cajas/custodias/{id}/entregar`); como el `cajero` **no** tiene ese permiso, no puede firmar que recibió su propio efectivo. La segregación la hace el permiso, no un candado de dominio |
| rrhh_admin | `rrhh.*`, `users.resetear_pin`, `consulta.documento` |
| — | `users.resetear_pin` está **aparte de `users.gestionar`** en los dos sentidos (ADR-041): RRHH atiende el "me olvidé el PIN" sin poder crear cuentas ni repartir roles, y administrar usuarios no trae de arrastre la facultad de entrar como cualquiera de ellos. **No** lo tiene `supervisor`: entrar como cualquiera de su turno rompe la segregación del ciclo de caja (ADR-025/048) — entrar como el cajero sería firmarse a sí mismo la recepción del efectivo por la puerta de al lado |
| — | `consulta.documento` (consultar un DNI/RUC contra RENIEC/SUNAT) es propio y no una consecuencia de poder crear personas: cada consulta gasta cuota del proveedor y trae datos personales de alguien que todavía no es nadie en el sistema. Lo tienen `rrhh_admin`, `comprador`, `cajero` y `supervisor` — los que dan altas |
| — | Dónde se usa: el botón «Buscar por DNI/RUC» (`components/consulta/buscar-documento.tsx`) en Usuarios → Personas, Compras → Proveedores y Ventas → Clientes. **El botón no se dibuja sin el permiso** — es de los pocos gates de UI que además evitan un gasto: sin él, un `contador` lo apretaba y se comía un 403, y una consulta que sí sale cuesta cuota. Sigue siendo UX; la autorización real la hace `require_permission` en cada request |
| — | `GET /consulta/{dni,ruc}/{n}` tiene **cuota propia** (2026-08-15): por usuario y por IP, con la misma ventana (`consulta_documento_*` en `settings`). Se cuenta **después** del permiso —a quien no puede consultar no hay que contarle nada— y por usuario **antes** que por IP, porque en un local todas las cajas salen por la misma dirección y un límite solo por IP deja al equipo entero sin consultar por culpa de uno |
| agente_ia | `sales.crear_pedido` (canal agente_ia, su marca) |
| hub_sucursal | `sync.leer`, `sync.empujar` (una sola sucursal, ADR-009) |

> La matriz completa por módulo se define al implementar cada módulo y su
> conjunto de acciones.

### Cuenta de servicio del hub de sucursal

`hub_sucursal` es el rol de una máquina, no de una persona: lo usa el hub
local de cada sucursal para sincronizar (ADR-009). Tres cosas lo hacen
distinto y valen la pena tenerlas presentes:

- **Alcance de exactamente una sucursal.** La API de sync deriva el tenant
  de las asignaciones de la cuenta y **rechaza (403)** una cuenta con cero
  o con más de una: un hub es de un local, y una cuenta más amplia
  convertiría el sync en una fuga entre locales. El parámetro de sucursal
  no existe en la API — no hay forma de pedir datos de otro local.
- **`sync.leer` es el único permiso del ERP que devuelve `pin_hash`.** Sin
  el hash replicado nadie puede autenticarse en el hub durante un corte, y
  un PDV donde nadie puede loguearse no vende. Viaja el hash Argon2id,
  nunca el PIN, y solo el de los usuarios de esa sucursal. No lo expone
  ningún otro endpoint.
- **`sync.empujar` no escribe filas crudas**: reproduce las ventas del
  corte por los mismos casos de uso que atiende un PDV en línea, con sus
  validaciones y su idempotencia.

Alta: `python -m src.seeders.hub --sucursal <uuid> --username hub_<local>`
(ver `docs/engineering/devops.md`).

### Cuentas de agente: token de API, no PIN (ADR-032)

Un `usuario` con `tipo=agente_ia` se autentica con un **token de API de
larga vida** (`token_agente`), emitido y revocado con `users.gestionar`
desde `/api/v1/users/{id}/tokens`. El PIN de 6 dígitos es un secreto de 20
bits para un proceso desatendido, y su lockout de 5 intentos es un modo de
falla que apaga integraciones.

Lo que **no** cambia: el token identifica al usuario y de ahí salen sus
roles, permisos, restricciones y sucursales igual que en cualquier login
(RN-GEN-004). Un agente sigue pudiendo exactamente lo que su rol le da —
`agente_ia` es `sales.crear_pedido` y nada más. Un usuario `humano` no
puede tener token (409), y el `tipo` se revalida en cada request.

El hub de sucursal todavía usa username + PIN (`cloud_sync_*`); migrarlo
obliga a rotar el secreto en cada local y está anotado en ROADMAP → Deuda
técnica.
