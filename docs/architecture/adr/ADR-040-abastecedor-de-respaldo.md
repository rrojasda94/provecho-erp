# ADR-040 — Almacén abastecedor de respaldo

- Estado: aceptado
- Fecha: 2026-08-12

## Contexto

Un almacén declara de quién se abastece (`almacen.almacen_abastecedor_id`,
ADR-020) y `crear_solicitud` lo usa cuando la solicitud no nombra otro. Con un
solo abastecedor, el día que ese almacén no está la sucursal no puede pedir
nada: `_abastecedor_valido` responde `almacén abastecedor no encontrado`, que
no le dice a nadie qué hacer.

No es hipotético. `DELETE /almacenes/{id}` **permite** dar de baja un almacén
que nadie usa como abastecedor, pero si se lo da de baja mientras otros
dependen de él —o si se lo da de baja y se olvida de repuntar a los locales—
el ciclo de abastecimiento del local queda roto sin aviso.

## Decisión

### 1. El respaldo es una columna de `almacen`, no de `sucursal`

`almacen.almacen_abastecedor_respaldo_id`, auto-FK nullable, junto al
principal.

Se evaluó ponerlo en `sucursal` —que es donde el usuario lo pidió— y se
descartó: **el que se abastece es el almacén**, no la sucursal. Una sucursal
puede tener más de uno (salón y cocina) y no tienen por qué abastecerse del
mismo lado. Guardar el par en `sucursal` sería una segunda fuente de la misma
verdad, y la primera pregunta al leerla sería "¿y si los almacenes dicen otra
cosa?".

**Dónde se edita es una decisión de pantalla, no de modelo**: el formulario de
Sucursal muestra los dos selectores y guarda sobre el almacén de esa sucursal,
porque es ahí donde uno los busca. Con más de un almacén la pregunta deja de
tener una sola respuesta y la pantalla lo dice, en vez de elegir por el
usuario cuál de los dos configura.

### 2. El respaldo entra solo cuando el principal no está vigente

`crear_solicitud` sin abastecedor explícito toma el principal; si el principal
está dado de baja, toma el respaldo (RN-INV-022).

**Un abastecedor pedido a mano NO cae al respaldo.** Quien nombra un almacén
está pidiendo a ese; darle otro en silencio sería despachar desde donde no se
pidió, y el que recibe no tendría cómo notarlo hasta contar la mercadería.

**"No vigente" es estar dado de baja, no estar sin stock.** Un respaldo que se
activara por faltante exigiría consultar stock de dos almacenes en cada
solicitud y volvería la elección impredecible: la misma solicitud, dos
minutos después, pediría a otro lado. El faltante ya tiene su camino —la
solicitud se aprueba por lo que hay (RN-INV-001/002)— y quien quiera otro
almacén puede nombrarlo.

### 3. Un respaldo igual al principal es un error, no un caso

Se rechaza al guardar: el día que el principal no esté, tampoco estará él. Es
la única validación propia que agrega; el resto —misma empresa, no ser uno
mismo— reusa la del principal.

### 4. Dar de baja mira también a quien lo tiene de respaldo

`AlmacenRepo.abastecidos_por` pasa a contar las dos columnas. Un respaldo que
apunta a un almacén borrado es peor que no tener respaldo: nadie se entera
hasta el día que hace falta.

### 5. Viaja al hub

`almacen` se replica a la sucursal (ADR-009) y el respaldo va con él, por el
mismo motivo por el que en 2026-08-07 hubo que agregar el principal: durante
un corte el local tiene que poder pedir, y un corte de red es exactamente
cuando no se puede ir a consultar quién es el suplente.

## Alternativas descartadas

- **El par en `sucursal`**: segunda fuente de la misma verdad (ver §1).
- **Una lista ordenada de abastecedores** (`orden` en una tabla puente): más
  general y sin caso que la pida. Con dos alcanza para lo que la operación
  hace hoy; el día que haya tres, la tabla se justifica.
- **Respaldo por falta de stock**: impredecible y caro en consultas (ver §2).
- **Fallback también para el abastecedor explícito**: despacharía desde donde
  no se pidió.

## Consecuencias

- Migración `a7c04e3b91d5`, sin backfill: nadie tiene respaldo hasta que
  alguien lo elija.
- El mensaje de "sin abastecedor" cambia de *configurado* a **vigente**: ahora
  cubre también el principal dado de baja sin respaldo. Prueba actualizada.
- Queda anotado en Deuda técnica que el selector no permite **borrar** un
  abastecedor ya puesto: los `PATCH` de organización tratan `null` como "no
  tocar" (convención de `schemas.py`), así que elegir "Ninguno" no lo limpia.
  Es una limitación previa a este cambio que ahora tiene un campo más.
