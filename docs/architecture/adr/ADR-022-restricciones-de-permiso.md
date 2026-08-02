# ADR-022 — Restricciones de permiso (monto/estado/horario)

- Estado: aceptado
- Fecha: 2026-08-02

## Contexto

CLAUDE.md declara la jerarquía de RBAC como
`Usuario → Rol → Permisos → Acciones → Restricciones → Sucursales → Empresa
→ Datos`. `permiso.restricciones` (JSONB) existe en el esquema desde el
slice inicial de `users`, pero nada lo leía: `rules.permite` solo comparaba
el código del permiso contra el comodín `*`, y `require_permission`/
`check_permission` no tenían forma de recibir el dato real de la operación
(monto, estado, hora) contra el que evaluar una condición. El campo era
descriptivo, no aplicado — deuda declarada explícitamente en
`users/README.md` y en el backlog transversal del ROADMAP.

Esto es distinto del umbral de aprobación que ya existe en `purchases`
(`purchases.aprobar` sobre `parametro_empresa`, ver ADR-014): ese es un
**umbral único por empresa** que decide qué permiso adicional hace falta.
Lo que faltaba es una condición **por rol, sobre un permiso ya concedido**
— por ejemplo, que el rol `supervisor` pueda autorizar
`sales.aplicar_descuento` pero solo hasta S/50, mientras `gerente` no tenga
tope. Ningún mecanismo existente cubre ese caso.

## Decisión

**Evaluar `permiso.restricciones` en el momento en que el permiso
efectivamente se usa**, no en el momento en que se concede.

- `users.domain.rules.ContextoPermiso` (dataclass pura: `monto`, `estado`,
  `hora`) representa el dato real de la operación.
- `cumple_restricciones(restricciones, contexto)` (pura) evalúa las claves
  soportadas: `monto_maximo`, `estados_permitidos` (lista), `horario`
  (`{"desde": "HH:MM", "hasta": "HH:MM"}`). Una dimensión sin dato en el
  contexto no bloquea — el llamador decide qué exige pasando o no ese campo.
- `UsuarioRepo.restricciones(usuario_id, codigo)` resuelve la restricción
  real del usuario: `None` si tiene el comodín `*`, si ninguno de sus roles
  otorga `codigo`, o si **alguno** de los roles que sí lo otorgan lo hace
  sin condición (basta uno libre para no acotar — mismo criterio OR que
  `rules.permite`).
- `check_permission(session, usuario, *codigos, contexto=None)` (`users/api/deps.py`)
  gana un parámetro opcional: sin él, se comporta exactamente igual que
  antes (retrocompatible con todo llamador existente). Con `contexto`,
  exige además que **alguno** de los códigos otorgados cumpla su
  restricción, o responde 403.
- `require_permission` (el `Depends` sin acceso al body) **no cambia**: una
  condición de monto/estado solo se conoce con el body ya parseado, así que
  sigue siendo trabajo de `check_permission`, tal como su docstring ya
  decía antes de este ADR.

## Primer uso real

`sales.aplicar_descuento`: el router calcula el monto real del descuento
(`ventas.calcular_monto_descuento`, una consulta pura que no persiste nada)
y llama `check_permission(session, autorizante, DESCONTAR,
contexto=ContextoPermiso(monto=monto))` **antes** de aplicar el descuento
— la venta no se toca si la restricción lo frena. `ContextoPermiso` se
re-exporta desde `users/api/deps.py`: es la única superficie de `users` que
otro módulo puede importar (`tests/test_arquitectura.py`), así que ningún
otro módulo importa `users.domain` directo.

No se retrofitea el umbral existente de `purchases.aprobar` (mecanismo
distinto, funcionando, fuera de alcance) ni se inventan usos de
`estados_permitidos`/`horario` sin un caso real que los pida — quedan
soportados por el motor, sin un segundo caller todavía.

## Consecuencias

- `permiso.restricciones` deja de ser solo documentación: un rol puede
  tener el mismo código de permiso que otro con una condición distinta
  (ej. tope de descuento por rol) sin crear un permiso nuevo por cada
  variante.
- Un usuario con el mismo permiso otorgado por dos roles con topes
  distintos toma el **primero que encuentra la consulta** (`ponytail:` en
  `UsuarioRepo.restricciones`) — hoy los datos sembrados nunca duplican un
  código entre roles de un mismo usuario. Fusionar de verdad (tomar el tope
  más permisivo entre todos) queda para cuando esa situación exista.
- La API pública sigue siendo `users/api/deps.py` — `ContextoPermiso` vive
  en `users/domain/rules.py` pero se re-exporta desde ahí para que otros
  módulos no necesiten (ni puedan) importar el dominio de `users`.

## Alternativas descartadas

- **Reutilizar el umbral de `parametro_empresa`** (patrón de `purchases`)
  para el tope de descuento — descartado: ese umbral es único por empresa,
  no por rol; hubiera exigido un umbral por rol fuera del modelo de
  permisos, duplicando lo que `restricciones` ya declara tener.
- **Evaluar restricciones dentro de `require_permission`** — descartado:
  esa dependencia corre antes de que FastAPI parsee el body, así que nunca
  tiene monto/estado disponibles. Forzarlo hubiera exigido mover la lectura
  del body a la dependencia, rompiendo el patrón establecido de
  `check_permission` para este caso exacto.
