# ADR-093 — El conteo cierra y arma el borrador

- Estado: aceptado
- Fecha: 2026-09-06
- Contexto: `src/modules/inventory/application/conteos.py`,
  `src/modules/inventory/application/solicitudes.py`,
  `frontend/app/(app)/inventario/solicitudes/`
- Relacionado: ADR-019 (conteo cíclico por categoría), ADR-051 (el
  requerimiento de la jornada), RN-INV-013, RN-INV-023, RN-INV-026

## Contexto

`docs/domain/workflows.md` §Abastecimiento de locales, paso 4, describe que
el conteo **genera** el borrador de requerimiento. Desde ADR-051
(2026-08-19) eso no pasaba: `borrador_del_almacen` arma la lista sola con lo
que está bajo `stock_minimo` **al abrir la pantalla**, independiente de
ADR-019. El SOP describía un flujo que el código no tenía — quedó anotado
como deuda técnica y como una decisión pendiente: ¿todo cierre de conteo
dispara un borrador, o solo el conteo general?

## Decisión

**Todo cierre dispara el refresco, sin distinguir conteo general de conteo
por categoría.** La alternativa —solo el general— exige que el código sepa
distinguir los dos casos y que quien cuenta una sola categoría entienda por
qué su cierre no actualiza nada. Es una distinción que no protege contra
ningún error real: `borrador_del_almacen` es **aditivo**
(`refrescar_sugerencias` no pisa lo ya tecleado, RN-INV-023), así que
dispararlo de más no tiene costo — en el peor caso agrega antes lo que se
iba a agregar solo al abrir la pantalla.

**La llamada es directa, no un evento.** `conteos.cerrar_conteo` invoca
`solicitudes.borrador_del_almacen` en el mismo módulo — las dos funciones
viven en `inventory/application/`. El bus de eventos (`src/core/events.py`)
existe para el límite **entre** módulos (CLAUDE.md: "los módulos se
comunican entre sí SOLO vía eventos"); no hay en todo el repo un caso de un
módulo suscrito a su propio evento, y crear uno acá sería indirección sin
ningún desacople que ganar — el emisor y el consumidor son el mismo código,
en el mismo commit, con el mismo dueño.

**Un almacén sin abastecedor no rompe el cierre.** El almacén central no
tiene abastecedor propio —es el principio de la cadena— y
`_abastecedor_valido` lo rechaza con `ReglaNegocio` al intentar armar un
borrador nuevo para él. Cerrar el conteo no puede depender de eso: es una
consecuencia del cierre, no una condición. `cerrar_conteo` atrapa
`(ReglaNegocio, NoEncontrado)` alrededor de la llamada y sigue — el conteo
cierra igual, sin borrador.

## Consecuencias

- Nueva regla **RN-INV-026** en `docs/domain/business-rules.md`.
- El desfase que la deuda ya anotaba sigue existiendo y no lo resuelve este
  ADR: el borrador se arma con el `stock_minimo` contra el stock del
  almacén, y el ajuste que el conteo genera queda **pendiente** — el stock
  no se corrige hasta que alguien lo apruebe. Un borrador armado al cerrar
  un conteo con diferencias grandes puede sugerir de menos hasta que el
  ajuste se aprueba. No se fuerza el orden (aprobar antes de sugerir)
  porque eso bloquearía el borrador por un aprobador que puede tardar días.
