# ADR-061 — El centro de labores no es el alcance de datos

- Estado: aceptado
- Fecha: 2026-08-24
- Contexto: `rrhh` (trabajador), `users` (usuario, sucursal, `usuario_sucursal`)
- Relacionado: ADR-004 (tenant por filtro de aplicación), RN-RRHH-008 (usuario
  ≠ trabajador), RN-RRHH-011 (reemplazo entre sucursales), RN-RRHH-019 (el
  centro de labores es de la empresa del trabajador),
  `docs/security/authorization.md`

## Contexto

No había forma de decir en el ERP **dónde trabaja** una persona ni **qué
locales alcanza** su cuenta. Dos huecos que desde la pantalla se veían como
uno solo — "no puedo asignar a los trabajadores a una sucursal":

1. `trabajador` llevaba `empresa_id` y nada más. Sin local, la asistencia no
   tenía a qué sucursal atribuirse, el contrato no podía decir dónde se presta
   el servicio y el reemplazo entre locales (RN-RRHH-011) no era representable.
2. `usuario_sucursal` existía y sus endpoints funcionaban desde el slice
   inicial, pero **no había pantalla**: fuera del seeder nadie podía asignar un
   local a una cuenta. Y el endpoint no verificaba tenant ni auditaba, así que
   quien administraba las cuentas de su empresa podía colgar un usuario a la
   sucursal de otra empresa del grupo sin dejar rastro.

## Decisión

### 1. Son dos conceptos distintos y quedan separados

`trabajador.sucursal_id` (nuevo, nullable) es el **centro de labores**: un
hecho laboral. Aparece en el contrato, manda en asistencia y planilla, y existe
aunque la persona no tenga cuenta en el ERP — un cocinero sin login trabaja en
un local igual.

`usuario_sucursal` (ya existía) es el **alcance de datos**: autorización. Sale
del JWT (`src/core/tenant.py`), lo reparte quien tiene `users.gestionar` y
cambiarlo no toca la relación laboral.

Fusionarlos habría sido cómodo y falso. Un supervisor **trabaja** en un local y
**ve** cuatro; un contador de oficina no trabaja en ninguno y los ve todos;
un cajero que cubre un turno prestado sigue en planilla de su local. Con una
sola columna, cada uno de esos casos obliga a elegir cuál de los dos
significados se sacrifica.

Es nullable a propósito: gerencia y administración no están en ningún local, y
los trabajadores que ya existían no tienen sucursal.

### 2. Un supervisor sobre varias sucursales no necesita entidad nueva

`usuario_sucursal` ya es N a N: el supervisor lleva tres filas. La pantalla
muestra chips y se agregan de a uno.

Se descartó una tabla `zona` (grupo nombrado de sucursales) porque hoy no hay
nada que colgarle: ningún reporte agrupa por zona, ningún permiso se define
por zona y ninguna regla de negocio la nombra. Sería una entidad más en el
modelo —con su alcance de tenant, su seeder y su CRUD— para ahorrar dos clics.
Cuando un reporte o una regla necesiten **nombrar** el conjunto, la zona se
justifica sola; ahí se agrega.

También se descartó `trabajador_sucursal` (varias sucursales por trabajador,
del lado de RRHH): duplicaría `usuario_sucursal` con otro nombre y obligaría a
decidir cuál manda cuando las dos difieran.

### 3. El alcance viaja en el token, y eso se dice en la pantalla

`sucursales` es un claim del JWT: asignar o quitar un local **no** le cambia
nada a una sesión ya abierta hasta que renueve (refresh o login). No se agregó
revocación inmediata —sería invalidar tokens vivos por un cambio de alcance,
maquinaria nueva para un caso que se resuelve volviendo a entrar—; se agregó
la advertencia en la pantalla, que es lo que faltaba de verdad.

### 4. Asignar alcance se valida contra el tenant y se audita

`asignar_sucursal` y `quitar_sucursal` ahora exigen que la sucursal sea de la
empresa del que administra y registran en `audit_log`. El superusuario queda
afuera del chequeo por el mismo motivo que en el alta de sucursales: administra
el grupo entero y el seeder lo ata a una empresa solo para que el resto del ERP
le funcione.

Repartir acceso a datos sin rastro dejaba sin respuesta la pregunta "quién
podía ver este local y desde cuándo". Por eso se audita también el quite: es la
otra mitad de esa pregunta.

## Consecuencias

- RRHH puede decir dónde trabaja cada persona; el alcance de acceso se reparte
  en Usuarios → Cuentas y las dos cosas se editan por separado.
- Migración `b6d29f10c47e`: una columna nullable, sin backfill. Los
  trabajadores que ya existen quedan sin centro de labores hasta que alguien
  se los asigne.
- `TrabajadorUpdate.sucursal_id` es el único campo del PATCH donde un `null`
  explícito **borra** en vez de significar "no tocar" — quedarse sin local es
  un estado válido y no había otra forma de volver a él.
- Queda pendiente (deuda en `ROADMAP.md`): `quitar_rol` sigue sin auditar, y un
  alcance de marca de verdad en el JWT si un supervisor termina cargando
  demasiadas sucursales sueltas.
