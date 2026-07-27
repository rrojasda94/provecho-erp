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
| Marca | Supervisor de una sola marca |
| Sucursal | Cajero atado a su(s) local(es) (`usuario_sucursal`) |
| Almacén | Almacenero limitado al almacén central |
| Módulo | Rol sin acceso al módulo de contabilidad |

## Reglas de autorización

- **Deny por defecto**: sin permiso explícito, la acción se rechaza (403).
- El alcance sale de los claims del JWT + asignaciones del usuario, nunca del
  body del request sin verificar.
- Un permiso sin restricción aplica a todo el alcance del usuario; con
  restricción, solo donde la condición se cumple.
- Cambios de roles/permisos se auditan.

## Matriz de permisos (semilla)

| Rol | Permisos base |
|-----|---------------|
| admin | `*` (todo, solo entornos internos) |
| supervisor | `inventory.*`, `purchases.aprobar`, `sales.leer`, aprueba solicitudes |
| almacenero | `inventory.transferir`, `inventory.recepcion`, `inventory.ajustar` |
| cajero | `sales.crear`, `sales.cobrar`, `sales.leer` (su sucursal) |
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
