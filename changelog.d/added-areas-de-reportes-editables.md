- **El mapa de distribución mostraba los huecos y no había cómo taparlos**
  (2026-09-05, Ola 3 de la auditoría del 2026-08-30). `/reportes/distribucion`
  marca en rojo los **huecos** —un hecho que ocurre y no se entera nadie— y
  las **fugas** —una regla sin destinatarios—, y el CRUD para arreglarlos
  existía en el backend desde ADR-033 sin que ninguna pantalla lo llamara.
  Ahora `/reportes/areas` crea áreas, las renombra, las desactiva y les suma
  o quita miembros. Un miembro es **un rol o una persona, nunca las dos**: el
  rol es «quien ocupe ese puesto» y sobrevive al cambio de gente, la persona
  es esa persona, y mezclarlos dejaría sin saber cuál manda cuando el puesto
  cambia de manos. El código del área no se edita —las reglas lo nombran— y un
  área sin miembros se dice en la pantalla: recibe y no se lo pasa a nadie,
  que es la mitad de una fuga.
  Costo aceptado: **editar las reglas** sigue siendo por API. Una regla lleva
  código de emisión, nivel, canal, sucursal y destinatarios de cuatro tipos
  distintos: es una pantalla propia, no un diálogo. Queda anotado como deuda.
