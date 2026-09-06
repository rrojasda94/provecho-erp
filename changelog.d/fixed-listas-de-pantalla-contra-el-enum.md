- **Una lista de la pantalla que se separa del enum no falla: ofrece un valor
  que la API rechaza recién al guardar** (2026-09-05, hallazgo #15 de la
  auditoría del 2026-08-30). El repo tenía dos pruebas de coherencia escritas
  a mano —los motivos de descuento del PDV y los estados de la jornada— y
  quince listas más con el mismo riesgo y ninguna prueba. Ahora es **una
  prueba parametrizada** que lee el `Enum` del modelo —no una copia— y lo
  compara con la lista de la pantalla: sumar una es agregar una fila, que era
  el punto de extenderla en vez de escribir la prueba número dieciséis.
  **Encontró una de entrada**: el diálogo de amonestación del legajo ofrecía
  «suspensión», que no es un valor de `amonestacion.tipo` — elegirla terminaba
  en un 422 al firmar la sanción.
- **`{ id, nombre }` estaba declarado diecinueve veces** (2026-09-05, mismo
  hallazgo): `Sucursal` once, `Categoria` cuatro, `Marca` tres, `Almacen` dos.
  Con la duplicación vino algo peor — pantallas importando el tipo de **otra
  pantalla**, que acopla dos vistas por un detalle que no es de ninguna de las
  dos. Viven ahora en `lib/catalogos.ts`.
  Costo aceptado: ahí van **solo las formas de referencia**, lo que hace falta
  para llenar un `<select>`. La ficha completa de una sucursal se sigue
  declarando donde se administra: un tipo compartido que crece con cada campo
  que alguna pantalla necesita deja de compartir nada.
