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

> La matriz completa por módulo se define al implementar cada módulo y su
> conjunto de acciones.
