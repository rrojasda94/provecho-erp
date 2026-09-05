- **Un rechazo del servidor dejaba de borrar lo tecleado en quince diálogos
  más** (2026-09-04, auditoría del 2026-08-30 §4). React 19 resetea los campos
  no controlados de un `<form>` cuando su acción termina, **también cuando
  devolvió error**: errarle a un dato de la factura del proveedor borraba
  serie, número y total ya escritos. `DialogoFormulario` lo resuelve
  despachando la acción a mano dentro de una transición, y ahora lo usan
  también Campañas (alta y brief), Contenido, Gerencia → Decisiones, Caja
  (firma de custodia y alta de terminal), Gerencia → Parámetros (proponer),
  Producción (orden, consumo y control de calidad), Órdenes de compra (alta,
  corrección, recepción y factura) y la nota de crédito de la jornada.
- **El tablero de contratación tenía su propio `DialogoFormulario`, con el
  mismo nombre** (2026-09-04). Una copia entera del molde, con su propio
  `EstadoRrhh` en vez de `EstadoFormulario` y sin el arreglo de React 19 ni el
  marcado de campos del 422 — dos componentes distintos llamados igual en el
  mismo repositorio. Queda un envoltorio de siete líneas sobre el molde común.
- **Cinco diálogos con estado propio abrían con los datos del anterior**
  (2026-09-04). Las líneas de consumo de producción, el veredicto de calidad,
  el resultado de un acta y las filas de una orden de compra son campos
  controlados, y `form.reset()` no los toca: la orden siguiente abría con los
  insumos de la anterior. Ahora se limpian al abrir — al abrir y no al enviar,
  para que un rechazo del servidor deje ver lo que se había cargado.
- **Corregir una orden de compra ya no abre un formulario vacío**
  (2026-09-04). Pedía sus ítems a la API *después* de abrir el diálogo, con
  un «Cargando...» que se reemplazaba solo un segundo más tarde. El molde
  acepta ahora un `alAbrir` asíncrono y espera antes de mostrar; lo mismo la
  nota de crédito, que carga las líneas acreditables.
- **`DialogoFormulario` acepta el ancho del panel** (2026-09-04). Nació
  clavado en `max-w-md` para formularios de una columna; una recepción de OC
  es `max-w-3xl` y a ese ancho cada línea se partía en tres renglones.
- **Lo que no se migró, y por qué**: `DialogoResolver` de Gerencia →
  Parámetros no es un diálogo-formulario sino un `<dialog>` con dos `<form>`
  independientes —aprobar y rechazar— con dos estados y un pie propio.
  Agrandar el molde para un solo llamador es peor negocio que dejarlo
  declarado en `docs/roadmap/deuda/frontend.md`. Fuera de alcance también los
  cinco diálogos de Catálogo y el importador de planilla, que no usan Server
  Actions sino `fetch` + `useState`: migrarlos es reescribirlos, no moverlos.
