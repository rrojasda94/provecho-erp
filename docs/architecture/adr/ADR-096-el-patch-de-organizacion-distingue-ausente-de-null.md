# ADR-096: El PATCH de organización distingue "ausente" de "`null` explícito"

## Estado

Aceptado (2026-09-06)

## Contexto

La convención del PATCH en todo el ERP es "un campo ausente o `null` = no
tocar" (`users/api/schemas.py`). Sirve para editar un solo campo sin repetir
los demás, pero no deja ningún camino para **vaciar** un opcional: no se
puede quitar el almacén abastecedor de un almacén, ni su respaldo, ni
desactivar el `radio_marcaje_m` de una sucursal una vez puesto. El selector
del frontend ya ofrece "Ninguno" y no hacía nada — el valor vacío se perdía
en la conversión a `undefined` de la capa de acciones, y aunque hubiera
llegado como `null`, `organizacion._aplicar` lo trataba igual que un campo
no enviado.

El precedente ya existe en el propio código: `admin.editar_usuario`
(ADR-070) resuelve el mismo problema con `model_dump(exclude_unset=True)` en
el router más un `_BORRABLES_USUARIO` explícito en la aplicación. Las cinco
entidades de organización (Grupo, Empresa, Marca, Sucursal, Almacén) no
seguían ese patrón.

## Decisión

Las cinco entidades de organización adoptan el mismo mecanismo:

- Los cuatro routers PATCH (`editar_empresa`, `editar_marca`,
  `editar_sucursal`, `editar_almacen`) pasan a
  `body.model_dump(exclude_unset=True)`. Esto hace que Pydantic solo incluya
  las claves que el cliente **envió**, sin importar su valor.
- `organizacion._aplicar` deja de leer con `campos.get(campo)` (que no puede
  distinguir "no vino" de "vino en `null`") y pasa a iterar con
  `if campo not in campos: continue`, comparando presencia en el dict en vez
  de verdad del valor.
- Un nuevo parámetro `borrables: frozenset[str]` en `_aplicar` dice qué
  campos aceptan `None` como valor válido a escribir; el resto de los
  campos, si llegan en `None`, no se tocan (protege contra un cliente que
  mande `{"nombre": null}` por error). Cada `editar_*` declara su propio
  whitelist:
  - `BORRABLES_EMPRESA = {"contacto", "config_fiscal", *CAMPOS_UBICACION}`
  - `editar_marca`: `{"skins"}`
  - `editar_sucursal`: `{"horario_atencion", "radio_marcaje_m", *CAMPOS_UBICACION}`
  - `editar_almacen`: `{"direccion", "sucursal_id", "almacen_abastecedor_id",
    "almacen_abastecedor_respaldo_id", *CAMPOS_UBICACION}`
- Grupo no gana ningún borrable: su único campo editable (`nombre`) es
  obligatorio y nunca se vacía.

## Efectos de segundo orden (mismo cambio, no aparte)

- **`editar_almacen`** derivaba sus valores de validación (`tipo`,
  `sucursal_id`, `almacen_abastecedor_id`, `..._respaldo_id`) con
  `campos.get(x) or almacen.x`. Ese patrón descarta un `None` intencional
  igual que uno ausente. Se cambia a `campos[x] if x in campos else
  almacen.x`, que sí distingue las tres situaciones.
- **`ubicacion.desanclar_si_cambio_el_texto`** decidía si desanclar leyendo
  `campos.get(campo_texto)` — el texto crudo de la request. Con el
  centinela nuevo, un campo de texto no-borrable (p. ej. `sucursal.direccion`,
  que sigue sin poder vaciarse) puede llegar en `null` explícito sin que
  `_aplicar` lo aplique, y la función interpretaba ese `null` como "cambió a
  vacío" y desanclaba igual. Se corrige leyendo `getattr(entidad,
  campo_texto)` — el valor **ya aplicado** a la entidad, después de
  `_aplicar` — que refleja lo que de verdad cambió y no lo que el cliente
  pidió.

## Consecuencias

- Es un cambio de contrato: antes, un cliente que mandaba el modelo completo
  con un campo en `null` no vaciaba nada; ahora, si ese campo está en la
  lista de borrables, sí lo vacía. Ningún cliente actual del ERP dependía del
  comportamiento viejo (los formularios de organización nunca ofrecían
  vaciar estos campos hasta este cambio).
- El frontend (`organizacion/actions.ts`) pasa a mandar `null` explícito en
  los dos selectores de abastecimiento en vez de `undefined` cuando el
  usuario elige "Ninguno".
- El contrato OpenAPI no cambia de forma (los `*Update` siguen siendo los
  mismos campos opcionales); lo que cambia es la semántica en tiempo de
  ejecución, invisible al esquema.

## Alternativas consideradas

- **Un valor centinela dedicado** (p. ej. una clase `NO_ENVIADO`) en vez de
  `exclude_unset=True`: más explícito por campo, pero reinventa lo que
  Pydantic ya resuelve y ADR-070 ya adoptó — habría dos mecanismos para el
  mismo problema en el mismo módulo.
- **Un DELETE de sub-recurso por campo** (p. ej.
  `DELETE /almacenes/{id}/abastecedor`): correcto en teoría REST, pero son
  nueve endpoints nuevos para un problema que el PATCH ya resuelve con un
  campo de más en el body.

## Nota de coordinación

Esta rama (`fix/transversal-patch-vaciar-un-opcional`) se escribió en
paralelo con `fix/transversal-relojes-documento-y-cache` (mergeada como
ADR-095) y el bloque de `inventory` (ADR-090 a 094), sobre el mismo `main`
que entonces terminaba en 089. Renumerada a 096 al mergear.
